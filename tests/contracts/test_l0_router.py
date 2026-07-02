"""L0 contract tests for the Router rules mapping.

Covers test ID:
  T-L0-ROUTER-001 — router-rules.json validates against router-rules.schema.json
"""

from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator


def _load_json(path: Path):
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def test_l0_router_001_router_rules_validate_against_meta_schema(contracts_dir: Path):
    """T-L0-ROUTER-001 — router-rules.json conforms to its meta-schema."""
    schema_path = contracts_dir / "router-rules.schema.json"
    rules_path = contracts_dir / "router-rules.json"
    assert schema_path.exists(), f"schema missing: {schema_path}"
    assert rules_path.exists(), f"router rules missing: {rules_path}"

    schema = _load_json(schema_path)
    Draft202012Validator.check_schema(schema)

    rules = _load_json(rules_path)
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(rules), key=lambda e: list(e.absolute_path))
    assert errors == [], "router-rules.json failed validation: " + "; ".join(
        f"{list(e.absolute_path)}: {e.message}" for e in errors
    )


def test_l0_router_activation_classes_within_allowed_set(contracts_dir: Path):
    """Defense-in-depth — activation_policy values are taken from the canonical set."""
    rules = _load_json(contracts_dir / "router-rules.json")
    allowed = {"AUTO_ACTIVATE", "AUTO_SUGGEST", "STORY_TAG_REQUIRED", "REVIEW_REQUIRED"}
    for pack_id, entry in rules["packs"].items():
        assert entry["activation_policy"] in allowed, (
            f"pack {pack_id} has illegal activation_policy {entry['activation_policy']!r}"
        )
