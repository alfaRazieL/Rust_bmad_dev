# Wave 3 — Active-context bundle builder — verification

- **Repo / branch:** `rdx-workspace/Rust_bmad_dev` @ `rdx-tea-integration`
- **Basis:** D3_RULE_OPERATION_PROVEN (D3.4.1). Productionization only.
- **W3 START_HEAD:** `6e1b2f346d1b8a260b8dba0401f0483656b0b57a` (== W2 FINAL_HEAD)
- **Pre-W3 owner checkpoint commit:** `f54b96307e30d7de8f310f0e9b2bae86d40794b4`
- **Python:** 3.14.4 (`rdx-tea/.venv-baseline`)
- **cwd for all commands:** repo root `.../rdx-workspace/Rust_bmad_dev`

## Pre-W3 regression (before any bundle-builder change)

| Check | Command | Result |
|---|---|---|
| router/forbidden/docs/boundary | `pytest rdx-tea/tests -k "router_parity or forbidden or docs_only or boundary" -q` | 20 passed (pre-change baseline) |
| W2 canonical snapshot pin | `python rdx-tea/evidence/hashes/w2_canonical_snapshot.py` | OK — `a97d9f85…c5e8d8` matches pin |
| full suite (baseline) | `pytest rdx-tea/tests -q` | 166 passed |
| W1 golden bundle (env-fixed) | `RDX_TEA_FAKE_NOW=2020-01-01… python …/w1_bundle_golden.py` | matches pin |

## Change summary

The proven D3.4.1 bundle builder already implemented identity fail-closed,
docs-only→empty, and field filtering. W3 **productionized** it:

1. **Byte-determinism (clock-free).** `prepare.py` no longer reads the
   wall-clock. `_stable_now()` (wall-clock default) → `_prepared_at_stamp()`
   returning `RDX_TEA_FAKE_NOW` if injected else `""`; `datetime` import
   removed. The `run-manifest.json` — whose sha256 the binder stamps into
   the sidecar as `prepare_manifest_sha256` — is now byte-identical across
   two independent OS processes with NO env injection. Bundle bytes are
   unchanged (W1 golden bundle column identical).
2. **Golden pin.** `evidence/hashes/w3_bundle_golden.{py,txt}` — 32 rows
   (8 workflows × 4 scenarios), clock-free, pinning `bundle_sha` +
   `manifest_sha` per scenario.
3. **Schema authority decided.** `architecture/SCHEMA_AUTHORITY.md`:
   `canonical/` is authoritative (shipped, source-locked); `architecture/`
   is a byte-identical mirror, drift-guarded by test.
4. **W3 tests** (`tests/integration/test_l3_w3_bundle_builder.py`, 23):
   two-process determinism, identity fail-closed, schema-valid manifest +
   binder sidecar, docs-only→empty for an "all"-CORE workflow, field
   filtering, golden verify, mirror drift guard.

## RED → GREEN (determinism)

See `W3_determinism_red_green.txt`. With the committed wall-clock
`prepare.py`, `test_w3_determinism_two_processes_*` and
`test_w3_determinism_prepare_source_has_no_wallclock` FAIL (2 failed).
With the clock-free `prepare.py`, all 3 determinism tests PASS.

## Gate results (all PASS)

| Gate | Command | Result |
|---|---|---|
| **G-W3-DETERMINISM** | `python rdx-tea/evidence/hashes/w3_bundle_golden.py` (+ 2-process test) | OK — 32 rows match pin; bundle+manifest byte-identical across processes |
| **G-W3-IDENTITY** | `pytest rdx-tea/tests -k identity -q` | 13 passed (missing/all-zero/non-hex SHA + diff_digest agreement fail-closed) |
| **G-W3-SCHEMA** | `pytest rdx-tea/tests -k schema -q` | 8 passed (manifest fields conform; binder sidecar validates rdx-tea-run.v1; docs-only→empty stays valid) |
| **G-DET** | w1 golden (env-fixed) + w2 canon pin | both match; no wall-clock/random in bundle builder |
| **G-SCOPE** | changed files vs `origin/main` | only `rdx-tea/**` (PASS) |
| **G-AUTH** (cross) | grep auth env in shipped surface | zero hits |
| **G-SPLIT-IMPORT** (cross) | grep live_harness/evals/evidence in shipped surface | zero hits |
| full suite | `pytest rdx-tea/tests -q` | **189 passed** |

## W2 invariants preserved

- Router NOT forked (`scripts/router.py` untouched).
- Canonical KB unchanged → `w2_canonical_snapshot.txt` still valid
  (`a97d9f85…c5e8d8`).
- Forbidden packs judged by manifest `active_packs[].rule_ids`; docs-only
  fixture activates `[]`; router parity tests green.
- Bundle bytes unchanged (W1 golden bundle column identical to W3).
