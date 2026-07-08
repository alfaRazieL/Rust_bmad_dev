"""L0 production/eval boundary contract (Wave 1 · G-W1-BOUNDARY · G-SPLIT-IMPORT).

The shipped surface — everything that the installer copies into a user
project — MUST be self-contained. It must never import the eval-only
`live-harness`/`evals` modules, and it must never reference a path under
`live-harness/`, `evals/`, or `evidence/`. Those directories do not ship
into a user project, so any such reference is either dead (best case) or a
runtime break (worst case), and it silently couples production to the
research plane.

This test is the executable form of the `G-SPLIT-IMPORT` acceptance-gate
grep:

    grep -rE "import (live_harness|evals)|live-harness/|evals/|evidence/" \
        rdx-tea/poc/install-tree rdx-tea/installer

It scans the shipped surface (the install-tree today; the installer tree
once Wave 7 adds it) and fails closed on any hit. `test_..._detector_...`
proves the detector actually fires on a known-bad sample, so a future
regression that reintroduces a reference cannot pass silently.

Boundary invariant (PRODUCTION_EVAL_SPLIT.md §5):

    PRODUCTION (install-tree + installer + wrapper Skills)
        MUST NOT import  live-harness/*  or  evals/*
        MUST NOT reference any path under  evidence/  evals/  live-harness/
    EVAL / HISTORICAL
        MAY read production runtime (to exercise/grade it)

Knowledge-plane only — no enforcement-plane assertions here
(project rule `feedback_rdx_tea_knowledge_first`).
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

RDX_TEA_DIR = Path(__file__).resolve().parent.parent.parent   # rdx-tea/

# The shipped surface. `installer/` does not exist yet (Wave 7); it is
# included here so the boundary is enforced automatically the moment it
# lands, with no test edit required.
SHIPPED_ROOTS = [
    RDX_TEA_DIR / "poc" / "install-tree",
    RDX_TEA_DIR / "installer",
]

# Text file extensions that make up the shipped surface. Compiled
# artefacts (`.pyc`) and `__pycache__/` are never shipped (gitignored)
# and are skipped. A file with no suffix (e.g. `VERSION`) is scanned.
TEXT_SUFFIXES = {
    ".py", ".md", ".json", ".lock", ".toml", ".yaml", ".yml", ".sh",
    ".txt", ".cfg", ".ini", "",
}

# Verbatim G-SPLIT-IMPORT patterns. Import forms + forbidden path
# literals. `live-harness/` is added to the path literals because that
# eval directory must not be referenced either (PRODUCTION_EVAL_SPLIT §5).
IMPORT_PATTERN = re.compile(r"\bimport\s+(live_harness|evals)\b"
                            r"|\bfrom\s+(live_harness|evals)\b")
PATH_PATTERNS = {
    "live-harness/": re.compile(r"live-harness/"),
    "evals/":        re.compile(r"\bevals/"),
    "evidence/":     re.compile(r"\bevidence/"),
}


def _iter_shipped_files():
    for root in SHIPPED_ROOTS:
        if not root.exists():
            continue
        for p in sorted(root.rglob("*")):
            if not p.is_file():
                continue
            if "__pycache__" in p.parts:
                continue
            if p.suffix not in TEXT_SUFFIXES:
                continue
            yield p


def find_violations(text: str) -> list[tuple[str, str, int]]:
    """Return (kind, matched-text, 1-based-line) for every boundary hit."""
    hits: list[tuple[str, str, int]] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        m = IMPORT_PATTERN.search(line)
        if m:
            hits.append(("import", m.group(0), lineno))
        for label, pat in PATH_PATTERNS.items():
            if pat.search(line):
                hits.append(("path", label, lineno))
    return hits


def test_shipped_surface_has_files_to_check():
    """Guard: the scan must actually find the install-tree, else a path
    typo would make the boundary test vacuously green."""
    files = list(_iter_shipped_files())
    assert files, "shipped-surface scan found no files — check SHIPPED_ROOTS"
    # sanity: the runtime scripts must be in the scanned set
    names = {p.name for p in files}
    assert "prepare.py" in names and "rdx_tea_wrapper.py" in names


def test_boundary_no_eval_or_evidence_references():
    """G-W1-BOUNDARY / G-SPLIT-IMPORT: zero references across the surface."""
    offences: list[str] = []
    for p in _iter_shipped_files():
        text = p.read_text(encoding="utf-8", errors="strict")
        for kind, matched, lineno in find_violations(text):
            rel = p.relative_to(RDX_TEA_DIR)
            offences.append(f"{rel}:{lineno}: [{kind}] {matched!r}")
    assert not offences, (
        "shipped surface references eval/evidence plane (boundary violation):\n"
        + "\n".join(offences)
    )


def test_boundary_no_python_imports_of_eval_modules():
    """AST-level: no shipped .py imports the live_harness/evals modules,
    even via aliased or dotted forms the regex might miss."""
    forbidden = {"live_harness", "evals"}
    offences: list[str] = []
    for p in _iter_shipped_files():
        if p.suffix != ".py":
            continue
        tree = ast.parse(p.read_text(encoding="utf-8"), filename=str(p))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] in forbidden:
                        offences.append(f"{p.name}: import {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                mod = (node.module or "").split(".")[0]
                if mod in forbidden:
                    offences.append(f"{p.name}: from {node.module} import ...")
    assert not offences, "shipped .py imports eval modules:\n" + "\n".join(offences)


@pytest.mark.parametrize("bad", [
    "import live_harness",
    "from live_harness.run_live import main",
    "import evals",
    "from evals import run_pilot",
    "path = 'rdx-tea/live-harness/fixtures/x.json'",
    "open('rdx-tea/evals/runs/schedule.json')",
    "REPORT = 'rdx-tea/evidence/final/D3_FINAL_VERIFICATION.json'",
])
def test_boundary_detector_flags_known_violations(bad):
    """RED-side proof: the detector must catch every known-bad form, so a
    reintroduced reference cannot slip past this test silently."""
    assert find_violations(bad), f"detector failed to flag: {bad!r}"


def test_boundary_detector_ignores_clean_lines():
    """The detector must not false-positive on legitimate content."""
    clean = [
        "import prepare",
        "from obligation_matrix import matrix_for",
        "# reads only the canonical KB under _bmad/rdx-tea/canonical/",
        "rdx_source_sha: 'd8140a25f8166bf0ca5ce5fc19f7cb1bd06a3d6d'",
    ]
    for line in clean:
        assert not find_violations(line), f"false positive on: {line!r}"
