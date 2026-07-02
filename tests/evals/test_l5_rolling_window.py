"""Phase 6 entry-gate: assert the rolling-window aggregator computes
pass rates, enforces per-case thresholds, and answers the
"7-day rolling window" exit-gate question per
RDX_IMPLEMENTATION_PLAN_TESTED.md §6 exit gate.
"""

from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path

import pytest


# Import path: rdx-validator/rdx_validator/evals (Phase 6.1 implementation).
# pytest's conftest.py adds rdx-validator to sys.path.
from rdx_validator.evals import (
    EvalCase,
    EvalRun,
    RollingWindowAggregator,
    ThresholdChecker,
    load_case,
)


def _make_run(slug: str, days_ago: int, passed: bool, run_id: str | None = None) -> EvalRun:
    ts = _dt.datetime(2026, 6, 30, 12, 0, 0, tzinfo=_dt.timezone.utc) - _dt.timedelta(days=days_ago)
    return EvalRun(
        case_slug=slug,
        run_id=run_id or f"r-{slug}-{days_ago}-{passed}",
        timestamp=ts,
        passed=passed,
    )


def test_load_case_parses_required_fields(evals_dir: Path) -> None:
    case = load_case(evals_dir / "router-not-skipped" / "case.yaml")
    assert isinstance(case, EvalCase)
    assert case.slug == "router-not-skipped"
    assert case.pass_threshold == 0.90
    assert case.repeat_count == 20
    assert case.rolling_window_days == 7


def test_aggregator_computes_pass_rate_within_window() -> None:
    now = _dt.datetime(2026, 6, 30, 12, 0, 0, tzinfo=_dt.timezone.utc)
    runs = [
        _make_run("router-not-skipped", days_ago=1, passed=True),
        _make_run("router-not-skipped", days_ago=2, passed=True),
        _make_run("router-not-skipped", days_ago=3, passed=False),
        _make_run("router-not-skipped", days_ago=4, passed=True),
    ]
    agg = RollingWindowAggregator(window_days=7, now=now)
    rate = agg.pass_rate("router-not-skipped", runs)
    assert rate == pytest.approx(0.75)


def test_aggregator_excludes_runs_outside_window() -> None:
    now = _dt.datetime(2026, 6, 30, 12, 0, 0, tzinfo=_dt.timezone.utc)
    runs = [
        _make_run("router-not-skipped", days_ago=1, passed=True),
        _make_run("router-not-skipped", days_ago=15, passed=False),  # outside 7-day window
        _make_run("router-not-skipped", days_ago=20, passed=False),  # outside
    ]
    agg = RollingWindowAggregator(window_days=7, now=now)
    rate = agg.pass_rate("router-not-skipped", runs)
    assert rate == pytest.approx(1.0), "stale failures must not count"


def test_aggregator_pass_rate_zero_runs_is_none() -> None:
    now = _dt.datetime(2026, 6, 30, 12, 0, 0, tzinfo=_dt.timezone.utc)
    agg = RollingWindowAggregator(window_days=7, now=now)
    assert agg.pass_rate("router-not-skipped", []) is None


def test_threshold_checker_blocks_below_threshold(evals_dir: Path) -> None:
    case = load_case(evals_dir / "router-not-skipped" / "case.yaml")
    now = _dt.datetime(2026, 6, 30, 12, 0, 0, tzinfo=_dt.timezone.utc)
    # 8 pass / 12 fail = 0.40 — well below 0.90 threshold
    runs = [_make_run("router-not-skipped", days_ago=1, passed=i < 8, run_id=f"r{i}") for i in range(20)]
    checker = ThresholdChecker(window_days=7, now=now)
    verdict = checker.check(case, runs)
    assert verdict.status == "BELOW_THRESHOLD"
    assert verdict.pass_rate == pytest.approx(0.40)
    assert verdict.threshold == 0.90
    assert verdict.blocking is True


def test_threshold_checker_passes_at_or_above_threshold(evals_dir: Path) -> None:
    case = load_case(evals_dir / "router-not-skipped" / "case.yaml")
    now = _dt.datetime(2026, 6, 30, 12, 0, 0, tzinfo=_dt.timezone.utc)
    # 19 pass / 20 = 0.95 — above 0.90 threshold
    runs = [_make_run("router-not-skipped", days_ago=1, passed=i < 19, run_id=f"r{i}") for i in range(20)]
    checker = ThresholdChecker(window_days=7, now=now)
    verdict = checker.check(case, runs)
    assert verdict.status == "PASS"
    assert verdict.pass_rate == pytest.approx(0.95)
    assert verdict.blocking is False


