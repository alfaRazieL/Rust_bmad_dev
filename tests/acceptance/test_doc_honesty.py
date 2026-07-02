"""T-V5-ACC-06 — Documentation does not call the wrapper / Modes 0-1 'hard
enforcement'.

From RDX_TEST_CASES.yaml::T-V5-ACC-06:
    Grep all .md files under .claude/skills/rdx-* for forbidden phrases:
      'hard enforcement', 'enforced (Mode 1)', 'guarantees compliance'
    Assert: no occurrences in wrapper / Mode-1 sections.

The forbidden phrase set is what's listed in the YAML test case. We allow
*negated* uses ('NOT hard enforcement', 'is not enforced', 'does not
guarantee compliance') because those are the right framing — they tell the
reader the wrapper is cooperative, not coercive.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
RDX_SKILLS_DIR = REPO_ROOT / ".claude" / "skills"

# Each forbidden phrase is paired with a regex that excludes the negated form.
# A line containing "is NOT hard enforcement" or "this is not a hard-enforcement
# claim" is permitted; the standalone assertion "hard enforcement" is not.
FORBIDDEN_PHRASES = (
    "hard enforcement",
    "enforced (mode 1)",
    "guarantees compliance",
)

# Pattern to detect explicit negation right before the phrase. Matches
# common forms: "not", "n't", "isn't", "is not", "does not", "no", etc.
_NEGATION_PATTERN = re.compile(
    r"\b(?:not|never|no|n't|without)\b[^.!?\n]{0,40}$",
    re.IGNORECASE,
)


def _iter_rdx_md_files():
    for skill_dir in sorted(RDX_SKILLS_DIR.glob("rdx-*")):
        if not skill_dir.is_dir():
            continue
        for md in skill_dir.rglob("*.md"):
            yield md


def _violations_in(text: str) -> list[tuple[int, str, str]]:
    """Return (line_number, phrase, line_text) tuples for offending lines."""
    out: list[tuple[int, str, str]] = []
    for n, raw in enumerate(text.splitlines(), start=1):
        line = raw.lower()
        for phrase in FORBIDDEN_PHRASES:
            idx = line.find(phrase)
            if idx == -1:
                continue
            preamble = line[:idx]
            if _NEGATION_PATTERN.search(preamble):
                # Negated form — that's the *correct* framing and is permitted.
                continue
            out.append((n, phrase, raw.strip()))
    return out


def test_t_v5_acc_06_no_forbidden_phrases_in_rdx_skill_docs():
    """T-V5-ACC-06 — grep .claude/skills/rdx-* SKILL.md / .md for forbidden
    phrases describing the wrapper or Mode 0/1 as enforcement."""
    assert RDX_SKILLS_DIR.exists(), f"missing .claude/skills at {RDX_SKILLS_DIR}"
    all_violations: list[tuple[Path, int, str, str]] = []
    files_scanned = 0
    for md in _iter_rdx_md_files():
        files_scanned += 1
        for line_no, phrase, line in _violations_in(md.read_text(encoding="utf-8")):
            all_violations.append((md, line_no, phrase, line))
    assert files_scanned > 0, "T-V5-ACC-06: no SKILL.md files were scanned"
    assert not all_violations, (
        "T-V5-ACC-06 FAILED — forbidden enforcement phrases found:\n"
        + "\n".join(
            f"  {path.relative_to(REPO_ROOT)}:{ln}: [{phr}] {text}"
            for path, ln, phr, text in all_violations
        )
    )


def test_negated_phrase_allowed_smoke():
    """Sanity: the violation detector treats negated forms as allowed."""
    safe_text = (
        "The wrapper is NOT hard enforcement.\n"
        "This does not guarantee compliance with anything.\n"
    )
    assert _violations_in(safe_text) == []


def test_naked_phrase_caught_smoke():
    """Sanity: the violation detector flags a standalone forbidden phrase."""
    bad_text = "RDX is a hard enforcement system across all modes.\n"
    violations = _violations_in(bad_text)
    assert len(violations) == 1
    assert violations[0][1] == "hard enforcement"
