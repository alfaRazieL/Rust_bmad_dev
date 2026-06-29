# Fixtures

All test inputs (diffs, Cargo projects, stories, evidence, approvals).

## Layout

```
fixtures/
├── diffs/              # per-pack diff fixtures (L2)
│   ├── async/          # ... per-pack subdirs
│   ├── unsafe/
│   ├── ffi/
│   ├── macro/
│   ├── api/
│   ├── cargo/
│   ├── test-pack/
│   ├── data/
│   ├── db/
│   ├── time/
│   ├── ops/
│   ├── perf/
│   ├── core-007/       # per-CORE-rule subdirs (L2)
│   ├── core-008/
│   ├── core-014/
│   ├── core-015/
│   ├── baseline/       # T-L1-BASE-* fixtures
│   └── digest-whitespace-pair/
├── cargo-projects/     # full minimal crates (L3)
├── stories/            # synthetic BMAD story files (L4)
├── evidence/           # synthetic evidence.json files (L1/L2/L7)
└── approvals/          # synthetic Cat-4 approvals (L8)
```

## Naming convention

- `positive-*` → expected to activate / FAIL
- `negative-*` → expected NOT to activate / PASS
- `ambiguous-*` → expected REVIEW_REQUIRED or STORY_TAG_REQUIRED
- Each `*.diff` (or `.json`) MUST have a sibling `.expected.json` with the canonical expected verdict

Example:
```
diffs/unsafe/positive-new-unsafe-block.diff
diffs/unsafe/positive-new-unsafe-block.expected.json
```

## What's already here

From Phase 0.3 spike, four diffs copied for reuse:

- `diffs/async/positive-tokio-spawn.diff` (TODO: rename from spike fixture)
- `diffs/async/negative-doc-only.diff`
- `diffs/unsafe/positive-new-unsafe-block.diff`
- `diffs/cargo/positive-add-dep.diff`

All other fixtures TBD per the Phase 2 entry-gate checklist in `RDX_IMPLEMENTATION_PLAN_TESTED.md`.
