# D3.1_PRODUCTION_LAYOUT_AUDIT

**Status:** the stage that closes the ten gaps between D3 (see
`D3_VARIANT_VERIFICATION_REPORT.md`) and a production-ready integration
seam. Every gap in the D3.1 prompt is addressed below with the exact
fix location and the runtime test that closes it.

## 0. Provenance

- Branch: `rdx-tea-integration`
- Prior HEAD (D3 verdict): `4f7e498314bb90f1b6291303593a8646da525d66`
- Upstream lock (unchanged): BMAD-METHOD v6.8.0 (`3bcd6c3c…`),
  BMAD TEA v1.19.0 (`8734d51f…`)
  (see `D3_SOURCE_LOCK_ADDENDUM.md` and `bootstrap/sources.lock`).

## 1. Overlay command didn't pass story / diff / tags (D3.1 prompt §1)

**Fix:** `rdx-tea/poc/install-tree/_bmad/rdx-tea/scripts/rdx_tea_wrapper.py`
resolves `_bmad-run/story.md`, `_bmad-run/diff.patch`, and
`_bmad-run/tags.txt` before calling `prepare.prepare()`. When the story
comes from git instead of a file, the wrapper falls back to
`git rev-parse HEAD` + `merge-base HEAD origin/main` + `git diff`. The
overlay TOML no longer embeds a partial CLI — it delegates to the
wrapper entrypoint.

**Test:** `test_l4_d31_e01_wrapper_runs_end_to_end_in_external_project`
runs the wrapper with real story/diff and asserts non-empty
`active_packs`.

## 2. `on_complete` binder didn't receive an artefact path (D3.1 prompt §2)

**Fix:** the wrapper-owned pattern (mirrors `rdx-dev-story`) removes
the placeholder problem entirely. After the child skill runs, the
wrapper discovers every real output by parsing the skill's
`workflow.yaml:outputs[].path` and applying its own substitution table.
It then invokes `binder.py` once per resolved output. The overlay's
`on_complete` field becomes a thin invocation of the wrapper's
post-child step.

**Test:** `test_l4_d31_e01` verifies the sidecar exists after the
wrapper runs. `_discover_outputs` in `rdx_tea_wrapper.py` is the
mechanism.

## 3. Sequential mode was recorded but not requested / verified (D3.1 prompt §3)

**Fix:** `rdx_tea_wrapper._verify_resolved_mode()` reads
`_bmad/tea/config.yaml:tea_execution_mode` and refuses to proceed
unless it resolves to `sequential` (or `auto` — which upstream
degrades to sequential when no subagent runtime is available).
Manifest AND sidecar record `execution_mode = "sequential"` AND
`requested_mode = "sequential"`.

**Test:** `test_l4_d31_e06_wrapper_verifies_sequential_mode` — flip
config to `subagent` and observe wrapper failing closed.

## 4. PoC depended on dev-repository paths (D3.1 prompt §4)

**Fix:** Production install layout
`rdx-tea/poc/install-tree/_bmad/rdx-tea/`:

```
_bmad/rdx-tea/
├── canonical/
│   ├── router-rules.json
│   ├── status-definitions.json
│   ├── rule-check-map.json
│   ├── authority-matrix.json
│   └── kb-sections/section-{4,5,6,8}-*.md
├── scripts/
│   ├── prepare.py
│   ├── binder.py
│   ├── rdx_tea_wrapper.py
│   ├── rdx_tea_validator.py
│   ├── rdx_parser.py
│   ├── obligation_matrix.py
│   ├── router.py     (vendored from RDX v1.1 rdx_validator/router.py)
│   └── diff.py       (vendored dependency of router.py)
├── bootstrap/
│   ├── bootstrap.py
│   └── sources.lock
└── VERSION
```

`rdx_parser._locate_canonical_root()` resolves the canonical payload in
this order: `$RDX_TEA_CANONICAL_ROOT` env → `<scripts>/canonical/` →
`<scripts>/../canonical/` → dev-tree fallback (only when the RDX repo
is on the walked path — the production install never hits it).

**Test:** `test_l4_d31_e05_no_rdx_dev_tree_paths_referenced` scans
every `.py/.sh/.toml/.yaml` file under the installed
`_bmad/rdx-tea/scripts/` and asserts the RDX repo absolute path is
never embedded. `test_l4_d31_e01` runs the wrapper in `/tmp` from a
project that never sees the RDX dev tree (PYTHONPATH cleared, no
env var pointing at the repo).

## 5. Obligation matrix wasn't enforced at rule-field level; CORE-* missing (D3.1 prompt §5)

**Fix:** `obligation_matrix.py` moves the matrix from documentation
into code with three axes per workflow:

- `packs`: set of pack_id (as before)
- `core_rules`: `True` / set of CORE-XXX / `None`
- `fields`: set of IR field names emitted in the bundle

`prepare._select_active_rules()` includes CORE-* rules under the
workflow's policy — but ONLY when at least one pack activates (so a
non-Rust story yields an empty bundle, not a stray Core dump).
`prepare._render_bundle()` filters every rule's emitted fields against
`fields_allowed(workflow)`. `WORKFLOW_OBLIGATION_MATRIX.csv` gains 8
new rows documenting the CORE inclusion policy per workflow.

