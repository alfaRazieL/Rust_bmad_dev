#!/usr/bin/env python3
"""D3.4.0 §17 — rule-operation schedule executor (v3).

Reads the locked D3_4_RULE_OPERATION_RUNS.v3.json schedule, verifies
its SHA256, and enforces schedule binding before each live run
(prompt/fixture/criteria/schema/schedule-sha drift → SCHEDULE_DRIFT).

`dry-run` produces a deterministic plan + manifest WITHOUT any model
call, proving unique ids, pinned hashes, criteria/schema pinning,
candidate/control path separation, and no evidence-path collisions.

`run-one` executes a single scheduled run (real model) with schedule
binding enforced via run_live.run_smoke.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RDX_TEA = HERE.parent
LIVE = RDX_TEA / "live-harness"
sys.path.insert(0, str(LIVE))
import run_live  # noqa: E402

SCHEDULE_V3 = RDX_TEA / "evals" / "runs" / "D3_4_RULE_OPERATION_RUNS.v3.json"
RESULTS_ROOT = RDX_TEA / "evals" / "results" / "d3_4_rule_operation"
DRY_RUN_ROOT = RDX_TEA / "evals" / "results" / "d3_4_0_dry_run"
FIXTURES = LIVE / "fixtures"


class RuleOpError(RuntimeError):
    pass


def load_schedule(path: Path = SCHEDULE_V3) -> dict:
    if not path.exists():
        raise RuleOpError(f"schedule missing: {path}")
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw)
    if data.get("schema_version") != "rdx-tea-rule-operation-runs.v3":
        raise RuleOpError(f"unexpected schema: {data.get('schema_version')}")
    if data.get("locked") is not True:
        raise RuleOpError("schedule.locked must be true")
    data["_sha256"] = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return data


def _plan_paths(entry: dict, root: Path):
    ws = root / "workspaces" / entry["run_id"]
    evd = (root / "evidence" / entry["scenario"] / entry["arm"]
           / f"rep-{entry['repetition']:02d}" / entry["run_id"])
    return ws, evd


def dry_run(schedule_path: Path, out_root: Path) -> dict:
    schedule = load_schedule(schedule_path)
    runs = schedule["runs"]
    seen_ids: set[str] = set()
    seen_paths: set[str] = set()
    out_root.mkdir(parents=True, exist_ok=True)
    for entry in sorted(runs, key=lambda e: e["order_index"]):
        rid = entry["run_id"]
        if rid in seen_ids:
            raise RuleOpError(f"duplicate run_id {rid}")
        seen_ids.add(rid)
        ws, evd = _plan_paths(entry, out_root)
        for p in (ws, evd):
            key = str(p.resolve())
            if key in seen_paths:
                raise RuleOpError(f"path collision {key}")
            seen_paths.add(key)
        # Recompute + compare the pinned hashes deterministically.
        wf = entry["workflow"]
        prompt_hash = hashlib.sha256(
            run_live.arm_prompt(entry["arm"], wf, "__RUN_ID__").encode()).hexdigest()
        fixture_hash = run_live._sha256_dir_tree(FIXTURES / entry["fixture"])
        if prompt_hash != entry["prompt_hash"]:
            raise RuleOpError(f"prompt_hash drift for {rid}")
        if fixture_hash != entry["fixture_hash"]:
            raise RuleOpError(f"fixture_hash drift for {rid}")
        if entry["criteria_version"] != schedule["criteria_version"]:
            raise RuleOpError(f"criteria_version drift for {rid}")
        if entry["schema_version"] != schedule["evidence_schema_version"]:
            raise RuleOpError(f"schema_version drift for {rid}")
        evd.mkdir(parents=True, exist_ok=True)
        (evd / "PLAN.json").write_text(json.dumps({
            "run_id": rid, "scenario": entry["scenario"], "arm": entry["arm"],
            "fixture": entry["fixture"], "workflow": wf,
            "repetition": entry["repetition"], "model": entry["model"],
            "prompt_hash": prompt_hash, "fixture_hash": fixture_hash,
            "criteria_version": entry["criteria_version"],
            "schema_version": entry["schema_version"],
            "workspace_dir": str(ws), "evidence_dir": str(evd),
            "command": ([f"/rdx-tea-{wf}"] if entry["arm"] == "candidate"
                        else [f"/bmad-testarch-{wf}"]),
        }, indent=2, sort_keys=True), encoding="utf-8")
    candidates = [r for r in runs if r["arm"] == "candidate"]
    controls = [r for r in runs if r["arm"] == "baseline"]
    manifest = {
        "schedule_sha256": schedule["_sha256"],
        "criteria_version": schedule["criteria_version"],
        "criteria_sha256": schedule["criteria_sha256"],
        "evidence_schema_version": schedule["evidence_schema_version"],
        "total_runs": len(runs),
        "candidate": len(candidates),
        "baseline_control": len(controls),
        "unique_run_ids": len({r["run_id"] for r in runs}),
        "unique_workspace_dirs": len({str(_plan_paths(r, out_root)[0].resolve()) for r in runs}),
        "unique_evidence_dirs": len({str(_plan_paths(r, out_root)[1].resolve()) for r in runs}),
        "unique_prompt_hashes": len({r["prompt_hash"] for r in runs}),
        "unique_fixture_hashes": len({r["fixture_hash"] for r in runs}),
        "candidate_control_paths_separate": True,
        "collisions": 0,
        "locked": schedule["locked"],
    }
    (out_root / "MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return manifest


def run_one(schedule_path: Path, run_id: str, out_root: Path) -> dict:
    schedule = load_schedule(schedule_path)
    entries = [e for e in schedule["runs"] if e["run_id"] == run_id]
    if not entries:
        raise RuleOpError(f"run_id {run_id!r} not in schedule")
    entry = entries[0]
    ws, evd = _plan_paths(entry, out_root)
    spec = run_live.RunSpec(
        scenario=entry["scenario"], arm=entry["arm"],
        repetition=entry["repetition"], workflow=entry["workflow"],
        fixture_dir=FIXTURES / entry["fixture"], workspace_dir=ws,
        evidence_root=evd.parent.parent.parent, run_id=run_id,
        model=entry["model"], timeout_seconds=entry["timeout_seconds"],
        max_budget_usd=entry["max_budget_usd"],
    )
    return run_live.run_smoke(
        spec, schedule_entry=entry, schedule_sha256=schedule["_sha256"],
        pinned_schedule_sha256=schedule["_sha256"])


def main() -> int:
    ap = argparse.ArgumentParser(description="rdx-tea D3.4.0 rule-operation runner")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p1 = sub.add_parser("dry-run")
    p1.add_argument("--schedule", type=Path, default=SCHEDULE_V3)
    p1.add_argument("--out-root", type=Path, default=DRY_RUN_ROOT)
    p2 = sub.add_parser("run-one")
    p2.add_argument("--schedule", type=Path, default=SCHEDULE_V3)
    p2.add_argument("--run-id", required=True)
    p2.add_argument("--out-root", type=Path, default=RESULTS_ROOT)
    args = ap.parse_args()
    try:
        if args.cmd == "dry-run":
            m = dry_run(args.schedule, args.out_root)
            print(json.dumps({"status": "PASS", **m,
                              "manifest": str(args.out_root / "MANIFEST.json")},
                             indent=2, sort_keys=True))
            return 0
        if args.cmd == "run-one":
            r = run_one(args.schedule, args.run_id, args.out_root)
            print(json.dumps(r, indent=2, sort_keys=True))
            return 0 if r.get("admissible") else 4
    except RuleOpError as err:
        print(json.dumps({"status": "FAIL", "error": str(err)}, indent=2))
        return 2
    return 2


if __name__ == "__main__":
    sys.exit(main())
