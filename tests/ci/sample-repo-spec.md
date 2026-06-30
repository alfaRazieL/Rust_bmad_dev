# Sample Repo Specification — Phase 5 L6 / L7

This document defines how the Phase 5 end-to-end fixtures are constructed.
It is the single source of truth so the L6 / L7 tests, the pre-push hook
installer, and the CI workflow stay in sync.

Two flavours of sample repository exist, both materialised at test time
in a temp dir (no permanent committed clone in this repo to keep CI fast
and reproducible):

1. **Local hook fixture** (`sample-repo-hook`)
   - Real `git init` repo + bare `git init --bare` remote on the same
     temp dir.
   - The pre-push hook installed by `rdx-hooks/scripts/install-hook.py`.
   - Used by `T-L6-HOOK-001..005`.

2. **Simulated GitHub repo** (`sample-github-repo` / `trusted-source-tests`)
   - Real `git init` repo with two branches: `main` (base) and `pr-head`.
   - The `rdx-ci-runner.py` script is invoked exactly as the
     `.github/workflows/rdx-gate.yml` workflow would invoke it, but
     locally — no GitHub Actions runtime is required.
   - Option B trust model is enforced by the runner: it pulls
     validator code, schema, and contracts from the **base** ref via
     `git show <ref>:<path>`, not from PR head files.
   - Used by `T-L6-CI-001..005`, `T-V5-ACC-05`, `T-L7-MOD-SCHEMA-001`,
     `T-L7-MOD-VALIDATOR-001`.

## Sample repo files

Every sample repo contains, on `main`:

- `Cargo.toml` (minimal — `[package] name = "demo" version = "0.0.0"`)
- `src/lib.rs` (empty `pub fn`)
- `src/auth/login.rs` (protected-file fixture for CORE-007 tests)
- `STORY.json` — story contract describing protected files + activated packs

The PR head branch (`pr-head`) carries the change under test.

## Branch protection (T-L7-WORKFLOW-MOD-001)

Branch protection is configured at the GitHub UI level (cannot be
expressed in repo code). The L7 test verifies that
`docs/branch-protection.md` documents the required rules:

1. PRs touching `.github/workflows/**` require a CODEOWNERS reviewer.
2. The required status check is `rdx-gate / validate` from
   `rdx-gate.yml` on the **target branch**.
3. Pull requests run with `permissions: contents: read` only (no
   `id-token`, no secrets) so fork PRs are safe by default
   (T-L6-CI-003).

## Secrets (intentionally empty for Phase 5)

No secrets are required for Cat-1 / Cat-2 verification. The workflow
runs `python -m pytest` and `rdx-ci-runner.py` only.

## Fixture lifecycle

Sample repos are created with `tmp_path` per-test and torn down by
pytest. The helpers live in `tests/ci/conftest.py`. No state leaks
between tests.
