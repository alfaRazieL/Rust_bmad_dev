"""D3.3.3 v3 harness tests — auth-preserving isolation and admission.

Deterministic only; no live model calls. Covers §18:
  - auth env preserved / no CLAUDE_CONFIG_DIR override / no secret
  - arm-specific project skill install
  - exact model IDs
  - memory_paths dict parsing
  - auth failure classification
  - non-zero exit fail-closed / failure cannot be FINALIZED-admissible
  - success cleanup observed after lock release
  - evidence v3 admission invariants (schema negatives)
  - resume ignores failed as completed / status distinguishes states
  - Task forbidden / runtime tool policy
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

import run_live  # noqa: E402
import invoke_runtime  # noqa: E402
import prepare_workspace  # noqa: E402


# ----------------------------------------------- auth env preservation

def test_isolation_does_not_override_config_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", "/user/real/config")
    iso = run_live.ProjectRuntimeIsolation(
        workspace=tmp_path, arm="candidate", workflow="atdd")
    env = iso.env()
    # The auth config dir must be inherited UNCHANGED.
    assert env.get("CLAUDE_CONFIG_DIR") == "/user/real/config"
    # No API key / token injected.
    assert not env.get("ANTHROPIC_API_KEY")
    assert not env.get("CLAUDE_CODE_OAUTH_TOKEN")
    # Only the auto-memory guard is added.
    assert env.get("CLAUDE_CODE_DISABLE_AUTO_MEMORY") == "1"


def test_isolation_preflight_flags_injected_api_key(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-should-not-be-here")
    iso = run_live.ProjectRuntimeIsolation(
        workspace=tmp_path, arm="candidate", workflow="atdd")
    iso.bootstrap()
    # skills dir won't match (workspace has none), but the API-key error
    # must be present.
    errors = iso.preflight()
    assert any("ANTHROPIC_API_KEY" in e for e in errors)


def test_isolation_bootstrap_writes_project_settings(tmp_path):
    iso = run_live.ProjectRuntimeIsolation(
        workspace=tmp_path, arm="candidate", workflow="atdd")
    iso.bootstrap()
    settings = json.loads(iso.settings_path.read_text())
    assert settings["autoMemoryEnabled"] is False
    assert settings["disableBundledSkills"] is True
    mcp = json.loads(iso.mcp_config_path.read_text())
    assert mcp["mcpServers"] == {}


def test_isolation_disallows_task_tools():
    iso = run_live.ProjectRuntimeIsolation(
        workspace=Path("/tmp/x"), arm="candidate", workflow="atdd")
    assert iso.disallowed_tools() == ["Task", "TaskOutput", "TaskStop"]


# --------------------------------------------------- exact model IDs

def test_exact_model_rejects_alias():
    with pytest.raises(RuntimeError):
        invoke_runtime._assert_exact_model("haiku", require_exact=True)
    with pytest.raises(RuntimeError):
        invoke_runtime._assert_exact_model("sonnet", require_exact=True)


def test_exact_model_accepts_dated_id():
    # Should not raise.
    invoke_runtime._assert_exact_model("claude-haiku-4-5-20251001",
                                       require_exact=True)


def test_exact_model_rejects_opus_even_dated():
    with pytest.raises(RuntimeError):
        invoke_runtime._assert_exact_model("opus", require_exact=True)


# --------------------------------------------- memory_paths dict parse

def test_memory_paths_dict_not_collapsed(tmp_path):
    t = tmp_path / "t.jsonl"
    t.write_text(json.dumps({
        "type": "system", "subtype": "init",
        "model": "claude-haiku-4-5-20251001",
        "tools": ["Skill", "Bash"],
        "memory_paths": {"auto": "/some/path/memory/"},
    }) + "\n", encoding="utf-8")
    surface = run_live._extract_runtime_init(t)
    assert surface["memory_paths"] == ["auto:/some/path/memory/"]
    assert surface["memory_paths"] != []


def test_memory_paths_variants():
    assert run_live._normalise_memory_paths(None) == []
    assert run_live._normalise_memory_paths("") == []
    assert run_live._normalise_memory_paths("/a") == ["/a"]
    assert run_live._normalise_memory_paths(["/a", "/b"]) == ["/a", "/b"]
    assert run_live._normalise_memory_paths({"auto": "/x"}) == ["auto:/x"]


def test_extra_init_fields_parsed(tmp_path):
    t = tmp_path / "t.jsonl"
    t.write_text(json.dumps({
        "type": "system", "subtype": "init",
        "model": "claude-haiku-4-5-20251001",
        "tools": ["Skill"],
        "apiKeySource": "none",
        "agents": ["Explore"],
        "analytics_disabled": False,
        "output_style": "default",
        "fast_mode_state": "off",
    }) + "\n", encoding="utf-8")
    s = run_live._extract_runtime_init(t)
    assert s["api_key_source"] == "none"
    assert s["output_style"] == "default"
    assert s["fast_mode_state"] == "off"


# ------------------------------------------- auth failure classification

def _obs(**kw):
    base = dict(observed_mode="OBSERVED_SEQUENTIAL",
               observed_mode_basis="no-subagent-events-surrogate",
               wrapper_skill_invoked=True, child_skill_invoked=True,
               task_tool_use_count=0, transcript_sha256="x", session_id="s")
    base.update(kw)
    return run_live.TranscriptObservation(**base)


def test_apiKeySource_none_is_not_auth_failure():
    """§10.2/§3 — apiKeySource none with a clean terminal result is NOT
    an auth failure."""
    runtime_result = {"authentication_failed": False, "is_error": False,
                       "result_event_seen": True, "model_turn_seen": True}
    out = run_live.classify_run_outcome(
        invocation={"exit_code": 0}, runtime_result=runtime_result,
        surface_diff={}, handshake={"mismatch": False},
        observed_model="claude-haiku-4-5-20251001",
        expected_model="claude-haiku-4-5-20251001",
        obs=_obs(), arm="candidate",
        candidate_checks={"bundle_present": True, "artifacts_non_empty": True,
                          "active_packs_ok": True, "verifier_all_pass": True,
                          "one_sidecar_per_artifact": True,
                          "active_packs": ["api", "async"],
                          "expected_packs": ["api", "async"]})
    assert out.outcome == "SUCCESS"
    assert out.admissible is True


def test_authentication_failed_classified():
    runtime_result = {"authentication_failed": True, "is_error": True,
                       "result_event_seen": True, "model_turn_seen": True}
    out = run_live.classify_run_outcome(
        invocation={"exit_code": 1}, runtime_result=runtime_result,
        surface_diff={}, handshake={"mismatch": False},
        observed_model="", expected_model="claude-haiku-4-5-20251001",
        obs=_obs(wrapper_skill_invoked=False, child_skill_invoked=False),
        arm="candidate")
    assert out.outcome == "AUTH_FAILURE"
    assert out.admissible is False


def test_nonzero_exit_fail_closed():
    runtime_result = {"authentication_failed": False, "is_error": False,
                       "result_event_seen": True, "model_turn_seen": True}
    out = run_live.classify_run_outcome(
        invocation={"exit_code": 2}, runtime_result=runtime_result,
        surface_diff={}, handshake={"mismatch": False},
        observed_model="claude-haiku-4-5-20251001",
        expected_model="claude-haiku-4-5-20251001",
        obs=_obs(), arm="candidate")
    assert out.outcome == "RUNTIME_FAILURE"
    assert out.admissible is False


def test_task_dispatch_is_workflow_failure():
    runtime_result = {"authentication_failed": False, "is_error": False,
                       "result_event_seen": True, "model_turn_seen": True}
    out = run_live.classify_run_outcome(
        invocation={"exit_code": 0}, runtime_result=runtime_result,
        surface_diff={}, handshake={"mismatch": False},
        observed_model="claude-haiku-4-5-20251001",
        expected_model="claude-haiku-4-5-20251001",
        obs=_obs(task_tool_use_count=1), arm="candidate")
    assert out.outcome == "WORKFLOW_FAILURE"


def test_contamination_classified():
    runtime_result = {"authentication_failed": False, "is_error": False,
                       "result_event_seen": True, "model_turn_seen": True}
    out = run_live.classify_run_outcome(
        invocation={"exit_code": 0}, runtime_result=runtime_result,
        surface_diff={"unexpected_mcp_servers": ["evil-mcp"]},
        handshake={"mismatch": False},
        observed_model="claude-haiku-4-5-20251001",
        expected_model="claude-haiku-4-5-20251001",
        obs=_obs(), arm="candidate")
    assert out.outcome == "CONTAMINATION"


# ------------------------------------------- v3 schema admission invariants

def _valid_v3_candidate(**overrides):
    b = {
        "schema_version": "rdx-tea-live-evidence.v3",
        "arm": "candidate",
        "scenario": "atdd-api-async-corrected",
        "workflow": "atdd",
        "repetition": 1,
        "run_id": "smoke-atdd-corrected-d3-3-3",
        "run_id_handshake": {"schedule": "smoke-atdd-corrected-d3-3-3", "mismatch": False},
        "auth_preflight_id": "D3_3_3_AUTH_PREFLIGHT",
        "workspace": {"path": "/tmp/ws", "config_dir_overridden": False,
                       "fixture_hash": "a" * 64},
        "identity": {"base_sha": "a" * 40, "head_sha": "b" * 40},
        "runtime": {"expected_surface": {}, "observed_surface": {},
                     "surface_diff": {}, "contamination": "",
                     "model_expected": "claude-haiku-4-5-20251001",
                     "model_observed": "claude-haiku-4-5-20251001"},
        "invocation": {"command_hash": "c" * 64, "prompt_hash": "d" * 64,
                        "exit_code": 0, "reason": "normal"},
        "runtime_result": {"result_event_seen": True, "is_error": False,
                            "authentication_failed": False, "model_turn_seen": True},
        "artifacts": {"new_artefacts": ["x.md"]},
        "hashes": {"run_report": "", "transcript": "", "bundle": ""},
        "observation": {"observed_mode": "OBSERVED_SEQUENTIAL",
                         "wrapper_skill_invoked": True, "child_skill_invoked": True,
                         "task_tool_use_count": 0, "transcript_sha256": "z",
                         "session_id": "s"},
        "run_outcome": "SUCCESS",
        "admissible": True,
        "admission_reasons": ["ok"],
        "cleanup": {"state": "FINALIZED",
                     "observed": {"lock_state": "absent", "overlay_state": "absent",
                                   "run_dir_retained": True, "transcript_retained": True}},
        "candidate": {"wrapper_skill_invoked": True, "child_skill_invoked": True,
                       "sidecars": ["s.json"], "active_packs": ["api", "async"],
                       "expected_rp_ids": ["RP-ASYNC-005", "RP-API-001"],
                       "verifier_all_pass": True, "bundle_present": True},
    }
    b.update(overrides)
    return b


def test_v3_schema_accepts_admissible_candidate():
    assert run_live._validate_bundle_v3(_valid_v3_candidate()) == []


def test_v3_schema_rejects_admissible_with_nonzero_exit():
    b = _valid_v3_candidate()
    b["invocation"]["exit_code"] = 1
    errors = run_live._validate_bundle_v3(b)
    assert errors, "admissible=true + exit!=0 must be rejected"


def test_v3_schema_rejects_admissible_with_contamination():
    b = _valid_v3_candidate()
    b["runtime"]["contamination"] = "unexpected_mcp_servers"
    assert run_live._validate_bundle_v3(b), "admissible+contamination rejected"


def test_v3_schema_rejects_admissible_with_run_id_mismatch():
    b = _valid_v3_candidate()
    b["run_id_handshake"]["mismatch"] = True
    assert run_live._validate_bundle_v3(b)


def test_v3_schema_rejects_admissible_candidate_without_wrapper():
    b = _valid_v3_candidate()
    b["observation"]["wrapper_skill_invoked"] = False
    assert run_live._validate_bundle_v3(b)


def test_v3_schema_rejects_admissible_auth_failed():
    b = _valid_v3_candidate()
    b["runtime_result"]["authentication_failed"] = True
    assert run_live._validate_bundle_v3(b)


def test_failure_bundle_cannot_be_admissible_finalized():
    """A run that failed cannot be admissible=true; and if exit!=0 the
    schema forbids admissible=true regardless of cleanup.state."""
    b = _valid_v3_candidate()
    b["run_outcome"] = "AUTH_FAILURE"
    b["admissible"] = True  # dishonest
    b["runtime_result"]["authentication_failed"] = True
    b["invocation"]["exit_code"] = 1
    assert run_live._validate_bundle_v3(b), "dishonest admissible must be rejected"


# ---------------------------------------------- admission gate recompute

def test_admit_bundle_passes_valid_candidate():
    res = run_live.admit_bundle(_valid_v3_candidate())
    assert res.admissible is True
    assert res.run_outcome == "SUCCESS"


def test_admit_bundle_flags_wrong_active_packs():
    b = _valid_v3_candidate()
    b["candidate"]["active_packs"] = ["async"]  # missing api
    res = run_live.admit_bundle(b)
    assert res.admissible is False
    assert any("active_packs" in r for r in res.reasons)


def test_admit_bundle_flags_lock_still_present():
    b = _valid_v3_candidate()
    b["cleanup"]["observed"]["lock_state"] = "owned-still-present"
    res = run_live.admit_bundle(b)
    assert res.admissible is False


# ---------------------------------------------- arm-specific skill install

@pytest.mark.parametrize("arm,expected", [
    ("baseline", ["bmad-testarch-atdd"]),
    ("candidate", ["bmad-testarch-atdd", "rdx-tea-atdd"]),
])
def test_arm_skills_mapping(arm, expected):
    assert sorted(prepare_workspace._arm_skills(arm, "atdd")) == sorted(expected)


def test_prepare_installs_only_arm_skills(tmp_path):
    upstream = os.environ.get("RDX_TEA_UPSTREAM_ROOT")
    tea = (Path(upstream) / "bmad-method-test-architecture-enterprise"
           if upstream else LIVE.parent.parent.parent
           / "upstream" / "bmad-method-test-architecture-enterprise")
    if not tea.exists():
        pytest.skip("upstream TEA not available for full prepare test")
    dest = tmp_path / "cand"
    prep = prepare_workspace.prepare(
        dest=dest,
        fixture=LIVE / "fixtures" / "atdd-api-async-corrected",
        scenario="atdd-api-async-corrected", workflow="atdd",
        run_id="test-cand", arm="candidate")
    skills = sorted(p.name for p in (dest / ".claude" / "skills").iterdir()
                     if p.is_dir())
    assert skills == ["bmad-testarch-atdd", "rdx-tea-atdd"]
    # No unrelated RDX skill (rdx-tea-test-design must NOT be present).
    assert "rdx-tea-test-design" not in skills

    dest2 = tmp_path / "base"
    prepare_workspace.prepare(
        dest=dest2,
        fixture=LIVE / "fixtures" / "atdd-api-async-corrected",
        scenario="atdd-api-async-corrected", workflow="atdd",
        run_id="test-base", arm="baseline")
    bskills = sorted(p.name for p in (dest2 / ".claude" / "skills").iterdir()
                      if p.is_dir())
    assert bskills == ["bmad-testarch-atdd"]
    assert "rdx-tea-atdd" not in bskills


# ---------------------------------------- cleanup observed after lock release

def test_release_lock_before_observe(tmp_path):
    ws = tmp_path / "ws"
    (ws / "_bmad" / "rdx-tea" / "runtime" / "atdd" / "r-1").mkdir(parents=True)
    (ws / "_bmad" / "rdx-tea" / "runtime" / "atdd" / "r-1"
     / "transcript.stream.jsonl").write_text("{}", encoding="utf-8")
    run_live.write_lock_json(ws, run_id="r-1", workflow="atdd")
    # Before release: lock present.
    pre = run_live.observe_cleanup(workspace=ws, workflow="atdd", run_id="r-1")
    assert pre["lock_state"] == "owned-still-present"
    # Release then observe.
    run_live._release_lock_and_overlay(ws, "atdd", "r-1")
    post = run_live.observe_cleanup(workspace=ws, workflow="atdd", run_id="r-1")
    assert post["lock_state"] == "absent"
    assert post["transcript_retained"] is True


# ----------------------------------------------- tool policy shape

def test_tea_tools_policy_forbids_task():
    policy = json.loads((LIVE / "policies" / "tea-tools-v1.json").read_text())
    for wf in ("atdd", "test-design"):
        entry = policy["workflows"][wf]
        assert "Task" in entry["forbidden_tools"]
        assert "Skill" in entry["required_tools"]
        assert "Task" not in entry["required_tools"]
    assert policy["source_hashes"]


# ----------------------------------------- resume/status admissibility (pilot)

def _write_bundle(evidence_dir: Path, admissible: bool, outcome: str):
    evidence_dir.mkdir(parents=True, exist_ok=True)
    b = _valid_v3_candidate()
    b["admissible"] = admissible
    b["run_outcome"] = outcome
    if not admissible:
        b["runtime_result"]["authentication_failed"] = True
        b["runtime_result"]["is_error"] = True
        b["invocation"]["exit_code"] = 1
    (evidence_dir / "live-evidence.v3.json").write_text(
        json.dumps(b), encoding="utf-8")


def test_run_pilot_status_and_resume_classify_admissibility(tmp_path):
    sys.path.insert(0, str(LIVE.parent / "evals"))
    import run_pilot
    schedule = run_pilot.load_schedule()
    plans = run_pilot.build_plan(schedule, tmp_path)
    # Mark one run completed (admissible), one failed (auth), leave rest pending.
    _write_bundle(plans[0].evidence_dir, True, "SUCCESS")
    _write_bundle(plans[1].evidence_dir, False, "AUTH_FAILURE")
    st = run_pilot.status(schedule, tmp_path)
    assert plans[0].run_id in st["completed"]
    assert plans[1].run_id in st["failed"]
    assert plans[1].run_id not in st["completed"]
    assert st["total"] == 18
    # resume: the failed run is NOT treated as completed.
    outcomes = run_pilot.resume(schedule, tmp_path, dry_run=True)
    by_id = {o["run_id"]: o for o in outcomes}
    assert by_id[plans[0].run_id]["status"] == "already-completed"
    assert by_id[plans[1].run_id]["status"] != "already-completed"
