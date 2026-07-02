# Branch Protection Setup — Phase 5 / Mode 3

This file documents the GitHub branch-protection configuration that
turns `rdx-gate.yml` into an actual enforcement boundary. Branch
protection is a GitHub-side setting; it cannot be expressed in repo
code, so this document is the source of truth for what an admin must
configure manually.

Without these settings, `rdx-gate.yml` only **reports** verdicts — it
does not block merges.

## Required configuration on `main`

Set the following at **Settings → Branches → Branch protection rules →
main**:

1. **Require status checks to pass before merging**
   - Required check: `rdx-gate / validate` (from
     `.github/workflows/rdx-gate.yml` on the target branch).
   - **Strict** — branches must be up to date before merging.
2. **Require pull request reviews before merging**
   - At least 1 approving review.
   - **CODEOWNERS review required** for changes to:
     - `.github/workflows/**` (T-L7-WORKFLOW-MOD-001)
     - `rdx-validator/**`
     - `tests/contracts/**`
     - `_bmad/rust-kb/**`
     - `.claude/skills/rdx-*/**`
3. **Do not allow bypassing the above settings.** Admins included.
4. **Restrict who can push to matching branches.** No direct pushes
   to `main` — everything goes through a PR.
5. **Require signed commits.** Optional but recommended for tamper
   evidence.
6. **Lock branch** for force-push protection.

## CODEOWNERS file

Maintain `.github/CODEOWNERS` so the rules above are routed
automatically:

```text
# Workflow + CI runner — must be reviewed by RDX maintainers (T-L7-WORKFLOW-MOD-001)
/.github/workflows/        @YOUR-ORG/rdx-maintainers
/.github/scripts/          @YOUR-ORG/rdx-maintainers

# Validator + contracts — governance
/rdx-validator/            @YOUR-ORG/rdx-maintainers
/tests/contracts/          @YOUR-ORG/rdx-maintainers
/_bmad/rust-kb/            @YOUR-ORG/rdx-maintainers

# RDX skills
/.claude/skills/rdx-       @YOUR-ORG/rdx-maintainers
```

(Replace `@YOUR-ORG/rdx-maintainers` with your actual GitHub team.)

## Why this matters

The `rdx-gate.yml` workflow uses Option B (validator loaded from the
PR base, not PR head) so a malicious PR cannot weaken the validator
itself. But a PR could rewrite the workflow file itself to skip the
validator — `pull_request`-triggered workflows in GitHub Actions
execute the PR head's workflow YAML, not the base's.

The defence against that is **branch protection requiring a
CODEOWNERS review for any `.github/workflows/**` change**. Without
this rule, the trust chain has a hole.

## Verifying the configuration

```bash
gh api repos/$OWNER/$REPO/branches/main/protection | jq '
  {
    enforce_admins: .enforce_admins.enabled,
    required_reviews: .required_pull_request_reviews,
    required_checks: .required_status_checks.contexts,
    restrictions: .restrictions
  }'
```

Expected:

- `enforce_admins.enabled = true`
- `required_pull_request_reviews.require_code_owner_reviews = true`
- `required_status_checks.contexts` includes `"rdx-gate / validate"`

## Reference

- Trust model: `RDX_TEST_STRATEGY.md` §7 (Option B)
- Workflow: `.github/workflows/rdx-gate.yml`
- Workflow-modification test: `tests/mutation/test_l7_workflow_mod.py`
  (T-L7-WORKFLOW-MOD-001)
