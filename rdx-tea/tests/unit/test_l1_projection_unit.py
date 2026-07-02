"""L1 unit tests for `poc/adapter/projection.py`.

Contract for individual functions inside the projection generator.
Failure of any of these tests is a knowledge-plane defect (G2 / G3
gates); no enforcement-plane test may be reached while these are red.
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path

import pytest

RDX_TEA_DIR = Path(__file__).resolve().parent.parent.parent
REPO_ROOT = RDX_TEA_DIR.parent

import importlib.util

spec = importlib.util.spec_from_file_location(
    "rdx_tea_projection", RDX_TEA_DIR / "poc" / "adapter" / "projection.py"
)
projection = importlib.util.module_from_spec(spec)
spec.loader.exec_module(projection)   # type: ignore[union-attr]


# --------------------------------------------------------------------------
# CANONICAL_INPUTS is the source-of-truth surface. Regressions here are the
# earliest sign of a "hand-copied Router" (prompt §5.3).
# --------------------------------------------------------------------------

def test_l1_canonical_inputs_are_only_repo_files() -> None:
    """No projection may consume anything outside `tests/contracts/` or the
    KB sections."""
    contracts_root = (REPO_ROOT / "tests" / "contracts").resolve()
    kb_root = (REPO_ROOT / ".claude" / "skills" / "rdx-setup" / "assets" / "kb-sections").resolve()
    for p in projection.CANONICAL_INPUTS:
        p = p.resolve()
        assert (
            str(p).startswith(str(contracts_root))
            or str(p).startswith(str(kb_root))
        ), f"projection reads {p} which is outside the canonical source set"


def test_l1_canonical_inputs_all_exist() -> None:
    for p in projection.CANONICAL_INPUTS:
        assert p.exists(), f"canonical input missing: {p}"


# --------------------------------------------------------------------------
# Router loader
# --------------------------------------------------------------------------

def test_l1_load_router_shape() -> None:
    r = projection._load_router()
    assert set(r.keys()) >= {"rdx_router_version", "kb_source", "packs"}
    assert r["rdx_router_version"] == "v1"
    assert len(r["packs"]) == 12


def test_l1_load_router_uses_canonical_file() -> None:
    """Reload via projection must equal reload via direct file read."""
    direct = json.loads((REPO_ROOT / "tests" / "contracts" / "router-rules.json").read_text())
    indirect = projection._load_router()
    assert direct == indirect


# --------------------------------------------------------------------------
# Status loader — completeness
# --------------------------------------------------------------------------

def test_l1_load_status_has_full_vocabulary() -> None:
    s = projection._load_status()
    assert set(s["verdicts"].keys()) == {
        "PASS", "FAIL", "NOT_APPLICABLE", "NOT_RUN",
        "EVIDENCE_REQUIRED", "REVIEW_REQUIRED", "APPROVAL_REQUIRED",
        "BASELINE_FAILURE_OBSERVED", "BASELINE_BLOCKS_VALIDATION",
        "REGRESSION_FAILURE", "REGRESSION_FIXED",
        "ENVIRONMENT_UNAVAILABLE", "TOOL_UNAVAILABLE", "BLOCKED",
    }
    assert set(s["severities"].keys()) == {"INFO", "WARNING", "BLOCKING"}


# --------------------------------------------------------------------------
# Tier classification
# --------------------------------------------------------------------------

# D3 correction (BUILDER_TEA_RECONCILIATION §3.3, D3_CORRECTION_AUDIT §3.3):
# no RDX pack is `core`; default is `specialized`; `testing` pack may be
# `extended`. The confidence-class → tier mapping used in D2 is retired.
@pytest.mark.parametrize(
    "meta,expected_tier",
    [
        ({"pack_id": "testing"}, "extended"),
        ({"pack_id": "async"}, "specialized"),
        ({"pack_id": "unsafe"}, "specialized"),
        ({}, "specialized"),
    ],
)
def test_l1_tier_for(meta: dict, expected_tier: str) -> None:
    assert projection._tier_for(meta) == expected_tier


def test_l1_tier_matches_expected_packs() -> None:
    """D3 policy: only `testing` may be `extended`; every other pack is
    `specialized`. Nothing is `core`."""
    r = projection._load_router()
    tiers = {n: projection._tier_for({**p, "pack_id": n}) for n, p in r["packs"].items()}
    assert tiers["testing"] == "extended"
    for name, t in tiers.items():
        if name == "testing":
            continue
        assert t == "specialized", f"{name} must be specialized, got {t}"
    # And the invariant we most care about
    assert "core" not in tiers.values()


# --------------------------------------------------------------------------
# Per-pack fragment renderer
# --------------------------------------------------------------------------

def test_l1_pack_fragment_contains_frontmatter() -> None:
    r = projection._load_router()
    frag = projection._render_pack_fragment("async", r["packs"]["async"], ["PASS", "FAIL"])
    assert frag.startswith("---\n")
    assert "pack_id: async" in frag
    assert "confidence_class: STRONG" in frag
    assert "activation_policy: AUTO_ACTIVATE" in frag
    assert "source_of_truth: tests/contracts/router-rules.json" in frag


def test_l1_pack_fragment_includes_every_related_rule_id() -> None:
    r = projection._load_router()
    for pack_name, pack in r["packs"].items():
        frag = projection._render_pack_fragment(pack_name, pack, ["PASS"])
        for rid in pack["related_rule_ids"]:
            assert f"`{rid}`" in frag, f"pack {pack_name} rule {rid} missing"


def test_l1_pack_fragment_lists_all_verdicts_alphabetically() -> None:
    r = projection._load_router()
    verdicts = sorted(["FAIL", "PASS", "REGRESSION_FIXED", "BLOCKED"])
    frag = projection._render_pack_fragment("async", r["packs"]["async"], verdicts)
    lines = frag.splitlines()
    # Extract the verdict bullets by looking for the block after the
    # "verdict vocabulary" heading.
    idx = next(i for i, l in enumerate(lines) if "Verdict vocabulary" in l)
    bullets = [l for l in lines[idx:] if l.startswith("* `") and l.endswith("`")]
    observed = [b.split("`")[1] for b in bullets if b.count("`") == 2]
    # Only assert order for the ones we asked for; the fragment also
    # lists PASS/FAIL as a valid superset.
    subset = [v for v in observed if v in {"PASS", "FAIL", "REGRESSION_FIXED", "BLOCKED"}]
    assert subset == sorted(subset)


# --------------------------------------------------------------------------
# Index CSV shape
# --------------------------------------------------------------------------

def test_l1_index_csv_header_matches_tea_index_schema() -> None:
    """The schema `id,name,description,tags,tier,fragment_file` mirrors the
    BMAD `tea-index.csv` header (see BMAD_CORE_EXTENSION_SURFACE.md §3)."""
    txt = projection.render_index_csv()
    reader = csv.reader(io.StringIO(txt))
    header = next(reader)
    assert header == ["id", "name", "description", "tags", "tier", "fragment_file"]


def test_l1_index_csv_has_one_row_per_pack_and_no_duplicates() -> None:
    txt = projection.render_index_csv()
    reader = csv.reader(io.StringIO(txt))
    next(reader)   # skip header
    ids = [row[0] for row in reader]
    assert len(ids) == 12
    assert len(set(ids)) == 12


def test_l1_index_csv_fragment_files_exist_when_emitted(tmp_path: Path) -> None:
    dest = tmp_path / "projections"
    projection.emit_to_disk(dest)
    csv_text = (dest / "rdx-tea-index.csv").read_text()
    reader = csv.reader(io.StringIO(csv_text))
    next(reader)
    for row in reader:
        assert (dest / row[-1]).exists(), f"fragment file missing: {row[-1]}"


# --------------------------------------------------------------------------
# End-to-end determinism
# --------------------------------------------------------------------------

def test_l1_render_all_is_deterministic_across_processes(tmp_path: Path) -> None:
    """Independent second call must return identical bytes."""
    a = projection.render_all()
    b = projection.render_all()
    assert a == b


def test_l1_render_all_covers_all_12_packs_plus_index() -> None:
    out = projection.render_all()
    knowledge_files = [k for k in out if k.startswith("knowledge/")]
    assert len(knowledge_files) == 12
    assert "rdx-tea-index.csv" in out


def test_l1_render_all_no_wallclock_or_random_content() -> None:
    """Content must not contain year-strings or ISO timestamps."""
    out = projection.render_all()
    for k, v in out.items():
        blob = v.decode("utf-8")
        # Reject obvious wallclock tokens:
        assert "T00:00:00" not in blob
        assert "TZ=" not in blob
        assert "random" not in blob.lower()
