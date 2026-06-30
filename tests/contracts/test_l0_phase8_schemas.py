"""L0 contract tests for the Phase 8 schemas.

Covers test IDs (subset of T-L8-CAT4-005 and the entry-gate "specs written"
boxes for approvers.schema.json + approval.v1.schema.json):

  T-L0-PHASE8-SCHEMA-001 — approvers.schema.json is a valid Draft 2020-12 schema
  T-L0-PHASE8-SCHEMA-002 — sample approvers.yaml validates against the schema
  T-L0-PHASE8-SCHEMA-003 — approvers.yaml missing the required `roles` block is rejected
  T-L0-PHASE8-SCHEMA-004 — approval.v1.schema.json is a valid Draft 2020-12 schema
  T-L0-PHASE8-SCHEMA-005 — valid approval JSON validates
  T-L0-PHASE8-SCHEMA-006 — approval missing rule_id is rejected
  T-L0-PHASE8-SCHEMA-007 — approval missing diff_digest is rejected
  T-L0-PHASE8-SCHEMA-008 — approval missing approver_identity is rejected
  T-L0-PHASE8-SCHEMA-009 — approval with decision=denied still validates

The two schemas live in `_bmad/rdx/` so the canonical paths are stable for
end-user projects that vendor RDX (the validator reads them from there).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator


REPO_ROOT = Path(__file__).resolve().parents[2]
RDX_DIR = REPO_ROOT / "_bmad" / "rdx"
APPROVERS_SCHEMA = RDX_DIR / "approvers.schema.json"
APPROVAL_SCHEMA = RDX_DIR / "approval.v1.schema.json"
APPROVERS_FIXTURES = REPO_ROOT / "tests" / "fixtures" / "approvers"
APPROVAL_FIXTURES = REPO_ROOT / "tests" / "fixtures" / "approvals" / "schema-cases"


def _load_json(path: Path):
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def _load_yaml(path: Path):
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


# ----- approvers.schema.json -----

def test_l0_phase8_schema_001_approvers_schema_is_draft_2020_12():
    """T-L0-PHASE8-SCHEMA-001 — approvers schema parses as Draft 2020-12."""
    assert APPROVERS_SCHEMA.exists(), f"schema missing: {APPROVERS_SCHEMA}"
    schema = _load_json(APPROVERS_SCHEMA)
    assert schema.get("$schema") == "https://json-schema.org/draft/2020-12/schema"
    assert schema.get("$id"), "$id must be set"
    Draft202012Validator.check_schema(schema)


def test_l0_phase8_schema_002_valid_approvers_yaml_passes():
    """T-L0-PHASE8-SCHEMA-002 — sample approvers.yaml validates."""
    schema = _load_json(APPROVERS_SCHEMA)
    sample = APPROVERS_FIXTURES / "sample-approvers" / "approvers.yaml"
    assert sample.exists(), f"fixture missing: {sample}"
    data = _load_yaml(sample)
    errors = list(Draft202012Validator(schema).iter_errors(data))
    assert errors == [], "valid approvers.yaml must not produce errors: " + "; ".join(
        f"{list(e.path)}: {e.message}" for e in errors
    )


def test_l0_phase8_schema_003_approvers_missing_roles_rejected():
    """T-L0-PHASE8-SCHEMA-003 — approvers.yaml missing top-level `roles` is rejected."""
    schema = _load_json(APPROVERS_SCHEMA)
    bad = APPROVERS_FIXTURES / "invalid-missing-roles" / "approvers.yaml"
    assert bad.exists(), f"fixture missing: {bad}"
    data = _load_yaml(bad)
    errors = list(Draft202012Validator(schema).iter_errors(data))
    assert errors, "schema must reject approvers.yaml without roles"


# ----- approval.v1.schema.json (T-L8-CAT4-005) -----

def test_l0_phase8_schema_004_approval_schema_is_draft_2020_12():
    """T-L0-PHASE8-SCHEMA-004 — approval schema parses as Draft 2020-12."""
    assert APPROVAL_SCHEMA.exists(), f"schema missing: {APPROVAL_SCHEMA}"
    schema = _load_json(APPROVAL_SCHEMA)
    assert schema.get("$schema") == "https://json-schema.org/draft/2020-12/schema"
    assert schema.get("$id"), "$id must be set"
    Draft202012Validator.check_schema(schema)


def test_l0_phase8_schema_005_valid_approval_passes():
    """T-L0-PHASE8-SCHEMA-005 — full valid approval JSON validates."""
    schema = _load_json(APPROVAL_SCHEMA)
    fixture = APPROVAL_FIXTURES / "valid.json"
    assert fixture.exists()
    errors = list(Draft202012Validator(schema).iter_errors(_load_json(fixture)))
    assert errors == [], "valid fixture must not produce errors: " + "; ".join(
        f"{list(e.path)}: {e.message}" for e in errors
    )


def test_l0_phase8_schema_006_approval_missing_rule_id_rejected():
    """T-L0-PHASE8-SCHEMA-006 — approval without rule_id is rejected."""
    schema = _load_json(APPROVAL_SCHEMA)
    fixture = APPROVAL_FIXTURES / "invalid-missing-rule-id.json"
    assert fixture.exists()
    errors = list(Draft202012Validator(schema).iter_errors(_load_json(fixture)))
    assert errors, "schema must reject approval without rule_id"
    assert any("rule_id" in (e.message or "") for e in errors)


def test_l0_phase8_schema_007_approval_missing_diff_digest_rejected():
    """T-L0-PHASE8-SCHEMA-007 — approval without diff_digest is rejected."""
    schema = _load_json(APPROVAL_SCHEMA)
    fixture = APPROVAL_FIXTURES / "invalid-missing-diff-digest.json"
    assert fixture.exists()
    errors = list(Draft202012Validator(schema).iter_errors(_load_json(fixture)))
    assert errors, "schema must reject approval without diff_digest"
    assert any("diff_digest" in (e.message or "") for e in errors)


def test_l0_phase8_schema_008_approval_missing_approver_identity_rejected():
    """T-L0-PHASE8-SCHEMA-008 — approval without approver_identity is rejected."""
    schema = _load_json(APPROVAL_SCHEMA)
    fixture = APPROVAL_FIXTURES / "invalid-missing-approver.json"
    assert fixture.exists()
    errors = list(Draft202012Validator(schema).iter_errors(_load_json(fixture)))
    assert errors, "schema must reject approval without approver_identity"
    assert any("approver_identity" in (e.message or "") for e in errors)


def test_l0_phase8_schema_009_approval_decision_denied_passes():
    """T-L0-PHASE8-SCHEMA-009 — decision=denied is a well-formed value (denials recorded too)."""
    schema = _load_json(APPROVAL_SCHEMA)
    fixture = APPROVAL_FIXTURES / "valid-denied.json"
    assert fixture.exists()
    errors = list(Draft202012Validator(schema).iter_errors(_load_json(fixture)))
    assert errors == [], "denied approval must validate (recorded for audit): " + "; ".join(
        f"{list(e.path)}: {e.message}" for e in errors
    )
