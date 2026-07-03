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
SCHEMA_VERSION = "rdx-tea-live-evidence.v1"
SCHEMA_V2_VERSION = "rdx-tea-live-evidence.v2"
INVOCATION_SCHEMA_VERSION = "rdx-tea-invocation.v1"

RDX_TEA_DIR = _HERE.parent
EVIDENCE_ROOT_DEFAULT = RDX_TEA_DIR / "evidence" / "live"

WORKFLOWS = {
    "test-design-async": "test-design",
    "atdd-api-async": "atdd",
    "atdd-api-async-corrected": "atdd",
    "docs-only-rust-repo": "test-design",
}

FIXTURE_DIR = _HERE / "fixtures"

DEFAULT_MODEL = "haiku"
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
            f"Invoke the /rdx-tea-{workflow} skill on the current project. "
            f"Follow every activation step in the wrapper's SKILL.md. Do "
            f"NOT skip the prepare-run or finalize-run subcommands. Use "
            f"the actual bmad-testarch-{workflow} child skill — do not "
            f"substitute output. The invocation contract file at "
            f"_bmad-run/rdx-tea-invocation.json pins run_id={run_id}. "
            f"Read that file first; use its run_id verbatim in every "
            f"wrapper command. Halt on any non-zero exit. When done, "
            f"summarise the run-report.json path."
        )
    raise OrchestratorError(f"unknown arm {arm!r}")


@dataclass
class ClaudeIsolation:
    """Isolated per-run Claude Code config directory.

    D3.3.2 §5.2 + §10: pilot integrity requires identical minimal
    environments for baseline and candidate. A dirty runtime (user
    MCP servers, user memory, unrelated skills) contaminates
    comparability. We construct a temporary CLAUDE_CONFIG_DIR under
    the run's evidence directory, seed it with only the arm-permitted
    skills, and disable MCP.
    """

    config_dir: Path
    arm: str
    workflow: str
    permission_mode: str = "bypassPermissions"

    @property
    def project_skills(self) -> list[str]:
        return arm_installed_skills(self.arm, self.workflow)

    def bootstrap(self, source_project: Path) -> None:
        """Populate the config dir with a minimal, deterministic layout.
        We do NOT touch the user's real ~/.claude directory.
        """
        self.config_dir.mkdir(parents=True, exist_ok=True)
        # Empty MCP servers.
        (self.config_dir / "mcp.json").write_text(
            json.dumps({"mcpServers": {}}, sort_keys=True), encoding="utf-8"
        )
        # Empty user memory.
        (self.config_dir / "CLAUDE.md").write_text("", encoding="utf-8")
        skills_dir = self.config_dir / "skills"
        skills_dir.mkdir(exist_ok=True)
        src_skills = source_project / ".claude" / "skills"
        if not src_skills.exists():
            return
        for skill_name in self.project_skills:
            src = src_skills / skill_name
            if not src.exists():
                continue
            dst = skills_dir / skill_name
            if dst.exists():
                continue
            shutil.copytree(src, dst)

    def env(self) -> dict[str, str]:
        e = dict(os.environ)
        e["CLAUDE_CONFIG_DIR"] = str(self.config_dir)
        # Deliberately DO NOT set CLAUDE_MCP_CONFIG — we scope MCP via
        # the isolated dir alone. Disable any inherited MCP by pointing
        # at the empty file we just wrote.
        e["CLAUDE_MCP_CONFIG"] = str(self.config_dir / "mcp.json")
        return e

    def preflight(self) -> list[str]:
        """D3.3.2 §10: return a list of policy errors, empty if OK."""
        errors: list[str] = []
        if not self.config_dir.exists():
            errors.append(f"config_dir missing: {self.config_dir}")
        mcp = self.config_dir / "mcp.json"
        if not mcp.exists():
            errors.append(f"mcp.json missing: {mcp}")
        else:
            try:
                data = json.loads(mcp.read_text(encoding="utf-8"))
            except json.JSONDecodeError as e:
                errors.append(f"mcp.json invalid: {e}")
                data = None
            if data is not None and data.get("mcpServers"):
                errors.append("mcp.json contains servers; expected empty")
        memory = self.config_dir / "CLAUDE.md"
        if memory.exists() and memory.read_text(encoding="utf-8").strip():
            errors.append("CLAUDE.md contains user memory; expected empty")
        skills_dir = self.config_dir / "skills"
        if not skills_dir.exists():
            errors.append(f"skills dir missing: {skills_dir}")
        else:
            present = sorted(p.name for p in skills_dir.iterdir() if p.is_dir())
            expected = sorted(self.project_skills)
            if present != expected:
                errors.append(f"installed skills {present} != expected {expected}")
        return errors


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
                    "plugins", "memory_paths"):
            v = event.get(key)
            if isinstance(v, list):
                surface[key] = [
                    (i.get("name") if isinstance(i, dict) and "name" in i else i)
                    for i in v
                ]
        # Session id often on init event.
        sid = event.get("session_id") or event.get("sessionId")
        if sid:
            surface["session_id"] = str(sid)
        surface["raw"] = event
        break
    return surface


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
    )
    if prep.get("run_id") != spec.run_id:
        raise OrchestratorError(
            f"prepare_workspace returned run_id={prep.get('run_id')!r} "
            f"but spec.run_id={spec.run_id!r}"
        )
    return prep


