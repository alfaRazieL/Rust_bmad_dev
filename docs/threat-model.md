# RDX Threat Model — Phase 9 / Mode 4 (High Assurance)

**Status:** v6 baseline. Authored as the Phase 9 entry-gate deliverable.

This document is the source of truth for which threats RDX defends against
in High Assurance mode, *how* each defence is implemented, and which
threats are explicitly out of scope (with the trigger that would put them
back into scope).

It is the rational basis for two non-obvious Phase 9 decisions:

1. **HMAC-signed evidence is NOT adopted in v6.** §7 explains why and §8
   names the trigger that would reopen the decision.
2. **The conditional implementation tasks in `RDX_IMPLEMENTATION_PLAN_TESTED.md`
   Phase 9** ("signed attestations", "audit trail retention policy", etc.) are
   resolved here per the *demand* test the plan asks for — either marked
   as covered by existing controls, deferred with a documented trigger, or
   reduced to operational guidance.

Cross-references:

- `RDX_VALIDATOR_ARCHITECTURE_VERIFICATION.md` §10 — HMAC architectural decision
- `RDX_TEST_STRATEGY.md` §7 (Option A/B/C) — CI validator-source trust model
- `docs/branch-protection.md` — GitHub-side controls assumed by this model
- `tests/mutation/` — the L7 adversarial suite that operationalises §6

---

## 1. Scope

In scope:

- The RDX validator (`rdx-validator/`) and its contracts (`tests/contracts/`).
- The evidence envelope (`rdx_schema_version: v1`) and the approval envelope
  (`_bmad/rdx/approval.v1.schema.json`).
- The CI gate workflow `.github/workflows/rdx-gate.yml` and the CI runner
  `.github/scripts/rdx-ci-runner.py`.
- The pre-push git hook installed by `rdx-setup --install-hook`.
- The BMAD KB sections shipped by `rdx-setup` (`_bmad/rust-kb/**`) and the
  wrapper skills (`.claude/skills/rdx-*`).
- The specialist-approval config (`_bmad/rdx/approvers.yaml`) and approval
  records (`_bmad/rdx/approvals/<diff_digest>.json`).

Out of scope:

- The host operating system, the host Python interpreter, the host git
  binary. RDX trusts these as Trusted Computing Base.
- GitHub itself (issuance of OIDC tokens, branch-protection enforcement,
  CODEOWNERS routing). RDX delegates these to the platform.
- Compromise of a maintainer's signing keys / GitHub credentials. RDX
  assumes the platform's account-security primitives.
- The correctness of `cargo`, `clippy`, `miri`, etc. RDX captures their
  exit codes and stdout digests; it does not re-implement them.
- The accuracy of LLM-produced Cat-3 *judgments*. RDX treats them as
  advisory unless an authorised human ratifies them.

---

## 2. Assets

| ID | Asset | Why it matters | Where it lives |
|----|-------|----------------|----------------|
| A1 | Validator source | Authoritative verdict producer | `rdx-validator/**` |
| A2 | Contract schemas | Define what "valid evidence" means | `tests/contracts/schemas/**` |
| A3 | Router rules | Determine which packs fire on which diff | `tests/contracts/router-rules.json` |
| A4 | KB rule text | Source of truth for what each rule means | `_bmad/rust-kb/**` and `.claude/skills/rdx-setup/assets/kb-sections/**` |
| A5 | Evidence envelope | Audit trail of every gate decision | per-PR artifact under CI; per-commit on disk locally |
| A6 | Approval records | Specialist sign-off for Cat-4 changes | `_bmad/rdx/approvals/<diff_digest>.json` |
| A7 | Approvers config | Who is allowed to approve what | `_bmad/rdx/approvers.yaml` |
| A8 | Mode declaration | Which enforcement level applies | `_bmad/rdx/config.toml` (project-level) |
| A9 | CI workflow YAML | Defines what CI actually runs | `.github/workflows/rdx-gate.yml` |
| A10 | Branch protection ruleset | Defines what GitHub will not let through | GitHub UI / API; documented in `docs/branch-protection.md` |

---

## 3. Threat actors

