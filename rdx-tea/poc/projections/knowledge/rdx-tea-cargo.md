---
pack_id: cargo
kb_section: 6.6
confidence_class: STRONG
activation_policy: AUTO_ACTIVATE
source_of_truth: tests/contracts/router-rules.json
---

# Rust risk pack: Cargo, features, workspace, toolchain, and dependencies

## When this pack activates

* Confidence: `STRONG`
* Policy: `AUTO_ACTIVATE`

### Positive signals (in diff/file):
* `Cargo.toml`
* `Cargo.lock`
* `rust-toolchain`
* `rust-toolchain.toml`
* `[features]`
* `[workspace]`
* `[patch.`
* `[replace]`
* `rust-version`
* `resolver = `

### Negative signals (suppress activation):
* code-only patch with no manifest/feature/dep/lockfile/toolchain impact
* cargo profile-only tuning
* duplicate resolved versions without identity/feature/size/policy evidence

### Path signals:
* `**/Cargo.toml`
* `**/Cargo.lock`
* `rust-toolchain`
* `rust-toolchain.toml`
* `.cargo/config.toml`

## Escalation triggers (require specialist review)
* toolchain/resolver change
* workspace-wide dependency policy change
* native links / -sys boundary
* MSRV or target matrix change
* dependency compromise or yanked-only resolution

## Related canonical rule IDs

Every rule ID below is defined by the RDX KB and MUST NOT be renamed by any downstream consumer:

* `RP-CARGO-001`
* `RP-CARGO-002`
* `RP-CARGO-003`
* `RP-CARGO-004`
* `RP-CARGO-005`
* `RP-CARGO-006`
* `RP-CARGO-007`
* `RP-CARGO-008`
* `RP-CARGO-009`

## Validation families the pack recommends

* manifest-lockfile-review
* resolved-graph-review
* feature-matrix-checks
* target-msrv-checks
* lint-policy-checks

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