def _invoke(spec: RunSpec, prep: dict, isolation: ClaudeIsolation) -> dict:
    """D3.3.2 §5.1 arm-specific runtime invocation.

    Baseline directly invokes the child skill; candidate invokes the
    wrapper (which is responsible for calling the child).
    """
    prompt = arm_prompt(spec.arm, spec.workflow, spec.run_id)
    old_env = dict(os.environ)
    try:
        os.environ.update(isolation.env())
        result = invoke_runtime.invoke(
            workspace=Path(prep["project"]),
            workflow=spec.workflow,
            run_id=spec.run_id,
            model=spec.model,
            max_budget_usd=spec.max_budget_usd,
            timeout_seconds=spec.timeout_seconds,
            prompt_override=prompt,
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


def _v2_bundle_common(*, spec: RunSpec, prep: dict, invocation: dict,
                       runtime_probe: dict, isolation: ClaudeIsolation,
                       obs: TranscriptObservation,
                       observed_surface: dict, expected_surface: dict,
                       cleanup_observed: dict,
                       handshake: dict,
                       new_artefacts: list[str],
                       run_report_path: Path, transcript_path: Path,
                       bundle_path: Path | None) -> dict:
    """Return the arm-neutral portion of the v2 bundle."""
    workspace = Path(prep["project"])
    surface_diff = compare_runtime_surface(observed_surface, expected_surface)
    contamination = contamination_reason(surface_diff)
    cmd_hash = _sha256_text(
        json.dumps(invocation.get("command", []), sort_keys=True)
    )
    return {
        "schema_version": SCHEMA_V2_VERSION,
        "arm": spec.arm,
        "scenario": spec.scenario,
        "workflow": spec.workflow,
        "repetition": spec.repetition,
        "run_id": spec.run_id,
        "run_id_handshake": handshake,
        "workspace": {
            "path": str(workspace),
            "config_dir": str(isolation.config_dir),
            "config_dir_hash": _sha256_dir_tree(isolation.config_dir),
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
                    "init_event_seen",
                )
            },
            "surface_diff": surface_diff,
            "contamination": contamination or "",
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
        "artifacts": {
            "new_artefacts": new_artefacts,
        },
        "hashes": {
            "run_report": _sha256_file(run_report_path) if run_report_path else "",
            "transcript": _sha256_file(transcript_path),
            "bundle": _sha256_file(bundle_path) if bundle_path else "",
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
            "state": "FINALIZED",
            "observed": cleanup_observed,
        },
    }


