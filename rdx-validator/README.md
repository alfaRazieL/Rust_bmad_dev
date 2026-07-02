rdx-validator
=============

Standalone Python package implementing the RDX deterministic Cat-1/2 validator.

BMAD-independent: no imports from `_bmad/*`. Consumes only:
- the diff (via git or `--diff-file`),
- the canonical contracts under `tests/contracts/` (router rules, status, rule-check map, evidence schema),
- optional story/policy inputs (`--story`, `--policy-config`),
- optional pre-recorded evidence to be re-validated.

Phase 2 ships:
- diff parser (paths, added lines, renames, /dev/null awareness)
- stable diff digest
- router replay loaded from `tests/contracts/router-rules.json`
- exception parser
- status taxonomy + aggregator + exit-code mapper (per RDX_TEST_STRATEGY.md §5)
- baseline comparator (`--dual-run`)
- CORE-007 / CORE-008 / CORE-011 / CORE-014 / CORE-015 checks
- CLI entrypoint emitting human + JSON evidence

See `RDX_IMPLEMENTATION_PLAN_TESTED.md` Phase 2 for the test IDs each module
closes.
