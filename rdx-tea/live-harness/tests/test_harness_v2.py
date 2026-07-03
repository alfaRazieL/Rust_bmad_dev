"""D3.3.2 v2 harness tests.

Additive to test_harness_unit.py; exercises the arm-aware execution
path, structured-only classifier, init-event parser, runtime-preflight,
JSON lock, observed cleanup, invocation contract, and v2 schema
branches.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
LIVE = HERE.parent
sys.path.insert(0, str(LIVE))

import run_live  # noqa: E402


# ------------------------------------------------------ arm-specific paths

def test_arm_prompt_baseline_never_mentions_rdx():
    p = run_live.arm_prompt("baseline", "atdd", "pilot-001")
    lo = p.lower()
    for banned in ("rdx", "wrapper", "rp-", "active-context",
                   "prepare-run", "finalize-run"):
        assert banned not in lo, (banned, p)
    assert "/bmad-testarch-atdd" in p
    assert "pilot-001" in p


def test_arm_prompt_candidate_names_wrapper_and_run_id():
    p = run_live.arm_prompt("candidate", "atdd", "pilot-042")
    # D3.3.3: the wrapper is invoked via the Skill tool (no slash prefix)
    # so the runtime emits a structured wrapper Skill event.
    assert "rdx-tea-atdd" in p
    assert "pilot-042" in p


def test_arm_prompts_are_different():
    b = run_live.arm_prompt("baseline", "atdd", "pilot-001")
    c = run_live.arm_prompt("candidate", "atdd", "pilot-001")
    assert b != c
    assert run_live._sha256_text(b) != run_live._sha256_text(c)


def test_arm_installed_skills_baseline_excludes_wrapper():
    baseline = run_live.arm_installed_skills("baseline", "atdd")
    candidate = run_live.arm_installed_skills("candidate", "atdd")
    assert "bmad-testarch-atdd" in baseline
    assert "rdx-tea-atdd" not in baseline
    assert "rdx-tea-atdd" in candidate
    assert "bmad-testarch-atdd" in candidate


# ------------------------------------------- structured-only classifier

def _stream(events):
    return "\n".join(json.dumps(e) for e in events) + "\n"


def test_classifier_ignores_free_text_wrapper_mention(tmp_path):
    """§8 adversarial case: assistant prose that mentions the wrapper
    without a tool_use event MUST NOT set wrapper_skill_invoked."""
    path = tmp_path / "t.jsonl"
    path.write_text(_stream([
        {"type": "assistant", "message": {"content": [
            {"type": "text",
             "text": "I would invoke rdx-tea-atdd and bmad-testarch-atdd next."}
        ]}},
    ]), encoding="utf-8")
    obs = run_live._classify_transcript(path, "atdd")
    assert obs.wrapper_skill_invoked is False
    assert obs.child_skill_invoked is False
    assert obs.observed_mode == "INFERRED_ABSENT"


def test_classifier_ignores_user_prompt_mention(tmp_path):
    """A user prompt that mentions both skill names is NOT evidence
    of invocation."""
    path = tmp_path / "t.jsonl"
    path.write_text(_stream([
        {"type": "user", "message": {"content": [
            {"type": "text",
             "text": "Please invoke /rdx-tea-atdd which calls "
                     "/bmad-testarch-atdd."}
        ]}},
    ]), encoding="utf-8")
    obs = run_live._classify_transcript(path, "atdd")
    assert obs.wrapper_skill_invoked is False
    assert obs.child_skill_invoked is False


def test_classifier_wrapper_only_leaves_child_false(tmp_path):
    path = tmp_path / "t.jsonl"
    path.write_text(_stream([
        {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "Skill",
             "input": {"skill": "rdx-tea-atdd"}},
        ]}},
    ]), encoding="utf-8")
    obs = run_live._classify_transcript(path, "atdd")
    assert obs.wrapper_skill_invoked is True
    assert obs.child_skill_invoked is False
    assert obs.observed_mode == "INFERRED_ABSENT"


def test_classifier_child_only_leaves_wrapper_false(tmp_path):
    path = tmp_path / "t.jsonl"
    path.write_text(_stream([
        {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "Skill",
             "input": {"skill": "bmad-testarch-atdd"}},
        ]}},
    ]), encoding="utf-8")
    obs = run_live._classify_transcript(path, "atdd")
    assert obs.wrapper_skill_invoked is False
    assert obs.child_skill_invoked is True
    assert obs.observed_mode == "INFERRED_ABSENT"


def test_classifier_task_tool_wins(tmp_path):
    """Any Task tool_use event → OBSERVED_SUBAGENT even if wrapper
    and child were also called."""
    path = tmp_path / "t.jsonl"
    path.write_text(_stream([
        {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "Skill",
             "input": {"skill": "rdx-tea-atdd"}},
            {"type": "tool_use", "name": "Skill",
             "input": {"skill": "bmad-testarch-atdd"}},
            {"type": "tool_use", "name": "Task",
             "input": {"description": "spawn subagent"}},
        ]}},
    ]), encoding="utf-8")
    obs = run_live._classify_transcript(path, "atdd")
    assert obs.observed_mode == "OBSERVED_SUBAGENT"
    assert obs.task_tool_use_count == 1


# ---------------------------------------------------- init event parser

def test_extract_runtime_init_reads_actual_fields(tmp_path):
    path = tmp_path / "t.jsonl"
    path.write_text(_stream([
        {"type": "system", "subtype": "init",
         "session_id": "sess-42",
         "claude_code_version": "2.1.126",
         "model": "claude-haiku-4-5-20251001",
         "permission_mode": "bypassPermissions",
         "tools": ["Bash", "Read", "Edit", "Skill"],
         "skills": [{"name": "rdx-tea-atdd"}, {"name": "bmad-testarch-atdd"}],
         "mcp_servers": [],
         "plugins": [],
         "memory_paths": []},
    ]), encoding="utf-8")
    surface = run_live._extract_runtime_init(path)
    assert surface["init_event_seen"] is True
    assert surface["claude_code_version"] == "2.1.126"
    assert surface["model"] == "claude-haiku-4-5-20251001"
    assert surface["permission_mode"] == "bypassPermissions"
    assert "Skill" in surface["tools"]
    assert "rdx-tea-atdd" in surface["skills"]
    assert surface["session_id"] == "sess-42"


def test_compare_runtime_surface_flags_contamination():
    observed = {"tools": ["Bash", "Skill"],
                "skills": ["rdx-tea-atdd", "bmad-testarch-atdd",
                           "unrelated-user-skill"],
                "mcp_servers": ["user-random-mcp"],
                "plugins": [],
                "model": "claude-haiku-4-5-20251001",
                "permission_mode": "bypassPermissions"}
    expected = {"tools": [],
                "skills": ["rdx-tea-atdd", "bmad-testarch-atdd"],
                "mcp_servers": [],
                "plugins": [],
                "model": "claude-haiku-4-5-20251001",
                "permission_mode": "bypassPermissions"}
    diff = run_live.compare_runtime_surface(observed, expected)
    assert diff["unexpected_skills"] == ["unrelated-user-skill"]
    assert diff["unexpected_mcp_servers"] == ["user-random-mcp"]
    reason = run_live.contamination_reason(diff)
    assert reason in ("unexpected_mcp_servers", "unexpected_plugins",
                      "unexpected_skills")


# ------------------------------------------------------ JSON lock

def test_json_lock_owned_by_exact_equality(tmp_path):
    (tmp_path / "_bmad" / "rdx-tea" / "runtime").mkdir(parents=True)
    run_live.write_lock_json(tmp_path, run_id="pilot-001", workflow="atdd")
    assert run_live._lock_owned_by(tmp_path, "pilot-001", "atdd") is True
    # A partial-substring match must NOT be considered ownership.
    assert run_live._lock_owned_by(tmp_path, "pilot-00", "atdd") is False
    assert run_live._lock_owned_by(tmp_path, "pilot-001", "test-design") is False


def test_json_lock_treats_legacy_string_as_unowned(tmp_path):
    lock_path = tmp_path / "_bmad" / "rdx-tea" / "runtime" / "active-run.lock"
    lock_path.parent.mkdir(parents=True)
    lock_path.write_text("atdd pilot-001 42\n", encoding="utf-8")
    # legacy string lock -> not JSON -> classified as unowned.
    assert run_live._lock_owned_by(tmp_path, "pilot-001", "atdd") is False


# ---------------------------------------------------- invocation contract

def test_emit_invocation_contract_shape(tmp_path):
    ws = tmp_path / "ws"
    (ws).mkdir()
    p = run_live.emit_invocation_contract(
        workspace=ws, run_id="pilot-007", scenario="atdd-api-async-corrected",
        arm="candidate", workflow="atdd", repetition=1,
        base_sha="a" * 40, head_sha="b" * 40,
        fixture_hash="c" * 64, prompt_hash="d" * 64,
    )
    data = json.loads(p.read_text())
    assert data["schema_version"] == "rdx-tea-invocation.v1"
    assert data["run_id"] == "pilot-007"
    assert data["arm"] == "candidate"


# --------------------------------------------- run_id handshake check

def test_run_id_handshake_no_mismatch_when_only_schedule(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    hs = run_live._check_run_id_handshake(
        workspace=ws, workflow="atdd", run_id="pilot-001",
    )
    assert hs["mismatch"] is False


def test_run_id_handshake_detects_mismatch(tmp_path):
    ws = tmp_path / "ws"
    (ws / "_bmad-run").mkdir(parents=True)
    (ws / "_bmad-run" / "rdx-tea-invocation.json").write_text(json.dumps({
        "run_id": "pilot-999",
    }), encoding="utf-8")
    hs = run_live._check_run_id_handshake(
        workspace=ws, workflow="atdd", run_id="pilot-001",
    )
    assert hs["mismatch"] is True
    assert hs["invocation_json"] == "pilot-999"


# ---------------------------------------------- v2 schema branches

_BASE_COMMON = {
    "schema_version": "rdx-tea-live-evidence.v2",
    "workflow": "atdd",
    "repetition": 1,
    "run_id": "pilot-001",
    "run_id_handshake": {"schedule": "pilot-001", "mismatch": False},
    "workspace": {"path": "/tmp/ws", "config_dir": "/tmp/cfg",
                    "config_dir_hash": "0" * 64,
                    "fixture_hash": "1" * 64},
    "identity": {"base_sha": "a" * 40, "head_sha": "b" * 40},
    "runtime": {
        "claude_code_path": "/opt/homebrew/bin/claude",
        "expected_surface": {},
        "observed_surface": {
            "claude_code_version": "2.1.126",
            "model": "haiku",
            "permission_mode": "bypassPermissions",
            "tools": [], "skills": [], "slash_commands": [],
            "mcp_servers": [], "plugins": [], "memory_paths": [],
            "session_id": "sess-1", "init_event_seen": True,
        },
        "surface_diff": {},
        "contamination": "",
        "timeout_seconds": 600,
        "max_budget_usd": 2.0,
    },
    "invocation": {
        "command_hash": "c" * 64,
        "prompt_hash": "d" * 64,
        "started_at": "2026-07-03T00:00:00+00:00",
        "finished_at": "2026-07-03T00:05:00+00:00",
        "exit_code": 0,
        "reason": "normal",
    },
    "artifacts": {"new_artefacts": []},
    "hashes": {"run_report": "e" * 64, "transcript": "f" * 64,
                "bundle": "0" * 64},
    "observation": {
        "observed_mode": "OBSERVED_SEQUENTIAL",
        "observed_mode_basis": "no-subagent-events-surrogate",
        "wrapper_skill_invoked": True,
        "child_skill_invoked": True,
        "task_tool_use_count": 0,
        "transcript_sha256": "1" * 64,
        "session_id": "sess-1",
    },
    "cleanup": {"state": "FINALIZED",
                  "observed": {"lock_state": "absent",
                                "overlay_state": "absent",
                                "run_dir_retained": True,
                                "transcript_retained": True}},
}


def _load_v2_schema():
    import jsonschema
    schema = json.loads(run_live.SCHEMA_V2_PATH.read_text(encoding="utf-8"))
    return jsonschema.Draft202012Validator(schema)


def test_v2_schema_accepts_minimal_candidate():
    validator = _load_v2_schema()
    bundle = dict(_BASE_COMMON)
    bundle["arm"] = "candidate"
    bundle["scenario"] = "atdd-api-async-corrected"
    bundle["candidate"] = {
        "wrapper_skill_invoked": True,
        "child_skill_invoked": True,
        "sidecars": ["sidecar-1.json"],
        "active_packs": ["api", "async"],
        "expected_rp_ids": ["RP-ASYNC-005"],
        "verifier_all_pass": True,
        "bundle_present": True,
    }
    errors = list(validator.iter_errors(bundle))
    assert errors == [], errors


def test_v2_schema_accepts_minimal_baseline():
    validator = _load_v2_schema()
    bundle = dict(_BASE_COMMON)
    bundle["arm"] = "baseline"
    bundle["scenario"] = "atdd-api-async-corrected"
    bundle["observation"] = dict(_BASE_COMMON["observation"])
    bundle["observation"]["wrapper_skill_invoked"] = False
    bundle["baseline"] = {
        "wrapper_skill_invoked": False,
        "direct_child_skill_invoked": True,
        "rdx_bundle_absent": True,
        "rdx_sidecars_absent": True,
        "rdx_overlay_absent": True,
    }
    errors = list(validator.iter_errors(bundle))
    assert errors == [], errors


def test_v2_schema_rejects_baseline_with_wrapper_invoked():
    validator = _load_v2_schema()
    bundle = dict(_BASE_COMMON)
    bundle["arm"] = "baseline"
    bundle["scenario"] = "test-design-async"
    bundle["baseline"] = {
        "wrapper_skill_invoked": True,   # <-- must be False by schema
        "direct_child_skill_invoked": True,
        "rdx_bundle_absent": True,
        "rdx_sidecars_absent": True,
        "rdx_overlay_absent": True,
    }
    errors = list(validator.iter_errors(bundle))
    assert errors, "baseline with wrapper_skill_invoked=True must be rejected"


def test_v2_schema_rejects_baseline_carrying_candidate_block():
    validator = _load_v2_schema()
    bundle = dict(_BASE_COMMON)
    bundle["arm"] = "baseline"
    bundle["scenario"] = "test-design-async"
    bundle["baseline"] = {
        "wrapper_skill_invoked": False,
        "direct_child_skill_invoked": True,
        "rdx_bundle_absent": True,
        "rdx_sidecars_absent": True,
        "rdx_overlay_absent": True,
    }
    bundle["candidate"] = {
        "wrapper_skill_invoked": True,
        "child_skill_invoked": True,
        "sidecars": [],
        "active_packs": ["async"],
        "expected_rp_ids": ["RP-ASYNC-005"],
        "verifier_all_pass": True,
        "bundle_present": True,
    }
    errors = list(validator.iter_errors(bundle))
    assert errors, "baseline+candidate blocks must not co-exist"


def test_v2_schema_rejects_candidate_missing_block():
    validator = _load_v2_schema()
    bundle = dict(_BASE_COMMON)
    bundle["arm"] = "candidate"
    bundle["scenario"] = "test-design-async"
    # NO candidate block
    errors = list(validator.iter_errors(bundle))
    assert errors, "candidate arm without candidate block must be rejected"


# ---------------------------------------------- schedule v2 shape

def test_schedule_v2_locked_and_18_runs():
    p = LIVE.parent / "evals" / "runs" / "D3_4_PILOT_RUNS.v2.json"
    if not p.exists():
        pytest.skip("schedule v2 not landed yet")
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data["schema_version"] == "rdx-tea-pilot-runs.v2"
    assert data["locked"] is True
    assert data["rubric_version"] == "rdx-tea-pilot-rubric.v3"
    assert len(data["runs"]) == 18
    scenarios = {r["scenario"] for r in data["runs"]}
    assert scenarios == {
        "test-design-async", "atdd-api-async-corrected",
        "docs-only-rust-repo",
    }
    ids = {r["run_id"] for r in data["runs"]}
    assert len(ids) == 18, "all 18 run ids must be unique"


# ------------------------------------------ observed cleanup

def test_observe_cleanup_reports_actual_state(tmp_path):
    ws = tmp_path / "ws"
    (ws / "_bmad" / "rdx-tea" / "runtime" / "atdd" / "r-1").mkdir(parents=True)
    (ws / "_bmad" / "custom").mkdir()
    obs = run_live.observe_cleanup(workspace=ws, workflow="atdd", run_id="r-1")
    assert obs["lock_state"] == "absent"
    assert obs["overlay_state"] == "absent"
    assert obs["run_dir_retained"] is True
    assert obs["transcript_retained"] is False


def test_observe_cleanup_flags_foreign_overlay(tmp_path):
    ws = tmp_path / "ws"
    (ws / "_bmad" / "rdx-tea" / "runtime" / "atdd" / "r-1").mkdir(parents=True)
    (ws / "_bmad" / "custom").mkdir()
    (ws / "_bmad" / "custom" / "bmad-testarch-atdd.toml").write_text(
        "[workflow]\n# user overlay\n", encoding="utf-8",
    )
    obs = run_live.observe_cleanup(workspace=ws, workflow="atdd", run_id="r-1")
    assert obs["overlay_state"] == "foreign-preserved"
