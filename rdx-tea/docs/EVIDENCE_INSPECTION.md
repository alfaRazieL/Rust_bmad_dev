# EVIDENCE INSPECTION — reading a run's evidence

Every finalized run leaves a self-describing evidence trail under:

```
<project>/_bmad/rdx-tea/runtime/<workflow>/<run_id>/
```

This guide explains each piece and how to re-check admissibility yourself.

## `run-report.json` — the aggregate

`finalize-run` writes `run-report.json` in the run directory. Its primitive
fields:

| Field | Meaning |
|---|---|
| `schema_version` | `rdx-tea-run.v1`. |
| `workflow` / `run_id` | Which workflow, which run. |
| `execution_mode` / `requested_mode` / `resolved_mode` | All must be `sequential`. `resolved_mode` echoes the host `_bmad/tea/config.yaml`. |
| `observed_mode` | `OBSERVED_SEQUENTIAL`, `INFERRED_ABSENT`, or `OBSERVED_SUBAGENT` (a Task/subagent was seen — inadmissible). |
| `new_artefacts` | Paths the child wrote (the delta). |
| `sidecars` | One sidecar object per artefact (see below). |
| `verifier` | One verifier result per sidecar (see below). |
| `workspace_delta` | The reality-checked delta the finalize computed. |
| `workspace_delta_consistency` | `{status, reasons}` — `PASS`/`FAIL`. |
| `artifact_consistency` | `{status, reasons}` — phantom claims fail; duplicate frontmatter warns. |
| `consistency_status` | Aggregate `PASS`/`FAIL` of the two consistency checks. |
| `admission` | The recomputed FINALIZED-admissibility verdict (see below). |
| `created_at` / `finalized_at` | Honest audit timestamps (not part of any hash). |

Read it with any JSON tool, for example:

```bash
python3 -c "import json,sys; d=json.load(open(sys.argv[1])); \
print('admissible:', d['admission']['admissible'], d['admission']['run_outcome']); \
print('consistency:', d['consistency_status']); \
print('artefacts:', len(d['new_artefacts']))" \
  <project>/_bmad/rdx-tea/runtime/<workflow>/<run_id>/run-report.json
```

## Sidecars — one per artefact

For every artefact the child wrote, the binder writes a sidecar next to it:

```
<artefact>.rdx-tea.json
```

The sidecar is the `rdx-tea-run.v1` binding record. Key fields:

| Field | Meaning |
|---|---|
| `artifact_path` / `artifact_sha256` | The bound artefact and its hash. |
| `run_id` / `workflow` | The run it belongs to. |
| `execution_mode` | Must be `sequential`. |
| `completed` | Must be `true` for an admissible run. |
| `base_sha` / `head_sha` / `diff_digest` | The identity the bundle was projected from. |
| `rdx_source_sha` / `tea_source_sha` | Source-lock identity. |
| `projection_hash` / `prepare_manifest_sha256` | Bundle + manifest hashes. |
| `active_packs` / `core_rules` / `rust_scope` | What the projection selected. |
| `prepared_at` / `bound_at` | Audit timestamps. |

There is exactly **one sidecar per artefact**. A missing sidecar, or a
sidecar count that does not equal the artefact count, makes the run
inadmissible.

## Verifier checks (behavioural integrity)

The verifier runs **9 checks** per sidecar and records each as
`{check, status, detail}`. `verdict` is `PASS` only when every check
passes; `failed_checks` lists any that did not.

| Check | What it proves |
|---|---|
| `schema` | The sidecar validates against `rdx-tea-run.v1`. |
| `manifest_hash` | The run-manifest on disk matches the recorded hash. |
| `bundle_hash` | `active-context.md` on disk matches the projection hash. |
| `artifact_hash` | The artefact on disk matches the bound hash. |
| `base_head_exist` | Both git commits exist. |
| `diff_digest_recomputed` | The diff digest recomputes from `diff.patch`. |
| `canonical_snapshot` | The KB canonical snapshot matches the pin. |
| `source_lock` | `sources.lock` identity is intact. |
| `artifact_boundary` | The artefact is in-project, not a symlink, inside declared output roots. |

The verifier is a **behavioural integrity check**, not an enforcement
verdict. (The enforcement-plane `rdx-tea-validate` command is deferred
backlog and is **not** part of D4 v1 — see the README's "Not included in
D4 v1" section.)

## Workspace delta & artifact consistency

`finalize-run` judges the run against **reality** — the real file delta and
the files actually on disk:

- **`workspace_delta`** — the set of new/changed files since the prepare
  snapshot. An empty delta is a fail-closed condition (nothing was
  written).
- **`workspace_delta_consistency`** — a declared-but-missing generated file
  fails; the delta must be internally consistent.
- **`artifact_consistency`** — a phantom file claim (an artefact claims a
  file that is not on disk) fails; duplicate frontmatter is a **warning
  only**, not a failure.

`consistency_status` is `PASS` only when both consistency checks pass.

## The admission block

`finalize-run` records an `admission` block that is **recomputed from the
report's own primitive fields** — it never trusts a self-declared flag. A
dishonest report that sets `admissible: true` while violating an invariant
is still reported as **not admissible**, with the violated reasons.

The block is `{admissible, run_outcome, reasons, workflow, run_id}`.
`run_outcome` is the first failing group in this fixed order (or
`SUCCESS`):

```
AUTH_FAILURE → RUNTIME_FAILURE → SCHEMA_FAILURE → MODE_FAILURE →
WORKFLOW_FAILURE → VERIFIER_FAILURE → CONSISTENCY_FAILURE → PARTIAL_RUN →
SUCCESS
```

A run is FINALIZED-admissible **only** when every group is clean.

### Recompute admissibility yourself

You can re-run the admission gate against any `run-report.json`:

```bash
python3 <project>/_bmad/rdx-tea/scripts/admission.py admit \
    --report <project>/_bmad/rdx-tea/runtime/<workflow>/<run_id>/run-report.json
```

Optionally cross-check the wrapper's run-state phase:

```bash
python3 <project>/_bmad/rdx-tea/scripts/admission.py admit \
    --report .../run-report.json \
    --state  .../run-state.json
```

The command prints the `{admissible, run_outcome, reasons, ...}` verdict and
exits `0` when admissible, `2` when not. Because it recomputes from
primitives, its verdict is authoritative regardless of anything the report
claims about itself.

## Where an inadmissible run points you

If `admission.admissible` is `false`, the `run_outcome` tells you which
guide section to read:

| `run_outcome` | See |
|---|---|
| `MODE_FAILURE` | [TROUBLESHOOTING.md](TROUBLESHOOTING.md#tea-mode-is-not-sequential) |
| `WORKFLOW_FAILURE` (empty delta / no sidecar / subagent observed) | [TROUBLESHOOTING.md](TROUBLESHOOTING.md#the-delta-is-empty) |
| `VERIFIER_FAILURE` | [TROUBLESHOOTING.md](TROUBLESHOOTING.md#a-verifier-check-failed) |
| `CONSISTENCY_FAILURE` | [TROUBLESHOOTING.md](TROUBLESHOOTING.md#consistency-failed) |
| `PARTIAL_RUN` | [TROUBLESHOOTING.md](TROUBLESHOOTING.md#admission-says-not-admissible) |
