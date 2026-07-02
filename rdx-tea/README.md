# `rdx-tea/` — verification of RDX × BMAD TEA integration

This directory holds the entire research, PoC, test, evidence, architecture,
test-design and implementation-plan output for the task defined by the prompt
`RDX_TEA_variant_D_verification_and_implementation_plan_prompt.md`.

The prompt requires that we **do not** implement TEA integration yet. Instead,
we must independently re-prove (or refute) the previously-proposed
"Variant D — Hybrid Adapter" architecture, and only after the verdict is
`PROVEN` (or `PARTIALLY_PROVEN`, per §15) draft a stage-based implementation
plan.

Nothing in this folder edits production RDX files. All hashes, PoC code,
overlays, and evidence live under `rdx-tea/` (prompt §2.3).

---

## Working branch

- Branch: `rdx-tea-integration`
- Base SHA: `d8140a25f8166bf0ca5ce5fc19f7cb1bd06a3d6d`
- Locked in: [`research/SOURCE_LOCK.md`](research/SOURCE_LOCK.md)

Never merge or force-push. Never open a PR from this branch unless the user
explicitly asks (prompt §2.3 and §23).

---

## Reading order

1. **[`research/SOURCE_LOCK.md`](research/SOURCE_LOCK.md)** — the immutable
   record of the repository state we are working against. Everything else
   references SHAs and hashes recorded here.

2. **`research/CURRENT_RDX_1_1_BASELINE.md`** — Phase 0. What the existing RDX
   1.1 suite actually does today, how many tests it runs, how long, and what
   already-installed extension points exist. Written before any TEA-specific
   work begins. *(pending)*

3. **`research/BMAD_CORE_EXTENSION_SURFACE.md`** — Phase 1. Reverse-engineered
   map of the official BMAD Core / Builder / TEA extension points, verified
   against source. *(pending)*

4. **`research/BMAD_BUILDER_CONFIRMATION.md`** and
   **`research/BMAD_TEA_CONFIRMATION.md`** — Phase 2. Independent confirmations
   from the official Builder and TEA agents, plus their reconciliation. *(pending)*

5. **`architecture/ADR-001-INTEGRATION-ARCHITECTURE.md`** — Phase 3. The
   verifiable candidate (Variant D, or an amended D2 if the review demands it).
   *(pending)*

6. **`poc/`** and **`tests/`** — Phase 4. Failing-tests-first TDD proof of the
   candidate. Every executed run is captured under `evidence/`. *(pending)*

7. **`research/VARIANT_D_VERIFICATION_REPORT.md`** and
   **`research/FINAL_ARCHITECTURE_VERDICT.md`** — one of `PROVEN` /
   `PARTIALLY_PROVEN` / `NOT_PROVEN` / `NOT_FEASIBLE`. *(pending)*

8. **`evidence/final/FINAL_VERIFICATION.json`** — machine-readable G0..G11
   gate status. *(pending)*

9. **`implementation-plan/`** — only populated to production quality if the
   verdict is `PROVEN` (prompt §15). *(pending)*

## Reproduce this workspace

```
mkdir -p /Users/m33tball/bmad_module_builder/rdx-workspace
cd    /Users/m33tball/bmad_module_builder/rdx-workspace
git clone https://github.com/alfaRazieL/Rust_bmad_dev.git
cd Rust_bmad_dev
git fetch origin --prune
# Verify SOURCE_LOCK §1 base SHA matches what you observe:
git rev-parse origin/main
git switch main
git pull --ff-only origin main
git switch -c rdx-tea-integration
```

## D3 update (2026-07-02)

Verdict upgraded from `PARTIALLY_PROVEN` (D2) to **`D3_PARTIALLY_PROVEN`**
under the amended Variant D3 architecture. Read in order:

1. `research/D3_CORRECTION_AUDIT.md`
2. `research/D3_SOURCE_LOCK_ADDENDUM.md`
3. `architecture/ADR-002-SEQUENTIAL-ACTIVE-BUNDLE.md`
4. `architecture/WORKFLOW_OBLIGATION_MATRIX.csv`
5. `architecture/rdx-tea-run.v1.schema.json`
6. `research/D3_VARIANT_VERIFICATION_REPORT.md`
7. `research/D3_CLAIM_EVIDENCE_MATRIX.md`
8. `evidence/final/D3_FINAL_VERIFICATION.json`
9. `implementation-plan/D3_PROOF_PLAN.md`

The D2-era `implementation-plan/PROOF_COMPLETION_PLAN.md` is retained
as SUPERSEDED.

## Progress at checkpoint

| Phase | Doc | Status |
|---|---|---|
| Source lock | `research/SOURCE_LOCK.md` | DONE |
| 0 — RDX baseline | `research/CURRENT_RDX_1_1_BASELINE.md` | DONE — **307/0/0 in 15.09 s** |
| 1 — Extension surface | `research/BMAD_CORE_EXTENSION_SURFACE.md` (+ §11 addendum) | DONE |
| 2a — Builder review | `evidence/screenshots-or-transcripts/phase2-builder-review.md` | DONE |
| 2b — TEA review | `evidence/screenshots-or-transcripts/phase2-tea-review.md` | DONE |
| 2c — Reconciliation | `research/BUILDER_TEA_RECONCILIATION.md` | DONE |
| 3 — Candidate (D2) | `architecture/ADR-001-INTEGRATION-ARCHITECTURE.md` | DONE |
| 4 — TDD proof, L0+L1 | `tests/contracts/`, `tests/unit/`, `poc/adapter/projection.py` | **32/32 green** |
| 4 — TDD proof, L2..L8 | see PROOF_COMPLETION_PLAN stages 02..09 | NOT_RUN |
| Verdict | `research/FINAL_ARCHITECTURE_VERDICT.md`, `evidence/final/FINAL_VERIFICATION.json` | `PARTIALLY_PROVEN` |
| Implementation plan | `implementation-plan/PROOF_COMPLETION_PLAN.md` + `stages/` | Drafts issued |

## Summary of runtime evidence at checkpoint

- 339 pytest nodes green (307 RDX baseline + 13 L0 projection + 19 L1 projection unit).
- 0 failed / 0 skipped / 0 warnings under isolated Python 3.14.4 venv.
- Byte-identical re-run of the projection generator across two invocations
  (hashes in `evidence/hashes/PHASE4_projection_output.txt`).
- Two independent subagent reviews (Builder + TEA) grounded in host BMAD
  6.8.0 source ended with 16 blocking objections total; all 16 are
  addressed in ADR-001 (Variant D2) or explicitly deferred to
  PROOF_COMPLETION_PLAN.

## Runtime evidence NOT collected at checkpoint

- No real TEA workflow was executed (G5).
- No subagent payload spy (G6).
- No lifecycle install/uninstall test (G4).
- No behavioural baseline vs candidate eval (G7).
- Enforcement-plane gates (G8..G11) blocked per knowledge-plane-first memo.

Full gate matrix: `evidence/final/FINAL_VERIFICATION.json`.
