---
pack_id: testing
kb_section: 6.7
confidence_class: MEDIUM
activation_policy: STORY_TAG_REQUIRED
source_of_truth: tests/contracts/router-rules.json
---

# Rust risk pack: Testing beyond the core loop

## When this pack activates

* Confidence: `MEDIUM`
* Policy: `STORY_TAG_REQUIRED`

### Positive signals (in diff/file):
* `proptest`
* `quickcheck`
* `cargo fuzz`
* `loom::`
* `miri`
* `compile_fail`
* `#[should_panic`

### Negative signals (suppress activation):
* ordinary compile + behavior tests already cover acceptance
* tool names appear only in docs or CI comments
* advanced test tools loaded as ritual

### Path signals:
* `fuzz/**`
* `tests/loom/**`
* `**/compile_fail/**`

## Escalation triggers (require specialist review)
* unsafe or FFI memory boundary
* lock-free/schedule-sensitive concurrency
* parser/security boundary
* production incident repro
* high-assurance/regulatory scope

## Related canonical rule IDs

Every rule ID below is defined by the RDX KB and MUST NOT be renamed by any downstream consumer:

* `RP-TEST-001`
* `RP-TEST-002`
* `RP-TEST-003`
* `RP-TEST-004`

## Validation families the pack recommends

* risk-based-validation-plan
* deterministic-regression-corpus
* fuzz-property-tests
* compile-fail-tests
* miri-loom-sanitizer-evidence

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
