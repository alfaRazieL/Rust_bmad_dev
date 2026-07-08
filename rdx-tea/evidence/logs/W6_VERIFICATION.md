# Wave 6 — Verifier / admission & failure semantics — verification

- **Repo / branch:** `rdx-workspace/Rust_bmad_dev` @ `rdx-tea-integration`
- **Basis:** D3_RULE_OPERATION_PROVEN (D3.4.1). Productionization only — the
  sequential wrapper-driven RDX→TEA lifecycle is already PROVEN; W6 hardens the
  verifier + fail-closed admission. G7 (behavioural benefit vs baseline) is out
  of scope, not claimed.
- **W6 START_HEAD:** `feb4087a7040bd895cf0bf2b59219d4874c02c17` (== W5 FINAL_HEAD)
- **Pre-W6 owner checkpoint commit:** `8ad39b4` (record Wave 5 owner checkpoint)
- **Python:** 3.14.4 (`rdx-tea/.venv-baseline`)
- **cwd for all commands:** repo root `.../rdx-workspace/Rust_bmad_dev`
- **Live model calls:** NONE. Tests use the env-gated deterministic
  fake-artefact path (`RDX_TEA_ALLOW_TEST_ARTEFACT=1`). The 12-run pilot / mass
  eval were NOT re-run; D3.4.1 evidence is cited.

## Pre-W6 regression (before any change) — all PASS

See `W6/PRE_W6_REGRESSION.txt`. Full suite 235 passed (matches W5 handoff).

## Change summary (productionization; proven lifecycle preserved)

W6 productionizes the ADR-006 §5-9 admission model on the SHIPPED surface,
without importing the eval harness (G-SPLIT-IMPORT), and confirms the
behavioural verifier fails closed per check. Documented in
`architecture/ADR-008-VERIFIER-ADMISSION-FAILURE-SEMANTICS.md`.

1. **9 verifier checks each fail closed on a mutated input.**
   `tests/mutation/test_l7_w6_verifier_mutation.py` builds one passing run,
   then mutates each hashed input surgically; each mutation flips EXACTLY that
   check to FAIL and the aggregate verdict to FAIL. Light hardening in
   `rdx_tea_validator.verify`: post-schema field reads are defensive (`.get`)
   so a schema-invalid sidecar yields a graceful check FAIL, not a crash — no
   generator/bundle output changed (W2/W3 golden pins unchanged).

2. **Admission recomputed from primitives — never a self-reported flag.** New
   shipped module `scripts/admission.py` (`admit_run`, CLI `admission.py
   admit`). Recomputes FINALIZED-admissibility from the report's own primitives;
   ignores any recorded `admissible` / `admission` field. Proven by
   `tests/unit/test_l1_w6_admission_recompute.py` (incl. a dishonest self-admit
   that is recomputed away). `finalize_run` records the recomputed block for
   audit; the gate never trusts it.

3. **Run outcomes in a fixed deterministic order.**
   `AUTH_FAILURE → RUNTIME_FAILURE → SCHEMA_FAILURE → MODE_FAILURE →
   WORKFLOW_FAILURE → VERIFIER_FAILURE → CONSISTENCY_FAILURE → PARTIAL_RUN →
   SUCCESS` (first-failure-wins). Mapped from ADR-006 §5. A failed/partial run
   is never FINALIZED-admissible.

4. **Cleanup + bounded retry policy documented** (ADR-008 §4-5): cleanup
   (overlay restore + lock release) happens on every exit incl. fail-closed;
   preserved failed evidence is never overwritten or promoted; retries are for
   INFRA/RUNTIME transients ONLY and never convert a rule-operation / verifier /
   admission / workspace-delta / artifact-consistency failure into an infra
   success.

## Fail-closed proof (end-to-end, `tests/integration/test_l3_w6_failclosed.py`)

| Scenario | finalize exit | recomputed admission | CLI `admit` exit |
|---|---|---|---|
| honest run | 0 | admissible SUCCESS | 0 |
| verifier check FAIL (tampered diff.patch) | 0 (lifecycle) | NOT admissible VERIFIER_FAILURE | 2 |
| Task/subagent observed | 0 (honest record) | NOT admissible WORKFLOW_FAILURE | 2 |
| phantom consistency FAIL | non-zero (fail-closed) | NOT admissible CONSISTENCY_FAILURE | 2 |
| partial (prepared, no finalize) | — | no report | 2 (RUNTIME_FAILURE) |
| dishonest self-admit (`admissible:true` + corrupted verifier) | — | recomputed NOT admissible | 2 |

On the consistency-failure path the active-run lock is released and the overlay
restored (W4/W5 cleanup invariant preserved), and the failed run-report is
preserved honestly.

## Gates (see `W6/W6_GATES.txt`)

| Gate | Command | Result |
|---|---|---|
| **G-W6-VERIFIER** | `pytest rdx-tea/tests -k verifier -q` | 15 passed (incl. 9-check mutation) |
| **G-W6-ADMISSION** | `pytest rdx-tea/tests -k admission -q` | 26 passed |
| **G-W6-FAILCLOSED** | `pytest rdx-tea/tests -k failclosed -q` | 6 passed |
| **G-DET** | W2 canonical + W3 bundle golden pins | both match pin (unchanged) |
| **G-AUTH** | grep shipped surface for auth env | CLEAN |
| **G-SPLIT-IMPORT** | grep shipped surface for eval/evidence refs | CLEAN |
| **G-SCOPE** | `git diff --name-only feb4087..HEAD` + worktree | only `rdx-tea/**` |
| full suite | `pytest rdx-tea/tests -q` | **277 passed** (235 + 42 new) |

## STOP conditions — none hit

- No verifier check can be bypassed (each fails closed + isolated).
- No failed/partial run becomes admissible.
- Admission never trusts a self-reported flag (recompute-only).
- No `rdx-tea-validate` / enforcement verdict / modes / hooks / CI-gate / Cat-4
  built (deferred backlog). No installer/CI/docs/subagent propagation built.
- No live model call; no pilot/mass eval re-run.
