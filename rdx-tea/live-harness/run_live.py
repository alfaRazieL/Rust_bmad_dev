#!/usr/bin/env python3
"""D3.3.1 unified live-harness orchestrator.

The single supported entry point for a live model-driven run. Composes:

    runtime discovery
    → isolated workspace
    → exact run identity (base/head SHA + workflow + scenario)
    → isolated Claude Code invocation
    → transcript reconciliation (post-runtime, separate op)
    → evidence verification (schema + hashes)
    → evidence collection under rdx-tea/evidence/live/<scenario>/<run_id>/
    → crash-safe cleanup (lock/overlay preserved on failure)

Subcommands
-----------
    run-smoke               one scenario × arm × repetition round-trip
    run-one                 same as run-smoke but with explicit run-id
    reconcile-transcript    (idempotent, no rebind, no sidecar changes)
    abort-run               idempotent cleanup with FAILED/ABORTED state

Deliberately NOT a helper library — every operation is invokable from
the command line so a reviewer can walk the lifecycle step by step
without hidden state.

Contract with the schema
------------------------
Every completed evidence bundle validates against
`rdx-tea/live-harness/schemas/live-evidence.v1.schema.json`. The
schema is the SSoT for what "complete" means; `run_live.py` fails
closed if the emitted bundle would not validate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

import collect_evidence
import invoke_runtime
import prepare_workspace
import runtime_discovery


SCHEMA_PATH = _HERE / "schemas" / "live-evidence.v1.schema.json"
SCHEMA_V2_PATH = _HERE / "schemas" / "live-evidence.v2.schema.json"
SCHEMA_V3_PATH = _HERE / "schemas" / "live-evidence.v3.schema.json"
SCHEMA_VERSION = "rdx-tea-live-evidence.v1"
SCHEMA_V2_VERSION = "rdx-tea-live-evidence.v2"
SCHEMA_V3_VERSION = "rdx-tea-live-evidence.v3"
INVOCATION_SCHEMA_VERSION = "rdx-tea-invocation.v1"
AUTH_PREFLIGHT_ID_DEFAULT = "D3_3_3_AUTH_PREFLIGHT"

RDX_TEA_DIR = _HERE.parent
EVIDENCE_ROOT_DEFAULT = RDX_TEA_DIR / "evidence" / "live"

WORKFLOWS = {
    "test-design-async": "test-design",
    "atdd-api-async": "atdd",
    "atdd-api-async-corrected": "atdd",
    "docs-only-rust-repo": "test-design",
}

FIXTURE_DIR = _HERE / "fixtures"

# D3.3.3 §8: default to the exact pinned schedule model ID, never an
# alias. run-smoke/run-one enforce require_exact_model=True downstream.
DEFAULT_MODEL = "claude-haiku-4-5-20251001"
DEFAULT_TIMEOUT_SECONDS = 900
DEFAULT_MAX_BUDGET_USD = 2.00


class OrchestratorError(RuntimeError):
    """Any failure the orchestrator wants to surface as exit-code 2."""


# ---------------------------------------------------------------- utility

def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes()) if path.exists() else ""


def _sha256_text(text: str) -> str:
    return _sha256_bytes(text.encode("utf-8"))


def _sha256_dir_tree(root: Path) -> str:
    """Deterministic hash of every regular file under root (sorted by
    resolved relative path). Used to fingerprint the isolated Claude
    Code config directory so a comparative pilot can prove baseline
    and candidate used byte-identical environments."""
    if not root.exists():
        return _sha256_bytes(b"")
    hasher = hashlib.sha256()
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(root).as_posix().encode("utf-8")
        hasher.update(len(rel).to_bytes(4, "big"))
        hasher.update(rel)
        hasher.update(_sha256_file(p).encode("utf-8"))
    return hasher.hexdigest()


def _atomic_write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)


# ---------------------------------------------------- output deduplication

def _canonicalize_output_roots(roots: Iterable[Path]) -> list[Path]:
    """Collapse nested output roots.

    Given `_bmad-output/` and `_bmad-output/test-artifacts/`, the child
    (test-artifacts) is a descendant of the parent and would double-
    count every artefact if both were scanned. Return only the
    resolved parents — every descendant is walked once.
    """
    canon: list[Path] = []
    resolved = sorted({r.resolve() for r in roots}, key=lambda p: len(p.parts))
    for r in resolved:
        if any(r.is_relative_to(existing) and r != existing for existing in canon):
            continue
        canon.append(r)
    return canon


def _walk_artefacts(canonical_roots: Iterable[Path]) -> list[Path]:
    """Walk canonical roots once; dedupe by resolved path; sort for
    deterministic evidence ordering."""
    seen: set[Path] = set()
    out: list[Path] = []
    for root in canonical_roots:
        if not root.exists():
            continue
        for p in sorted(root.rglob("*")):
            if not p.is_file():
                continue
            resolved = p.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            out.append(p)
    return out


# ------------------------------------------------- isolated Claude config

def arm_installed_skills(arm: str, workflow: str) -> list[str]:
    """D3.3.2 §5.2. Arm-specific installed-skill allowlist.

    Baseline arm MUST NOT see the RDX wrapper skill — otherwise a
    baseline run could be indistinguishable from a candidate run and
    the comparative pilot loses its scientific meaning. Candidate arm
    sees the wrapper (which itself invokes the child).
    """
    child = f"bmad-testarch-{workflow}"
    wrapper = f"rdx-tea-{workflow}"
    if arm == "baseline":
        return [child]
    if arm == "candidate":
        return [wrapper, child]
    raise OrchestratorError(f"unknown arm {arm!r}")


def arm_prompt(arm: str, workflow: str, run_id: str) -> str:
    """D3.3.2 §5.1. Arm-specific prompt.

    Baseline prompt must not mention RDX, wrapper, RP IDs, active-
    context, prepare-run, or finalize-run. Candidate prompt names the
    wrapper explicitly. Both prompts carry the schedule-owned run_id
    so evidence correlation is deterministic.
    """
    if arm == "baseline":
        return (
            f"Invoke the /bmad-testarch-{workflow} skill on the current "
            f"project. Follow every activation step in its SKILL.md. Use "
            f"run_id={run_id} in any output filenames or run identifiers "
            f"where the skill accepts one. Read the story at "
            f"_bmad-run/story.md and tags at _bmad-run/tags.txt if present."
        )
    if arm == "candidate":
        return (
            f"Use the Skill tool to invoke the skill named "
            f"rdx-tea-{workflow} (do NOT expand it as a slash command, and "
            f"do NOT just read its SKILL.md — actually call the Skill "
            f"tool with skill=rdx-tea-{workflow}). That wrapper skill will "
            f"then instruct you to invoke the child skill "
            f"bmad-testarch-{workflow}; invoke that child ALSO via the "
            f"Skill tool. Follow every activation step in the wrapper's "
            f"SKILL.md; do NOT skip the prepare-run or finalize-run "
            f"subcommands. The invocation contract file at "
            f"_bmad-run/rdx-tea-invocation.json pins run_id={run_id}; read "
            f"it first and use its run_id verbatim in every wrapper "
            f"command. Halt on any non-zero exit. When done, summarise the "
            f"run-report.json path."
        )
    raise OrchestratorError(f"unknown arm {arm!r}")


# Official bundled/built-in slash-commands that Claude Code 2.1.x always
# surfaces even under project-only settings. They are the SAME for both
# arms and are classified as runtime_builtins, not contamination.
OFFICIAL_BUNDLED_SLASH_COMMANDS = frozenset({
    "clear", "compact", "config", "context", "heapdump", "init",
    "reload-skills", "review", "security-review", "usage-credits",
    "extra-usage", "usage", "insights", "goal", "team-onboarding",
})

# The subagent-dispatch tool and its lifecycle tools that MUST be denied
# for a sequential pilot (D3.3.3 §9.2).
FORBIDDEN_RUNTIME_TOOLS = ("Task", "TaskOutput", "TaskStop")

# Project settings we request (D3.3.3 §6.2). Names verified against the
# installed CLI; unknown keys are ignored by the CLI rather than fatal.
PROJECT_SETTINGS = {
    "disableBundledSkills": True,
    "disableClaudeAiConnectors": True,
    "autoMemoryEnabled": False,
}


@dataclass
class ProjectRuntimeIsolation:
    """Auth-preserving project runtime isolation (D3.3.3 §6).

    Unlike the D3.3.2 `ClaudeIsolation`, this abstraction NEVER sets
    `CLAUDE_CONFIG_DIR`. It isolates only the PROJECT surface — MCP,
    memory, bundled skills, tools — via project-local files and CLI
    flags, and inherits the user's existing CLI OAuth environment. The
    D3.3.2 approach broke OAuth by pointing CLAUDE_CONFIG_DIR at a temp
    dir; see rdx-tea/research/D3_3_3_PRECONDITION_AUDIT.md §4.

    Physical skill isolation is the responsibility of
    prepare_workspace (arm-specific install into workspace/.claude/
    skills); this class does NOT copy skills anywhere.
    """

    workspace: Path
    arm: str
    workflow: str
    permission_mode: str = "bypassPermissions"

    @property
    def project_skills(self) -> list[str]:
        return arm_installed_skills(self.arm, self.workflow)

    @property
    def settings_path(self) -> Path:
        return self.workspace / ".claude" / "settings.json"

    @property
    def mcp_config_path(self) -> Path:
        return self.workspace / ".claude" / "empty-mcp.json"

    def bootstrap(self) -> None:
        """Write project-only settings + empty MCP config INTO the
        workspace. Never touches ~/.claude or CLAUDE_CONFIG_DIR."""
        claude_dir = self.workspace / ".claude"
        claude_dir.mkdir(parents=True, exist_ok=True)
        self.settings_path.write_text(
            json.dumps(PROJECT_SETTINGS, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        self.mcp_config_path.write_text(
            json.dumps({"mcpServers": {}}, sort_keys=True), encoding="utf-8"
        )

    def env(self) -> dict[str, str]:
        """Inherit the existing auth environment UNCHANGED. The only
        addition is an auto-memory fail-closed guard, which does not
        affect authentication."""
        e = dict(os.environ)
        # D3.3.3 §6.2 extra fail-closed guard. Never override
        # CLAUDE_CONFIG_DIR / never inject an API key.
        e["CLAUDE_CODE_DISABLE_AUTO_MEMORY"] = "1"
        return e

    def setting_sources(self) -> str:
        return "project"

    def disallowed_tools(self) -> list[str]:
        return list(FORBIDDEN_RUNTIME_TOOLS)

    def preflight(self) -> list[str]:
        """D3.3.3 §6/§20: return a list of policy errors, empty if OK.

        Fail-closed BEFORE any token is spent. Asserts:
          - CLAUDE_CONFIG_DIR is NOT being overridden by us;
          - no API key / token helper in our env;
          - project settings + empty MCP exist;
          - workspace .claude/skills matches the arm allowlist exactly
            (physical skill isolation from prepare_workspace).
        """
        errors: list[str] = []
        env = self.env()
        # We must not have injected any auth override.
        if env.get("CLAUDE_CONFIG_DIR") != os.environ.get("CLAUDE_CONFIG_DIR"):
            errors.append("CLAUDE_CONFIG_DIR was modified by isolation.env()")
        if "ANTHROPIC_API_KEY" in env and env.get("ANTHROPIC_API_KEY"):
            errors.append("ANTHROPIC_API_KEY present in isolation env")
        if env.get("CLAUDE_CODE_OAUTH_TOKEN"):
            errors.append("CLAUDE_CODE_OAUTH_TOKEN present in isolation env")
        if not self.settings_path.exists():
            errors.append(f"project settings missing: {self.settings_path}")
        else:
            try:
                data = json.loads(self.settings_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as e:
                errors.append(f"settings.json invalid: {e}")
                data = {}
            if data.get("autoMemoryEnabled") is not False:
                errors.append("settings.autoMemoryEnabled must be false")
        if not self.mcp_config_path.exists():
            errors.append(f"empty MCP config missing: {self.mcp_config_path}")
        else:
            try:
                mdata = json.loads(self.mcp_config_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as e:
                errors.append(f"empty-mcp.json invalid: {e}")
                mdata = {}
            if mdata.get("mcpServers"):
                errors.append("empty-mcp.json contains servers; expected empty")
        skills_dir = self.workspace / ".claude" / "skills"
        if not skills_dir.exists():
            errors.append(f"workspace skills dir missing: {skills_dir}")
        else:
            present = sorted(p.name for p in skills_dir.iterdir() if p.is_dir())
            expected = sorted(self.project_skills)
            if present != expected:
                errors.append(
                    f"workspace skills {present} != arm-expected {expected}"
                )
        return errors


# Backwards-compatible alias — the D3.3.2 name now maps to the
# auth-preserving class so any lingering import does not silently
# resurrect the CLAUDE_CONFIG_DIR override.
ClaudeIsolation = ProjectRuntimeIsolation


# ------------------------------------------------------- invocation contract

def emit_invocation_contract(*, workspace: Path, run_id: str, scenario: str,
                             arm: str, workflow: str, repetition: int,
                             base_sha: str, head_sha: str,
                             fixture_hash: str, prompt_hash: str) -> Path:
    """D3.3.2 §6.2. Write the invocation.json read by the wrapper skill
    so schedule-owned run_id is used verbatim end-to-end."""
    target = workspace / "_bmad-run" / "rdx-tea-invocation.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": INVOCATION_SCHEMA_VERSION,
        "run_id": run_id,
        "scenario": scenario,
        "arm": arm,
        "workflow": workflow,
        "repetition": repetition,
        "base_sha": base_sha,
        "head_sha": head_sha,
        "fixture_hash": fixture_hash,
        "prompt_hash": prompt_hash,
    }
    _atomic_write_json(target, payload)
    return target


# --------------------------------------------------- structured JSON lock

def _lock_path(workspace: Path) -> Path:
    return workspace / "_bmad" / "rdx-tea" / "runtime" / "active-run.lock"


def _read_lock_json(workspace: Path) -> dict | None:
    """Return the structured lock content, or None if lock is absent or
    unreadable JSON. Legacy string locks are treated as `None` to force
    an explicit ownership decision instead of substring guessing."""
    lp = _lock_path(workspace)
    if not lp.exists():
        return None
    text = lp.read_text(encoding="utf-8")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _lock_owned_by(workspace: Path, run_id: str, workflow: str) -> bool:
    data = _read_lock_json(workspace)
    if data is None:
        return False
    return data.get("run_id") == run_id and data.get("workflow") == workflow


def write_lock_json(workspace: Path, *, run_id: str, workflow: str,
                    pid: int | None = None) -> Path:
    lp = _lock_path(workspace)
    lp.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "run_id": run_id,
        "workflow": workflow,
        "pid": pid if pid is not None else os.getpid(),
        "created_at": _utc_now(),
    }
    _atomic_write_json(lp, payload)
    return lp


# ------------------------------------------------------- init event parser

def _extract_runtime_init(transcript_path: Path) -> dict:
    """D3.3.2 §9. Read stream-json `system`/`init` events and record the
    ACTUAL surface reported by Claude Code — model, permission_mode,
    tools, skills, slash_commands, mcp_servers, plugins, memory paths.

    We tolerate schema drift: unknown fields land in `raw`. Absent
    fields are empty lists, not omitted, so downstream diffing is
    tractable.
    """
    surface = {
        "claude_code_version": "",
        "model": "",
        "permission_mode": "",
        "tools": [],
        "skills": [],
        "slash_commands": [],
        "mcp_servers": [],
        "plugins": [],
        "memory_paths": [],
        "session_id": "",
        # D3.3.3 §10.2 extra fields.
        "api_key_source": "",
        "agents": [],
        "analytics_disabled": None,
        "output_style": "",
        "fast_mode_state": "",
        "init_event_seen": False,
        "raw": {},
    }
    if not transcript_path.exists():
        return surface
    for line in transcript_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        etype = str(event.get("type", "")).lower()
        subtype = str(event.get("subtype", "")).lower()
        is_init = (etype == "system" and subtype == "init") or etype == "init"
        if not is_init:
            # Fall back: some builds attach the init payload to the first
            # event under a `session` block.
            if etype == "system" and "tools" in event:
                is_init = True
        if not is_init:
            continue
        surface["init_event_seen"] = True
        surface["claude_code_version"] = str(event.get("claude_code_version")
                                             or event.get("version") or "")
        surface["model"] = str(event.get("model") or "")
        surface["permission_mode"] = str(event.get("permission_mode")
                                          or event.get("permissionMode") or "")
        for key in ("tools", "skills", "slash_commands", "mcp_servers",
                    "plugins", "agents"):
            v = event.get(key)
            if isinstance(v, list):
                surface[key] = [
                    (i.get("name") if isinstance(i, dict) and "name" in i else i)
                    for i in v
                ]
        # D3.3.3 §10.1 — memory_paths may be dict / list / str / null.
        # Normalise to a sorted list of path strings WITHOUT collapsing
        # a populated dict to a false empty list.
        surface["memory_paths"] = _normalise_memory_paths(event.get("memory_paths"))
        # D3.3.3 §10.2 extra fields.
        surface["api_key_source"] = str(event.get("apiKeySource")
                                         or event.get("api_key_source") or "")
        surface["analytics_disabled"] = event.get("analytics_disabled")
        surface["output_style"] = str(event.get("output_style") or "")
        surface["fast_mode_state"] = str(event.get("fast_mode_state") or "")
        # Session id often on init event.
        sid = event.get("session_id") or event.get("sessionId")
        if sid:
            surface["session_id"] = str(sid)
        surface["raw"] = event
        break
    return surface


def _normalise_memory_paths(v) -> list[str]:
    """D3.3.3 §10.1. Accept dict / list / str / null; never collapse a
    populated dict into a false empty list."""
    if v is None:
        return []
    if isinstance(v, str):
        return [v] if v else []
    if isinstance(v, dict):
        out: list[str] = []
        for key, val in sorted(v.items()):
            if isinstance(val, str) and val:
                out.append(f"{key}:{val}")
            elif val:
                out.append(f"{key}:{val!r}")
        return out
    if isinstance(v, list):
        return [
            (i.get("path") if isinstance(i, dict) and "path" in i else str(i))
            for i in v
        ]
    return [str(v)]


def compare_runtime_surface(observed: dict, expected: dict) -> dict:
    """D3.3.2 §9. Return a structured diff between observed and expected
    runtime surfaces. `RUN_INVALID_RUNTIME_CONTAMINATION` fires when any
    of the diffs below is populated."""
    diff = {
        "unexpected_tools": sorted(set(observed.get("tools", []))
                                    - set(expected.get("tools", []))),
        "missing_expected_skills": sorted(set(expected.get("skills", []))
                                           - set(observed.get("skills", []))),
        "unexpected_skills": sorted(set(observed.get("skills", []))
                                     - set(expected.get("skills", []))),
        "unexpected_mcp_servers": sorted(set(observed.get("mcp_servers", []))
                                          - set(expected.get("mcp_servers", []))),
        "unexpected_plugins": sorted(set(observed.get("plugins", []))
                                      - set(expected.get("plugins", []))),
        "model_mismatch": (
            observed.get("model", "") != ""
            and expected.get("model", "") != ""
            and observed["model"] != expected["model"]
        ),
        "permission_mode_mismatch": (
            observed.get("permission_mode", "") != ""
            and expected.get("permission_mode", "") != ""
            and observed["permission_mode"] != expected["permission_mode"]
        ),
    }
    return diff


def contamination_reason(diff: dict) -> str | None:
    if diff.get("unexpected_mcp_servers"):
        return "unexpected_mcp_servers"
    if diff.get("unexpected_plugins"):
        return "unexpected_plugins"
    if diff.get("unexpected_skills"):
        return "unexpected_skills"
    if diff.get("model_mismatch"):
        return "model_mismatch"
    if diff.get("permission_mode_mismatch"):
        return "permission_mode_mismatch"
    return None


# ---------------------------------------------------- runtime result + outcome

# D3.3.3 §11.2 run outcome enum.
RUN_OUTCOMES = (
    "AUTH_FAILURE",
    "RUNTIME_FAILURE",
    "TIMEOUT",
    "CONTAMINATION",
    "RUN_ID_MISMATCH",
    "WORKFLOW_FAILURE",
    "VERIFIER_FAILURE",
    "SCHEMA_FAILURE",
    "SUCCESS",
)


def extract_runtime_result(transcript_path: Path) -> dict:
    """Read the terminal `result` event and any authentication error.

    D3.3.3 §10.3 / §11.1. Auth status is judged by the COMBINATION of
    exit code, result.is_error, and error type — never by apiKeySource.
    """
    result = {
        "result_event_seen": False,
        "is_error": None,
        "subtype": "",
        "api_error_status": None,
        "terminal_reason": "",
        "result_text": "",
        "authentication_failed": False,
        "model_turn_seen": False,
    }
    if not transcript_path.exists():
        return result
    for line in transcript_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        etype = str(event.get("type", "")).lower()
        if etype == "assistant":
            result["model_turn_seen"] = True
            if str(event.get("error", "")).lower() == "authentication_failed":
                result["authentication_failed"] = True
        if etype == "result":
            result["result_event_seen"] = True
            result["is_error"] = event.get("is_error")
            result["subtype"] = str(event.get("subtype") or "")
            result["api_error_status"] = event.get("api_error_status")
            result["terminal_reason"] = str(event.get("terminal_reason") or "")
            result["result_text"] = str(event.get("result") or "")
            if "not logged in" in result["result_text"].lower():
                result["authentication_failed"] = True
    return result


@dataclass
class RunOutcome:
    outcome: str
    admissible: bool
    reasons: list[str]


def classify_run_outcome(*, invocation: dict, runtime_result: dict,
                         surface_diff: dict, handshake: dict,
                         observed_model: str, expected_model: str,
                         obs: "TranscriptObservation",
                         arm: str,
                         candidate_checks: dict | None = None) -> RunOutcome:
    """D3.3.3 §11 fail-closed classification. Returns the FIRST failure
    outcome (order matters: auth before runtime before contamination),
    or SUCCESS only if every check passes.
    """
    reasons: list[str] = []

    # Auth failure.
    if runtime_result.get("authentication_failed"):
        return RunOutcome("AUTH_FAILURE", False, ["authentication_failed in transcript"])

    # Timeout.
    if invocation.get("reason") == "timeout" or invocation.get("exit_code") == -1:
        return RunOutcome("TIMEOUT", False, ["runtime timed out"])

    # Runtime failure: non-zero exit, is_error, no init/model turn.
    if invocation.get("exit_code", 1) != 0:
        reasons.append(f"exit_code={invocation.get('exit_code')}")
    if runtime_result.get("is_error") is True:
        reasons.append("result.is_error=true")
    if not runtime_result.get("result_event_seen"):
        reasons.append("no terminal result event")
    if not runtime_result.get("model_turn_seen"):
        reasons.append("no model turn")
    if reasons:
        return RunOutcome("RUNTIME_FAILURE", False, reasons)

    # Model mismatch (treated as a runtime failure class per §8).
    if expected_model and observed_model and observed_model != expected_model:
        return RunOutcome("RUNTIME_FAILURE", False,
                          [f"RUN_INVALID_MODEL_MISMATCH observed={observed_model} "
                           f"expected={expected_model}"])

    # Contamination.
    if contamination_reason(surface_diff):
        return RunOutcome("CONTAMINATION", False,
                          [f"contamination={contamination_reason(surface_diff)}"])

    # Run-id mismatch.
    if handshake.get("mismatch"):
        return RunOutcome("RUN_ID_MISMATCH", False, ["run_id handshake mismatch"])

    # Task/subagent dispatch.
    if obs.task_tool_use_count > 0:
        return RunOutcome("WORKFLOW_FAILURE", False,
                          [f"task_tool_use_count={obs.task_tool_use_count}"])

    if arm == "candidate":
        cc = candidate_checks or {}
        if not obs.wrapper_skill_invoked:
            reasons.append("wrapper_skill_invoked=false")
        if not obs.child_skill_invoked:
            reasons.append("child_skill_invoked=false")
        if reasons:
            return RunOutcome("WORKFLOW_FAILURE", False, reasons)
        if obs.observed_mode != "OBSERVED_SEQUENTIAL":
            return RunOutcome("WORKFLOW_FAILURE", False,
                              [f"observed_mode={obs.observed_mode}"])
        if not cc.get("bundle_present"):
            return RunOutcome("WORKFLOW_FAILURE", False, ["rdx bundle absent"])
        if not cc.get("artifacts_non_empty"):
            return RunOutcome("WORKFLOW_FAILURE", False, ["no artifacts"])
        if not cc.get("active_packs_ok"):
            return RunOutcome("WORKFLOW_FAILURE", False,
                              [f"active_packs={cc.get('active_packs')} "
                               f"expected={cc.get('expected_packs')}"])
        if not cc.get("verifier_all_pass"):
            return RunOutcome("VERIFIER_FAILURE", False, ["verifier not all PASS"])
        if not cc.get("one_sidecar_per_artifact"):
            return RunOutcome("VERIFIER_FAILURE", False,
                              ["sidecar/artifact count mismatch"])
    else:  # baseline
        if obs.wrapper_skill_invoked:
            return RunOutcome("WORKFLOW_FAILURE", False,
                              ["baseline invoked RDX wrapper"])
        if not obs.child_skill_invoked:
            return RunOutcome("WORKFLOW_FAILURE", False,
                              ["baseline did not invoke child skill"])

    return RunOutcome("SUCCESS", True, ["all checks passed"])


# ------------------------------------------------------ transcript parsing

@dataclass
class TranscriptObservation:
    observed_mode: str
    observed_mode_basis: str
    wrapper_skill_invoked: bool
    child_skill_invoked: bool
    task_tool_use_count: int
    transcript_sha256: str
    session_id: str


_SKILL_TOOL_NAMES = ("skill", "slashcommand", "slash_command")


def _iter_tool_use_events(events: Iterable[dict]) -> Iterable[dict]:
    """Yield only structured `tool_use` blocks — no free-text scanning.
    Blocks can live at either `event.tool_use = {...}` or under
    `event.message.content[*].type == 'tool_use'` or
    `event.content[*].type == 'tool_use'`. Assistant prose (`text`
    blocks) is deliberately ignored — D3.3.2 §8.
    """
    for event in events:
        # top-level tool_use
        tu = event.get("tool_use")
        if isinstance(tu, dict):
            yield tu
        # assistant messages
        msg = event.get("message")
        if isinstance(msg, dict):
            content = msg.get("content")
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_use":
                        yield block
        content = event.get("content")
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    yield block


def _classify_tool_use(tu: dict, wrapper_skill: str, child_skill: str) -> dict:
    """Return a per-block classification: does it represent an invocation
    of the wrapper skill, the child skill, or a Task subagent dispatch?

    Only STRUCTURED signals count: `name` must be a Skill/SlashCommand
    invocation tool (not arbitrary Bash / Read / etc.), and the target
    identifier lives in explicit fields.
    """
    result = {"wrapper": False, "child": False, "task": False}
    name = str(tu.get("name") or "").lower()
    inp = tu.get("input") if isinstance(tu.get("input"), dict) else {}
    if name == "task":
        result["task"] = True
        return result
    if name in _SKILL_TOOL_NAMES or name.startswith("mcp__skill"):
        # Explicit skill invocation. The invoked skill sits in one of a
        # small set of documented fields — never assistant prose.
        skill_target = (
            inp.get("skill")
            or inp.get("name")
            or inp.get("skill_name")
            or inp.get("slash_command")
            or ""
        )
        st = str(skill_target).strip().lstrip("/").lower()
        if st == wrapper_skill.lower():
            result["wrapper"] = True
        if st == child_skill.lower():
            result["child"] = True
    return result


def _classify_transcript(transcript_path: Path, workflow: str) -> TranscriptObservation:
    """D3.3.2 §8 structured-only classifier.

    Only `tool_use` blocks with `name` in `{Skill, SlashCommand, ...}`
    can set wrapper/child invocation booleans. `name == "Task"` counts
    a subagent dispatch. Free-text assistant prose is IGNORED — a
    message that says "I invoked rdx-tea-atdd" produces no signal.

    Transitions:
      - transcript missing → TRANSCRIPT_MISSING
      - transcript unreadable / no valid JSON lines → TRANSCRIPT_INVALID
      - any Task tool_use → OBSERVED_SUBAGENT
      - wrapper AND child structured Skill events → OBSERVED_SEQUENTIAL
        (basis: no-subagent-events-surrogate)
      - otherwise → INFERRED_ABSENT (basis: no-subagent-events-surrogate)
    """
    if not transcript_path.exists():
        return TranscriptObservation(
            observed_mode="TRANSCRIPT_MISSING",
            observed_mode_basis="transcript-missing",
            wrapper_skill_invoked=False,
            child_skill_invoked=False,
            task_tool_use_count=0,
            transcript_sha256="",
            session_id="",
        )
    raw = transcript_path.read_bytes()
    sha = _sha256_bytes(raw)
    wrapper_skill = f"rdx-tea-{workflow}"
    child_skill = f"bmad-testarch-{workflow}"

    events: list[dict] = []
    invalid_lines = 0
    valid_lines = 0
    session_id = ""
    for line in raw.decode("utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            invalid_lines += 1
            continue
        valid_lines += 1
        events.append(event)
        sid = event.get("session_id") or event.get("sessionId")
        if sid and not session_id:
            session_id = str(sid)

    if valid_lines == 0:
        return TranscriptObservation(
            observed_mode="TRANSCRIPT_INVALID",
            observed_mode_basis="transcript-invalid",
            wrapper_skill_invoked=False,
            child_skill_invoked=False,
            task_tool_use_count=0,
            transcript_sha256=sha,
            session_id="",
        )

    wrapper_seen = False
    child_seen = False
    task_uses = 0
    for tu in _iter_tool_use_events(events):
        c = _classify_tool_use(tu, wrapper_skill, child_skill)
        wrapper_seen = wrapper_seen or c["wrapper"]
        child_seen = child_seen or c["child"]
        if c["task"]:
            task_uses += 1

    if task_uses > 0:
        return TranscriptObservation(
            observed_mode="OBSERVED_SUBAGENT",
            observed_mode_basis="direct-subagent-event",
            wrapper_skill_invoked=wrapper_seen,
            child_skill_invoked=child_seen,
            task_tool_use_count=task_uses,
            transcript_sha256=sha,
            session_id=session_id,
        )
    if wrapper_seen and child_seen:
        return TranscriptObservation(
            observed_mode="OBSERVED_SEQUENTIAL",
            observed_mode_basis="no-subagent-events-surrogate",
            wrapper_skill_invoked=True,
            child_skill_invoked=True,
            task_tool_use_count=0,
            transcript_sha256=sha,
            session_id=session_id,
        )
    return TranscriptObservation(
        observed_mode="INFERRED_ABSENT",
        observed_mode_basis="no-subagent-events-surrogate",
        wrapper_skill_invoked=wrapper_seen,
        child_skill_invoked=child_seen,
        task_tool_use_count=task_uses,
        transcript_sha256=sha,
        session_id=session_id,
    )


# ------------------------------------------------------------ reconcile op

def reconcile_transcript(*, run_report_path: Path, transcript_path: Path,
                         workflow: str) -> dict:
    """Idempotent post-runtime reconciliation.

    Reads the completed run-report.json, classifies the transcript, and
    atomically writes back the observation fields. NEVER touches
    artifacts, sidecars, or run-state.json. Safe to call multiple
    times; the result depends only on transcript bytes.
    """
    if not run_report_path.exists():
        raise OrchestratorError(f"run-report.json missing: {run_report_path}")
    report = json.loads(run_report_path.read_text(encoding="utf-8"))
    obs = _classify_transcript(transcript_path, workflow)
    updates = {
        "requested_mode": "sequential",
        "configured_mode": report.get("resolved_mode", "unknown"),
        "observed_mode": obs.observed_mode,
        "observed_mode_basis": obs.observed_mode_basis,
        "wrapper_skill_invoked": obs.wrapper_skill_invoked,
        "child_skill_invoked": obs.child_skill_invoked,
        "task_tool_use_count": obs.task_tool_use_count,
        "transcript_sha256": obs.transcript_sha256,
        "session_id": obs.session_id,
    }
    # Merge without touching artifact or sidecar fields.
    report.update({
        "requested_mode": updates["requested_mode"],
        "configured_mode": updates["configured_mode"],
        "observed_mode": updates["observed_mode"],
        "observed_mode_basis": updates["observed_mode_basis"],
        "wrapper_skill_invoked": updates["wrapper_skill_invoked"],
        "child_skill_invoked": updates["child_skill_invoked"],
        "task_tool_use_count": updates["task_tool_use_count"],
        "transcript_sha256": updates["transcript_sha256"],
        "session_id": updates["session_id"],
        "reconciled_at": _utc_now(),
    })
    _atomic_write_json(run_report_path, report)
    return updates


# ---------------------------------------------------------- schema check

def _validate_bundle(bundle: dict) -> list[str]:
    try:
        import jsonschema
    except ImportError:
        return ["jsonschema library missing — install pytest jsonschema pyyaml"]
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    return [e.message for e in validator.iter_errors(bundle)]


# ------------------------------------------------------------------ RunSpec

@dataclass
class RunSpec:
    scenario: str
    arm: str
    repetition: int
    workflow: str
    fixture_dir: Path
    workspace_dir: Path
    evidence_root: Path
    run_id: str
    model: str = DEFAULT_MODEL
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
    max_budget_usd: float = DEFAULT_MAX_BUDGET_USD
    isolated_config_dir: Path | None = None


# ----------------------------------------------------------------- run-one

def _prepare(spec: RunSpec) -> dict:
    """Create the disposable workspace and record prepare outputs.

    D3.3.2 §6.1: schedule-owned run_id is the single source of truth.
    The workspace prep uses `spec.run_id` verbatim; nothing generates
    a fresh timestamp id here.
    """
    prep = prepare_workspace.prepare(
        dest=spec.workspace_dir,
        fixture=spec.fixture_dir,
        scenario=spec.scenario,
        workflow=spec.workflow,
        run_id=spec.run_id,
        arm=spec.arm,
    )
    if prep.get("run_id") != spec.run_id:
        raise OrchestratorError(
            f"prepare_workspace returned run_id={prep.get('run_id')!r} "
            f"but spec.run_id={spec.run_id!r}"
        )
    return prep


def _invoke(spec: RunSpec, prep: dict,
            isolation: ProjectRuntimeIsolation) -> dict:
    """D3.3.3 §5.1/§6 arm-specific runtime invocation with project-only
    isolation. Baseline directly invokes the child skill; candidate
    invokes the wrapper. Auth environment is inherited UNCHANGED — no
    CLAUDE_CONFIG_DIR override, no API key.
    """
    prompt = arm_prompt(spec.arm, spec.workflow, spec.run_id)
    old_env = dict(os.environ)
    try:
        # isolation.env() only adds CLAUDE_CODE_DISABLE_AUTO_MEMORY; it
        # never overrides CLAUDE_CONFIG_DIR.
        os.environ.update(isolation.env())
        result = invoke_runtime.invoke(
            workspace=Path(prep["project"]),
            workflow=spec.workflow,
            run_id=spec.run_id,
            model=spec.model,
            max_budget_usd=spec.max_budget_usd,
            timeout_seconds=spec.timeout_seconds,
            prompt_override=prompt,
            settings_path=isolation.settings_path,
            mcp_config_path=isolation.mcp_config_path,
            setting_sources=isolation.setting_sources(),
            disallowed_tools=isolation.disallowed_tools(),
            permission_mode=isolation.permission_mode,
            require_exact_model=True,
        )
    finally:
        os.environ.clear()
        os.environ.update(old_env)
    result["prompt"] = prompt
    result["prompt_hash"] = _sha256_text(prompt)
    return result


def _check_run_id_handshake(*, workspace: Path, workflow: str,
                            run_id: str) -> dict:
    """D3.3.2 §6.4. Compare the schedule-owned run_id against every
    place a run_id can appear post-run. Any mismatch is a PILOT_INVALID
    signal."""
    handshake = {
        "schedule": run_id,
        "invocation_json": None,
        "workspace_runtime_dir": None,
        "run_report": None,
        "mismatch": False,
    }
    inv = workspace / "_bmad-run" / "rdx-tea-invocation.json"
    if inv.exists():
        try:
            handshake["invocation_json"] = json.loads(
                inv.read_text(encoding="utf-8")
            ).get("run_id")
        except json.JSONDecodeError:
            handshake["invocation_json"] = "INVALID_JSON"
    runtime_dir = workspace / "_bmad" / "rdx-tea" / "runtime" / workflow
    if runtime_dir.exists():
        subdirs = [p.name for p in runtime_dir.iterdir() if p.is_dir()]
        if run_id in subdirs:
            handshake["workspace_runtime_dir"] = run_id
        elif subdirs:
            handshake["workspace_runtime_dir"] = subdirs[0]
    rr = runtime_dir / run_id / "run-report.json"
    if rr.exists():
        try:
            handshake["run_report"] = json.loads(
                rr.read_text(encoding="utf-8")
            ).get("run_id")
        except json.JSONDecodeError:
            handshake["run_report"] = "INVALID_JSON"
    # Only mismatched if a value is present AND differs from schedule.
    for k in ("invocation_json", "workspace_runtime_dir", "run_report"):
        v = handshake[k]
        if v is None:
            continue
        if v != run_id:
            handshake["mismatch"] = True
            break
    return handshake


def _finalize_evidence_v3(spec: RunSpec, prep: dict, invocation: dict,
                          runtime_probe: dict,
                          isolation: ProjectRuntimeIsolation,
                          obs: TranscriptObservation,
                          cleanup_observed: dict, cleanup_state: str,
                          auth_preflight_id: str) -> tuple[Path, RunOutcome]:
    """D3.3.3 §12. Assemble and write the admission-aware v3 bundle.

    `cleanup_observed` is measured by the caller AFTER lock release
    (§13). Returns (bundle_path, RunOutcome). Never raises on a failed
    run — a failed run yields a non-admissible bundle. A SCHEMA_FAILURE
    is the only outcome that reflects a bundle that would not validate.
    """
    workspace = Path(prep["project"])
    workflow = spec.workflow
    run_id = spec.run_id

    inv = collect_evidence.collect(
        workspace=workspace,
        workflow=workflow,
        run_id=run_id,
        scenario=f"{spec.scenario}/{spec.arm}/rep-{spec.repetition:02d}",
        evidence_root=spec.evidence_root,
        invocation=invocation,
        runtime=runtime_probe,
    )
    evidence_dir = Path(inv["evidence_dir"])

    canonical_roots = _canonicalize_output_roots([
        workspace / "_bmad-output",
        workspace / "_bmad-output" / "test-artifacts",
    ])
    walked = _walk_artefacts(canonical_roots)
    new_artefacts = sorted({
        str((evidence_dir / "tea-artifacts" / f.name).as_posix())
        for f in walked if not f.name.endswith(".rdx-tea.json")
    })
    sidecars = sorted({
        str((evidence_dir / "sidecars" / f.name).as_posix())
        for f in walked if f.name.endswith(".rdx-tea.json")
    })

    run_report = evidence_dir / "run-report.json"
    transcript = evidence_dir / "transcript.stream.jsonl"
    bundle = evidence_dir / "active-context.md"

    observed_surface = _extract_runtime_init(transcript)
    runtime_result = extract_runtime_result(transcript)
    # Expected surface: exactly the arm skills, empty MCP/plugins.
    expected_surface = {
        "model": spec.model,
        "skills": sorted(isolation.project_skills),
        "mcp_servers": [],
        "plugins": [],
        "tools": [],
        # permission_mode intentionally not compared: it is symmetric
        # across arms and the CLI reports its own normalised value.
        "permission_mode": observed_surface.get("permission_mode", ""),
    }
    surface_diff = compare_runtime_surface(observed_surface, expected_surface)
    contamination = contamination_reason(surface_diff) or ""
    handshake = _check_run_id_handshake(
        workspace=workspace, workflow=workflow, run_id=run_id,
    )
    cmd_hash = _sha256_text(json.dumps(invocation.get("command", []), sort_keys=True))

    common = {
        "schema_version": SCHEMA_V3_VERSION,
        "arm": spec.arm,
        "scenario": spec.scenario,
        "workflow": spec.workflow,
        "repetition": spec.repetition,
        "run_id": spec.run_id,
        "run_id_handshake": handshake,
        "auth_preflight_id": auth_preflight_id,
        "workspace": {
            "path": str(workspace),
            "config_dir_overridden": False,
            "fixture_hash": _sha256_dir_tree(spec.fixture_dir),
        },
        "identity": {
            "base_sha": prep["base_sha"],
            "head_sha": prep["head_sha"],
        },
        "runtime": {
            "claude_code_path": runtime_probe.get("cli", "unknown"),
            "expected_surface": expected_surface,
            "observed_surface": {
                k: observed_surface.get(k)
                for k in (
                    "claude_code_version", "model", "permission_mode",
                    "tools", "skills", "slash_commands", "mcp_servers",
                    "plugins", "memory_paths", "session_id",
                    "api_key_source", "agents", "analytics_disabled",
                    "output_style", "fast_mode_state", "init_event_seen",
                )
            },
            "surface_diff": surface_diff,
            "contamination": contamination,
            "model_expected": spec.model,
            "model_observed": observed_surface.get("model", ""),
            "timeout_seconds": spec.timeout_seconds,
            "max_budget_usd": spec.max_budget_usd,
        },
        "invocation": {
            "command_hash": cmd_hash,
            "prompt_hash": invocation.get("prompt_hash", ""),
            "started_at": invocation.get("started_at", _utc_now()),
            "finished_at": invocation.get("finished_at", _utc_now()),
            "exit_code": invocation.get("exit_code", 0),
            "reason": (
                "timeout" if invocation.get("reason") == "timeout"
                else "normal" if invocation.get("exit_code") == 0
                else "runtime_error"
            ),
        },
        "runtime_result": {
            "result_event_seen": runtime_result["result_event_seen"],
            "is_error": runtime_result["is_error"],
            "subtype": runtime_result["subtype"],
            "authentication_failed": runtime_result["authentication_failed"],
            "model_turn_seen": runtime_result["model_turn_seen"],
            "terminal_reason": runtime_result["terminal_reason"],
        },
        "artifacts": {"new_artefacts": new_artefacts},
        "hashes": {
            "run_report": _sha256_file(run_report) if run_report.exists() else "",
            "transcript": _sha256_file(transcript),
            "bundle": _sha256_file(bundle) if bundle.exists() else "",
        },
        "observation": {
            "observed_mode": obs.observed_mode,
            "observed_mode_basis": obs.observed_mode_basis,
            "wrapper_skill_invoked": obs.wrapper_skill_invoked,
            "child_skill_invoked": obs.child_skill_invoked,
            "task_tool_use_count": obs.task_tool_use_count,
            "transcript_sha256": obs.transcript_sha256 or "",
            "session_id": obs.session_id or "",
        },
        "cleanup": {
            "state": cleanup_state,
            "observed": cleanup_observed,
        },
    }

    candidate_checks = None
    if spec.arm == "candidate":
        active_packs = _collect_active_packs(run_report)
        expected_packs = _expected_active_packs(spec.scenario)
        common["candidate"] = {
            "wrapper_skill_invoked": obs.wrapper_skill_invoked,
            "child_skill_invoked": obs.child_skill_invoked,
            "sidecars": sidecars,
            "active_packs": active_packs,
            "expected_rp_ids": _collect_expected_rp_ids(spec.scenario),
            "verifier_all_pass": _verifier_all_pass(run_report),
            "bundle_present": bundle.exists(),
        }
        candidate_checks = {
            "bundle_present": bundle.exists(),
            "artifacts_non_empty": len(new_artefacts) > 0,
            "active_packs": active_packs,
            "expected_packs": expected_packs,
            "active_packs_ok": sorted(active_packs) == sorted(expected_packs),
            "verifier_all_pass": _verifier_all_pass(run_report),
            "one_sidecar_per_artifact": len(sidecars) == len(new_artefacts)
            and len(new_artefacts) > 0,
        }
    else:  # baseline
        common["baseline"] = {
            "wrapper_skill_invoked": obs.wrapper_skill_invoked,
            "direct_child_skill_invoked": obs.child_skill_invoked,
            "rdx_bundle_absent": not bundle.exists(),
            "rdx_sidecars_absent": len(sidecars) == 0,
            "rdx_overlay_absent": not (
                workspace / "_bmad" / "custom"
                / f"bmad-testarch-{workflow}.toml"
            ).exists(),
        }

    # Classify outcome + admissibility BEFORE writing so they are in
    # the bundle.
    outcome = classify_run_outcome(
        invocation=invocation, runtime_result=runtime_result,
        surface_diff=surface_diff, handshake=handshake,
        observed_model=observed_surface.get("model", ""),
        expected_model=spec.model, obs=obs, arm=spec.arm,
        candidate_checks=candidate_checks,
    )
    common["run_outcome"] = outcome.outcome
    common["admissible"] = outcome.admissible
    common["admission_reasons"] = outcome.reasons

    errors = _validate_bundle_v3(common)
    if errors:
        # A bundle that would not validate is itself a SCHEMA_FAILURE;
        # record it non-admissibly rather than raising and losing
        # evidence.
        common["run_outcome"] = "SCHEMA_FAILURE"
        common["admissible"] = False
        common["admission_reasons"] = ["schema validation failed: "
                                        + "; ".join(errors[:5])]
        (evidence_dir / "live-evidence.v3.errors.txt").write_text(
            "\n".join(errors) + "\n", encoding="utf-8",
        )
        outcome = RunOutcome("SCHEMA_FAILURE", False, common["admission_reasons"])

    bundle_out = evidence_dir / "live-evidence.v3.json"
    _atomic_write_json(bundle_out, common)
    return bundle_out, outcome


def _expected_active_packs(scenario: str) -> list[str]:
    return {
        "test-design-async": ["async"],
        "atdd-api-async": ["async"],
        "atdd-api-async-corrected": ["api", "async"],
        "docs-only-rust-repo": [],
    }.get(scenario, [])


def _collect_active_packs(run_report_path: Path) -> list[str]:
    if not run_report_path.exists():
        return []
    try:
        data = json.loads(run_report_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    # run-report.json may reference active_packs via nested sidecars.
    packs: set[str] = set()
    for sc in data.get("sidecars", []):
        if isinstance(sc, dict):
            for p in sc.get("active_packs", []) or []:
                if isinstance(p, dict):
                    if "pack_id" in p:
                        packs.add(str(p["pack_id"]))
                elif isinstance(p, str):
                    packs.add(p)
    return sorted(packs)


def _collect_expected_rp_ids(scenario: str) -> list[str]:
    """Map scenario → expected RP-* ids per rubric v2/v3."""
    return {
        "test-design-async": ["RP-ASYNC-005"],
        "atdd-api-async": ["RP-ASYNC-005"],
        "atdd-api-async-corrected": ["RP-ASYNC-005", "RP-API-001"],
        "docs-only-rust-repo": [],
    }.get(scenario, [])


def _verifier_all_pass(run_report_path: Path) -> bool:
    if not run_report_path.exists():
        return False
    try:
        data = json.loads(run_report_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    ver = data.get("verifier", [])
    if not ver:
        return False
    for v in ver:
        # Each verifier entry carries a top-level `verdict` plus a
        # `checks` array. Accept either a top-level `verdict`/`status`
        # of PASS OR an all-PASS `checks` array with no failed_checks.
        verdict = str(v.get("verdict") or v.get("status") or "").upper()
        if verdict and verdict != "PASS":
            return False
        if v.get("failed_checks"):
            return False
        checks = v.get("checks") or []
        if checks and any(
            str(c.get("status", "")).upper() != "PASS" for c in checks
        ):
            return False
        if not verdict and not checks:
            # Neither a verdict nor checks present — cannot confirm PASS.
            return False
    return True


def _validate_bundle_v2(bundle: dict) -> list[str]:
    try:
        import jsonschema
    except ImportError:
        return ["jsonschema library missing"]
    if not SCHEMA_V2_PATH.exists():
        return [f"v2 schema missing at {SCHEMA_V2_PATH}"]
    schema = json.loads(SCHEMA_V2_PATH.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    return [e.message for e in validator.iter_errors(bundle)]


def _validate_bundle_v3(bundle: dict) -> list[str]:
    try:
        import jsonschema
    except ImportError:
        return ["jsonschema library missing"]
    if not SCHEMA_V3_PATH.exists():
        return [f"v3 schema missing at {SCHEMA_V3_PATH}"]
    schema = json.loads(SCHEMA_V3_PATH.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    return [e.message for e in validator.iter_errors(bundle)]


# ------------------------------------------------------ admission gate

@dataclass
class AdmissionResult:
    admissible: bool
    run_outcome: str
    reasons: list[str]
    arm: str
    run_id: str


def admit_bundle(bundle: dict) -> AdmissionResult:
    """D3.3.3 §14. Reusable structured admission gate over a v3 bundle.

    Recomputes admissibility from the bundle's own recorded fields —
    it does NOT trust the bundle's `admissible` field blindly. A bundle
    that claims admissible=true but violates any invariant is reported
    as NOT admissible with the violated reasons.
    """
    reasons: list[str] = []
    arm = bundle.get("arm", "")
    run_id = bundle.get("run_id", "")

    # Schema-level gate first.
    schema_errors = _validate_bundle_v3(bundle)
    if schema_errors:
        return AdmissionResult(False, "SCHEMA_FAILURE",
                               ["schema: " + e for e in schema_errors[:5]],
                               arm, run_id)

    if bundle.get("run_outcome") != "SUCCESS":
        reasons.append(f"run_outcome={bundle.get('run_outcome')}")
    inv = bundle.get("invocation", {})
    if inv.get("exit_code") != 0:
        reasons.append(f"exit_code={inv.get('exit_code')}")
    rr = bundle.get("runtime_result", {})
    if rr.get("is_error") is True:
        reasons.append("result.is_error=true")
    if rr.get("authentication_failed"):
        reasons.append("authentication_failed")
    if bundle.get("runtime", {}).get("contamination"):
        reasons.append(f"contamination={bundle['runtime']['contamination']}")
    if bundle.get("run_id_handshake", {}).get("mismatch"):
        reasons.append("run_id mismatch")
    model_exp = bundle.get("runtime", {}).get("model_expected", "")
    model_obs = bundle.get("runtime", {}).get("model_observed", "")
    if model_exp and model_obs and model_exp != model_obs:
        reasons.append(f"model mismatch {model_obs}!={model_exp}")
    obs = bundle.get("observation", {})
    if obs.get("task_tool_use_count", 0) != 0:
        reasons.append(f"task_tool_use_count={obs.get('task_tool_use_count')}")

    if arm == "candidate":
        cand = bundle.get("candidate", {})
        if not obs.get("wrapper_skill_invoked"):
            reasons.append("wrapper_skill_invoked=false")
        if not obs.get("child_skill_invoked"):
            reasons.append("child_skill_invoked=false")
        if obs.get("observed_mode") != "OBSERVED_SEQUENTIAL":
            reasons.append(f"observed_mode={obs.get('observed_mode')}")
        if not cand.get("bundle_present"):
            reasons.append("bundle absent")
        if not bundle.get("artifacts", {}).get("new_artefacts"):
            reasons.append("artifacts empty")
        if not cand.get("verifier_all_pass"):
            reasons.append("verifier not all PASS")
        exp = sorted(cand.get("expected_rp_ids", []))
        active = sorted(cand.get("active_packs", []))
        expected_packs = sorted(_expected_active_packs(bundle.get("scenario", "")))
        if active != expected_packs:
            reasons.append(f"active_packs {active} != {expected_packs}")
        sidecars = cand.get("sidecars", [])
        arts = bundle.get("artifacts", {}).get("new_artefacts", [])
        if arts and len(sidecars) != len(arts):
            reasons.append(f"sidecars({len(sidecars)}) != artefacts({len(arts)})")
    elif arm == "baseline":
        base = bundle.get("baseline", {})
        if obs.get("wrapper_skill_invoked"):
            reasons.append("baseline invoked wrapper")
        if not obs.get("child_skill_invoked"):
            reasons.append("baseline did not invoke child")
        if not base.get("rdx_bundle_absent"):
            reasons.append("baseline has RDX bundle")
        if not base.get("rdx_sidecars_absent"):
            reasons.append("baseline has RDX sidecars")

    # Cleanup gate.
    cl = bundle.get("cleanup", {}).get("observed", {})
    if cl.get("lock_state") != "absent":
        reasons.append(f"lock_state={cl.get('lock_state')}")
    if cl.get("overlay_state") not in ("absent", "foreign-preserved"):
        reasons.append(f"overlay_state={cl.get('overlay_state')}")
    if not cl.get("run_dir_retained"):
        reasons.append("run_dir not retained")
    if not cl.get("transcript_retained"):
        reasons.append("transcript not retained")

    admissible = not reasons
    return AdmissionResult(
        admissible,
        bundle.get("run_outcome", "SUCCESS") if admissible else
        bundle.get("run_outcome", "RUNTIME_FAILURE"),
        reasons or ["all admission checks passed"],
        arm, run_id,
    )


# ------------------------------------------------------------ abort_run op

def observe_cleanup(*, workspace: Path, workflow: str, run_id: str) -> dict:
    """D3.3.2 §13.2. Return the ACTUAL post-cleanup state observed on
    disk. No booleans are constants; we re-read each surface after
    cleanup and record the truth."""
    lock_data = _read_lock_json(workspace)
    lock_state = "absent"
    if lock_data is not None:
        if lock_data.get("run_id") == run_id:
            lock_state = "owned-still-present"
        else:
            lock_state = "foreign-present"
    overlay = workspace / "_bmad" / "custom" / f"bmad-testarch-{workflow}.toml"
    marker = "# rdx-tea-owned run-specific overlay"
    if not overlay.exists():
        overlay_state = "absent"
    else:
        text = overlay.read_text(encoding="utf-8", errors="replace")
        if text.startswith(marker):
            overlay_state = "rdx-owned-still-present"
        else:
            overlay_state = "foreign-preserved"
    run_dir = workspace / "_bmad" / "rdx-tea" / "runtime" / workflow / run_id
    return {
        "lock_state": lock_state,
        "overlay_state": overlay_state,
        "run_dir_retained": run_dir.exists(),
        "transcript_retained": (run_dir / "transcript.stream.jsonl").exists(),
    }


def abort_run(*, workspace: Path, workflow: str, run_id: str,
              state: str = "ABORTED", reason: str = "",
              failure_class: str = "") -> dict:
    """Idempotent teardown of a failed / interrupted run.

    D3.3.2 §13:
      - structured JSON lock, exact-equality ownership check;
      - preserve transcripts and logs;
      - never delete a foreign lock (mismatched run_id → no-op);
      - never touch a foreign overlay;
      - always emit an abort marker AND a schema-compatible cleanup
        observation dict, even on repeated calls.
    """
    started_at = _utc_now()
    changed = {
        "lock_released": False,
        "overlay_restored": False,
        "state": state,
        "run_id": run_id,
        "workflow": workflow,
        "reason": reason,
        "failure_class": failure_class,
        "at": started_at,
    }
    lock = _lock_path(workspace)
    if lock.exists() and _lock_owned_by(workspace, run_id, workflow):
        lock.unlink()
        changed["lock_released"] = True

    overlay = workspace / "_bmad" / "custom" / f"bmad-testarch-{workflow}.toml"
    backup = (workspace / "_bmad" / "rdx-tea" / "runtime" / workflow / run_id
              / "overlay-backup.toml")
    marker = "# rdx-tea-owned run-specific overlay"
    if overlay.exists():
        try:
            text = overlay.read_text(encoding="utf-8")
        except OSError:
            text = ""
        if text.startswith(marker):
            if backup.exists():
                overlay.write_bytes(backup.read_bytes())
            else:
                overlay.unlink(missing_ok=True)
            changed["overlay_restored"] = True

    # Observed cleanup — after our writes above, re-read state.
    observed = observe_cleanup(workspace=workspace, workflow=workflow,
                               run_id=run_id)
    changed["observed"] = observed

    # Record an abort marker under the run dir. Never overwrite an
    # earlier one — append a suffix if needed to preserve history.
    run_dir = workspace / "_bmad" / "rdx-tea" / "runtime" / workflow / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    abort_marker = run_dir / "aborted.json"
    if abort_marker.exists():
        idx = 1
        while (run_dir / f"aborted.{idx}.json").exists():
            idx += 1
        abort_marker = run_dir / f"aborted.{idx}.json"
    _atomic_write_json(abort_marker, changed)
    return changed


# ------------------------------------------------------------- run-smoke

def run_smoke(spec: RunSpec,
              auth_preflight_id: str = AUTH_PREFLIGHT_ID_DEFAULT) -> dict:
    """D3.3.3 full lifecycle, fail-closed.

    Success path (§13):
      prep → contract → lock → bootstrap → preflight → invoke →
      reconcile → RELEASE lock + restore overlay → observe cleanup →
      emit v3 evidence + classify outcome.

    A non-SUCCESS outcome yields a non-admissible bundle and a
    non-zero-style result dict (`status: failed`, `admissible: false`).
    An infra error before invocation (bad prep, preflight fail) aborts
    and emits failure evidence, then re-raises a typed error.
    """
    if not spec.run_id:
        raise OrchestratorError("spec.run_id is required (schedule-owned)")

    runtime_probe = runtime_discovery.discover()
    if runtime_probe.get("status") != "READY":
        raise OrchestratorError(f"runtime not ready: {runtime_probe}")

    prep: dict | None = None
    invocation: dict = {}
    isolation = ProjectRuntimeIsolation(
        workspace=spec.workspace_dir,
        arm=spec.arm,
        workflow=spec.workflow,
    )

    try:
        prep = _prepare(spec)
        workspace = Path(prep["project"])

        prompt = arm_prompt(spec.arm, spec.workflow, spec.run_id)
        emit_invocation_contract(
            workspace=workspace,
            run_id=spec.run_id,
            scenario=spec.scenario,
            arm=spec.arm,
            workflow=spec.workflow,
            repetition=spec.repetition,
            base_sha=prep["base_sha"],
            head_sha=prep["head_sha"],
            fixture_hash=_sha256_dir_tree(spec.fixture_dir),
            prompt_hash=_sha256_text(prompt),
        )

        write_lock_json(workspace, run_id=spec.run_id, workflow=spec.workflow)
        isolation.bootstrap()

        preflight_errors = isolation.preflight()
        if preflight_errors:
            raise OrchestratorError(
                "isolation preflight failed: " + "; ".join(preflight_errors)
            )

        invocation = _invoke(spec, prep, isolation)

        run_dir = (workspace / "_bmad" / "rdx-tea" / "runtime"
                   / spec.workflow / spec.run_id)
        transcript_path = run_dir / "transcript.stream.jsonl"
        report_path = run_dir / "run-report.json"
        if report_path.exists():
            reconcile_transcript(
                run_report_path=report_path,
                transcript_path=transcript_path,
                workflow=spec.workflow,
            )
        obs = _classify_transcript(transcript_path, spec.workflow)

        # D3.3.3 §13 — release lock + restore overlay BEFORE observing
        # cleanup, so lock_state reflects the released state.
        _release_lock_and_overlay(workspace, spec.workflow, spec.run_id)
        cleanup_observed = observe_cleanup(
            workspace=workspace, workflow=spec.workflow, run_id=spec.run_id,
        )

        cleanup_state = ("FINALIZED"
                         if outcome_is_success(invocation, transcript_path)
                         else "FAILED")
        bundle_path, outcome = _finalize_evidence_v3(
            spec, prep, invocation, runtime_probe, isolation, obs,
            cleanup_observed=cleanup_observed,
            cleanup_state=cleanup_state,
            auth_preflight_id=auth_preflight_id,
        )
        return {
            "status": "ok" if outcome.admissible else "failed",
            "run_outcome": outcome.outcome,
            "admissible": outcome.admissible,
            "admission_reasons": outcome.reasons,
            "bundle": str(bundle_path),
            "run_id": spec.run_id,
        }
    except (KeyboardInterrupt, subprocess.TimeoutExpired) as err:
        if prep is not None:
            abort_run(workspace=Path(prep["project"]), workflow=spec.workflow,
                      run_id=spec.run_id, state="ABORTED", reason=str(err),
                      failure_class=type(err).__name__)
        raise
    except OrchestratorError:
        if prep is not None:
            abort_run(workspace=Path(prep["project"]), workflow=spec.workflow,
                      run_id=spec.run_id, state="FAILED",
                      reason="orchestrator error", failure_class="OrchestratorError")
        raise
    except Exception as err:
        if prep is not None:
            abort_run(workspace=Path(prep["project"]), workflow=spec.workflow,
                      run_id=spec.run_id, state="FAILED", reason=str(err),
                      failure_class=type(err).__name__)
        raise


def outcome_is_success(invocation: dict, transcript_path: Path) -> bool:
    """Quick pre-check used only to pick the cleanup.state label. The
    authoritative classification is done in _finalize_evidence_v3."""
    if invocation.get("exit_code") != 0:
        return False
    rr = extract_runtime_result(transcript_path)
    return (rr.get("is_error") is not True
            and not rr.get("authentication_failed")
            and rr.get("model_turn_seen") is True)


def _release_lock_and_overlay(workspace: Path, workflow: str,
                              run_id: str) -> None:
    """Release our own lock and restore/remove our overlay (D3.3.3 §13).
    Foreign locks/overlays are left untouched."""
    lock_path = _lock_path(workspace)
    if _lock_owned_by(workspace, run_id, workflow):
        lock_path.unlink(missing_ok=True)
    overlay = workspace / "_bmad" / "custom" / f"bmad-testarch-{workflow}.toml"
    backup = (workspace / "_bmad" / "rdx-tea" / "runtime" / workflow / run_id
              / "overlay-backup.toml")
    marker = "# rdx-tea-owned run-specific overlay"
    if overlay.exists():
        try:
            text = overlay.read_text(encoding="utf-8")
        except OSError:
            text = ""
        if text.startswith(marker):
            if backup.exists():
                overlay.write_bytes(backup.read_bytes())
            else:
                overlay.unlink(missing_ok=True)


# -------------------------------------------------------------------- CLI

def _add_common(sp: argparse.ArgumentParser, *, run_id_required: bool) -> None:
    sp.add_argument("--scenario", required=True, choices=sorted(WORKFLOWS.keys()))
    sp.add_argument("--arm", required=True, choices=("baseline", "candidate"))
    sp.add_argument("--repetition", type=int, default=1)
    sp.add_argument("--workspace-dir", required=True, type=Path)
    sp.add_argument("--evidence-root", type=Path, default=EVIDENCE_ROOT_DEFAULT)
    sp.add_argument("--fixture-dir", type=Path, default=None)
    sp.add_argument("--model", default=DEFAULT_MODEL)
    sp.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    sp.add_argument("--max-budget-usd", type=float, default=DEFAULT_MAX_BUDGET_USD)
    sp.add_argument("--isolated-config-dir", type=Path, default=None)
    sp.add_argument("--run-id", required=run_id_required, default=None,
                    help=("D3.3.2 §6.1: schedule-owned run id. Required for "
                          "run-one; optional for run-smoke (auto-generated "
                          "as smoke-<scenario>-<utc>)."))


def _mk_spec(args) -> RunSpec:
    run_id = args.run_id
    if not run_id:
        run_id = (f"smoke-{args.scenario}-{args.arm}-"
                  f"{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}")
    return RunSpec(
        scenario=args.scenario,
        arm=args.arm,
        repetition=args.repetition,
        workflow=WORKFLOWS[args.scenario],
        fixture_dir=(args.fixture_dir or (FIXTURE_DIR / args.scenario)),
        workspace_dir=args.workspace_dir,
        evidence_root=args.evidence_root,
        run_id=run_id,
        model=args.model,
        timeout_seconds=args.timeout_seconds,
        max_budget_usd=args.max_budget_usd,
        isolated_config_dir=args.isolated_config_dir,
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="rdx-tea D3.3.2 live orchestrator")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_smoke = sub.add_parser("run-smoke")
    _add_common(p_smoke, run_id_required=False)

    p_one = sub.add_parser("run-one")
    _add_common(p_one, run_id_required=True)

    p_pre = sub.add_parser("runtime-preflight")
    p_pre.add_argument("--workspace", required=True, type=Path)
    p_pre.add_argument("--arm", required=True, choices=("baseline", "candidate"))
    p_pre.add_argument("--workflow", required=True,
                       choices=("test-design", "atdd"))

    p_reco = sub.add_parser("reconcile-transcript")
    p_reco.add_argument("--run-report", required=True, type=Path)
    p_reco.add_argument("--transcript", required=True, type=Path)
    p_reco.add_argument("--workflow", required=True)

    p_abort = sub.add_parser("abort-run")
    p_abort.add_argument("--workspace", required=True, type=Path)
    p_abort.add_argument("--workflow", required=True)
    p_abort.add_argument("--run-id", required=True)
    p_abort.add_argument("--state", choices=("ABORTED", "FAILED"), default="ABORTED")
    p_abort.add_argument("--reason", default="")

    p_admit = sub.add_parser("admit")
    p_admit.add_argument("--bundle", required=True, type=Path)

    args = ap.parse_args()

    try:
        if args.cmd in ("run-smoke", "run-one"):
            spec = _mk_spec(args)
            r = run_smoke(spec)
            print(json.dumps(r, indent=2, sort_keys=True))
            return 0 if r.get("admissible") else 4
        if args.cmd == "reconcile-transcript":
            r = reconcile_transcript(
                run_report_path=args.run_report,
                transcript_path=args.transcript,
                workflow=args.workflow,
            )
            print(json.dumps(r, indent=2, sort_keys=True))
            return 0
        if args.cmd == "abort-run":
            r = abort_run(workspace=args.workspace, workflow=args.workflow,
                          run_id=args.run_id, state=args.state, reason=args.reason)
            print(json.dumps(r, indent=2, sort_keys=True))
            return 0
        if args.cmd == "runtime-preflight":
            iso = ProjectRuntimeIsolation(
                workspace=args.workspace,
                arm=args.arm,
                workflow=args.workflow,
            )
            iso.bootstrap()
            errors = iso.preflight()
            report = {
                "workspace": str(args.workspace),
                "arm": args.arm,
                "workflow": args.workflow,
                "expected_skills": sorted(iso.project_skills),
                "config_dir_overridden": False,
                "errors": errors,
                "status": "PASS" if not errors else "FAIL",
            }
            print(json.dumps(report, indent=2, sort_keys=True))
            return 0 if not errors else 3
        if args.cmd == "admit":
            bundle = json.loads(args.bundle.read_text(encoding="utf-8"))
            res = admit_bundle(bundle)
            print(json.dumps({
                "admissible": res.admissible,
                "run_outcome": res.run_outcome,
                "arm": res.arm,
                "run_id": res.run_id,
                "reasons": res.reasons,
            }, indent=2, sort_keys=True))
            return 0 if res.admissible else 4
    except OrchestratorError as err:
        print(f"run_live failed: {err}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    sys.exit(main())
