# DEVELOPMENT_WINDOW_INDEX

Prompt §16 requires a self-contained plan for executing later stages in
separate fresh CLI contexts. This file is the operator's manual.

## Sequence

| Window | Stage | Prereqs (must be PASS at window entry) | Parallelisable? |
|---|---|---|---|
| W1 | Stage 01 | none | no (needs SOURCE_LOCK freeze) |
| W2 | Stage 02 | W1 green | no (extends generator) |
| W3 | Stage 03 | W1 green | yes with W4 |
| W4 | Stage 04 | W1 green + cargo toolchain | yes with W3 |
| W5 | Stage 05 | W2, W3, W4 green | no |
| W6 | Stage 06 | W5 sequential subset green | no |
| W7 | Stage 07 | W5, W6 green | no (large N-runs) |
| W8 | Stage 08 | G0..G7 PASS in FINAL_VERIFICATION | no (enforcement plane) |
| W9 | Stage 09 | G8 PASS | no |

Stages 03 and 04 are the only pair that can be worked in parallel; every
other pair has a hard dependency.

## What to hand to the next window

At the start of each new fresh-context session, load:

1. `rdx-tea/README.md` (navigation).
2. `rdx-tea/research/SOURCE_LOCK.md` — verify `d8140a25…` still matches
   `git rev-parse origin/main`. If not, first update SOURCE_LOCK and
   restart Stage 01.
3. `rdx-tea/architecture/ADR-001-INTEGRATION-ARCHITECTURE.md` — the
   authoritative design.
4. `rdx-tea/research/BUILDER_TEA_RECONCILIATION.md` — non-negotiable
   Variant D2 constraints (§3).
5. `rdx-tea/evidence/final/FINAL_VERIFICATION.json` — current gate
   status.
6. The specific stage file `rdx-tea/implementation-plan/stages/STAGE-NN-*.md`.
7. Memory file `feedback_rdx_tea_knowledge_first.md` — knowledge-plane-first
   ordering.

The stage file is the **entry contract**. It says exactly:
- Entry gate.
- Files allowed to touch.
- Tests to write first (RED expected).
- Implementation tasks.
- Exit gate (test-suite state + gate change in FINAL_VERIFICATION).
- Rollback instruction.

Nothing outside these files matters. Do not depend on prior chat
history.

## SHA + branch discipline

- Every window verifies:
  ```bash
  git rev-parse HEAD
  git branch --show-current   # must be rdx-tea-integration
  git rev-parse origin/main   # compare to SOURCE_LOCK.md §1
  git diff --check
  ```
- If the branch is dirty from a previous window's uncommitted work,
  the operator makes a decision before the new window begins.

## Commit boundary

At most **one logical commit per stage**, or a small number of related
commits (e.g. "add failing tests" + "make tests pass"). Do NOT batch
multiple stages into a single commit.

Commit message convention:
```
rdx-tea stage NN: <verb> <what>

- G-gate impact: ...
- Evidence: rdx-tea/evidence/logs/stageNN-*.log
```

## When a window fails

If a window cannot complete its stage (blocker discovered, test refuses
to be written, environment gap), do NOT partially commit. Instead:

1. Add a Blocker section to the stage file itself.
2. Update `FINAL_VERIFICATION.json` gate status to `INCONCLUSIVE` with a
   pointer to the blocker.
3. Add a `PROOF_COMPLETION_PLAN.md` entry proposing what needs to change
   before the stage is re-attempted.

Never inflate a `NOT_RUN` or `INCONCLUSIVE` to `PASS`.
