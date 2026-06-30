"""T-DOC-HONESTY-EXTENDED-001 — Phase 10 reaffirmation of T-V5-ACC-06.

The narrow acceptance test `tests/acceptance/test_doc_honesty.py` scans
`.claude/skills/rdx-*/**.md`. Phase 10 ships user-facing documentation in
`README.md` and `docs/*.md`, which the narrow test does not cover. This
test extends the same forbidden-phrase scan to those files. It uses the
same allow-list semantics (negated forms are permitted), so the two
tests share a single canonical regex behavior.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

FORBIDDEN_PHRASES = (
    "hard enforcement",
    "enforced (mode 1)",
    "guarantees compliance",
)

_NEGATION_PATTERN = re.compile(
    r"\b(?:not|never|no|n't|without)\b[^.!?\n]{0,40}$",
    re.IGNORECASE,
)


def _iter_doc_md_files():
    readme = REPO_ROOT / "README.md"
    if readme.exists():
        yield readme
    docs_dir = REPO_ROOT / "docs"
    if docs_dir.exists():
        for md in sorted(docs_dir.rglob("*.md")):
            yield md


def _violations_in(text: str) -> list[tuple[int, str, str]]:
    out: list[tuple[int, str, str]] = []
    for n, raw in enumerate(text.splitlines(), start=1):
        line = raw.lower()
        for phrase in FORBIDDEN_PHRASES:
            idx = line.find(phrase)
            if idx == -1:
                continue
            preamble = line[:idx]
            if _NEGATION_PATTERN.search(preamble):
                continue
            out.append((n, phrase, raw.strip()))
    return out


def test_no_forbidden_phrases_in_readme_or_docs():
    files = list(_iter_doc_md_files())
    assert files, "expected README.md and/or docs/*.md to exist"
    violations: list[tuple[Path, int, str, str]] = []
    for md in files:
        for line_no, phrase, line in _violations_in(
                md.read_text(encoding="utf-8")):
            violations.append((md, line_no, phrase, line))
    assert not violations, (
        "T-DOC-HONESTY-EXTENDED-001 FAILED — forbidden phrases found:\n"
        + "\n".join(
            f"  {p.relative_to(REPO_ROOT)}:{ln}: [{phr}] {text}"
            for p, ln, phr, text in violations
        )
    )
