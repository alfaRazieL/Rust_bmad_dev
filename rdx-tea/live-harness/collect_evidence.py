#!/usr/bin/env python3
"""Collect the D3.3 §7 evidence bundle from a completed live run.

Copies transcript + run-report + sidecars + manifest + bundle into
`rdx-tea/evidence/live/<scenario>/<run_id>/` and produces a
`workspace-manifest.json`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def _sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def collect(*,
            workspace: Path,
            workflow: str,
            run_id: str,
            scenario: str,
            evidence_root: Path,
            invocation: dict,
            runtime: dict) -> dict:
    target = evidence_root / scenario / run_id
    target.mkdir(parents=True, exist_ok=True)
    run_dir = workspace / "_bmad" / "rdx-tea" / "runtime" / workflow / run_id
    inventory = {}
    for name in ("active-context.md", "run-manifest.json", "run-report.json",
                 "run-state.json", "diff.patch", "transcript.stream.jsonl",
                 "overlay-backup.toml"):
        src = run_dir / name
        if src.exists():
            dst = target / name
            shutil.copy2(src, dst)
            inventory[name] = _sha256(dst)
    # Copy sidecars.
    art_dir = workspace / "_bmad-output" / "test-artifacts"
    if art_dir.exists():
        sidecars_dir = target / "sidecars"
        artefacts_dir = target / "tea-artifacts"
        sidecars_dir.mkdir(exist_ok=True)
        artefacts_dir.mkdir(exist_ok=True)
        for f in art_dir.rglob("*"):
            if f.is_file():
                if f.name.endswith(".rdx-tea.json"):
                    dst = sidecars_dir / f.name
                else:
                    dst = artefacts_dir / f.name
                shutil.copy2(f, dst)
                inventory[dst.relative_to(target).as_posix()] = _sha256(dst)
    # Metadata files.
    (target / "runtime.json").write_text(json.dumps(runtime, indent=2, sort_keys=True))
    (target / "invocation.json").write_text(json.dumps(invocation, indent=2, sort_keys=True))
    (target / "workspace-manifest.json").write_text(
        json.dumps({
            "workspace": str(workspace),
            "workflow": workflow,
            "run_id": run_id,
            "scenario": scenario,
            "inventory": inventory,
            "collected_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        }, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (target / "exit-code.txt").write_text(str(invocation.get("exit_code", "")))
    return {"evidence_dir": str(target), "inventory": inventory}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", required=True, type=Path)
    ap.add_argument("--workflow", required=True)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--scenario", required=True)
    ap.add_argument("--evidence-root", required=True, type=Path)
    ap.add_argument("--invocation-json", required=True, type=Path)
    ap.add_argument("--runtime-json", required=True, type=Path)
    args = ap.parse_args()
    invocation = json.loads(args.invocation_json.read_text())
    runtime = json.loads(args.runtime_json.read_text())
    r = collect(
        workspace=args.workspace, workflow=args.workflow, run_id=args.run_id,
        scenario=args.scenario, evidence_root=args.evidence_root,
        invocation=invocation, runtime=runtime,
    )
    print(json.dumps(r, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
