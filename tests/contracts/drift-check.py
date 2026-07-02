#!/usr/bin/env python3
"""KB ↔ mapping drift checker (T-L0-DRIFT-001 + T-L0-DRIFT-002).

Two modes:

  --mode router : assert that the set of packs declared in KB §5 (the router
                  table) and the set of pack keys in router-rules.json are
                  bijective. Pack label matching is canonicalised to a lower-
                  case slug-ish form so "Async and concurrency" matches "async".
  --mode rules  : assert that every rule ID referenced in rule-check-map.json
                  exists as a heading in the KB sections.

Exit codes
----------
  0  : drift checks pass
  1  : drift detected (details printed to stderr)
  2  : invocation error (missing files, bad mode, etc.)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
KB_DIR = REPO_ROOT / ".claude" / "skills" / "rdx-setup" / "assets" / "kb-sections"
CONTRACTS_DIR = REPO_ROOT / "tests" / "contracts"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _parse_kb_router_packs(section_text: str) -> list[str]:
    """Return canonical pack labels from KB §5 markdown table — first column.

    Drops the header row ("Pack") and the alignment row (`|---|...`).
    """
    labels: list[str] = []
    for line in section_text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        # alignment row
        if set(stripped.replace("|", "").replace(":", "").strip()) <= {"-", " "}:
            continue
        first_cell = stripped.split("|")[1].strip()
        if not first_cell or first_cell.lower() == "pack":
            continue
        labels.append(first_cell)
    return labels


def _canonical_label_to_slug(label: str) -> str:
    """Normalise a human KB label to the slug used in router-rules.json keys.

    Examples
    --------
      "Async and concurrency"                          -> "async"
      "Unsafe and memory"                              -> "unsafe"
      "FFI and plugin ABI"                             -> "ffi"
      "Macros, build scripts, and generated code"      -> "macro"
      "Public API, SemVer, and documentation"          -> "api"
      "Cargo, features, workspace, toolchain, ..."     -> "cargo"
      "Testing beyond the core loop"                   -> "testing"
      "Data, security, and external I/O"               -> "data-security-io"
      "Database, messaging, and distributed state"     -> "db"
      "Time, configuration, and API clients"           -> "time-config-client"
      "Operations, observability, and rollback"        -> "ops"
      "Performance, portability, no_std, WASM, ..."    -> "perf"

    The canonicalisation is intentionally a hand-rolled lookup keyed on a
    normalised prefix; that keeps the mapping explicit and easy to audit.
    """
    normalised = label.strip().lower()
    table: list[tuple[str, str]] = [
        ("async and concurrency", "async"),
        ("unsafe and memory", "unsafe"),
        ("ffi and plugin abi", "ffi"),
        ("macros, build scripts", "macro"),
        ("public api, semver", "api"),
        ("cargo, features, workspace", "cargo"),
        ("testing beyond the core loop", "testing"),
        ("data, security, and external i/o", "data-security-io"),
        ("database, messaging, and distributed state", "db"),
        ("time, configuration, and api clients", "time-config-client"),
        ("operations, observability, and rollback", "ops"),
        ("performance, portability", "perf"),
    ]
    for prefix, slug in table:
        if normalised.startswith(prefix):
            return slug
    # Fall back to a generic slug if KB grows: lowercase, non-alnum -> '-'
    fallback = re.sub(r"[^a-z0-9]+", "-", normalised).strip("-")
    return fallback


def check_router_drift() -> int:
    kb_path = KB_DIR / "section-5-router.md"
    rules_path = CONTRACTS_DIR / "router-rules.json"
    if not kb_path.exists():
        print(f"ERROR: KB section missing: {kb_path}", file=sys.stderr)
        return 2
    if not rules_path.exists():
        print(f"ERROR: router-rules.json missing: {rules_path}", file=sys.stderr)
        return 2

    kb_labels = _parse_kb_router_packs(_read(kb_path))
    kb_slugs = {_canonical_label_to_slug(label) for label in kb_labels}
    rules = json.loads(_read(rules_path))
    json_slugs = set(rules.get("packs", {}).keys())

    missing_in_json = sorted(kb_slugs - json_slugs)
    missing_in_kb = sorted(json_slugs - kb_slugs)

    if missing_in_json or missing_in_kb:
        print("DRIFT DETECTED between KB §5 and router-rules.json", file=sys.stderr)
        if missing_in_json:
            print(f"  packs in KB but absent from router-rules.json: {missing_in_json}", file=sys.stderr)
        if missing_in_kb:
            print(f"  packs in router-rules.json but absent from KB:    {missing_in_kb}", file=sys.stderr)
        return 1

    print(f"router drift: OK ({len(kb_slugs)} packs match bijectively)")
    return 0


_RULE_HEADING_RE = re.compile(r"^###\s+(CORE-\d{3}|RP-[A-Z]+-\d{3}|GOV-\d{3})\b", re.MULTILINE)


def _collect_kb_rule_ids() -> set[str]:
    ids: set[str] = set()
    for md_path in sorted(KB_DIR.glob("section-*.md")):
        ids.update(_RULE_HEADING_RE.findall(_read(md_path)))
    return ids


def check_rule_drift() -> int:
    map_path = CONTRACTS_DIR / "rule-check-map.json"
    if not map_path.exists():
        print(f"ERROR: rule-check-map.json missing: {map_path}", file=sys.stderr)
        return 2

    kb_ids = _collect_kb_rule_ids()
    rule_map = json.loads(_read(map_path)).get("rules", {})
    map_ids = set(rule_map.keys())

    unknown = sorted(map_ids - kb_ids)
    if unknown:
        print("DRIFT DETECTED — rule-check-map.json references IDs not in KB:", file=sys.stderr)
        for unk in unknown:
            print(f"  {unk}", file=sys.stderr)
        return 1

    # Information only: rules in KB without an entry in the mapping. Not an error
    # — Phase 1 may cover a subset of rules, and later phases extend the map.
    uncovered = sorted(kb_ids - map_ids)
    print(
        f"rule drift: OK (mapping references {len(map_ids)} IDs, all present in KB; "
        f"{len(uncovered)} additional KB rules await mapping in later phases)"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["router", "rules", "all"], default="all")
    args = parser.parse_args(argv)
    if args.mode in ("router", "all"):
        rc = check_router_drift()
        if rc != 0:
            return rc
    if args.mode in ("rules", "all"):
        rc = check_rule_drift()
        if rc != 0:
            return rc
    return 0


if __name__ == "__main__":
    sys.exit(main())
