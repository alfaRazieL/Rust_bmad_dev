"""T-L7-FAKE-PASS-001 — Author commits an evidence.json with rules.CORE-011
verdict=PASS but no command evidence. CI's schema validation rejects it
AND the validator re-run produces the authoritative verdict.

Defense layer: L2 schema + L6 CI re-run.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest


FAKE_PASS_EVIDENCE = {
    "rdx_schema_version": "v1",
    "story_id": "STORY-FAKE-001",
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
            # NOTE: no `evidence` array — this is the fake.
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


def test_l7_fake_pass_rejected_by_schema(schema_path):
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(FAKE_PASS_EVIDENCE, schema)
