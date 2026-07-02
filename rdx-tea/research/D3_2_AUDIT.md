# D3.2_AUDIT — Live invocation closure (deterministic side)

**Prior HEAD (D3.1 verdict):** `0e3a3ab4553c6cff9c5b093723764d414e9388d1`.  
**Governing prompt:** D3.2 LIVE INVOCATION CLOSURE (13 concrete gaps).  
**Live 3-smoke status:** `NOT_RUN` — see `D3_2_NOT_RUN.md` for the exact
runtime blocker.

Every D3.2 prompt gap is closed by a specific artefact plus a runtime
test. Table below is the single-source status; details follow.

| # | Gap | Fix location | Runtime test |
|---|---|---|---|
| 1 | Overlay didn't pass story/diff/tags → empty bundle | `rdx_tea_wrapper.py::prepare_run` reads `_bmad-run/*` + `git diff base..head` | `test_l4_d31_e01_two_phase_wrapper_end_to_end` |
| 2 | `on_complete` binder lacked artefact path | Wrapper-owned finalize-run discovers outputs and binds each; overlay no longer relies on `on_complete` placeholder | Same E01 + `finalize-run` writes a real report |
| 3 | Sequential mode only recorded, not enforced | `_assert_sequential_mode` rejects `auto`, `subagent`, `agent-team` | `test_l4_d31_e06_wrapper_rejects_non_sequential` |
| 4 | PoC depended on dev-repo paths | `install-tree/canonical/` bundles schema; `_locate_canonical_root` resolves script-adjacent path | `test_l4_d31_e05_no_rdx_dev_tree_paths_referenced` |
| 5 | Obligation matrix not enforced at field level; CORE missing | `obligation_matrix.py` axes packs/core_rules/fields; prepare filters fields per workflow; CORE-* per workflow when rust_scope | `test_l1_matrix_coverage_of_all_parsed_rules` (138×8=1104 cells) |
| 6 | `or True` in tag test; parity was subset | Replaced with exact set equality + BOTH story-tag arms | `test_l2_d07_router_parity`, `test_l2_d10_story_tag_required_pack_gated_on_tag` |
| 7 | Binder didn't verify bundle hash | `binder.bind()` recomputes bundle sha; verifier recomputes both bundle+artefact hashes | `test_l4_d31_e03_verifier_fails_on_bundle_tamper` |
| 8 | Zero-SHA fallbacks + optional identity | `_validate_sha` rejects `0*40`; `_resolve_identity` uses `git cat-file -e`; prepare/binder/wrapper require identity | `test_l4_d31_e04_prepare_fails_closed_without_identity` |
| 9 | `D3_FINAL_VERIFICATION.json` referenced stale HEAD | Verdict addendum records D3.1 start head + adds `tested_subject_sha`, `evidence_commit_sha`, `github_actions_run_id` fields | Machine-readable in `D3_FINAL_VERIFICATION.json` |
| 10 | Bootstrap lacked clean-worktree + file hashes; CI lacked repro upstream | `bootstrap._assert_clean_worktree` + `_assert_expected_hashes`; CI runs `bootstrap.py` and fails on skipped upstream tests | `test_l4_d31_e07_bootstrap_verifies_upstream_tags` |
| 11 | Bootstrap needed clean worktree verification + expected file hashes | Same as (10) | Same |
| 12 | CI used `.venv-baseline`; needed `sys.executable` | Workflow uses actions/setup-python + plain `python -m pytest` — no venv path hardcode | `.github/workflows/rdx-tea-integration-check.yml` |
| 13 | Verification identity missing three fields | Added `tested_subject_sha`, `evidence_commit_sha`, `github_actions_run_id` | `D3_FINAL_VERIFICATION.json` gates.G12/G13 |

## 1. Two-phase wrapper

`rdx_tea_wrapper.py` now has two subcommands:

- `prepare-run --workflow W --project-root P --run-id R
              --base-sha X --head-sha Y --skill-dir SKILL
              [--allow-fixture-diff PATH]`

- `finalize-run --workflow W --project-root P --run-id R
                [--verify-only] [--test-write-fake-artefact]`

State flows through
`{project-root}/_bmad/rdx-tea/runtime/<workflow>/<run_id>/run-state.json`.
`--test-write-fake-artefact` is gated by `RDX_TEA_ALLOW_TEST_ARTEFACT=1`
and is not accepted in production. `--allow-fixture-diff` is gated by
`RDX_TEA_ALLOW_FIXTURE_DIFF=1`.

