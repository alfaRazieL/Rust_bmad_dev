# ADR-004 — Pilot harness architecture

Status: ACCEPTED (D3.3.1)
Date: 2026-07-03
Supersedes: none
Superseded by: none

## Context

D3.3 executed three real Claude Code smoke runs and produced live
evidence bundles, but review found six methodological gaps:

1. no single canonical entry point (`run_live.py` was documented in
   the README but not implemented);
2. `observed_mode` classification was performed by a wrapper hook
   inside the still-running LLM session — before the transcript
   was materialised — and therefore always returned `INFERRED_ABSENT`;
3. output roots were scanned nested, so every artefact was recorded
   twice;
4. ATDD smoke used bare `api` / `async` tags with a diff that
   contained none of the api pack's positive signals, so the api pack
   never activated;
5. failure paths (timeout, missing artefact, verifier raise,
   KeyboardInterrupt) left the active-run lock and run-specific
   overlay in place;
6. the pilot rubric mixed candidate-only fidelity metrics (RP-* IDs)
   with comparative quality metrics graded against baseline.

Any comparative pilot built on top of D3.3 as-is would either fail to
run or would systematically underscore baseline on metrics baseline
has no way to satisfy. That is the definition of an invalid pilot.

## Decision

Adopt a single, canonical D3.3.1 pilot harness with the following
shape:

1. `rdx-tea/live-harness/run_live.py` is the ONLY supported entry
   point. It exposes four commands: `run-smoke`, `run-one`,
   `reconcile-transcript`, `abort-run`. Every step is a callable and
   every step is also a subcommand so reviewers can reproduce or
   inspect any individual stage.
2. `reconcile-transcript` is a separate operation from
   `finalize_run`. It is idempotent: it reads a completed
   `run-report.json`, classifies the transcript, and writes back
   only the observation fields atomically. It NEVER re-binds
   artefacts, NEVER creates sidecars, NEVER touches the run-state
   phase. Repeated calls produce identical results.
3. Output canonicalisation is enforced at the harness layer, not at
   the wrapper layer. Nested roots collapse to their closest common
   ancestor; artefacts dedupe by resolved path; each artefact →
   exactly one sidecar → exactly one verifier result.
4. `abort_run` guarantees crash-safe cleanup: foreign locks are
   preserved, foreign overlays are preserved, own state transitions
   to `ABORTED` or `FAILED`, and an `aborted.json` marker records
   the reason. Called from `try/except` around invoke and finalize.
5. Every run creates an isolated `CLAUDE_CONFIG_DIR` seeded only
   with the project rdx-tea skills; MCP disabled; empty user memory;
   config directory tree hashed for the evidence bundle.
6. Evidence bundles validate against
   `schemas/live-evidence.v1.schema.json` (Draft-2020-12) — a
   schema-fail is a run-fail.
7. Pilot rubric splits into
   `candidate_integration_fidelity` (candidate-only) and
   `comparative_artifact_quality` (identical scoring on baseline
   and candidate). Baseline is never penalised for missing RP-* IDs.
8. Pilot schedule (18 runs, seed=20260703, fixed model, fixed
   fixture hashes, fixed grader version) is committed BEFORE the
   first pilot run and asserted immutable by
   `test_pilot_schedule_precommitted`.

## Rationale for the non-obvious choices

- `reconcile-transcript` separate from `finalize-run --verify-only`:
  `finalize_run` mutates run state (`phase = finalized`) and the
  binder is not designed to skip re-scanning. Reusing it would
  silently rebind artefacts on the second call and would fail on
  the third (`state.phase != prepared`). A dedicated reconciler
  makes the invariant explicit.

- Empty `mcp.json` instead of `--bare`: at the time of writing
  `claude --bare` disables Skill discovery, which would break the
  candidate arm. Setting `CLAUDE_MCP_CONFIG` to a file with
  `{"mcpServers": {}}` is the minimal-hostile option that both
  disables MCP and keeps Skills discoverable.

- Old ATDD fixture retained on disk: deleting it would look like
  cover-up. Retaining it AND marking it
  `ATDD_ASYNC_ONLY_PREVIOUS_EVIDENCE` documents the audit trail; the
  regression guard test refuses silent re-use.

- Two-commit identity: `PENDING` in an evidence file is the honest
  representation of "CI has not run yet". Papering over PENDING
  values would be worse than the placeholder. The identity closes
  when the second commit lands, and that closure is auditable.

## Consequences

- Reviewers have a single canonical command to reproduce a live
  smoke and a schema to validate its outputs; the harness is easier
  to audit than three loose scripts.
- Comparative pilot is grade-correct by construction: baseline
  never scored on RP-* IDs; docs-only never divides by zero;
  sanitisation strips arm-identifying strings before the layer-2
  grader sees a sample.
- Any future divergence between the deterministic fixture-router
  behaviour and the live-model bundle is caught by
  `test_corrected_atdd_activates_api_pack` before a pilot run is
  wasted on it.
- The pilot cannot start until Blocker §1 (corrected ATDD smoke
  live) and Blocker §2 (CI closure) close. This is a deliberate
  hard-stop enforced by the D3.3.1 verdict machinery, not by
  reviewer discipline.

## Alternatives considered

- Fold `run_live.py` into `finalize_run --verify-only`: rejected
  because it violates the phase invariant and rebinds artefacts.
- Delete the old ATDD fixture: rejected because it destroys audit
  trail and makes it harder to reproduce §2.4 of the audit.
- Skip runtime isolation to save engineering effort: rejected
  because a comparative pilot with contaminated environments is
  scientifically meaningless.
- Skip the schema and rely on ad-hoc field checks: rejected because
  the pilot rubric depends on those fields; without a schema the
  first missing field would surface as a grader crash mid-pilot.
