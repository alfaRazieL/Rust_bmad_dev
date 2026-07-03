# D3.3.2 Execution Closure Report

Scope: pilot-harness execution validity closure. Every deliverable
below aligns with a specific gap in `D3_3_2_PRECONDITION_AUDIT.md`.

## 1. Arm-separated execution paths

### 1.1 Arm-specific prompts and skill install

- `rdx-tea/live-harness/run_live.py::arm_prompt(arm, workflow, run_id)`
  emits a **baseline** prompt (`Invoke /bmad-testarch-<workflow>`)
  that contains none of the banned tokens (`rdx`, `wrapper`, `rp-`,
  `active-context`, `prepare-run`, `finalize-run`) and a **candidate**
  prompt (`Invoke /rdx-tea-<workflow>`) that references the invocation
  contract file.
- `arm_installed_skills(arm, workflow)` gates the isolated Claude
  config: baseline gets only `bmad-testarch-<workflow>`; candidate
  gets `rdx-tea-<workflow>` AND `bmad-testarch-<workflow>`.
- Both arms use the same isolated `CLAUDE_CONFIG_DIR` policy, same
  model, same timeout, same budget, same MCP-empty file.
- Regression tests: `test_arm_prompt_baseline_never_mentions_rdx`,
  `test_arm_prompt_candidate_names_wrapper_and_run_id`,
  `test_arm_installed_skills_baseline_excludes_wrapper`.

### 1.2 Arm-specific acceptance

`live-evidence.v2.schema.json` uses `if/then + not` branches keyed on
`arm`. A baseline bundle carrying `candidate` (or `baseline.wrapper_
skill_invoked == true`) is rejected. A candidate bundle lacking the
`candidate` block is rejected. Regression tests:
`test_v2_schema_rejects_baseline_with_wrapper_invoked`,
`test_v2_schema_rejects_baseline_carrying_candidate_block`,
`test_v2_schema_rejects_candidate_missing_block`.

## 2. Schedule-owned run_id end-to-end

- `RunSpec.run_id` is a **required** field (no default).
- `run-one` CLI subcommand requires `--run-id` (argparse `required=True`).
- `run-smoke` can auto-generate a smoke id (`smoke-<scenario>-<arm>-<utc>`)
  but never for pilot runs (the pilot executor always passes an
  explicit id from the schedule).
- `emit_invocation_contract()` writes `_bmad-run/rdx-tea-invocation.json`
  BEFORE the wrapper runs. The wrapper's `prepare_run` reads that file
  and refuses to proceed if `run_id`, `workflow`, or `arm` disagree
  with its CLI arguments — see the new
  `_read_invocation_contract` block in `rdx_tea_wrapper.py`.
- Wrapper SKILL.md instructions (for both `rdx-tea-test-design` and
  `rdx-tea-atdd`) now begin with reading the invocation contract and
  using its `run_id` verbatim; timestamp fallback is only for legacy,
  contract-less invocations.
- Post-run `_check_run_id_handshake()` compares `schedule.run_id`
  against `invocation.json`, workspace runtime dir, and run-report.
  Any mismatch surfaces as `run_id_handshake.mismatch == true` in the
  v2 bundle, which fails the pilot rubric's `invalid_when` clause.
- Regression tests:
  `test_run_id_handshake_no_mismatch_when_only_schedule`,
  `test_run_id_handshake_detects_mismatch`.

## 3. Structured-only transcript classifier

- `_walk_for_invocations` (free-text substring version) is deleted.
- New `_iter_tool_use_events` yields ONLY `tool_use` blocks with
  `type == "tool_use"` inside assistant messages or top-level events.
- `_classify_tool_use` accepts a Skill invocation only when
  `name in {"Skill", "SlashCommand", "slash_command"}` and the
  invoked skill lives in `input.skill` / `input.name` /
  `input.slash_command`. Assistant prose and user prompts are
  ignored.
- Adversarial regression tests exercise every explicit case from
  §8 of the handoff (free-text mention, user prompt mention, wrapper
  only, child only, both + task, invalid transcript).

## 4. Actual runtime init parsing

- `_extract_runtime_init(transcript_path)` reads `system`/`init`
  events from the stream JSONL and records the ACTUAL surface:
  claude_code_version, model, permission_mode, tools, skills,
  slash_commands, mcp_servers, plugins, memory_paths, session_id.
- `compare_runtime_surface(observed, expected)` returns a structured
  diff; `contamination_reason(diff)` returns the first reason (or
  `None`).
- V2 evidence stores `observed_surface`, `expected_surface`,
  `surface_diff`, and `contamination`. Constants like `mcp_servers=[]`
  are gone. Regression test:
  `test_extract_runtime_init_reads_actual_fields`,
  `test_compare_runtime_surface_flags_contamination`.

## 5. Runtime preflight and isolation refinements

- `ClaudeIsolation.preflight()` returns a list of policy errors —
  missing config dir, non-empty MCP, non-empty CLAUDE.md, mis-set
  skills. `run_smoke` calls it BEFORE any token is spent; the harness
  fails closed if any error is present.
- New `run_live.py runtime-preflight` subcommand emits a JSON report
  with `status: PASS|FAIL` and a non-zero exit on failure — CI or
  operators can run it standalone.
