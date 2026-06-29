"""Minimal SKILL.md front-matter + section extractor.

Used by wrapper-resume L4 static tests to assert that
`.claude/skills/rdx-dev-story/SKILL.md` declares all the safeguards
required by T-L4-WR-001..006 (BEFORE/AFTER ordering, recursion guard,
missing-artifact check, validator halt sentinel, risk-tag preservation,
child invocation step).

Static parsing is sufficient for Phase 3's deterministic exit gate; the
runtime LLM-cooperative confirmation is covered separately by L5 evals
in Phase 6 (≥85% over 20 runs per the plan).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import NamedTuple


class ParsedSkill(NamedTuple):
    name: str
    description: str
    body: str
    headings: list[str]


_FRONT_MATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
_HEADING_RE = re.compile(r"^#{1,6}\s+(.+)$", re.MULTILINE)


def parse(path: Path) -> ParsedSkill:
    text = path.read_text(encoding="utf-8")
    m = _FRONT_MATTER_RE.match(text)
    if not m:
        raise ValueError(f"{path}: missing YAML front-matter")
    fm_block = m.group(1)
    body = text[m.end():]

    name = ""
    description = ""
    for line in fm_block.splitlines():
        if line.startswith("name:"):
            name = line.split(":", 1)[1].strip()
        elif line.startswith("description:"):
            description = line.split(":", 1)[1].strip()

    headings = _HEADING_RE.findall(body)
    return ParsedSkill(name=name, description=description, body=body, headings=headings)


def contains_any(haystack: str, needles: list[str]) -> bool:
    return any(n in haystack for n in needles)
