---
name: rdx-code-review
description: RDX wrapper for the BMad Code Review workflow. Invokes bmad-code-review as a child skill, then adds the RDX Rule Auditor (rdx-judgment) layer before emitting a unified final report. Soft-gate cooperative orchestrator — real enforcement lives in git hooks (Mode 2) and the CI required check (Mode 3). See RDX_TEST_STRATEGY.md §8 for the R1 vs R2 decision.
---

# RDX Code Review Wrapper (R2)

This skill is the BMad-integration surface of RDX for the Code Review
menu code (CR). It wraps the standard `bmad-code-review` child skill
with an RDX-specific post-step:

1. Contract intake — read story + diff + active packs (from the prior
   rdx-dev-story run's `router.json`)
2. Invoke `bmad-code-review` (the child) — standard 3 review layers
   (Blind / Edge Case / Acceptance) — unchanged
3. Invoke `rdx-judgment` — RDX Rule Auditor — Cat-3 findings against
   active-pack rules
4. Unified final report — merge standard + RDX layers; one verdict
   decision; halt on validator FAIL

The R2 design is the primary integration per `RDX_TEST_STRATEGY.md` §8.
The R1 alternative (on_complete hook) is shipped as a *control test*
artefact only — see `.claude/skills/rdx-setup/assets/workflow-
overrides/bmad-code-review.toml`. R1's timing limitation (findings
arrive AFTER triage finalization) is why R2 is primary.

## Honest framing (T-V5-ACC-06)

This wrapper is a **soft gate** — a cooperative orchestrator that
depends on the LLM honoring the SKILL.md prose. It is **not hard
enforcement**. Real enforcement lives in:

- the pre-push git hook installed by `rdx-setup` (Mode 2 / Local Gated)
- the GitHub Actions required check (Mode 3 / CI Enforced)
- the rdx-judgment-finding v1 JSON Schema (Cat-1 immutability)
- the `filter_active_scope` helper in `rdx_validator.judgment` (scope
  discipline)

A non-cooperative LLM can skip steps in this file. The hook, CI,
schema, and scope filter are what actually block bad findings. This
file is workflow UX + the happy-path evidence trail.

## Recursion guard

This skill MUST NOT invoke itself. The only Skill-tool invocations in
this file target `bmad-code-review` (Step 2) and `rdx-judgment` (Step
3). If you find yourself about to call `rdx-code-review` from inside
`rdx-code-review`, STOP and emit the sentinel
`WRAPPER_RECURSION_DETECTED` instead.

## Conventions

- `{project-root}` is the project working directory where `_bmad/` lives.
- `{trace-log}` is the per-session trace file at
  `{project-root}/_bmad/rdx/last-run/cr-trace.log`.
- `{judgment-out}` is `{project-root}/_bmad/rdx/last-run/judgment.json`.
- `{cr-report-out}` is `{project-root}/_bmad/rdx/last-run/cr-report.md`.
- `{router-json}` is `{project-root}/_bmad/rdx/last-run/router.json`
  (produced by the most recent rdx-dev-story run — REQUIRED).

---

## Step 1 — BEFORE marker + scope read

Append the BEFORE marker:

```bash
mkdir -p {project-root}/_bmad/rdx/last-run
echo "BEFORE rdx-code-review step=1 ts=$(date +%s)" >> {trace-log}
```

Read `{router-json}`. If it does not exist, this CR was invoked
without a prior dev-story run — emit `WRAPPER_HALTED_NO_ROUTER` and
HALT. (The reviewer needs to know which packs are in scope.)

Capture `active_packs`, `review_required_rules`, and the diff path.

## Step 2 — Invoke child skill (bmad-code-review)

Use the Skill tool to invoke the skill named `bmad-code-review`. This
runs the standard 3 review layers (Blind / Edge Case / Acceptance) —
unchanged from the base BMad behavior. Pass the diff path and the
story; do NOT pass the active-packs envelope (the child does not need
it).

The child writes its findings to
`{project-root}/_bmad/rdx/last-run/cr-standard.json` (or whatever its
canonical output path is; surface the path in the trace log).

