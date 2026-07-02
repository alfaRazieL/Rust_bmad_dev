---
pack_id: ffi
kb_section: 6.3
confidence_class: STRONG
activation_policy: AUTO_ACTIVATE
source_of_truth: tests/contracts/router-rules.json
---

# Rust risk pack: FFI and plugin ABI

## When this pack activates

* Confidence: `STRONG`
* Policy: `AUTO_ACTIVATE`

### Positive signals (in diff/file):
* `extern "C"`
* `extern "system"`
* `#[no_mangle]`
* `#[export_name]`
* `cdylib`
* `staticlib`
* `bindgen`
* `cbindgen`
* `libloading`
* `*const c_char`
* `*mut c_void`

### Negative signals (suppress activation):
* pure Rust module boundary
* public Rust API/SemVer with no foreign ABI
* ordinary dependency linking

### Path signals:
* `**/build.rs`
* `**/wrapper.h`
* `**/bindings.rs`

## Escalation triggers (require specialist review)
* cross-language unwinding
* callbacks with reentrancy/thread/unload concerns
* independently built plugins
* security-sensitive native boundary

## Related canonical rule IDs

Every rule ID below is defined by the RDX KB and MUST NOT be renamed by any downstream consumer:

* `RP-FFI-001`
* `RP-FFI-002`
* `RP-FFI-003`
* `RP-FFI-004`
* `RP-FFI-005`
* `RP-FFI-006`
* `RP-FFI-007`

## Validation families the pack recommends

* abi-layout-review
* header-or-binding-diff-review
* panic-containment-tests
* target-matrix-checks

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
