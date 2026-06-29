"""CORE-014 — Test/lint suppression discipline.

T-L2-CORE014-001 — added #[ignore] on a test → EVIDENCE_REQUIRED
T-L2-CORE014-002 — removed #[test] item → FAIL
T-L2-CORE014-003 — assert!(true) tautology added → FAIL
"""

from __future__ import annotations

import re
from typing import Iterable

from ..diff import FileChange
from ..status import RuleVerdict, Severity, Verdict


_IGNORE_ATTR = re.compile(r"#\[ignore\b")
_TEST_ATTR = re.compile(r"#\[test\b")
_VACUOUS_ASSERT = re.compile(r"\bassert!\s*\(\s*true\s*\)")
_ALLOW_OK = re.compile(r"//\s*RDX-ALLOW")


def check_core_014(
    changes: Iterable[FileChange],
    authorised_exception: bool = False,
) -> RuleVerdict:
    ignore_hits: list[str] = []
    removed_tests: list[str] = []
    vacuous_hits: list[str] = []

    for change in changes:
        path = change.post_path or change.old_path or "<unknown>"
        added_text = "\n".join(change.added_lines)
        removed_text = "\n".join(change.removed_lines)

        if _IGNORE_ATTR.search(added_text):
            if not _ALLOW_OK.search(added_text):
                ignore_hits.append(path)

        if _TEST_ATTR.search(removed_text) and not _TEST_ATTR.search(added_text):
            # The #[test] attribute existed before, but not after — likely deletion.
            removed_tests.append(path)

        if _VACUOUS_ASSERT.search(added_text):
            vacuous_hits.append(path)

    if not (ignore_hits or removed_tests or vacuous_hits):
        return RuleVerdict(
            rule_id="CORE-014",
            category=1,
            verdict=Verdict.NOT_APPLICABLE,
            severity=Severity.INFO,
        )

    if removed_tests or vacuous_hits:
        # Hard suppressions: test deletion or vacuous assertion.
        if authorised_exception:
            return RuleVerdict(
                rule_id="CORE-014",
                category=1,
                verdict=Verdict.PASS,
                severity=Severity.INFO,
                reason="suppression has authorised exception",
            )
        reason_parts = []
        if removed_tests:
            reason_parts.append(f"#[test] removed in {removed_tests[0]}")
        if vacuous_hits:
            reason_parts.append(f"vacuous assertion in {vacuous_hits[0]}")
        return RuleVerdict(
            rule_id="CORE-014",
            category=1,
            verdict=Verdict.FAIL,
            severity=Severity.BLOCKING,
            reason="; ".join(reason_parts),
        )

    # Only #[ignore] additions: EVIDENCE_REQUIRED (soft block) — Mode 2+ → exit 3.
    if authorised_exception:
        return RuleVerdict(
            rule_id="CORE-014",
            category=1,
            verdict=Verdict.PASS,
            severity=Severity.INFO,
            reason="#[ignore] addition has authorised exception",
        )
    return RuleVerdict(
        rule_id="CORE-014",
        category=1,
        verdict=Verdict.EVIDENCE_REQUIRED,
        severity=Severity.BLOCKING,
        reason=f"#[ignore] added to test in {ignore_hits[0]}",
    )
