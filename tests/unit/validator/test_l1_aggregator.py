"""L1 unit tests for the status aggregator and exit-code mapper.

Closes:
  T-L1-AGG-001  — aggregator returns BLOCKED when any FAIL present
  T-L1-AGG-002  — NOT_RUN-with-reason does NOT block in Mode 0/1
  T-L1-AGG-003  — NOT_RUN-without-reason promotes to FAIL
  T-L1-EXIT-001 — all PASS → 0
  T-L1-EXIT-002 — any FAIL → 1 (overrides REVIEW_REQUIRED)
  T-L1-EXIT-003 — REVIEW_REQUIRED without FAIL → 4
  T-L1-EXIT-004 — APPROVAL_REQUIRED without FAIL → 3
  T-L1-EXIT-005 — ENVIRONMENT_UNAVAILABLE → 2 always
  T-L1-POL-001  — advisory mode → exit always 0
"""

from __future__ import annotations

import json
from pathlib import Path

from rdx_validator.policy import load as load_policy
from rdx_validator.status import (
    Mode,
    Policy,
    RuleVerdict,
    Severity,
    Verdict,
    aggregate,
    exit_code_for,
)


def _load_rules(path: Path) -> list[RuleVerdict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return [
        RuleVerdict(
            rule_id=r["rule_id"],
            category=r["category"],
            verdict=Verdict(r["verdict"]),
            severity=Severity(r.get("severity", "INFO")),
            reason=r.get("reason"),
        )
        for r in data["rules"]
    ]


# ---------- T-L1-AGG-001 ----------
def test_l1_agg_001_any_fail_yields_blocked(fixtures_dir: Path):
    rules = _load_rules(fixtures_dir / "evidence" / "agg-one-fail.json")
    agg = aggregate(rules)
    assert agg.verdict == Verdict.BLOCKED
    assert agg.exit_code == 1


# ---------- T-L1-AGG-002 ----------
def test_l1_agg_002_not_run_with_reason_mode0_does_not_block(fixtures_dir: Path):
    rules = _load_rules(fixtures_dir / "evidence" / "agg-not-run-with-reason.json")
    policy = Policy(
        mode=Mode.MODE_0,
        accepted_not_run_reasons=("cargo audit offline",),
    )
    agg = aggregate(rules, policy)
    assert agg.verdict != Verdict.BLOCKED
    assert agg.exit_code == 0


# ---------- T-L1-AGG-003 ----------
def test_l1_agg_003_not_run_without_reason_promoted_to_fail(fixtures_dir: Path):
    rules = _load_rules(fixtures_dir / "evidence" / "agg-not-run-no-reason.json")
    agg = aggregate(rules)
    promoted = agg.by_rule["CORE-011"]
    assert promoted.verdict == Verdict.FAIL
    assert promoted.is_blocking is True
    assert agg.verdict == Verdict.BLOCKED
    assert agg.exit_code == 1
    assert "CORE-011" in agg.promoted_rules


# ---------- T-L1-EXIT-001 ----------
def test_l1_exit_001_all_pass_to_0():
    rules = [
        RuleVerdict(rule_id="CORE-007", category=1, verdict=Verdict.PASS),
        RuleVerdict(rule_id="CORE-011", category=1, verdict=Verdict.NOT_APPLICABLE),
    ]
    assert exit_code_for(rules) == 0


# ---------- T-L1-EXIT-002 ----------
def test_l1_exit_002_fail_overrides_review_required():
    rules = [
        RuleVerdict(rule_id="CORE-011", category=1, verdict=Verdict.FAIL, severity=Severity.BLOCKING),
        RuleVerdict(rule_id="CORE-001", category=3, verdict=Verdict.REVIEW_REQUIRED),
    ]
    assert exit_code_for(rules) == 1


# ---------- T-L1-EXIT-003 ----------
def test_l1_exit_003_review_required_only_to_4():
    rules = [
        RuleVerdict(rule_id="CORE-007", category=1, verdict=Verdict.PASS),
        RuleVerdict(rule_id="CORE-001", category=3, verdict=Verdict.REVIEW_REQUIRED),
    ]
    assert exit_code_for(rules) == 4


# ---------- T-L1-EXIT-004 ----------
def test_l1_exit_004_approval_required_only_to_3():
    rules = [
        RuleVerdict(rule_id="RP-UNSAFE-001", category=4, verdict=Verdict.APPROVAL_REQUIRED, severity=Severity.BLOCKING),
    ]
    assert exit_code_for(rules) == 3


# ---------- T-L1-EXIT-005 ----------
def test_l1_exit_005_environment_unavailable_to_2():
    rules = [
        RuleVerdict(rule_id="CORE-011", category=1, verdict=Verdict.ENVIRONMENT_UNAVAILABLE, severity=Severity.BLOCKING),
        # Even with a FAIL present, env-unavailable wins
        RuleVerdict(rule_id="CORE-007", category=1, verdict=Verdict.FAIL, severity=Severity.BLOCKING),
    ]
    assert exit_code_for(rules) == 2


# ---------- T-L1-POL-001 ----------
def test_l1_pol_001_advisory_mode_never_blocks(fixtures_dir: Path):
    policy = load_policy(fixtures_dir / "policy" / "advisory-mode.json")
    assert policy.advisory is True
    rules = [
        RuleVerdict(rule_id="CORE-011", category=1, verdict=Verdict.FAIL, severity=Severity.BLOCKING),
    ]
    agg = aggregate(rules, policy)
    assert agg.exit_code == 0
    assert agg.verdict == Verdict.PASS
