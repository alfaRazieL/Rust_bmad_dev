#!/usr/bin/env python3
"""D3.3.2 §11 + Wave 8 CI check helper.

Subcommands consumed by .github/workflows/rdx-tea-integration-check.yml:

    refuse-skips <junit.xml>
        Exit non-zero if the JUnit XML contains ANY <skipped> element
        whose containing classname does not appear on the design-skip
        allowlist. D3.3.2 §11.2 replaces the older --collect-only
        heuristic, which missed fixture-body pytest.skip() calls.

    unique-count <junit.xml> [<junit.xml> ...]
        Emit a JSON object with unique test node IDs across every input
        JUnit XML — not summed re-executions. Includes per-XML tallies
        so re-execution is visible if it happens.

    boundary-check <surface> [<surface> ...]        (Wave 8, G-SPLIT-IMPORT)
        Scan a shipped/distribution surface and FAIL on any hit of
        `import live_harness`, `import evals`, `live-harness/`, `evals/`,
        `evidence/` or `research/`. The production runtime must never
        import the live-harness/eval planes or reference their paths.

    auth-check <surface> [<surface> ...]            (Wave 8, G-AUTH)
        Scan a shipped/distribution surface and FAIL on any auth material
        (`ANTHROPIC_API_KEY`, `CLAUDE_CODE_OAUTH_TOKEN`, `apiKeyHelper`,
        `setup-token`, `.credentials.json`) or a `CLAUDE_CONFIG_DIR`
        override. Auth is preserved by shipping nothing that touches it.

Both surface scans are FAIL-CLOSED: a surface path that does not exist is
an ERROR (a rename must never silently pass the gate), `__pycache__` is
ignored, and undecodable (binary) files are skipped rather than crashing.

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

# --------------------------------------------------------------------------- #
# Wave 8 shipped-surface gates (G-SPLIT-IMPORT + G-AUTH).
#
# These substrings are the exact tokens enumerated by the Wave 8 acceptance
# gates. Matching is a plain substring test (case-sensitive) — the same
# semantics as the `grep -F`-style checks the gates document.
# --------------------------------------------------------------------------- #
BOUNDARY_TOKENS = (
    "import live_harness",
    "import evals",
    "live-harness/",
    "evals/",
    "evidence/",
    "research/",
)

AUTH_TOKENS = (
    "ANTHROPIC_API_KEY",
    "CLAUDE_CODE_OAUTH_TOKEN",
    "apiKeyHelper",
    "setup-token",
    ".credentials.json",
    "CLAUDE_CONFIG_DIR",
)

# Exit codes (distinct so CI logs make the failing gate obvious).
EXIT_REFUSE_SKIPS = 6
EXIT_BOUNDARY = 7
EXIT_AUTH = 8
EXIT_MISSING_SURFACE = 9


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
        return EXIT_REFUSE_SKIPS
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


# --------------------------------------------------------------------------- #
# Wave 8 shipped-surface scans (deterministic, fail-closed).
# --------------------------------------------------------------------------- #
def _surface_files(roots: list[Path]) -> list[Path]:
    """Sorted list of files under every surface root, skipping
    ``__pycache__`` (compiled artefacts are not the shipped source)."""
    files: list[Path] = []
    for root in roots:
        root = Path(root)
        if root.is_file():
            files.append(root)
        elif root.is_dir():
            for p in sorted(root.rglob("*")):
                if p.is_file() and "__pycache__" not in p.parts:
                    files.append(p)
    return sorted(files)


def _missing_surfaces(roots: list[Path]) -> list[str]:
    return sorted(str(r) for r in roots if not Path(r).exists())


def _scan_surface(roots: list[Path], tokens: tuple[str, ...]) -> list[dict]:
    hits: list[dict] = []
    for p in _surface_files(roots):
        try:
            text = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, ValueError, OSError):
            # Undecodable/binary files carry no shippable source tokens.
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            for tok in tokens:
                if tok in line:
                    hits.append({
                        "file": p.as_posix(),
                        "line": lineno,
                        "token": tok,
                        "text": line.strip()[:200],
                    })
    hits.sort(key=lambda h: (h["file"], h["line"], h["token"]))
    return hits


def _surface_scan(check: str, roots: list[Path], tokens: tuple[str, ...],
                  fail_code: int) -> int:
    missing = _missing_surfaces(roots)
    if missing:
        print(json.dumps({"check": check, "status": "ERROR",
                          "missing_surfaces": missing},
                         indent=2, sort_keys=True))
        return EXIT_MISSING_SURFACE
    hits = _scan_surface(roots, tokens)
    status = "FAIL" if hits else "PASS"
    print(json.dumps({"check": check, "status": status,
                      "surfaces": sorted(str(r) for r in roots),
                      "tokens": list(tokens), "hits": hits},
                     indent=2, sort_keys=True))
    return fail_code if hits else 0


def boundary_check(roots: list[Path]) -> int:
    """G-SPLIT-IMPORT: FAIL on any live-harness/eval boundary token."""
    return _surface_scan("boundary", roots, BOUNDARY_TOKENS, EXIT_BOUNDARY)


def auth_check(roots: list[Path]) -> int:
    """G-AUTH: FAIL on any auth material or config-dir override."""
    return _surface_scan("auth", roots, AUTH_TOKENS, EXIT_AUTH)


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("refuse-skips")
    p1.add_argument("junit", type=Path)

    p2 = sub.add_parser("unique-count")
    p2.add_argument("junits", nargs="+", type=Path)

    p3 = sub.add_parser("boundary-check")
    p3.add_argument("surfaces", nargs="+", type=Path)

    p4 = sub.add_parser("auth-check")
    p4.add_argument("surfaces", nargs="+", type=Path)

    args = ap.parse_args()
    if args.cmd == "refuse-skips":
        return refuse_skips(args.junit)
    if args.cmd == "unique-count":
        r = unique_count(args.junits)
        print(json.dumps(r, indent=2, sort_keys=True))
        return 0
    if args.cmd == "boundary-check":
        return boundary_check(args.surfaces)
    if args.cmd == "auth-check":
        return auth_check(args.surfaces)
    return 2


if __name__ == "__main__":
    sys.exit(main())
