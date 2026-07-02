# Spike 0.3 — Standalone validator prototype

**Question:** Can a BMAD-agnostic Python CLI reproduce router replay on real git diffs with stable digests and machine-readable verdicts?

**Verdict:** EXPERIMENT VERIFIED on 4 fixtures.

## Files

- `rdx_validator.py` — 260 LOC Python 3 prototype, stdlib only (no pip dependencies)
- `fixtures/fixture-{1,2,3,4}-*.diff` — 4 test diffs covering async, doc-only-async, unsafe, Cargo.toml

## How to reproduce

```bash
cd spikes/0.3-standalone-validator

python3 rdx_validator.py --diff-file fixtures/fixture-1-real-async.diff
# Expected: activated_packs: ["async"], exit 0

python3 rdx_validator.py --diff-file fixtures/fixture-2-doc-only-async.diff
# Expected: activated_packs: [], exit 0  (comment-only async ignored)

python3 rdx_validator.py --diff-file fixtures/fixture-3-new-unsafe.diff
# Expected: activated_packs: ["unsafe"], exit 0

python3 rdx_validator.py --diff-file fixtures/fixture-4-cargo.diff
# Expected: activated_packs: ["cargo"], paths: ["Cargo.toml"], exit 0
```

Or against a real git repo:
```bash
python3 rdx_validator.py --base main --head HEAD --cwd /path/to/repo
```

## Exit codes (stable contract)

- `0` — PASS or all checks NOT_APPLICABLE
- `1` — FAIL (blocking finding) *(not yet emitted in this prototype — Phase 2)*
- `2` — ENVIRONMENT_UNAVAILABLE (git missing, not a repo)
- `3` — NOT_RUN with insufficient reason

## Scope of this prototype

**Done:**
- ✓ git diff parsing (paths, hunks, added lines)
- ✓ `diff_digest` SHA-256 computation
- ✓ Router replay (Async, Unsafe, FFI, Cargo)
- ✓ Comment-vs-code distinction (negative trigger for doc-only matches)
- ✓ JSON output (schema-ready)
- ✓ Stable exit code contract

**Intentionally NOT done (Phase 2):**
- CORE-007 protected-file enforcement
- CORE-011 compile-evidence requirement
- CORE-014 suppression detection
- CORE-008 panic-discipline detection
- Base/head dual-run for baseline disambiguation
- Evidence schema validation
- Exception parsing
- Real blocking exit code

## What this prototype proves for V5

- Validator can be **BMAD-agnostic** (zero BMAD imports — usable from Codex CLI, Cursor, raw shell)
- Validator can run with **stdlib only** (no pip / uv friction for users)
- Router replay can be expressed as data (the inline `ROUTER_RULES` dict in this prototype will become `router-rules.json` in Phase 1.2)
- The shape of the output JSON is the starting point for `rdx-evidence.v1.schema.json` (Phase 1.4)
