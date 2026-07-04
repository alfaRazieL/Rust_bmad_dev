# D3.4.1 Blockers

## Closed in this stage

- **12-run rule-operation pilot (was OPEN in D3.4.0 §1)** — CLOSED.
  Executed the locked `D3_4_RULE_OPERATION_RUNS.v3.json` (9 candidate +
  3 control) against the fixed apparatus. Deterministic verdict
  **RULE_OPERATION_PASS** (9/9 candidate pass, 3/3 control clean).
- **Candidate finalize-completion stability (was MITIGATED in D3.4.0
  §2)** — CHARACTERIZED and CLOSED for this pilot. Finalize-run
  completion = 9/9 (100%) in a single session, zero retries. The
  D3.4.0 one-off `WORKFLOW_FAILURE` did not recur on any of the 9
  candidate runs, including the longer ATDD story (runs 4–6).
- **Latent scheduled run_one path never live-exercised** — CLOSED. First
  live scheduled execution surfaced and fixed a real apparatus defect
  (below).

## Fixed apparatus defects surfaced by this pilot

- **F-D3.4.1-1 — false SCHEDULE_DRIFT on every scheduled run.**
  `run_live._finalize_evidence_v4` compared the schedule's pinned
  prompt-hash (a run-id-normalised TEMPLATE hash, `sha256(arm_prompt(
  arm, wf, "__RUN_ID__"))`) against the REAL per-run prompt hash (which
  embeds the variable run_id). They can never match, so every `run_one`
  execution was marked non-admissible with `prompt_hash drift`, despite
  a fully correct RDX lifecycle. Fixed by computing the binding hash
  with the same `__RUN_ID__` placeholder the schedule generator and
  dry-run use; the per-run run_id remains verified by
  `run_id_handshake`, and `invocation.prompt_hash` still records the
  real prompt hash. Regression test:
  `test_scheduled_prompt_hash_is_run_id_normalised_template`. The locked
  schedule (`0b2cd8ee…`) and criteria (`3288de4f…`) were NOT modified.
  Commit `b9b244c`. (D3.4.0 smokes hid this because they ran
  `NOT_SCHEDULED` via `run_smoke`.)

- **F-D3.4.1-2 — harness requires absolute paths (operator note).**
  `invoke_runtime.invoke` runs the CLI with `cwd=<workspace>` while
  passing `--settings/--add-dir/--mcp-config`; relative values break
  ("Settings file not found"). Runners MUST pass an absolute
  `--out-root`. No code change; documented in the preserved attempt-01
  NOTE and the driver.

## Open (non-blocking; do NOT block D4 / MASTER_IMPLEMENTATION_PLAN)

- **§1 Baseline artefact production is interaction-gated.** The bare
  child `bmad-testarch-*` TEA workflow is interactive; without the RDX
  wrapper's non-interactive prepare/finalize scaffolding it stops at the
  greeting/elicitation step and emits 0 artefacts. This is acceptable
  for the control's isolation-only role (artefacts are not a baseline
  admission requirement) but means the control arm does not
  independently demonstrate full child-artefact production. If a future
  stage wants a baseline that also drives artefacts, add a
  non-interactive baseline prompt (kept RDX-free) — but note this is not
  needed to prove rule-operation.

- **§2 Schedule prompt-hash naming.** The schedule field `prompt_hash`
  is really a template hash. Consider renaming/adding
  `prompt_template_hash` in a future schedule version (would change the
  schedule sha — out of scope here) to prevent recurrence of the
  F-D3.4.1-1 confusion.

- **§3 LLM diagnostic layer.** Remains DRY_RUN_ONLY / optional; cannot
  override the deterministic verdict. Not run.

- **§4 Absolute paths embedded in evidence.** Final pilot bundles record
  absolute machine workspace paths (as the D3.4.0 smokes did with
  `/tmp/...`). No secrets are exposed (paths only). Cosmetic.

## Findings carried forward (load-bearing, still valid)

- F1 (D3.4.0) — forbidden packs judged by ACTIVE packs, not prose
  cross-references. Held: docs-only candidates activated no pack.
- F2 (D3.4.0) — duplicate frontmatter treated as reconcilable warning,
  fail only on fabrication. Held: artifact_consistency PASS on all.
- F3 (D3.4.0) — declared generated `.rs` test files collected/verified/
  preserved. Held: ATDD candidate runs verifier PASS with preserved
  artefacts.
