"""L1 W6 — admission recomputed from primitive fields (G-W6-ADMISSION).

`admission.admit_run` must recompute FINALIZED-admissibility from a run-report's
OWN primitive fields, in a fixed deterministic order, and must NEVER trust a
recorded `admissible` / `admission` flag — a dishonest bundle cannot self-admit.

These are fast, pure-Python unit tests over report dicts (no subprocess): they
build a known-admissible report, then apply one violation at a time and assert
the exact fail-closed outcome, plus the fixed-order tie-break and the
self-admit-immunity property.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

RDX_TEA_DIR = Path(__file__).resolve().parent.parent.parent
ADMISSION_PY = (RDX_TEA_DIR / "poc" / "install-tree" / "_bmad" / "rdx-tea"
                / "scripts" / "admission.py")


def _load():
    spec = importlib.util.spec_from_file_location("admission", ADMISSION_PY)
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m  # dataclass introspection needs this registered
    spec.loader.exec_module(m)
    return m


admission = _load()


def _passing_verifier() -> dict:
    return {
        "verdict": "PASS",
        "failed_checks": [],
        "run_id": "r1",
        "checks": [{"check": c, "status": "PASS", "detail": ""} for c in (
            "schema", "manifest_hash", "bundle_hash", "artifact_hash",
            "base_head_exist", "diff_digest_recomputed", "canonical_snapshot",
            "source_lock", "artifact_boundary")],
    }


def _admissible_report() -> dict:
    return {
        "schema_version": "rdx-tea-run.v1",
        "workflow": "test-design",
        "run_id": "r1",
        "execution_mode": "sequential",
        "requested_mode": "sequential",
        "resolved_mode": "sequential",
        "observed_mode": "INFERRED_ABSENT",
        "sidecars": [{"execution_mode": "sequential", "completed": True,
                      "artifact_path": "_bmad-output/a.md"}],
        "verifier": [_passing_verifier()],
        "workspace_delta": {"created_files": ["_bmad-output/a.md"],
                            "modified_files": [], "declared_missing_files": []},
        "workspace_delta_consistency": {"status": "PASS", "reasons": []},
        "artifact_consistency": {"status": "PASS", "reasons": [], "warnings": []},
        "consistency_status": "PASS",
        "new_artefacts": ["_bmad-output/a.md"],
        "verify_only": False,
    }


# ------------------------------------------------------------- happy path

def test_w6_admission_baseline_report_is_admissible() -> None:
    r = admission.admit_run(_admissible_report())
    assert r.admissible is True
    assert r.run_outcome == "SUCCESS"


def test_w6_admission_run_outcomes_order_auth_first_success_last() -> None:
    assert admission.RUN_OUTCOMES[0] == "AUTH_FAILURE"
    assert admission.RUN_OUTCOMES[-1] == "SUCCESS"
    # Fixed, unique ordering.
    assert len(admission.RUN_OUTCOMES) == len(set(admission.RUN_OUTCOMES))


# -------------------------------- never trust a self-reported admissible flag

def test_w6_admission_ignores_dishonest_self_reported_flag() -> None:
    """A bundle that self-declares admissible=true but fails a verifier check
    is recomputed as NOT admissible — it cannot self-admit."""
    r = _admissible_report()
    r["admissible"] = True
    r["admission"] = {"admissible": True, "run_outcome": "SUCCESS", "reasons": []}
    r["verifier"][0]["verdict"] = "FAIL"
    r["verifier"][0]["failed_checks"] = ["bundle_hash"]
    result = admission.admit_run(r)
    assert result.admissible is False
    assert result.run_outcome == "VERIFIER_FAILURE"


# ------------------------------------------------------------- schema group

def test_w6_admission_missing_primitive_field_is_schema_failure() -> None:
    r = _admissible_report()
    del r["consistency_status"]
    result = admission.admit_run(r)
    assert result.admissible is False
    assert result.run_outcome == "SCHEMA_FAILURE"


def test_w6_admission_wrong_schema_version_is_schema_failure() -> None:
    r = _admissible_report()
    r["schema_version"] = "rdx-tea-run.v0"
    assert admission.admit_run(r).run_outcome == "SCHEMA_FAILURE"


def test_w6_admission_absent_report_is_runtime_failure() -> None:
    assert admission.admit_run({}).run_outcome == "RUNTIME_FAILURE"
    assert admission.admit_run(None).admissible is False


# -------------------------------------------------------------- mode group

@pytest.mark.parametrize("field", ["execution_mode", "resolved_mode"])
def test_w6_admission_non_sequential_mode_is_mode_failure(field: str) -> None:
    r = _admissible_report()
    r[field] = "agent-team"
    result = admission.admit_run(r)
    assert result.admissible is False
    assert result.run_outcome == "MODE_FAILURE"


def test_w6_admission_sidecar_non_sequential_mode_is_mode_failure() -> None:
    r = _admissible_report()
    r["sidecars"][0]["execution_mode"] = "subagent"
    assert admission.admit_run(r).run_outcome == "MODE_FAILURE"


# ----------------------------------------------------------- workflow group

def test_w6_admission_observed_subagent_is_workflow_failure() -> None:
    r = _admissible_report()
    r["observed_mode"] = "OBSERVED_SUBAGENT"
    result = admission.admit_run(r)
    assert result.admissible is False
    assert result.run_outcome == "WORKFLOW_FAILURE"


def test_w6_admission_no_artefact_is_workflow_failure() -> None:
    r = _admissible_report()
    r["new_artefacts"] = []
    assert admission.admit_run(r).run_outcome == "WORKFLOW_FAILURE"


def test_w6_admission_sidecar_artefact_count_mismatch_is_workflow_failure() -> None:
    r = _admissible_report()
    r["sidecars"].append({"execution_mode": "sequential", "completed": True})
    assert admission.admit_run(r).run_outcome == "WORKFLOW_FAILURE"


def test_w6_admission_missing_sidecar_is_workflow_failure() -> None:
    r = _admissible_report()
    r["sidecars"] = []
    assert admission.admit_run(r).run_outcome == "WORKFLOW_FAILURE"


# ----------------------------------------------------------- verifier group

def test_w6_admission_verifier_verdict_fail_is_verifier_failure() -> None:
    r = _admissible_report()
    r["verifier"][0]["verdict"] = "FAIL"
    assert admission.admit_run(r).run_outcome == "VERIFIER_FAILURE"


def test_w6_admission_verifier_check_fail_is_verifier_failure() -> None:
    r = _admissible_report()
    r["verifier"][0]["checks"][2]["status"] = "FAIL"
    assert admission.admit_run(r).run_outcome == "VERIFIER_FAILURE"


def test_w6_admission_empty_verifier_is_verifier_failure() -> None:
    r = _admissible_report()
    r["verifier"] = []
    assert admission.admit_run(r).run_outcome == "VERIFIER_FAILURE"


# --------------------------------------------------------- consistency group

@pytest.mark.parametrize("path", [
    ("consistency_status",),
    ("workspace_delta_consistency", "status"),
    ("artifact_consistency", "status"),
])
def test_w6_admission_consistency_fail_is_consistency_failure(path) -> None:
    r = _admissible_report()
    if len(path) == 1:
        r[path[0]] = "FAIL"
    else:
        r[path[0]][path[1]] = "FAIL"
    result = admission.admit_run(r)
    assert result.admissible is False
    assert result.run_outcome == "CONSISTENCY_FAILURE"


def test_w6_admission_missing_workspace_delta_is_consistency_failure() -> None:
    r = _admissible_report()
    r["workspace_delta"] = {}
    assert admission.admit_run(r).run_outcome == "CONSISTENCY_FAILURE"


# ------------------------------------------------------------ partial group

def test_w6_admission_verify_only_is_partial_run() -> None:
    r = _admissible_report()
    r["verify_only"] = True
    result = admission.admit_run(r)
    assert result.admissible is False
    assert result.run_outcome == "PARTIAL_RUN"


@pytest.mark.parametrize("phase", ["prepared", "finalized_consistency_failed",
                                   "finalized_not_admissible"])
def test_w6_admission_non_finalized_phase_is_partial_run(phase: str) -> None:
    # Report content is otherwise clean; only the wrapper phase is not final.
    result = admission.admit_run(_admissible_report(), state_phase=phase)
    assert result.admissible is False
    assert result.run_outcome == "PARTIAL_RUN"


def test_w6_admission_finalized_phase_is_admissible() -> None:
    result = admission.admit_run(_admissible_report(), state_phase="finalized")
    assert result.admissible is True


# --------------------------------------------------- fixed-order tie-break

def test_w6_admission_fixed_order_earliest_failure_wins() -> None:
    """With several violations, the earliest group in RUN_OUTCOMES wins."""
    r = _admissible_report()
    r["resolved_mode"] = "agent-team"           # MODE_FAILURE (earlier)
    r["verifier"][0]["verdict"] = "FAIL"        # VERIFIER_FAILURE (later)
    r["consistency_status"] = "FAIL"            # CONSISTENCY_FAILURE (later)
    assert admission.admit_run(r).run_outcome == "MODE_FAILURE"
    # Schema failure outranks a mode failure.
    r["schema_version"] = "bad"
    assert admission.admit_run(r).run_outcome == "SCHEMA_FAILURE"
