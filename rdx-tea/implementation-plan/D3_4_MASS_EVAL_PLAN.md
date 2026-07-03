# D3.4 — Mass evaluation plan (precommitted, not executed)

Governs the eval expansion after D3.3's 3/3 smoke PASS. The pilot
(N=3 per arm) is defined here as a **prerequisite** to any mass run.
Mass N ≥ 10 / N ≥ 20 evals are **not** executed inside this repo —
they are budgeted here.

## Pilot (N=3 per arm) — first gate

- Scenarios (from `rdx-tea/evals/D3_3_PILOT_RUBRIC.yaml`):
  - `test-design-async` (positive)
  - `atdd-api-async` (positive)
  - `docs-only-rust-repo` (negative control)
- Arms:
  - **Baseline** — invoke `/bmad-testarch-test-design` (or `-atdd`)
    directly; no RDX-TEA overlay.
  - **Candidate** — invoke `/rdx-tea-test-design` (or `-atdd`); the
    D3.3 install-tree wrapper.
- N: 3 per (scenario × arm) → 18 runs.
- Randomised order: e.g. `A B B A A B ...` with `hashlib(seed=scenario)`
  precommitted in a `runs.json`.
- Model: haiku (cheap), `--max-budget-usd 2.00`, timeout 600 s.
- Isolation: disposable git worktree per run
  (`rdx-tea/live-harness/prepare_workspace.py`).
- Evidence per run: full `rdx-tea/evidence/live/pilot/<scenario>/<arm>/<n>/`
  with the D3.3 §7 bundle.

### Pilot decision (§9.6 of D3.3 prompt)

Grade all 18 samples blinded against
`rdx-tea/evals/D3_3_PILOT_RUBRIC.yaml`. Verdict enum:
`PILOT_SIGNAL_POSITIVE | PILOT_INCONCLUSIVE | PILOT_NEGATIVE | PILOT_INVALID`.

`PILOT_SIGNAL_POSITIVE` **does not** promote D3 to `PROVEN` — it only
unlocks the mass eval.

### Pilot cost estimate

- 18 runs × haiku × ~$0.30 = **≈ $5.40**
- Wall-clock: ~18 × 4 min = **~72 min** (serial); shorter with parallel.
- Reviewer/grader (deterministic detectors): negligible.
- Blinded LLM grader (optional Sonnet pass over the JSON extracts):
  ~18 × ~$0.10 = **~$1.80**.
- **Total pilot budget: ~$7.20 + ~1.5 h wall-clock.**

## Mass eval (only after PILOT_SIGNAL_POSITIVE)

- N ≥ 10 per (scenario × arm) for ordinary claims.
- N ≥ 20 per (scenario × arm) for critical claims (Router never
  skipped, no self-attested Cat-1 PASS, unsafe/FFI escalation, no
  irrelevant pack on negative controls, worker payload preservation).

### Mass cost estimate (upper bound with the six scenarios)

Assumptions per run at haiku pricing observed in D3.3 (≈ $0.30):

- 6 scenarios × 2 arms × 20 runs = 240 runs.
- 240 × $0.30 = **≈ $72** LLM budget.
- Plus blinded evaluator pass (≈ 240 × $0.10 at haiku) = **≈ $24**.
- **Total mass budget: ≈ $100.**
- Wall-clock: parallel `run_live.py` with 4 concurrent workers →
  ~240 × 4 min / 4 = **~4 h**.

## Implementation checklist

Before starting the pilot:

1. Land `run_live.py --scenario X --n N --arm baseline|candidate`
   orchestrator that internally calls `prepare_workspace`,
   `invoke_runtime`, `collect_evidence`, and post-hoc
   `finalize-run --verify-only` so `observed_mode` is direct.
2. Land a blinded rename step + grader that emits
   `rdx-tea/evals/results/pilot/<scenario>/<sample-id>.json`.
3. Add a `.github/workflows/rdx-tea-pilot.yml` **manual dispatch**
   workflow that runs the pilot from a machine with the auth
   credentials. Not on every push. Not on `main`.
4. Add regression tests that assert the blinded rename never leaks the
   arm into filenames or metadata.

## Do NOT

- Do not run mass eval before positive pilot.
- Do not use Opus for eval runs (cost policy).
- Do not merge pilot results into `main`.
- Do not include the ANTHROPIC_API_KEY in workflow files.
- Do not attempt to interpret a `PILOT_INCONCLUSIVE` result as
  positive.

## Ownership

- Pilot: RDX-TEA integrator, one shot.
- Mass: RDX-TEA integrator + independent reviewer, staged.
- MASTER_IMPLEMENTATION_PLAN.md still forbidden until mass eval
  produces a signed positive.
