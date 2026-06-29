"""L0 contract tests for status taxonomy and authority matrix.

Covers test IDs:
  T-L0-STATUS-001 — status-definitions.json contains exactly the 14 canonical
                    verdicts and 3 severities (per RDX_TEST_STRATEGY.md §5).
  T-L0-STATUS-002 — authority-matrix.json provides an entry for every
                    (field × actor) cell.

The expected verdict/severity sets are inline in this test to keep the strategy
document as the single source of truth — drift here must be a conscious decision.
"""

from __future__ import annotations

import json
from pathlib import Path

CANONICAL_VERDICTS = {
    "PASS",
    "FAIL",
    "NOT_APPLICABLE",
    "NOT_RUN",
    "EVIDENCE_REQUIRED",
    "REVIEW_REQUIRED",
    "APPROVAL_REQUIRED",
    "BASELINE_FAILURE_OBSERVED",
    "BASELINE_BLOCKS_VALIDATION",
    "REGRESSION_FAILURE",
    "REGRESSION_FIXED",
    "ENVIRONMENT_UNAVAILABLE",
    "TOOL_UNAVAILABLE",
    "BLOCKED",
}
CANONICAL_SEVERITIES = {"INFO", "WARNING", "BLOCKING"}

# Authority actors (rows) and evidence fields (columns) per RDX_TEST_STRATEGY.md §5
# and the traceability matrix authority columns.
REQUIRED_ACTORS = {"LLM", "Validator", "Evaluator", "Specialist", "CI"}
REQUIRED_FIELDS = {
    "verdict_cat1",
    "verdict_cat2",
    "verdict_cat3",
    "verdict_cat4",
    "diff_digest",
    "head_sha",
    "exception_grant",
    "approval_signature",
    "command_evidence",
    "story_tag",
    "router_activation",
}


def _load(path: Path):
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def test_l0_status_001_canonical_taxonomy(contracts_dir: Path):
    """T-L0-STATUS-001 — verdict + severity sets are exactly canonical."""
    status_path = contracts_dir / "status-definitions.json"
    assert status_path.exists(), f"status-definitions.json missing: {status_path}"
    doc = _load(status_path)

    verdicts = set(doc.get("verdicts", {}).keys())
    severities = set(doc.get("severities", {}).keys())

    assert verdicts == CANONICAL_VERDICTS, (
        f"verdict mismatch: missing={CANONICAL_VERDICTS - verdicts}, "
        f"extra={verdicts - CANONICAL_VERDICTS}"
    )
    assert severities == CANONICAL_SEVERITIES, (
        f"severity mismatch: missing={CANONICAL_SEVERITIES - severities}, "
        f"extra={severities - CANONICAL_SEVERITIES}"
    )


def test_l0_status_001_exit_code_mapping_complete(contracts_dir: Path):
    """Each verdict carries an exit-code class (0/1/2/3/4) per strategy §5.3."""
    doc = _load(contracts_dir / "status-definitions.json")
    valid_codes = {0, 1, 2, 3, 4}
    for verdict, body in doc["verdicts"].items():
        assert "exit_code_class" in body, f"verdict {verdict} missing exit_code_class"
        assert body["exit_code_class"] in valid_codes, (
            f"verdict {verdict} has out-of-range exit_code_class {body['exit_code_class']}"
        )


def test_l0_status_002_authority_matrix_complete(contracts_dir: Path):
    """T-L0-STATUS-002 — every (field × actor) cell is populated."""
    matrix_path = contracts_dir / "authority-matrix.json"
    assert matrix_path.exists(), f"authority-matrix.json missing: {matrix_path}"
    matrix = _load(matrix_path)

    fields = matrix.get("fields", {})
    missing = REQUIRED_FIELDS - set(fields.keys())
    assert not missing, f"authority-matrix.json missing fields: {sorted(missing)}"

    extra = set(fields.keys()) - REQUIRED_FIELDS
    assert not extra, f"authority-matrix.json has unexpected fields: {sorted(extra)}"

    allowed_authorities = {"WRITE", "READ", "VERIFY", "FORBIDDEN"}
    for field_name, actor_map in fields.items():
        missing_actors = REQUIRED_ACTORS - set(actor_map.keys())
        assert not missing_actors, (
            f"field {field_name} missing actors: {sorted(missing_actors)}"
        )
        for actor, authority in actor_map.items():
            assert authority in allowed_authorities, (
                f"field {field_name}, actor {actor}: illegal authority {authority!r}"
            )
