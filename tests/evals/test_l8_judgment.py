"""Phase 7 L8 — rdx-judgment structural + harness tests.

These tests lock the *contract* the rdx-judgment skill consumes and
emits. The runtime LLM behavior (variance, scope respect, doc
classification) is measured by the L5 cases and by bmad-eval-runner;
this layer guarantees the inputs are well-formed and the harness can
score the outputs.

Coverage:
- T-L8-EVAL-CONSISTENT-001 — variance harness contract on the
  `clear-violation` fixture (N=20, variance ≤ 1).
- T-L8-ACTIVE-RULES-001 — scope discipline contract on the
  `scoped-to-unsafe` fixture (only RP-UNSAFE-* / CORE-* allowed).
- T-L8-DOC-CLASS-001 — doc-classification fixture pairs governance vs
  ordinary docs and asserts the expected-findings-about-* contract.

Plus: the rdx-judgment SKILL.md must declare these constraints in prose
so a cooperative LLM can honor them, and the rdx-judgment-finding JSON
Schema must enforce the verdict set + Cat-1 immutability invariant.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from tests.bmad._helpers.skill_parser import parse


HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent

CAT3_CASES = REPO_ROOT / "tests" / "fixtures" / "cat3-cases"
JUDGMENT_SKILL = REPO_ROOT / ".claude" / "skills" / "rdx-judgment" / "SKILL.md"
FINDING_SCHEMA = (
    REPO_ROOT / "tests" / "contracts" / "schemas" / "rdx-judgment-finding.v1.schema.json"
)


# ─── T-L8-EVAL-CONSISTENT-001 ────────────────────────────────────────────


def test_clear_violation_fixture_exists_and_declares_variance_threshold():
    case_path = CAT3_CASES / "clear-violation" / "case.json"
    assert case_path.exists(), f"clear-violation fixture missing: {case_path}"
    data = json.loads(case_path.read_text(encoding="utf-8"))
    assert data["test_id"] == "T-L8-EVAL-CONSISTENT-001"
    assert data["n_runs"] >= 10, "variance test requires N >= 10"
    assert data["variance_threshold"] >= 0
    # Must declare a single canonical expected verdict that all N runs
    # should converge on. Otherwise variance is meaningless.
    assert data["expected_verdict"] in (
        "PASS",
        "FAIL",
        "DECISION_REQUIRED",
        "SPECIALIST_REQUIRED",
        "INSUFFICIENT_EVIDENCE",
    )
    assert data["expected_rule_id"].startswith("RP-") or data[
        "expected_rule_id"
    ].startswith("CORE-")


def test_variance_harness_counts_differing_verdicts():
    """The harness API consumed by bmad-eval-runner: given N run records,
    count how many produced a verdict that differs from the canonical
    expected verdict. variance == count of differing runs."""

    from rdx_validator.judgment import count_verdict_variance

    canonical = "FAIL"
    runs = [
        {"verdict": "FAIL"},
        {"verdict": "FAIL"},
        {"verdict": "FAIL"},
        {"verdict": "PASS"},  # one differing
        {"verdict": "FAIL"},
    ]
    assert count_verdict_variance(runs, canonical) == 1

    runs_all_same = [{"verdict": "FAIL"}] * 20
    assert count_verdict_variance(runs_all_same, canonical) == 0

    runs_all_different = [{"verdict": "DECISION_REQUIRED"}] * 5
    assert count_verdict_variance(runs_all_different, canonical) == 5


# ─── T-L8-ACTIVE-RULES-001 ───────────────────────────────────────────────


def test_scoped_to_unsafe_fixture_declares_scope_envelope():
    case_path = CAT3_CASES / "scoped-to-unsafe" / "case.json"
    assert case_path.exists(), f"scoped-to-unsafe fixture missing: {case_path}"
    data = json.loads(case_path.read_text(encoding="utf-8"))
    assert data["test_id"] == "T-L8-ACTIVE-RULES-001"
    assert "unsafe" in data["active_packs"]
    # The fixture must explicitly list which inactive packs the agent
    # must NOT touch. Otherwise the test silently degrades into "did
    # you say anything about unsafe?"
    forbidden = data["forbidden_rule_id_prefixes"]
    for needle in ["RP-ASYNC-", "RP-FFI-", "RP-MACRO-", "RP-DB-"]:
        assert needle in forbidden


def test_scope_filter_rejects_inactive_pack_findings():
    """rdx-judgment ships a `filter_active_scope` helper that bmad-eval-
    runner uses to detect scope violations in transcripts."""

    from rdx_validator.judgment import filter_active_scope

    case = json.loads(
        (CAT3_CASES / "scoped-to-unsafe" / "case.json").read_text(encoding="utf-8")
    )
    findings = [
        {"rule_id": "RP-UNSAFE-002"},  # allowed
        {"rule_id": "RP-UNSAFE-003"},  # allowed
        {"rule_id": "CORE-007"},  # allowed (always-on)
        {"rule_id": "RP-ASYNC-001"},  # FORBIDDEN
        {"rule_id": "RP-FFI-002"},  # FORBIDDEN
    ]
    result = filter_active_scope(
        findings,
        allowed_prefixes=case["allowed_rule_id_prefixes"],
        forbidden_prefixes=case["forbidden_rule_id_prefixes"],
    )
    assert result.in_scope == [
        {"rule_id": "RP-UNSAFE-002"},
        {"rule_id": "RP-UNSAFE-003"},
        {"rule_id": "CORE-007"},
    ]
    assert result.out_of_scope == [
        {"rule_id": "RP-ASYNC-001"},
        {"rule_id": "RP-FFI-002"},
    ]
    assert result.scope_violation is True


def test_scope_filter_accepts_all_in_scope():
    from rdx_validator.judgment import filter_active_scope

    findings = [
        {"rule_id": "RP-UNSAFE-002"},
        {"rule_id": "CORE-014"},
    ]
    result = filter_active_scope(
        findings,
        allowed_prefixes=["RP-UNSAFE-", "CORE-"],
        forbidden_prefixes=["RP-ASYNC-", "RP-FFI-"],
    )
    assert result.scope_violation is False
    assert result.out_of_scope == []


# ─── T-L8-DOC-CLASS-001 ──────────────────────────────────────────────────


def test_governance_doc_fixture_pairs_governance_and_ordinary():
    case_path = CAT3_CASES / "governance-doc-vs-ordinary" / "case.json"
    assert case_path.exists(), (
        f"governance-doc-vs-ordinary fixture missing: {case_path}"
    )
    data = json.loads(case_path.read_text(encoding="utf-8"))
    assert data["test_id"] == "T-L8-DOC-CLASS-001"
    assert data["governance_doc_paths"], "fixture must list at least one governance doc"
    assert data["ordinary_doc_paths"], "fixture must list at least one ordinary doc"
    assert data["expected_findings_about_governance"] is True
    assert data["expected_findings_about_ordinary"] is False


def test_classify_doc_kind_known_governance_paths():
    """rdx-judgment carries a deterministic classifier (governance vs
    ordinary doc) used to scope reviewer attention. The classifier
    answers "should rdx-judgment review this file?" — Phase 7 §7.5."""

    from rdx_validator.judgment import classify_doc_kind

    # Governance docs (Phase 7 §7.5).
    assert classify_doc_kind("docs/architecture.md") == "governance"
    assert classify_doc_kind("docs/adr/0001-storage-engine.md") == "governance"
    assert classify_doc_kind("docs/api/v1.md") == "governance"
    assert classify_doc_kind("docs/security/threat-model.md") == "governance"
    assert classify_doc_kind("docs/persistence/schema.md") == "governance"
    assert classify_doc_kind(".claude/skills/rdx-setup/assets/kb-sections/section-4-core.md") == "governance"
    assert classify_doc_kind("tests/contracts/router-rules.json") == "governance"

    # Ordinary docs.
    assert classify_doc_kind("README.md") == "ordinary"
    assert classify_doc_kind("CHANGELOG.md") == "ordinary"
    assert classify_doc_kind("docs/marketing/launch-blog.md") == "ordinary"


# ─── Finding schema (used by all three L8 tests + L5) ────────────────────


@pytest.fixture(scope="module")
def finding_schema() -> dict:
    assert FINDING_SCHEMA.exists(), (
        f"rdx-judgment finding schema missing: {FINDING_SCHEMA}"
    )
    return json.loads(FINDING_SCHEMA.read_text(encoding="utf-8"))


def test_finding_schema_enumerates_v6_verdicts(finding_schema):
    """The verdict enum must match RDX_IMPLEMENTATION_PLAN_TESTED.md §7.2:
    PASS, FAIL, DECISION_REQUIRED, SPECIALIST_REQUIRED, INSUFFICIENT_EVIDENCE."""
    verdict_def = finding_schema["properties"]["verdict"]
    assert set(verdict_def["enum"]) == {
        "PASS",
        "FAIL",
        "DECISION_REQUIRED",
        "SPECIALIST_REQUIRED",
        "INSUFFICIENT_EVIDENCE",
    }


def test_finding_schema_requires_v6_fields(finding_schema):
    """Required fields per Phase 7 §7.2."""
    required = set(finding_schema["required"])
    assert required >= {
        "rule_id",
        "location",
        "contract_ref",
        "reasoning",
        "verdict",
        "confidence",
        "suggested_routing",
    }


def test_finding_schema_validates_well_formed_finding(finding_schema):
    finding = {
        "rule_id": "RP-UNSAFE-002",
        "location": {"file": "src/atomic_state.rs", "line": 12},
        "contract_ref": "RDX KB section-6.2",
        "reasoning": "Manual Send/Sync on struct holding raw pointer without sync story.",
        "verdict": "FAIL",
        "confidence": 0.9,
        "suggested_routing": "SPECIALIST_REQUIRED",
    }
    jsonschema.validate(finding, finding_schema)


def test_finding_schema_rejects_cat1_pass_by_evaluator(finding_schema):
    """The schema must reject a finding that tries to set Cat-1 verdict
    to PASS from the evaluator. This is the structural counterpart to
    T-L5-CAT3-NO-CAT1-001 — even a malicious or confused agent cannot
    smuggle an override past the schema."""

    cat1_pass = {
        "rule_id": "CORE-007",
        "category": 1,  # Cat-1 — validator authority
        "location": {"file": "_bmad/scripts/resolve_customization.py"},
        "contract_ref": "CORE-007 protected files",
        "reasoning": "I think this should pass.",
        "verdict": "PASS",
        "confidence": 0.99,
        "suggested_routing": "PASS",
        "set_by": "evaluator",
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(cat1_pass, finding_schema)


# ─── rdx-judgment SKILL prose contract ───────────────────────────────────


def test_judgment_skill_declares_scope_discipline():
    """The skill body MUST tell the LLM to load only active packs."""
    body = parse(JUDGMENT_SKILL).body.lower()
    assert "active packs" in body or "active-packs" in body
    assert "do not load" in body or "must not load" in body or "no full kb" in body


def test_judgment_skill_declares_cat1_immutability():
    body = parse(JUDGMENT_SKILL).body.lower()
    assert "cat-1" in body or "category 1" in body
    assert "immutable" in body or "do not overturn" in body or "must not overturn" in body


def test_judgment_skill_declares_doc_classification():
    body = parse(JUDGMENT_SKILL).body.lower()
    # Governance docs in scope; ordinary docs out of scope.
    assert "governance" in body
    assert "readme" in body or "ordinary" in body or "marketing" in body


def test_judgment_skill_declares_verdict_set():
    body = parse(JUDGMENT_SKILL).body
    for verdict in [
        "PASS",
        "FAIL",
        "DECISION_REQUIRED",
        "SPECIALIST_REQUIRED",
        "INSUFFICIENT_EVIDENCE",
    ]:
        assert verdict in body, f"judgment SKILL.md must declare verdict {verdict}"


def test_judgment_skill_does_not_claim_specialist_authority():
    """rdx-judgment is Cat-3. It must NOT claim to assign Cat-4 specialist
    approval. Authority matrix §1.5."""
    body = parse(JUDGMENT_SKILL).body.lower()
    forbidden_claims = [
        "rdx-judgment grants approval",
        "rdx-judgment can approve",
        "evaluator approves cat-4",
    ]
    for phrase in forbidden_claims:
        assert phrase not in body, (
            f"rdx-judgment SKILL.md must not claim Cat-4 authority: {phrase!r}"
        )
