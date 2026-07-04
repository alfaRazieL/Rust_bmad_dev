# D3.4.1 — RDX Rule-Operation Pilot Report (12-run)

Aggregate deterministic verdict: **RULE_OPERATION_PASS**
(9/9 candidate rule-operation pass; 3/3 controls clean).

Goal framing: prove RDX rules operate correctly and stably inside real
BMAD TEA workflows. This is NOT a benefit-vs-baseline benchmark — the
candidate/RDX arm is the object of proof; the baseline exists only to
prove control isolation.

## 1. Execution context

| Field | Value |
|---|---|
| Branch | `rdx-tea-integration` |
| Apparatus (tested subject) | fixed at commit `b9b244c` (false-SCHEDULE_DRIFT binding fix) |
| Schedule | `D3_4_RULE_OPERATION_RUNS.v3.json` sha256 `0b2cd8ee…` (locked, unchanged) |
| Criteria | `D3_4_RULE_OPERATION_CRITERIA.v1.yaml` sha256 `3288de4f…` (unchanged) |
| Evidence schema | `rdx-tea-live-evidence.v4` |
| Model (all runs) | `claude-haiku-4-5-20251001` (exact dated ID; observed == expected) |
| Auth | existing CLI OAuth; no API key; `CLAUDE_CONFIG_DIR` not overridden |
| Runtime | Claude Code CLI 2.1.191, `--strict-mcp-config` empty MCP, `--disallowedTools Task TaskOutput TaskStop` |
| Pilot window | 2026-07-04T06:12:53Z → 06:55:08Z (~42 min, sequential) |

## 2. Per-run results (all 12)

| # | run_id | arm | outcome | adm | wrap | child | mode | task | packs | exp_rule | forb_rule | verifier | art/side | wd | ac | binding | ~dur |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | ruleop-cand-001-test-design-async-rep01 | cand | SUCCESS | ✅ | ✅ | ✅ | SEQUENTIAL | 0 | [async] | PASS | PASS | PASS | 2/2 | PASS | PASS | PASS | 4m40s |
| 2 | ruleop-cand-002-test-design-async-rep02 | cand | SUCCESS | ✅ | ✅ | ✅ | SEQUENTIAL | 0 | [async] | PASS | PASS | PASS | 2/2 | PASS | PASS | PASS | 4m27s |
| 3 | ruleop-cand-003-test-design-async-rep03 | cand | SUCCESS | ✅ | ✅ | ✅ | SEQUENTIAL | 0 | [async] | PASS | PASS | PASS | 2/2 | PASS | PASS | PASS | 4m34s |
| 4 | ruleop-cand-004-atdd-api-async-corrected-rep01 | cand | SUCCESS | ✅ | ✅ | ✅ | SEQUENTIAL | 0 | [api, async] | PASS | PASS | PASS | 1/1 | PASS | PASS | PASS | 4m08s |
| 5 | ruleop-cand-005-atdd-api-async-corrected-rep02 | cand | SUCCESS | ✅ | ✅ | ✅ | SEQUENTIAL | 0 | [api, async] | PASS | PASS | PASS | 1/1 | PASS | PASS | PASS | 5m04s |
| 6 | ruleop-cand-006-atdd-api-async-corrected-rep03 | cand | SUCCESS | ✅ | ✅ | ✅ | SEQUENTIAL | 0 | [api, async] | PASS | PASS | PASS | 2/2 | PASS | PASS | PASS | 6m01s |
| 7 | ruleop-cand-007-docs-only-rust-repo-rep01 | cand | SUCCESS | ✅ | ✅ | ✅ | SEQUENTIAL | 0 | [] | PASS | PASS | PASS | 2/2 | PASS | PASS | PASS | 4m21s |
| 8 | ruleop-cand-008-docs-only-rust-repo-rep02 | cand | SUCCESS | ✅ | ✅ | ✅ | SEQUENTIAL | 0 | [] | PASS | PASS | PASS | 2/2 | PASS | PASS | PASS | 3m23s |
| 9 | ruleop-cand-009-docs-only-rust-repo-rep03 | cand | SUCCESS | ✅ | ✅ | ✅ | SEQUENTIAL | 0 | [] | PASS | PASS | PASS | 2/2 | PASS | PASS | PASS | 3m46s |
| 10 | ruleop-ctrl-010-test-design-async-rep01 | base | SUCCESS | ✅ | ❌(none) | ✅ | INFERRED_ABSENT | 0 | — | — | — | — | 0/0 | PASS | PASS | PASS | 31s |
| 11 | ruleop-ctrl-011-atdd-api-async-corrected-rep01 | base | SUCCESS | ✅ | ❌(none) | ✅ | INFERRED_ABSENT | 0 | — | — | — | — | 0/0 | PASS | PASS | PASS | 46s |
| 12 | ruleop-ctrl-012-docs-only-rust-repo-rep01 | base | SUCCESS | ✅ | ❌(none) | ✅ | INFERRED_ABSENT | 0 | — | — | — | — | 0/0 | PASS | PASS | PASS | 34s |

