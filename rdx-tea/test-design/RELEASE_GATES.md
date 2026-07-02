# RELEASE_GATES

Numeric thresholds. Referenced by G0..G11 gates in
`rdx-tea/evidence/final/FINAL_VERIFICATION.json`.

Sourced from prompt §21.

| # | Threshold | Value | Gate | Status |
|---|---|---|---|---|
| T1 | Deterministic contract/unit/integration mandatory tests | 100% PASS | G2, G3 | 32/32 PASS at checkpoint |
| T2 | Existing RDX regression | 100% of baseline preserved | G0 | 307/307 preserved (339 total after adapter tests) |
| T3 | Canonical projection drift | 0 | G2 | 0 observed |
| T4 | Invalid TOML outputs | 0 | G4 | pending (Stage 4) |
| T5 | Lost canonical rule IDs | 0 | G2, G3 | 0 observed |
| T6 | Cat-1 self-attested PASS accepted | 0 | G8 | pending (Stage 8) |
| T7 | Unsafe/FFI missing escalation | 0 | G3, G5 | pending (Stage 5, Stage 7) |
| T8 | Stale approval accepted | 0 | G8, G9 | pending (Stage 8) |
| T9 | Critical tamper cases caught | 100% (24/24) | G10 | pending (Stage 8) |
| T10 | Negative-control irrelevant-pack false positive | ≤ 5% | G7 | pending (Stage 7) |
| T11 | Strong-positive Router false negative | ≤ 2% | G3, G7 | pending (Stage 2 + Stage 7) |
| T12 | Worker payload critical preservation | ≥ 95% | G6 | pending (Stage 6) |
| T13 | Behavioural improvement over baseline | Statistically + practically explainable | G7 | pending (Stage 7) |
| T14 | Context overhead | Measured, not asserted | G7 | pending (Stage 7) |

Failure of any threshold blocks the enforcement-plane gates
(G8..G11). PROOF_COMPLETION_PLAN sequences the stages accordingly.
