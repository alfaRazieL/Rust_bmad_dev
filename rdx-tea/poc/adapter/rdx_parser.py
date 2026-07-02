"""Semantic RDX rule parser (Phase B of the D3 proof).

Reads the canonical RDX KB markdown files
(`.claude/skills/rdx-setup/assets/kb-sections/section-{4,6,8}-*.md`)
and returns the FULL normative body of every rule, not just IDs.

This addresses `D3_CORRECTION_AUDIT §3.2` (metadata → semantic
projection). The parser is intentionally strict — a malformed rule
block raises `RdxParseError` (fail-closed, prompt §5.2).

Public API:
  parse_all() -> list[dict]
  parse_file(path) -> list[dict]
  source_hashes() -> dict[str, str]
  RdxParseError
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Iterator

_HERE = Path(__file__).resolve().parent
RDX_TEA_DIR = _HERE.parent.parent
REPO_ROOT = RDX_TEA_DIR.parent
KB_DIR = REPO_ROOT / ".claude" / "skills" / "rdx-setup" / "assets" / "kb-sections"

# Section files parsed for rules. Section 5 (router) is data, not
# normative rule text; section 7 (recipes) is non-normative — see
# `section-4-core.md` §1 audience layers.
CANONICAL_KB_FILES = [
    KB_DIR / "section-4-core.md",
    KB_DIR / "section-6-packs.md",
    KB_DIR / "section-8-governance.md",
]


class RdxParseError(RuntimeError):
    """Raised when a rule block is missing a mandatory field or its
    header does not match the RDX rule shape."""


_HEADING_RE = re.compile(
    r"^###\s+(?P<id>(?:CORE|RP-[A-Z]+|GOV|REC-[A-Z]+)-\d{3})\s+—\s+(?P<title>.+?)\s*$"
)
_SUBSECTION_RE = re.compile(r"^##\s+\d+\.")
# Field rows always look like `- **Field:** …` on a single line, though
# `Sources:` may span multiple lines (unusual). Parser reads until the
# next `- **` or a blank line followed by another heading.
_FIELD_RE = re.compile(r"^-\s+\*\*(?P<name>[^:]+):\*\*\s*(?P<value>.*)$")

# Mapping from RP-<CODE>-nnn code to the RDX router pack id.
_PACK_CODE_TO_PACK_ID = {
    "ASYNC": "async",
    "UNSAFE": "unsafe",
    "FFI": "ffi",
    "MACRO": "macro",
    "API": "api",
    "CARGO": "cargo",
    "TEST": "testing",
    "DATA": "data-security-io",
    "SEC": "data-security-io",
    "IO": "data-security-io",
    "DB": "db",
    "TIME": "time-config-client",
    "OPS": "ops",
    "PERF": "perf",
}

_MANDATORY_FIELDS = (
    "layer", "importance", "trigger", "risk",
    "rule", "required_reasoning", "validation", "exceptions", "sources",
)


def _slug(field_name: str) -> str:
    """Normalise `**Required reasoning:**` → `required_reasoning`."""
    return field_name.strip().lower().replace(" ", "_")


def _classify_pack(rule_id: str, current_subsection_pack: str | None) -> str:
    """Return the pack id for a rule.

    * `CORE-*` and `GOV-*` and `REC-*` → 'core', 'governance', 'recipes'.
    * `RP-<CODE>-nnn` → mapped code (async, unsafe, …).
    """
    if rule_id.startswith("CORE-"):
        return "core"
    if rule_id.startswith("GOV-"):
        return "governance"
    if rule_id.startswith("REC-"):
        return "recipes"
    m = re.match(r"^RP-([A-Z]+)-\d{3}$", rule_id)
    if not m:
        raise RdxParseError(f"cannot classify pack for {rule_id}")
    code = m.group(1)
    pack = _PACK_CODE_TO_PACK_ID.get(code)
    if not pack:
        raise RdxParseError(
            f"unknown pack code {code} in {rule_id}; extend "
            "_PACK_CODE_TO_PACK_ID"
        )
    # Fallback: prefer the pack derived from the enclosing subsection,
    # if compatible.
    if current_subsection_pack and current_subsection_pack != pack:
        # Not necessarily an error — a `RP-DATA-*` rule may sit under
        # a broader "data-security-io" pack subsection. Trust the code.
        pass
    return pack


def _iter_blocks(text: str) -> Iterator[tuple[str, str, int]]:
    """Yield (rule_id, block_body, source_line_1_based) for every
    ### <RULE-ID> — <Title> block until the next ### heading."""
    lines = text.splitlines()
    i = 0
    n = len(lines)
    while i < n:
        m = _HEADING_RE.match(lines[i])
        if not m:
            i += 1
            continue
        rid = m.group("id")
        title = m.group("title")
        start = i
        i += 1
        body_start = i
        # Consume until next ### heading (or ## sub-section change,
        # since some KB files use ## as a divider between packs).
        while i < n:
            if lines[i].startswith("### "):
                break
            if lines[i].startswith("## "):
                break
            i += 1
        body = "\n".join(lines[body_start:i])
        yield rid, title, body, start + 1


