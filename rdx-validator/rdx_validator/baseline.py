"""Baseline comparator (dual-run support).

Closes (Phase 2):
  T-L1-BASE-001 — base=red & head=red same signature → BASELINE_FAILURE_OBSERVED
  T-L1-BASE-002 — base=red & head=red new signature → REGRESSION_FAILURE
  T-L1-BASE-003 — base=green & head=red → REGRESSION_FAILURE
  T-L1-BASE-004 — base=red & head=green → REGRESSION_FIXED
"""

from __future__ import annotations

from dataclasses import dataclass

from .status import Verdict


@dataclass(frozen=True)
class RunResult:
    passed: bool
    error_signature: str | None = None

    @classmethod
    def passing(cls) -> "RunResult":
        return cls(passed=True)

    @classmethod
    def failing(cls, signature: str) -> "RunResult":
        return cls(passed=False, error_signature=signature)


def compare(base: RunResult, head: RunResult) -> Verdict:
    """Return the baseline verdict for a (base, head) pair."""
    if base.passed and head.passed:
        return Verdict.PASS
    if base.passed and not head.passed:
        return Verdict.REGRESSION_FAILURE
    if not base.passed and head.passed:
        return Verdict.REGRESSION_FIXED
    # Both fail
    if base.error_signature is not None and head.error_signature == base.error_signature:
        return Verdict.BASELINE_FAILURE_OBSERVED
    return Verdict.REGRESSION_FAILURE


def block_validation(base: RunResult) -> bool:
    """True if the base failure prevents a meaningful head check.

    A `BASELINE_BLOCKS_VALIDATION` verdict is set by callers when they detect
    that the base failure makes the head check unmeasurable (e.g., compile
    failure that masks downstream checks).
    """
    return not base.passed and base.error_signature is not None
