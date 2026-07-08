---
name: rdx-tea-atdd
description: RDX wrapper for the BMad TEA `bmad-testarch-atdd` workflow. Runs the D3.3 two-phase orchestration — deterministic prepare (active-context bundle, sequential-mode assertion, run-specific overlay), invokes the original bmad-testarch-atdd child skill, then deterministic finalize/bind/verify. Mirrors the rdx-dev-story pattern; direct TEA invocation without this wrapper is UNVALIDATED.
---

# rdx-tea-atdd — Wrapper for BMad TEA `bmad-testarch-atdd`

You are the RDX-TEA wrapper for TEA's `bmad-testarch-atdd` workflow.

## Contract

- Always run **sequential** mode. Refuse to proceed if `tea_execution_mode` in `{project-root}/_bmad/tea/config.yaml` is not the literal `sequential`.
- Every artefact of a single invocation shares one `run_id` (URL-safe slug, ≥ 4 chars). Runtime dir: `{project-root}/_bmad/rdx-tea/runtime/atdd/<run_id>/`.
- Direct invocation of the child skill without this wrapper is treated as UNVALIDATED — no sidecar, no verifier.
- ATDD's step-c files include subagent-payload construction (`bmad-testarch-atdd/steps-c/step-04-generate-tests.md:56-83`). The wrapper's sequential guard is load-bearing.

## Conventions

- Bare paths (`resources/…`) resolve from the skill root.
- `{project-root}` resolves from the project working directory.
- `{skill-root}` resolves to this skill's install directory (`.claude/skills/rdx-tea-atdd/`).

## Activation

### Step 1 — Resolve inputs
- Read `{project-root}/_bmad-run/story.md` (or the story the user provided).
- Read tags from `{project-root}/_bmad-run/tags.txt` if present.
- Read `{project-root}/_bmad-run/rdx-tea-invocation.json` if present.
  If it exists, use its `run_id` field verbatim. Do NOT generate a
  timestamp id when the invocation file is present. If it is absent,
  fall back to `atdd-YYYYMMDD-HHMMSS`.

### Step 2 — Resolve identity strictly
- `head_sha = git rev-parse HEAD` (inside `{project-root}`)
- `base_sha = git merge-base HEAD origin/main` (fallback to `main`, then `HEAD^`, then head — for single-commit repos)
- Verify both via `git cat-file -e`. Refuse to continue if either fails.

### Step 3 — Verify TEA runtime mode
- Read `{project-root}/_bmad/tea/config.yaml:tea_execution_mode`.
- If it is not exactly `sequential`, HALT and print a fix-config instruction.
- `auto` is rejected — ATDD would otherwise resolve to subagent mode when a runtime probe reports a subagent runtime.

### Step 4 — Prepare
Run:
```
python3 {project-root}/_bmad/rdx-tea/scripts/rdx_tea_wrapper.py prepare-run \
    --workflow atdd \
    --project-root {project-root} \
    --run-id <run_id> \
    --skill-dir {project-root}/.claude/skills/bmad-testarch-atdd \
    --base-sha <base_sha> --head-sha <head_sha>
```
HALT on non-zero exit. The command:

- writes the run-specific overlay at `_bmad/custom/bmad-testarch-atdd.toml` referencing the exact `<run_id>` bundle path;
- backs up any pre-existing overlay under `_bmad/rdx-tea/runtime/atdd/<run_id>/overlay-backup.toml`;
- acquires `_bmad/rdx-tea/runtime/active-run.lock` (second concurrent run in the same workspace refuses);
- writes `_bmad/rdx-tea/runtime/atdd/<run_id>/active-context.md` (bundle), `run-manifest.json`, `run-state.json`, `diff.patch`.

### Step 5 — Invoke the child skill
Dispatch the standard `bmad-testarch-atdd` skill (child) with a sequential-mode hint. The child reads its `persistent_facts`, which now include the RDX active-context bundle written in Step 4 (via the overlay from Step 4).

Invoke the child in the SAME session, non-interactively, with subagent/Task
dispatch disabled: pass `--disallowedTools Task TaskOutput TaskStop`. ATDD's
step-c files construct subagent payloads; the sequential guard plus this
disallow-list keep the run in one session — the observed Task dispatch count
MUST be 0. Never dispatch the child via a `Task`/subagent tool.

Do NOT simulate the child skill. If you cannot dispatch the child in this session, HALT and report `NOT_RUN` — do NOT run `--test-write-fake-artefact` in a production session.

### Step 6 — Finalize
Run:
```
python3 {project-root}/_bmad/rdx-tea/scripts/rdx_tea_wrapper.py finalize-run \
    --workflow atdd \
    --project-root {project-root} \
    --run-id <run_id>
```
This discovers every artefact the child wrote (delta since Step 4 snapshot), binds a sidecar per artefact, and runs the D3.3 verifier. It also restores the pre-existing overlay from backup and releases the active-run lock. HALT on non-zero exit.

### Step 7 — Report
Print the `_bmad/rdx-tea/runtime/atdd/<run_id>/run-report.json` contents (redacted). If any verifier check FAILed, surface the check names to the user. Include the `observed_mode` field verbatim.

## Critical actions

- Never write a Cat-1 PASS or any RDX verdict field into an artefact. Verdicts are computed downstream by `rdx-tea-validate` (deferred).
- Never invoke the child with `--simulate-child` or `--test-write-fake-artefact` in a production session — those flags are for headless PoC tests only.
- Never touch upstream skill directories. All overlays live under `{project-root}/_bmad/custom/`.