def _parse_fields(body: str, rule_id: str, source_file: str, source_line: int) -> dict:
    """Parse the field bullets of a single rule block."""
    fields: dict[str, str] = {}
    lines = body.splitlines()
    i = 0
    n = len(lines)
    current_key: str | None = None
    current_value_parts: list[str] = []
    while i < n:
        line = lines[i]
        m = _FIELD_RE.match(line)
        if m:
            if current_key:
                fields[current_key] = " ".join(current_value_parts).strip()
            current_key = _slug(m.group("name"))
            current_value_parts = [m.group("value").strip()]
        elif current_key is not None:
            stripped = line.strip()
            if stripped:
                current_value_parts.append(stripped)
        i += 1
    if current_key:
        fields[current_key] = " ".join(current_value_parts).strip()
    missing = [f for f in _MANDATORY_FIELDS if f not in fields]
    if missing:
        raise RdxParseError(
            f"rule {rule_id} ({source_file}:{source_line}) missing mandatory "
            f"fields: {missing}"
        )
    for k in _MANDATORY_FIELDS:
        if not fields[k]:
            raise RdxParseError(
                f"rule {rule_id} ({source_file}:{source_line}) field {k!r} empty"
            )
    # Convert sources into a list (split on commas / semicolons; strip
    # backticks and quotes).
    raw_sources = fields["sources"]
    src_list = [s.strip(" `,;\"'") for s in re.split(r"[,;]", raw_sources) if s.strip()]
    return {
        "layer": fields["layer"],
        "importance": fields["importance"],
        "trigger": fields["trigger"],
        "risk": fields["risk"],
        "rule": fields["rule"],
        "required_reasoning": fields["required_reasoning"],
        "validation": fields["validation"],
        "exceptions": fields["exceptions"],
        "sources": src_list,
    }


def parse_file(path: Path) -> list[dict]:
    """Parse one canonical KB file. Returns a list of rules in source
    order."""
    text = path.read_text(encoding="utf-8")
    try:
        source_file = str(path.relative_to(REPO_ROOT))
    except ValueError:
        # Path is outside the repo root (e.g. a pytest tmp file).
        source_file = str(path)
    out: list[dict] = []
    for rid, title, body, line_no in _iter_blocks(text):
        fields = _parse_fields(body, rid, source_file, line_no)
        pack_id = _classify_pack(rid, None)
        entry = {
            "rule_id": rid,
            "title": title.strip(),
            "pack_id": pack_id,
            "source_file": source_file,
            "source_line": line_no,
            **fields,
        }
        out.append(entry)
    return out


def parse_all() -> list[dict]:
    """Parse every canonical KB file in `CANONICAL_KB_FILES`."""
    out: list[dict] = []
    for f in CANONICAL_KB_FILES:
        out.extend(parse_file(f))
    return out


def source_hashes() -> dict[str, str]:
    """SHA-256 of each canonical KB file, keyed by repo-relative path."""
    return {
        str(f.relative_to(REPO_ROOT)): hashlib.sha256(f.read_bytes()).hexdigest()
        for f in CANONICAL_KB_FILES
    }


if __name__ == "__main__":
    import json
    import sys
    try:
        rules = parse_all()
    except RdxParseError as err:
        print(f"parse error: {err}", file=sys.stderr)
        sys.exit(1)
    print(json.dumps({
        "count": len(rules),
        "source_hashes": source_hashes(),
        "sample_rp_async_005": next(
            (r for r in rules if r["rule_id"] == "RP-ASYNC-005"), None
        ),
    }, indent=2))
