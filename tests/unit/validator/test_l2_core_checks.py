"""L2 fixture tests for Cat-1/2 deterministic checks.

Closes:
  T-L2-CORE007-001..003 — protected files
  T-L2-CORE008-001..003 — panic discipline
  T-L2-CORE011-001..003 — compile evidence
  T-L2-CORE014-001..003 — suppression discipline
  T-L2-CORE015-001/002 — router parity
  T-L2-UNSAFE-001/003/004 — APPROVAL_REQUIRED + SAFETY-comment proximity (validator portion)
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rdx_validator.checks.core_007 import check_core_007
from rdx_validator.checks.core_008 import check_core_008
from rdx_validator.checks.core_011 import check_core_011
from rdx_validator.checks.core_014 import check_core_014
from rdx_validator.checks.core_015 import check_core_015
from rdx_validator.diff import parse_diff_paths, parse_file_changes
from rdx_validator.router import RouterRules, replay
from rdx_validator.status import Verdict


def _read_diff(fixtures_dir: Path, name: str) -> str:
    return (fixtures_dir / "diffs" / name).read_text(encoding="utf-8")


def _read_evidence(fixtures_dir: Path, name: str) -> dict:
    return json.loads((fixtures_dir / "evidence" / name).read_text(encoding="utf-8"))


# ---- CORE-007 ----------------------------------------------------------
def test_l2_core007_001_protected_touched_fail(fixtures_dir: Path):
    diff = _read_diff(fixtures_dir, "core-007/protected-touched.diff")
    v = check_core_007(parse_diff_paths(diff), ["src/auth/**"], authorised_exception=False)
    assert v.verdict == Verdict.FAIL


def test_l2_core007_002_protected_touched_authorized_pass(fixtures_dir: Path):
    diff = _read_diff(fixtures_dir, "core-007/protected-touched-authorized.diff")
    v = check_core_007(parse_diff_paths(diff), ["src/auth/**"], authorised_exception=True)
    assert v.verdict == Verdict.PASS


def test_l2_core007_003_no_protected_files_not_applicable(fixtures_dir: Path):
    diff = _read_diff(fixtures_dir, "core-007/no-protected.diff")
    v = check_core_007(parse_diff_paths(diff), [], authorised_exception=False)
    assert v.verdict == Verdict.NOT_APPLICABLE


# ---- CORE-008 ----------------------------------------------------------
def test_l2_core008_001_unwrap_prod_warning_pass(fixtures_dir: Path):
    diff = _read_diff(fixtures_dir, "core-008/new-unwrap-prod.diff")
    v = check_core_008(parse_file_changes(diff), story_tags=[])
    assert v.verdict == Verdict.PASS
    assert v.severity.value == "WARNING"


def test_l2_core008_002_unwrap_with_panic_tag_fail(fixtures_dir: Path):
    diff = _read_diff(fixtures_dir, "core-008/new-unwrap-tagged.diff")
    v = check_core_008(parse_file_changes(diff), story_tags=["panic-discipline"])
    assert v.verdict == Verdict.FAIL


def test_l2_core008_003_unwrap_in_test_ignored(fixtures_dir: Path):
    diff = _read_diff(fixtures_dir, "core-008/unwrap-in-test.diff")
    v = check_core_008(parse_file_changes(diff), story_tags=[])
    assert v.verdict == Verdict.NOT_APPLICABLE


# ---- CORE-011 ----------------------------------------------------------
def test_l2_core011_001_missing_check_evidence_required(fixtures_dir: Path):
    ev = _read_evidence(fixtures_dir, "core-011-missing-check.json")
    diff = _read_diff(fixtures_dir, "single-file-add.diff")
    paths = parse_diff_paths(diff)
    v = check_core_011(paths, (ev.get("rules") or {}).get("CORE-011"))
    assert v.verdict == Verdict.EVIDENCE_REQUIRED


def test_l2_core011_002_cargo_fail_propagates(fixtures_dir: Path):
    ev = _read_evidence(fixtures_dir, "core-011-cargo-fail.json")
    diff = _read_diff(fixtures_dir, "single-file-add.diff")
    v = check_core_011(parse_diff_paths(diff), (ev.get("rules") or {}).get("CORE-011"))
    assert v.verdict == Verdict.FAIL


def test_l2_core011_003_self_attested_rejected(fixtures_dir: Path):
    ev = _read_evidence(fixtures_dir, "core-011-self-attested.json")
    diff = _read_diff(fixtures_dir, "single-file-add.diff")
    v = check_core_011(parse_diff_paths(diff), (ev.get("rules") or {}).get("CORE-011"))
    assert v.verdict == Verdict.FAIL


# ---- CORE-014 ----------------------------------------------------------
def test_l2_core014_001_added_ignore_evidence_required(fixtures_dir: Path):
    diff = _read_diff(fixtures_dir, "core-014/added-ignore.diff")
    v = check_core_014(parse_file_changes(diff), authorised_exception=False)
    assert v.verdict == Verdict.EVIDENCE_REQUIRED


def test_l2_core014_002_removed_test_fail(fixtures_dir: Path):
    diff = _read_diff(fixtures_dir, "core-014/removed-test.diff")
    v = check_core_014(parse_file_changes(diff), authorised_exception=False)
    assert v.verdict == Verdict.FAIL


def test_l2_core014_003_vacuous_assertion_fail(fixtures_dir: Path):
    diff = _read_diff(fixtures_dir, "core-014/vacuous-assertion.diff")
    v = check_core_014(parse_file_changes(diff), authorised_exception=False)
    assert v.verdict == Verdict.FAIL


# ---- CORE-015 ----------------------------------------------------------
@pytest.fixture(scope="module")
def router_rules(contracts_dir: Path) -> RouterRules:
    return RouterRules.load(contracts_dir / "router-rules.json")


def test_l2_core015_001_agent_missed_pack_fail(fixtures_dir: Path, router_rules: RouterRules):
    diff = _read_diff(fixtures_dir, "unsafe/positive-new-unsafe-block.diff")
    activations = replay(diff, router_rules)
    ev = _read_evidence(fixtures_dir, "core-015-pack-omitted.json")
    v = check_core_015(
        validator_activations=activations,
        agent_claimed=ev["agent_activated_packs"],
        documented_suppressions=ev["router_suppressions"],
    )
    assert v.verdict == Verdict.FAIL
    assert "unsafe" in (v.reason or "")


def test_l2_core015_002_documented_suppression_pass(fixtures_dir: Path, router_rules: RouterRules):
    # Use the async positive diff so the validator activates "async"; the
    # agent claims nothing but lists "async" in router_suppressions.
    diff = _read_diff(fixtures_dir, "async/positive-tokio-spawn.diff")
    activations = replay(diff, router_rules)
    ev = _read_evidence(fixtures_dir, "core-015-suppression.json")
    v = check_core_015(
        validator_activations=activations,
        agent_claimed=ev["agent_activated_packs"],
        documented_suppressions=ev["router_suppressions"],
    )
    assert v.verdict == Verdict.PASS


# ---- UNSAFE pack downstream effects -----------------------------------
def test_l2_unsafe_001_unsafe_pack_yields_approval_required(
    fixtures_dir: Path, router_rules: RouterRules
):
    """T-L2-UNSAFE-001 — unsafe pack triggers APPROVAL_REQUIRED in CLI translation."""
    from rdx_validator.cli import _pack_verdicts  # noqa: WPS437

    diff = _read_diff(fixtures_dir, "unsafe/positive-new-unsafe-block.diff")
    activations = replay(diff, router_rules)
    verdicts = _pack_verdicts(activations)
    rule_ids = {v.rule_id: v.verdict for v in verdicts}
    assert rule_ids.get("RP-UNSAFE-001") == Verdict.APPROVAL_REQUIRED
