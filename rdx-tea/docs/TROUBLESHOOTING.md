# TROUBLESHOOTING — RDX-TEA refusals

The adapter fails **closed**: when an invariant is violated it refuses and
tells you why, rather than producing a misleading result. This guide maps
the common refusals to their fix.

## Authentication is preserved

**Symptom:** you are unsure whether RDX-TEA changed your login, or you are
looking for where to configure a credential.

**Explanation:** RDX-TEA has no authentication step. The installer writes
and reads no authentication material, and never sets or overrides the CLI
configuration-directory environment variable. Your existing session is
inherited unchanged. There is nothing to configure and nothing to undo.
If your session works for BMad TEA today, it works for RDX-TEA — the
adapter never touches it.

## TEA mode is not sequential

**Symptom:** the wrapper HALTs with a message that
`tea_execution_mode` resolves to something other than `sequential` (e.g.
`auto`, `subagent`, `agent-team`, or empty).

**Cause:** the wrapper runs sequential mode only, and asserts the literal
`sequential` at both `prepare-run` and `finalize-run`. `auto` is rejected
because it could resolve to a subagent runtime.

**Fix:** set the mode in `<project>/_bmad/tea/config.yaml`:

```yaml
tea_execution_mode: sequential
```

Then re-invoke the wrapper Skill.

## The delta is empty

**Symptom:** `finalize-run` fails closed with "no new artefact discovered
under output dirs", or the admission `run_outcome` is `WORKFLOW_FAILURE`
with "no new artefacts".

**Cause:** the child skill either never ran, wrote nothing, or wrote
outside the canonical output roots; or an existing artefact's SHA was
unchanged (the child did not actually write it).

**Fix:**

1. Confirm the child `bmad-testarch-<workflow>` skill actually ran to
   completion in the same session (it must not be gated interactively).
2. Confirm the child wrote under the project's output roots
   (`_bmad-output/**`, including `test-artifacts`).
3. Note: a **docs-only** diff legitimately projects an empty bundle. If
   there is genuinely no Rust surface and no artefact to produce, an empty
   delta is expected — there is nothing to finalize.

## A run lock is held

**Symptom:** `prepare-run` refuses with "another RDX-TEA run is active …
Refuse to start a second concurrent run in the same workspace."

**Cause:** the active-run lock at
`<project>/_bmad/rdx-tea/runtime/active-run.lock` is held by another run.
Only one RDX-TEA run may be active per workspace.

**Fix:**

1. If another run is genuinely in progress, wait for it to finish —
   `finalize-run` releases the lock (even when it fails closed).
2. If a previous run crashed and left a stale lock, inspect the lock
   (it is a small JSON file recording `run_id`, `workflow`, `pid`,
   `created_at`). Once you have confirmed no run is active, remove the
   stale lock file and re-invoke.

## Overlay restoration

**Symptom:** you had a pre-existing `_bmad/custom/bmad-testarch-<workflow>.toml`
overlay and want to know what happened to it.

**Explanation:** `prepare-run` writes a run-specific overlay pointing at
this run's bundle, backing up any pre-existing overlay to
`<run dir>/overlay-backup.toml`. `finalize-run` restores that backup (or
removes the wrapper-owned overlay if there was none) — always, even when
the run fails closed. If a crash interrupted a run mid-flight, restore your
overlay manually from `overlay-backup.toml` in the run directory.

## A verifier check failed

**Symptom:** the `run-report.json` shows a `verifier` entry with
`verdict: FAIL` and one or more `failed_checks`; admission `run_outcome` is
`VERIFIER_FAILURE`.

**Cause / fix by check** (see
[EVIDENCE_INSPECTION.md](EVIDENCE_INSPECTION.md#verifier-checks-behavioural-integrity)
for the full list):

- `bundle_hash` / `manifest_hash` / `artifact_hash` — a file was modified
  after it was bound. Do not edit the bundle, manifest, or artefact between
  `prepare-run` and `finalize-run`; re-run from `prepare-run`.
- `base_head_exist` — a referenced git commit is gone (e.g. history was
  rewritten). Re-run with valid `--base-sha`/`--head-sha`.
- `canonical_snapshot` / `source_lock` — the installed KB or `sources.lock`
  drifted from the pinned identity. Re-install the adapter (`update`).
- `artifact_boundary` — the artefact is a symlink or lands outside the
  declared output roots. The child must write real files inside
  `_bmad-output/**`.

## Consistency failed

**Symptom:** `consistency_status: FAIL`; admission `run_outcome` is
`CONSISTENCY_FAILURE`. The `reasons` come from
`workspace_delta_consistency` and/or `artifact_consistency`.

**Cause / fix:**

- **Phantom claim** — an artefact claims a generated file that is not on
  disk. Ensure every file the artefact references was actually written.
- **Declared-but-missing** — the delta declares a generated file that is
  absent. Same fix: write it, or stop declaring it.
- **Duplicate frontmatter** — a **warning only**; it does not fail the run.
  You may clean it up but it is not blocking.

## Admission says not admissible

**Symptom:** `admission.admissible` is `false`.

**How to read it:** the `run_outcome` names the first failing group and
`reasons` lists the specifics. Recompute it yourself at any time:

```bash
python3 <project>/_bmad/rdx-tea/scripts/admission.py admit \
    --report <project>/_bmad/rdx-tea/runtime/<workflow>/<run_id>/run-report.json \
    --state  <project>/_bmad/rdx-tea/runtime/<workflow>/<run_id>/run-state.json
```

Then follow the matching section above:

| `run_outcome` | Section |
|---|---|
| `MODE_FAILURE` | [TEA mode is not sequential](#tea-mode-is-not-sequential) |
| `WORKFLOW_FAILURE` | [The delta is empty](#the-delta-is-empty) (also: a subagent was observed — re-run strictly sequential so no Task/subagent dispatch occurs) |
| `VERIFIER_FAILURE` | [A verifier check failed](#a-verifier-check-failed) |
| `CONSISTENCY_FAILURE` | [Consistency failed](#consistency-failed) |
| `PARTIAL_RUN` | A `--verify-only` advisory run, or a run whose state phase is not `finalized`, is never a finalized admission. Complete a full `finalize-run`. |
| `SCHEMA_FAILURE` | A primitive field is missing or wrong-typed. Re-run from `prepare-run`; do not hand-edit `run-report.json`. |

The admission gate recomputes from primitive fields and **ignores any
recorded `admissible` flag**, so its verdict is authoritative even for a
tampered report.

## Installer version refusal

**Symptom:** the installer prints
`{"status": "REFUSED", "reason": "... TEA version ... outside the supported
range ..."}` and installs nothing.

**Cause:** `<project>/_bmad/tea/config.yaml` declares a TEA version outside
the window supported by this adapter (derived from `sources.lock`: same
major, at least the pinned minor/patch), or an unparseable version.

**Fix:** use an adapter build whose `sources.lock` supports your project's
TEA version, or align the project's declared TEA version with the supported
range. The installer is fail-closed by design — it will not install against
an unsupported TEA.

---

If a refusal is not covered here, read the `reasons` array in
`run-report.json` (or the installer's `reason` field): every fail-closed
path records a human-readable reason.
