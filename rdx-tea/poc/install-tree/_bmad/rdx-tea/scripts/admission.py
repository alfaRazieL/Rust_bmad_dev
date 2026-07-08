"""RDX-TEA fail-closed admission model (W6 / ADR-006 §5-9, ADR-008).

Production-plane admission gate. Recomputes the FINALIZED-admissibility of a
production run-report (`run-report.json`, produced by the wrapper's
`finalize-run`) **from its own primitive fields**. It NEVER trusts a recorded
`admissible` / `admission` field: a dishonest bundle that self-declares
`admissible: true` while violating an invariant is reported as NOT admissible,
with the violated reasons. A dishonest bundle cannot self-admit.

This is the shipped-surface counterpart of the eval-plane `admit_bundle`
(the reference lives in the eval harness, REFERENCE ONLY). It is a clean
re-implementation: this module imports no eval-plane module and references no
eval-plane or evidence-plane path (G-SPLIT-IMPORT). Determinism only — no
wall-clock, no random, sorted iteration; the same report always yields the
same verdict.

## Run outcomes — fixed deterministic order (ADR-006 §5)

`admit_run` evaluates a fixed ordered list of check groups and returns the
FIRST group that produces any reason (fail-closed, first-failure-wins). A run
is FINALIZED-admissible ONLY when every group is clean → `SUCCESS`.

    AUTH_FAILURE        auth marker recorded in the report (parity; the shipped
                        finalize never sets it, honoured for future runtimes)
    RUNTIME_FAILURE     report absent / not an object
    SCHEMA_FAILURE      missing or wrong-typed primitive field; wrong
                        schema_version
    MODE_FAILURE        execution_mode / requested_mode / resolved_mode (or a
                        sidecar's execution_mode) is not the literal
                        'sequential'
    WORKFLOW_FAILURE    Task/subagent observed (observed_mode ==
                        OBSERVED_SUBAGENT); no new artefact; no sidecar; sidecar
                        count != artefact count; a sidecar not completed
    VERIFIER_FAILURE    any verifier result is not PASS, or carries a failing
                        check / non-empty failed_checks, or is absent
    CONSISTENCY_FAILURE workspace_delta absent; workspace_delta_consistency,
                        artifact_consistency, or consistency_status not PASS
    PARTIAL_RUN         a --verify-only advisory run, or a wrapper run-state
                        phase that is not 'finalized' (e.g. 'prepared',
                        'finalized_consistency_failed', 'finalized_not_admissible')
    SUCCESS             every group clean → FINALIZED-admissible

Mapping to ADR-006 §5's live-plane order (AUTH_FAILURE → TIMEOUT →
RUNTIME_FAILURE → CONTAMINATION → RUN_ID_MISMATCH → WORKFLOW_FAILURE →
VERIFIER_FAILURE → SCHEMA_FAILURE → SUCCESS): the live-only classes (TIMEOUT,
CONTAMINATION, RUN_ID_MISMATCH) belong to the invocation layer, not the
finalize report, and are absent here; SCHEMA is promoted ahead of the content
groups (as in the live `admit_bundle`, which schema-gates first) so the content
checks can assume every primitive field is present.

## Invariants (never FINALIZED-admissible)

  * consistency_status == "FAIL"
  * workspace_delta_consistency.status == "FAIL"
  * artifact_consistency.status == "FAIL"
  * any verifier check FAIL
  * a partial / failed wrapper state (incl. finalized_consistency_failed)
  * a non-sequential execution/resolved mode
  * a Task/subagent-observed run
  * a missing sidecar / sidecar-artefact count mismatch
  * a missing or invalid primitive field
  * a self-reported `admissible` flag — ignored; admission is recomputed
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

# Fixed deterministic outcome order (see module docstring). Index in this
# tuple is the evaluation order; SUCCESS is only reached when every prior
# group is clean.
RUN_OUTCOMES = (
    "AUTH_FAILURE",
    "RUNTIME_FAILURE",
    "SCHEMA_FAILURE",
    "MODE_FAILURE",
    "WORKFLOW_FAILURE",
    "VERIFIER_FAILURE",
    "CONSISTENCY_FAILURE",
    "PARTIAL_RUN",
    "SUCCESS",
)

# Primitive fields the report MUST carry for admission to be computable.
REQUIRED_REPORT_FIELDS = (
    "schema_version", "workflow", "run_id",
    "execution_mode", "resolved_mode", "observed_mode",
    "sidecars", "verifier",
    "workspace_delta", "workspace_delta_consistency",
    "artifact_consistency", "consistency_status",
    "new_artefacts",
)

_SCHEMA_VERSION = "rdx-tea-run.v1"
_SEQUENTIAL = "sequential"


@dataclass
class AdmissionResult:
    admissible: bool
    run_outcome: str
    reasons: list[str]
    workflow: str
    run_id: str

    def to_dict(self) -> dict:
        return {
            "admissible": self.admissible,
            "run_outcome": self.run_outcome,
            "reasons": list(self.reasons),
            "workflow": self.workflow,
            "run_id": self.run_id,
        }


# --------------------------------------------------------------- check groups
# Each group reads ONLY the report's primitive fields (never `admissible` /
# `admission`) and returns a list of reasons. An empty list means the group is
# clean. All accessors are defensive (`.get`) so a schema-broken report yields
# graceful reasons, never a crash.

def _check_auth(report: dict) -> list[str]:
    reasons: list[str] = []
    if report.get("authentication_failed") is True:
        reasons.append("authentication_failed=true")
    status = str(report.get("auth_status", "")).strip().upper()
    if status in ("FAIL", "FAILURE", "AUTH_FAILURE"):
        reasons.append(f"auth_status={status}")
    return reasons


def _check_runtime(report: dict) -> list[str]:
    # `admit_run` already rejects a wholly-absent report; this guards a
    # report that is present but explicitly records a runtime abort.
    if str(report.get("run_outcome_hint", "")).upper() == "RUNTIME_FAILURE":
        return ["run recorded a runtime abort"]
    return []


def _check_schema(report: dict) -> list[str]:
    reasons: list[str] = []
    if report.get("schema_version") != _SCHEMA_VERSION:
        reasons.append(
            f"schema_version={report.get('schema_version')!r} != {_SCHEMA_VERSION!r}")
    for field in REQUIRED_REPORT_FIELDS:
        if field not in report:
            reasons.append(f"missing primitive field: {field}")
    for field in ("sidecars", "verifier", "new_artefacts"):
        if field in report and not isinstance(report[field], list):
            reasons.append(f"{field} must be a list")
    for field in ("workspace_delta", "workspace_delta_consistency",
                  "artifact_consistency"):
        if field in report and not isinstance(report[field], dict):
            reasons.append(f"{field} must be an object")
    return sorted(dict.fromkeys(reasons))


def _check_mode(report: dict) -> list[str]:
    reasons: list[str] = []
    for key in ("execution_mode", "resolved_mode"):
        if str(report.get(key, "")).strip().lower() != _SEQUENTIAL:
            reasons.append(f"{key}={report.get(key)!r} != 'sequential'")
    requested = report.get("requested_mode")
    if requested is not None and str(requested).strip().lower() != _SEQUENTIAL:
        reasons.append(f"requested_mode={requested!r} != 'sequential'")
    for sc in report.get("sidecars", []):
        if isinstance(sc, dict) and \
                str(sc.get("execution_mode", "")).strip().lower() != _SEQUENTIAL:
            reasons.append(f"sidecar execution_mode={sc.get('execution_mode')!r}")
    return reasons


def _check_workflow(report: dict) -> list[str]:
    reasons: list[str] = []
    if str(report.get("observed_mode", "")) == "OBSERVED_SUBAGENT":
        reasons.append("observed_mode=OBSERVED_SUBAGENT (Task/subagent dispatch)")
    new_artefacts = report.get("new_artefacts", [])
    sidecars = report.get("sidecars", [])
    if not new_artefacts:
        reasons.append("no new artefacts")
    if not sidecars:
        reasons.append("no sidecars")
    if new_artefacts and sidecars and len(sidecars) != len(new_artefacts):
        reasons.append(
            f"sidecar count {len(sidecars)} != artefact count {len(new_artefacts)}")
    for sc in sidecars:
        if isinstance(sc, dict) and sc.get("completed") is not True:
            reasons.append(f"sidecar completed={sc.get('completed')!r}")
    return reasons


def _check_verifier(report: dict) -> list[str]:
    reasons: list[str] = []
    results = report.get("verifier", [])
    if not results:
        reasons.append("verifier results absent")
    for v in results:
        if not isinstance(v, dict):
            reasons.append("verifier entry is not an object")
            continue
        if v.get("verdict") != "PASS":
            reasons.append(f"verifier verdict={v.get('verdict')!r}")
        for check in v.get("failed_checks") or []:
            reasons.append(f"verifier check FAIL: {check}")
        for check in v.get("checks", []):
            if isinstance(check, dict) and check.get("status") == "FAIL":
                reasons.append(f"verifier check FAIL: {check.get('check')}")
    return sorted(dict.fromkeys(reasons))


def _check_consistency(report: dict) -> list[str]:
    reasons: list[str] = []
    if not report.get("workspace_delta"):
        reasons.append("workspace_delta absent")
    wdc = report.get("workspace_delta_consistency", {})
    if not isinstance(wdc, dict) or wdc.get("status") != "PASS":
        reasons.append(
            f"workspace_delta_consistency={_status_of(wdc)!r} != 'PASS'")
    ac = report.get("artifact_consistency", {})
    if not isinstance(ac, dict) or ac.get("status") != "PASS":
        reasons.append(f"artifact_consistency={_status_of(ac)!r} != 'PASS'")
    if report.get("consistency_status") != "PASS":
        reasons.append(
            f"consistency_status={report.get('consistency_status')!r} != 'PASS'")
    return reasons


def _check_partial(report: dict, state_phase: str | None) -> list[str]:
    reasons: list[str] = []
    if report.get("verify_only") is True:
        reasons.append("verify_only advisory run is not a finalized admission")
    if state_phase is not None and state_phase != "finalized":
        reasons.append(f"run-state phase={state_phase!r} != 'finalized'")
    return reasons


def _status_of(obj) -> str:
    return obj.get("status") if isinstance(obj, dict) else str(obj)


# ------------------------------------------------------------- admission gate

def admit_run(report: dict, *, state_phase: str | None = None) -> AdmissionResult:
    """Recompute FINALIZED-admissibility of a run-report from its primitives.

    The recomputation IGNORES any recorded `admissible` / `admission` field on
    the report (never trust a self-reported flag). Returns the first failing
    outcome in `RUN_OUTCOMES` order, or SUCCESS only when every group is clean.
    """
    workflow = report.get("workflow", "") if isinstance(report, dict) else ""
    run_id = report.get("run_id", "") if isinstance(report, dict) else ""
    if not isinstance(report, dict) or not report:
        return AdmissionResult(
            False, "RUNTIME_FAILURE", ["run-report absent or not an object"],
            workflow, run_id)

    groups = (
        ("AUTH_FAILURE", lambda: _check_auth(report)),
        ("RUNTIME_FAILURE", lambda: _check_runtime(report)),
        ("SCHEMA_FAILURE", lambda: _check_schema(report)),
        ("MODE_FAILURE", lambda: _check_mode(report)),
        ("WORKFLOW_FAILURE", lambda: _check_workflow(report)),
        ("VERIFIER_FAILURE", lambda: _check_verifier(report)),
        ("CONSISTENCY_FAILURE", lambda: _check_consistency(report)),
        ("PARTIAL_RUN", lambda: _check_partial(report, state_phase)),
    )
    for outcome, group in groups:
        reasons = group()
        if reasons:
            return AdmissionResult(
                False, outcome, list(dict.fromkeys(reasons)), workflow, run_id)
    return AdmissionResult(
        True, "SUCCESS", ["all admission checks passed"], workflow, run_id)


# ------------------------------------------------------------------ CLI

def _load_phase(state_path: Path | None) -> str | None:
    if state_path is None or not state_path.exists():
        return None
    try:
        return json.loads(state_path.read_text(encoding="utf-8")).get("phase")
    except (json.JSONDecodeError, OSError):
        return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Recompute FINALIZED-admissibility of an RDX-TEA run-report."
    )
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("admit", help="admit a run-report.json")
    a.add_argument("--report", required=True, type=Path)
    a.add_argument("--state", type=Path, default=None,
                   help="optional run-state.json for phase cross-check")
    args = ap.parse_args(argv)

    if not args.report.exists():
        print(json.dumps(AdmissionResult(
            False, "RUNTIME_FAILURE", [f"run-report missing: {args.report}"],
            "", "").to_dict(), indent=2, sort_keys=True))
        return 2
    try:
        report = json.loads(args.report.read_text(encoding="utf-8"))
    except json.JSONDecodeError as err:
        print(json.dumps(AdmissionResult(
            False, "SCHEMA_FAILURE", [f"invalid JSON: {err}"], "", "").to_dict(),
            indent=2, sort_keys=True))
        return 2

    result = admit_run(report, state_phase=_load_phase(args.state))
    print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
    return 0 if result.admissible else 2


if __name__ == "__main__":
    sys.exit(main())