| ID | Actor | Capability | Realism |
|----|-------|------------|---------|
| TA-1 | Malicious external contributor | Open PRs from forks; cannot trigger CI with secrets; cannot push to `main` | High (any open-source project sees this) |
| TA-2 | Malicious internal contributor with write to feature branches | Push to non-protected branches; open PRs from same-repo branches | Medium |
| TA-3 | Uncooperative LLM agent | Generates code or evidence; can omit steps, fabricate digests, ignore wrapper-issued instructions | High (per Phase 0 spike — wrapper enforcement is convention) |
| TA-4 | Compromised approver account | Authenticated as a real approver identity but operated by attacker | Low — credential compromise is platform-level (out of TCB) |
| TA-5 | Compromised maintainer account with `admin` on `main` | Can bypass branch protection (if `enforce_admins=false`) and rewrite history | Low — but blast radius is total |
| TA-6 | Supply-chain attacker on PyPI / a transitive dep | Lands code that mutates validator behaviour at runtime | Low for v6 (validator deps pinned) |

TA-5 has the biggest blast radius but is also out of RDX's reach — the only
defence is the operational requirement that `enforce_admins=true` is set
(see `docs/branch-protection.md` §"Required configuration on `main`" item 3).
A compromised admin is, by definition, beyond what a gate inside the repo
can prevent.

---

## 4. Trust boundaries

