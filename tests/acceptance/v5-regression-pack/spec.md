# V5 Regression Pack — T-V6-ACC-01 fixture

T-V6-ACC-01 asserts that the entire V5 acceptance set still passes after
the Phase 7 changes (rdx-judgment + rdx-code-review wrapper). The spec
below catalogues which existing test files cover which V5 acceptance ID,
and the L3 acceptance test in `../test_v6_acceptance.py` runs them as a
single regression subprocess.

| V5 ID         | Title                                                | Where it is verified                                                                 |
|---------------|------------------------------------------------------|--------------------------------------------------------------------------------------|
| T-V5-ACC-01   | Standalone validator works without BMAD              | Phase 2 — entire `tests/unit/validator/` suite + `rdx-validator/` package import.    |
| T-V5-ACC-02   | All 12 packs trigger correctly on positive fixtures  | `tests/unit/validator/test_l2_router_packs.py` (per-pack positive coverage).         |
| T-V5-ACC-03   | Weak-signal packs do NOT block without story tags    | `tests/unit/validator/test_l2_router_packs.py` (negative-no-tag fixtures).           |
| T-V5-ACC-04   | Evidence authority enforced                          | `tests/contracts/test_l0_schema_evidence.py` (Cat-1 self-attest rejection).          |
| T-V5-ACC-05   | CI independently recomputes deterministic verdicts   | `tests/ci/test_l6_ci_workflow.py::test_v5_acc_05_ci_matches_local`.                  |
| T-V5-ACC-06   | Docs honesty (no false "hard enforcement" claims)    | `tests/acceptance/test_doc_honesty.py`.                                              |
| T-V5-ACC-07   | Existing RDX KB behavior not regressed               | `tests/contracts/test_l0_drift.py` + KB drift check in `.github/workflows/rdx-l0-contracts.yml`. |

The V6 acceptance harness runs `pytest tests/contracts tests/unit
tests/acceptance/test_doc_honesty.py tests/ci/test_l6_ci_workflow.py` as
a single subprocess to prove all V5 evidence still passes. A failure in
any of those modules invalidates V6 release per
RDX_IMPLEMENTATION_PLAN_TESTED.md Phase 7 exit gate.
