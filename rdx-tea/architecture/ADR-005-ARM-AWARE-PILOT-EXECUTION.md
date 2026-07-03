# ADR-005 — Arm-aware pilot execution

Status: ACCEPTED (D3.3.2)
Date: 2026-07-03
Supersedes: none
Extends: ADR-004-PILOT-HARNESS

## Context

Post-D3.3.1 audit found that the harness had a single execution path
that always invoked the RDX wrapper — "baseline" and "candidate"
differed only in a label on the evidence bundle. A comparative pilot
built on that path would score identical work under both arms and
prove nothing about RDX-vs-non-RDX behavioural benefit.

The audit also found supporting gaps: schedule-owned run_id was
ignored end-to-end; the evidence schema had no baseline branch; the
Skill classifier accepted free-text prose as invocation evidence; the
runtime surface was recorded as the intended surface rather than
what Claude Code reported at init; CI silently skipped 34 upstream
tests via a fixture-time `pytest.skip()` and reported a 533-passed
count that summed re-executions.

## Decision

Adopt arm-aware pilot execution with the following invariants,
enforced at CODE level, not by reviewer discipline:

1. **Arm-specific prompts**. `arm_prompt(arm, workflow, run_id)` is
   the single source of truth. Baseline prompts never mention RDX,
   wrapper, RP-*, active-context, prepare-run, or finalize-run.
   Candidate prompts pin the invocation contract.

2. **Arm-specific installed skills**. `arm_installed_skills` returns
   only the child skill for baseline and both wrapper+child for
   candidate. The isolated `CLAUDE_CONFIG_DIR` preflight fails
   closed if the installed set doesn't match.

3. **Arm-aware evidence schema (v2)**. `live-evidence.v2.schema.json`
   uses `if/then + not` branches: baseline bundles must carry a
   `baseline` block with `wrapper_skill_invoked == false`, no
   candidate block; candidate bundles must carry the `candidate`
   block with sidecars/active_packs/verifier_all_pass, no baseline
   block.

4. **Schedule-owned run_id end-to-end**. `RunSpec.run_id` is
   required. `emit_invocation_contract` writes
   `_bmad-run/rdx-tea-invocation.json` BEFORE the wrapper runs. The
   wrapper's `prepare_run` reads that file and refuses to proceed
   on any mismatch. Post-run `_check_run_id_handshake` compares all
   four surfaces; any divergence is `PILOT_INVALID`.

5. **Structured-only classifier**. The transcript classifier reads
   only `tool_use` blocks with an explicit `name` in the Skill /
   SlashCommand family. Assistant prose is deliberately ignored.

6. **Observed runtime surface**. `_extract_runtime_init` parses the
   actual `system`/`init` event. Evidence records
   `observed_surface`, `expected_surface`, `surface_diff`, and
   `contamination` — never a constant like `mcp_servers=[]`.

7. **Structured JSON lock**. `active-run.lock` is a JSON document
   with `run_id`, `workflow`, `pid`, `created_at`. Ownership is
   exact equality. Legacy string locks are treated as unowned so
   they cannot be silently released.

8. **Observed cleanup**. `observe_cleanup()` re-reads on-disk state
   after cleanup and records it verbatim. No booleans are constants.

9. **Real source-lock verify**. `bootstrap.py --verify-only` exists
   and is called without `|| echo` masking. Drift fails CI.

10. **CI skip and unique-count gates**. `ci_check.py refuse-skips`
    parses JUnit XML; `ci_check.py unique-count` reports unique
    node IDs and re-execution counts.

11. **Rubric v3, schedule v2**. Two positive scenarios explicit;
    decision rule EITHER/OR; schedule locked with hash-verifiable
    prompt/fixture/rubric/grader versions.

## Rationale for non-obvious choices

- **Keep `bypassPermissions`**. Claude Code CLI currently refuses to
  run headless without an explicit `--permission-mode`. Baseline and
  candidate use the SAME value, so the arms remain comparable; the
  observed permission mode is captured in evidence so any future
  drift is visible. Removing bypassPermissions entirely would
  require a Claude Code CLI feature that does not exist today.

- **Empty MCP file instead of `--bare`**. `--bare` also disables
  Skill discovery, which the candidate arm depends on. An empty
  `mcp.json` scoped via `CLAUDE_MCP_CONFIG` and `CLAUDE_CONFIG_DIR`
  is the minimal-hostile alternative.

- **Old ATDD fixture retained**. Removing it would look like
  cover-up; the negative-guard test `test_old_atdd_fixture_does_not_
  activate_api_pack` prevents silent re-use.

- **LLM grader NOT run in D3.3.2**. Layer-2 semantic grading is
  fully implemented and testable but returns `NOT_RUN` per sample.
  Running it would either require the live pilot (blocked by BLOCKERS
  §2) or synthetic samples that would poison the disagreement gate.
  The grader interface is nevertheless proven by the disagreement
  regression test.

## Consequences

- Baseline and candidate execution paths are provably different at
  code and at schema level.
- Any run whose evidence fails the arm-aware v2 schema is rejected
  before the grader sees it — pilot invalidity is detected at
  ingest, not at aggregation.
- Free-text prose can no longer inflate wrapper/child invocation
  counts. A model that says "I would invoke rdx-tea-atdd" without a
  structured Skill event produces `INFERRED_ABSENT`, not
  `OBSERVED_SEQUENTIAL`.
- CI can no longer report PASS with 34 fixture-time skips hidden;
  either the skip is on the reviewed allowlist or CI exits 6.
- Two positive scenarios and one negative control are precommitted;
  the rubric decision rule matches the actual scenario count.

## Alternatives considered

- **Single execution path with metadata-only arm flag** — rejected;
  it is the exact bug this ADR fixes.
- **Free-text `--bare` runtime** — rejected; breaks Skill discovery.
- **Recompute the CI test count off `.pytest_cache`** — rejected;
  the cache is not a stable interface. JUnit XML is the contract.
- **Merge rubric v2 and rubric v3 by silent edit** — rejected;
  supersession is auditable via `supersedes:` field in both YAMLs.
