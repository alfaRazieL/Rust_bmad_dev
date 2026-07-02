"""T-L7-MOD-SCHEMA-001 — PR modifies rdx-evidence.schema.json to weaken
it. CI loads schema from main branch, so weak evidence is still
rejected.

This test demonstrates the Option B trust model at the schema layer:
the ci-runner records `schema_source` in its output, and validation is
performed against the base-branch schema.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import jsonschema
import pytest


def test_l7_modified_schema_has_no_effect(schema_path, tmp_path):
    """Even if a PR ships a permissive schema, the base-branch schema
    rejects the fake evidence — we model this by validating with the
    canonical schema from this repo (which corresponds to `main` in the
    Option B model)."""
    base_schema = json.loads(schema_path.read_text(encoding="utf-8"))

    # PR's "weakened" schema (would allow Cat-1 PASS without command).
    weak_schema = json.loads(schema_path.read_text(encoding="utf-8"))
    # neuter the conditional that requires `command` for Cat-1 PASS:
    # walk every nested object and drop any `allOf` we find.
    def _strip_allof(node):
        if isinstance(node, dict):
            node.pop("allOf", None)
            for v in node.values():
                _strip_allof(v)
        elif isinstance(node, list):
            for v in node:
                _strip_allof(v)

    _strip_allof(weak_schema)

    fake_evidence = {
        "rdx_schema_version": "v1",
        "story_id": "STORY-MOD-SCHEMA-001",
        "head_sha": "a" * 40,
        "base_sha": "b" * 40,
        "diff_digest": "0" * 64,
        "mode": "MODE_3",
        "rules": {
            "CORE-011": {
                "category": 1,
                "verdict": "PASS",
                "severity": "INFO",
                "author": "VALIDATOR",
            }
        },
        "aggregate": {
            "verdict": "PASS",
            "exit_code": 0,
            "blocking_count": 0,
            "warning_count": 0,
            "info_count": 1,
        },
        "validator": {"name": "rdx-validator", "version": "0.1.0", "source": "PR_HEAD"},
    }

    # Weak schema would accept this — that's the attacker's win condition.
    try:
        jsonschema.validate(fake_evidence, weak_schema)
    except jsonschema.ValidationError:
        pytest.fail("Weak schema unexpectedly rejected; test premise broken")

    # Base schema (Option B source-of-truth) must reject.
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(fake_evidence, base_schema)
