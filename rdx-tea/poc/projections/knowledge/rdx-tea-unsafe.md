---
pack_id: unsafe
kb_section: 6.2
confidence_class: STRONG
activation_policy: AUTO_ACTIVATE
source_of_truth: tests/contracts/router-rules.json
---

# Rust risk pack: Unsafe and memory

## When this pack activates

* Confidence: `STRONG`
* Policy: `AUTO_ACTIVATE`

### Positive signals (in diff/file):
* `unsafe fn`
* `unsafe {`
* `unsafe impl`
* `MaybeUninit`
* `ManuallyDrop`
* `Pin<`
* `NonNull`
* `transmute`
* `AtomicUsize`
* `AtomicPtr`
* `asm!`
* `global_asm!`
* `naked_asm!`

### Negative signals (suppress activation):
* borrow-checker fix with no UB-relevant unsafe surface
* consuming reviewed safe abstraction without touching invariants

### Path signals:
* `**/*.rs`

## Escalation triggers (require specialist review)
* public safe abstraction backed by unsafe
* manual Send/Sync
* atomics/lock-free synchronization
* Miri/sanitizer coverage blocked

## Related canonical rule IDs

Every rule ID below is defined by the RDX KB and MUST NOT be renamed by any downstream consumer:

* `RP-UNSAFE-001`
* `RP-UNSAFE-002`
* `RP-UNSAFE-003`
* `RP-UNSAFE-004`
* `RP-UNSAFE-005`
* `RP-UNSAFE-006`
* `RP-UNSAFE-007`
* `RP-UNSAFE-008`
* `RP-UNSAFE-009`
* `RP-UNSAFE-010`
* `RP-UNSAFE-011`

## Validation families the pack recommends

* unsafe-review
* local-safety-contract-review
* compile-lint-gates
* miri-where-applicable
* loom-for-modeled-atomics

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
