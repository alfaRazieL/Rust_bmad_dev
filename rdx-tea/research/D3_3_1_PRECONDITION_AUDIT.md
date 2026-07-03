# D3.3.1 — Precondition audit before pilot

Independent re-verification of D3.3 claims and stop-condition gaps.
Nothing in this file trusts the prior gate status merely because the
prior report recorded PASS. Every gap below is grounded in code and
committed evidence, and is closed (or documented as still-open) in the
D3.3.1 stabilization work that follows.

## §1 Repository state at start

- Branch: `rdx-tea-integration`
- START_HEAD: `3d3d5f888a778904cb8a6ba87377da1e598682f2` (matches handoff)
- `origin/main`: `d8140a25f8166bf0ca5ce5fc19f7cb1bd06a3d6d`
- Last CI-tested subject: `06092b67fd53a187926bbbe913cb8205ec6385c5`
- Last confirmed GitHub Actions run: `28636630783`

Working tree at start was clean apart from a project-local `.agents/`
scratch directory unrelated to `rdx-tea/`.

## §2 Verified gaps in D3.3 (all confirmed by grepping the actual repo)

### §2.1 Missing orchestrator

The `rdx-tea/live-harness/README.md` layout section advertises:

    live-harness/
    ├── run_live.py                  # orchestrator …
    ├── schemas/
    │   └── live-evidence.v1.schema.json
    └── tests/
        └── test_harness_unit.py

At `START_HEAD` these three files did NOT exist:

    $ ls rdx-tea/live-harness/schemas rdx-tea/live-harness/tests
    (both empty)
    $ ls rdx-tea/live-harness/run_live.py
    ls: rdx-tea/live-harness/run_live.py: No such file or directory

Consequence: reviewers cannot run a single canonical command to
reproduce a live smoke; there is no schema pinning what a
"complete" evidence bundle contains; no unit-test surface guards
the harness against regressions. This is a D3.3.1 STOP condition.

### §2.2 `observed_mode = INFERRED_ABSENT` in every smoke

All three smoke bundles under `rdx-tea/evidence/live/` end with
`observed_mode: "INFERRED_ABSENT"` in `run-report.json`. Root cause
inspected in `rdx_tea_wrapper.py::_infer_observed_mode` and
`invoke_runtime.py::_stream_transcript`:

- `invoke_runtime.py` writes the stream JSONL AFTER `claude -p`
  exits — so during `finalize_run` inside the same session the
  transcript file is empty or absent.
- `finalize_run` accepts only `phase == "prepared"`; running it a
  second time in a `--verify-only` mode still transitions state
  and re-runs binder on `_delta_outputs`, which is not idempotent.

Fix implemented in D3.3.1 as a separate `reconcile-transcript`
operation (§3.2 below) that never rebinds and never mutates
sidecars.

### §2.3 Nested-roots duplication

`prepare.py::_output_dirs` returns both `_bmad-output` and
`_bmad-output/test-artifacts`. Because `_bmad-output` is the parent,
every file under `test-artifacts` was scanned twice. The committed
smoke `run-report.json` files contain identical duplicated entries
under `new_artefacts`, sidecars and verifier results. Regression
guarded by `test_harness_unit.py::test_walk_artefacts_no_duplicates`.

### §2.4 ATDD smoke did NOT activate the API pack

Programmatic re-verification with the vendored router:

    $ python3 -c "…replay(diff, rules, ['api','async'])…"
    OLD fixture: active packs: ['async']

Why:

- `api` pack policy is `STORY_TAG_REQUIRED`; canonical
  `story_tags = ["publish=true", "library-crate", "stable-cli-contract"]`.
- The bare tag `api` matches `pack_name in story_tag_set`, but the
  router still requires at least one matching positive signal or
  path signal.
- The old fixture's diff `pub async fn create_user` in `src/api.rs`
  contains none of api's positive_signals (`pub fn`, `pub struct`,
  `pub enum`, `pub trait`, `pub use`, `pub mod`, `#[deprecated`)
  and none of its path_signals (`**/lib.rs`, `**/src/lib.rs`).

Fix: `fixtures/atdd-api-async-corrected/` with `publish=true` +
`async` tags and a diff on `src/lib.rs` exposing `pub struct User`
and `pub async fn create_user`. Re-verification with router.replay
now returns `['api', 'async']` deterministically, guarded by
`test_corrected_atdd_activates_api_pack`. Old fixture retained with
label `ATDD_ASYNC_ONLY_PREVIOUS_EVIDENCE`.

### §2.5 Cleanup not crash-safe

`rdx_tea_wrapper.finalize_run` restores the overlay and releases
the lock only on the success path — the last two lines before
`return report`. Any prior exception (`no new artefact`, verifier
raise, binder raise, KeyboardInterrupt, timeout) leaves:

