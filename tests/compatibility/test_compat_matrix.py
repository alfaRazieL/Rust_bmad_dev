"""Phase 6 §6.4 exit gate — Compatibility matrix shape.

RDX_IMPLEMENTATION_PLAN_TESTED.md §6 exit gate row:
  "Compatibility matrix passes for Python 3.11/3.12/3.13 × Ubuntu/macOS"

This test verifies the canonical compatibility manifest lives at
tests/compatibility/matrix.md (closing the "to be authored Phase 6"
note in README.md) and declares the required OS × Python combinations.
The actual matrix RUN happens in .github/workflows/rdx-compat-matrix.yml.
"""

from __future__ import annotations

import json
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MATRIX_MD = REPO_ROOT / "tests" / "compatibility" / "matrix.md"

# Required (OS, Python) pairs per the §6 exit gate.
REQUIRED_PAIRS: list[tuple[str, str]] = [
    ("ubuntu-latest", "3.11"),
    ("ubuntu-latest", "3.12"),
    ("ubuntu-latest", "3.13"),
    ("macos-latest",  "3.11"),
    ("macos-latest",  "3.12"),
    ("macos-latest",  "3.13"),
]


def _load_machine_block() -> dict:
    text = MATRIX_MD.read_text(encoding="utf-8")
    m = re.search(
        r"<!-- machine-readable-block-begin -->\s*```json\s*(\{.*?\})\s*```\s*<!-- machine-readable-block-end -->",
        text,
        re.DOTALL,
    )
    assert m, "matrix.md must contain a fenced JSON block between the marker comments"
    return json.loads(m.group(1))


def test_matrix_md_exists() -> None:
    assert MATRIX_MD.exists(), (
        "tests/compatibility/matrix.md is the Phase 6 §6.4 deliverable "
        "promised by tests/compatibility/README.md"
    )


def test_matrix_declares_v5_minimums() -> None:
    data = _load_machine_block()
    mins = data["minimums"]
    assert mins["python"] == "3.11"
    assert mins["git"] == "2.30"
    assert mins["rust"] == "stable"
    assert "bmad" in mins


def test_matrix_covers_required_os_python_pairs() -> None:
    data = _load_machine_block()
    have = {(row["os"], row["python"]) for row in data["rows"]}
    missing = set(REQUIRED_PAIRS) - have
    assert not missing, f"matrix missing required (OS, Python) pairs: {missing}"


def test_matrix_unsupported_list_excludes_python_310_and_below() -> None:
    data = _load_machine_block()
    unsupported = " ".join(data["unsupported"])
    assert "python<3.11" in unsupported, (
        "matrix.md must explicitly mark Python <3.11 as unsupported "
        "(README.md V5 minimums)"
    )


def test_matrix_at_least_one_row_runs_full_l0_through_l7() -> None:
    """Per §6.4 the V5 release gate requires *some* row to run the full
    L0-L7 superset so we know the cross-layer interactions actually
    execute on a real OS, not just per-layer in isolation."""
    data = _load_machine_block()
    required_gates = {"L0", "L1", "L2", "L3", "L4", "L6", "L7"}
    has_full = any(set(row["gates"]).issuperset(required_gates) for row in data["rows"])
    assert has_full, (
        "no compatibility row runs the full L0..L7 superset; "
        "the CI gate must keep one row carrying the whole stack"
    )
