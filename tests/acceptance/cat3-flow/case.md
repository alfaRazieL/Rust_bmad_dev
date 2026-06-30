# Cat-3 Flow — T-V6-ACC-02 fixture

Combined acceptance scenario: a story enters REVIEW_REQUIRED on a Cat-3
rule (RP-UNSAFE-002 Send/Sync invariants), the rdx-judgment evaluator
runs against the active-packs scope, and:

1. The evaluator routes the case (PASS / FAIL / DECISION_REQUIRED /
   SPECIALIST_REQUIRED / INSUFFICIENT_EVIDENCE).
2. The evaluator does NOT touch the Cat-1 finding from the validator
   (CORE-007 = FAIL stays FAIL — schema-enforced).

The first claim is exercised by `test_l8_judgment.py::test_scope_filter_*`
(structural) and `tests/evals/cat3-scope/case.yaml` (statistical, run by
bmad-eval-runner).

The second claim is exercised by
`test_l8_judgment.py::test_finding_schema_rejects_cat1_pass_by_evaluator`
(structural) and `tests/evals/cat3-cat1-immutable/case.yaml` (statistical).

T-V6-ACC-02 in this file is the cross-cut assertion: both structural
guards are in place AND both eval cases are wired into the harness with
their canonical thresholds (≥95% / 100%).
