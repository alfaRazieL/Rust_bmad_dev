# RDX Tests

This directory holds **all** RDX tests, structured by layer (L0..L8) per `RDX_TEST_STRATEGY.md` §2.

Test cases are catalogued machine-readably in `../RDX_TEST_CASES.yaml`. Every file or fixture here must trace back to a test ID in that YAML.

## Layout

| Subdir | Layer | What lives here |
|--------|-------|-----------------|
| `contracts/` | L0 | JSON Schemas, golden snapshots, drift checkers |
| `unit/` | L1 | Pytest modules per validator source file |
| `fixtures/` | L1–L8 inputs | Diffs, Cargo projects, stories, evidence, approvals |
| `integration/` | L3 | Drivers that run validator against Cargo fixtures |
| `bmad/` | L4 | BMAD-specific: menu override, wrapper-resume, setup-uninstall, code-review |
| `evals/` | L5 | Behavioral eval configs (consumed by `bmad-eval-runner`) |
| `ci/` | L6 | CI / hook end-to-end fixtures |
| `mutation/` | L7 | Adversarial/security tests |
| `compatibility/` | cross-cutting | OS × Python × Rust × BMAD version matrix tests |
| `acceptance/` | release gates | V5/V6 black-box acceptance suites |

## Rules

1. **No production code in `tests/`.** Test fixtures, harnesses, and stubs only.
2. **Every fixture has an expected verdict** stored alongside it (e.g., `fixture.diff` + `fixture.expected.json`).
3. **Test naming traces to the YAML.** A test file's docstring or filename references the test ID (e.g., `test_l1_diff_001.py` → `T-L1-DIFF-001`).
4. **No magic numbers.** Expected outputs come from fixtures, not from inline literals in test code.

## How to add a test

1. Open `../RDX_TEST_CASES.yaml`; find or add the entry
2. Create fixture(s) under `fixtures/`
3. Create the test driver under the layer-appropriate subdir
4. Run pytest — should fail (red)
5. Implement the production code that makes it pass (green)
6. Commit referencing the test ID
