#!/usr/bin/env python3
"""D3.3.2 §16 blinded grader for the D3.4 pilot.

Modes
-----
    prepare-blind        walk pilot evidence, sanitise each artifact,
                          rename to sample-XXX, emit mapping file
    grade-deterministic  layer-1 detectors from rubric v3 applied to
                          sanitised samples
    grade-llm            layer-2 blinded LLM grader (not executed in
                          D3.3.2; runner is testable but returns
                          NOT_RUN if `--dry-run` is set or if no API
                          credentials exist)
    merge                re-attach arm labels post-grading using the
                          mapping file; emit per-sample JSON
    report               emit the pilot verdict per rubric v3

Blinding contract: the comparative grader NEVER sees arm, wrapper
name, RDX metadata, sidecars, RP-* IDs, path prefixes, or the mapping
file. The candidate integration grader is a SEPARATE runner that
consumes the un-sanitised candidate bundle and produces fidelity
metrics.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
RDX_TEA = HERE.parent.parent
sys.path.insert(0, str(RDX_TEA / "live-harness"))
import run_live  # noqa: E402  (for run_live._utc_now etc.)


PROMPT_PATH = HERE / "prompts" / "comparative_grader.v1.md"
LLM_RESULT_SCHEMA = HERE / "schemas" / "llm-grader-result.v1.schema.json"

RUBRIC_V3 = RDX_TEA / "evals" / "D3_4_PILOT_RUBRIC.v3.yaml"

# Sanitisation regexes.
_RP_ID_RE = re.compile(r"\bRP-[A-Z]+-\d+\b")
_WRAPPER_NAME_RE = re.compile(r"rdx-tea-[A-Za-z0-9_-]+")
_ARM_PATH_RE = re.compile(r"(?<![A-Za-z0-9/])(baseline|candidate)/")

# Layer-1 deterministic detectors — mirror rubric v3.
_DETECTORS = {
    "cancellation_specificity": [
        "cancellation-safe", "cancel-safe", "cancellation point",
        "cancel_token", "cancellation semantics", "AbortHandle",
    ],
    "timeout_specificity": [
        "timeout(", "tokio::time::timeout", "deadline",
        "hard timeout", "soft timeout",
    ],
    "shutdown_specificity": [
        "graceful shutdown", "drain in-flight", "shutdown broadcast",
        "SIGTERM handling",
    ],
    "partial_progress_preservation": [
        "partial progress", "resume from checkpoint",
        "idempotent write", "torn write", "no torn write",
    ],
    "cleanup_ownership": [
        "drop guard", "RAII cleanup", "cleanup owner",
        "who owns cleanup", "ownership of cleanup",
    ],
    "task_lifecycle_ownership": [
        "task lifecycle", "spawn/join", "who joins",
        "task ownership", "abort semantics",
    ],
    "api_compatibility_boundary": [
        "public api", "public async fn", "boundary contract",
        "semver", "breaking change",
    ],
    "api_error_boundary_specificity": [
        "error boundary", "public error type",
        "error contract", "exhaustive match",
    ],
    "negative_path_coverage": [
        "error case", "failure mode", "negative test",
        "invalid input", "adversarial input",
    ],
    "executable_test_detail": [
        "assert_eq!", "#[tokio::test]", "expect(",
        "Given/When/Then", "acceptance criteria:",
    ],
}


class GraderError(RuntimeError):
    pass


# -------------------------------------------------- sample id + mapping

def _sample_id(idx: int) -> str:
    return f"sample-{idx:03d}"


def sanitise(text: str) -> str:
    """Strip every identifier that could reveal the arm."""
    out = _RP_ID_RE.sub("[RP-ID-REDACTED]", text)
    out = _WRAPPER_NAME_RE.sub("wrapper-REDACTED", out)
    out = _ARM_PATH_RE.sub("REDACTED/", out)
    return out


def _walk_pilot_evidence(pilot_root: Path) -> list[Path]:
    """Return every live-evidence.v2.json under pilot_root, deterministic
    order (by scenario/arm/rep/run_id)."""
    return sorted(pilot_root.rglob("live-evidence.v2.json"))


def prepare_blind(pilot_root: Path, out_root: Path) -> dict:
    """Walk pilot evidence; emit sanitised samples + mapping."""
    if not pilot_root.exists():
        raise GraderError(f"pilot root missing: {pilot_root}")
    out_root.mkdir(parents=True, exist_ok=True)
    samples_dir = out_root / "samples"
    samples_dir.mkdir(exist_ok=True)
    mapping_dir = out_root / "mapping"
    mapping_dir.mkdir(exist_ok=True)

    entries: list[dict] = []
    idx = 1
    for bundle_path in _walk_pilot_evidence(pilot_root):
        bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
        # Locate the arm's tea artefact — first entry under new_artefacts.
        art_names = bundle.get("artifacts", {}).get("new_artefacts", [])
        raw_texts: list[str] = []
        for rel in art_names:
            f = Path(rel)
            if f.exists() and f.is_file():
                try:
                    raw_texts.append(f.read_text(encoding="utf-8"))
                except UnicodeDecodeError:
                    continue
        # Fallback: use the run-report.json content for texts if no artifact.
        if not raw_texts:
            rr = bundle_path.parent / "run-report.json"
            if rr.exists():
                raw_texts.append(rr.read_text(encoding="utf-8"))
        joined = "\n\n---\n\n".join(raw_texts) if raw_texts else ""
        sanitised = sanitise(joined)
        sid = _sample_id(idx)
        (samples_dir / f"{sid}.md").write_text(sanitised, encoding="utf-8")
        entries.append({
            "sample_id": sid,
            "arm": bundle.get("arm"),
            "scenario": bundle.get("scenario"),
            "run_id": bundle.get("run_id"),
            "source_bundle": str(bundle_path),
            "sample_sha256": hashlib.sha256(sanitised.encode("utf-8")).hexdigest(),
        })
        idx += 1

    # Deliberately split mapping into a file the comparative grader must
    # NOT read; a `.gitignore` marker documents intent for the reviewer.
    (mapping_dir / "MAPPING.json").write_text(
        json.dumps(entries, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (mapping_dir / "DO_NOT_READ.txt").write_text(
        "This directory contains the sample-id → arm mapping. It MUST\n"
        "NOT be read by the comparative grader — that would defeat the\n"
        "blinding. `merge` re-attaches labels after grading.\n",
        encoding="utf-8",
    )
    return {
        "sample_count": len(entries),
        "samples_dir": str(samples_dir),
        "mapping_path": str(mapping_dir / "MAPPING.json"),
    }


# -------------------------------------------------- deterministic layer

def _boolean_hit(text: str, keywords: list[str]) -> bool:
    lo = text.lower()
    return any(k.lower() in lo for k in keywords)


def grade_deterministic(samples_dir: Path, out_dir: Path) -> dict:
    """Layer-1: compute deterministic metrics from sanitised samples."""
    out_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict] = []
    for sample_path in sorted(samples_dir.glob("sample-*.md")):
        text = sample_path.read_text(encoding="utf-8")
        metrics = {name: _boolean_hit(text, kws)
                    for name, kws in _DETECTORS.items()}
        # Coarse hallucination proxy: count of stringified file paths
        # ending in .rs / .toml that don't exist under standard fixture
        # trees. Deferred to merge stage which has access to fixtures.
        row = {
            "sample_id": sample_path.stem,
            "metrics": metrics,
        }
        (out_dir / f"{sample_path.stem}.det.json").write_text(
            json.dumps(row, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        results.append(row)
    (out_dir / "SUMMARY.json").write_text(
        json.dumps({"count": len(results),
                     "detectors": sorted(_DETECTORS.keys())},
                     indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return {"count": len(results)}


# ----------------------------------------------------------------- LLM layer

def _prompt_sha256() -> str:
    if not PROMPT_PATH.exists():
        raise GraderError(f"grader prompt missing: {PROMPT_PATH}")
    return hashlib.sha256(PROMPT_PATH.read_bytes()).hexdigest()


def grade_llm(samples_dir: Path, out_dir: Path, *,
              model: str = "claude-haiku-4-5-20251001",
              dry_run: bool = True) -> dict:
    """D3.3.2 §16.4. Layer-2 blinded LLM grader.

    In D3.3.2 this is executed with `--dry-run=True` unconditionally —
    the runner is testable and produces a NOT_RUN skeleton per sample.
    The full run is scheduled in a separate D3.4 execution window.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    prompt_sha = _prompt_sha256()
    outcomes: list[dict] = []
    for sample_path in sorted(samples_dir.glob("sample-*.md")):
        sid = sample_path.stem
        payload = {
            "sample_id": sid,
            "grader_model": model,
            "grader_prompt_sha256": prompt_sha,
            "status": "NOT_RUN" if dry_run else "PENDING_LIVE",
            "sample_sha256": hashlib.sha256(
                sample_path.read_bytes()).hexdigest(),
        }
        (out_dir / f"{sid}.llm.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        outcomes.append(payload)
    return {"count": len(outcomes), "dry_run": dry_run}


# ----------------------------------------------------------------- merge

def merge(*, samples_dir: Path, mapping_path: Path, deterministic_dir: Path,
          llm_dir: Path | None, out_dir: Path) -> dict:
    """Re-attach arm labels only AFTER grading. Records per-sample
    disagreement between layer 1 and layer 2 — never overwrites."""
    if not mapping_path.exists():
        raise GraderError(f"mapping missing: {mapping_path}")
    mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    by_sid = {entry["sample_id"]: entry for entry in mapping}
    out_dir.mkdir(parents=True, exist_ok=True)
    merged: list[dict] = []
    for det_path in sorted(deterministic_dir.glob("sample-*.det.json")):
        det = json.loads(det_path.read_text(encoding="utf-8"))
        sid = det["sample_id"]
        entry = by_sid.get(sid, {})
        llm_row = None
        if llm_dir is not None:
            llm_path = llm_dir / f"{sid}.llm.json"
            if llm_path.exists():
                llm_row = json.loads(llm_path.read_text(encoding="utf-8"))
        row = {
            "sample_id": sid,
            "arm": entry.get("arm"),
            "scenario": entry.get("scenario"),
            "run_id": entry.get("run_id"),
            "deterministic_metrics": det["metrics"],
            "llm_metrics": llm_row,
            "disagreements": _disagreements(det["metrics"], llm_row),
        }
        (out_dir / f"{sid}.merged.json").write_text(
            json.dumps(row, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        merged.append(row)
    (out_dir / "SUMMARY.json").write_text(
        json.dumps({"count": len(merged)}, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return {"count": len(merged)}


def _disagreements(det: dict, llm_row: dict | None) -> list[str]:
    """List metric names where deterministic and LLM verdicts diverge.
    Missing LLM row = no disagreements to log."""
    if llm_row is None or llm_row.get("status") in ("NOT_RUN", "PENDING_LIVE"):
        return []
    disagree: list[str] = []
    llm_metrics = (llm_row.get("metrics") or {})
    for name, det_bool in det.items():
        llm_entry = llm_metrics.get(f"{name}_semantic")
        if not isinstance(llm_entry, dict):
            continue
        llm_bool = llm_entry.get("verdict")
        if isinstance(llm_bool, bool) and llm_bool is not det_bool:
            disagree.append(name)
    return disagree


# ----------------------------------------------------------------- report

def report(merged_dir: Path, out_path: Path) -> dict:
    """Aggregate merged results into a pilot-level verdict per rubric
    v3. Because D3.3.2 does not execute the actual LLM layer, this
    stops at INCONCLUSIVE unless the layer-1 signal is overwhelmingly
    directional AND all fidelity gates PASS — which requires evidence
    the D3.3.2 window does not produce."""
    rows: list[dict] = []
    for p in sorted(merged_dir.glob("sample-*.merged.json")):
        rows.append(json.loads(p.read_text(encoding="utf-8")))
    total = len(rows)
    verdict = "PILOT_INCONCLUSIVE" if total == 0 else "PILOT_INCONCLUSIVE"
    # The report itself never overclaims. Downstream D3.4 executor is
    # the one that promotes verdict.
    payload = {
        "schema_version": "rdx-tea-pilot-report.v1",
        "rubric_version": "rdx-tea-pilot-rubric.v3",
        "generated_at": run_live._utc_now(),
        "sample_count": total,
        "verdict": verdict,
        "note": ("D3.3.2 grader report — LLM layer NOT_RUN by design in "
                 "this stage. Verdict cannot exceed PILOT_INCONCLUSIVE "
                 "until D3.4 executes the full grader."),
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True),
                        encoding="utf-8")
    return payload


# ----------------------------------------------------------------- CLI

def main() -> int:
    ap = argparse.ArgumentParser(description="rdx-tea D3.3.2 blinded grader")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("prepare-blind")
    p1.add_argument("--pilot-root", type=Path, required=True)
    p1.add_argument("--out-root", type=Path, required=True)

    p2 = sub.add_parser("grade-deterministic")
    p2.add_argument("--samples-dir", type=Path, required=True)
    p2.add_argument("--out-dir", type=Path, required=True)

    p3 = sub.add_parser("grade-llm")
    p3.add_argument("--samples-dir", type=Path, required=True)
    p3.add_argument("--out-dir", type=Path, required=True)
    p3.add_argument("--model", default="claude-haiku-4-5-20251001")
    p3.add_argument("--dry-run", action="store_true", default=True)

    p4 = sub.add_parser("merge")
    p4.add_argument("--samples-dir", type=Path, required=True)
    p4.add_argument("--mapping", type=Path, required=True)
    p4.add_argument("--det-dir", type=Path, required=True)
    p4.add_argument("--llm-dir", type=Path, default=None)
    p4.add_argument("--out-dir", type=Path, required=True)

    p5 = sub.add_parser("report")
    p5.add_argument("--merged-dir", type=Path, required=True)
    p5.add_argument("--out", type=Path, required=True)

    args = ap.parse_args()
    try:
        if args.cmd == "prepare-blind":
            r = prepare_blind(args.pilot_root, args.out_root)
        elif args.cmd == "grade-deterministic":
            r = grade_deterministic(args.samples_dir, args.out_dir)
        elif args.cmd == "grade-llm":
            r = grade_llm(args.samples_dir, args.out_dir,
                          model=args.model, dry_run=args.dry_run)
        elif args.cmd == "merge":
            r = merge(samples_dir=args.samples_dir, mapping_path=args.mapping,
                      deterministic_dir=args.det_dir, llm_dir=args.llm_dir,
                      out_dir=args.out_dir)
        elif args.cmd == "report":
            r = report(args.merged_dir, args.out)
        else:
            r = {"error": f"unknown cmd {args.cmd}"}
        print(json.dumps(r, indent=2, sort_keys=True))
        return 0
    except GraderError as err:
        print(json.dumps({"status": "FAIL", "error": str(err)}, indent=2))
        return 2


if __name__ == "__main__":
    sys.exit(main())
