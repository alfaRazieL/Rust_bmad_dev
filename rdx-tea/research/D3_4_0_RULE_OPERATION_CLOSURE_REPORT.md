# D3.4.0 Rule-Operation Validity Closure Report

Scope: close the validity gaps found after D3.3.3 so a real rule-
operation pilot can be scientifically and technically valid. No
statement here is stronger than the committed evidence.

## 1. Goal reframing

D3.4 proves RDX **rule-operation correctness and stability** in real
TEA workflows, not "RDX is better than TEA". Baseline is a control
arm (isolation / no RDX contamination). See ADR-007.

## 2. Wrapper artifact dedupe at source

`rdx_tea_wrapper._output_dirs()` now collapses nested output roots
(`_bmad-output/test-artifacts` under `_bmad-output`);
`_snapshot_outputs` and `_delta_outputs` dedupe by resolved real
path. Result: `run-report.json` carries one `new_artefacts` /
`sidecars` / `verifier` entry per unique artefact. The D3.3.3 smoke's
run-report had the same artefact twice (2 sidecars / 2 verifier
entries); under the fix a single artefact yields a single sidecar and
single verifier result. 5 unit tests
(`test_l1_wrapper_output_dedupe.py`).

## 3. Workspace delta + declared-file validation

`rule_operation.collect_workspace_delta` records created / modified /
deleted files (git porcelain + untracked), hashes them, extracts the
files the TEA artifact DECLARES it generated, and checks which exist.
A declared generated file that is missing (and not precommitted as
`declarationPlannedNotGenerated`) makes the run
`ARTIFACT_DECLARATION_FAILURE` / inadmissible. Actual generated files
are preserved under `evidence/.../workspace-delta/`.

Finding: the D3.3.3 admissible smoke declared
`tests/integration/create_user_api.rs` and `user_creation_e2e.rs`;
both EXIST in the workspace but were never preserved in evidence.
Under v4 they are collected, verified, and copied.

## 4. Artifact-consistency detectors (deterministic, no LLM)

`rule_operation.check_artifact_consistency` detects duplicate
frontmatter keys, contradictory frontmatter values (judged against
reality — a declared file that does not exist), phantom file claims,
and project-path escapes. Duplicate keys whose values reconcile with
the workspace delta are warnings; unreconcilable contradictions and
phantom claims FAIL `artifact_consistency`.

Finding: the D3.3.3 artifact has duplicate frontmatter keys
(`generatedTestFiles`, `storyId`, …). Because the declared files
exist, it is consistent-with-reality (PASS) with the duplicates
recorded as warnings — exactly the calibration that lets a genuine
candidate pass while catching fabrication.

## 5. Evidence schema v4

`live-evidence.v4.schema.json` adds `workspace_delta`,
`artifact_consistency`, `rule_operation` (candidate),
`baseline_control` (baseline), and `schedule_binding`. Admission
invariants forbid `admissible=true` when workspace-delta or
artifact-consistency fail, when a candidate's rule-operation gates
fail, or when a baseline shows RDX contamination. `admit_bundle` is
version-aware. 27 v4 tests.

## 6. Precommitted rule-operation criteria

`D3_4_RULE_OPERATION_CRITERIA.v1.yaml` (sha256
`3288de4fb4cdce54050d4811105e9520e2952d0cf14b41cd18d51b5188530920`)
fixes, before any run: expected active packs, `all_of` / `any_of`
rule conditions (the API rule is an `any_of` of RP-API-001/004/005 so
a correct run is not penalised for citing a different relevant rule),
forbidden prefixes, and what counts as "rule present" (bundle /
sidecar / artifact). Candidate admission reads this file, not ad hoc
code.

## 7. Latent + control fixtures

`test-design-async-latent`, `atdd-api-async-latent`,
`docs-only-rust-repo-control` describe natural requirements without
naming RDX rules or detector phrases. Router replay confirms routing
from tags/diff: `[async]`, `[api, async]`, `[]`. Old fixtures are
retained (superseded, not deleted).

## 8. Schedule v3 + binding enforcement

`D3_4_RULE_OPERATION_RUNS.v3.json` (12 locked runs: 9 candidate ×3
reps + 3 baseline controls; schedule sha256
`0b2cd8eede3c8ae6c7d6d02cd98f464a7cfb119012caed41d0b59f3844abc97d`).
`run_rule_operation.py` enforces binding before each live run
(prompt / fixture / criteria / schema / schedule-sha drift →
`SCHEDULE_DRIFT`, inadmissible). Deterministic dry-run PASSes: 12
unique ids, 12 unique workspace/evidence dirs, 3 fixture hashes, 4
prompt hashes, candidate/control paths separate, no collisions.

## 9. Baseline live control smoke (§14)

`run_id=smoke-baseline-control-d3-4-0`, arm baseline, latent ATDD
fixture, exact model, existing OAuth. Result: exit 0, direct child
Skill event true, wrapper Skill event false, RDX bundle / sidecars /
rule_operation absent, no RP-* obligation leakage, Task 0,
workspace-delta PASS, artifact-consistency PASS, schema v4 PASS,
admissible SUCCESS. The control arm runs uncontaminated. Evidence:
`rdx-tea/evidence/live/smoke-baseline-control-d3-4-0/`.

## 10. Paired apparatus smoke (§15)

Baseline (the control run above) + candidate
(`smoke-paired-candidate-d3-4-0`) on the SAME latent fixture
(`atdd-api-async-latent`), same fixture_hash
(`3695de221cc8b4b3…`), same model, same MCP/settings/memory/tool
policy; only skills + prompts differ. Both admissible. Candidate
rule-operation PASS: active_packs `[api, async]`, expected rule
condition PASS (matched RP-ASYNC-005 + RP-API-001/004/005),
forbidden condition PASS, verifier PASS, 1 artifact / 1 sidecar,
workspace-delta PASS, artifact-consistency PASS, Task 0,
OBSERVED_SEQUENTIAL. The candidate cited the rules although the
latent story never named them — rules were TRIGGERED from tags/diff,
not hand-fed. Evidence:
`rdx-tea/evidence/live/smoke-paired-apparatus-d3-4-0/`.

Note: the first candidate attempt completed the model turn but did
NOT run the final `finalize-run` (no run-report.json) — an honest
WORKFLOW_FAILURE. The candidate prompt was strengthened to require
finalize-run completion (schedule v3 prompt hashes regenerated
pre-pilot); the re-run completed and is admissible. The failed
attempt is documented, not hidden.

## 11. Rule-operation grader

`grade_rule_operation.py` produced `RULE_OPERATION_PASS` over the two
smokes (1/1 candidate pass, 1/1 control clean). LLM diagnostic layer
is optional dry-run and did not influence the verdict. This is the
APPARATUS-level verdict for two smokes — NOT the 12-run pilot, which
is deliberately not executed in D3.4.0.

## 12. What is proven vs not

- PROVEN: the rule-operation apparatus is valid and complete — source
  dedupe, workspace delta, declared-file checks, artifact consistency,
  precommitted criteria, latent fixtures, schedule binding, v4
  admission, deterministic grader, and TWO admissible live smokes (a
  clean baseline control and a candidate that operates RDX rules on a
  latent fixture).
- NOT proven here: the full 12-run rule-operation pilot and its
  aggregate stability verdict; the live LLM diagnostic. These belong
  to the next stage.
