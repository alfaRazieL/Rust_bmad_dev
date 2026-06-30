"""Phase 6 §6.1 — Deterministic regression timing.

RDX_TEST_STRATEGY.md §6 row:
  "Execution time L0+L1+L2 locally ≤ 30s"
RDX_IMPLEMENTATION_PLAN_TESTED.md §6.1:
  "All L0/L1/L2 regression suite runs in < 30s locally"

This test invokes pytest on the three layers in a subprocess and asserts
wall-clock duration < 30s + exit code 0. Guarded against pytest-in-pytest
recursion by limiting the sub-run to tests/contracts and tests/unit
(this test lives in tests/acceptance, so is NOT re-collected by the
child).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
BUDGET_SECONDS = 30.0


def _running_under_self() -> bool:
    return os.environ.get("RDX_REGRESSION_TIMING_INNER") == "1"


@pytest.mark.skipif(
    _running_under_self(),
    reason="recursion guard — child pytest must not re-run the timing harness",
)
def test_l0_l1_l2_regression_under_30s() -> None:
    env = dict(os.environ)
    env["RDX_REGRESSION_TIMING_INNER"] = "1"

    start = time.perf_counter()
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/contracts",
            "tests/unit",
            "-q",
            "--no-header",
            "-p",
            "no:cacheprovider",
        ],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=BUDGET_SECONDS * 2,
    )
    elapsed = time.perf_counter() - start

    combined = (result.stdout + result.stderr)[-2000:]
    assert result.returncode == 0, (
        f"L0+L1+L2 regression failed (rc={result.returncode}):\n{combined}"
    )
    assert elapsed < BUDGET_SECONDS, (
        f"L0+L1+L2 regression took {elapsed:.2f}s, budget is {BUDGET_SECONDS}s "
        f"(RDX_TEST_STRATEGY.md §6). Profile slow tests:\n{combined}"
    )
