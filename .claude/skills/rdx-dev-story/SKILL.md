---
name: rdx-dev-story
description: RDX wrapper for the dev-story workflow. Orchestrates contract intake, Risk Router pre-pass, the bmad-dev-story child skill, evidence collection, and the rdx-validator. Acts as a soft-gate cooperative orchestrator — real enforcement lives in git hooks (Phase 5) and the CI required check, see RDX_TEST_STRATEGY.md §5.3.
---

# RDX Dev Story Wrapper

This skill is the BMad-integration surface of RDX. It wraps the standard
`bmad-dev-story` child skill with RDX-specific pre- and post-steps:

1. Contract intake — read story file, capture active risk tags
2. Risk Router pre-pass — record which packs the router activates
3. Invoke `bmad-dev-story` (the child) — standard BMad behavior
4. Evidence collection — gather diff + tool outputs into evidence
5. Run `rdx-validator` — deterministic Cat-1/Cat-2 checks
6. Final report — surface findings; on validator FAIL, halt the workflow

## Honest framing (T-V5-ACC-06)

This wrapper is a **soft gate** — a cooperative orchestrator that depends on
the LLM honoring the SKILL.md prose. It is NOT a programmatic enforcement
boundary. Real enforcement lives in:

- the pre-push git hook installed by `rdx-setup` (Mode 2 / Local Gated)
- the GitHub Actions required check (Mode 3 / CI Enforced)

A non-cooperative or distracted LLM can skip steps in this file. The hook
and CI are what actually block bad merges. The wrapper's job is UX + the
happy-path evidence trail.

## Recursion guard

This skill MUST NOT invoke itself. The only child skill it invokes is
`bmad-dev-story` (Step 3). If you find yourself about to call
`rdx-dev-story` from inside `rdx-dev-story`, STOP and emit the sentinel
`WRAPPER_RECURSION_DETECTED` instead. The no-recursion rule is structural:
there is exactly one Skill-tool invocation in this file, and it targets
`bmad-dev-story`.

## Conventions

- `{project-root}` is the project working directory where `_bmad/` lives.
- `{trace-log}` is the per-session trace file at
  `{project-root}/_bmad/rdx/last-run/trace.log`.
- `{evidence-out}` is `{project-root}/_bmad/rdx/last-run/evidence.json`.
- `{story-file}` is the path passed in via the `--story` argument or
  resolved from `_bmad/state/current-story.md`.

Create `{project-root}/_bmad/rdx/last-run/` if it does not exist before
writing trace/evidence artifacts.

---

## Step 1 — Contract intake + BEFORE marker

Read `{story-file}`. Extract the active risk tags from its `risk_tags:`
front-matter block (e.g. `risk_tags: [async, unsafe, ffi]`). If no
`risk_tags` field is present, set the list to `[]`.

Persist the captured tags to **stable storage** — write them to
`{project-root}/_bmad/rdx/last-run/risk-tags.before.json` as a JSON array.
This file is the canonical source for Step 6's tag-equality assertion
across the child boundary. Do NOT rely on chat memory or `persistent_facts`
ephemeral state — the on-disk file is the authority.

Append the BEFORE marker to the trace log:

```bash
mkdir -p {project-root}/_bmad/rdx/last-run
echo "BEFORE rdx-dev-story step=1 ts=$(date +%s)" >> {trace-log}
```

## Step 2 — Risk Router pre-pass

Consult `{project-root}/_bmad/rust-kb/section-5-router.md` and the
machine-readable `tests/contracts/router-rules.json` (shipped with RDX).
For each pack referenced by the captured risk tags or by file-path signals
in the diff, record the activation class (AUTO_ACTIVATE / AUTO_SUGGEST /
STORY_TAG_REQUIRED / REVIEW_REQUIRED).

Write the router decision to
`{project-root}/_bmad/rdx/last-run/router.json`. This file feeds the
validator's `--policy-config` argument in Step 5.

## Step 3 — Invoke child skill (bmad-dev-story)

Use the Skill tool to invoke the skill named `bmad-dev-story`. Pass the
story file path through; do NOT pass the full router or risk-tag context
(context discipline — only active tags + active KB sections, per Phase 3.4
of the plan).

The child skill is the standard BMad dev workflow. It will produce a diff
and update story state.

### Step 3a — Child error handling

If the child output contains the sentinel `ERROR_MARKER` (or any explicit
child-side error signal), do NOT crash this wrapper. Set
`wrapper_status=child_error` in `{project-root}/_bmad/rdx/last-run/state.json`
and continue to Step 4 — the validator still has useful work to do (it can
record EVIDENCE_REQUIRED or NOT_RUN verdicts honestly).

