#!/usr/bin/env python3
"""Duplicate-rule-ID guard (T-L0-RULE-IDS-001).

Scans every KB section markdown file for `### <RULE-ID>` headings. Each rule
ID (CORE-NNN / RP-PACK-NNN / GOV-NNN) must appear at most once across all
sections — duplicates indicate that a rule was copied or that namespacing has
broken.

Exit codes:
  0 — no duplicates
  1 — duplicates detected
  2 — KB directory missing
"""

from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
KB_DIR = REPO_ROOT / ".claude" / "skills" / "rdx-setup" / "assets" / "kb-sections"

_HEADING_RE = re.compile(r"^###\s+(CORE-\d{3}|RP-[A-Z]+-\d{3}|GOV-\d{3})\b", re.MULTILINE)


def main() -> int:
    if not KB_DIR.exists():
        print(f"ERROR: KB directory missing: {KB_DIR}", file=sys.stderr)
        return 2

    occurrences: dict[str, list[Path]] = defaultdict(list)
    for md_path in sorted(KB_DIR.glob("section-*.md")):
        for rule_id in _HEADING_RE.findall(md_path.read_text(encoding="utf-8")):
            occurrences[rule_id].append(md_path)

    duplicates = {rid: paths for rid, paths in occurrences.items() if len(paths) > 1}
    if duplicates:
        print("DUPLICATE rule IDs detected:", file=sys.stderr)
        for rid, paths in sorted(duplicates.items()):
            rels = ", ".join(p.relative_to(REPO_ROOT).as_posix() for p in paths)
            print(f"  {rid}: {rels}", file=sys.stderr)
        return 1

    print(f"duplicate-id-check: OK ({len(occurrences)} unique rule IDs across {len(set(p for paths in occurrences.values() for p in paths))} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
