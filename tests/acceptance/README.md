# Acceptance Suites

Release-gating tests. **The release manager runs these before publishing a tagged version.**

## Layout

```
acceptance/
├── v5-acceptance.md           # checklist for T-V5-ACC-01..07
├── v6-acceptance.md           # checklist for T-V6-ACC-01..05
├── standalone-no-bmad/        # T-V5-ACC-01
├── all-pack-positives/        # T-V5-ACC-02
├── weak-signals-no-tag/       # T-V5-ACC-03
├── authority-matrix-coverage/ # T-V5-ACC-04
├── doc-honesty/               # T-V5-ACC-06
├── kb-no-regression/          # T-V5-ACC-07
├── v5-regression-pack/        # T-V6-ACC-01 (re-runs V5 suite)
├── cat3-flow/                 # T-V6-ACC-02
├── cr-r2-integration/         # T-V6-ACC-03
├── cat4-flow/                 # T-V6-ACC-04
└── ha-adversarial-suite/      # T-V6-ACC-05
```

## Release process

1. Bump version in `marketplace.json` and `module.yaml`
2. Run full acceptance suite for the target version (V5 OR V6)
3. All tests must pass with no flakes in 3 consecutive runs
4. Tag release; push tag; create GitHub release
5. Acceptance suite log archived to `acceptance/runs/v<version>-<date>.log`

## What an acceptance test is NOT

- Not a unit test (those live in `unit/`)
- Not a re-run of fixtures (those live in `integration/`)
- Acceptance tests are **black-box** — they exercise RDX as a user would (install → use → uninstall)
