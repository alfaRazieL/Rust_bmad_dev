# D3.3.1 Stabilization Report

Scope: harness stabilization prior to the D3.4 blinded pilot. This
report documents the deliverables that landed in this cycle, what
they prove, and what still requires live-model execution before a
`D3_3_1_PASS` verdict is justified.

Unlike D3.3, this cycle does not claim to have executed new
model-driven live runs. The corrected ATDD smoke and the 18-run
pilot both require a headless Claude Code CLI session that is out of
scope for a Python-only implementation window per the handoff §5
constraint on mass evals. All deliverables below are code and text
that a live-runtime follow-up will consume.

## 1. Unified `run_live.py` orchestrator

Location: `rdx-tea/live-harness/run_live.py`.

Subcommands:

- `run-smoke` / `run-one` — runtime discovery → prepare → invoke →
  reconcile → collect → schema-validate;
- `reconcile-transcript` — idempotent post-runtime observation;
- `abort-run` — crash-safe cleanup with foreign lock/overlay
  preservation.

The orchestrator NEVER re-runs `finalize_run --verify-only` as its
reconciliation. `finalize_run` is not idempotent (it accepts only
`phase == "prepared"` and its binder loop mutates sidecars);
`reconcile-transcript` is a separate operation that only writes the
`observed_mode` / `wrapper_skill_invoked` / `child_skill_invoked` /
`task_tool_use_count` / `transcript_sha256` / `session_id` fields
into `run-report.json` atomically. See
`test_reconcile_transcript_updates_report_atomically` for the
regression guard.

## 2. Output deduplication

`_canonicalize_output_roots` collapses `_bmad-output/test-artifacts`
into `_bmad-output` when both are supplied (`test-artifacts` is a
descendant). `_walk_artefacts` deduplicates by resolved path. The
`new_artefacts` and `sidecars` arrays in the emitted
`live-evidence.v1.json` therefore have `uniqueItems: true` in the
schema and cannot double-list.

## 3. Crash-safe lifecycle

`abort_run` is idempotent and rejects foreign locks (`lock_owned_by`
check) and foreign overlays (missing rdx-tea marker). It writes an
`aborted.json` marker under the run dir; repeated calls append
`aborted.<n>.json` so history is preserved. `run_smoke` wraps
`_prepare` / `_invoke` / `_finalize_evidence` in `try/except` and
routes `KeyboardInterrupt` / `TimeoutExpired` / arbitrary exceptions
through `abort_run` before re-raising.

## 4. Corrected ATDD fixture

`rdx-tea/live-harness/fixtures/atdd-api-async-corrected/` uses:

- story tags `publish=true`, `async` (canonical STORY_TAG_REQUIRED
  values for the api pack);
- `src/lib.rs` with `pub struct User`, `pub enum ApiError`,
  `pub async fn create_user` (matches both api's path signal
  `**/lib.rs` and its positive signal `pub struct`).

Router replay confirms `active_packs == [api, async]`. Regression
guarded by `test_corrected_atdd_activates_api_pack` and by the
negative-guard `test_old_atdd_fixture_does_not_activate_api_pack`
so the old fixture is not silently re-used.

The old fixture is retained under `atdd-api-async/`; the historical
evidence bundle is annotated with
`rdx-tea/evidence/live/smoke-atdd/ATDD_ASYNC_ONLY_PREVIOUS_EVIDENCE.md`.

## 5. Runtime isolation

`ClaudeIsolation`:

- creates a per-run temporary `CLAUDE_CONFIG_DIR`;
- seeds it with `mcp.json` containing `{"mcpServers": {}}`;
- seeds it with an empty `CLAUDE.md` (no user memory leakage);
- copies only the project's `rdx-tea-<workflow>` skill directory in;
- computes `config_dir_hash = sha256(sorted-tree)` and records it in
  the evidence bundle so baseline and candidate arms can prove they
  used byte-identical environments.

`invoke_runtime.invoke` is called inside a `finally`-guarded env swap
so `CLAUDE_CONFIG_DIR` cannot leak into the next scenario.

## 6. Evidence schema

`rdx-tea/live-harness/schemas/live-evidence.v1.schema.json`
(Draft-2020-12) requires:

- scenario / arm / repetition / run_id / workspace identity;
- base and head SHA (40 hex);
- runtime block: version, model_id, permission_mode, available_tools,
  available_skills, mcp_servers, timeout, budget;
- invocation block: command_hash, timestamps, exit_code, reason enum;
- hashes: run_report, transcript, bundle (each 64 hex);
- observation block: requested / configured / observed modes plus
  their surrogate basis, wrapper / child invocation booleans,
  task_tool_use_count, transcript_sha256, session_id;
- cleanup block: state ∈ {FINALIZED, ABORTED, FAILED},
  lock_released, overlay_restored.

Every emitted bundle validates before the run is considered
successful. If validation fails the errors are dumped alongside the
bundle and the orchestrator raises.

## 7. Harness unit tests

`rdx-tea/live-harness/tests/test_harness_unit.py` — 19 tests, all
green under `pytest 9.1.1` in the project venv. Coverage:

