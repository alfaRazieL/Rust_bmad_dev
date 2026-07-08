# ADR-008 — Behavioural verifier, fail-closed admission, run outcomes, cleanup & retry

Status: ACCEPTED (D4 Wave 6)
Date: 2026-07-09
Extends: ADR-006-AUTH-PRESERVING-RUNTIME-ISOLATION (§5-9)
Basis: `D3_RULE_OPERATION_PROVEN` (D3.4.1). Productionization of a proven
sequential wrapper-driven RDX→TEA lifecycle. NOT a benchmark; G7 is out of
scope and not claimed.

## Context

ADR-006 §5-9 defined, for the eval plane, a fail-closed run-outcome
classification, an admission gate that recomputes admissibility from a
bundle's own fields (never trusting a recorded `admissible` flag), and a
cleanup/retry discipline. That logic lived in the eval harness
(`live-harness/run_live.py` — `classify_run_outcome`, `admit_bundle`), which is
NOT installed into a user project. Wave 6 productionizes the equivalent model
on the SHIPPED surface, over the wrapper's own `run-report.json`, importing no
eval-plane module and referencing no eval/evidence path (G-SPLIT-IMPORT) — the
same production/eval-split re-implementation pattern used for
`workspace_delta.py` in Wave 5.

This ADR does NOT build the deferred `rdx-tea-validate` enforcement verdict
(`rdx-validator/rdx_tea/**`, STAGE-08) nor any mode/hook/CI-gate/Cat-4
machinery (STAGE-09). Those remain backlog.

## Decision

### 1. Behavioural verifier — 9 checks, each fails closed

`scripts/rdx_tea_validator.py::verify` performs nine checks, each bound to a
hashed input on disk; mutating that input flips EXACTLY that check to FAIL and
the aggregate `verdict` to FAIL (proven by
`tests/mutation/test_l7_w6_verifier_mutation.py`):

| check | hashed input | mutation that fails it |
|---|---|---|
| `schema` | the sidecar JSON | any schema violation (`additionalProperties:false`) |
| `manifest_hash` | `run-manifest.json` bytes | rewrite any manifest byte |
| `bundle_hash` | `active-context.md` | tamper the bundle |
| `artifact_hash` | the TEA artefact bytes | tamper the artefact |
| `base_head_exist` | `base_sha`/`head_sha` git objects | point at a nonexistent commit |
| `diff_digest_recomputed` | `diff.patch` | tamper the diff |
| `canonical_snapshot` | canonical KB/contract files | tamper a canonical source |
| `source_lock` | `bootstrap/sources.lock` | change a recorded source SHA |
| `artifact_boundary` | the artefact path | symlink / traversal / outside project-root |

Post-schema field reads are defensive (`.get`): a schema-invalid sidecar that
dropped a required field yields a graceful check FAIL, never a crash — strictly
more fail-closed. No check can be bypassed; a failing check can never be
recorded as PASS.

### 2. Admission recomputed from primitives — a dishonest bundle cannot self-admit

`scripts/admission.py::admit_run(report, state_phase=None)` recomputes
FINALIZED-admissibility from the run-report's OWN primitive fields
(`execution_mode`, `resolved_mode`, `observed_mode`, `sidecars`, `verifier`,
`workspace_delta`, `workspace_delta_consistency`, `artifact_consistency`,
`consistency_status`, `new_artefacts`, and the optional wrapper run-state
`phase`). It IGNORES any recorded `admissible` / `admission` field: a bundle
that self-declares `admissible: true` while violating an invariant is reported
NOT admissible, with the violated reasons. `finalize-run` records the
recomputed block for audit, but the gate never trusts it. Exposed as
`admission.py admit --report <run-report.json> [--state <run-state.json>]`
(exit 0 admissible, exit 2 otherwise).

### 3. Run outcomes — fixed deterministic order

`admit_run` evaluates a fixed ordered list of check groups and returns the
FIRST group that produces any reason (fail-closed, first-failure-wins);
`SUCCESS` (FINALIZED-admissible) requires every group clean:

    AUTH_FAILURE → RUNTIME_FAILURE → SCHEMA_FAILURE → MODE_FAILURE →
    WORKFLOW_FAILURE → VERIFIER_FAILURE → CONSISTENCY_FAILURE →
    PARTIAL_RUN → SUCCESS