def _finalize_evidence(spec: RunSpec, prep: dict, invocation: dict,
                       runtime_probe: dict, isolation: ClaudeIsolation,
                       obs: TranscriptObservation) -> Path:
    """Assemble and write the arm-aware live-evidence v2 bundle."""
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
    expected_surface = {
        "model": spec.model,
        "permission_mode": isolation.permission_mode,
        "skills": sorted(isolation.project_skills),
        "mcp_servers": [],
        "plugins": [],
        "tools": [],  # do not enforce tool allowlist here; policy-level
    }
    cleanup_observed = observe_cleanup(
        workspace=workspace, workflow=workflow, run_id=run_id,
    )
    handshake = _check_run_id_handshake(
        workspace=workspace, workflow=workflow, run_id=run_id,
    )

    common = _v2_bundle_common(
        spec=spec, prep=prep, invocation=invocation,
        runtime_probe=runtime_probe, isolation=isolation,
        obs=obs, observed_surface=observed_surface,
        expected_surface=expected_surface,
        cleanup_observed=cleanup_observed, handshake=handshake,
        new_artefacts=new_artefacts,
        run_report_path=run_report if run_report.exists() else None,
        transcript_path=transcript,
        bundle_path=bundle if bundle.exists() else None,
    )

    if spec.arm == "candidate":
        common["candidate"] = {
            "wrapper_skill_invoked": obs.wrapper_skill_invoked,
            "child_skill_invoked": obs.child_skill_invoked,
            "sidecars": sidecars,
            "active_packs": _collect_active_packs(run_report),
            "expected_rp_ids": _collect_expected_rp_ids(spec.scenario),
            "verifier_all_pass": _verifier_all_pass(run_report),
            "bundle_present": bundle.exists(),
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

    errors = _validate_bundle_v2(common)
    bundle_out = evidence_dir / "live-evidence.v2.json"
    _atomic_write_json(bundle_out, common)
    if errors:
        (evidence_dir / "live-evidence.v2.errors.txt").write_text(
            "\n".join(errors) + "\n", encoding="utf-8",
        )
        raise OrchestratorError(
            f"emitted v2 bundle fails schema validation: {errors[:3]}"
        )
    return bundle_out


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
        if str(v.get("status", "")).upper() != "PASS":
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

def run_smoke(spec: RunSpec) -> dict:
    """Full lifecycle: discovery → prep → invocation-contract → invoke →
    reconcile → v2 evidence → observed cleanup.

    On any failure the workspace is left intact so a reviewer can
    inspect it, but locks/overlays are released and an abort marker is
    written.
    """
    if not spec.run_id:
        raise OrchestratorError("spec.run_id is required (schedule-owned)")

    runtime_probe = runtime_discovery.discover()
    if runtime_probe.get("status") != "READY":
        raise OrchestratorError(f"runtime not ready: {runtime_probe}")

    prep: dict | None = None
    invocation: dict = {}
    isolation = ClaudeIsolation(
        config_dir=(spec.isolated_config_dir
                    or (spec.evidence_root / spec.scenario / spec.arm
                        / f"rep-{spec.repetition:02d}" / "isolated-config")),
        arm=spec.arm,
        workflow=spec.workflow,
    )

    try:
        prep = _prepare(spec)
        workspace = Path(prep["project"])

        # D3.3.2 §6.2 — emit invocation contract BEFORE the wrapper
        # runs, so the wrapper reads schedule-owned run_id verbatim.
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

        # D3.3.2 §13 — write structured lock BEFORE runtime call.
        write_lock_json(workspace, run_id=spec.run_id, workflow=spec.workflow)

        isolation.bootstrap(workspace)

        # D3.3.2 §10 — preflight must pass before we spend a token.
        preflight_errors = isolation.preflight()
        if preflight_errors:
            raise OrchestratorError(
                "isolation preflight failed: " + "; ".join(preflight_errors)
            )

        invocation = _invoke(spec, prep, isolation)

        # Reconcile transcript now that the runtime has exited.
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

        bundle_path = _finalize_evidence(
            spec, prep, invocation, runtime_probe, isolation, obs,
        )
        # Release own lock at end of successful run.
        lock_path = _lock_path(workspace)
        if _lock_owned_by(workspace, spec.run_id, spec.workflow):
            lock_path.unlink(missing_ok=True)
        return {
            "status": "ok",
            "bundle": str(bundle_path),
            "run_id": spec.run_id,
        }
    except (KeyboardInterrupt, subprocess.TimeoutExpired) as err:
        if prep is not None:
            abort_run(workspace=Path(prep["project"]), workflow=spec.workflow,
                      run_id=spec.run_id, state="ABORTED", reason=str(err),
                      failure_class=type(err).__name__)
        raise
    except Exception as err:
        if prep is not None:
            abort_run(workspace=Path(prep["project"]), workflow=spec.workflow,
                      run_id=spec.run_id, state="FAILED", reason=str(err),
                      failure_class=type(err).__name__)
        raise


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
    p_pre.add_argument("--config-dir", required=True, type=Path)
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

    args = ap.parse_args()

    try:
        if args.cmd in ("run-smoke", "run-one"):
            spec = _mk_spec(args)
            r = run_smoke(spec)
            print(json.dumps(r, indent=2, sort_keys=True))
            return 0
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
            iso = ClaudeIsolation(
                config_dir=args.config_dir,
                arm=args.arm,
                workflow=args.workflow,
            )
            errors = iso.preflight()
            report = {
                "config_dir": str(args.config_dir),
                "arm": args.arm,
                "workflow": args.workflow,
                "expected_skills": sorted(iso.project_skills),
                "errors": errors,
                "status": "PASS" if not errors else "FAIL",
            }
            print(json.dumps(report, indent=2, sort_keys=True))
            return 0 if not errors else 3
    except OrchestratorError as err:
        print(f"run_live failed: {err}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    sys.exit(main())
