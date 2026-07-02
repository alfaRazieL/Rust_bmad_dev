---
pack_id: async
kb_section: 6.1
confidence_class: STRONG
activation_policy: AUTO_ACTIVATE
source_of_truth: tests/contracts/router-rules.json
---

# Rust risk pack: Async and concurrency

## When this pack activates

* Confidence: `STRONG`
* Policy: `AUTO_ACTIVATE`

### Positive signals (in diff/file):
* `async fn`
* `.await`
* `impl Future`
* `impl Stream`
* `tokio::spawn`
* `select!`
* `channel`
* `mpsc::`
* `JoinHandle`
* `Mutex across .await`

### Negative signals (suppress activation):
* purely synchronous code
* docs-only mention of async
* no changed await or task lifecycle

### Path signals:
* `**/*.rs`

## Escalation triggers (require specialist review)
* custom Future/Waker/executor
* lock-free or atomic synchronization
* public async trait/runtime API

## Related canonical rule IDs

Every rule ID below is defined by the RDX KB and MUST NOT be renamed by any downstream consumer:

* `RP-ASYNC-001`
* `RP-ASYNC-002`
* `RP-ASYNC-003`
* `RP-ASYNC-004`
* `RP-ASYNC-005`
* `RP-ASYNC-006`
* `RP-ASYNC-007`
* `RP-ASYNC-008`
* `RP-ASYNC-009`

## Validation families the pack recommends

* compile-at-spawn-boundaries
* async-behavior-tests
* cancellation-shutdown-tests
* concurrency-review

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
