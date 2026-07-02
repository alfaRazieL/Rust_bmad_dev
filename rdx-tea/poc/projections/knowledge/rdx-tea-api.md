---
pack_id: api
kb_section: 6.5
confidence_class: MEDIUM
activation_policy: STORY_TAG_REQUIRED
source_of_truth: tests/contracts/router-rules.json
---

# Rust risk pack: Public API, SemVer, and documentation

## When this pack activates

* Confidence: `MEDIUM`
* Policy: `STORY_TAG_REQUIRED`

### Positive signals (in diff/file):
* `pub fn`
* `pub struct`
* `pub enum`
* `pub trait`
* `pub use`
* `#[deprecated`
* `pub mod`

### Negative signals (suppress activation):
* private application or prototype
* pub(crate)/module-only visibility
* docs with no public contract change
* public-looking generated code that is not exported

### Path signals:
* `**/lib.rs`
* `**/src/lib.rs`

## Escalation triggers (require specialist review)
* published or publishable crate
* stable SDK or framework extension trait
* deprecation/removal/yank
* downstream breakage evidence

## Related canonical rule IDs

Every rule ID below is defined by the RDX KB and MUST NOT be renamed by any downstream consumer:

* `RP-API-001`
* `RP-API-002`
* `RP-API-003`
* `RP-API-004`
* `RP-API-005`
* `RP-API-006`
* `RP-API-007`
* `RP-API-008`
* `RP-API-009`
* `RP-API-010`
* `RP-API-011`
* `RP-API-012`
* `RP-API-013`
* `RP-API-014`
* `RP-API-015`
* `RP-API-016`
* `RP-API-017`
* `RP-API-018`

## Validation families the pack recommends

* api-review
* downstream-compile-checks
* semver-release-review
* rustdoc-doctest-review

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