- `bypassPermissions` remains for both arms because Claude Code CLI
  currently refuses to run headless without an explicit
  `--permission-mode`; the SAME value is set for baseline and
  candidate so the arms remain comparable. This is documented in the
  ADR as a known-and-symmetric compromise.

## 6. CI hardening

- Single upstream root: `RDX_TEA_UPSTREAM_ROOT` exported in every
  step that touches upstream. Bootstrap, tests, and (future) harness
  reads all read from `os.environ["RDX_TEA_UPSTREAM_ROOT"]` before
  falling back to `<repo>/../upstream`. Test 4 §5 confirmed the CI's
  historical layout diverged from the tests' expected layout — this
  is closed.
- Structured skip gate: `rdx-tea/live-harness/ci_check.py refuse-skips`
  parses JUnit XML for real `<skipped>` elements. The empty allowlist
  at `ci_check_allowlist.txt` means every skip is unauthorised;
  future additions require an explicit review.
- Unique-count: `ci_check.py unique-count` walks every JUnit XML,
  reports `unique_collected`, `unique_passed`, `unique_failed`,
  `unique_skipped`, and `reexecutions` derived from the set
  difference between summed totals and unique node IDs.
- `source-lock-report` step now calls the real
  `bootstrap.py --verify-only` — no `|| echo` masking. On drift the
  step exits non-zero and CI fails.

## 7. Rubric v3 + schedule v2

- `D3_4_PILOT_RUBRIC.v3.yaml` (schema_version
  `rdx-tea-pilot-rubric.v3`) supersedes v2. Explicit `positive_scenarios`
  list has exactly two entries (`test-design-async`,
  `atdd-api-async-corrected`); `negative_control_scenarios` lists
  `docs-only-rust-repo`. Decision rule uses unambiguous EITHER/OR
  logic across the two positive scenarios instead of the impossible
  `≥ 2 of 3` phrasing.
- `D3_4_PILOT_RUNS.v2.json` (schema_version `rdx-tea-pilot-runs.v2`)
  binds each of the 18 runs to arm-specific prompt hashes, fixture
  hashes, rubric version, grader version, retry policy, and order
  seed. `locked=true`. Schedule SHA256:
  `29b57ee5a5fd98fdd66e3bb0484453da9992fa57f027aea57b158eedb600d5c6`.

## 8. Pilot executor + blinded grader

- `rdx-tea/evals/run_pilot.py` composes discovery, prepare, invoke,
  reconcile, evidence, cleanup via `run_live.RunSpec`. Subcommands:
  `dry-run`, `run-one`, `resume`, `status`. Dry-run produces
  `PLAN.json` per run and a top-level `MANIFEST.json` — see §10 below.
- `rdx-tea/evals/grading/grade_pilot.py` implements
  `prepare-blind`, `grade-deterministic`, `grade-llm`, `merge`,
  `report`. Comparative grader never sees arm, wrapper, RDX ids,
  paths, or the mapping file. Layer-2 LLM grader interface is
  testable but runs with `dry_run=True` in D3.3.2 — the report
  therefore cannot exceed `PILOT_INCONCLUSIVE`.
- Grader tests cover the blinding contract (RP-id / wrapper / arm
  path stripping), the deterministic detectors, the disagreement
  recording (never overwrites), and the DO_NOT_READ mapping marker.

## 9. Structured lock and observed cleanup

- `active-run.lock` is now a JSON document with `run_id`, `workflow`,
  `pid`, `created_at`. Ownership check is exact equality — no
  substring. Legacy string locks are treated as unowned so a
  wandering one from a pre-D3.3.2 run is preserved for inspection
  rather than silently released.
- `observe_cleanup()` re-reads lock/overlay/rundir/transcript state
  AFTER cleanup writes. V2 evidence records the observed dict rather
  than a boolean constant. Regression tests
  `test_observe_cleanup_reports_actual_state`,
  `test_observe_cleanup_flags_foreign_overlay`.

## 10. Deterministic 18-run dry-run

`python3 rdx-tea/evals/run_pilot.py dry-run` (executed on FINAL_HEAD)
produced `rdx-tea/evals/results/d3_3_2_dry_run/MANIFEST.json`:

    total_runs=18   baseline=9   candidate=9
    unique_run_ids=18            unique_workspace_dirs=18
    unique_config_dirs=18        unique_evidence_dirs=18
    unique_prompt_hashes=4        (2 arms × 2 workflows)
    arm_command_difference=True  schedule_immutable_flag=True
    baseline_command=[/bmad-testarch-test-design]
    candidate_command=[/rdx-tea-test-design]

No path collisions. Every run has a `PLAN.json` under
`rdx-tea/evals/results/d3_3_2_dry_run/evidence/<scenario>/<arm>/…`.

## 11. What is NOT executed in this cycle

- No live model-driven runs. The corrected ATDD live smoke described
  in §18 of the handoff is deferred to a subsequent live-execution
  step; the schedule and harness are ready but the live smoke has not
  been dispatched inside this window (see BLOCKERS §1 for the exact
  command that closes it).
- No LLM grader run. The grader interface is testable and returns
  `NOT_RUN` per sample when `dry_run=True`.
- Verdict is therefore `D3_3_2_PARTIAL` and D3.4 readiness is
  `D3_4_NOT_READY`.
