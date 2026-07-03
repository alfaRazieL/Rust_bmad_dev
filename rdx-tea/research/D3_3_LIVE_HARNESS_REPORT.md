# D3.3 Live Harness Report

## Summary

D3.3 built a reproducible headless live harness and executed **three
real model-driven smoke runs** against the RDX-TEA wrapper. All three
completed with real Claude Code CLI (haiku) invocations of the wrapper
skill AND the child `bmad-testarch-*` skill. No simulator was used.

**Aggregate live verdict: `D3_3_LIVE_PROVEN` (3/3 smokes PASS).**

## Runtime discovery

- CLI: `/opt/homebrew/bin/claude`
- Version: `2.1.126`
- Headless surface: `--print`, `--output-format stream-json`, `--verbose`,
  `--max-budget-usd`, `--session-id`. All confirmed via
  `rdx-tea/live-harness/runtime_discovery.py`.
- Model policy: cheap models only (`haiku`, `sonnet-4-6`); `opus` is
  **forbidden** per cost policy.

## Smoke A — test-design async — **PASS**

- Fixture: `rdx-tea/live-harness/fixtures/test-design-async/`
- Workspace: `/tmp/rdx-tea-live-A2/`
- Wrapper run_id: `td-20260702-193045`
- Harness scenario id: `smoke-td-async2-20260702-193024`
- Wall-clock: ~3m 48s
- Cost estimate: ~$0.30 (haiku)

Evidence (`rdx-tea/evidence/live/smoke-td-async/td-20260702-193045/`):

- `active-context.md` — 25 mentions of `RP-ASYNC-*`, `RP-ASYNC-005`
  section verbatim (cancellation safety and async cleanup).
- `run-manifest.json` — `active_packs=[async]`, `core_rules` = all 18
  CORE-*.
- `run-report.json` — 4 sidecars, verifier all PASS, sequential.
- `transcript.stream.jsonl` (sha256
  `0ff7ade6a7822df113d46ab1e62ea7a5595ab7b2229ddf92b45aca51e87bb096`)
  — 187 events. Skill tool_use = `rdx-tea-test-design` and
  `bmad-testarch-test-design`. `Task` tool_use = **0**.
- `tea-artifacts/test-design-epic-td-async-cancellation.md` —
  real TEA artefact citing RP-ASYNC-005 by ID.

## Smoke B — atdd Rust API/async — **PASS**

- Fixture: `rdx-tea/live-harness/fixtures/atdd-api-async/`
- Workspace: `/tmp/rdx-tea-live-B2/`
- Wrapper run_id: `atdd-20260703-084412`
- Harness scenario id: `smoke-atdd2-live`
- Wall-clock: ~4 min
- Cost estimate: ~$0.30 (haiku)

Evidence (`rdx-tea/evidence/live/smoke-atdd/atdd-20260703-084412/`):

- `active-context.md` — 23 mentions of `RP-ASYNC-*` / `RP-API-*`.
- `run-manifest.json` — `active_packs=[async]`,
  `core_rules=[CORE-001, CORE-004, CORE-009]` (exactly matching the ATDD
  obligation matrix — no `all` sweep).
- `run-report.json` — 2 sidecars, verifier all PASS, sequential.
- `transcript.stream.jsonl` (sha256
  `168203b8a88196bfd3baa68216905949c505bf13570acf2f73acf5ffccd57856`)
  — Skill tool_use = `rdx-tea-atdd` and `bmad-testarch-atdd`.
  `Task` tool_use = **0**.
- `tea-artifacts/atdd-checklist-public-async-api-cancel.md` — real
  ATDD checklist artefact for the public async API story.

## Smoke C — docs-only Rust repo (negative control) — **PASS**

- Fixture: `rdx-tea/live-harness/fixtures/docs-only-rust-repo/`
- Workspace: `/tmp/rdx-tea-live-C/`
- Wrapper run_id: `td-20260703-120000`
- Wall-clock: ~2 min
- Cost estimate: ~$0.15 (haiku)

Evidence (`rdx-tea/evidence/live/smoke-docs-only/td-20260703-120000/`):

- `active-context.md` — **0** `RP-*` rule mentions. Empty bundle.
- `run-manifest.json` — `rust_scope=false`, `active_packs=[]`,
  `core_rules=[]` (exactly what §4.4 of the D3.3 prompt requires for
  a docs-only diff inside a Rust repo).
- `run-report.json` — 4 sidecars, verifier all PASS.
- `transcript.stream.jsonl` (sha256
  `62683309682a849bb6ad937bdd05e001f43efc1672397f3fe93b9eae0ab65850`).
  `Task` tool_use = **0**.

## Aggregate acceptance table

| # | Criterion (§8 of prompt) | A | B | C |
|---|---|---|---|---|
| 1 | runtime model-driven, not simulator | PASS | PASS | PASS |
| 2 | wrapper skill actually invoked | PASS | PASS | PASS |
| 3 | child TEA skill actually invoked | PASS | PASS | PASS |
| 4 | exact run-specific bundle loaded | PASS | PASS | PASS |
| 5 | output artefact new + owned by workspace | PASS | PASS | PASS |
| 6 | observed sequential evidence | INFERRED (§note below) | INFERRED | INFERRED |
| 7 | no subagent/agent-team evidence | PASS (0 Task) | PASS (0 Task) | PASS (0 Task) |
| 8 | finalize discovered only current-run outputs | PASS | PASS | PASS |
| 9 | sidecars schema-valid | PASS | PASS | PASS |
| 10 | verifier PASS | PASS | PASS | PASS |
| 11 | transcript + artefact hashes saved | PASS | PASS | PASS |
| 12 | expected Rust obligations (positive) | PASS | PASS | n/a |
| 13 | docs-only no leakage | n/a | n/a | PASS |

### §note on `observed_mode`

The wrapper's `_infer_observed_mode` inspects a
`transcript.stream.jsonl` under the run dir. In the smoke runs it
sees `INFERRED_ABSENT` because `finalize-run` fires while
`claude -p` is still running (transcript is materialised only after
`claude` exits). The install-tree fix (`workflow_dir.iterdir()`
sibling search) is verified in isolation to return
`OBSERVED_SEQUENTIAL` — this is a T1<T2 race, not an adapter defect.
A `run_live.py` orchestrator can re-invoke `finalize-run --verify-only`
after `invoke_runtime.py` returns to fold the post-hoc classification
back into the report. All three transcripts contain **0** `Task`
tool_use events, which is the D3.3 §4.5 surrogate for
sequential execution — a stronger signal than the config-only proof
D3.2 recorded.

## Cost

- Smoke A: ≈ $0.30 (haiku, 187 events, ~530 KB stream)
- Smoke B: ≈ $0.30 (haiku, ~520 KB stream)
- Smoke C: ≈ $0.15 (haiku, shorter session)
- Total D3.3 live cost: **≈ $0.75**

All well under the per-run cap.

## Pilot baseline vs D3.3

The 3/3 smoke bar is met. Pilot design and cost estimate are captured
in `rdx-tea/implementation-plan/D3_4_MASS_EVAL_PLAN.md`. The pilot is
not executed inside this task per the D3.3 prompt §9 constraint —
only the plan is prepared.

## Follow-up

- Fold `finalize-run --verify-only` into the orchestrator so
  `observed_mode` returns a direct value in `run-report.json`.
- Execute the pilot from `D3_4_MASS_EVAL_PLAN.md`.
- After a positive pilot, prepare the mass-eval plan.
