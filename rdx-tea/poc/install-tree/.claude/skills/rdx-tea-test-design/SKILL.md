---
name: rdx-tea-test-design
description: RDX wrapper for the BMad TEA `bmad-testarch-test-design` workflow. Runs the D3.2 two-phase orchestration — deterministic prepare (active-context bundle, sequential-mode assertion), invokes the original bmad-testarch-test-design child skill, then deterministic finalize/bind/verify. Mirrors the rdx-dev-story pattern; direct TEA invocation without this wrapper is UNVALIDATED.
---

# rdx-tea-test-design — Wrapper for BMad TEA `bmad-testarch-test-design`

You are the RDX-TEA wrapper for TEA's `bmad-testarch-test-design` workflow.

## Contract

- Always run **sequential** mode. Refuse to proceed if `tea_execution_mode` in `{project-root}/_bmad/tea/config.yaml` is not the literal `sequential`.
- Every artefact of a single invocation shares one `run_id` (URL-safe slug, ≥ 4 chars). Runtime dir: `{project-root}/_bmad/rdx-tea/runtime/test-design/<run_id>/`.
- Direct invocation of the child skill without this wrapper is treated as UNVALIDATED — no sidecar, no verifier.

## Conventions

- Bare paths (`resources/…`) resolve from the skill root.
- `{project-root}` resolves from the project working directory.
- `{skill-root}` resolves to this skill's install directory (`.claude/skills/rdx-tea-test-design/`).

## Activation

### Step 1 — Resolve inputs
- Read `{project-root}/_bmad-run/story.md` (or the story the user provided).
- Read tags from `{project-root}/_bmad-run/tags.txt` if present.
- Read `{project-root}/_bmad-run/rdx-tea-invocation.json` if present.
  If it exists, use its `run_id` field verbatim. Do NOT generate a
  timestamp id when the invocation file is present. If it is absent,
  fall back to `td-YYYYMMDD-HHMMSS`.

### Step 2 — Resolve identity strictly
- `head_sha = git rev-parse HEAD` (inside `{project-root}`)
- `base_sha = git merge-base HEAD origin/main` (fallback to `main`, then `HEAD^`, then head — for single-commit repos)
- Verify both via `git cat-file -e`. Refuse to continue if either fails.

### Step 3 — Verify TEA runtime mode
- Read `{project-root}/_bmad/tea/config.yaml:tea_execution_mode`.
- If it is not exactly `sequential`, HALT and print a fix-config instruction.

### Step 4 — Prepare
Run:
```
python3 {project-root}/_bmad/rdx-tea/scripts/rdx_tea_wrapper.py prepare-run \
    --workflow test-design \
    --project-root {project-root} \
    --run-id <run_id> \
    --skill-dir {project-root}/.claude/skills/bmad-testarch-test-design \
    --base-sha <base_sha> --head-sha <head_sha>
```
HALT on non-zero exit. The command writes:
  - `_bmad/rdx-tea/runtime/test-design/<run_id>/active-context.md` (bundle)
  - `_bmad/rdx-tea/runtime/test-design/<run_id>/run-manifest.json`
  - `_bmad/rdx-tea/runtime/test-design/<run_id>/run-state.json` (snapshot)
  - `_bmad/rdx-tea/runtime/test-design/<run_id>/diff.patch`

### Step 5 — Invoke the child skill
Dispatch the standard `bmad-testarch-test-design` skill (child) with the sequential-mode hint. The child reads its `persistent_facts`, which now include the active-context bundle written in Step 4 (via the `_bmad/custom/bmad-testarch-test-design.toml` overlay installed by `rdx-tea-setup`).

Do NOT simulate the child skill.

### Step 6 — Finalize
Run:
```
python3 {project-root}/_bmad/rdx-tea/scripts/rdx_tea_wrapper.py finalize-run \
    --workflow test-design \
    --project-root {project-root} \
    --run-id <run_id>
```
This discovers every artefact the child wrote (delta since Step 4 snapshot), binds a sidecar per artefact, and runs the D3.2 verifier. HALT on non-zero exit.

### Step 7 — Report
Print the `_bmad/rdx-tea/runtime/test-design/<run_id>/run-report.json` contents (redacted). If any verifier check FAILed, surface the check names to the user.

## Critical actions

- Never write a Cat-1 PASS or any RDX verdict field into an artefact. Verdicts are computed downstream by `rdx-tea-validate` (deferred).
- Never invoke the child with `--simulate-child` or `--test-write-fake-artefact` in a production session — those flags are for headless PoC tests only.
- Never touch upstream skill directories. All overlays live under `{project-root}/_bmad/custom/`.
