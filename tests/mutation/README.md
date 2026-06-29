# L7 — Security / Mutation / Adversarial Tests

Phase 5 + Phase 8 + Phase 9 deliverable.

## Layout

Each subdirectory holds one bypass attempt with its expected detection mechanism.

```
mutation/
├── fake-pass/             # T-L7-FAKE-PASS-001 — manually-written PASS rejected
├── stale-diff-digest/     # T-L7-STALE-DIFF-001 — evidence pinned to old diff
├── wrong-base-sha/        # T-L7-WRONG-BASE-001 — evidence claims wrong base
├── disabled-pack/         # T-L7-DISABLED-PACK-001 — agent omits real pack
├── modified-schema/       # T-L7-MOD-SCHEMA-001 — PR weakens evidence schema
├── modified-validator/    # T-L7-MOD-VALIDATOR-001 — PR rewrites validator to PASS
├── deleted-test/          # T-L7-DEL-TEST-001 — PR removes failing tests
├── approval-reuse/        # T-L7-APPROVAL-REUSE-001 — old approval on new diff
├── oversized-diff/        # T-L7-OVERSIZED-DIFF-001 — DOS-resistance
└── workflow-modified/     # T-L7-WORKFLOW-MOD-001 — PR weakens CI workflow itself
```

## Defense layers proven

Each test demonstrates defense at one or more layers:
- **L2 schema-level** (fake-pass, modified-schema)
- **L6 CI-level** (stale-diff, wrong-base, modified-validator)
- **L8 governance-level** (approval-reuse, workflow-modified)

The test isn't just "did the bypass fail" but "WHICH layer caught it" — important for understanding defense depth.
