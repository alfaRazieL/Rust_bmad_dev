"""D3.4.0 v4 harness tests — rule-operation, workspace delta, artifact
consistency, schema v4, schedule binding, grader. Deterministic only.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
LIVE = HERE.parent
sys.path.insert(0, str(LIVE))
sys.path.insert(0, str(LIVE.parent / "evals" / "grading"))

import run_live  # noqa: E402
import rule_operation as ro  # noqa: E402


# --------------------------------------------------- workspace delta

def _init_git_ws(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=ws, check=True)
    (ws / "base.txt").write_text("base", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=ws, check=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t",
                    "commit", "-q", "-m", "base"], cwd=ws, check=True)
    return ws


def test_workspace_delta_lists_created(tmp_path):
    ws = _init_git_ws(tmp_path)
    (ws / "tests").mkdir()
    (ws / "tests" / "new_test.rs").write_text("fn t() {}", encoding="utf-8")
    delta = ro.collect_workspace_delta(ws)
    assert "tests/new_test.rs" in delta["created_files"]


def test_declared_generated_file_exists_passes(tmp_path):
    ws = _init_git_ws(tmp_path)
    (ws / "_bmad-output").mkdir()
    (ws / "tests").mkdir()
    (ws / "tests" / "gen.rs").write_text("fn g() {}", encoding="utf-8")
    art = ws / "_bmad-output" / "checklist.md"
    art.write_text(
        "---\ngeneratedTestFiles:\n  - 'tests/gen.rs'\n---\n# c\n",
        encoding="utf-8")
    delta = ro.collect_workspace_delta(ws, artifact_paths=[art])
    assert delta["declared_existing_files"] == ["tests/gen.rs"]
    assert delta["declared_missing_files"] == []
    status, reasons = ro.workspace_delta_consistency(delta)
    assert status == "PASS"


def test_declared_generated_file_missing_inadmissible(tmp_path):
    ws = _init_git_ws(tmp_path)
    (ws / "_bmad-output").mkdir()
    art = ws / "_bmad-output" / "checklist.md"
    art.write_text(
        "---\ngeneratedTestFiles:\n  - 'tests/phantom.rs'\n---\n# c\n",
        encoding="utf-8")
    delta = ro.collect_workspace_delta(ws, artifact_paths=[art])
    assert "tests/phantom.rs" in delta["declared_missing_files"]
    status, reasons = ro.workspace_delta_consistency(delta)
    assert status == "FAIL"


def test_planned_not_generated_escape_hatch(tmp_path):
    ws = _init_git_ws(tmp_path)
    (ws / "_bmad-output").mkdir()
    art = ws / "_bmad-output" / "checklist.md"
    art.write_text(
        "---\ngeneratedTestFiles:\n  - 'tests/planned.rs'\n"
        "declarationPlannedNotGenerated: true\n---\n",
        encoding="utf-8")
    delta = ro.collect_workspace_delta(ws, artifact_paths=[art])
    status, _ = ro.workspace_delta_consistency(delta)
    assert status == "PASS"  # missing file tolerated because planned


# --------------------------------------------------- artifact consistency

def test_duplicate_frontmatter_keys_detected_but_reconcilable(tmp_path):
    ws = _init_git_ws(tmp_path)
    (ws / "_bmad-output").mkdir()
    (ws / "tests").mkdir()
    (ws / "tests" / "a.rs").write_text("fn a(){}", encoding="utf-8")
    art = ws / "_bmad-output" / "c.md"
    art.write_text(
        "---\ngeneratedTestFiles:\n  - 'tests/a.rs'\n"
        "storyId: 'x'\ngeneratedTestFiles: []\nstoryId: 'x'\n---\n",
        encoding="utf-8")
    delta = ro.collect_workspace_delta(ws, artifact_paths=[art])
    ac = ro.check_artifact_consistency([art], ws, delta)
    # duplicate keys recorded as warnings
    assert any("generatedTestFiles" in k for k in ac["duplicate_frontmatter_keys"])
    # but reconcilable with reality (tests/a.rs exists) → PASS
    assert ac["status"] == "PASS"
    assert ac["contradictory_frontmatter"] == []


def test_contradictory_frontmatter_unreconcilable_fails(tmp_path):
    ws = _init_git_ws(tmp_path)
    (ws / "_bmad-output").mkdir()
    art = ws / "_bmad-output" / "c.md"
    # declares a file in one block that does not exist → contradiction
    art.write_text(
        "---\ngeneratedTestFiles:\n  - 'tests/ghost.rs'\n"
        "generatedTestFiles: []\n---\n",
        encoding="utf-8")
    delta = ro.collect_workspace_delta(ws, artifact_paths=[art])
    ac = ro.check_artifact_consistency([art], ws, delta)
    assert ac["status"] == "FAIL"
    assert ac["contradictory_frontmatter"]


# --------------------------------------------------- rule operation

def test_evaluate_rule_operation_forbidden_ignores_cross_reference(tmp_path):
    """A forbidden rule id mentioned only as a CROSS-REFERENCE in prose
    must NOT fail forbidden_rule_condition — only ACTIVE packs count."""
    criteria = run_live.load_rule_criteria()
    bundle = tmp_path / "active-context.md"
    bundle.write_text(
        "active_packs: api, async\n"
        "RP-API-004 owns X. See also RP-FFI-003 for ABI details.\n"
        "RP-ASYNC-005 cancellation.\n", encoding="utf-8")
    rr = tmp_path / "run-report.json"
    rr.write_text(json.dumps({"sidecars": [
        {"active_packs": [{"pack_id": "api", "rule_ids": ["RP-API-004"]},
                          {"pack_id": "async", "rule_ids": ["RP-ASYNC-005"]}]}]}),
        encoding="utf-8")
    res = run_live.evaluate_rule_operation(
        scenario="atdd-api-async-corrected", active_packs=["api", "async"],
        bundle_path=bundle, run_report_path=rr, artifact_paths=[],
        criteria=criteria)
    assert res["packs_ok"] is True
    assert res["expected_rule_condition"] == "PASS"
    assert res["forbidden_rule_condition"] == "PASS"


def test_evaluate_rule_operation_forbidden_active_pack_fails(tmp_path):
    criteria = run_live.load_rule_criteria()
    bundle = tmp_path / "active-context.md"
    bundle.write_text("RP-UNSAFE-001 active\n", encoding="utf-8")
    rr = tmp_path / "run-report.json"
    rr.write_text(json.dumps({"sidecars": [
        {"active_packs": [{"pack_id": "unsafe", "rule_ids": ["RP-UNSAFE-001"]}]}]}),
        encoding="utf-8")
    res = run_live.evaluate_rule_operation(
        scenario="atdd-api-async-corrected", active_packs=["api", "async", "unsafe"],
        bundle_path=bundle, run_report_path=rr, artifact_paths=[],
        criteria=criteria)
    assert res["forbidden_rule_condition"] == "FAIL"


def test_evaluate_rule_operation_any_of_api_rule(tmp_path):
    criteria = run_live.load_rule_criteria()
    bundle = tmp_path / "b.md"
    # cites RP-API-005 (member of any_of) but not RP-API-001
    bundle.write_text("RP-ASYNC-005 and RP-API-005 present\n", encoding="utf-8")
    rr = tmp_path / "rr.json"
    rr.write_text(json.dumps({"sidecars": []}), encoding="utf-8")
    res = run_live.evaluate_rule_operation(
        scenario="atdd-api-async-corrected", active_packs=["api", "async"],
        bundle_path=bundle, run_report_path=rr, artifact_paths=[],
        criteria=criteria)
    assert res["expected_rule_condition"] == "PASS"
    assert "RP-API-005" in res["matched_rules"]


# --------------------------------------------------- schedule binding

def _spec():
    return run_live.RunSpec(
        scenario="atdd-api-async-corrected", arm="candidate", repetition=1,
        workflow="atdd", fixture_dir=LIVE / "fixtures" / "atdd-api-async-latent",
        workspace_dir=Path("/tmp/x"), evidence_root=Path("/tmp/y"),
        run_id="r-1", model="claude-haiku-4-5-20251001")


def test_schedule_binding_not_scheduled_for_smoke():
    b = run_live.evaluate_schedule_binding(
        spec=_spec(), observed_prompt_hash="a", observed_fixture_hash="b",
        schedule_entry=None, schedule_sha256=None, pinned_schedule_sha256=None,
        criteria_version="v1", expected_criteria_version=None,
        schema_version="v4", expected_schema_version=None)
    assert b["status"] == "NOT_SCHEDULED"


@pytest.mark.parametrize("field,entry,obs_prompt,obs_fixture,sha,pinned", [
    ("prompt", {"prompt_hash": "OTHER", "fixture_hash": "b"}, "a", "b", None, None),
    ("fixture", {"prompt_hash": "a", "fixture_hash": "OTHER"}, "a", "b", None, None),
])
def test_schedule_binding_hash_drift_rejected(field, entry, obs_prompt, obs_fixture, sha, pinned):
    b = run_live.evaluate_schedule_binding(
        spec=_spec(), observed_prompt_hash=obs_prompt,
        observed_fixture_hash=obs_fixture, schedule_entry=entry,
        schedule_sha256=sha, pinned_schedule_sha256=pinned,
        criteria_version="v1", expected_criteria_version="v1",
        schema_version="v4", expected_schema_version="v4")
    assert b["status"] == "FAIL"


def test_schedule_binding_criteria_and_schema_drift():
    b = run_live.evaluate_schedule_binding(
        spec=_spec(), observed_prompt_hash="a", observed_fixture_hash="b",
        schedule_entry={"prompt_hash": "a", "fixture_hash": "b"},
        schedule_sha256="S", pinned_schedule_sha256="S",
        criteria_version="v2", expected_criteria_version="v1",
        schema_version="v3", expected_schema_version="v4")
    assert b["status"] == "FAIL"
    assert "criteria_version drift" in b["drift_reasons"]
    assert "schema_version drift" in b["drift_reasons"]


def test_schedule_binding_sha_drift():
    b = run_live.evaluate_schedule_binding(
        spec=_spec(), observed_prompt_hash="a", observed_fixture_hash="b",
        schedule_entry={"prompt_hash": "a", "fixture_hash": "b"},
        schedule_sha256="ACTUAL", pinned_schedule_sha256="PINNED",
        criteria_version="v1", expected_criteria_version="v1",
        schema_version="v4", expected_schema_version="v4")
    assert b["status"] == "FAIL"
    assert "schedule_sha256 drift" in b["drift_reasons"]


# --------- D3.4.1 regression: run-id-normalised prompt-template binding

_SCHEDULE_V3 = LIVE.parent / "evals" / "runs" / "D3_4_RULE_OPERATION_RUNS.v3.json"


def test_scheduled_prompt_hash_is_run_id_normalised_template():
    """The schedule pins the prompt TEMPLATE hash (run_id placeholder),
    which is why all repetitions of a scenario share one prompt_hash and
    why the runtime binding must normalise the run_id before hashing.

    Regression for the D3.4.1 false SCHEDULE_DRIFT: every scheduled run
    reported `prompt_hash drift` because the runtime compared the real
    per-run prompt (with the variable run_id embedded) against the
    template hash the schedule pins.
    """
    schedule = json.loads(_SCHEDULE_V3.read_text(encoding="utf-8"))
    runs = schedule["runs"]

    # (a) Each entry's pinned prompt_hash equals the run-id-normalised
    # template hash the runtime now computes for binding.
    for e in runs:
        template_hash = run_live._sha256_text(
            run_live.arm_prompt(e["arm"], e["workflow"], "__RUN_ID__"))
        assert e["prompt_hash"] == template_hash, e["run_id"]

    # (b) Repetitions of one scenario/arm share the template hash even
    # though their real run_ids (and thus real prompts) differ.
    reps = [e for e in runs
            if e["scenario"] == "test-design-async" and e["arm"] == "candidate"]
    assert len({e["run_id"] for e in reps}) == 3
    assert len({e["prompt_hash"] for e in reps}) == 1
    real_prompts = {run_live._sha256_text(
        run_live.arm_prompt(e["arm"], e["workflow"], e["run_id"])) for e in reps}
    assert len(real_prompts) == 3  # real per-run prompts genuinely differ

    # (c) Binding PASSES when compared with the normalised template hash.
    e0 = reps[0]
    b = run_live.evaluate_schedule_binding(
        spec=_spec(), observed_prompt_hash=e0["prompt_hash"],
        observed_fixture_hash=e0["fixture_hash"], schedule_entry=e0,
        schedule_sha256="S", pinned_schedule_sha256="S",
        criteria_version=e0["criteria_version"],
        expected_criteria_version=e0["criteria_version"],
        schema_version=e0["schema_version"],
        expected_schema_version=e0["schema_version"])
    assert b["status"] == "PASS", b["drift_reasons"]

    # (d) A genuine template change is still caught as drift.
    b2 = run_live.evaluate_schedule_binding(
        spec=_spec(), observed_prompt_hash="TAMPERED", observed_fixture_hash=e0["fixture_hash"],
        schedule_entry=e0, schedule_sha256="S", pinned_schedule_sha256="S",
        criteria_version=e0["criteria_version"],
        expected_criteria_version=e0["criteria_version"],
        schema_version=e0["schema_version"],
        expected_schema_version=e0["schema_version"])
    assert b2["status"] == "FAIL"
    assert "prompt_hash drift" in b2["drift_reasons"]


# --------------------------------------------------- v4 schema

def _valid_v4_candidate(**over):
    b = {
        "schema_version": "rdx-tea-live-evidence.v4", "arm": "candidate",
        "scenario": "atdd-api-async-corrected", "workflow": "atdd",
        "repetition": 1, "run_id": "run-0001",
        "run_id_handshake": {"schedule": "run-0001", "mismatch": False},
        "auth_preflight_id": "P",
        "workspace": {"path": "/w", "config_dir_overridden": False, "fixture_hash": "a"*64},
        "identity": {"base_sha": "a"*40, "head_sha": "b"*40},
        "runtime": {"expected_surface": {}, "observed_surface": {}, "surface_diff": {},
                     "contamination": "", "model_expected": "m", "model_observed": "m"},
        "invocation": {"command_hash": "c"*64, "prompt_hash": "d"*64, "exit_code": 0, "reason": "normal"},
        "runtime_result": {"result_event_seen": True, "is_error": False,
                            "authentication_failed": False, "model_turn_seen": True},
        "artifacts": {"new_artefacts": ["a.md"]},
        "hashes": {"run_report": "", "transcript": "", "bundle": ""},
        "observation": {"observed_mode": "OBSERVED_SEQUENTIAL", "wrapper_skill_invoked": True,
                         "child_skill_invoked": True, "task_tool_use_count": 0,
                         "transcript_sha256": "z", "session_id": "s"},
        "run_outcome": "SUCCESS", "admissible": True, "admission_reasons": ["ok"],
        "cleanup": {"state": "FINALIZED", "observed": {"lock_state": "absent",
                     "overlay_state": "absent", "run_dir_retained": True, "transcript_retained": True}},
        "workspace_delta": {"created_files": [], "modified_files": [], "deleted_files": [],
                             "declared_generated_files": [], "declared_existing_files": [],
                             "declared_missing_files": [], "consistency": "PASS"},
        "artifact_consistency": {"status": "PASS", "duplicate_frontmatter_keys": [],
                                  "contradictory_frontmatter": [], "phantom_file_claims": []},
        "schedule_binding": {"status": "NOT_SCHEDULED"},
        "rule_operation": {"active_packs": ["api", "async"], "expected_active_packs": ["api", "async"],
                            "packs_ok": True, "expected_rule_condition": "PASS",
                            "forbidden_rule_condition": "PASS"},
        "candidate": {"wrapper_skill_invoked": True, "child_skill_invoked": True,
                       "sidecars": ["s.json"], "active_packs": ["api", "async"],
                       "expected_rp_ids": ["RP-ASYNC-005"], "verifier_all_pass": True,
                       "bundle_present": True},
    }
    b.update(over)
    return b


def test_v4_schema_accepts_admissible_candidate():
    assert run_live._validate_bundle_v4(_valid_v4_candidate()) == []


def test_v4_schema_rejects_admissible_with_bad_workspace_delta():
    b = _valid_v4_candidate()
    b["workspace_delta"]["consistency"] = "FAIL"
    assert run_live._validate_bundle_v4(b)


def test_v4_schema_rejects_admissible_with_bad_artifact_consistency():
    b = _valid_v4_candidate()
    b["artifact_consistency"]["status"] = "FAIL"
    assert run_live._validate_bundle_v4(b)


def test_v4_schema_rejects_admissible_candidate_forbidden_fail():
    b = _valid_v4_candidate()
    b["rule_operation"]["forbidden_rule_condition"] = "FAIL"
    assert run_live._validate_bundle_v4(b)


def test_v4_schema_rejects_candidate_missing_rule_operation():
    b = _valid_v4_candidate()
    del b["rule_operation"]
    assert run_live._validate_bundle_v4(b)


def test_v4_admit_bundle_recomputes_candidate():
    res = run_live.admit_bundle(_valid_v4_candidate())
    assert res.admissible is True


def test_v4_admit_flags_forbidden():
    b = _valid_v4_candidate()
    b["rule_operation"]["forbidden_rule_condition"] = "FAIL"
    b["admissible"] = False
    b["run_outcome"] = "WORKFLOW_FAILURE"
    res = run_live.admit_bundle(b)
    assert res.admissible is False


# --------------------------------------------------- baseline control

def _valid_v4_baseline(**over):
    b = _valid_v4_candidate()
    del b["candidate"]
    del b["rule_operation"]
    b["arm"] = "baseline"
    b["observation"]["wrapper_skill_invoked"] = False
    b["baseline_control"] = {"rule_operation_absent": True, "rdx_bundle_absent": True,
                              "rdx_sidecars_absent": True, "no_rp_obligation_leakage": True}
    b["baseline"] = {"wrapper_skill_invoked": False, "direct_child_skill_invoked": True,
                      "rdx_bundle_absent": True, "rdx_sidecars_absent": True,
                      "rdx_overlay_absent": True}
    b.update(over)
    return b


def test_v4_schema_accepts_baseline_control():
    assert run_live._validate_bundle_v4(_valid_v4_baseline()) == []


def test_v4_schema_rejects_baseline_with_wrapper():
    b = _valid_v4_baseline()
    b["observation"]["wrapper_skill_invoked"] = True
    assert run_live._validate_bundle_v4(b)


def test_evaluate_baseline_leakage_flags_rp(tmp_path):
    art = tmp_path / "a.md"
    art.write_text("This mentions RP-ASYNC-005 obligation.", encoding="utf-8")
    leak = run_live.evaluate_baseline_leakage(
        artifact_paths=[art], workspace=tmp_path, workflow="atdd",
        bundle_present=False, sidecars=[])
    assert leak["no_rp_obligation_leakage"] is False
    assert "RP-ASYNC-005" in leak["rp_leakage_hits"]


# --------------------------------------------------- grader + schedule

def test_rule_operation_grader_verdict():
    import grade_rule_operation as g
    rows = [
        {"arm": "candidate", "rule_operation_pass": True},
        {"arm": "candidate", "rule_operation_pass": True},
        {"arm": "baseline", "control_clean": True},
    ]
    v = g.rule_operation_verdict(rows)
    assert v["verdict"] == "RULE_OPERATION_PASS"
    v2 = g.rule_operation_verdict(rows, schedule_drift=True)
    assert v2["verdict"] == "RULE_OPERATION_INVALID"
    v3 = g.rule_operation_verdict([
        {"arm": "candidate", "rule_operation_pass": True},
        {"arm": "candidate", "rule_operation_pass": False},
        {"arm": "baseline", "control_clean": True}])
    assert v3["verdict"] == "RULE_OPERATION_PARTIAL"


def test_schedule_v3_locked_and_12_runs():
    p = LIVE.parent / "evals" / "runs" / "D3_4_RULE_OPERATION_RUNS.v3.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data["schema_version"] == "rdx-tea-rule-operation-runs.v3"
    assert data["locked"] is True
    assert len(data["runs"]) == 12
    assert sum(1 for r in data["runs"] if r["arm"] == "candidate") == 9
    assert sum(1 for r in data["runs"] if r["arm"] == "baseline") == 3
    assert len({r["run_id"] for r in data["runs"]}) == 12
    assert data["criteria_version"] == "rdx-tea-rule-operation-criteria.v1"
    assert data["evidence_schema_version"] == "rdx-tea-live-evidence.v4"


def test_criteria_v1_shape():
    import yaml
    p = LIVE.parent / "evals" / "D3_4_RULE_OPERATION_CRITERIA.v1.yaml"
    d = yaml.safe_load(p.read_text(encoding="utf-8"))
    assert d["criteria_version"] == "rdx-tea-rule-operation-criteria.v1"
    atdd = d["scenarios"]["atdd-api-async-corrected"]
    assert atdd["expected_active_packs"] == ["api", "async"]
    anyof = [c for c in atdd["required_rule_conditions"] if "any_of" in c][0]
    assert set(["RP-API-001", "RP-API-004", "RP-API-005"]).issubset(set(anyof["any_of"]))
