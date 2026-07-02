# MASTER_TEST_STRATEGY

**Scope:** Variant D2 (ADR-001) verification and, ultimately, its
production RDX-TEA adapter.

**Rule of ordering:** knowledge-plane before enforcement-plane
(memory `feedback_rdx_tea_knowledge_first`). Concretely: L0–L5 knowledge
tests must be green before L6–L8 enforcement tests are attempted.

## 1. Layer catalog (built on RDX 1.1 L0..L8)

| Layer | Purpose | Currently green (Phase 4 checkpoint) | Planned |
|---|---|---:|---:|
| L0 static contracts | Canonical hashes, IDs, status vocab, projection index, source→projection map, no manual Router drift | 13 | 40+ (add L0 fixture-level integrity checks per PROOF_COMPLETION_PLAN Stage 1) |
| L1 unit | RDX parser, IR builder, projection generator, Router adapter, tier classifier, front-matter parser | 19 | 60+ (parser round-trip, RP-* extractor, KB-heading extractor, front-matter validator, artefact reader, subagent-seed formatter, per-workflow scope filter) |
| L2 fixtures per Router pack | Positive/negative/ambiguous fixtures for each of 12 packs, 13 shapes per prompt §12 L2 | 0 (existing RDX `tests/unit/validator/test_l2_router_packs.py::26 nodes` used as baseline evidence, not projection-side) | 12 × 13 = 156, subset of which will be re-used from RDX fixtures |
| L3 real Rust projects | Safe lib, CLI, async service, workspace, unsafe crate, FFI crate, proc-macro / build script, public API / SemVer, feature matrix / MSRV, serde / untrusted input, DB / distributed, time / retry, ops / tracing, perf / no_std / WASM, green + intentionally broken controls | 0 | 15 canonical projects × 2 verdicts (green + red) = 30 |
| L4 BMAD + TEA integration | Real workflow runs of all 8 testarch skills — sequential, subagent, agent-team, fallback | 0 | 8 × 3 modes = 24 sanity runs + 8 install/uninstall smoke |
| L5 behavioural evals | Baseline vs candidate; rule recall / precision / FP rate / FN rate / irrelevant-pack loading / Router compliance / test-strategy quality / Rust command correctness / negative coverage / traceability / self-attested Cat-1 PASS / subagent knowledge loss / context cost / runtime | 0 | 10 grading criteria × N=10 per critical + N=20 per critical claim ⇒ 100+ (see BEHAVIORAL_EVAL_PLAN.md) |
| L6 hook / CI | pre-push hook + `rdx-gate.yml` reused + `rdx-tea-gate.yml` new; trust boundary; fork/PR threat model | 0 (baseline `tests/ci/` still green) | 15 new + reuse 11 baseline |
| L7 mutation / adversarial | The 24 scenarios in prompt §12 L7 | 0 (baseline `tests/mutation/` still green) | 24 new + reuse 31 baseline |
| L8 judgment / governance | Cat-3 scope, Cat-4 approval binding, unsafe/FFI/security ownership | 0 (baseline `tests/evals/` + `tests/integration/cat4/` still green) | 8 new + reuse 46 baseline |

Total target for production: ≥ 300 meaningful test cases (prompt §11.2).
The count in `TEST_CASES.yaml` today is dominated by baseline + Phase-4
L0/L1 (339); the remaining ~ 300 are enumerated as PLANNED with owner
stage and status.

## 2. Test discipline

- **Test-first:** every planned test has an ID and a red state before
  code is written (prompt §11.1).
- **Test-inflation caveat:** parametrized invocations are counted
  separately from unique test intents (prompt §11.2). See
  `TEST_CASES.yaml` `parametrized_invocations` field.
- **Evidence:** every executed test saves command, cwd, env,
  git SHA, start/end time, exit code, stdout, stderr, artefact hashes
  under `rdx-tea/evidence/` (prompt §20).
- **Determinism:** knowledge-plane tests must be idempotent — the
  projection generator must produce byte-identical output across runs.
- **Independence:** each subagent-review or eval run happens in a fresh
  context that has not seen prior verdicts (prompt §9.3).
- **Statistical thresholds:** critical behavioural claims require
  N ≥ 20 repeated runs; ordinary claims N ≥ 10 (prompt §12 L5).

## 3. Traceability

- `TEST_TRACEABILITY_MATRIX.md` maps every claim in CLAIM_EVIDENCE_MATRIX
  to test IDs.
- `TEST_CASES.yaml` is the authoritative test-case catalog (planned +
  implemented).
- Each PROOF_COMPLETION_PLAN stage owns a range of `TEST_CASES.yaml`
  IDs (see stage headers).

## 4. Release gates

`RELEASE_GATES.md` lists the numeric thresholds per prompt §21:

- Deterministic L0/L1/L2 tests: 100% PASS
- Existing RDX regression: 100% of baseline preserved
- Canonical projection drift: 0
- Invalid TOML outputs: 0
- Lost canonical rule IDs: 0
- Self-attested Cat-1 PASS accepted: 0
- Unsafe / FFI missing escalation: 0
- Stale approval accepted: 0
- Critical tamper cases caught: 100%
- Negative-control irrelevant-pack false positive: ≤ 5%
- Strong-positive Router false negative: ≤ 2%
- Worker payload critical preservation: ≥ 95%
- Behavioural improvement: statistically and practically explainable
- Context overhead: measured, not asserted

Failure of any threshold blocks the enforcement plane (G8+).