`wrap ❌(none)` for baseline is the DESIRED result: the baseline never
invokes the RDX wrapper. `art/side` = TEA artefacts / RDX sidecars.

## 3. Per-scenario candidate pass count

| Scenario | Fixture | Expected packs | Candidate runs | Pass | Matched rules |
|---|---|---|---|---|---|
| test-design-async | test-design-async-latent | [async] | 3 | **3/3** | RP-ASYNC-005 (all) |
| atdd-api-async-corrected | atdd-api-async-latent | [api, async] | 3 | **3/3** | RP-ASYNC-005 + RP-API-001/004/005 (all) |
| docs-only-rust-repo | docs-only-rust-repo-control | [] | 3 | **3/3** | none (correctly no pack activated; forbidden `RP-` prefix respected) |

Rule activation was **latent-driven**: the fixtures carry Rust
story/diff/tags, not hand-fed RP ids. The async pack (RP-ASYNC-005) and,
for the ATDD scenario, the api pack (RP-API-001/004/005 via the
precommitted `any_of` set) activated from the workload alone, and the
docs-only repo correctly activated NO pack across all 3 repetitions.

## 4. Control cleanliness (isolation)

All 3 baseline/control runs: `wrapper_skill_invoked=false`,
`direct_child_skill_invoked=true`, `rdx_bundle_absent=true`,
`rdx_sidecars_absent=true`, `rule_operation_absent=true`,
`rp_leakage_hits=[]` (no RP-* obligation leakage), task-dispatch 0,
workspace_delta/artifact_consistency PASS, schema v4 PASS, cleanup
clean. **No RDX contamination in any control.**

Honest characterization: each control invoked the child
`bmad-testarch-*` skill via a structured `Skill` tool call, but the bare
child TEA workflow is interactive — it reached its greeting/elicitation
step and ended without emitting TEA artefacts (0 artefacts, ~30–46s).
This is fully consistent with the control's ONLY purpose (proving
no-RDX contamination), which does not require artefact production. It is
reported here for transparency, not as a benefit-vs-baseline claim. The
candidate arm, carrying the wrapper's non-interactive prepare-run/
finalize-run scaffolding, drove the same child to completion with
artefacts in every scenario (including the docs-only control fixture,
where it produced artefacts yet correctly activated no pack).

## 5. Retry / failure table

| Attempt | Scope | Class | Model invoked? | Disposition |
|---|---|---|---|---|
| attempt-01 | all 12 | INFRA_FAILURE (relative `--out-root` → CLI "Settings file not found") | No (0-byte transcripts) | preserved, retried per policy |
| attempt-02 | run 1 | apparatus defect: false SCHEDULE_DRIFT (per-run prompt-hash vs template-hash) | Yes (lifecycle correct) | preserved; fixed at `b9b244c`; retried |
| **final** | all 12 | — | Yes | **12/12 SUCCESS admissible, 0 retries needed in the graded run** |

