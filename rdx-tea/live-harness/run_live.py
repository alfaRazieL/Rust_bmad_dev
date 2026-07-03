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
SCHEMA_VERSION = "rdx-tea-live-evidence.v1"

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

@dataclass
class ClaudeIsolation:
    """Isolated per-run Claude Code config directory.

    D3.3.1 §6.6: pilot integrity requires identical minimal environments
    for baseline and candidate. A dirty runtime (user MCP servers, user
    memory, unrelated skills) contaminates comparability. We construct
    a temporary CLAUDE_CONFIG_DIR under the run's evidence directory,
    seed it with the project's rdx-tea skills only, and disable MCP.
    """

    config_dir: Path
    project_skills: list[str]
    permission_mode: str = "bypassPermissions"

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
        # Project skills copied into the isolated config so `claude`
        # can discover /rdx-tea-* wrappers without the user's global
        # skills leaking in.
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


def _classify_transcript(transcript_path: Path, workflow: str) -> TranscriptObservation:
    """Parse the finished stream-json transcript.

    OBSERVED_SEQUENTIAL requires:
      - transcript valid;
      - wrapper Skill (rdx-tea-<workflow>) referenced in a tool_use;
      - child Skill (bmad-testarch-<workflow>) referenced in a tool_use;
      - Task tool_use count == 0.
    Any Task tool_use event => OBSERVED_SUBAGENT.
    Missing/unreadable transcript => TRANSCRIPT_MISSING/TRANSCRIPT_INVALID.

    Absence of a direct subagent_dispatch/mode event is recorded as
    `observed_mode_basis=no-subagent-events-surrogate` so downstream
    review can distinguish surrogate from direct proof.
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
    wrapper_seen = False
    child_seen = False
    task_uses = 0
    session_id = ""
    invalid = False
    for line in raw.decode("utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            invalid = True
            continue
        # session id — Claude Code emits `session_id` on init events.
        sid = event.get("session_id") or event.get("sessionId")
        if sid and not session_id:
            session_id = str(sid)
        # Skill / Task invocations show up under `message.content[*]`
        # for assistant events, and inside `tool_use` blocks. We walk
        # generically so future format tweaks do not silently break
        # this parser.
        _walk_for_invocations(event, wrapper_skill, child_skill, counters := {})
        wrapper_seen = wrapper_seen or counters.get("wrapper", False)
        child_seen = child_seen or counters.get("child", False)
        task_uses += counters.get("task", 0)
    if invalid and not (wrapper_seen or child_seen):
        return TranscriptObservation(
            observed_mode="TRANSCRIPT_INVALID",
            observed_mode_basis="transcript-invalid",
            wrapper_skill_invoked=wrapper_seen,
            child_skill_invoked=child_seen,
            task_tool_use_count=task_uses,
            transcript_sha256=sha,
            session_id=session_id,
        )
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


def _walk_for_invocations(node: Any, wrapper_skill: str, child_skill: str,
                          counters: dict) -> None:
    """Recursively walk a JSON node looking for tool_use blocks that
    reference the wrapper skill, the child skill, or the Task tool.
    Fills the counters dict in place so the caller sees a rolled-up
    per-event summary."""
    if isinstance(node, dict):
        tool_name = node.get("name")
        if isinstance(tool_name, str):
            tn = tool_name.lower()
            if tn == "task":
                counters["task"] = counters.get("task", 0) + 1
            if tn.startswith("skill"):
                # Skill invocation blocks: look at input.skill or input.name.
                skill_input = node.get("input") or {}
                sk = str(skill_input.get("skill")
                         or skill_input.get("name") or "").lower()
                if wrapper_skill in sk:
                    counters["wrapper"] = True
                if child_skill in sk:
                    counters["child"] = True
        # Some Claude Code events name the skill directly.
        skill_field = node.get("skill") or node.get("skill_name")
        if isinstance(skill_field, str):
            sf = skill_field.lower()
            if wrapper_skill in sf:
                counters["wrapper"] = True
            if child_skill in sf:
                counters["child"] = True
        # Recurse.
        for v in node.values():
            _walk_for_invocations(v, wrapper_skill, child_skill, counters)
    elif isinstance(node, list):
        for v in node:
            _walk_for_invocations(v, wrapper_skill, child_skill, counters)
    elif isinstance(node, str):
        # Fallback: some events serialise Skill uses as free-form text
        # like "invoking rdx-tea-atdd". The mode we care about is
        # OBSERVED_SEQUENTIAL only when the wrapper AND child were both
        # invoked; substring hits are a coarse signal only used as a
        # last resort surrogate.
        s = node.lower()
        if wrapper_skill in s:
            counters["wrapper"] = True
        if child_skill in s:
            counters["child"] = True


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
    model: str = DEFAULT_MODEL
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
    max_budget_usd: float = DEFAULT_MAX_BUDGET_USD
    run_id: str = ""
    isolated_config_dir: Path | None = None


# ----------------------------------------------------------------- run-one

def _prepare(spec: RunSpec) -> dict:
    """Create the disposable workspace and record prepare outputs."""
    return prepare_workspace.prepare(
        dest=spec.workspace_dir,
        fixture=spec.fixture_dir,
        scenario=spec.scenario,
        workflow=spec.workflow,
    )


def _invoke(spec: RunSpec, prep: dict, isolation: ClaudeIsolation) -> dict:
    """Run claude in headless mode inside the isolated config."""
    # Reuse invoke_runtime but override env with the isolated CLAUDE_CONFIG_DIR.
    old_env = dict(os.environ)
    try:
        os.environ.update(isolation.env())
        result = invoke_runtime.invoke(
            workspace=Path(prep["project"]),
            workflow=spec.workflow,
            run_id=prep["run_id"],
            model=spec.model,
            max_budget_usd=spec.max_budget_usd,
            timeout_seconds=spec.timeout_seconds,
        )
    finally:
        # Restore env fully; do NOT leak CLAUDE_CONFIG_DIR into a
        # subsequent scenario.
        os.environ.clear()
        os.environ.update(old_env)
    return result


def _finalize_evidence(spec: RunSpec, prep: dict, invocation: dict,
                       runtime: dict, isolation: ClaudeIsolation,
                       obs: TranscriptObservation) -> Path:
    """Assemble the schema-valid live-evidence bundle and write it."""
    workspace = Path(prep["project"])
    workflow = spec.workflow
    run_id = prep["run_id"]

    # Collect the standard §7 bundle (transcript, run-report, sidecars,
    # artefacts, workspace-manifest) — reuse collect_evidence but dedupe
    # after by walking canonical roots.
    inv = collect_evidence.collect(
        workspace=workspace,
        workflow=workflow,
        run_id=run_id,
        scenario=f"{spec.scenario}/{spec.arm}/rep-{spec.repetition:02d}",
        evidence_root=spec.evidence_root,
        invocation=invocation,
        runtime=runtime,
    )
    evidence_dir = Path(inv["evidence_dir"])

    # Deduplicate: rebuild the tea-artifacts/sidecars listings by canonical
    # walk so the same file scanned via two output roots appears once.
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

    # Compute required hashes.
    run_report = evidence_dir / "run-report.json"
    transcript = evidence_dir / "transcript.stream.jsonl"
    bundle = evidence_dir / "active-context.md"

    # Command hash derived from the invocation command list.
    cmd_hash = _sha256_text(json.dumps(invocation.get("command", []), sort_keys=True))

    bundle_payload = {
        "schema_version": SCHEMA_VERSION,
        "scenario": spec.scenario,
        "arm": spec.arm,
        "repetition": spec.repetition,
        "run_id": run_id,
        "workspace": {
            "path": str(workspace),
            "config_dir": str(isolation.config_dir),
            "config_dir_hash": _sha256_dir_tree(isolation.config_dir),
        },
        "identity": {
            "base_sha": prep["base_sha"],
            "head_sha": prep["head_sha"],
            "workflow": workflow,
        },
        "runtime": {
            "claude_code_version": runtime.get("version", "unknown"),
            "claude_code_path": runtime.get("cli", "unknown"),
            "model_id": spec.model,
            "permission_mode": isolation.permission_mode,
            "available_tools": sorted(runtime.get("surface", {}).keys()),
            "available_skills": sorted(isolation.project_skills),
            "mcp_servers": [],
            "timeout_seconds": spec.timeout_seconds,
            "max_budget_usd": spec.max_budget_usd,
        },
        "invocation": {
            "command_hash": cmd_hash,
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
            "sidecars": sidecars,
        },
        "hashes": {
            "run_report": _sha256_file(run_report),
            "transcript": _sha256_file(transcript),
            "bundle": _sha256_file(bundle),
        },
        "observation": {
            "requested_mode": "sequential",
            "configured_mode": "sequential",
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
            "lock_released": True,
            "overlay_restored": True,
        },
    }

    errors = _validate_bundle(bundle_payload)
    bundle_path = evidence_dir / "live-evidence.v1.json"
    _atomic_write_json(bundle_path, bundle_payload)
    if errors:
        (evidence_dir / "live-evidence.v1.errors.txt").write_text(
            "\n".join(errors) + "\n", encoding="utf-8",
        )
        raise OrchestratorError(
            f"emitted bundle fails schema validation: {errors[:3]}"
        )
    return bundle_path


# --------------------------------------------------------- lock inspection

def _lock_path(workspace: Path) -> Path:
    return workspace / "_bmad" / "rdx-tea" / "runtime" / "active-run.lock"


def _lock_owned_by(workspace: Path, run_id: str) -> bool:
    lp = _lock_path(workspace)
    if not lp.exists():
        return False
    return run_id in lp.read_text(encoding="utf-8")


# ------------------------------------------------------------ abort_run op

def abort_run(*, workspace: Path, workflow: str, run_id: str,
              state: str = "ABORTED", reason: str = "") -> dict:
    """Idempotent teardown of a failed / interrupted run.

    Rules:
      - preserve transcripts and logs;
      - never delete a foreign lock (mismatched run_id → no-op);
      - never touch a foreign overlay;
      - always produce an abort record even on repeated calls.

    Returns a dict describing what actually changed.
    """
    changed = {
        "lock_released": False,
        "overlay_restored": False,
        "state": state,
        "run_id": run_id,
        "workflow": workflow,
        "reason": reason,
        "at": _utc_now(),
    }
    lock = _lock_path(workspace)
    if lock.exists() and _lock_owned_by(workspace, run_id):
        lock.unlink()
        changed["lock_released"] = True

    # Overlay restore uses the wrapper's own logic — but only if we can
    # import the wrapper without side effects. To stay crash-safe we
    # simply remove an rdx-tea-owned overlay if the backup does not
    # exist, and restore the backup otherwise.
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
    """Full lifecycle: discovery → prep → invoke → reconcile → collect.

    On any failure the workspace is left intact so a reviewer can
    inspect it, but locks/overlays are released and an abort marker is
    written.
    """
    runtime = runtime_discovery.discover()
    if runtime.get("status") != "READY":
        raise OrchestratorError(f"runtime not ready: {runtime}")

    prep: dict | None = None
    invocation: dict = {}
    isolation = ClaudeIsolation(
        config_dir=(spec.isolated_config_dir
                    or (spec.evidence_root / spec.scenario / spec.arm
                        / f"rep-{spec.repetition:02d}" / "isolated-config")),
        project_skills=[f"rdx-tea-{spec.workflow}"],
    )

    try:
        prep = _prepare(spec)
        # Bootstrap isolated config AFTER prepare_workspace copied
        # rdx-tea skills into the workspace, so we can seed them into
        # the isolated dir.
        isolation.bootstrap(Path(prep["project"]))
        invocation = _invoke(spec, prep, isolation)

        # Reconcile transcript now that the runtime has exited.
        workspace = Path(prep["project"])
        run_dir = (workspace / "_bmad" / "rdx-tea" / "runtime"
                   / spec.workflow / prep["run_id"])
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
            spec, prep, invocation, runtime, isolation, obs,
        )
        return {
            "status": "ok",
            "bundle": str(bundle_path),
            "run_id": prep["run_id"],
        }
    except (KeyboardInterrupt, subprocess.TimeoutExpired) as err:
        if prep is not None:
            abort_run(workspace=Path(prep["project"]), workflow=spec.workflow,
                      run_id=prep["run_id"], state="ABORTED", reason=str(err))
        raise
    except Exception as err:
        if prep is not None:
            abort_run(workspace=Path(prep["project"]), workflow=spec.workflow,
                      run_id=prep["run_id"], state="FAILED", reason=str(err))
        raise


# -------------------------------------------------------------------- CLI

def _add_common(sp: argparse.ArgumentParser) -> None:
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


def _mk_spec(args) -> RunSpec:
    return RunSpec(
        scenario=args.scenario,
        arm=args.arm,
        repetition=args.repetition,
        workflow=WORKFLOWS[args.scenario],
        fixture_dir=(args.fixture_dir or (FIXTURE_DIR / args.scenario)),
        workspace_dir=args.workspace_dir,
        evidence_root=args.evidence_root,
        model=args.model,
        timeout_seconds=args.timeout_seconds,
        max_budget_usd=args.max_budget_usd,
        isolated_config_dir=args.isolated_config_dir,
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="rdx-tea D3.3.1 live orchestrator")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_smoke = sub.add_parser("run-smoke")
    _add_common(p_smoke)

    p_one = sub.add_parser("run-one")
    _add_common(p_one)

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
    except OrchestratorError as err:
        print(f"run_live failed: {err}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    sys.exit(main())
