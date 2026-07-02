# FINAL_ARCHITECTURE_VERDICT

**Verdict:** `PARTIALLY_PROVEN`
**Proven architecture:** Variant D2 (per ADR-001) — an amendment of the
original Variant D that survives both independent Phase-2 reviews.

## Why not `PROVEN`

Per prompt §14 last paragraph, `PROVEN` is only permitted when every
mandatory gate G0..G11 is PASS. The current evidence table
(`rdx-tea/evidence/final/FINAL_VERIFICATION.json`) has:

- G0 PASS (baseline 307/0/0, still green after 32 new tests).
- G1 PASS (both Builder and TEA independent reviews confirm the extension
  surface).
- G2 PASS (13 L0 + 19 L1 tests; determinism; hash-stability).
- G3 PARTIAL_PASS (contract-level parity proven; fixture replay
  positive/negative/ambiguous not yet written for the projection).
- G4..G7 NOT_RUN — no real TEA workflow invocation, no subagent payload
  spy, no lifecycle install/uninstall, no behavioural eval.
- G8..G11 BLOCKED behind their knowledge-plane prerequisites per the
  knowledge-plane-first memo.

`NOT_RUN` and `BLOCKED` are explicitly not-promotable to PASS
(prompt §14 last paragraph).

## Why not `NOT_PROVEN` / `NOT_FEASIBLE`

The Phase-1 source verification and Phase-2 independent reviews
establish that:

1. An official extension surface exists (three-layer TOML merge,
   `persistent_facts` glob loader, workflow-local resources, subagent
   activation contract).
2. A deterministic projection generator can preserve canonical rule IDs,
   status vocabulary, and Router semantics — proven by the 32 green
   L0/L1 tests.
3. The remaining risks (subagent propagation seam; per-workflow scope;
   `rdx-evidence.v1` compatibility) each have concrete, verifiable
   answers documented in ADR-001 and are testable in isolated stages.

No source-level contradiction was found that would make integration
infeasible. The design is not disproven; it is *not yet* proven.

## Rejected / modified parts of Variant D

Preserved from Variant D:

- Canonical RDX contracts as the projection generator's only inputs.
- Deterministic projection generator emitting fragments + index.
- `persistent_facts` glob as the injection channel.
- `_bmad/custom/**.toml` overlays as the official override mechanism.
- `rdx-evidence.v1` schema as the RDX-side envelope target.
- MODE_0..MODE_4 tie-in on the enforcement side.

Rejected in Variant D → replaced in Variant D2:

- Agent-level `bmad-tea` overlay for Rust knowledge (both reviews).
- Uniform 8-way overlay across all `bmad-testarch-*` (both reviews).
- Parallel RDX-owned `rdx-tea-index.csv` alongside skill-owned one
  (TEA §10(b)).
- Assumption that `persistent_facts` propagate into subagents
  (both reviews).
- Writing generated files into skill-owned `resources/knowledge/`
  (both reviews).
- Full `rdx-evidence.v1` schema fusion for TEA artefacts
  (TEA §6; Builder §5).

Modified:

- Install path for generated fragments: `_bmad/rdx-tea/knowledge/…`
  (Builder Q7 wins over TEA §10(e)).
- Per-workflow scope filter: only rules whose scope-of-concern
  intersects the workflow (Builder Q9 + TEA §7 union table in
  `BUILDER_TEA_RECONCILIATION §3.3`).
- Subagent seed mechanism: adapter-owned per-workflow seed fragment
  registered via `activation_steps_prepend` (ADR-001 §7).

## Confirmation trail

- Builder (independent subagent, fresh context):
  `rdx-tea/evidence/screenshots-or-transcripts/phase2-builder-review.md`
  — 10 answers with source line refs; 6 blocking objections.
- TEA (independent subagent, fresh context):
  `rdx-tea/evidence/screenshots-or-transcripts/phase2-tea-review.md`
  — 10 answers with source line refs; 10 blocking objections.
- Reconciliation of the two, plus the single disagreement (install path
  `_bmad/rdx-tea/` vs `_bmad/custom/rdx-tea/`):
  `rdx-tea/research/BUILDER_TEA_RECONCILIATION.md`.

## Implementation plan status

Per prompt §15 second sub-section:

- Full MASTER_IMPLEMENTATION_PLAN.md is **not** issued (verdict is not
  `PROVEN`).
- `rdx-tea/implementation-plan/PROOF_COMPLETION_PLAN.md` closes the
  NOT_RUN gates first.
- Draft production stages remain in `rdx-tea/implementation-plan/stages/`
  in a clearly-marked BLOCKED state.
