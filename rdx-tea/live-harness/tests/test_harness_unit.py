"""D3.3.1 harness unit tests.

These are DETERMINISTIC tests only — no live model calls. They exercise
the code paths that the pilot rubric depends on:

* transcript reconciliation classifies correctly for well-formed,
  malformed, and empty inputs;
* reconciliation is idempotent — repeated calls do not rebind
  artifacts or modify run-state;
* output canonicalisation does not double-count artefacts scanned via
  both `_bmad-output` and `_bmad-output/test-artifacts`;
* abort-run is fail-safe: foreign locks/overlays are preserved;
* the corrected ATDD fixture activates the `api` pack.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
LIVE = HERE.parent
sys.path.insert(0, str(LIVE))
sys.path.insert(0, str(
    LIVE.parent / "poc" / "install-tree" / "_bmad" / "rdx-tea" / "scripts"
))

import run_live  # noqa: E402  — after sys.path setup


# -------------------------------------------------- transcript classifier

def _write_transcript(path: Path, events: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8",
    )


def test_classify_missing_transcript(tmp_path):
    obs = run_live._classify_transcript(tmp_path / "nope.jsonl", "atdd")
    assert obs.observed_mode == "TRANSCRIPT_MISSING"
    assert obs.observed_mode_basis == "transcript-missing"
    assert obs.task_tool_use_count == 0


def test_classify_invalid_transcript(tmp_path):
    path = tmp_path / "t.jsonl"
    path.write_text("not-json\nalso-not-json\n", encoding="utf-8")
    obs = run_live._classify_transcript(path, "atdd")
    assert obs.observed_mode == "TRANSCRIPT_INVALID"


def test_classify_observed_sequential(tmp_path):
    path = tmp_path / "t.jsonl"
    _write_transcript(path, [
        {"type": "system", "session_id": "sess-1"},
        {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "Skill",
             "input": {"skill": "rdx-tea-atdd"}},
        ]}},
        {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "Skill",
             "input": {"skill": "bmad-testarch-atdd"}},
        ]}},
    ])
    obs = run_live._classify_transcript(path, "atdd")
    assert obs.observed_mode == "OBSERVED_SEQUENTIAL"
    assert obs.observed_mode_basis == "no-subagent-events-surrogate"
    assert obs.wrapper_skill_invoked is True
    assert obs.child_skill_invoked is True
    assert obs.task_tool_use_count == 0
    assert obs.session_id == "sess-1"


def test_classify_observed_subagent(tmp_path):
    path = tmp_path / "t.jsonl"
    _write_transcript(path, [
        {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "Task",
             "input": {"prompt": "spawn"}},
        ]}},
    ])
    obs = run_live._classify_transcript(path, "atdd")
    assert obs.observed_mode == "OBSERVED_SUBAGENT"
    assert obs.observed_mode_basis == "direct-subagent-event"
    assert obs.task_tool_use_count == 1


# ------------------------------------------------------ reconcile-idempotent

def test_reconcile_transcript_updates_report_atomically(tmp_path):
    report = tmp_path / "run-report.json"
    report.write_text(json.dumps({
        "schema_version": "rdx-tea-run.v1",
        "workflow": "atdd",
        "run_id": "test-1",
        "resolved_mode": "sequential",
        "sidecars": [{"a": 1}],
        "verifier": [{"b": 2}],
        "new_artefacts": ["/x"],
    }), encoding="utf-8")
    transcript = tmp_path / "t.jsonl"
    _write_transcript(transcript, [
        {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "Skill",
             "input": {"skill": "rdx-tea-atdd"}},
        ]}},
        {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "Skill",
             "input": {"skill": "bmad-testarch-atdd"}},
        ]}},
    ])
    r1 = run_live.reconcile_transcript(
        run_report_path=report, transcript_path=transcript, workflow="atdd",
    )
    assert r1["observed_mode"] == "OBSERVED_SEQUENTIAL"
    data1 = json.loads(report.read_text())
    # artifact/sidecar/verifier fields are NOT touched
    assert data1["sidecars"] == [{"a": 1}]
    assert data1["verifier"] == [{"b": 2}]
    assert data1["new_artefacts"] == ["/x"]

    # Idempotent: re-run — no rebind, same classification.
    r2 = run_live.reconcile_transcript(
        run_report_path=report, transcript_path=transcript, workflow="atdd",
    )
    assert r2["observed_mode"] == "OBSERVED_SEQUENTIAL"
    data2 = json.loads(report.read_text())
    assert data2["sidecars"] == [{"a": 1}]
    assert data2["new_artefacts"] == ["/x"]


# --------------------------------------------------------- dedup outputs

def test_canonicalize_output_roots_collapses_nested(tmp_path):
    parent = tmp_path / "_bmad-output"
    child = parent / "test-artifacts"
    child.mkdir(parents=True)
    roots = run_live._canonicalize_output_roots([parent, child])
    assert roots == [parent.resolve()]


def test_walk_artefacts_no_duplicates(tmp_path):
    parent = tmp_path / "_bmad-output"
    child = parent / "test-artifacts"
    child.mkdir(parents=True)
    (child / "one.md").write_text("hello", encoding="utf-8")
    (child / "one.md.rdx-tea.json").write_text("{}", encoding="utf-8")
    roots = run_live._canonicalize_output_roots([parent, child])
    walked = run_live._walk_artefacts(roots)
    names = [p.name for p in walked]
    assert sorted(names) == ["one.md", "one.md.rdx-tea.json"]
    assert len(names) == len(set(names))


def test_one_artifact_one_sidecar(tmp_path):
    """A single artefact plus its sidecar should surface exactly one
    tea-artifacts entry AND exactly one sidecar entry in the finalized
    inventory — not two of each because of nested roots."""
    parent = tmp_path / "_bmad-output"
    child = parent / "test-artifacts"
    child.mkdir(parents=True)
    (child / "artefact.md").write_text("hello", encoding="utf-8")
    (child / "artefact.md.rdx-tea.json").write_text("{}", encoding="utf-8")
    walked = run_live._walk_artefacts(
        run_live._canonicalize_output_roots([parent, child])
    )
    md = [p for p in walked if p.suffix == ".md"]
    sidecars = [p for p in walked if p.name.endswith(".rdx-tea.json")]
    assert len(md) == 1
    assert len(sidecars) == 1


# --------------------------------------------------------- abort-run tests

def _mk_workspace(tmp_path: Path, workflow: str, run_id: str,
                  overlay_text: str | None = None,
                  backup_text: str | None = None,
                  lock_text: str | None = None) -> Path:
    """Create a fake workspace tree with the paths run_live.abort_run
    inspects. Returns the workspace root."""
    ws = tmp_path / "ws"
    (ws / "_bmad" / "rdx-tea" / "runtime").mkdir(parents=True)
    (ws / "_bmad" / "rdx-tea" / "runtime" / workflow / run_id).mkdir(parents=True)
    (ws / "_bmad" / "custom").mkdir(parents=True)
    if overlay_text is not None:
        (ws / "_bmad" / "custom" / f"bmad-testarch-{workflow}.toml"
         ).write_text(overlay_text, encoding="utf-8")
    if backup_text is not None:
        (ws / "_bmad" / "rdx-tea" / "runtime" / workflow / run_id
         / "overlay-backup.toml").write_text(backup_text, encoding="utf-8")
    if lock_text is not None:
        (ws / "_bmad" / "rdx-tea" / "runtime" / "active-run.lock"
         ).write_text(lock_text, encoding="utf-8")
    return ws


def test_abort_run_idempotent_no_state(tmp_path):
    ws = _mk_workspace(tmp_path, "atdd", "r-1")
    r1 = run_live.abort_run(workspace=ws, workflow="atdd", run_id="r-1")
    r2 = run_live.abort_run(workspace=ws, workflow="atdd", run_id="r-1")
    assert r1["state"] == r2["state"] == "ABORTED"


def test_abort_run_releases_owned_lock(tmp_path):
    ws = _mk_workspace(tmp_path, "atdd", "r-1", lock_text=json.dumps({
        "run_id": "r-1", "workflow": "atdd", "pid": 42,
        "created_at": "2026-07-03T00:00:00+00:00",
    }))
    r = run_live.abort_run(workspace=ws, workflow="atdd", run_id="r-1")
    assert r["lock_released"] is True
    assert not (ws / "_bmad" / "rdx-tea" / "runtime" / "active-run.lock"
                ).exists()


def test_abort_run_preserves_foreign_lock(tmp_path):
    ws = _mk_workspace(tmp_path, "atdd", "r-1", lock_text=json.dumps({
        "run_id": "OTHER-RUN", "workflow": "atdd", "pid": 99,
        "created_at": "2026-07-03T00:00:00+00:00",
    }))
    r = run_live.abort_run(workspace=ws, workflow="atdd", run_id="r-1")
    assert r["lock_released"] is False
    assert (ws / "_bmad" / "rdx-tea" / "runtime" / "active-run.lock"
            ).exists()


def test_abort_run_ignores_legacy_string_lock(tmp_path):
    """Old-style substring locks (D3.3.1 and earlier) must NOT be
    released; the structured classifier treats them as unowned so a
    stale legacy lock is preserved for manual inspection rather than
    silently deleted."""
    ws = _mk_workspace(tmp_path, "atdd", "r-1",
                       lock_text="atdd r-1 42\n")
    r = run_live.abort_run(workspace=ws, workflow="atdd", run_id="r-1")
    assert r["lock_released"] is False
    assert (ws / "_bmad" / "rdx-tea" / "runtime" / "active-run.lock"
            ).exists()


def test_abort_run_restores_backup_overlay(tmp_path):
    marker = "# rdx-tea-owned run-specific overlay\n"
    ws = _mk_workspace(
        tmp_path, "atdd", "r-1",
        overlay_text=marker + "[workflow]\npersistent_facts=[]\n",
        backup_text="[workflow]\n# original user overlay\n",
    )
    r = run_live.abort_run(workspace=ws, workflow="atdd", run_id="r-1")
    assert r["overlay_restored"] is True
    ov = (ws / "_bmad" / "custom" / "bmad-testarch-atdd.toml"
          ).read_text(encoding="utf-8")
    assert "original user overlay" in ov


def test_abort_run_preserves_foreign_overlay(tmp_path):
    ws = _mk_workspace(
        tmp_path, "atdd", "r-1",
        overlay_text="[workflow]\n# user's real overlay — not ours\n",
    )
    r = run_live.abort_run(workspace=ws, workflow="atdd", run_id="r-1")
    assert r["overlay_restored"] is False
    ov = (ws / "_bmad" / "custom" / "bmad-testarch-atdd.toml"
          ).read_text(encoding="utf-8")
    assert "user's real overlay" in ov


# ------------------------------------------------- corrected ATDD fixture

def test_corrected_atdd_activates_api_pack():
    from router import RouterRules, activated_pack_names, replay
    rules_path = (LIVE.parent / "poc" / "install-tree" / "_bmad" / "rdx-tea"
                  / "canonical" / "router-rules.json")
    rules = RouterRules.load(rules_path)
    fixture = LIVE / "fixtures" / "atdd-api-async-corrected"
    diff = (fixture / "diff.patch").read_text(encoding="utf-8")
    tags = [ln.strip() for ln in
            (fixture / "_bmad-run" / "tags.txt").read_text().splitlines()
            if ln.strip()]
    acts = replay(diff, rules, tags)
    active = sorted(activated_pack_names(acts))
    assert "api" in active
    assert "async" in active


def test_old_atdd_fixture_does_not_activate_api_pack():
    """Regression guard for §4.4 — the pre-D3.3.1 fixture must remain
    async-only so nobody re-uses it thinking they'll get api coverage."""
    from router import RouterRules, activated_pack_names, replay
    rules_path = (LIVE.parent / "poc" / "install-tree" / "_bmad" / "rdx-tea"
                  / "canonical" / "router-rules.json")
    rules = RouterRules.load(rules_path)
    fixture = LIVE / "fixtures" / "atdd-api-async"
    diff = (fixture / "diff.patch").read_text(encoding="utf-8")
    tags = [ln.strip() for ln in
            (fixture / "_bmad-run" / "tags.txt").read_text().splitlines()
            if ln.strip()]
    acts = replay(diff, rules, tags)
    active = sorted(activated_pack_names(acts))
    assert active == ["async"]


