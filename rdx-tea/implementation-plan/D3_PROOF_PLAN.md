# D3_PROOF_PLAN

**Supersedes:** `PROOF_COMPLETION_PLAN.md` (D2-era).  
**Verdict at plan write time:** `D3_PARTIALLY_PROVEN`
(`D3_FINAL_VERIFICATION.json`).  
**Rule (per D3 prompt §11):** production `MASTER_IMPLEMENTATION_PLAN.md`
is created only after `D3_PROVEN`.

The plan continues from the runtime state proved in Phases A–E + H of
this work window. Each stage is a self-contained fresh-context work
item.

## Ordering

```
Stage-01 done → Stage-02 done → Stage-03 done → Stage-04 done →
Stage-05 done → Stage-06 done → Stage-07 done → Stage-08 done →
Stage-09 done → Stage-10 done
```

Stages 01–08 close knowledge-plane and adapter proof. Stages 09–10
close the enforcement plane.

Stages proved in THIS window:

| # | Name | Gate change | Test file / evidence |
|---|---|---|---|
| A | Correct D2 evidence | G1→PARTIAL; G2→PARTIAL then PASS(semantic); tier RED regression retired | `D3_CORRECTION_AUDIT.md`, `test_l1_regressions_d3.py` |
| B | Semantic parser | G2→PASS | `rdx_parser.py`, `test_l1_rdx_parser_v2.py` |
| C | Upstream customization | G1→PASS | `test_l4_upstream_customization.py` |
| D | Dynamic active-bundle | G3→PASS | `prepare.py`, `test_l2_dynamic_active_bundle.py` |
| E | Sequential vertical slice | G5→PARTIAL, G6→PASS(v1), G8→PARTIAL | `binder.py`, `test_l4_sequential_vertical_slice.py` |
| H | Lifecycle partial | G4→PARTIAL | `test_l4_d3_lifecycle.py` |
| F | Falsification | G10→PARTIAL | `test_l7_d3_falsification.py` |

Stages NOT proved (this file is their brief):

## Stage-01 — Live LLM test-design run (closes G5, feeds G7)

Entry gate: G0–G4 PASS.

Scope allowed:
- `rdx-tea/evals/baseline/{workflow}/{fixture}/transcripts/`
- `rdx-tea/evals/variant-d3/{workflow}/{fixture}/transcripts/`
- new `rdx-tea/scripts/run-tea-workflow.sh`
- fixture stories under `rdx-tea/fixtures/stories/`

Tests written first:
- Grader assertions on transcript JSON: `active_packs` present, rule
  IDs cited match Router; no invented IDs; no Cat-1 PASS in artefact.

Exit gate: at least three transcripts per workflow × per fixture (one
per each of: `test-design` async story, `test-design` doc-only
control, `atdd` unsafe story). If runtime cannot run the LLM in this
work window, record NOT_RUN and freeze downstream stages.

## Stage-02 — Baseline vs candidate behavioural eval (closes G7)

Entry gate: Stage-01 green.

Scope allowed: `rdx-tea/evals/**`, grader, aggregate report.

Tests written first: schema-checked rubric per BEHAVIORAL_EVAL_PLAN.md.

Exit gate: N≥10 (normal) or N≥20 (critical) runs per arm with
statistical CI. Improvement measurable; no regression on negative
controls.

## Stage-03 — RDX validator extension `rdx-tea-validate` (closes G8)

Entry gate: G7 PASS.

Scope allowed: `rdx-validator/rdx_tea/**` (new subpackage),
`rdx-tea/tests/mutation/test_l7_validator_*.py`.

Tests written first: 24 tamper cases from prompt §7; Cat-1 authority
regression suite from RDX baseline.

Exit gate: G8 PASS. `rdx-tea-validate <sidecar>` emits a valid
`rdx-evidence.v1` envelope; LLM-set Cat-1 PASS rejected.

## Stage-04 — MODE tie-in + pre-push hook + rdx-tea-gate.yml (closes G9)

Entry gate: G8 PASS.

Scope allowed: `rdx-tea/tests/ci/`, `rdx-tea/scripts/`,
`.github/workflows/rdx-tea-gate.yml` (new — separate from rdx-gate).

Tests written first: mode-behaviour parity with RDX baseline; hook
`--no-verify` bypass recorded; CI loads validator from target branch.

Exit gate: G9 PASS.

## Stage-05 — Production installer / uninstaller / rollback (closes G4)

Entry gate: G7 PASS (adapter is proven useful).

Scope allowed: `_bmad/rdx-tea/setup/**`, `rdx-tea/tests/lifecycle/**`.

Tests written first: fresh install; update; uninstall preserves
`.user.toml`; rollback restores previous overlay; interrupted install
leaves no partial state.

Exit gate: G4 PASS.

## Stage-06 — Upstream version compat matrix (closes G11)

Entry gate: G8 PASS.

Scope allowed: compat harness under `rdx-tea/tests/compat/`.

Tests written first: hash-mismatch on `resolve_customization.py`
version triggers fail-closed; unsupported TEA tag rejected with a
useful message.

Exit gate: G11 PASS.

## Stage-07 — Judgment / Cat-4 for adapter-generated artefacts

Entry gate: G8, G9 PASS.

Scope allowed: `rdx-tea/tests/acceptance/**`.

Tests written first: Cat-4 approval binding for adapter-owned files;
LLM cannot upgrade Cat-1.

## Stage-08 — Full workflow expansion

Entry gate: Stages 01–04 green for test-design + atdd.

Scope allowed: real LLM runs across the remaining six workflows
(framework, ci, automate, test-review, nfr, trace).

Exit gate: `active_packs` correct per obligation matrix on each; no
LLM-set verdict; sidecar valid.

## Stage-09 — Behavioural adversarial evals

Entry gate: G7 PASS, Stage-08 green.

Scope: red-team fixtures where the story is misleading and the
adapter must not activate the wrong pack.

## Stage-10 — Release / documentation

Entry gate: G0..G11 PASS.

Only then: archive this D3_PROOF_PLAN as `IMPLEMENTATION_LOG.md` and
write `MASTER_IMPLEMENTATION_PLAN.md`.

## What is BLOCKED

- MASTER_IMPLEMENTATION_PLAN.md — waits for D3_PROVEN.
- Any production change outside `rdx-tea/` or `rdx-validator/rdx_tea/`.
- Any host BMAD modification — adapter is overlay-only.

## Rollback

Every stage ends with one or more logical commits on
`rdx-tea-integration`. Rollback = `git reset` to previous stage
commit. No production file outside adapter-owned paths is touched.

## Guardrails re-affirmed

- Only the `rdx-tea-integration` branch may receive commits.
- No PR, no merge, no force push.
- Do not delete any `evidence/` file — supersede by addendum.
- Never inflate `NOT_RUN` / `INCONCLUSIVE` to `PASS`.
- Never claim subagent support in v1.
