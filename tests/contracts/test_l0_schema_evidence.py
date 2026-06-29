"""L0 contract tests for the evidence schema.

Covers test IDs:
  T-L0-SCHEMA-001 — schema file is a valid JSON Schema (Draft 2020-12)
  T-L0-SCHEMA-002 — valid evidence sample passes schema
  T-L0-SCHEMA-003 — invalid evidence (missing diff_digest) is rejected
  T-L0-SCHEMA-004 — schema forbids LLM-written Cat-1 PASS without command evidence
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError


def _load_json(path: Path):
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def test_l0_schema_001_schema_is_valid_draft_2020_12(contracts_dir: Path):
    """T-L0-SCHEMA-001 — the evidence schema parses as Draft 2020-12."""
    schema_path = contracts_dir / "schemas" / "rdx-evidence.v1.schema.json"
    assert schema_path.exists(), f"schema missing: {schema_path}"
    schema = _load_json(schema_path)

    assert schema.get("$schema") == "https://json-schema.org/draft/2020-12/schema"
    assert schema.get("$id"), "$id must be set"

    Draft202012Validator.check_schema(schema)


def test_l0_schema_002_valid_evidence_passes(contracts_dir: Path, fixtures_dir: Path):
    """T-L0-SCHEMA-002 — a fully-populated valid evidence sample validates."""
    schema = _load_json(contracts_dir / "schemas" / "rdx-evidence.v1.schema.json")
    fixture_path = fixtures_dir / "evidence" / "valid-minimal.json"
    assert fixture_path.exists(), f"fixture missing: {fixture_path}"

    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(_load_json(fixture_path)), key=lambda e: e.path)
    assert errors == [], "valid fixture must not produce errors: " + "; ".join(
        f"{list(e.path)}: {e.message}" for e in errors
    )


def test_l0_schema_003_missing_diff_digest_is_rejected(contracts_dir: Path, fixtures_dir: Path):
    """T-L0-SCHEMA-003 — evidence without diff_digest must fail validation."""
    schema = _load_json(contracts_dir / "schemas" / "rdx-evidence.v1.schema.json")
    fixture_path = fixtures_dir / "evidence" / "invalid-missing-diff-digest.json"
    assert fixture_path.exists()

    validator = Draft202012Validator(schema)
    errors = list(validator.iter_errors(_load_json(fixture_path)))
    assert errors, "schema must reject fixtures without diff_digest"
    paths = {tuple(e.absolute_path) for e in errors}
    error_text = " ".join(e.message for e in errors)
    assert any("diff_digest" in e.message for e in errors) or () in paths, (
        "error must reference diff_digest field"
    )
    assert "diff_digest" in error_text


def test_l0_schema_004_cat1_pass_requires_command_evidence(
    contracts_dir: Path, fixtures_dir: Path
):
    """T-L0-SCHEMA-004 — a Cat-1 PASS without command/exit_code/output_digest is rejected.

    The schema must encode authority: an LLM cannot self-attest PASS for a Cat-1
    rule; PASS for those rules requires structured tool evidence.
    """
    schema = _load_json(contracts_dir / "schemas" / "rdx-evidence.v1.schema.json")
    fixture_path = fixtures_dir / "evidence" / "invalid-cat1-pass-no-command.json"
    assert fixture_path.exists()

    validator = Draft202012Validator(schema)
    errors = list(validator.iter_errors(_load_json(fixture_path)))
    assert errors, "schema must forbid Cat-1 PASS without command evidence"
