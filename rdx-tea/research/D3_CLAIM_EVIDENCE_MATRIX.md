# D3_CLAIM_EVIDENCE_MATRIX

Supersedes `CLAIM_EVIDENCE_MATRIX.md` (D2 era). Rows below reflect the
runtime work in Phases A–E + H of the D3 proof. Confidence uses:
HIGH (source + upstream verified + green runtime test),
MEDIUM (source + verified but limited coverage),
LOW (design only), UNSUPPORTED_BY_DESIGN (explicit non-goal).

| # | Claim | Source | Runtime | Confidence | Anchor |
|---|---|---|---|---|---|
| C1 | 14-verdict + 3-severity vocabulary preserved (EVIDENCE_REQUIRED, not EVIDENCE_MISSING) | tests/contracts/status-definitions.json | test_l0_status_vocabulary_complete PASS | HIGH | G2, G3 |
| C2 | Canonical rule ID prefixes CORE/RP/GOV, no RUST-* | rule-check-map.json + KB | test_l0_router_rule_ids_prefixes + test_l1_parser_v2_no_rust_prefix_ids PASS | HIGH | G2 |
| C3 | Semantic bodies of 138 rules recovered verbatim | KB + rdx_parser.py | test_l1_parser_v2_every_rule_has_mandatory_fields + test_l1_parser_v2_rp_async_005_is_semantic PASS | HIGH | G2 semantic (NEW) |
| C4 | Router replay preserved (12 packs, activation, story-tag policy) | tests/contracts/router-rules.json | test_l0_router_packs_canonical PASS + test_l2_d07_router_parity_with_rdx_validator PASS | HIGH | G3 |
| C5 | RDX baseline suite still green under isolated venv | tests/ | 307/307 in 15.09s + 397/397 with adapter tests | HIGH | G0 |
| C6 | Upstream BMAD 6.8.0 / TEA v1.19.0 SHAs locked, host matches tags | rdx-tea/research/D3_SOURCE_LOCK_ADDENDUM.md | D3_UPSTREAM_LOCK.txt shasum comparison | HIGH | G1 |
| C7 | Real upstream resolve_customization.py merges D3 overlay correctly | upstream v6.8.0 script | 9 test_l4_upstream_customization tests PASS | HIGH | G1 |
| C8 | activation_steps_prepend runs BEFORE persistent_facts | upstream test-design/SKILL.md Step 2 → 3 | test_l4_c01 + test_l4_c02 PASS | HIGH | G1 seam A |
| C9 | on_complete runs as final terminal instruction after output | upstream test-design/steps-c/step-05-generate-output.md:232-236 | test_l4_c03 PASS + test_l4_e01 PASS | HIGH | G1 seam B |
| C10 | User `.user.toml` overlay is preserved by merge | resolver source | test_l4_c05 + test_l4_h03 PASS | HIGH | G4 partial |
| C11 | No skill-root modifications after resolver run | resolver source | test_l4_c07 PASS | HIGH | G1 |
| C12 | Bundle is deterministic byte-identical (single + cross-process) | prepare.py | test_l2_d05 + test_l7_f07 PASS | HIGH | G3 |
| C13 | Bundle atomically replaced on rerun, no `.tmp` leftover | prepare.py + os.replace | test_l2_d12 + test_l4_h02 + test_l4_h04 PASS | HIGH | G3, G4 partial |
| C14 | Non-Rust diff produces empty bundle | Router | test_l2_d03 + test_l7_f04 PASS | HIGH | G3 |
| C15 | Doc-only diff excludes async pack | Router | test_l2_d02 PASS | HIGH | G3 |
| C16 | Obligation matrix filters (trace never carries unsafe) | ADR-002 §4 + BUILDER_TEA_RECONCILIATION §3.3 | test_l2_d09 PASS | HIGH | G3 |
| C17 | Bundle carries no RDX verdict vocabulary | prepare.py + schema | test_l2_d04 + test_l7_f05 PASS | HIGH | G8 |
| C18 | Sidecar schema forbids verdict fields (additionalProperties: false) | rdx-tea-run.v1.schema.json | test_l4_e01 validates + test_l4_e01 asserts no banned field | HIGH | G8 partial |
| C19 | Binder fails closed without prepare manifest | binder.py | test_l7_f01 + test_l4_e04 PASS | HIGH | G8 partial, G10 partial |
| C20 | Bundle hash change is detectable after binding (tamper detection) | binder projection_hash | test_l7_f02 PASS | HIGH | G10 partial |
| C21 | Artefact hash change is detectable after binding | binder artifact_sha256 | test_l4_e02 + test_l7_f03 PASS | HIGH | G10 partial |
| C22 | Sequential mode is recorded verbatim in manifest AND sidecar | prepare.py + binder.py | test_l4_e05 PASS | HIGH | G6 v1 |
| C23 | Legacy parallel rdx-tea-index.csv NOT consumed | prepare.py source scan | test_l7_f06 PASS | HIGH | correction |
| C24 | Unknown workflow yields empty active_packs (fails safe) | prepare.py obligation matrix | test_l7_f08 PASS | HIGH | G10 partial |
| C25 | Subagent context does NOT inherit persistent_facts | upstream code + Phase-2 reviews | (not tested — non-goal for v1) | UNSUPPORTED_BY_DESIGN | G6F |
| C26 | Behavioural improvement over baseline | design (D3_PROOF_PLAN) | NOT_RUN | LOW | G7 |
| C27 | RDX validator can derive rdx-evidence.v1 envelope from sidecar | design (ADR-002 §9-§11) | NOT_RUN | LOW | G8 remainder |
| C28 | MODE_0..MODE_4 tie-in has real behavioural differences | design | NOT_RUN | LOW | G9 |
| C29 | Fresh install / uninstall / rollback is safe | design | NOT_RUN | LOW | G4 remainder |
| C30 | Hash-mismatch upstream upgrade fails closed | design | NOT_RUN | LOW | G11 remainder |
| C31 | Prepare + binder deterministic across two subprocess invocations | prepare.py + binder.py | test_l7_f07 PASS | HIGH | G3, G10 |

## Summary

- HIGH-confidence claims: 24 (C1–C24).
- UNSUPPORTED_BY_DESIGN: 1 (C25 / G6F).
- LOW-confidence design-only: 5 (C26–C30).
- HIGH-confidence additional: 1 (C31).

D3_PROVEN would require C26–C30 to reach HIGH via runtime evidence.
Current status is `D3_PARTIALLY_PROVEN`.
