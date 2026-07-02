"""CORE-007 — Protected files boundary.

T-L2-CORE007-001 — diff modifies protected file → FAIL
T-L2-CORE007-002 — protected file touched WITH authorization in evidence → PASS
T-L2-CORE007-003 — empty protected_files in story → NOT_APPLICABLE
"""

from __future__ import annotations

import fnmatch
from typing import Iterable

from ..status import RuleVerdict, Severity, Verdict


def _matches_any(globs: Iterable[str], path: str) -> bool:
    for g in globs:
        if fnmatch.fnmatch(path, g):
            return True
        if g.endswith("/**") and (path == g[:-3] or path.startswith(g[:-2])):
            return True
        if g.startswith("**/") and fnmatch.fnmatch(path, g[3:]):
            return True
    return False


def check_core_007(
    paths_changed: Iterable[str],
    protected_files: Iterable[str],
    authorised_exception: bool,
) -> RuleVerdict:
    protected = list(protected_files)
    if not protected:
        return RuleVerdict(
            rule_id="CORE-007",
            category=1,
            verdict=Verdict.NOT_APPLICABLE,
            severity=Severity.INFO,
        )
    hits = [p for p in paths_changed if _matches_any(protected, p)]
    if not hits:
        return RuleVerdict(
            rule_id="CORE-007",
            category=1,
            verdict=Verdict.PASS,
            severity=Severity.INFO,
        )
    if authorised_exception:
        return RuleVerdict(
            rule_id="CORE-007",
            category=1,
            verdict=Verdict.PASS,
            severity=Severity.INFO,
            reason="authorised exception in evidence",
        )
    return RuleVerdict(
        rule_id="CORE-007",
        category=1,
        verdict=Verdict.FAIL,
        severity=Severity.BLOCKING,
        reason=f"protected files touched: {', '.join(hits)}",
    )