def test_threshold_checker_insufficient_data(evals_dir: Path) -> None:
    """A case that demands N=20 runs but only has 3 cannot be marked PASS.
    The exit-gate (RDX_IMPLEMENTATION_PLAN_TESTED.md §6 exit) says
    "L5 thresholds met for 7-day rolling window" — that implicitly
    requires having at least repeat_count runs in window."""

    case = load_case(evals_dir / "router-not-skipped" / "case.yaml")
    now = _dt.datetime(2026, 6, 30, 12, 0, 0, tzinfo=_dt.timezone.utc)
    runs = [_make_run("router-not-skipped", days_ago=1, passed=True, run_id=f"r{i}") for i in range(3)]
    checker = ThresholdChecker(window_days=7, now=now)
    verdict = checker.check(case, runs)
    assert verdict.status == "INSUFFICIENT_DATA"
    assert verdict.blocking is True, (
        "missing the runs that prove the threshold IS the release blocker"
    )


def test_threshold_checker_100pct_case_one_failure_blocks(evals_dir: Path) -> None:
    """A 100%-threshold case (e.g. no-self-attested-pass) must NEVER
    accept even a single failure within window."""

    case = load_case(evals_dir / "no-self-attested-pass" / "case.yaml")
    assert case.pass_threshold == 1.0
    now = _dt.datetime(2026, 6, 30, 12, 0, 0, tzinfo=_dt.timezone.utc)
    runs = [_make_run("no-self-attested-pass", days_ago=1, passed=i != 0, run_id=f"r{i}") for i in range(20)]
    checker = ThresholdChecker(window_days=7, now=now)
    verdict = checker.check(case, runs)
    assert verdict.status == "BELOW_THRESHOLD"
    assert verdict.blocking is True


def test_aggregator_load_runs_from_artifacts_dir(tmp_path: Path) -> None:
    """Runs are persisted as one JSON file per run in case.artifacts_dir.
    The aggregator loads them all and returns them in chronological order."""

    runs_dir = tmp_path / "runs"
    runs_dir.mkdir(parents=True)
    for i, (days_ago, passed) in enumerate([(3, True), (1, False), (2, True)]):
        rec = {
            "case_slug": "demo",
            "run_id": f"r{i}",
            "timestamp": (
                _dt.datetime(2026, 6, 30, 12, 0, 0, tzinfo=_dt.timezone.utc)
                - _dt.timedelta(days=days_ago)
            ).isoformat(),
            "passed": passed,
        }
        (runs_dir / f"{rec['run_id']}.json").write_text(json.dumps(rec), encoding="utf-8")

    from rdx_validator.evals import load_runs

    runs = load_runs(runs_dir)
    assert len(runs) == 3
    # Records authored: r0=3 days ago, r1=1 day ago, r2=2 days ago.
    # Ascending by timestamp ⇒ oldest first: r0 (-3d), r2 (-2d), r1 (-1d).
    assert [r.run_id for r in runs] == ["r0", "r2", "r1"]


def test_threshold_checker_status_uses_canonical_taxonomy(evals_dir: Path) -> None:
    """Verdict statuses must be drawn from a fixed set so CI can map
    them to exit codes deterministically (cf RDX_TEST_STRATEGY.md §5)."""
    case = load_case(evals_dir / "router-not-skipped" / "case.yaml")
    now = _dt.datetime(2026, 6, 30, 12, 0, 0, tzinfo=_dt.timezone.utc)
    checker = ThresholdChecker(window_days=7, now=now)

    # PASS, BELOW_THRESHOLD, INSUFFICIENT_DATA — and nothing else.
    allowed = {"PASS", "BELOW_THRESHOLD", "INSUFFICIENT_DATA"}
    for runs in [
        [],
        [_make_run("router-not-skipped", days_ago=1, passed=True, run_id=f"r{i}") for i in range(20)],
        [_make_run("router-not-skipped", days_ago=1, passed=False, run_id=f"r{i}") for i in range(20)],
    ]:
        v = checker.check(case, runs)
        assert v.status in allowed, f"status {v.status!r} not in canonical taxonomy"
