# D3.4.0 Blockers

## Closed in this stage

- Wrapper duplicate artifacts at source — CLOSED (dedupe in
  `_output_dirs`/`_delta_outputs`; run-report one-per-artefact).
- Workspace delta not preserved/verified — CLOSED (workspace_delta +
  declared-file existence + evidence copy).
- Artifact consistency undetected — CLOSED (deterministic detectors).
- Evidence schema cannot represent rule-operation — CLOSED (v4).
- Rule-operation criteria decided post-hoc — CLOSED (criteria v1,
  any_of API rule).
- Fixtures hand-feeding obligations — CLOSED (latent/control fixtures).
- Schedule binding not enforced — CLOSED (runtime binding + drift).
- Baseline live lifecycle unproven — CLOSED (baseline control smoke).
- Grader looks for v2 / always INCONCLUSIVE — CLOSED for rule-operation
  (`grade_rule_operation.py` deterministic verdict over v4).

## Open (belong to the next stage — NOT D3.4.0 scope)

### §1 Full rule-operation pilot (12 runs)
- Status: NOT_RUN (correctly deferred). Execute
  `D3_4_RULE_OPERATION_RUNS.v3.json` (9 candidate + 3 control) and
  produce the aggregate RULE_OPERATION verdict.
- Precondition satisfied: D3.4.0 PASS + admissible baseline control +
  admissible candidate rule-operation on a latent fixture.

### §2 Candidate finalize-completion stability
- Status: MITIGATED, not fully characterised. On the longer latent
  story the model sometimes finished without running the final
  `finalize-run` (one honest WORKFLOW_FAILURE before the admissible
  re-run). The candidate prompt now hard-requires finalize-run
  completion, but the multi-run pilot should measure how often the
  model completes the RDX lifecycle in one session and apply the
  precommitted retry policy for genuine infra/runtime failures.

### §3 `grade_pilot.py` legacy v2/report
- Status: SUPERSEDED for rule-operation by `grade_rule_operation.py`.
  The legacy `grade_pilot.py` (v2 glob, always PILOT_INCONCLUSIVE) is
  retained for the historical comparative path but is NOT used for the
  rule-operation verdict.

### §4 Live LLM diagnostic
- Status: DRY_RUN_ONLY. `grade_rule_operation.py grade-llm-diagnostic`
  runs dry; a live diagnostic pass is optional and never overrides the
  deterministic verdict.

## Findings recorded (load-bearing for the pilot)

- F1 — Forbidden packs must be judged by ACTIVE packs, not prose
  cross-references (an api/async bundle legitimately references
  RP-FFI-003/RP-UNSAFE-003 in exception text).
- F2 — TEA checklists can emit duplicate frontmatter blocks; the
  artifact-consistency detector treats them as reconcilable-with-
  reality warnings and only fails on genuine fabrication.
- F3 — The child ATDD workflow can declare generated `.rs` test files;
  these must be collected, verified, and preserved (the D3.3.3 smoke
  generated them but never preserved them).