**Tests:**
- The end-to-end smoke shows `test-design` bundles all 18 CORE-* rules.
- `test_l2_d09_workflow_obligation_matrix_applied` still verifies
  scope filtering (trace excludes unsafe).
- The manifest carries `workflow_obligation_matrix.core_rules_policy`
  and the emitted `core_rules[]` list.

## 6. Router parity had `or True` escape (D3.1 prompt §6)

**Fix:** `test_l2_d10_story_tag_required_pack_gated_on_tag` now
asserts BOTH branches:
- without the tag → `api` NOT in `active_packs`
- with the tag → `api` MUST be in `active_packs`

Same file: `test_l2_d07_router_parity_with_rdx_validator` now requires
EXACT SET EQUALITY between `(Router ∩ obligation-matrix)` and the
packs emitted by prepare — no subset slack.

## 7. Binder / validator did not fail-closed on hash disagreement (D3.1 prompt §7)

**Fix:** `binder.bind()` recomputes `sha256(active-context.md)` and
raises `BinderError` if it disagrees with `manifest.bundle_sha256`.
The new `rdx_tea_validator.validate()` recomputes
`sha256(artifact)` and raises `ValidatorError` if it disagrees with
`sidecar.artifact_sha256`. Sidecar identity fields are checked for
presence too — missing → validator refuses.

**Tests:**
- `test_l4_d31_e03_binder_fails_closed_when_bundle_tampered` — tamper
  the bundle, invoke binder via CLI, assert non-zero exit and the
  word "tamper" in stderr.
- `test_l4_e02_sidecar_invalidated_on_artifact_mutation` (D3 era) still
  verifies artefact-tamper detection.

## 8. Identity fields were optional / environment-only (D3.1 prompt §8)

**Fix:** `prepare.prepare()` requires an `identity` dict with
mandatory `base_sha`, `head_sha`, `rdx_source_sha`, `tea_source_sha`.
`diff_digest` is COMPUTED by prepare (SHA-256 of the read diff) and
stamped back — if the caller supplied a mismatched digest, prepare
refuses. CLI `prepare.py` accepts these as required flags. Wrapper
loads `bootstrap/sources.lock` for RDX/TEA SHAs and resolves base/head
via git. Sidecar schema `rdx-tea-run.v1.schema.json` promotes ALL
identity fields to `required`, with `base_sha`/`head_sha` regex
tightened to 40-hex.

**Test:**
- `test_l4_d31_e04_prepare_fails_closed_without_identity` — invoke
  prepare CLI omitting the SHAs, assert non-zero exit.
- `test_l4_d31_e02_sidecar_schema_valid_from_external_project` —
  JSON-schema-validate every sidecar the wrapper produces.
- The manifest smoke output records the identity block verbatim.

## 9. D3_FINAL_VERIFICATION.json referenced a stale HEAD (D3.1 prompt §9)

**Fix:** the file is rewritten below to reference the actual HEAD
after the D3.1 series lands. New gate G12 (production-layout closure)
added. See `D3_FINAL_VERIFICATION.json`.

## 10. Reproducible bootstrap + branch-only CI (D3.1 prompt §10)

**Fix:**
- `bootstrap/sources.lock` (YAML) records the exact tags and SHAs of
  BMAD-METHOD v6.8.0 and TEA v1.19.0.
- `bootstrap/bootstrap.py` clones/updates each upstream at the pinned
  tag and refuses on SHA mismatch.
- New CI workflow `.github/workflows/rdx-tea-integration-check.yml`
  runs `pytest rdx-tea/tests/` on pushes and PRs targeting ONLY
  `rdx-tea-integration`. It is skipped on any push targeting `main`
  and explicitly declines `pull_request` events opened against `main`
  (fail-closed guard).

**Tests:**
- `test_l4_d31_e07_bootstrap_verifies_upstream_tags` — invoke
  `bootstrap.py` against a pre-checked-out copy and assert the
  returned SHAs match the lock.

## Summary of new evidence

| Test file | New tests | Purpose |
|---|---:|---|
| `tests/bmad-tea/test_l4_d31_external_project_slice.py` | 7 | End-to-end in fresh external tmp project |
| `tests/integration/test_l2_dynamic_active_bundle.py` (updated) | 13 | Bundle behaviour, exact parity, identity mandatory |
| `tests/bmad-tea/test_l4_sequential_vertical_slice.py` (updated) | 6 | Old D3 slice re-based on install-tree |

Full suite after D3.1: 404/404 in ~18 s. Baseline 307/0/0 unchanged.

## What D3.1 does NOT close

- G7 behavioural benefit — still `NOT_RUN`. Requires real LLM runs.
- G8 full — `rdx-tea-validate` inside `rdx-validator/rdx_tea/` still
  deferred. The install-tree ships a self-contained validator stub;
  the RDX-side subcommand comes with the enforcement plane.
- G9/G10 (modes, hook, CI trust boundary) still `BLOCKED` behind G7.

D3.1 is the last integration-plane closure before the LLM-driven
proofs. The knowledge plane is now honest PASS at production layout.