# ------------------------------------------------- evidence schema loads

def test_evidence_schema_is_valid_draft2020():
    import jsonschema
    schema = json.loads(run_live.SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)


def test_evidence_schema_rejects_incomplete_bundle():
    import jsonschema
    schema = json.loads(run_live.SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    bad = {"schema_version": "rdx-tea-live-evidence.v1"}
    errors = list(validator.iter_errors(bad))
    assert errors, "empty bundle must fail schema validation"


def test_evidence_schema_accepts_minimal_valid_bundle():
    import jsonschema
    schema = json.loads(run_live.SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    good = {
        "schema_version": "rdx-tea-live-evidence.v1",
        "scenario": "test-design-async",
        "arm": "candidate",
        "repetition": 1,
        "run_id": "smoke-1",
        "workspace": {
            "path": "/tmp/ws",
            "config_dir": "/tmp/cfg",
            "config_dir_hash": "a" * 64,
        },
        "identity": {
            "base_sha": "0" * 40,
            "head_sha": "1" * 40,
            "workflow": "test-design",
        },
        "runtime": {
            "claude_code_version": "2.1.126",
            "claude_code_path": "/opt/homebrew/bin/claude",
            "model_id": "claude-haiku-4-5-20251001",
            "permission_mode": "bypassPermissions",
            "available_tools": [],
            "available_skills": [],
            "mcp_servers": [],
            "timeout_seconds": 600,
            "max_budget_usd": 2.0,
        },
        "invocation": {
            "command_hash": "b" * 64,
            "started_at": "2026-07-03T00:00:00+00:00",
            "finished_at": "2026-07-03T00:05:00+00:00",
            "exit_code": 0,
            "reason": "normal",
        },
        "artifacts": {"new_artefacts": [], "sidecars": []},
        "hashes": {
            "run_report": "c" * 64,
            "transcript": "d" * 64,
            "bundle": "e" * 64,
        },
        "observation": {
            "requested_mode": "sequential",
            "configured_mode": "sequential",
            "observed_mode": "OBSERVED_SEQUENTIAL",
            "observed_mode_basis": "no-subagent-events-surrogate",
            "wrapper_skill_invoked": True,
            "child_skill_invoked": True,
            "task_tool_use_count": 0,
            "transcript_sha256": "f" * 64,
            "session_id": "sess-x",
        },
        "cleanup": {
            "state": "FINALIZED",
            "lock_released": True,
            "overlay_restored": True,
        },
    }
    errors = list(validator.iter_errors(good))
    assert not errors, f"expected valid bundle to pass: {errors}"


# ------------------------------------------- pilot schedule immutability

def test_pilot_schedule_precommitted():
    """The D3.4 pilot schedule must exist and be locked before any run.
    This test guards against silent edits — the SHA256 of the schedule
    is captured in D3_3_1_FINAL_VERIFICATION.json and cross-checked at
    pilot time."""
    import hashlib
    schedule = (LIVE.parent / "evals" / "runs" / "D3_4_PILOT_RUNS.json")
    assert schedule.exists()
    data = json.loads(schedule.read_text(encoding="utf-8"))
    assert data["schema_version"] == "rdx-tea-pilot-runs.v1"
    assert data["locked"] is True
    # Deterministic size: 3 scenarios × 2 arms × 3 repetitions = 18 runs.
    assert len(data["runs"]) == 18
    # The pack of runs contains exactly the expected cells.
    cells = {(r["scenario"], r["arm"], r["repetition"]) for r in data["runs"]}
    expected = {
        (sc, arm, rep)
        for sc in ("test-design-async", "atdd-api-async-corrected",
                   "docs-only-rust-repo")
        for arm in ("baseline", "candidate")
        for rep in (1, 2, 3)
    }
    assert cells == expected
    # Fixed seed and grader.
    assert data["seed"] > 0
    assert data["grader_version"]
