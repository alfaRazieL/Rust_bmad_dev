# D3.3.1 Blockers

Blockers still open at the end of this cycle. Each entry says
what is missing, why the missing piece matters, and what evidence
would close it.

## §1 Corrected ATDD smoke — live model-driven run

- Status: NOT_RUN.
- What's needed: one live invocation of `run_live.py run-smoke
  --scenario atdd-api-async-corrected --arm candidate` against a real
  Claude Code CLI (`claude-haiku-4-5-20251001`) in an isolated
  `CLAUDE_CONFIG_DIR`. Expected observations:
    - `active_packs == [api, async]` (already deterministically proven);
    - `observed_mode == OBSERVED_SEQUENTIAL` post-reconciliation;
    - `wrapper_skill_invoked == True`;
    - `child_skill_invoked == True`;
    - `task_tool_use_count == 0`.
- Why it matters: G14 (LLM side of the invocation closure) is only
  PARTIAL until propagation of the api pack in a live TEA artefact is
  observed. Without this, the D3.3.1 §7 clause 6 (`corrected ATDD
  smoke activates api + async`) is not fully closed.
- Closure evidence: `rdx-tea/evidence/live/smoke-atdd-api-corrected/**`
  with a schema-valid `live-evidence.v1.json`.

## §2 CI conclusion for D3.3.1 code commit

- Status: PENDING.
- What's needed: push the D3.3.1 code commit, wait for
  `.github/workflows/rdx-tea-integration-check.yml` to complete,
  record the `github_actions_run_id`, URL, and conclusion in a
  follow-up evidence commit that also captures `tested_subject_sha`
  (code commit) and `evidence_commit_sha` (its own SHA).
- Why it matters: `evidence/final/D3_3_1_FINAL_VERIFICATION.json`
  currently contains `PENDING` sentinels for those fields. The
  D3.3.1 §7 clauses 10, 11, 12 (CI green, artifacts uploaded,
  evidence identity without PENDING) all depend on it.
- Closure evidence: an updated `D3_3_1_FINAL_VERIFICATION.json`
  landed as a subsequent evidence commit.

## §3 D3.4 pilot execution

- Status: NOT_RUN.
- What's needed: 18 model-driven runs per the precommitted schedule
  `rdx-tea/evals/runs/D3_4_PILOT_RUNS.json`, plus the grader passes,
  plus the pilot verdict per rubric v2.
- Why it matters: the whole point of the RDX-TEA integration is to
  demonstrate behavioural benefit (G7). Nothing in this cycle claims
  benefit — that claim requires the pilot.
- Precondition (STOP): D3.3.1 must be PASS (not PARTIAL) before the
  pilot can start. Blockers §1 and §2 must both close first.

## §4 Blinded grader implementation

- Status: DESIGN_ONLY.
- What's needed: a runner script `rdx-tea/evals/grading/grade_pilot.py`
  that consumes `D3_4_PILOT_RUBRIC.yaml`, walks the sanitised
  evidence, computes the layer-1 deterministic metrics, dispatches
  the layer-2 blinded LLM grader, records disagreement, and merges
  per-sample results under `rdx-tea/evals/results/d3_4_pilot/`.
- Why it matters: the rubric is a contract; the grader is the enforcement.
- Not implemented in this window because it depends on the corrected
  ATDD smoke landing first (otherwise the grader would be executed
  against evidence bundles from the old fixture and would silently
  perpetuate §2.4 error).

## Non-blockers (already closed)

- run_live orchestrator, schema, tests, dedup, crash-safe cleanup,
  runtime isolation, corrected fixture, rubric v2, precommitted
  schedule, CI hardening — all landed in this cycle. See
  `D3_3_1_STABILIZATION_REPORT.md` §1–§10.
