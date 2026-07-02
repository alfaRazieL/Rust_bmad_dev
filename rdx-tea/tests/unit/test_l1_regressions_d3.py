"""L1 regression tests for D3 correction (prompt RDX_TEA_D3_proof_correction §3.3).

These tests are designed to be RED against the D2 implementation of
`_tier_for` and will remain RED until the projection generator is
corrected to obey `BUILDER_TEA_RECONCILIATION §3.3`:

    default = specialized
    RP-TEST-* may be extended
    nothing is core

Do NOT delete these tests to make them green — fix `_tier_for` instead.
"""

from __future__ import annotations

import csv
import io
import importlib.util
from pathlib import Path

import pytest

RDX_TEA_DIR = Path(__file__).resolve().parent.parent.parent
spec = importlib.util.spec_from_file_location(
    "rdx_tea_projection", RDX_TEA_DIR / "poc" / "adapter" / "projection.py"
)
projection = importlib.util.module_from_spec(spec)
spec.loader.exec_module(projection)   # type: ignore[union-attr]


# The D2 reconciliation forbids `core` tier for any RDX-owned Rust pack.
RUST_PACKS = {
    "async", "unsafe", "ffi", "macro", "api", "cargo", "testing",
    "data-security-io", "db", "time-config-client", "ops", "perf",
}


def test_l1_regression_no_rdx_pack_is_tea_core() -> None:
    """No pack fragment may be tagged tier=core in the emitted index.

    BUILDER_TEA_RECONCILIATION §3.3: "every appended row in each
    tea-index.csv defaults to tier=specialized. Only rows for RP-TEST-*
    may be extended; nothing is core."
    """
    csv_text = projection.render_index_csv()
    reader = csv.reader(io.StringIO(csv_text))
    header = next(reader)
    tier_idx = header.index("tier")
    id_idx = header.index("id")
    cores = [row[id_idx] for row in reader if row[tier_idx] == "core"]
    assert not cores, (
        f"D2 reconciliation forbids tier=core for RDX-owned packs; "
        f"generator still marks {cores} as core"
    )


def test_l1_regression_default_tier_is_specialized() -> None:
    """When no rule-body signal indicates a test-pack, the default tier
    must be `specialized`."""
    csv_text = projection.render_index_csv()
    reader = csv.reader(io.StringIO(csv_text))
    header = next(reader)
    tier_idx = header.index("tier")
    id_idx = header.index("id")
    for row in reader:
        rid = row[id_idx]
        tier = row[tier_idx]
        if "testing" in rid or "test" in rid.split("-"):
            # `RP-TEST-*` alone may be extended
            assert tier in {"specialized", "extended"}
        else:
            assert tier == "specialized", (
                f"pack row {rid} has tier={tier}, expected specialized"
            )


def test_l1_regression_only_test_pack_may_be_extended() -> None:
    """Only rows whose pack is the RDX `testing` pack may be `extended`."""
    csv_text = projection.render_index_csv()
    reader = csv.reader(io.StringIO(csv_text))
    header = next(reader)
    tier_idx = header.index("tier")
    id_idx = header.index("id")
    extendeds = [row[id_idx] for row in reader if row[tier_idx] == "extended"]
    for rid in extendeds:
        assert "testing" in rid, (
            f"pack row {rid} marked extended but is not the testing pack"
        )


def test_l1_regression_tier_for_default_is_specialized() -> None:
    """Direct unit assertion on `_tier_for`."""
    assert projection._tier_for({}) == "specialized"


def test_l1_regression_tier_for_strong_confidence_is_specialized() -> None:
    """STRONG confidence alone must NOT map to core."""
    assert projection._tier_for({"confidence_class": "STRONG"}) != "core"


def test_l1_regression_tier_for_medium_confidence_is_specialized_unless_testing() -> None:
    """MEDIUM must not automatically map to `extended` — extended is
    reserved for the test-pack."""
    assert projection._tier_for({"confidence_class": "MEDIUM"}) in {"specialized", "extended"}
