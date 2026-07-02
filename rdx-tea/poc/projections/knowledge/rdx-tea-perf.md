---
pack_id: perf
kb_section: 6.11
confidence_class: WEAK
activation_policy: STORY_TAG_REQUIRED
source_of_truth: tests/contracts/router-rules.json
---

# Rust risk pack: Performance, portability, no_std, WASM, and embedded

## When this pack activates

* Confidence: `WEAK`
* Policy: `STORY_TAG_REQUIRED`

### Positive signals (in diff/file):
* `#[no_std]`
* `no_std`
* `wasm32`
* `target_arch`
* `target_feature`
* `criterion::`
* `iai::`
* `std::simd`
* `core::arch`
* `GlobalAlloc`

### Negative signals (suppress activation):
* cosmetic style refactor
* cold code with no performance claim
* correctness-only bugfix unless it changes a measured path
* cookbook micro-optimisations without baseline evidence

### Path signals:
* `benches/**`
* `**/*.bench.rs`

## Escalation triggers (require specialist review)
* hard SLA or resource budget
* no_std/embedded/WASM target support
* unsafe/SIMD/intrinsics
* custom allocator
* benchmark numbers drive acceptance

## Related canonical rule IDs

Every rule ID below is defined by the RDX KB and MUST NOT be renamed by any downstream consumer:

* `RP-PERF-001`
* `RP-PERF-002`
* `RP-PERF-003`
* `RP-PERF-004`
* `RP-PERF-005`
* `RP-PERF-006`
* `RP-PERF-007`
* `RP-PERF-008`

## Validation families the pack recommends

* baseline-and-before-after-benchmarks
* profiler-allocation-codegen-evidence
* target-matrix-or-cross-compilation-checks
* portability-review

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
