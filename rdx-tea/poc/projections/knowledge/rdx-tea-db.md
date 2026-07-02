---
pack_id: db
kb_section: 6.9
confidence_class: MEDIUM
activation_policy: AUTO_SUGGEST
source_of_truth: tests/contracts/router-rules.json
---

# Rust risk pack: Database, messaging, and distributed state

## When this pack activates

* Confidence: `MEDIUM`
* Policy: `AUTO_SUGGEST`

### Positive signals (in diff/file):
* `sqlx::`
* `diesel::`
* `tokio_postgres`
* `rusqlite`
* `sea_orm`
* `redis::`
* `lapin::`
* `rdkafka::`
* `rabbitmq`
* `BEGIN;`
* `COMMIT;`
* `ROLLBACK`

### Negative signals (suppress activation):
* in-memory-only collections
* local file/cache persistence without DB or queue semantics
* HTTP/API client calls with no durable state
* docs-only mentions

### Path signals:
* `**/migrations/**`
* `**/schema.sql`
* `**/*.sql`
* `**/diesel.toml`

## Escalation triggers (require specialist review)
* production schema migration
* rollback or mixed-version deploy
* exactly-once claims
* poison-message handling
* money/time/nullability mapping

## Related canonical rule IDs

Every rule ID below is defined by the RDX KB and MUST NOT be renamed by any downstream consumer:

* `RP-DB-001`
* `RP-DB-002`
* `RP-DB-003`
* `RP-DB-004`
* `RP-DB-005`
* `RP-DB-006`

## Validation families the pack recommends

* db-integration-tests
* transaction-rollback-tests
* duplicate-delivery-replay-tests
* migration-expand-contract-validation

## Verdict vocabulary (from RDX canonical status)

The following verdicts are the ONLY strings allowed in an rdx-evidence.v1 envelope and MUST also be used by any TEA-side artefact that participates in the same verdict trail:

* `APPROVAL_REQUIRED`
* `BASELINE_BLOCKS_VALIDATION`
* `BASELINE_FAILURE_OBSERVED`
* `BLOCKED`
* `ENVIRONMENT_UNAVAILABLE`
* `EVIDENCE_REQUIRED`
* `FAIL`
* `NOT_APPLICABLE`
* `NOT_RUN`
* `PASS`
* `REGRESSION_FAILURE`
* `REGRESSION_FIXED`
* `REVIEW_REQUIRED`
* `TOOL_UNAVAILABLE`

## Contract for TEA workflows using this fragment

1. If the story description or diff matches the positive signals above and no negative signal or `story_tag` suppression applies, add this pack's `related_rule_ids` to the `active_packs[].rule_ids` field of the test-design artefact.
2. Do NOT paraphrase a rule ID. IDs are strings, not descriptions.
3. Emit the resulting artefact using verdict strings from the vocabulary above.
