# tests/docs/ — Phase 10 documentation tests

Deterministic structural tests that verify the user-facing documentation
satisfies the Phase 10 entry/exit gates from
`RDX_IMPLEMENTATION_PLAN_TESTED.md` and the doc-honesty acceptance test
`T-V5-ACC-06`.

These tests parse `README.md`, `docs/*.md`, and `.claude/skills/rdx-*/**.md`
as plain text. They do NOT depend on the validator, BMAD, or any external
service. They are safe to run in any CI lane.

## Test IDs closed here

- T-DOC-CHECKLIST-001  — `docs/doc-review-checklist.md` exists and enumerates the 14 implementation topics.
- T-DOC-README-CI-COST-001 — README has both "GH Actions Free" and "switching to paid" subsections with required content.
- T-DOC-README-MODE2-001 — README positions Mode 2 as a release-quality option, never as a "stepping stone".
- T-DOC-README-ARCHITECTURE-001 — README covers architecture (modes 0–4, validator, wrapper, hook, CI, Cat-1..4, specialist approvals).
- T-DOC-HONESTY-EXTENDED-001 — T-V5-ACC-06 forbidden-phrase scan extended to README.md + docs/*.md.

The narrow doc-honesty test `tests/acceptance/test_doc_honesty.py`
(which scans `.claude/skills/rdx-*/**.md`) remains the official close-out
for T-V5-ACC-06 itself; the extended scan here is additional coverage.

## Why a separate folder?

Doc tests run on every PR that touches `README.md`, `docs/**.md`, or
`.claude/skills/rdx-*/**.md`. Keeping them isolated lets a "docs-only" PR
skip the slow validator-binding tests while still exercising the
release-blocking acceptance gates listed above.