### Step 2a — Child error handling

If the child output contains `ERROR_MARKER` or any explicit child-
side error signal, do NOT crash this wrapper. Set
`wrapper_status=child_error` in
`{project-root}/_bmad/rdx/last-run/cr-state.json` and continue to
Step 3 — the RDX Rule Auditor still has useful work to do on the
diff alone.

## Step 3 — Invoke rdx-judgment

Use the Skill tool to invoke the skill named `rdx-judgment`. Pass the
active-packs envelope (from Step 1) and the validator findings (from
the prior dev-story `evidence.json`). The judgment skill writes
`{judgment-out}`.

Check the rdx-judgment exit sentinel:

| Sentinel | Action |
|----------|--------|
| `RDX_JUDGMENT_COMPLETE` | continue to Step 4 |
| `RDX_JUDGMENT_SCHEMA_VIOLATION` | HALT — emit `WRAPPER_HALTED_DUE_TO_JUDGMENT_SCHEMA`; a finding tried to overturn Cat-1 |
| `RDX_JUDGMENT_SCOPE_VIOLATION` | continue with WARNING; surface the out-of-scope findings in the unified report so the reviewer can prune them |
| `JUDGMENT_RECURSION_DETECTED` | HALT — emit `WRAPPER_HALTED_JUDGMENT_RECURSION` |

## Step 4 — Unified final report

Write `{cr-report-out}` with sections in this order:

1. **Standard Review (bmad-code-review)** — the three standard layers
   from Step 2's output.
2. **RDX Rule Auditor (rdx-judgment)** — the Cat-3 findings from
   `{judgment-out}` grouped by verdict (PASS / FAIL /
   DECISION_REQUIRED / SPECIALIST_REQUIRED / INSUFFICIENT_EVIDENCE).
3. **Validator findings (carried from dev-story)** — Cat-1/2 verdicts
   from `evidence.json`. These are immutable — present them verbatim;
   the judgment layer cannot have changed them.
4. **Combined verdict** — single FAIL/PASS/REVIEW_REQUIRED decision
   per the rules in `RDX_TEST_STRATEGY.md` §5.3. FAIL on any Cat-1 or
   Cat-2 from the validator dominates. Cat-3 FAIL dominates
   REVIEW_REQUIRED.
5. **Soft-gate disclaimer** — "This report is advisory. The pre-push
   hook and CI required check are the actual enforcement points."

## Step 5 — AFTER marker + completion sentinel

Append the AFTER marker:

```bash
echo "AFTER rdx-code-review step=5 ts=$(date +%s)" >> {trace-log}
```

Emit the literal sentinel `RDX_CR_FLOW_COMPLETE` on the last line of
your response if and only if all five steps executed without HALT.

---

## Failure-mode summary

| Sentinel | Scenario |
|----------|----------|
| `RDX_CR_FLOW_COMPLETE` | Happy path: BEFORE → CHILD_CR → JUDGMENT → UNIFIED_REPORT → AFTER |
| `WRAPPER_HALTED_NO_ROUTER` | router.json missing — CR invoked without prior dev-story run |
| `wrapper_status=child_error` (continue) | bmad-code-review emitted ERROR_MARKER |
| `WRAPPER_HALTED_DUE_TO_JUDGMENT_SCHEMA` | rdx-judgment finding violated v1 schema (typically Cat-1 PASS by evaluator) |
| `WRAPPER_HALTED_JUDGMENT_RECURSION` | rdx-judgment tried to call itself |
| `WRAPPER_RECURSION_DETECTED` | rdx-code-review tried to call itself |

This is workflow UX, **not hard enforcement**. See the soft-gate
disclaimer at the top of this file.

The structural contract for this wrapper is locked by the L4 tests in
`tests/bmad/code-review/test_code_review_wrappers.py`. The runtime
LLM-cooperative behavior is the same surface as the Phase 3 rdx-dev-
story wrapper — measured by L5 evals + one-shot Claude Code sessions
per `RDX_TEST_STRATEGY.md` §2.
