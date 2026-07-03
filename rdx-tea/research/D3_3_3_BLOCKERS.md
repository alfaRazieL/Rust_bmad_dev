# D3.3.3 Blockers

## Closed in this stage

- §1 (D3.3.2) Isolated `CLAUDE_CONFIG_DIR` broke OAuth — CLOSED.
  `ProjectRuntimeIsolation` never overrides `CLAUDE_CONFIG_DIR`;
  project isolation uses `--setting-sources project` +
  `--strict-mcp-config` + workspace `.claude/settings.json`. Auth
  preflights and the admissible live smoke prove OAuth survives.
- Corrected-ATDD candidate live smoke — CLOSED. One admissible SUCCESS
  bundle at `rdx-tea/evidence/live/smoke-atdd-api-corrected-v3/`.

## Open (belong to later stages — NOT this stage's scope)

### §1 D3.4 blinded behavioural pilot
- Status: NOT_RUN (correctly deferred).
- What's needed: 18 model runs per
  `rdx-tea/evals/runs/D3_4_PILOT_RUNS.v2.json` (new SHA256
  `31861b48ca51887cd57bef6d1673b93be25ac69021c029018ed4d59c968bfdb2`),
  then the blinded grader passes and the rubric-v3 verdict.
- Precondition satisfied: D3.3.3 PASS + admissible candidate smoke.

### §2 Baseline arm live behaviour
- Status: NOT_RUN. Only the candidate arm was exercised live in this
  stage. The baseline execution path is proven deterministically
  (arm-specific skills/prompt/schema) but not yet on a live model.
  This is part of the D3.4 pilot.

### §3 Live blinded LLM grader
- Status: DRY_RUN_ONLY. `grade_pilot.py grade-llm` remains testable
  with `dry_run=True`; a live grader pass requires the D3.4 pilot
  artifacts and is out of scope here.

## Findings recorded (not blockers, but load-bearing for D3.4)

### F1 — Slash-command skills are expanded inline, not as Skill events
Claude Code 2.1.191 expands a slash-command skill named in the prompt
INLINE; it does not emit a `Skill` tool_use for it. To obtain a
structured wrapper Skill event the prompt must instruct the model to
invoke the wrapper via the Skill TOOL. `arm_prompt` (candidate) was
updated accordingly and the schedule prompt hashes regenerated
pre-pilot. The D3.4 pilot MUST use this prompt form or the candidate
integration fidelity check (wrapper structured Skill event) cannot be
satisfied.

### F2 — Verifier report shape
The wrapper's verifier records a top-level `verdict` + a `checks`
array (with `failed_checks`), not a top-level `status`. The harness
reader was corrected to read `verdict`/`checks`. Any future consumer
of `run-report.json` must read the same fields.
