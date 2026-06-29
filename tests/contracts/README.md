# L0 — Static Contract Tests

Phase 1 deliverable. These tests load schemas/mappings and assert structural properties.

## Files to author at Phase 1 entry

| File | Test IDs covered |
|------|------------------|
| `schemas/rdx-evidence.v1.schema.json` | T-L0-SCHEMA-001..004 |
| `schemas/router-rules.schema.json` | T-L0-ROUTER-001 |
| `status-definitions.json` | T-L0-STATUS-001 |
| `authority-matrix.json` | T-L0-STATUS-002 |
| `rule-check-map.json` | T-L0-DRIFT-002 |
| `drift-check.py` | T-L0-DRIFT-001, T-L0-DRIFT-002, T-L0-RULE-IDS-001 |
| `verify-traceability.py` | (cross-cuts requirement coverage) |
| `golden/router-rules.golden.json` | golden snapshot for diff-on-change |

All schemas use JSON Schema Draft 2020-12.

## Drift policy

Any change to `_bmad/rust-kb/section-{4,5,6,8}-*.md` or `router-rules.json` MUST be accompanied by a passing `drift-check.py`. CI enforces.
