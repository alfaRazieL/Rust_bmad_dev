"""L1 unit tests for the baseline comparator.

Closes:
  T-L1-BASE-001 — base red, head red, same signature → BASELINE_FAILURE_OBSERVED
  T-L1-BASE-002 — base red, head red, new signature → REGRESSION_FAILURE
  T-L1-BASE-003 — base green, head red → REGRESSION_FAILURE
  T-L1-BASE-004 — base red, head green → REGRESSION_FIXED
"""

from __future__ import annotations

import json
from pathlib import Path

from rdx_validator.baseline import RunResult, compare
from rdx_validator.status import Verdict


def _load_pair(fixtures_dir: Path, name: str) -> tuple[RunResult, RunResult]:
    data = json.loads((fixtures_dir / "baseline" / name).read_text(encoding="utf-8"))

    def to_run(d: dict) -> RunResult:
        return RunResult(passed=d["passed"], error_signature=d.get("error_signature"))

    return to_run(data["base"]), to_run(data["head"])


def test_l1_base_001_same_signature(fixtures_dir: Path):
    base, head = _load_pair(fixtures_dir, "same-error-signature.json")
    assert compare(base, head) == Verdict.BASELINE_FAILURE_OBSERVED


def test_l1_base_002_new_signature(fixtures_dir: Path):
    base, head = _load_pair(fixtures_dir, "new-error-signature.json")
    assert compare(base, head) == Verdict.REGRESSION_FAILURE


def test_l1_base_003_green_to_red(fixtures_dir: Path):
    base, head = _load_pair(fixtures_dir, "green-to-red.json")
    assert compare(base, head) == Verdict.REGRESSION_FAILURE


def test_l1_base_004_red_to_green(fixtures_dir: Path):
    base, head = _load_pair(fixtures_dir, "red-to-green.json")
    assert compare(base, head) == Verdict.REGRESSION_FIXED
