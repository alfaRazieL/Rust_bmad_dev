---
pack_id: time-config-client
kb_section: 6.10
confidence_class: MEDIUM
activation_policy: AUTO_SUGGEST
source_of_truth: tests/contracts/router-rules.json
---

# Rust risk pack: Time, configuration, and API clients

## When this pack activates

* Confidence: `MEDIUM`
* Policy: `AUTO_SUGGEST`

### Positive signals (in diff/file):
* `Duration::from_`
* `Instant::now`
* `SystemTime::now`
* `tokio::time::sleep`
* `tokio::time::timeout`
* `retry_backoff`
* `config::Config`
* `figment`
* `envy::`
* `notify::`
* `reqwest::Client`
* `hyper::client`

### Negative signals (suppress activation):
* pure computation with no clock/config/external-client boundary
* one-off constant config with no validation/reload behaviour
* ordinary unit tests with no timing oracle
* API client mention with no changed call/retry/deadline behaviour

### Path signals:
* `**/config.rs`
* `**/client.rs`

## Escalation triggers (require specialist review)
* dynamic config reload
* credential/cert hot reload
* process-wide env mutation in tests/runtime
* external API mutation retries
* deadline/cancellation affects correctness

## Related canonical rule IDs

Every rule ID below is defined by the RDX KB and MUST NOT be renamed by any downstream consumer:

* `RP-TIME-001`
* `RP-TIME-002`
* `RP-TIME-003`
* `RP-TIME-004`
* `RP-TIME-005`
* `RP-TIME-006`
* `RP-TIME-007`

## Validation families the pack recommends

* config-validation-reload-tests
* timeout-retry-backoff-tests
* deterministic-time-tests
* environment-isolation-review
* api-client-fault-tests

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
