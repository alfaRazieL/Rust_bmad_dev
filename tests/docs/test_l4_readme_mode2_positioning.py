"""T-DOC-README-MODE2-001 — Phase 10 exit-gate: Mode 2 must be positioned
as a valid release-quality option, NOT as a "stepping stone" to Mode 3.

The phrase "stepping stone" is a known anti-framing identified in the
plan ("Mode 2 (Local Gated, no-CI) should be positioned as a valid
release-quality option, NOT as a 'stepping stone' to Mode 3"). The test
allows the negated form ("not a stepping stone") because that framing
actively defends the policy.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
README = REPO_ROOT / "README.md"


def _segments_around_mode2(text: str) -> list[str]:
    """Return short windows of text around every Mode-2 mention so we
    can inspect the wording in context. ±200 chars per match."""
    matches = []
    for m in re.finditer(r"mode\s*2", text, re.IGNORECASE):
        start = max(0, m.start() - 200)
        end = min(len(text), m.end() + 200)
        matches.append(text[start:end])
    return matches


def test_readme_mentions_mode2():
    body = README.read_text(encoding="utf-8")
    assert re.search(r"mode\s*2", body, re.IGNORECASE), (
        "README must reference Mode 2 by name."
    )


def test_readme_positions_mode2_as_release_quality():
    body = README.read_text(encoding="utf-8").lower()
    assert "release-quality" in body or "release quality" in body, (
        "README must position Mode 2 as a release-quality option."
    )
    windows = " ".join(_segments_around_mode2(body))
    assert "release" in windows, (
        "the release-quality framing must appear near a Mode 2 mention."
    )


def test_readme_never_calls_mode2_a_stepping_stone():
    body = README.read_text(encoding="utf-8")
    for window in _segments_around_mode2(body):
        low = window.lower()
        idx = low.find("stepping stone")
        if idx == -1:
            continue
        preamble = low[:idx]
        negated = re.search(r"\b(?:not|never|no|n't)\b[^.!?\n]{0,40}$",
                            preamble, re.IGNORECASE)
        assert negated, (
            "README positions Mode 2 as a 'stepping stone' to Mode 3. "
            f"Forbidden by plan §Phase 10. Context:\n{window}"
        )
