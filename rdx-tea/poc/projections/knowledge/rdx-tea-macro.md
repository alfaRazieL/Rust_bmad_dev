---
pack_id: macro
kb_section: 6.4
confidence_class: STRONG
activation_policy: AUTO_ACTIVATE
source_of_truth: tests/contracts/router-rules.json
---

# Rust risk pack: Macros, build scripts, and generated code

## When this pack activates

* Confidence: `STRONG`
* Policy: `AUTO_ACTIVATE`

### Positive signals (in diff/file):
* `macro_rules!`
* `proc_macro`
* `#[proc_macro_derive`
* `#[proc_macro_attribute`
* `build.rs`
* `include!(concat!(env!("OUT_DIR")`
* `OUT_DIR`
* `cargo:rerun-if`
* `bindgen::Builder`
* `cbindgen::Builder`

### Negative signals (suppress activation):
* ordinary functions/modules express the behavior
* generated artifacts not touched
* FFI-only generated bindings with no macro/build change

### Path signals:
* `**/build.rs`
* `**/*.rs`

## Escalation triggers (require specialist review)
* public macro API
* proc macros consuming user input
* cross-compilation-sensitive codegen
* checked-in generated artifacts

## Related canonical rule IDs

Every rule ID below is defined by the RDX KB and MUST NOT be renamed by any downstream consumer:

* `RP-MACRO-001`
* `RP-MACRO-002`
* `RP-MACRO-003`
* `RP-MACRO-004`

## Validation families the pack recommends

* expansion-review
* compile-pass-fail-macro-tests
* generated-artifact-drift-checks
* build-script-rerun-review

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
