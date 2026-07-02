"""CORE-008 — Panic discipline.

T-L2-CORE008-001 — new .unwrap() in prod code → WARNING (PASS verdict)
T-L2-CORE008-002 — new .unwrap() WITH story tag 'panic-discipline' → FAIL
T-L2-CORE008-003 — .unwrap() inside #[cfg(test)] → NOT_APPLICABLE
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from ..diff import FileChange
from ..status import RuleVerdict, Severity, Verdict


_UNWRAP_PATTERN = re.compile(r"\.(unwrap|expect)\s*\(")
_PANIC_PATTERN = re.compile(r"\bpanic!\s*\(")
_TEST_CFG_PATTERN = re.compile(r"#\[cfg\(test\)\]")


@dataclass
class _FileHits:
    path: str
    in_test_only: bool
    hit_count: int


def _file_added_block(change: FileChange) -> str:
    return "\n".join(change.added_lines)


def _scan_change(change: FileChange) -> _FileHits | None:
    path = change.post_path
    if path is None:
        return None
    if not path.endswith(".rs"):
        return None
    text = _file_added_block(change)
    if not text:
        return None
    unwrap_hits = list(_UNWRAP_PATTERN.finditer(text))
    panic_hits = list(_PANIC_PATTERN.finditer(text))
    hits = unwrap_hits + panic_hits
    if not hits:
        return None
    # If the new code is inside a #[cfg(test)] block (added in the same diff),
    # treat as test code. A simple heuristic: any added #[cfg(test)] in the
    # same file marker.
    in_test_only = bool(_TEST_CFG_PATTERN.search(text)) or path.startswith("tests/") or "/tests/" in path
    return _FileHits(path=path, in_test_only=in_test_only, hit_count=len(hits))


def check_core_008(
    changes: Iterable[FileChange],
    story_tags: Iterable[str],
) -> RuleVerdict:
    hits: list[_FileHits] = []
    for c in changes:
        h = _scan_change(c)
        if h is not None:
            hits.append(h)
    prod_hits = [h for h in hits if not h.in_test_only]

    if not hits:
        return RuleVerdict(
            rule_id="CORE-008",
            category=2,
            verdict=Verdict.NOT_APPLICABLE,
            severity=Severity.INFO,
        )
    if not prod_hits:
        return RuleVerdict(
            rule_id="CORE-008",
            category=2,
            verdict=Verdict.NOT_APPLICABLE,
            severity=Severity.INFO,
            reason="unwrap/panic confined to test code",
        )
    has_tag = "panic-discipline" in set(story_tags)
    if has_tag:
        return RuleVerdict(
            rule_id="CORE-008",
            category=2,
            verdict=Verdict.FAIL,
            severity=Severity.BLOCKING,
            reason=f"unwrap/panic in production with panic-discipline tag: {prod_hits[0].path}",
        )
    return RuleVerdict(
        rule_id="CORE-008",
        category=2,
        verdict=Verdict.PASS,
        severity=Severity.WARNING,
        reason=f"unwrap/panic found in production: {prod_hits[0].path}",
    )
