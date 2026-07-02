# L7 — Security / Mutation / Adversarial Tests

Phase 5 + Phase 8 + Phase 9 deliverable.

## Layout

Each subdirectory holds one bypass attempt with its expected detection mechanism.

```
mutation/
├── fake-pass/                          # T-L7-FAKE-PASS-001
├── stale-diff-digest/                  # T-L7-STALE-DIFF-001
├── wrong-base-sha/                     # T-L7-WRONG-BASE-001
├── disabled-pack/                      # T-L7-DISABLED-PACK-001
├── modified-schema/                    # T-L7-MOD-SCHEMA-001
├── modified-validator/                 # T-L7-MOD-VALIDATOR-001
├── deleted-test/                       # T-L7-DEL-TEST-001
├── approval-reuse/                     # T-L7-APPROVAL-REUSE-001 (driver in tests/integration/cat4/)
├── oversized-diff/                     # T-L7-OVERSIZED-DIFF-001 — DOS-resistance
├── workflow-modified/                  # T-L7-WORKFLOW-MOD-001 — PR weakens CI workflow itself
├── test_l7_ha_mode_downgrade.py        # T-L7-HA-MODE-DOWNGRADE-001 — Phase 9 HA-specific
└── test_l7_ha_approvers_forgery.py     # T-L7-HA-APPROVERS-FORGERY-001 — Phase 9 HA-specific
```

## Defense layers proven

Each test demonstrates defense at one or more layers:
- **L2 schema-level** (fake-pass, modified-schema)
- **L6 CI-level** (stale-diff, wrong-base, modified-validator)
- **L8 governance-level** (approval-reuse, workflow-modified, ha-mode-downgrade, ha-approvers-forgery)

The test isn't just "did the bypass fail" but "WHICH layer caught it" — important for understanding defense depth.

## Acceptance drivers

- Phase 6 V5 release gate: `test_l7_full_suite.py` — V5 L7 bypass map.
- Phase 9 HA release gate: `tests/acceptance/ha-adversarial-suite/test_v6_acc_05.py` (T-V6-ACC-05) — runs this whole directory as a subprocess and asserts the catalogue of V6 HA-specific modules is in sync with `RDX_TEST_CASES.yaml`. See `docs/threat-model.md` §6 for the threat-model rationale tying each module to a defence layer.
