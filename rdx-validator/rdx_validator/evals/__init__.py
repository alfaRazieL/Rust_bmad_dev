"""Phase 6 — L5 eval-runner harness.

The bmad-eval-runner skill (external) executes the prompts in
tests/evals/<slug>/case.yaml against a real LLM and writes one JSON
record per run into <case>.artifacts_dir. This module is the local-side
harness that loads cases, loads runs, and applies the rolling-window
threshold contract defined in RDX_TEST_STRATEGY.md §6.

Nothing here calls an LLM; that boundary is owned by bmad-eval-runner.
"""

from __future__ import annotations

import dataclasses as _dc
import datetime as _dt
import json
import os
from pathlib import Path
from typing import Iterable

import yaml


__all__ = [
    "EvalCase",
    "EvalRun",
    "RollingWindowAggregator",
    "ThresholdChecker",
    "ThresholdVerdict",
    "load_case",
    "load_runs",
]


@_dc.dataclass(frozen=True)
class EvalCase:
    """Subset of case.yaml fields the harness consumes. Other fields
    (prompt, expected_assertions, grader_model) are owned by
    bmad-eval-runner and do not affect threshold judgment."""

    id: str
    slug: str
    phase: int
    layer: str
    pass_threshold: float
    repeat_count: int
    rolling_window_days: int
    gate: str
    artifacts_dir: str


@_dc.dataclass(frozen=True)
class EvalRun:
    case_slug: str
    run_id: str
    timestamp: _dt.datetime
    passed: bool


@_dc.dataclass(frozen=True)
class ThresholdVerdict:
    """Result of applying a case's threshold to a window of runs."""

    case_slug: str
    status: str            # 'PASS' | 'BELOW_THRESHOLD' | 'INSUFFICIENT_DATA'
    pass_rate: float | None
    threshold: float
    runs_in_window: int
    runs_required: int
    blocking: bool


_ALLOWED_STATUSES = ("PASS", "BELOW_THRESHOLD", "INSUFFICIENT_DATA")


def load_case(case_path: Path) -> EvalCase:
    data = yaml.safe_load(Path(case_path).read_text(encoding="utf-8"))
    return EvalCase(
        id=data["id"],
        slug=data["slug"],
        phase=int(data["phase"]),
        layer=data["layer"],
        pass_threshold=float(data["pass_threshold"]),
        repeat_count=int(data["repeat_count"]),
        rolling_window_days=int(data["rolling_window_days"]),
        gate=data["gate"],
        artifacts_dir=data["artifacts_dir"],
    )


def load_runs(runs_dir: Path) -> list[EvalRun]:
    """Read every *.json run record from `runs_dir` and return them
    sorted by timestamp ascending. Missing dir → empty list."""

    p = Path(runs_dir)
    if not p.exists():
        return []
    out: list[EvalRun] = []
    for f in sorted(p.iterdir()):
        if f.suffix != ".json":
            continue
        rec = json.loads(f.read_text(encoding="utf-8"))
        out.append(
            EvalRun(
                case_slug=rec["case_slug"],
                run_id=rec["run_id"],
                timestamp=_dt.datetime.fromisoformat(rec["timestamp"]),
                passed=bool(rec["passed"]),
            )
        )
    out.sort(key=lambda r: r.timestamp)
    return out


class RollingWindowAggregator:
    """Computes per-case pass rate over a sliding window of N days."""

    def __init__(self, window_days: int, now: _dt.datetime | None = None) -> None:
        if window_days <= 0:
            raise ValueError("window_days must be positive")
        self.window_days = window_days
        self.now = now or _dt.datetime.now(_dt.timezone.utc)

    def _in_window(self, run: EvalRun) -> bool:
        cutoff = self.now - _dt.timedelta(days=self.window_days)
        return run.timestamp >= cutoff

    def runs_in_window(self, case_slug: str, runs: Iterable[EvalRun]) -> list[EvalRun]:
        return [r for r in runs if r.case_slug == case_slug and self._in_window(r)]

    def pass_rate(self, case_slug: str, runs: Iterable[EvalRun]) -> float | None:
        bucket = self.runs_in_window(case_slug, runs)
        if not bucket:
            return None
        return sum(1 for r in bucket if r.passed) / len(bucket)


class ThresholdChecker:
    """Applies an EvalCase's pass_threshold + repeat_count to a window
    of runs and emits a ThresholdVerdict whose status is drawn from
    the canonical taxonomy."""

    def __init__(self, window_days: int, now: _dt.datetime | None = None) -> None:
        self.aggregator = RollingWindowAggregator(window_days=window_days, now=now)

    def check(self, case: EvalCase, runs: Iterable[EvalRun]) -> ThresholdVerdict:
        bucket = self.aggregator.runs_in_window(case.slug, runs)
        runs_in_window = len(bucket)
        rate = self.aggregator.pass_rate(case.slug, runs)

        if runs_in_window < case.repeat_count:
            verdict = ThresholdVerdict(
                case_slug=case.slug,
                status="INSUFFICIENT_DATA",
                pass_rate=rate,
                threshold=case.pass_threshold,
                runs_in_window=runs_in_window,
                runs_required=case.repeat_count,
                blocking=True,
            )
        elif rate is None or rate < case.pass_threshold:
            verdict = ThresholdVerdict(
                case_slug=case.slug,
                status="BELOW_THRESHOLD",
                pass_rate=rate,
                threshold=case.pass_threshold,
                runs_in_window=runs_in_window,
                runs_required=case.repeat_count,
                blocking=True,
            )
        else:
            verdict = ThresholdVerdict(
                case_slug=case.slug,
                status="PASS",
                pass_rate=rate,
                threshold=case.pass_threshold,
                runs_in_window=runs_in_window,
                runs_required=case.repeat_count,
                blocking=False,
            )

        assert verdict.status in _ALLOWED_STATUSES, (
            f"internal: status {verdict.status!r} not in canonical taxonomy"
        )
        return verdict