- `max_retries_per_run_id: 1` — not consumed in the final graded pilot
  (every run succeeded on its first attempt against the fixed apparatus).
- Every failed attempt is preserved under
  `rdx-tea/evals/results/_d3_4_1_preserved_failed_attempts/` with a
  NOTE; nothing was overwritten or silently replaced.
- No run failed with AUTH_FAILURE, CONTAMINATION, TASK_DISPATCH,
  RUN_ID_MISMATCH, SCHEMA_FAILURE, VERIFIER_FAILURE, CONTROL_LEAKAGE, or
  ARTIFACT_DECLARATION_FAILURE in the final pilot.

## 6. Finalize-completion rate (§14 explicit)

D3.4.0 recorded ONE honest candidate `WORKFLOW_FAILURE` where the model
ended without running `finalize-run` (no run-report.json), before the
candidate prompt was strengthened.

**D3.4.1 result: the finalize-run gap did NOT recur.** All 9 candidate
runs completed the full RDX lifecycle — prepare-run → child skill →
finalize-run → run-report.json — in a single session, yielding a
run-report.json and admissible v4 evidence. **Finalize-completion rate =
9/9 (100%)** with zero retries. The strengthened candidate prompt is
sufficient to drive one-session lifecycle completion on all three
scenarios (including the longer ATDD story, runs 4–6).

## 7. Common failure classes (final pilot)

None. 0 candidate failures, 0 control leakage, 0 schedule drift, 0
forbidden-pack activation, 0 verifier failures, 0 unreconciled
workspace/artifact-consistency failures, 0 task/subagent dispatch, 0
runtime contamination.

## 8. Artifact / workspace-delta consistency summary

- workspace_delta.consistency = PASS on all 12 (declared generated files
  reconciled against actual files; no phantom/planned-not-generated
  escapes flagged).
- artifact_consistency.status = PASS on all 12 (no duplicate/
  contradictory frontmatter fabrications, no phantom file claims, no
  nonexistent project paths).
- Candidate one-sidecar-per-artifact held on all 9 (2/2 or 1/1).

## 9. Verifier summary

Candidate `verifier_all_pass = true` on all 9. Baseline has no RDX
verifier (correct — no RDX runtime). No verifier failure due to any real
rule-binding or canonical-source problem.

## 10. Rule-condition summary

- expected_rule_condition = PASS on all 9 candidates (required rule
  present via projection: active-context bundle / sidecar active_packs
  rule_ids / artifact text — union sources per criteria v1).
- forbidden_rule_condition = PASS on all 9 (no forbidden-prefix pack
  activated; docs-only activated none at all).

## 11. Task/subagent dispatch & runtime contamination

task_tool_use_count = 0 on all 12; runtime.contamination = "" on all 12;
observed model == expected on all 12. No unexpected MCP servers, skills,
or plugins.

## 12. Final verdict

```
RULE_OPERATION_PASS
```

All candidate runs pass rule-operation; all controls clean; no schedule
drift; no forbidden packs; no verifier failures; no unreconciled
consistency failures. This satisfies the §13 PASS interpretation.

D3.4.1 status: **D3_4_1_PASS**.
Overall D3: **D3_RULE_OPERATION_PROVEN** (the multi-run stability signal
deferred by D3.4.0 is now supplied).

## 13. Recommendation for next stage

Proceed to **D4 — MASTER_IMPLEMENTATION_PLAN.md** (a separate stage; NOT
written here). Before or during D4, address the non-blocking items in
`D3_4_1_BLOCKERS.md` (notably: baseline artefact production is
interaction-gated; the schedule pins a template prompt-hash — consider
recording it explicitly as `prompt_template_hash` to avoid future
confusion). None of these affect the RULE_OPERATION_PASS verdict.
