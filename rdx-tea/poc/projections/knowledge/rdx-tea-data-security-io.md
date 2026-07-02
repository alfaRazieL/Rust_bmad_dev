---
pack_id: data-security-io
kb_section: 6.8
confidence_class: MEDIUM
activation_policy: AUTO_SUGGEST
source_of_truth: tests/contracts/router-rules.json
---

# Rust risk pack: Data, security, and external I/O

## When this pack activates

* Confidence: `MEDIUM`
* Policy: `AUTO_SUGGEST`

### Positive signals (in diff/file):
* `serde::`
* `Deserialize`
* `Serialize`
* `serde_json`
* `regex::`
* `rustls`
* `openssl`
* `ring::`
* `sha2::`
* `std::fs`
* `std::net`
* `std::process::Command`
* `reqwest`
* `hyper::`
* `tokio::net`

### Negative signals (suppress activation):
* purely internal trusted values with no boundary change
* compile-only generated types with no data contract
* DB/queue/migration behaviour belongs in db pack
* runtime config parsing belongs in time-config-client pack

### Path signals:
* `**/*.rs`

## Escalation triggers (require specialist review)
* auth, crypto, session tokens or key material
* user-supplied URL/path/subprocess/network target
* credentials or PII
* high-volume untrusted input
* archive expansion
* supply-chain/build-time dependency trust boundary

## Related canonical rule IDs

Every rule ID below is defined by the RDX KB and MUST NOT be renamed by any downstream consumer:

* `RP-DATA-001`
* `RP-DATA-002`
* `RP-DATA-003`
* `RP-DATA-004`
* `RP-DATA-005`
* `RP-DATA-006`
* `RP-DATA-007`
* `RP-DATA-008`
* `RP-DATA-009`
* `RP-SEC-001`
* `RP-SEC-002`
* `RP-SEC-003`
* `RP-SEC-004`
* `RP-SEC-005`
* `RP-SEC-006`
* `RP-IO-001`
* `RP-IO-002`
* `RP-IO-003`
* `RP-IO-004`
* `RP-IO-005`
* `RP-IO-006`
* `RP-IO-007`
* `RP-IO-008`

## Validation families the pack recommends

* boundary-and-negative-tests
* parser-fuzz-adversarial-tests
* redaction-tests
* security-review
* i-o-integration-and-fault-tests

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
