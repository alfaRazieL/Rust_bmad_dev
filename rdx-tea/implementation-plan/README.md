# `implementation-plan/` — reader's guide

Verdict at checkpoint = `PARTIALLY_PROVEN` (see
`rdx-tea/research/FINAL_ARCHITECTURE_VERDICT.md`). Per prompt §15
second sub-section, this folder emits a proof-completion plan, not a
full production plan. Production stages remain as stubs until every
knowledge-plane gate closes.

Read order:

1. `PROOF_COMPLETION_PLAN.md` — the master sequence of nine stages that
   close the `NOT_RUN` / `BLOCKED` gates.
2. `DEVELOPMENT_WINDOW_INDEX.md` — how to run the stages in separate
   fresh CLI contexts.
3. `GLOBAL_GUARDRAILS.md` — the invariant rules every stage must obey.
4. `stages/STAGE-NN-*.md` — self-contained stubs for each of the nine
   stages. Each is intentionally short; the meat lives in
   PROOF_COMPLETION_PLAN.
5. `FINAL_ACCEPTANCE_CHECKLIST.md` — the boxes that must be checked
   before verdict is promotable to `PROVEN`.

## Stages at a glance

| # | Owning gate(s) | Depends on |
|---|---|---|
| 01 | G0, G1 (kept) + SOURCE_LOCK coverage | — |
| 02 | G3 → PASS | 01 |
| 03 | G4 → PASS | 01 |
| 04 | G3 refinement + G5 pre-req | 01 |
| 05 | G5 → PASS | 02, 03, 04 |
| 06 | G6 → PASS | 05 |
| 07 | G7 → PASS | 05, 06 |
| 08 | G8, G10 → PASS | G0..G7 all PASS |
| 09 | G9, G11 → PASS; verdict promotable | 08 |