- `_bmad/rdx-tea/runtime/active-run.lock` populated;
- `_bmad/custom/bmad-testarch-<workflow>.toml` still holding the
  run-scoped overlay;
- run state stuck in `phase = "prepared"`.

Fix: `run_live.abort_run` is idempotent, foreign-lock/overlay-safe,
and always emits an `aborted.json` marker under the run directory.
Guarded by the abort tests in `test_harness_unit.py`.

### §2.6 Evidence identity contained PENDING

`rdx-tea/evidence/final/D3_3_FINAL_VERIFICATION.json`:

    "evidence_commit_sha": "PENDING (this file's next commit)"

This is unacceptable — every evidence file should be self-verifying
against a code commit. Fix: D3.3.1 emits a new
`D3_3_1_FINAL_VERIFICATION.json` written in a follow-up evidence
commit that references the D3.3.1 code commit as
`tested_subject_sha` and its own commit SHA as `evidence_commit_sha`
(two-commit identity).

### §2.7 Live evidence bundles incomplete

`collect_evidence.collect` writes `runtime.json`, `invocation.json`,
`workspace-manifest.json`, and `exit-code.txt`, but the fields
required by the pilot rubric (session_id, model_id, config_dir_hash,
transcript_sha, wrapper/child skill invoked, task_tool_use_count)
were not stored anywhere. Fix: `run_live.py` emits
`live-evidence.v1.json` validated by the new JSON schema, containing
every required field.

### §2.8 Pilot rubric methodologically wrong

- `D3_3_PILOT_RUBRIC.yaml` scored baseline against RP-* IDs that
  baseline has no visibility of. Docs-only had `expected_rp_ids_min = []`
  causing a division-by-zero risk. ATDD expected only `[async]`,
  which entrenches the §2.4 error.

Fix: `D3_4_PILOT_RUBRIC.yaml` (v2) splits metrics into two families
(candidate-only fidelity vs identical comparative quality), removes
the docs-only recall metric, and inserts a blinded LLM grader
alongside the deterministic detectors.

### §2.9 Runtime environment contamination risk

D3.3 transcripts inherited the user's `~/.claude` config: personal
MCP servers, personal skills, personal memory. That is unusable for
a comparative pilot: baseline and candidate must see identical
minimal environments. Fix: `run_live.ClaudeIsolation` builds a
per-run `CLAUDE_CONFIG_DIR`, seeds only project skills, and disables
MCP. `config_dir_hash` is recorded in the evidence bundle so the
grader can prove baseline and candidate used byte-identical
environments.

## §3 Gates (start state → after this cycle's plan)

| Gate | D3.3 recorded | D3.3.1 verified today | Post-D3.3.1 target |
|---|---|---|---|
| G5  | PASS          | PARTIAL (nested-roots + observed_mode) | PASS after harness stabilization |
| G6  | PASS          | PARTIAL (INFERRED_ABSENT in every smoke) | PASS after reconciliation returns OBSERVED_SEQUENTIAL |
| G7  | NOT_RUN       | NOT_RUN                                 | NOT_RUN — still awaits blinded pilot |
| G13 | PASS          | PARTIAL (evidence identity has PENDING) | PASS after two-commit identity |
| G14 | PASS          | PARTIAL (ATDD API pack not activated)  | PASS only after corrected ATDD smoke succeeds |
| G21 | PASS          | PARTIAL (CI does not upload artifacts) | PASS after CI hardening |
| G24 | NOT_RUN       | NOT_RUN                                 | NOT_RUN in this window |

The re-recording appears in
`evidence/final/D3_3_1_FINAL_VERIFICATION.json`.

## §4 Stop conditions still open at time of writing

- Corrected ATDD smoke (§2.4 fix) is deterministic-only in this
  window. A model-driven re-run inside an isolated Claude Code
  environment is required before D3.4 can start. See
  `D3_3_1_BLOCKERS.md` §1.
- Grader implementation for the layer-2 semantic pass is defined by
  rubric YAML but the runner script is not yet written.
- Live-model runs are not executed in this window per §5 of the
  handoff (mass N≥10/N≥20 forbidden; and pilot admissibility gate
  requires the closed stop conditions above).

## §5 What this audit does NOT claim

- It does NOT claim `OBSERVED_SEQUENTIAL` for the three legacy D3.3
  smokes. The transcripts contain zero Task events (verified from
  the committed `transcript.stream.jsonl` SHAs) but were classified
  by the wrapper as `INFERRED_ABSENT` because the transcript wasn't
  materialised when `finalize_run` read it. The new
  `reconcile-transcript` operation reclassifies THOSE transcripts as
  well when it is applied post-hoc, but the historical records under
  `evidence/live/` are left unchanged in this cycle to preserve the
  original evidence.
- It does NOT claim `D3_3_1_PASS`. That verdict is only issued once
  every §7 acceptance clause in the handoff holds — including the
  corrected ATDD smoke and the CI evidence identity.
