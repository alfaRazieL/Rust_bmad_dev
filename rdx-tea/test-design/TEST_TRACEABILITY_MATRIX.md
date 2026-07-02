# TEST_TRACEABILITY_MATRIX

Maps `CLAIM_EVIDENCE_MATRIX` claims to `TEST_CASES.yaml` case IDs and
FINAL_VERIFICATION gates.

| Claim | Test IDs | G-gate | Status |
|---|---|---|---|
| C1 status vocab | L0-STATUS-01, L1-PROJ-04 | G2 | PASS |
| C2 rule ID prefixes | L0-ROUTER-02, L0-RCM-01 | G2 | PASS |
| C3 12 packs canonical | L0-ROUTER-01 | G3 | PASS |
| C4 STORY_TAG set | L0-ROUTER-03 | G3 | PASS |
| C5 RDX suite green | BASELINE-RDX-01 | G0 | PASS |
| C6 no regression | BASELINE-RDX-01 (re-run) | G0 | PASS |
| C7 three-layer merge | (source-only; L4-INSTALL-* planned) | G1, G4 | PARTIAL: G1 PASS, G4 PLANNED |
| C8 persistent_facts glob | (source-only; L4-TEA-* planned) | G1, G5 | PARTIAL: G1 PASS, G5 PLANNED |
| C9 tea-index schema | (source-only; L1-INDEX-* implemented) | G1, G2 | PASS |
| C10 no subagent inherit | (design; L4-TEA-* subagent-mode planned) | G1, G6 | PARTIAL: G1 PASS, G6 PLANNED |
| C11 install path | (design in ADR-001; L4-INSTALL-* planned) | G4 | PLANNED |
| C12 scope filter | L2-{pack}-{shape} planned | G3, G7 | PLANNED |
| C13 verdict enum only | (design in ADR-001; L4/L5 planned) | G8 | BLOCKED |
| C14 deterministic generator | L0-PROJ-02, L1-PROJ-* determinism | G2 | PASS |
| C15 every pack has fragment + row | L0-PROJ-03, L0-PROJ-04 | G2, G3 | PASS |
| C16 skill roots DO NOT EDIT | (source-only guard) | G1 | PASS |
| C17 subagent seed lands | L4-TEA-*-subagent planned | G6 | PLANNED |
| C18 validator subcommand | (post-KP; L6 planned) | G8 | BLOCKED |
| C19 lifecycle safety | L4-INSTALL-* planned | G4 | PLANNED |
| C20 measurable improvement | L5-EVAL-* planned | G7 | PLANNED |
