# Wave 4 — Wrapper Skills & non-interactive lifecycle — verification

- **Repo / branch:** `rdx-workspace/Rust_bmad_dev` @ `rdx-tea-integration`
- **Basis:** D3_RULE_OPERATION_PROVEN (D3.4.1). Productionization only — the
  sequential wrapper-driven RDX→TEA lifecycle is already PROVEN; W4 hardens
  it. G7 (behavioural benefit vs baseline) is out of scope, not claimed.
- **W4 START_HEAD:** `b22ce957dcffd6486f476ee38dc01e136483ab1e` (== W3 FINAL_HEAD)
- **Pre-W4 owner checkpoint commit:** `2ffeda6` (record Wave 3 owner checkpoint)
- **Python:** 3.14.4 (`rdx-tea/.venv-baseline`)
- **cwd for all commands:** repo root `.../rdx-workspace/Rust_bmad_dev`
- **Live model calls:** NONE. Tests use the env-gated deterministic
  fake-artefact path (`RDX_TEA_ALLOW_TEST_ARTEFACT=1`).

## Pre-W4 regression (before any wrapper/SKILL change) — all PASS

See `W4_pre_regression_GREEN.log`.

| Check | Command | Result |
|---|---|---|
| router/forbidden/docs/boundary | `pytest rdx-tea/tests -k "router_parity or forbidden or docs_only or boundary" -q` | 21 passed |
| W2 canonical snapshot pin | `python rdx-tea/evidence/hashes/w2_canonical_snapshot.py` | OK — `a97d9f85…c5e8d8` matches pin |
| W3 golden bundle pin | `python rdx-tea/evidence/hashes/w3_bundle_golden.py` | OK — 32 rows match pin |
| identity/schema/determinism | `pytest rdx-tea/tests -k "identity or schema or determinism" -q` | 24 passed |
| full suite (baseline) | `pytest rdx-tea/tests -q` | 189 passed |

## Change summary (productionization; proven lifecycle preserved)

The D3.3/D3.4.1 wrapper already implemented the two-phase lifecycle
(invocation-contract handshake, sequential fail-closed, overlay
backup/restore, active-run lock, empty-delta fail-closed, env-gated
test-only flags). W4 **productionized** it and closed the two documented
gaps, all under RED→GREEN:

1. **Honest run-report audit stamp.** `rdx_tea_wrapper.finalize_run` now
   emits `created_at` (the canonical wall-clock audit field documented by
   `prepare.py`/`binder.py`) alongside the retained `finalized_at` alias.
   The run-report is NOT hashed into the verification chain, so this never
   touches determinism. The hashed `run-manifest.json` still carries no
   wall-clock (`prepared_at == ""` by default) — W3 invariant preserved.
2. **`--disallowedTools Task TaskOutput TaskStop` documented.** Both wrapper
   Skills (`rdx-tea-test-design`, `rdx-tea-atdd`) now instruct Step 5 to
   invoke the child non-interactively in the same session with
   Task/subagent dispatch disabled (observed Task dispatch MUST be 0). The
   ATDD Skill additionally ties the disallow-list to its step-c subagent
   payload construction. No production command line carries a test-only flag.

No generator changed (`prepare.py`, canonical KB, router all untouched) →
no golden re-pin required; W1/W2/W3 golden hashes byte-identical.

### New tests (RED → GREEN)

- `tests/lifecycle/test_l4_w4_lifecycle.py` (24) — self-contained (no
  upstream clone): invocation contract (run_id verbatim, mismatch/arm/
  workflow fail-closed, absent→fallback); sequential fail-closed on prepare
  (auto/subagent/agent-team/parallel) AND finalize; empty-delta fail-closed;
  `--simulate-child` rejected by argparse on both phases;
  `--test-write-fake-artefact` and `--allow-fixture-diff` env-gated;
  no-Task observed_mode; wrapper source never dispatches subagents; Skills
  document `--disallowedTools`; overlay backup+restore / remove-when-none;
  lock acquire/refuse/release; `prepared_at == ""` (no wall-clock in
  manifest); wrapper accepts empty `prepared_at`; run-report `created_at`
  and sidecar `bound_at` audit stamps live outside the hashed manifest.