## 2. Real BMAD Skill wrappers

`rdx-tea/poc/install-tree/.claude/skills/rdx-tea-test-design/SKILL.md`
and `.../rdx-tea-atdd/SKILL.md` mirror the `rdx-dev-story` pattern with
seven activation steps: resolve inputs → strict identity → sequential
guard → prepare-run → invoke the ORIGINAL `bmad-testarch-*` child skill →
finalize-run → report. Neither skill simulates the child.

## 3. Sequential-only enforcement

`wrapper._assert_sequential_mode()` accepts ONLY the literal string
`sequential`. `auto`, `subagent`, `agent-team`, `""` and anything else
raises `WrapperError`. Verified end-to-end by
`test_l4_d31_e06_wrapper_rejects_non_sequential`.

## 4. Strict git identity

`_resolve_identity` returns SHAs only after `git cat-file -e` confirms
each exists as a git object. `_validate_sha` refuses `0*40` and non-hex
values. `prepare.prepare()` re-validates on entry — even in-process
callers cannot skip.

## 5. Real diff generation

`prepare-run` uses `git diff base..head` in production. Fixture diffs
are permitted only when `RDX_TEA_ALLOW_FIXTURE_DIFF=1` is set — tests
opt in explicitly.

## 6. Run-scoped layout

`_bmad/rdx-tea/runtime/<workflow>/<run_id>/` holds the bundle, manifest,
state file, diff copy, run-report, and every artefact sidecar of a
single wrapper invocation. Two runs with different ids never touch
each other (`test_l4_d31_e08_run_scoped_layout_isolates_runs`).

## 7. Output snapshot + delta

`prepare-run` captures a pre-snapshot of every file under the workflow's
declared output dirs; `finalize-run` computes the delta (new or
sha-changed files) and refuses if the delta is empty ("child skill
either never ran or wrote nothing"). Symlink artefacts are refused.

## 8. Rust scope

`prepare._detect_rust_scope()` returns `True` when `Cargo.toml`,
`rust-toolchain[.toml]`, or any `.rs` file exists under project-root.
`rust_scope=False` yields an empty bundle regardless of packs.
`rust_scope=True` + no active pack still produces the workflow's CORE
subset.

## 9. Single-source obligation matrix

`obligation_matrix.py` is the source. `generate_csv()` regenerates
`WORKFLOW_OBLIGATION_MATRIX.csv` from Python. `coverage_for()` reports
per (workflow, rule_id) decision. `test_l1_matrix_coverage_of_all_parsed_rules`
asserts all 138 rules × 8 workflows = 1104 cells are covered.

## 10. Behavioural verifier

`rdx_tea_validator.verify()` reports pass/fail per check across 9
integrity dimensions: schema, manifest_hash, bundle_hash, artifact_hash,
base_head_exist, diff_digest_recomputed, canonical_snapshot,
source_lock, artifact_boundary. Result carries every check for later
behavioural eval comparison. Failure → sidecar rejected. Cat-1 verdict
still not written by any adapter component.

## 11. Bootstrap hardening

`bootstrap.py` refuses to proceed if either upstream clone has a dirty
worktree (unless `RDX_TEA_BOOTSTRAP_SKIP_WORKTREE_CHECK=1` — production
never sets this). It also verifies four load-bearing upstream file
hashes against `sources.lock:expected_file_hashes`.

## 12. CI hardening

`.github/workflows/rdx-tea-integration-check.yml`:

- Refuse-on-main guard.
- No PR against main.
- `actions/setup-python@v5` + `python -m pytest` (no hardcoded venv).
- Runs `bootstrap.py` before the tests so subsequent upstream-touching
  tests do not skip.
- `verify-no-skip-in-upstream-tests` step exits 6 if any test in
  `rdx-tea/tests/bmad-tea/` reports SKIPPED (bootstrap failed silently).
- `no-main-modifications` job asserts every changed path since
  merge-base with main is under `rdx-tea/` or
  `.github/workflows/rdx-tea-*.yml`.

## 13. Verification identity

`D3_FINAL_VERIFICATION.json` now records:

- `tested_subject_sha` — the `rdx-tea-integration` HEAD the tests ran against
- `evidence_commit_sha` — the commit that contained this verdict file
- `github_actions_run_id` — filled in by CI when the workflow completes
  (recorded as `PENDING` until the GH Actions push run reports back)
