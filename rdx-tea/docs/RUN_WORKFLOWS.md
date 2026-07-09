# RUN WORKFLOWS — the validated wrapper path

How to run a BMad TEA workflow through the RDX-TEA wrapper. Two workflows
are supported:

- **`rdx-tea-test-design`** — wraps `bmad-testarch-test-design`.
- **`rdx-tea-atdd`** — wraps `bmad-testarch-atdd`.

You invoke the **wrapper Skill**, not the child TEA skill directly. The
wrapper runs a deterministic two-phase lifecycle and invokes the
unmodified child skill in between.

> Direct invocation of the child `bmad-testarch-*` skill without the
> wrapper is **unvalidated**: it produces no active-context bundle, no
> sidecar, and no verifier result. Always go through the wrapper Skill.

## Prerequisite: TEA must be in sequential mode

The wrapper runs **sequential mode only**. Set it once per project in
`<project>/_bmad/tea/config.yaml`:

```yaml
tea_execution_mode: sequential
```

Any other value — including `auto`, `subagent`, and `agent-team` — is
rejected. The wrapper asserts the literal `sequential` at both `prepare-run`
and `finalize-run`. If it is not sequential, the wrapper HALTs with a
fix-config instruction (see
[TROUBLESHOOTING.md](TROUBLESHOOTING.md#tea-mode-is-not-sequential)).

Sequential mode means the child skill runs to completion in **one
session** without spawning any Task/subagent worker. The observed Task
dispatch count MUST be `0`.

## The lifecycle: prepare → child → finalize

Invoke the wrapper Skill (`rdx-tea-test-design` or `rdx-tea-atdd`). The
Skill orchestrates three steps:

### 1. `prepare-run` (deterministic)

The wrapper resolves inputs and identity, asserts sequential mode,
generates the diff, builds the active-context bundle, writes a run-specific
overlay, acquires the workspace lock, and snapshots the output directories:

```bash
python3 <project>/_bmad/rdx-tea/scripts/rdx_tea_wrapper.py prepare-run \
    --workflow test-design \
    --project-root <project> \
    --run-id <run_id> \
    --skill-dir <project>/.claude/skills/bmad-testarch-test-design \
    --base-sha <base_sha> --head-sha <head_sha>
```

(For ATDD, use `--workflow atdd` and
`--skill-dir <project>/.claude/skills/bmad-testarch-atdd`.)

`prepare-run` writes, under
`<project>/_bmad/rdx-tea/runtime/<workflow>/<run_id>/`:

- `active-context.md` — the projected active-context bundle;
- `run-manifest.json` — bundle sha, canonical-snapshot sha, identity;
- `run-state.json` — the pre-run output snapshot (`phase: prepared`);
- `diff.patch` — the base..head diff the bundle was projected from.

Identity is strict: `head_sha` and `base_sha` must both exist as git
objects (verified with `git cat-file -e`). The wrapper refuses to continue
otherwise.

### 2. Invoke the child TEA skill (same session, subagents disabled)

The wrapper dispatches the standard `bmad-testarch-<workflow>` child skill
**in the same session**, non-interactively, with subagent/Task dispatch
disabled:

```
--disallowedTools Task TaskOutput TaskStop
```

The child reads its `persistent_facts`, which now include the
active-context bundle (via the overlay `prepare-run` wrote under
`_bmad/custom/`). The wrapper **never simulates the child** and **never
dispatches it through a Task/subagent tool** — the sequential guard plus
this disallow-list keep the whole run in one session.

If the child cannot be dispatched in this session, the wrapper HALTs and
reports `NOT_RUN`. It does not fabricate an artefact.

### 3. `finalize-run` (deterministic)

After the child returns, the wrapper discovers the delta (files the child
wrote since the prepare snapshot), binds one sidecar per artefact, runs the
verifier, checks workspace-delta and artifact consistency, computes the
admission verdict, restores the overlay, and releases the lock:

```bash
python3 <project>/_bmad/rdx-tea/scripts/rdx_tea_wrapper.py finalize-run \
    --workflow test-design \
    --project-root <project> \
    --run-id <run_id>
```

`finalize-run` fails closed if: no new artefact was discovered, an
artefact's SHA is unchanged (the child never wrote), any sidecar fails
verification, workspace/artifact consistency fails, or the resolved mode is
not sequential. On any of these it still writes an honest `run-report.json`
recording the failure — it never silently promotes a failed run.

## The run-report

`finalize-run` writes the aggregate report at:

```
<project>/_bmad/rdx-tea/runtime/<workflow>/<run_id>/run-report.json
```

Report it back (redacted) after the run. If any verifier check FAILed,
surface the failing check names. For ATDD, also surface the `observed_mode`
field verbatim.

To read and interpret the report, sidecars, verifier, and admission block,
see [EVIDENCE_INSPECTION.md](EVIDENCE_INSPECTION.md).

## Run identity (`run_id`)

Every artefact of a single invocation shares one `run_id` (a URL-safe slug,
at least 4 characters). If `<project>/_bmad-run/rdx-tea-invocation.json`
exists, the wrapper uses its `run_id` verbatim; otherwise it falls back to
`td-YYYYMMDD-HHMMSS` (test-design) or `atdd-YYYYMMDD-HHMMSS` (ATDD). Two
concurrent runs in the same workspace are refused by the active-run lock —
see [TROUBLESHOOTING.md](TROUBLESHOOTING.md#a-run-lock-is-held).

## Optional inputs

`prepare-run` reads these if present (all optional):

- `<project>/_bmad-run/story.md` — the story under test;
- `<project>/_bmad-run/tags.txt` — story tags that gate pack activation;
- `<project>/_bmad-run/rdx-tea-invocation.json` — a pinned `run_id`.

A docs-only diff (no Rust surface) projects an empty bundle — that is
expected, not a failure.