This maps ADR-006 §5's live-plane order (AUTH → TIMEOUT → RUNTIME →
CONTAMINATION → RUN_ID_MISMATCH → WORKFLOW → VERIFIER → SCHEMA → SUCCESS) onto
the finalize report: the live-only classes (TIMEOUT, CONTAMINATION,
RUN_ID_MISMATCH) belong to the invocation layer and are absent here; SCHEMA is
promoted ahead of the content groups (as in the live `admit_bundle`) so the
content checks may assume every primitive field is present.

A run is **never FINALIZED-admissible** when any of the following hold:
`consistency_status == "FAIL"`; `workspace_delta_consistency.status == "FAIL"`;
`artifact_consistency.status == "FAIL"`; any verifier check FAIL; a
missing/count-mismatched sidecar; a non-sequential execution/resolved mode; a
Task/subagent-observed run (`observed_mode == "OBSERVED_SUBAGENT"`); a partial
or failed wrapper state (incl. `finalized_consistency_failed`); a missing or
invalid primitive field; or a `--verify-only` advisory run.

The wrapper's `finalize-run` exit code reflects the LIFECYCLE outcome (it fails
closed on non-sequential mode, empty delta, bundle tamper, and
artifact/workspace consistency). A verifier-failing or subagent-observed run
may complete the lifecycle (exit 0) but is recorded with
`admission.admissible == false`; `admission.admit_run` is the authoritative
FINALIZED-admissible verdict consumed downstream (mirroring ADR-006: the
harness records, the gate judges).

### 4. Cleanup — always, even on the failure path

`finalize-run` restores/removes the run-specific overlay and releases the
active-run lock on EVERY exit, including fail-closed exits, so the workspace is
left clean and unlocked (proven on the consistency-failure path by
`tests/integration/test_l3_w6_failclosed.py`). The failed `run-report.json` is
preserved honestly with its FAIL fields; it is never overwritten or promoted to
success.

### 5. Bounded retry policy — INFRA / RUNTIME only

Retries are permitted ONLY for INFRA/RUNTIME-class transients (e.g. a
git/subprocess I/O error, an aborted process, an environment fault) that never
reached a rule-operation decision. A retry:

- MUST NOT convert a rule-operation, verifier, admission, workspace-delta, or
  artifact-consistency FAILURE into an infra retry or an infra success — those
  are decisions about the candidate's output, not transients;
- MUST NOT overwrite or delete a preserved failed attempt — a new attempt is
  recorded under its own `run_id` (run-scoped directory), leaving prior
  evidence intact (ADR-006 §9 versioned-attempt discipline);
- MUST re-run the full prepare → child → finalize lifecycle for the new
  attempt (no partial resume of a decided run);
- inherits fail-closed admission: the retried run is admissible only if it
  independently satisfies every group in §3.

Enforcement of retry orchestration (scheduler, attempt suffixes) is out of
scope for the shipped runtime; this ADR fixes the SEMANTICS the runtime and any
future orchestrator must honour.

## Consequences

- Every verifier check is provably fail-closed and isolated (per-check mutation
  tests), so the integrity signal cannot be silently weakened.
- Admissibility is a pure function of recorded primitives; a dishonest bundle
  cannot self-admit, and the same report always yields the same verdict
  (determinism; no wall-clock/random in the admission path).
- A failed or partial run is inadmissible by construction, while its evidence
  is preserved — audits see the truth, not a masked success.
- The shipped runtime carries the admission gate without importing the eval
  harness (G-SPLIT-IMPORT preserved).

## Alternatives considered

- **Trust the wrapper's recorded `admissible` flag** — rejected (ADR-006 §8
  rationale): the gate recomputes from primitives so a dishonest bundle cannot
  self-admit.
- **Make `finalize-run` hard-abort on a subagent-observed run** — rejected: the
  wrapper's job is honest recording; forcing a non-zero exit there would drop
  the recorded `observed_mode` evidence and break the D3.3 observed-mode
  surrogate. Admission (not the exit code) is the authoritative gate.
- **Import `admit_bundle` from the eval harness** — rejected by the
  production/eval split (G-SPLIT-IMPORT); re-implemented on the shipped surface.
