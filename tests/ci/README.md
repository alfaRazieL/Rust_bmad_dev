# L6 — Hook + CI End-to-End Tests

Phase 5 deliverable.

## Layout

```
ci/
├── sample-repo-hook/        # T-L6-HOOK-001..005 — local pre-push behavior
├── sample-github-repo/      # T-L6-CI-001 — real GitHub Actions required check
├── trusted-source-tests/    # T-L6-CI-002 — validator loaded from base, not PR head
├── fork-pr-simulation/      # T-L6-CI-003 — workflow without secrets
├── baseline-regression/     # T-L6-CI-004 — dual-run baseline disambiguation in CI
└── stale-evidence-pr/       # T-L6-CI-005 — diff_digest mismatch rejection
```

## Sample repo plan

A separate, dedicated GitHub repo is provisioned for end-to-end tests (NOT this main RDX repo). The repo specification lives in `sample-repo-spec.md` and lists:
- Branch protection setup
- Required status check name
- Secrets configuration (intentionally minimal for fork-PR-safety tests)
- Initial commits / fixture setup

## What's tested at CI level vs locally

| Test | Local hook | GitHub CI |
|------|-----------|-----------|
| Hook blocks invalid push | ✓ (full) | n/a |
| Required check blocks invalid PR | n/a | ✓ (full) |
| Trusted source (PR can't tamper) | n/a | ✓ (only meaningful in CI) |
| Fork PR safety | n/a | ✓ |
| Dual-run baseline | possible locally | ✓ authoritative |
