#!/usr/bin/env python3
"""D3.4.0 §16 — rule-operation grader.

Primary verdict is DETERMINISTIC (no LLM): it is computed from the v4
evidence bundles' admissibility, pack activation, rule conditions,
forbidden packs, artifact/workspace-delta consistency, verifier, and
control-leakage fields. The optional LLM diagnostic layer can inspect
sanitised artifact quality but CANNOT override the deterministic
rule-operation verdict.

Modes:
    prepare-rule-operation   walk v4 evidence, build a per-run summary
    grade-deterministic      compute per-run deterministic rule-op result
    grade-llm-diagnostic     optional; dry-run in D3.4.0 (NOT required)
    merge                    combine deterministic + diagnostic
    report                   emit the rule-operation verdict

Verdicts: RULE_OPERATION_PASS / PARTIAL / FAIL / INVALID.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RDX_TEA = HERE.parent.parent
sys.path.insert(0, str(RDX_TEA / "live-harness"))
import run_live  # noqa: E402  (for admit_bundle + _expected_active_packs)


def _walk_v4_bundles(root: Path) -> list[Path]:
    return sorted(root.rglob("live-evidence.v4.json"))


def _load(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


# ------------------------------------------------------ deterministic grade

def grade_bundle_deterministic(bundle: dict) -> dict:
    """Per-run deterministic rule-operation result. Re-admits the bundle
    and, for candidates, checks the rule-operation gates; for baselines,
    checks control isolation."""
    arm = bundle.get("arm", "")
    run_id = bundle.get("run_id", "")
    res = run_live.admit_bundle(bundle)
    row = {
        "run_id": run_id,
        "arm": arm,
        "scenario": bundle.get("scenario"),
        "admissible": res.admissible,
        "run_outcome": bundle.get("run_outcome"),
        "reasons": res.reasons,
    }
    if arm == "candidate":
        ro = bundle.get("rule_operation", {})
        row.update({
            "packs_ok": ro.get("packs_ok"),
            "expected_rule_condition": ro.get("expected_rule_condition"),
            "forbidden_rule_condition": ro.get("forbidden_rule_condition"),
            "verifier_all_pass": bundle.get("candidate", {}).get("verifier_all_pass"),
            "artifact_consistency": bundle.get("artifact_consistency", {}).get("status"),
            "workspace_delta_consistency": bundle.get("workspace_delta", {}).get("consistency"),
            "rule_operation_pass": (
                res.admissible
                and ro.get("packs_ok") is True
                and ro.get("expected_rule_condition") == "PASS"
                and ro.get("forbidden_rule_condition") == "PASS"
            ),
        })
    else:  # baseline control
        bc = bundle.get("baseline_control", {})
        row.update({
            "no_rp_leakage": bc.get("no_rp_obligation_leakage"),
            "rdx_bundle_absent": bc.get("rdx_bundle_absent"),
            "rdx_sidecars_absent": bc.get("rdx_sidecars_absent"),
            "control_clean": (
                res.admissible
                and bc.get("no_rp_obligation_leakage") is True
                and bc.get("rdx_bundle_absent") is True
                and bc.get("rdx_sidecars_absent") is True
            ),
        })
    return row


def grade_deterministic(root: Path, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for bp in _walk_v4_bundles(root):
        row = grade_bundle_deterministic(_load(bp))
        rows.append(row)
        (out_dir / f"{row['run_id']}.det.json").write_text(
            json.dumps(row, indent=2, sort_keys=True), encoding="utf-8")
    (out_dir / "SUMMARY.json").write_text(
        json.dumps({"count": len(rows)}, indent=2, sort_keys=True),
        encoding="utf-8")
    return {"count": len(rows)}


# ------------------------------------------------------ verdict

def rule_operation_verdict(det_rows: list[dict], *,
                           schedule_drift: bool = False) -> dict:
    """D3.4.0 §16.3 decision rule (deterministic)."""
    candidates = [r for r in det_rows if r["arm"] == "candidate"]
    controls = [r for r in det_rows if r["arm"] == "baseline"]

    if schedule_drift:
        return {"verdict": "RULE_OPERATION_INVALID",
                "reason": "schedule drift detected"}
    if not candidates:
        return {"verdict": "RULE_OPERATION_INVALID",
                "reason": "no candidate runs graded"}

    all_cand_pass = all(r.get("rule_operation_pass") for r in candidates)
    any_cand_pass = any(r.get("rule_operation_pass") for r in candidates)
    controls_clean = all(r.get("control_clean") for r in controls) if controls else True

    if all_cand_pass and controls_clean:
        verdict = "RULE_OPERATION_PASS"
    elif any_cand_pass and controls_clean:
        verdict = "RULE_OPERATION_PARTIAL"
    else:
        verdict = "RULE_OPERATION_FAIL"
    return {
        "verdict": verdict,
        "candidate_total": len(candidates),
        "candidate_pass": sum(1 for r in candidates if r.get("rule_operation_pass")),
        "control_total": len(controls),
        "control_clean": sum(1 for r in controls if r.get("control_clean")),
    }


def report(det_dir: Path, out_path: Path,
           schedule_drift: bool = False) -> dict:
    rows = [_load(p) for p in sorted(det_dir.glob("*.det.json"))]
    v = rule_operation_verdict(rows, schedule_drift=schedule_drift)
    payload = {
        "schema_version": "rdx-tea-rule-operation-report.v1",
        "generated_at": run_live._utc_now(),
        "sample_count": len(rows),
        **v,
        "note": ("Deterministic rule-operation verdict. LLM diagnostic "
                 "layer is optional and cannot override this verdict."),
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True),
                        encoding="utf-8")
    return payload


# ------------------------------------------------------ llm diagnostic

def grade_llm_diagnostic(root: Path, out_dir: Path, *,
                         dry_run: bool = True) -> dict:
    """Optional diagnostic; NOT required for the rule-operation verdict.
    D3.4.0 keeps it dry-run."""
    out_dir.mkdir(parents=True, exist_ok=True)
    n = 0
    for bp in _walk_v4_bundles(root):
        bundle = _load(bp)
        (out_dir / f"{bundle.get('run_id')}.llm.json").write_text(
            json.dumps({"run_id": bundle.get("run_id"),
                        "status": "NOT_RUN" if dry_run else "PENDING_LIVE",
                        "note": "diagnostic only; cannot override "
                                "deterministic rule-operation verdict"},
                       indent=2, sort_keys=True), encoding="utf-8")
        n += 1
    return {"count": n, "dry_run": dry_run,
            "required_for_verdict": False}


# ------------------------------------------------------ CLI

def main() -> int:
    ap = argparse.ArgumentParser(description="rdx-tea D3.4.0 rule-operation grader")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("prepare-rule-operation")
    p1.add_argument("--root", type=Path, required=True)
    p1.add_argument("--out-dir", type=Path, required=True)

    p2 = sub.add_parser("grade-deterministic")
    p2.add_argument("--root", type=Path, required=True)
    p2.add_argument("--out-dir", type=Path, required=True)

    p3 = sub.add_parser("grade-llm-diagnostic")
    p3.add_argument("--root", type=Path, required=True)
    p3.add_argument("--out-dir", type=Path, required=True)
    p3.add_argument("--dry-run", action="store_true", default=True)

    p4 = sub.add_parser("merge")
    p4.add_argument("--det-dir", type=Path, required=True)
    p4.add_argument("--llm-dir", type=Path, default=None)
    p4.add_argument("--out-dir", type=Path, required=True)

    p5 = sub.add_parser("report")
    p5.add_argument("--det-dir", type=Path, required=True)
    p5.add_argument("--out", type=Path, required=True)
    p5.add_argument("--schedule-drift", action="store_true")

    args = ap.parse_args()
    if args.cmd in ("prepare-rule-operation", "grade-deterministic"):
        r = grade_deterministic(args.root, args.out_dir)
    elif args.cmd == "grade-llm-diagnostic":
        r = grade_llm_diagnostic(args.root, args.out_dir, dry_run=args.dry_run)
    elif args.cmd == "merge":
        # merge is a thin pass-through: deterministic rows are canonical.
        rows = [_load(p) for p in sorted(args.det_dir.glob("*.det.json"))]
        args.out_dir.mkdir(parents=True, exist_ok=True)
        for row in rows:
            (args.out_dir / f"{row['run_id']}.merged.json").write_text(
                json.dumps(row, indent=2, sort_keys=True), encoding="utf-8")
        r = {"count": len(rows)}
    elif args.cmd == "report":
        r = report(args.det_dir, args.out, schedule_drift=args.schedule_drift)
    else:
        r = {"error": f"unknown cmd {args.cmd}"}
    print(json.dumps(r, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
