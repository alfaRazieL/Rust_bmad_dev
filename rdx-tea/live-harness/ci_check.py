#!/usr/bin/env python3
"""D3.3.2 §11 CI check helper.

Two subcommands consumed by .github/workflows/rdx-tea-integration-check.yml:

    refuse-skips <junit.xml>
        Exit non-zero if the JUnit XML contains ANY <skipped> element
        whose containing classname does not appear on the design-skip
        allowlist. D3.3.2 §11.2 replaces the older --collect-only
        heuristic, which missed fixture-body pytest.skip() calls.

    unique-count <junit.xml> [<junit.xml> ...]
        Emit a JSON object with unique test node IDs across every input
        JUnit XML — not summed re-executions. Includes per-XML tallies
        so re-execution is visible if it happens.

Design-skip allowlist lives in a small, versioned file next to this
script (`ci_check_allowlist.txt`) so a reviewer can see exactly which
skips are considered admissible.
"""

from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
ALLOWLIST_PATH = HERE / "ci_check_allowlist.txt"


def _read_allowlist() -> set[str]:
    if not ALLOWLIST_PATH.exists():
        return set()
    return {
        line.strip()
        for line in ALLOWLIST_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    }


def _iter_testcases(paths: list[Path]):
    for p in paths:
        tree = ET.parse(p)
        for tc in tree.iter("testcase"):
            yield p, tc


def refuse_skips(junit_path: Path) -> int:
    allowlist = _read_allowlist()
    bad: list[dict] = []
    for _, tc in _iter_testcases([junit_path]):
        sk = tc.find("skipped")
        if sk is None:
            continue
        cls = tc.get("classname") or ""
        nm = tc.get("name") or ""
        node = f"{cls}::{nm}"
        # Allowlist checks BOTH exact node ID and classname prefix.
        allowed = (
            node in allowlist
            or any(cls.startswith(a.rstrip("*")) for a in allowlist
                    if a.endswith("*"))
        )
        if not allowed:
            bad.append({
                "class": cls, "name": nm,
                "reason": (sk.get("message") or "")[:200],
            })
    if bad:
        print(json.dumps({"status": "FAIL", "unauthorised_skips": bad},
                          indent=2, sort_keys=True))
        return 6
    print(json.dumps({"status": "PASS", "unauthorised_skips": []},
                      indent=2, sort_keys=True))
    return 0


def unique_count(paths: list[Path]) -> dict:
    per_file: dict[str, dict[str, int]] = {}
    passed_ids: set[str] = set()
    failed_ids: set[str] = set()
    skipped_ids: set[str] = set()
    collected_ids: set[str] = set()
    for p in paths:
        p_passed = p_failed = p_skipped = 0
        for _, tc in _iter_testcases([p]):
            node = f"{tc.get('classname')}::{tc.get('name')}"
            collected_ids.add(node)
            if tc.find("skipped") is not None:
                skipped_ids.add(node)
                p_skipped += 1
            elif tc.find("failure") is not None or tc.find("error") is not None:
                failed_ids.add(node)
                p_failed += 1
            else:
                passed_ids.add(node)
                p_passed += 1
        per_file[str(p)] = {"passed": p_passed, "failed": p_failed,
                              "skipped": p_skipped, "total": p_passed + p_failed + p_skipped}
    reexecutions = sum(v["total"] for v in per_file.values()) - len(collected_ids)
    return {
        "unique_collected": len(collected_ids),
        "unique_passed": len(passed_ids - failed_ids - skipped_ids),
        "unique_failed": len(failed_ids),
        "unique_skipped": len(skipped_ids - failed_ids - passed_ids),
        "reexecutions": reexecutions,
        "per_file": per_file,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("refuse-skips")
    p1.add_argument("junit", type=Path)

    p2 = sub.add_parser("unique-count")
    p2.add_argument("junits", nargs="+", type=Path)

    args = ap.parse_args()
    if args.cmd == "refuse-skips":
        return refuse_skips(args.junit)
    if args.cmd == "unique-count":
        r = unique_count(args.junits)
        print(json.dumps(r, indent=2, sort_keys=True))
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
