# RDX Documentation Review Checklist (Phase 10 entry-gate)

Before tagging an RDX release, walk this list and tick each item. The
list mirrors `RDX_IMPLEMENTATION_PLAN_TESTED.md` Phase 10 §
Implementation tasks; reviewer checks should map 1:1 to that section.

This file is consumed by `tests/docs/test_l4_doc_review_checklist.py`,
so adding or renaming items here means updating the test in the same
commit.

## Architecture and behavior

- [ ] **architecture overview** — README explains validator → wrapper → hook → CI stack and how Cat-1/2/3/4 categories flow through it.
- [ ] **mode comparison** — README enumerates Mode 0/1/2/3/4 with a "what enforces what" matrix and the canonical labels Advisory / Local Validated / Local Gated / CI Enforced / Specialist Approval.
- [ ] **status semantics** — README documents PASS / FAIL / REVIEW_REQUIRED / APPROVAL_REQUIRED and the exit-code taxonomy (0/1/2/3/4) per `RDX_TEST_STRATEGY.md` §5.
- [ ] **evidence schema** — README references `tests/contracts/schemas/rdx-evidence.v1.schema.json` and explains what a verdict envelope contains.
- [ ] **exception model** — README describes the policy exception mechanism and how the validator scopes it.

## Install / update / uninstall / CI / hooks

- [ ] **installation** — README has a working install path that points at `/rdx-setup` and `_bmad/config.yaml` registration.
- [ ] **update** — README walks the upgrade path from RDX 1.0 → 1.x.
- [ ] **uninstall** — README documents `rdx-setup` uninstall + hook removal.
- [ ] **hook behavior** — README explains the pre-push hook's role.
- [ ] **--no-verify** — README documents `git push --no-verify` as the recorded bypass.
- [ ] **CI setup** — README explains `rdx-gate.yml`, the validator-from-base-branch loading model, and how to mark the workflow as a required check.

## Review / approvals / docs hygiene

- [ ] **review integration** — README describes the `rdx-code-review` wrapper and the `rdx-judgment` Cat-3 evaluator.
- [ ] **specialist approvals** — README documents the A3 + B1 Cat-4 flow (`_bmad/rdx/approvers.yaml`, `_bmad/rdx/approvals/<digest>.json`, generated CODEOWNERS).
- [ ] **troubleshooting** — README contains a troubleshooting section covering common validator / hook / wrapper failures.
- [ ] **compatibility matrix** — README links `tests/compatibility/matrix.md`.
- [ ] **limitations** — README enumerates current limitations (Windows native, web-only Claude, non-Claude CLIs, etc.).

## Public positioning (T-V5-ACC-06)

- [ ] RDX does NOT prove correctness of all Rust decisions.
- [ ] Cat-1 is deterministic.
- [ ] Cat-2 verifies evidence.
- [ ] Cat-3 is judgment review.
- [ ] Cat-4 requires approval.
- [ ] CI is the source of enforcement.
- [ ] Wrapper is workflow UX (NOT a programmatic boundary).

## CI cost (Phase 10 locked 2026-06-30)

- [ ] "Using RDX with GitHub Actions Free plan" subsection present with 2,000-min budget, owner aggregation, typical 5–15 min/PR, Mode 2 no-CI fallback, numbered rdx-gate.yml setup.
- [ ] "When you need more than 2,000 minutes — switching to paid" subsection present with Pro/Team/Enterprise comparison, self-hosted runners, organization-move walkthrough, and cost-calculator hint.

## Mode 2 framing

- [ ] Mode 2 (Local Gated) is positioned as a release-quality option in its own right.
- [ ] No text frames Mode 2 as a "stepping stone" to Mode 3 (negated form "not a stepping stone" is permitted).
