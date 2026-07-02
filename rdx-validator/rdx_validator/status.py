"""Status taxonomy + aggregator + exit-code mapper.

Source of truth: `tests/contracts/status-definitions.json` and
`RDX_TEST_STRATEGY.md` §5.

Closes (Phase 2):
  T-L1-AGG-001..003 — aggregator behaviour
  T-L1-EXIT-001..005 — exit-code mapping
  T-L1-POL-001    — policy-aware advisory mode
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable


class Mode(str, Enum):
    MODE_0 = "MODE_0"
    MODE_1 = "MODE_1"
    MODE_2 = "MODE_2"
    MODE_3 = "MODE_3"
    MODE_4 = "MODE_4"


class Verdict(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    NOT_RUN = "NOT_RUN"
    EVIDENCE_REQUIRED = "EVIDENCE_REQUIRED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    BASELINE_FAILURE_OBSERVED = "BASELINE_FAILURE_OBSERVED"
    BASELINE_BLOCKS_VALIDATION = "BASELINE_BLOCKS_VALIDATION"
    REGRESSION_FAILURE = "REGRESSION_FAILURE"
    REGRESSION_FIXED = "REGRESSION_FIXED"
    ENVIRONMENT_UNAVAILABLE = "ENVIRONMENT_UNAVAILABLE"
    TOOL_UNAVAILABLE = "TOOL_UNAVAILABLE"
    BLOCKED = "BLOCKED"


class Severity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    BLOCKING = "BLOCKING"


# Verdicts that drive exit code 1 (FAIL class)
_FAIL_VERDICTS: frozenset[str] = frozenset({Verdict.FAIL.value, Verdict.REGRESSION_FAILURE.value})

# Verdicts that drive exit code 3 (blocked-but-not-runtime-error class)
_BLOCKED3_VERDICTS: frozenset[str] = frozenset(
    {
        Verdict.BLOCKED.value,
        Verdict.BASELINE_BLOCKS_VALIDATION.value,
        Verdict.APPROVAL_REQUIRED.value,
        Verdict.EVIDENCE_REQUIRED.value,
    }
)

# NOT_RUN may also drive exit 3 if the reason is not on the approved list.
# Phase 2 takes a strict default: any NOT_RUN with a reason maps to exit 3
# unless the policy says advisory.
_NOT_RUN = Verdict.NOT_RUN.value


@dataclass(frozen=True)
class RuleVerdict:
    rule_id: str
    category: int
    verdict: Verdict
    severity: Severity = Severity.INFO
    reason: str | None = None  # required for NOT_RUN
    blocking_override: bool | None = None  # set by aggregator / policy

    @property
    def is_blocking(self) -> bool:
        if self.blocking_override is not None:
            return self.blocking_override
        if self.severity == Severity.BLOCKING:
            return True
        if self.verdict.value in _FAIL_VERDICTS:
            return True
        return False


@dataclass
class Policy:
    """Per-project policy resolved from `--policy-config` / `--mode`."""

    mode: Mode = Mode.MODE_2
    advisory: bool = False  # if True, all FAIL → reported, exit always 0
    accepted_not_run_reasons: tuple[str, ...] = ()
    approval_for_baseline_block: bool = False  # override BASELINE_BLOCKS_VALIDATION

    def not_run_is_blocking(self, reason: str | None) -> bool:
        """Strategy §5.1: NOT_RUN is blocking in Mode 2+ unless reason approved.

        T-L1-AGG-002: a NOT_RUN *with* a recorded reason does NOT block in Mode 0/1.
        T-L1-AGG-003: a NOT_RUN *without* a reason is promoted to FAIL by the aggregator.
        """
        if self.advisory:
            return False
        if self.mode in (Mode.MODE_0, Mode.MODE_1):
            return False
        # Mode 2+: any NOT_RUN blocks unless reason is on the approved list
        if reason and reason in self.accepted_not_run_reasons:
            return False
        return True


@dataclass
class Aggregate:
    verdict: Verdict
    exit_code: int
    blocking_count: int = 0
    warning_count: int = 0
    info_count: int = 0
    promoted_rules: list[str] = field(default_factory=list)
    by_rule: dict[str, RuleVerdict] = field(default_factory=dict)


def normalise_rules(rules: Iterable[RuleVerdict], policy: Policy) -> list[RuleVerdict]:
    """Apply policy semantics to per-rule verdicts.

    - NOT_RUN without a reason → upgraded to FAIL (T-L1-AGG-003)
    - NOT_RUN with reason: blocking determined by policy
    - In advisory mode (T-L1-POL-001): all blocking flags are cleared so exit
      code resolves to 0.
    """
    out: list[RuleVerdict] = []
    for r in rules:
        v = r.verdict
        sev = r.severity
        block = None
        if v == Verdict.NOT_RUN:
            if not r.reason:
                v = Verdict.FAIL
                sev = Severity.BLOCKING
                block = True
            else:
                block = policy.not_run_is_blocking(r.reason)
                if sev == Severity.INFO and block:
                    sev = Severity.BLOCKING
        if policy.advisory:
            # Advisory mode keeps the per-rule verdict but never blocks.
            block = False
            if sev == Severity.BLOCKING:
                sev = Severity.WARNING
        out.append(
            RuleVerdict(
                rule_id=r.rule_id,
                category=r.category,
                verdict=v,
                severity=sev,
                reason=r.reason,
                blocking_override=block,
            )
        )
    return out


def aggregate(rules: Iterable[RuleVerdict], policy: Policy | None = None) -> Aggregate:
    policy = policy or Policy()
    norm = normalise_rules(rules, policy)

    blocking_count = sum(1 for r in norm if r.is_blocking)
    warning_count = sum(1 for r in norm if r.severity == Severity.WARNING and not r.is_blocking)
    info_count = sum(1 for r in norm if r.severity == Severity.INFO and not r.is_blocking)
    promoted = [r.rule_id for r in norm if r.verdict == Verdict.FAIL and not _was_originally_fail(rules, r.rule_id)]

    verdict = aggregate_verdict(norm, policy)
    exit_code = exit_code_for(norm, policy)

    return Aggregate(
        verdict=verdict,
        exit_code=exit_code,
        blocking_count=blocking_count,
        warning_count=warning_count,
        info_count=info_count,
        promoted_rules=promoted,
        by_rule={r.rule_id: r for r in norm},
    )


def _was_originally_fail(original: Iterable[RuleVerdict], rule_id: str) -> bool:
    for r in original:
        if r.rule_id == rule_id:
            return r.verdict == Verdict.FAIL
    return False


def aggregate_verdict(rules: Iterable[RuleVerdict], policy: Policy) -> Verdict:
    rule_list = list(rules)
    if policy.advisory:
        return Verdict.PASS
    if any(r.verdict == Verdict.ENVIRONMENT_UNAVAILABLE for r in rule_list):
        return Verdict.ENVIRONMENT_UNAVAILABLE
    if any(r.verdict in (Verdict.FAIL, Verdict.REGRESSION_FAILURE) for r in rule_list):
        return Verdict.BLOCKED
    if any(r.is_blocking for r in rule_list):
        return Verdict.BLOCKED
    if any(r.verdict == Verdict.APPROVAL_REQUIRED for r in rule_list):
        return Verdict.BLOCKED
    if any(r.verdict == Verdict.EVIDENCE_REQUIRED for r in rule_list):
        return Verdict.BLOCKED
    if any(r.verdict == Verdict.REVIEW_REQUIRED for r in rule_list):
        return Verdict.REVIEW_REQUIRED
    if any(r.verdict == Verdict.BASELINE_FAILURE_OBSERVED for r in rule_list):
        return Verdict.BASELINE_FAILURE_OBSERVED
    if all(r.verdict == Verdict.NOT_APPLICABLE for r in rule_list):
        return Verdict.NOT_APPLICABLE
    return Verdict.PASS


def exit_code_for(rules: Iterable[RuleVerdict], policy: Policy | None = None) -> int:
    """Compute exit code per RDX_TEST_STRATEGY.md §5.3.

    Resolution order:
      ENVIRONMENT_UNAVAILABLE → 2
      FAIL or REGRESSION_FAILURE → 1
      BLOCKED / BASELINE_BLOCKS_VALIDATION / APPROVAL_REQUIRED / EVIDENCE_REQUIRED → 3
      REVIEW_REQUIRED → 4
      otherwise → 0
    """
    policy = policy or Policy()
    rule_list = list(rules)
    if policy.advisory:
        return 0
    has_env = any(r.verdict == Verdict.ENVIRONMENT_UNAVAILABLE for r in rule_list)
    if has_env:
        return 2
    has_fail = any(r.verdict.value in _FAIL_VERDICTS for r in rule_list)
    if has_fail:
        return 1
    has_blocked = any(
        r.verdict.value in _BLOCKED3_VERDICTS for r in rule_list
    )
    if has_blocked:
        return 3
    # Blocking NOT_RUN counts as exit 3 too.
    if any(r.verdict == Verdict.NOT_RUN and r.is_blocking for r in rule_list):
        return 3
    if any(r.verdict == Verdict.REVIEW_REQUIRED for r in rule_list):
        return 4
    return 0
