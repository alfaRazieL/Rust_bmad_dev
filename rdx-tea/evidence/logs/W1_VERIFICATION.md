# Wave 1 verification — production/eval boundary + version reconciliation

**Wave:** W1 (Production layout & source boundaries)
**Repo:** `rdx-workspace/Rust_bmad_dev`  ·  **Branch:** `rdx-tea-integration`
**START_HEAD:** `bed1b30babd3ad71b3894ff631e60154f820c18f` (D3.4.1 handoff SHA)
**Basis:** `D3_RULE_OPERATION_PROVEN` (D3.4.1) — productionization, not a new experiment.
**Env:** determinism via `RDX_TEA_FAKE_NOW=2020-01-01T00:00:00+00:00`; no wallclock/random.
Python: `rdx-tea/.venv-baseline/bin/python` (3.14.4, pytest 9.1.1, jsonschema, pyyaml).
**Auth:** OAuth session inherited unchanged; `CLAUDE_CONFIG_DIR` never set/overridden; no API key / token / setup-token / apiKeyHelper used or written.

## What changed (all under `rdx-tea/**`, in scope)

| File | Change | Behaviour impact |
|---|---|---|
| `poc/install-tree/_bmad/rdx-tea/VERSION` | `0.3.1` → `0.3.2` | none — no generator reads `VERSION` (proven by grep) |
| `poc/install-tree/_bmad/rdx-tea/bootstrap/sources.lock` | comment-only reword to drop `evidence/`/`research/` path literals | none — YAML comment; `yaml.safe_load` values byte-identical; file not self-hashed; bundle does not depend on it |
| `poc/install-tree/README.md` | **new** — install-tree pointer/README (no physical move) | none (doc) |
| `poc/adapter/README.md` | **new** — classify keep-as-reference (not deleted) | none (doc) |
| `tests/contracts/test_l0_boundary_split_import.py` | **new** — boundary/import test (11 tests) | test-only |
| `evidence/hashes/w1_bundle_golden.py` | **new** — deterministic golden-bundle harness | evidence/tooling |
| `evidence/hashes/w1_bundle_golden.txt` | **new** — pinned 32-row golden signature | evidence |
| `evidence/logs/W1_*.{md,txt,log}` | **new** — this evidence | evidence |

Nothing deleted. Install-tree not moved. No generator logic changed.

## Gate results

| Gate | Result | Command / evidence |
|---|---|---|
| **G-W1-VERSION** | **PASS** | `cat VERSION` = `0.3.2` == `sources.lock:adapter_version` = `0.3.2` |
| **G-W1-BOUNDARY** | **PASS** | `pytest rdx-tea/tests/ -k boundary` → 11 passed, 126 deselected; see `W1_boundary-report.txt` |
| **G-W1-NOBEHAVIOUR** | **PASS** | golden bundle signature byte-identical pre/post; sha256 `94dffb95d763716f74803fff07a966da7dae08db8503bd1808b0c2e122a17bc9` unchanged |
| **G-SPLIT-IMPORT** | **PASS** | verbatim gate grep over shipped surface → zero hits |
| **G-DET** | **PASS** | golden harness identical across two processes; sorted iteration; `RDX_TEA_FAKE_NOW` used; no wallclock/random |
| **G-SCOPE** | **PASS** | branch delta vs `merge-base(origin/main)` = only `rdx-tea/`; `.agents/` untracked and never staged |
| **G-AUTH** (cross-cutting) | **PASS** | auth-material grep over shipped surface + touched files → zero hits |

## Determinism evidence (G-DET / G-W1-NOBEHAVIOUR)

`w1_bundle_golden.py` drives the PRODUCTION `prepare.prepare()` across all
8 obligation-matrix workflows × 4 representative inputs (32 cases), hashing
`active-context.md` and `run-manifest.json` bytes.

- Pre-change (2 processes): identical → pinned to `w1_bundle_golden.txt`
  (signature sha256 `94dffb95…`).
- Post-change (2 processes): identical, and byte-identical to the pin.

Reproduce:
```
RDX_TEA_FAKE_NOW=2020-01-01T00:00:00+00:00 \
  rdx-tea/.venv-baseline/bin/python rdx-tea/evidence/hashes/w1_bundle_golden.py \
  | diff - rdx-tea/evidence/hashes/w1_bundle_golden.txt   # => no diff
```

## Boundary test RED→GREEN proof

- GREEN (clean surface): `pytest -k boundary` → 11 passed.
- RED (injected `import live_harness` + `evidence/` path in a temp shipped
  `.py`): `test_boundary_no_eval_or_evidence_references` and
  `test_boundary_no_python_imports_of_eval_modules` both FAIL (2 failed).
- GREEN again after removing the temp file: 11 passed.
- Detector self-tests (`test_boundary_detector_flags_known_violations`,
  parametrized ×7) prove the detector fires on every known-bad form.

## Full suite (no behaviour regression)

`pytest rdx-tea/tests -q` → **137 passed** (126 pre-existing unchanged + 11
new boundary). Pre-existing count re-confirmed with the boundary file
ignored → 126 passed. See `W1_full_suite_GREEN.log`.

## Version reconciliation rationale

`VERSION` pinned **up** to `0.3.2` (not lock down to `0.3.1`) because the
frozen D3.4.1 pilot workspaces
(`evals/results/d3_4_rule_operation/workspaces/**/sources.lock`) all carry
`adapter_version: "0.3.2"` — `0.3.2` is the version actually exercised by
the proven pilot. Master plan §6.6 W1 directs "pin `VERSION ==
adapter_version`".

## Stop conditions

None hit. No golden bundle hash changed; no CI path broken; install-tree
not moved.