```
┌────────────────────── PR sandbox (TA-1 / TA-2 controlled) ─────────────────────┐
│                                                                                │
│  Working tree   → contains arbitrary code, schemas, workflows, validator code  │
│  Local hook     → optional; runs validator from PR head                        │
│  Cat-3 LLM      → may be uncooperative (TA-3)                                  │
│                                                                                │
└────────────────────────┬──────────────────────────────────────────────────────┘
                         │
                         │   PR opens
                         ▼
┌────────────────────── CI worker (GitHub-controlled VM) ───────────────────────┐
│                                                                                │
│  github/scripts/rdx-ci-runner.py    ◄── loaded from PR HEAD                    │
│  rdx-validator/**                   ◄── loaded from PR BASE (Option B)         │
│  tests/contracts/**                 ◄── loaded from PR BASE                    │
│  approvals + approvers              ◄── loaded from PR HEAD (but the diff      │
│                                          itself is governance-gated)           │
│                                                                                │
└────────────────────────┬──────────────────────────────────────────────────────┘
                         │
                         │   verdict + evidence
                         ▼
┌────────────────────── GitHub merge gate (platform-controlled) ────────────────┐
│                                                                                │
│  Required check `rdx-gate / validate` must be green                           │
│  CODEOWNERS review on `.github/workflows/**`, `rdx-validator/**`,             │
│  `tests/contracts/**`, `_bmad/rust-kb/**`, `_bmad/rdx/**`                     │
│  enforce_admins = true                                                        │
│                                                                                │
└────────────────────────────────────────────────────────────────────────────────┘
```

The single most load-bearing boundary is **CI loads validator + contracts
from the PR base, not from PR head** (Option B, `RDX_TEST_STRATEGY.md` §7).
This is what makes A1, A2, A3 effectively immutable from inside a PR.

---

## 5. Defence summary

| Defence | Mechanism | Test that proves it |
|---------|-----------|----------------------|
| Evidence cannot be fabricated by the agent | Schema (A2) requires `command` + `exit_code` + `output_digest` for Cat-1 PASS. Re-run by CI confirms. | `tests/mutation/test_l7_fake_pass.py` (T-L7-FAKE-PASS-001) |
| Stale evidence cannot survive a diff change | `diff_digest` is recomputed by CI and compared against the envelope. | `test_l7_stale_diff.py` (T-L7-STALE-DIFF-001) |
| Wrong base claim is rejected | CI ignores the envelope's `base_sha` claim and uses `github.event.pull_request.base.sha`. | `test_l7_wrong_base.py` (T-L7-WRONG-BASE-001) |
| Disabling a router pack from the agent side cannot suppress its rule | Router replay is authoritative; `_load_packs` runs on the CI side from base contracts. | `test_l7_disabled_pack.py` (T-L7-DISABLED-PACK-001) |
| Weakening the schema in a PR has no effect on the verdict | Schema (A2) is loaded by CI from base ref. | `test_l7_mod_schema.py` (T-L7-MOD-SCHEMA-001) |
| Rewriting the validator in a PR has no effect on the verdict | Validator (A1) is loaded by CI from base ref via `--validator-ref`. | `test_l7_mod_validator.py` (T-L7-MOD-VALIDATOR-001) |
| Deleting a test that was previously failing does not erase the regression | Cargo / pytest re-run by CI ignores what the PR removed from the historical set; baseline-failure semantics detect the disappearance as a regression. | `test_l7_del_test.py` (T-L7-DEL-TEST-001) |
| Replaying an old approval against a new diff is rejected | Approval JSON's file name + body must both equal the *current* `diff_digest`. | `test_l7_oversized_diff.py` (for DoS) + Cat-4 approver tests + `test_v6_acc_05.py` (HA suite) cover T-L7-APPROVAL-REUSE-001 |
| A PR that rewrites `rdx-gate.yml` itself cannot weaken CI | Branch protection requires CODEOWNERS review on `.github/workflows/**`. | `test_l7_workflow_mod.py` (T-L7-WORKFLOW-MOD-001) |
| A PR that lowers the project's enforcement mode is caught | `_bmad/rdx/config.toml` lives under the `_bmad/rdx/**` governance pattern; the validator emits APPROVAL_REQUIRED. | `tests/mutation/test_l7_ha_mode_downgrade.py` (T-L7-HA-MODE-DOWNGRADE-001) — Phase 9 new |
| A PR that adds an attacker as a Cat-4 approver is caught | `_bmad/rdx/approvers.yaml` lives under the same governance pattern. | `tests/mutation/test_l7_ha_approvers_forgery.py` (T-L7-HA-APPROVERS-FORGERY-001) — Phase 9 new |
| Specialist approvals cannot be granted by a non-CODEOWNER (off-platform) | `_bmad/rdx/approvals/**` is governance-gated; only governance role can land an approval that targets a governance rule. | T-L8-GOV-001 (existing) + branch protection on `_bmad/rdx/**` |
| Resource-exhaustion DoS via a giant diff | Validator imposes a hard cap on diff bytes; oversized diffs emit `ENVIRONMENT_UNAVAILABLE` (exit 2), CI fails. | `test_l7_oversized_diff.py` (T-L7-OVERSIZED-DIFF-001) |

---

## 6. Bypass-path taxonomy (each row is an L7 test)

These map 1:1 to test files under `tests/mutation/`. The Phase 9 acceptance
test (T-V6-ACC-05) runs the entire set as a black box and asserts 100%
detection.

### V5 baseline (Phase 5)

1. **Fake PASS** — author submits a hand-edited `evidence.json` with `verdict: PASS` but no command evidence. Schema rejects + CI re-run produces authoritative verdict. → T-L7-FAKE-PASS-001.
2. **Stale diff digest** — evidence pinned to last week's diff. CI recomputes digest, mismatch → block. → T-L7-STALE-DIFF-001.
3. **Wrong base SHA** — envelope claims a base that isn't the PR's actual base. CI ignores claim and uses `pull_request.base.sha`. → T-L7-WRONG-BASE-001.
4. **Disabled pack** — agent omits a pack it should have activated; router replay activates it anyway. → T-L7-DISABLED-PACK-001.
5. **Modified schema** — PR weakens `rdx-evidence.v1.schema.json`; CI loads schema from base. → T-L7-MOD-SCHEMA-001.
6. **Modified validator** — PR rewrites validator to always PASS; CI loads validator from base via `--validator-ref`. → T-L7-MOD-VALIDATOR-001.
7. **Deleted test** — PR removes a failing test to "fix" the regression; baseline disambiguation detects the disappearance as a regression. → T-L7-DEL-TEST-001.
8. **Oversized diff** — diff exceeds the validator's hard cap; emits ENVIRONMENT_UNAVAILABLE + exit 2 (DoS-resistant). → T-L7-OVERSIZED-DIFF-001.
9. **Workflow modification** — PR weakens `.github/workflows/rdx-gate.yml`; branch protection on `.github/workflows/**` requires CODEOWNERS review. → T-L7-WORKFLOW-MOD-001.

### V6 Cat-4 (Phase 8)

10. **Approval reuse** — approval pinned to old `diff_digest` is replayed on a new diff. File name binding + body field both check; mismatch → block. → T-L7-APPROVAL-REUSE-001.

### V6 HA-specific (Phase 9 — new)

11. **Mode downgrade** — PR rewrites `_bmad/rdx/config.toml` from MODE_4 → MODE_3 (or removes the file). `_bmad/rdx/**` governance pattern in `approvers.yaml.example` requires GOV-RDX-001 approval. → **T-L7-HA-MODE-DOWNGRADE-001**.
12. **Approvers forgery** — PR appends an attacker identity to `roles.unsafe-reviewers.identities` in `_bmad/rdx/approvers.yaml`. Same `_bmad/rdx/**` governance pattern catches it. → **T-L7-HA-APPROVERS-FORGERY-001**.

---

## 7. Why no HMAC in v6

The previous design report (`RDX_VALIDATOR_ARCHITECTURE_VERIFICATION.md` §10)
recommended **no HMAC** in v1; this section restates and updates that
recommendation for v6 in the form a Phase 9 threat model demands.

**Claim:** HMAC-signed evidence adds no marginal trust to RDX as long as the
CI workflow independently re-runs Cat-1 checks and recomputes deterministic
verdicts from the diff.

**Why the claim holds:**

- CI loads validator + contracts from the PR base (Option B). The verdict
  CI produces is a pure function of `(diff, base-validator, base-contracts,
  base-KB)`. Nothing the agent or PR author signs can change that function's
  output.
- For Cat-3 LLM judgments — which CI cannot re-run authoritatively — the
  cache key is `(diff_digest, kb_digest, rule_id)`. A miss triggers a fresh
  judgment; a hit is accepted only when the cache entry's digest fields
  match the current diff. HMAC adds nothing here; the digest binding is
  what makes the cache safe to consult.
- For Cat-4 approvals, the approval JSON's file name *is* the
  `diff_digest`. The body's `diff_digest` field is also checked against
  the actual diff. Two independent comparisons + the GitHub commit
  history that records *who* added the file. HMAC would add a third
  comparison whose key would itself become a new asset to protect.
- The cost of HMAC is non-trivial: key rotation, fork-PR secret access
  (forked PRs receive no secrets), OSS-contributor onboarding friction,
  rebind on key compromise.

**What the claim assumes (and the test that proves it):**

- The CI workflow *does* re-run from base. Tested by T-L7-MOD-VALIDATOR-001
  and T-L7-MOD-SCHEMA-001.
- The CI workflow YAML itself cannot be silently rewritten. Tested by
  T-L7-WORKFLOW-MOD-001 + governance on `.github/workflows/**`.
- The approval JSON's binding cannot be replayed across diffs. Tested by
  T-L7-APPROVAL-REUSE-001.

If any one of these three assumptions stops holding, the HMAC decision
should be revisited.

---

## 8. Triggers to revisit (decisions deferred, not abandoned)

Phase 9's "implementation tasks (only if real demand exists)" each map to a
trigger here. If the trigger fires, open a follow-up phase.

| Phase 9 task | Decision (v6) | Trigger to revisit |
|--------------|----------------|---------------------|
| Signed attestations (HMAC) | **Not adopted** (§7) | A real bypass shows that CI's re-run is circumventable in some environment (e.g., reusable workflow used cross-org where validator-ref is honoured but base contracts are not loaded). |
| Protected validator source (immutable release tag — Option C) | **Already supported, opt-in** (`--validator-ref` accepts any git ref). Operational guidance: pass a tag for HA. | RDX ships a 1.0 release tag; document migration from Option B to Option C in the README. |
| Provenance evidence | **Already present** — every envelope carries `validator.source` (`PR_HEAD` / `BASE` / `<git-ref>`), `head_sha`, `base_sha`, `kb_digest`, `diff_digest`. | Auditors request SLSA-style attestations that go beyond what the envelope already records. |
| Audit trail retention policy | **Operational, not code** — recommend uploading the evidence envelope as a CI artifact with default `actions/upload-artifact` retention (90 days), and storing a digest of the envelope in a long-lived audit log. | Industry-specific retention requirement (e.g., financial 7-year) — adopt an external log sink. |
| Organization-level required workflows documentation | **Operational, documented in `docs/branch-protection.md`** plus the README CI sections (Phase 10). | RDX gets adopted at organization scale and a single repo's branch-protection page is no longer the right governance surface. |

---

## 9. Residual risk register

| ID | Risk | Severity | Mitigation in v6 | Why we accept it |
|----|------|----------|-------------------|-------------------|
| R-1 | Admin with `enforce_admins=false` bypasses every defence | Total | Documented requirement (`docs/branch-protection.md` §3) to set `enforce_admins=true`; periodic check via `gh api`. | Out of RDX's control; ultimately platform policy. |
| R-2 | Cat-3 LLM judgments are non-deterministic | Medium | Cached per `(diff_digest, kb_digest, rule_id)`; auditor can re-issue; CI does not block on Cat-3 in Mode 3. | Cost-benefit: re-running a fresh judgment on every PR is expensive. |
| R-3 | A fork PR cannot run Cat-3 in the blocking workflow (no secrets) | Low | Cat-3 runs in a separate `workflow_run`-triggered job. Fork PRs from external contributors get human review for Cat-3. | GitHub-imposed; deliberately. |
| R-4 | Pre-push hook is bypassable via `git push --no-verify` | Low | Bypass is recorded as a row in the evidence/hook log; documented in `RDX_TEST_STRATEGY.md` §10. Mode 2 alone is not sufficient for HA; pair with Mode 3. | Hooks are local; the documented bypass is part of the contract. |
| R-5 | Supply-chain compromise of a validator Python dep | Low | Pinned deps; CI runs in a clean ubuntu-latest with `permissions: contents: read`; no secrets passed. | Standard supply-chain hygiene; not RDX-specific. |
| R-6 | A Cat-4 approver has their account compromised | Low (per actor) | Platform 2FA / SSO; CODEOWNERS approval requires the GitHub identity, not just a typed email. | Account security is platform-level. |
| R-7 | A determined attacker rewrites history on `main` (TA-5) | Total | `lock_branch` + `enforce_admins=true` + signed commits recommended (`docs/branch-protection.md` §6). | If admin is compromised, the repo is already lost. |

---

## 10. HA mode operational checklist

A project claiming Mode 4 (High Assurance) must operationally guarantee:

1. **Branch protection on `main` per `docs/branch-protection.md`** —
   including `enforce_admins=true` and CODEOWNERS reviews on the protected
   path set, which for HA includes `_bmad/rdx/**` and `_bmad/rust-kb/**`.
2. **`_bmad/rdx/approvers.yaml`** populated for the project's actual risk
   surface and routed via `.github/CODEOWNERS` (regenerated by
   `rdx-setup sync-codeowners`).
3. **`_bmad/rdx/config.toml`** declares `mode = "MODE_4"`. This file is
   under `_bmad/rdx/**`, so changes require governance approval.
4. **The CI gate workflow loads validator from a pinned ref** — either
   the PR base (Option B, default) or a tagged RDX release (Option C).
   Document the choice in the repo README.
5. **Cat-3 LLM judgments are cached and human-ratifiable** — the auditor
   skill (`rdx-judgment`) emits findings against the
   `rdx-judgment-finding.v1` schema; a CODEOWNER for the affected path
   ratifies non-trivial findings before merge.
6. **Evidence envelopes are uploaded as CI artifacts** with the
   organisation's retention policy applied.
7. **The threat model in this file is reviewed annually** and on any
   security-relevant infrastructure change (new CI provider, new identity
   system, organisation move).

---

## 11. Phase 9 acceptance gate (T-V6-ACC-05)

Acceptance: the full L7 mutation suite (§6 — V5 baseline + Phase 8
Cat-4 + Phase 9 HA-specific) must run green when collected as a single
pytest run. The driver is `tests/acceptance/ha-adversarial-suite/`. A
failing module is a release-blocker for RDX 1.5.

The acceptance test does not re-implement the bypass attempts; it runs
the canonical modules under `tests/mutation/` so a single bypass class
is described in exactly one place.
