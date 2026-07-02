"""CORE-011 — Compile evidence required.

T-L2-CORE011-001 — code change but no compile_check evidence → EVIDENCE_REQUIRED
T-L2-CORE011-002 — evidence has cargo check FAIL → CORE-011 FAIL
T-L2-CORE011-003 — evidence claims PASS without command digest → REJECTED (FAIL)

`evidence_block` is the per-rule evidence sub-object loaded from the evidence
JSON (or None when absent).
"""

from __future__ import annotations

from typing import Iterable

from ..status import RuleVerdict, Severity, Verdict


def _has_rust_change(paths: Iterable[str]) -> bool:
    for p in paths:
        if p.endswith(".rs"):
            return True
    return False


def check_core_011(
    paths_changed: Iterable[str],
    evidence_block: dict | None,
) -> RuleVerdict:
    paths = list(paths_changed)
    if not _has_rust_change(paths):
        return RuleVerdict(
            rule_id="CORE-011",
            category=1,
            verdict=Verdict.NOT_APPLICABLE,
            severity=Severity.INFO,
        )
    if evidence_block is None:
        return RuleVerdict(
            rule_id="CORE-011",
            category=1,
            verdict=Verdict.EVIDENCE_REQUIRED,
            severity=Severity.BLOCKING,
            reason="cargo check evidence absent for Rust diff",
        )
    verdict_claim = (evidence_block.get("verdict") or "").upper()
    ev_list = evidence_block.get("evidence") or []
    # If claim is PASS, the schema (and Cat-1 rule) requires command + exit_code + output_digest.
    if verdict_claim == "PASS":
        if not ev_list:
            return RuleVerdict(
                rule_id="CORE-011",
                category=1,
                verdict=Verdict.FAIL,
                severity=Severity.BLOCKING,
                reason="Cat-1 PASS without command evidence (rejected as self-attestation)",
            )
        for item in ev_list:
            if not isinstance(item, dict):
                return RuleVerdict(
                    rule_id="CORE-011",
                    category=1,
                    verdict=Verdict.FAIL,
                    severity=Severity.BLOCKING,
                    reason="malformed evidence array",
                )
            if not all(k in item and item[k] not in (None, "") for k in ("command", "exit_code", "output_digest")):
                return RuleVerdict(
                    rule_id="CORE-011",
                    category=1,
                    verdict=Verdict.FAIL,
                    severity=Severity.BLOCKING,
                    reason="Cat-1 PASS evidence missing command/exit_code/output_digest",
                )
            if item["exit_code"] != 0:
                return RuleVerdict(
                    rule_id="CORE-011",
                    category=1,
                    verdict=Verdict.FAIL,
                    severity=Severity.BLOCKING,
                    reason=f"cargo check exit_code={item['exit_code']}",
                )
        return RuleVerdict(
            rule_id="CORE-011",
            category=1,
            verdict=Verdict.PASS,
            severity=Severity.INFO,
        )
    # Non-PASS claims: propagate.
    if verdict_claim == "FAIL":
        return RuleVerdict(
            rule_id="CORE-011",
            category=1,
            verdict=Verdict.FAIL,
            severity=Severity.BLOCKING,
            reason=evidence_block.get("message") or "cargo check failed",
        )
    if verdict_claim == "NOT_RUN":
        return RuleVerdict(
            rule_id="CORE-011",
            category=1,
            verdict=Verdict.NOT_RUN,
            severity=Severity.INFO,
            reason=evidence_block.get("message"),
        )
    # No verdict claim — evidence absent
    return RuleVerdict(
        rule_id="CORE-011",
        category=1,
        verdict=Verdict.EVIDENCE_REQUIRED,
        severity=Severity.BLOCKING,
        reason="evidence block has no verdict",
    )