- `tests/bmad-tea/test_l4_w4_sequential_slice.py` (3) — self-contained
  end-to-end sequential slice (prepare→fake-child→finalize): run-report
  written with `created_at`; sidecar validates against the **canonical**
  (authoritative) `rdx-tea-run.v1` schema; sequential fail-closed.

RED before change: (a) SKILL.md lacked `--disallowedTools Task TaskOutput
TaskStop`; (b) run-report lacked `created_at`. See `W4_red_green.txt`.

## Gate results (all PASS)

| Gate | Command | Result |
|---|---|---|
| **G-W4-LIFECYCLE** | `pytest rdx-tea/tests/bmad-tea -q` | 29 passed; run-report written (`evidence/artifacts/w4_sample_run_report.json`) |
| **G-W4-SEQUENTIAL** | `pytest rdx-tea/tests -k sequential -q` | 15 passed; non-sequential HALTs on both phases |
| **G-W4-NOTASK** | `pytest rdx-tea/tests/lifecycle -q` + SKILL.md grep | 38 passed; Task dispatch 0; prod path never uses `--simulate-child`/`--test-write-fake-artefact`; 0 prod command lines carry a test-only flag |
| **G-AUTH** (cross) | grep auth env in `poc/install-tree`,`installer` | 0 hits (no ANTHROPIC_API_KEY/OAUTH/setup-token/apiKeyHelper/CLAUDE_CONFIG_DIR) |
| **G-SPLIT-IMPORT** (cross) | grep live-harness/evals/evidence in shipped surface | 0 hits |
| **G-DET** (cross) | W1 (env-fixed) + W2 canon + W3 golden pins; 2-process determinism | all match; 5 passed |
| **G-SCOPE** (cross) | changed files vs `origin/main` outside allowed roots | 0 out-of-scope |
| full suite | `pytest rdx-tea/tests -q` | **216 passed** (+27 vs 189 baseline) |

## W3 invariants preserved

- No wall-clock reintroduced into `run-manifest.json` (`prepared_at == ""`
  by default; injected `RDX_TEA_FAKE_NOW` is a deterministic caller value).
- `prepare.py` untouched → W3 determinism + golden bundle pin unchanged.
- `w3_bundle_golden.py` and `w2_canonical_snapshot.py` still PASS.
- Schema authority unchanged: `canonical/` authoritative; `architecture/`
  byte-identical mirror.
- Router parity / forbidden-by-active-packs (W2) still PASS.
- Honest wall-clock audit stamps only in non-hashed run-report `created_at`
  and binder sidecar `bound_at`.
- Production runtime imports no `live-harness`/`evals`.

## Compatibility checks (required)

| Assertion | Where proven | Result |
|---|---|---|
| prepare emits `prepared_at == ""` by default | `test_l4_w4_prepared_at_empty_by_default_no_wallclock_in_manifest` | PASS |
| wrapper accepts `prepared_at == ""` | `test_l4_w4_wrapper_accepts_empty_prepared_at_through_finalize` | PASS |
| binder sidecar still validates | `test_l4_w4_sequential_slice_sidecar_schema_valid` (canonical schema) | PASS |
| run-report `created_at` is an audit stamp outside hashed manifest | `test_l4_w4_run_report_created_at_is_audit_stamp_outside_hashed_manifest` | PASS |
| sidecar `bound_at` is an audit stamp outside hashed manifest | `test_l4_w4_sidecar_bound_at_is_audit_stamp_outside_hashed_manifest` | PASS |

## Stop conditions (WAVE_4_PROMPT) — none hit

- Wrapper simulates child in production: NO (`--simulate-child` removed;
  `--test-write-fake-artefact` env-gated to `RDX_TEA_ALLOW_TEST_ARTEFACT=1`).
- Task dispatch appears: NO (observed_mode never `OBSERVED_SUBAGENT`;
  Skills disallow Task/TaskOutput/TaskStop).
- Non-sequential admitted: NO (fail-closed on both phases).
- Overlay not restored: NO (restore-from-backup / remove-when-none proven).