- transcript classifier (missing, invalid, sequential, subagent);
- reconciliation idempotence and no-rebind;
- output canonicalisation and dedup regression;
- abort-run: idempotence, owned lock release, foreign lock preserved,
  backup restore, foreign overlay preserved;
- corrected ATDD fixture activation of `api` and `async`;
- old fixture regression: still only `async`;
- schema validity (draft-2020-12);
- schema rejects incomplete bundles;
- schema accepts a minimal valid bundle;
- pilot schedule precommitted (18 runs, locked, correct scenarios).

## 8. Pilot rubric v2

`rdx-tea/evals/D3_4_PILOT_RUBRIC.yaml` (schema_version
`rdx-tea-pilot-rubric.v2`) supersedes `D3_3_PILOT_RUBRIC.yaml` and
splits scoring:

- `candidate_integration_fidelity` — candidate-only. Boolean gates
  on active packs, expected RP-* IDs, invented ID rate, forbidden
  pack absence, verifier PASS, exact bundle hash, and
  `observed_mode == OBSERVED_SEQUENTIAL`.
- `comparative_artifact_quality` — identical scoring on baseline and
  candidate. Layer 1 deterministic detectors (cancellation, timeout,
  shutdown, partial progress, cleanup ownership, task lifecycle,
  API boundary/error, negative paths, executable detail, contradictions,
  hallucinated facts). Layer 2 blinded LLM grader. Layer 3 efficiency
  counters.
- `docs_only_control` — no denominator. Assert
  `rdx_leakage_count == 0` and `irrelevant_rust_requirement_count == 0`
  for BOTH arms.
- `evaluator_isolation` — mandatory sanitisation (filenames,
  frontmatter, RP-* IDs, wrapper names, sidecars, path prefixes);
  separate `candidate_integration_grader` that sees full evidence.

## 9. Precommitted pilot schedule

`rdx-tea/evals/runs/D3_4_PILOT_RUNS.json` (locked=true, seed=20260703).

- 3 scenarios × 2 arms × 3 repetitions = 18 runs;
- randomised order using `hashlib`-friendly `random.seed(20260703)`;
- each run captures scenario, arm, repetition, model
  (`claude-haiku-4-5-20251001`), timeout, budget, and fixture_hash;
- `grader_version = rdx-tea-grader.v1`; grader prompt hash pinned;
- schedule SHA256 committed:
  `9fb991a33b71d448eb2cbc15fb19914f2f3776f16be2055855df1c87795d7f08`.

Regression test asserts locked==true and the 18-cell coverage.

## 10. Evidence identity and CI hardening

`.github/workflows/rdx-tea-integration-check.yml` now:

- runs one canonical deterministic suite emitting JUnit XML per
  section (baseline, adapter, live-harness);
- refuses mandatory skips (`--collect-only | grep SKIPPED`);
- writes a source-lock report from `bootstrap.py --verify-only`;
- writes a SHA256 manifest of every CI artifact;
- records `run-metadata.json` with the tested subject SHA and GH
  Actions run URL;
- uploads every CI artifact via `actions/upload-artifact@v4` with a
  30-day retention.

`evidence/final/D3_3_1_FINAL_VERIFICATION.json` uses a two-commit
identity design: the code commit sets `tested_subject_sha`; a
follow-up evidence commit rewrites `tested_subject_sha`,
`evidence_commit_sha`, `github_actions_run_id`, `_url`, `_conclusion`,
and `test_count_pytest` once CI returns.

## 11. What is NOT yet proven in this cycle

- No new live model-driven smoke is executed here — the corrected
  ATDD smoke and the 18-run pilot are code-and-plan only.
- `evidence/final/D3_3_1_FINAL_VERIFICATION.json` legitimately still
  contains `PENDING` for CI-derived fields. Those are closed by the
  evidence commit after CI runs, not by any judgment.
- Verdict is therefore `D3_3_1_PARTIAL`. The pilot MUST NOT start
  until the corrected ATDD smoke and the CI closure land.

## 12. Files added/modified

Added:

- `rdx-tea/live-harness/run_live.py`
- `rdx-tea/live-harness/schemas/live-evidence.v1.schema.json`
- `rdx-tea/live-harness/tests/__init__.py`
- `rdx-tea/live-harness/tests/test_harness_unit.py`
- `rdx-tea/live-harness/fixtures/atdd-api-async-corrected/`
  (story.md, tags.txt, Cargo.toml, diff.patch)
- `rdx-tea/evidence/live/smoke-atdd/ATDD_ASYNC_ONLY_PREVIOUS_EVIDENCE.md`
- `rdx-tea/evals/D3_4_PILOT_RUBRIC.yaml`
- `rdx-tea/evals/runs/D3_4_PILOT_RUNS.json`
- `rdx-tea/architecture/ADR-004-PILOT-HARNESS.md`
- `rdx-tea/evidence/final/D3_3_1_FINAL_VERIFICATION.json`
- `rdx-tea/research/D3_3_1_PRECONDITION_AUDIT.md`
- `rdx-tea/research/D3_3_1_STABILIZATION_REPORT.md` (this file)
- `rdx-tea/research/D3_3_1_BLOCKERS.md`

Modified:

- `.github/workflows/rdx-tea-integration-check.yml` (CI hardening
  per §10 above).