The principle: a child-emitted error is reportable, not catastrophic.
Crashing the wrapper would lose the evidence trail.

## Step 4 — AFTER marker + post-child artifact check

Append the AFTER marker:

```bash
echo "AFTER rdx-dev-story step=4 ts=$(date +%s)" >> {trace-log}
```

Check that the child produced the required post-child artifact — either a
non-empty diff at `{project-root}/_bmad/rdx/last-run/diff.patch` or
explicit evidence at `{project-root}/_bmad/rdx/last-run/evidence.json`.

If neither exists, emit the diagnostic sentinel `MISSING_ARTIFACT` and
HALT. Do not call the validator on no input. Record:

```
WRAPPER_HALTED_MISSING_ARTIFACT path={project-root}/_bmad/rdx/last-run/
```

Re-read the risk tags from
`{project-root}/_bmad/rdx/last-run/risk-tags.before.json` (the file you
wrote in Step 1) and verify the file is still present and parses as JSON.
This is the first half of the tag-preservation contract; the second half is
Step 6.

## Step 5 — Run rdx-validator

Invoke the validator with the artifacts collected so far:

```bash
python rdx-validator/rdx_validator/cli.py \
  --project-root {project-root} \
  --story {story-file} \
  --diff-file {project-root}/_bmad/rdx/last-run/diff.patch \
  --policy-config {project-root}/_bmad/rdx/last-run/router.json \
  --evidence-out {evidence-out}
```

**You MUST report the exact exit code.** Exit code mapping (per
`RDX_TEST_STRATEGY.md` §5.3):

| Exit code | Action |
|-----------|--------|
| 0 | continue to Step 6 |
| 1 | HALT — emit `WRAPPER_HALTED_DUE_TO_VALIDATOR_FAIL` |
| 2 | HALT — `WRAPPER_HALTED_ENVIRONMENT_UNAVAILABLE` |
| 3 | HALT — `WRAPPER_HALTED_BLOCKED` (approval/evidence required) |
| 4 | continue with REVIEW_REQUIRED note (informational in Mode 3) |

A non-zero exit code that maps to HALT means: stop here, do not call any
further skills, do not mark the story complete. Output the relevant
sentinel line so downstream tooling (the post-merge dashboard, the L5
eval harness) can parse the halt reason.

Soft-gate reminder: this is wrapper-level cooperation. The hook
(`.git/hooks/pre-push`) and the CI required check are what guarantee a
FAIL cannot reach `main` — see `RDX_VALIDATOR_ARCHITECTURE_VERIFICATION.md`
§15 (Variant V5 enforcement boundary).

## Step 6 — Risk-tag equality + final report

Re-read the risk tags from
`{project-root}/_bmad/rdx/last-run/risk-tags.before.json`. Compare with
the tags currently in `{story-file}`'s front matter. They MUST be
byte-identical (RDX persistent_facts and the story file together are the
stable storage that survives the child boundary — see T-L4-WR-006).

If they differ, record the diagnostic `RISK_TAG_MUTATION_DETECTED` with
the before/after values and treat as FAIL.

Then write the final report to
`{project-root}/_bmad/rdx/last-run/report.md` summarizing:

- Risk-Router activations (from Step 2's `router.json`)
- Child completion status (PASS / `child_error`)
- Validator verdicts grouped by category (Cat-1 deterministic, Cat-2
  evidence-bearing, Cat-3 review-required, Cat-4 approval-required)
- Soft-gate disclaimer: "This report is advisory. The pre-push hook and
  CI required check are the actual enforcement points."

Emit the literal sentinel `WRAPPER_FLOW_COMPLETE` on the last line of your
response if and only if all six steps above executed without HALT.

---

## Failure-mode summary (mapped to T-L4-WR-001..006)

| Sentinel | Scenario | Test ID |
|----------|----------|---------|
| `WRAPPER_FLOW_COMPLETE` | Happy path: BEFORE → CHILD → AFTER | T-L4-WR-001 |
| `wrapper_status=child_error` (continue) | Child emits `ERROR_MARKER` | T-L4-WR-002 |
| `WRAPPER_HALTED_DUE_TO_VALIDATOR_FAIL` | Validator exit code 1 | T-L4-WR-003 |
| `WRAPPER_RECURSION_DETECTED` | Self-invocation attempt | T-L4-WR-004 |
| `WRAPPER_HALTED_MISSING_ARTIFACT` | Post-child artifact absent | T-L4-WR-005 |
| `RISK_TAG_MUTATION_DETECTED` | Tags not preserved across child | T-L4-WR-006 |

This is workflow UX, not hard enforcement. See the soft-gate disclaimer at
the top of this file.
