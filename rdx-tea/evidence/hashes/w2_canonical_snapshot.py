#!/usr/bin/env python3
"""W2 canonical snapshot hash pin harness (G-W2-CANON).

Recomputes the RDX canonical snapshot hash that the PRODUCTION
`prepare.prepare()` stamps into every `run-manifest.json` as
`rdx_canonical_snapshot_sha256`, and compares it to the pinned value in
`w2_canonical_snapshot.txt`.

The hash is `prepare._canonical_snapshot_hash()`: sha256 over a sorted
`"<name> <sha256(file)>"` manifest of the canonical KB files
(router-rules.json, status-definitions.json, rule-check-map.json,
authority-matrix.json, section-4-core.md, section-6-packs.md,
section-8-governance.md) under the install-tree `canonical/`.

Deterministic: no wallclock, no randomness, sorted iteration inside the
generator. Any canonical/ change moves this hash and REQUIRES a
source-lock re-pin + a SOURCE_LOCK addendum before re-pinning here.

Usage:
    python rdx-tea/evidence/hashes/w2_canonical_snapshot.py            # verify
    python rdx-tea/evidence/hashes/w2_canonical_snapshot.py --print    # just print
    python rdx-tea/evidence/hashes/w2_canonical_snapshot.py --write    # re-pin
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve()
RDX_TEA_DIR = HERE.parent.parent.parent  # rdx-tea/
INSTALL_SCRIPTS = (
    RDX_TEA_DIR / "poc" / "install-tree" / "_bmad" / "rdx-tea" / "scripts"
)
PIN_FILE = HERE.parent / "w2_canonical_snapshot.txt"

sys.path.insert(0, str(INSTALL_SCRIPTS))
# Fresh resolution → install-tree canonical (the shipped source of truth).
for _m in ("rdx_parser", "prepare"):
    sys.modules.pop(_m, None)
import prepare as prepare_mod  # noqa: E402


def compute() -> str:
    return prepare_mod._canonical_snapshot_hash()


def read_pin() -> str | None:
    if not PIN_FILE.exists():
        return None
    import re
    m = re.search(r"\b([0-9a-f]{64})\b", PIN_FILE.read_text(encoding="utf-8"))
    return m.group(1) if m else None


def render_pin(sha: str) -> str:
    return (
        "# W2 canonical snapshot hash pin (G-W2-CANON)\n"
        "#\n"
        "# sha256 over a sorted `<name> <sha256(file)>` manifest of the\n"
        "# install-tree canonical KB files, as computed by the PRODUCTION\n"
        "# prepare._canonical_snapshot_hash() and stamped into every\n"
        "# run-manifest.json as rdx_canonical_snapshot_sha256.\n"
        "#\n"
        "# Canonical files hashed (under poc/install-tree/_bmad/rdx-tea/canonical/):\n"
        "#   router-rules.json, status-definitions.json, rule-check-map.json,\n"
        "#   authority-matrix.json, kb-sections/section-4-core.md,\n"
        "#   kb-sections/section-6-packs.md, kb-sections/section-8-governance.md\n"
        "#\n"
        "# Deterministic (sorted, no wallclock/random). Any canonical/ change\n"
        "# moves this hash and REQUIRES a source-lock re-pin + SOURCE_LOCK\n"
        "# addendum before re-pinning. Verify: w2_canonical_snapshot.py.\n"
        f"{sha}  canonical-snapshot\n"
    )


def main(argv: list[str]) -> int:
    sha = compute()
    if "--print" in argv:
        print(sha)
        return 0
    if "--write" in argv:
        PIN_FILE.write_text(render_pin(sha), encoding="utf-8")
        print(f"pinned {sha} -> {PIN_FILE.name}")
        return 0
    pinned = read_pin()
    if pinned is None:
        print(f"NO PIN present at {PIN_FILE.name}; computed={sha}", file=sys.stderr)
        return 2
    if pinned != sha:
        print(f"DRIFT: computed={sha} != pinned={pinned}", file=sys.stderr)
        return 1
    print(f"OK canonical snapshot {sha} matches pin")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
