"""Phase 7 entry-gate: structural contract for the three Cat-3 / doc-
classification L5 cases (T-L5-CAT3-SCOPE-001, T-L5-CAT3-NO-CAT1-001,
T-L5-DOC-001).

Mirrors the Phase 6 test (`test_l5_eval_cases.py`) — locks the case-file
shape so bmad-eval-runner has a stable contract to consume. The actual
statistical pass-rate enforcement happens once the runner produces real
run records; this test only proves the harness inputs are well-formed.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml


PHASE7_SLUGS = [
    "cat3-scope",
    "cat3-cat1-immutable",
    "doc-not-rust",
]

REQUIRED_FIELDS = [
    "id",
    "slug",
    "phase",
    "layer",
    "title",
    "prompt",
    "expected_assertions",
    "repeat_count",
    "pass_threshold",
    "grader_model",
    "tested_model",
    "rolling_window_days",
    "gate",
    "artifacts_dir",
]

# Phase 7 exit-gate thresholds (RDX_IMPLEMENTATION_PLAN_TESTED.md §7
# "T-L5-CAT3-SCOPE-001 ≥ 95% / T-L5-CAT3-NO-CAT1-001 = 100% /
#  T-L5-DOC-001 — no Rust noise on non-Rust docs").
EXPECTED_THRESHOLDS = {
    "cat3-scope": 0.95,
    "cat3-cat1-immutable": 1.00,
    "doc-not-rust": 0.95,
}


@pytest.mark.parametrize("slug", PHASE7_SLUGS)
def test_phase7_case_file_exists_and_has_required_fields(
    evals_dir: Path, slug: str
) -> None:
    case_path = evals_dir / slug / "case.yaml"
    assert case_path.exists(), f"missing eval case file: {case_path}"
    data = yaml.safe_load(case_path.read_text(encoding="utf-8"))
    assert isinstance(data, dict), f"{case_path} must parse to a mapping"
    missing = [f for f in REQUIRED_FIELDS if f not in data]
    assert not missing, f"{case_path} missing fields: {missing}"
    assert data["phase"] == 7, f"{case_path} must be phase 7"
    assert data["layer"] == "L5"
    assert data["gate"] == "exit-phase-7"
    assert data["slug"] == slug
    assert data["repeat_count"] >= 10, "L5 evals require N>=10 per strategy §2"
    assert 0.0 < float(data["pass_threshold"]) <= 1.0
    assert isinstance(data["expected_assertions"], list) and data["expected_assertions"], (
        f"{case_path} must declare expected_assertions"
    )


@pytest.mark.parametrize("slug", PHASE7_SLUGS)
def test_phase7_thresholds_match_plan(evals_dir: Path, slug: str) -> None:
    """Drift guard — Phase 7 exit-gate thresholds (95/100/95) are locked."""
    data = yaml.safe_load(
        (evals_dir / slug / "case.yaml").read_text(encoding="utf-8")
    )
    assert float(data["pass_threshold"]) == EXPECTED_THRESHOLDS[slug], (
        f"{slug} threshold drifted from RDX_IMPLEMENTATION_PLAN_TESTED.md §7: "
        f"file={data['pass_threshold']} expected={EXPECTED_THRESHOLDS[slug]}"
    )


def test_cat3_scope_rubric_lists_inactive_packs(evals_dir: Path) -> None:
    """The scope rubric MUST explicitly forbid inactive-pack rule IDs in
    the transcript. Otherwise the test silently degrades into "did the
    model say anything about unsafe?" which is too weak."""
    data = yaml.safe_load(
        (evals_dir / "cat3-scope" / "case.yaml").read_text(encoding="utf-8")
    )
    forbidden = []
    for a in data["expected_assertions"]:
        forbidden.extend(a.get("must_not_contain_any", []) or [])
    # At minimum: the most-easily-confused inactive packs.
    for needle in ["RP-ASYNC", "RP-FFI", "RP-MACRO", "RP-DB"]:
        assert needle in forbidden, (
            f"cat3-scope rubric must explicitly forbid {needle} in transcript"
        )


def test_cat3_cat1_immutable_demands_100pct(evals_dir: Path) -> None:
    """Authority-matrix invariant: Cat-1 NEVER overturned. 100% required."""
    data = yaml.safe_load(
        (evals_dir / "cat3-cat1-immutable" / "case.yaml").read_text(encoding="utf-8")
    )
    assert float(data["pass_threshold"]) == 1.00


def test_doc_not_rust_forbids_rust_rule_ids(evals_dir: Path) -> None:
    """The doc-classification rubric must forbid every Rust-specific rule
    family on a README-only diff. False findings on ordinary docs erode
    trust faster than missed findings (strategy §1 principle 5)."""
    data = yaml.safe_load(
        (evals_dir / "doc-not-rust" / "case.yaml").read_text(encoding="utf-8")
    )
    forbidden = []
    for a in data["expected_assertions"]:
        forbidden.extend(a.get("must_not_contain_any", []) or [])
    for needle in ["RP-UNSAFE", "RP-ASYNC", "RP-FFI", "CORE-007"]:
        assert needle in forbidden, (
            f"doc-not-rust rubric must explicitly forbid {needle} on README-only diff"
        )
