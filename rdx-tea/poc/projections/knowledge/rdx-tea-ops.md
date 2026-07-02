---
pack_id: ops
kb_section: 6.10
confidence_class: WEAK
activation_policy: STORY_TAG_REQUIRED
source_of_truth: tests/contracts/router-rules.json
---

# Rust risk pack: Operations, observability, and rollback

## When this pack activates

* Confidence: `WEAK`
* Policy: `STORY_TAG_REQUIRED`

### Positive signals (in diff/file):
* `tracing::`
* `tracing_subscriber`
* `prometheus::`
* `metrics::`
* `opentelemetry`
* `signal::ctrl_c`
* `tokio::signal`
* `health_check`
* `readiness`
* `liveness`

### Negative signals (suppress activation):
* local prototype, one-shot CLI, library-only change with no deployment/operator contract
* ordinary debug logging with no telemetry pipeline
* production observability not activated merely because code has main
* generic cleanup covered by CORE-009

### Path signals:
* `**/k8s/**`
* `**/deploy/**`
* `**/Dockerfile`

## Escalation triggers (require specialist review)
* production rollout or rollback risk
* telemetry can block request paths or grow unbounded
* high-cardinality or sensitive metrics
* signal/shutdown affects in-flight work

## Related canonical rule IDs

Every rule ID below is defined by the RDX KB and MUST NOT be renamed by any downstream consumer:

* `RP-OPS-001`
* `RP-OPS-002`
* `RP-OPS-003`
* `RP-OPS-004`
* `RP-OPS-005`
* `RP-OPS-006`
* `RP-OPS-007`
* `RP-OPS-008`
* `RP-OPS-009`

## Validation families the pack recommends

* ops-review
* service-integration-tests
* shutdown-drain-tests
* telemetry-cardinality-redaction-checks
* release-rollback-gate-review

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
