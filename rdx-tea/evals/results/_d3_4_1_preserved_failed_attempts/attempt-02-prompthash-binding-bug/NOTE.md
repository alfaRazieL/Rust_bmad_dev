# Preserved failed attempt 02 — false SCHEDULE_DRIFT (prompt_hash binding bug)

Class: **apparatus defect** (schedule-binding hash mismatch). NOT a
candidate rule-operation failure, NOT auth, NOT schedule tampering.

## What happened
The first *real* scheduled run (`ruleop-cand-001-test-design-async-rep01`,
absolute paths, model invoked) executed the RDX lifecycle **correctly**:

- wrapper skill invoked = true, child skill invoked = true
- observed_mode = OBSERVED_SEQUENTIAL, task_tool_use_count = 0
- active_packs = [async] == expected, matched RP-ASYNC-005
- expected_rule_condition = PASS, forbidden_rule_condition = PASS
- verifier_all_pass = true, 2 artefacts / 2 sidecars
- workspace_delta = PASS, artifact_consistency = PASS, cleanup clean
- exit_code 0, model claude-haiku-4-5-20251001, no contamination

…yet `admissible = false`, `run_outcome = SCHEDULE_DRIFT`, sole reason
`prompt_hash drift`.

## Root cause (proven)
The locked schedule pins `prompt_hash` as the **run-id-normalised prompt
template** hash — `sha256(arm_prompt(arm, wf, "__RUN_ID__"))` — which is
why all three repetitions of a scenario share ONE `prompt_hash`
(rep01/rep02/rep03 → `0273c3d6…`). The dry-run acceptance gate uses
exactly this placeholder and PASSES. But the runtime binding in
`run_live._finalize_evidence_v4` compared the schedule's template hash
against the **real** per-run prompt hash (`invocation.prompt_hash`),
which embeds the variable `run_id`. Those can never be equal, so EVERY
scheduled run produced a false `prompt_hash drift`.

The D3.4.0 smokes never exposed this because they ran via `run_smoke`
WITHOUT a schedule entry (`schedule_binding = NOT_SCHEDULED`); the
schedule-bound `run_one` path had only ever been exercised by the
dry-run (which uses the placeholder consistently). D3.4.1 is the first
live scheduled execution and correctly surfaced the latent bug.

## Fix (in tested subject)
`run_live._finalize_evidence_v4` now computes the binding prompt hash as
`_sha256_text(arm_prompt(spec.arm, spec.workflow, "__RUN_ID__"))`,
matching the schedule generator + dry-run definition. Schedule binding
therefore verifies the prompt **template** (its real intent); the
per-run `run_id` remains verified separately by `run_id_handshake`. The
recorded `invocation.prompt_hash` still stores the REAL prompt hash for
audit. Regression test added:
`test_scheduled_prompt_hash_is_run_id_normalised_template`.

The locked schedule (sha256 `0b2cd8ee…`) and criteria (`3288de4f…`) were
NOT modified. No rule-operation semantics changed.

## Preservation
This run's SCHEDULE_DRIFT bundle is preserved here (moved, never
overwritten). Retried per precommitted policy after the apparatus fix.
