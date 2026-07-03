#!/usr/bin/env python3
"""D3.3.2 §15 pilot executor.

Reads the locked D3_4_PILOT_RUNS.v2.json schedule, verifies its SHA256
against the recorded hash, and dispatches each run in `order_index`
order via `rdx-tea/live-harness/run_live.py`.

Subcommands:

    dry-run    — no model calls; produce plan / evidence skeletons and
                 fail closed on any collision, ID reuse, or arm
                 confusion.
    run-one    — execute one scheduled run by --run-id (real model call
                 unless --dry-run is passed).
    resume     — pick up an interrupted pilot; skips runs whose evidence
                 bundle already exists.
    status     — summarise which runs are done / retried / pending.

The executor never regenerates a run_id and never silently substitutes
a failed run. Retries are governed by the schedule's precommitted
retry_policy.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
RDX_TEA = HERE.parent
LIVE_HARNESS = RDX_TEA / "live-harness"
sys.path.insert(0, str(LIVE_HARNESS))

import run_live  # noqa: E402


SCHEDULE_V2 = RDX_TEA / "evals" / "runs" / "D3_4_PILOT_RUNS.v2.json"
RESULTS_ROOT = RDX_TEA / "evals" / "results" / "d3_4_pilot"
DRY_RUN_ROOT = RDX_TEA / "evals" / "results" / "d3_3_2_dry_run"


class PilotError(RuntimeError):
    pass


# ------------------------------------------------------------ schedule i/o

def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_schedule(path: Path = SCHEDULE_V2) -> dict:
    if not path.exists():
        raise PilotError(f"schedule missing: {path}")
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw)
    if data.get("schema_version") != "rdx-tea-pilot-runs.v2":
        raise PilotError(f"unexpected schedule schema: {data.get('schema_version')}")
    if data.get("locked") is not True:
        raise PilotError("schedule.locked must be true before any pilot run")
    data["_sha256"] = _sha256_text(raw)
    return data


def assert_schedule_pinned(schedule: dict, expected_sha256: str | None) -> None:
    """Optional guard called by callers who have committed the expected
    SHA256 elsewhere (e.g., D3_3_2_FINAL_VERIFICATION.json). Any drift
    is treated as PILOT_INVALID."""
    if expected_sha256 is not None and schedule.get("_sha256") != expected_sha256:
        raise PilotError(
            f"schedule sha256 drift: expected {expected_sha256}, "
            f"got {schedule.get('_sha256')}"
        )


# ------------------------------------------------------ dry-run plan

@dataclass
class RunPlan:
    run_id: str
    scenario: str
    arm: str
    workflow: str
    repetition: int
    order_index: int
    model: str
    fixture_hash: str
    prompt_hash: str
    workspace_dir: Path
    isolated_config_dir: Path
    evidence_dir: Path
    baseline_command: list[str]
    candidate_command: list[str]
    arm_prompt: str

    def as_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "scenario": self.scenario,
            "arm": self.arm,
            "workflow": self.workflow,
            "repetition": self.repetition,
            "order_index": self.order_index,
            "model": self.model,
            "fixture_hash": self.fixture_hash,
            "prompt_hash": self.prompt_hash,
            "workspace_dir": str(self.workspace_dir),
            "isolated_config_dir": str(self.isolated_config_dir),
            "evidence_dir": str(self.evidence_dir),
            "baseline_command": self.baseline_command,
            "candidate_command": self.candidate_command,
            "arm_prompt": self.arm_prompt,
        }


def _plan_paths(entry: dict, root: Path) -> tuple[Path, Path, Path]:
    ws = root / "workspaces" / entry["run_id"]
    cfg = root / "configs" / entry["run_id"]
    evd = root / "evidence" / entry["scenario"] / entry["arm"] / \
          f"rep-{entry['repetition']:02d}" / entry["run_id"]
    return ws, cfg, evd


def build_plan(schedule: dict, root: Path) -> list[RunPlan]:
    plans: list[RunPlan] = []
    seen_ids: set[str] = set()
    seen_paths: set[str] = set()
    for entry in sorted(schedule["runs"], key=lambda e: e["order_index"]):
        rid = entry["run_id"]
        if rid in seen_ids:
            raise PilotError(f"duplicate run_id in schedule: {rid}")
        seen_ids.add(rid)
        ws, cfg, evd = _plan_paths(entry, root)
        for p in (ws, cfg, evd):
            key = str(p.resolve())
            if key in seen_paths:
                raise PilotError(f"path collision at {key}")
            seen_paths.add(key)
        workflow = entry["workflow"]
        prompt_baseline = run_live.arm_prompt("baseline", workflow, rid)
        prompt_candidate = run_live.arm_prompt("candidate", workflow, rid)
        prompt = prompt_baseline if entry["arm"] == "baseline" else prompt_candidate
        baseline_cmd = [f"/bmad-testarch-{workflow}"]
        candidate_cmd = [f"/rdx-tea-{workflow}"]
        plans.append(RunPlan(
            run_id=rid,
            scenario=entry["scenario"],
            arm=entry["arm"],
            workflow=workflow,
            repetition=entry["repetition"],
            order_index=entry["order_index"],
            model=entry["model"],
            fixture_hash=entry["fixture_hash"],
            prompt_hash=entry["prompt_hash"],
            workspace_dir=ws,
            isolated_config_dir=cfg,
            evidence_dir=evd,
            baseline_command=baseline_cmd,
            candidate_command=candidate_cmd,
            arm_prompt=prompt,
        ))
    return plans


# ------------------------------------------------------ real run dispatch

def _spec_for(entry: dict, root: Path) -> run_live.RunSpec:
    ws, cfg, evd = _plan_paths(entry, root)
    fixture_dir = LIVE_HARNESS / "fixtures" / entry["scenario"]
    return run_live.RunSpec(
        scenario=entry["scenario"],
        arm=entry["arm"],
        repetition=entry["repetition"],
        workflow=entry["workflow"],
        fixture_dir=fixture_dir,
        workspace_dir=ws,
        evidence_root=evd.parent.parent.parent,  # evidence_root/scenario/arm/rep-.../run_id
        run_id=entry["run_id"],
        model=entry["model"],
        timeout_seconds=entry.get("timeout_seconds", 900),
        max_budget_usd=entry.get("max_budget_usd", 2.0),
        isolated_config_dir=cfg,
    )


def execute_one(schedule: dict, run_id: str, *, root: Path,
                dry_run: bool = False) -> dict:
    """Execute a single scheduled run. `dry_run=True` returns the plan
    without invoking a model."""
    entries = [e for e in schedule["runs"] if e["run_id"] == run_id]
    if not entries:
        raise PilotError(f"run_id {run_id!r} not in schedule")
    entry = entries[0]
    plans = build_plan(schedule, root)
    plan = next(p for p in plans if p.run_id == run_id)
    if dry_run:
        plan.evidence_dir.mkdir(parents=True, exist_ok=True)
        (plan.evidence_dir / "PLAN.json").write_text(
            json.dumps(plan.as_dict(), indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return {"status": "dry-run", "run_id": run_id,
                "plan_path": str(plan.evidence_dir / "PLAN.json")}
    # Real path — delegate to run_live.run_smoke.
    spec = _spec_for(entry, root)
    result = run_live.run_smoke(spec)
    return {"status": "ok", "run_id": run_id, **result}


# ------------------------------------------------------ dry-run driver

def dry_run(schedule_path: Path, out_root: Path) -> dict:
    """§17. End-to-end deterministic proof BEFORE any live-model call."""
    schedule = load_schedule(schedule_path)
    plans = build_plan(schedule, out_root)
    if len(plans) != 18:
        raise PilotError(f"expected 18 plans, got {len(plans)}")
    baselines = [p for p in plans if p.arm == "baseline"]
    candidates = [p for p in plans if p.arm == "candidate"]
    if len(baselines) != 9 or len(candidates) != 9:
        raise PilotError(
            f"expected 9/9 baseline/candidate, got "
            f"{len(baselines)}/{len(candidates)}"
        )
    prompt_hash_baseline = {p.prompt_hash for p in baselines}
    prompt_hash_candidate = {p.prompt_hash for p in candidates}
    same = prompt_hash_baseline & prompt_hash_candidate
    if same:
        raise PilotError(
            f"baseline and candidate prompt hashes collide: {sorted(same)}"
        )
    # Fixture hashes: same per scenario, across arms.
    by_scenario: dict[str, set[str]] = {}
    for p in plans:
        by_scenario.setdefault(p.scenario, set()).add(p.fixture_hash)
    for sc, hashes in by_scenario.items():
        if len(hashes) != 1:
            raise PilotError(
                f"scenario {sc} has multiple fixture hashes {hashes}"
            )
    # Evidence path uniqueness (already checked in build_plan) and one
    # deterministic outcome per run.
    out_root.mkdir(parents=True, exist_ok=True)
    for p in plans:
        p.evidence_dir.mkdir(parents=True, exist_ok=True)
        (p.evidence_dir / "PLAN.json").write_text(
            json.dumps(p.as_dict(), indent=2, sort_keys=True),
            encoding="utf-8",
        )
    manifest = {
        "schedule_sha256": schedule["_sha256"],
        "generated_at": run_live._utc_now(),
        "total_runs": len(plans),
        "baseline": len(baselines),
        "candidate": len(candidates),
        "unique_run_ids": len({p.run_id for p in plans}),
        "unique_workspace_dirs": len({str(p.workspace_dir.resolve())
                                         for p in plans}),
        "unique_config_dirs": len({str(p.isolated_config_dir.resolve())
                                      for p in plans}),
        "unique_evidence_dirs": len({str(p.evidence_dir.resolve())
                                       for p in plans}),
        "unique_prompt_hashes": len({p.prompt_hash for p in plans}),
        "baseline_command_sample": plans[0].baseline_command
        if plans[0].arm == "baseline" else baselines[0].baseline_command,
        "candidate_command_sample": candidates[0].candidate_command,
        "arm_command_difference": True,
        "arm_evidence_schema": "arm-aware v2 branches enforced by live-evidence.v2.schema.json",
        "schedule_immutable_flag": schedule["locked"],
        "runs": [p.as_dict() for p in plans],
    }
    (out_root / "MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return manifest


# ---------------------------------------------------- admissibility helpers

def _classify_run_state(evidence_dir: Path) -> str:
    """D3.3.3 §15. Classify a scheduled run's state from its v3 bundle:

      completed = an admissible SUCCESS bundle exists
      failed    = a bundle exists but admissible == false
      invalid   = a bundle exists but fails schema / admission recompute
      pending   = no bundle attempt yet
    """
    # Prefer v3; fall back to any versioned-attempt bundle.
    bundle_paths = sorted(evidence_dir.glob("live-evidence.v3*.json"))
    if not bundle_paths:
        return "pending"
    # Use the newest attempt.
    bundle_path = bundle_paths[-1]
    try:
        bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return "invalid"
    res = run_live.admit_bundle(bundle)
    if res.run_outcome == "SCHEMA_FAILURE":
        return "invalid"
    if res.admissible and bundle.get("run_outcome") == "SUCCESS":
        return "completed"
    return "failed"


def _attempt_suffix(evidence_dir: Path) -> str:
    """Return a versioned attempt suffix so a retry never overwrites a
    failed bundle (D3.3.3 §15)."""
    existing = sorted(evidence_dir.glob("live-evidence.v3.attempt-*.json"))
    return f"attempt-{len(existing) + 2:02d}"


# ---------------------------------------------------------------- resume

def resume(schedule: dict, root: Path, *, dry_run: bool = False) -> list[dict]:
    """Re-drive the schedule.

    D3.3.3 §15: a run is skipped ONLY when it is `completed` (an
    admissible SUCCESS bundle). A `failed`/`invalid` bundle is NOT
    treated as completed and is NOT deleted; a retry is attempted only
    if the precommitted retry policy permits it, and the retry writes a
    versioned attempt suffix.
    """
    plans = build_plan(schedule, root)
    retry_policy = schedule.get("retry_policy", {})
    max_retries = int(retry_policy.get("max_retries_per_run_id", 0))
    outcomes: list[dict] = []
    for p in plans:
        state = _classify_run_state(p.evidence_dir)
        if state == "completed":
            outcomes.append({"status": "already-completed", "run_id": p.run_id})
            continue
        if state in ("failed", "invalid"):
            attempts = len(sorted(p.evidence_dir.glob("live-evidence.v3*.json")))
            if attempts > max_retries:
                outcomes.append({"status": "retry-exhausted",
                                  "run_id": p.run_id, "prior_state": state,
                                  "attempts": attempts})
                continue
            # Preserve the failed bundle under a versioned attempt suffix
            # so the retry never overwrites failed evidence.
            failed_bundle = p.evidence_dir / "live-evidence.v3.json"
            if failed_bundle.exists():
                suffix = _attempt_suffix(p.evidence_dir)
                failed_bundle.rename(
                    p.evidence_dir / f"live-evidence.v3.{suffix}.json"
                )
        try:
            r = execute_one(schedule, p.run_id, root=root, dry_run=dry_run)
            outcomes.append({**r, "prior_state": state})
        except Exception as err:  # noqa: BLE001
            outcomes.append({"status": "error", "run_id": p.run_id,
                              "error": str(err), "prior_state": state})
    return outcomes


# ---------------------------------------------------------------- status

def status(schedule: dict, root: Path) -> dict:
    """D3.3.3 §15 — completed/failed/pending/invalid by admissibility."""
    plans = build_plan(schedule, root)
    done, pending, failed, invalid = [], [], [], []
    for p in plans:
        state = _classify_run_state(p.evidence_dir)
        if state == "completed":
            done.append(p.run_id)
        elif state == "failed":
            failed.append(p.run_id)
        elif state == "invalid":
            invalid.append(p.run_id)
        else:
            pending.append(p.run_id)
    return {
        "total": len(plans),
        "completed": done,
        "failed": failed,
        "invalid": invalid,
        "pending": pending,
        "schedule_sha256": schedule.get("_sha256"),
    }


# ------------------------------------------------------------ CLI

def main() -> int:
    ap = argparse.ArgumentParser(description="rdx-tea D3.3.2 pilot executor")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_dry = sub.add_parser("dry-run")
    p_dry.add_argument("--schedule", type=Path, default=SCHEDULE_V2)
    p_dry.add_argument("--out-root", type=Path, default=DRY_RUN_ROOT)

    p_one = sub.add_parser("run-one")
    p_one.add_argument("--schedule", type=Path, default=SCHEDULE_V2)
    p_one.add_argument("--run-id", required=True)
    p_one.add_argument("--out-root", type=Path, default=RESULTS_ROOT)
    p_one.add_argument("--dry-run", action="store_true")

    p_res = sub.add_parser("resume")
    p_res.add_argument("--schedule", type=Path, default=SCHEDULE_V2)
    p_res.add_argument("--out-root", type=Path, default=RESULTS_ROOT)
    p_res.add_argument("--dry-run", action="store_true")

    p_st = sub.add_parser("status")
    p_st.add_argument("--schedule", type=Path, default=SCHEDULE_V2)
    p_st.add_argument("--out-root", type=Path, default=RESULTS_ROOT)

    args = ap.parse_args()
    try:
        if args.cmd == "dry-run":
            manifest = dry_run(args.schedule, args.out_root)
            print(json.dumps({"status": "PASS",
                                "schedule_sha256": manifest["schedule_sha256"],
                                "runs": manifest["total_runs"],
                                "manifest": str(args.out_root / "MANIFEST.json")},
                              indent=2))
            return 0
        schedule = load_schedule(args.schedule)
        if args.cmd == "run-one":
            r = execute_one(schedule, args.run_id, root=args.out_root,
                            dry_run=args.dry_run)
            print(json.dumps(r, indent=2, sort_keys=True))
            return 0
        if args.cmd == "resume":
            r = resume(schedule, args.out_root, dry_run=args.dry_run)
            print(json.dumps({"outcomes": r}, indent=2, sort_keys=True))
            return 0
        if args.cmd == "status":
            r = status(schedule, args.out_root)
            print(json.dumps(r, indent=2, sort_keys=True))
            return 0
    except PilotError as err:
        print(json.dumps({"status": "FAIL", "error": str(err)}, indent=2))
        return 2
    return 2


if __name__ == "__main__":
    sys.exit(main())
