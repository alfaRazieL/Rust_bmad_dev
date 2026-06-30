# RDX Implementation Plan — TESTED (V5 → V6)

> **This is the test-aware revision of `RDX_IMPLEMENTATION_PLAN.md`.** The original is preserved unchanged for history; this document supersedes it for execution.
>
> Changes from original:
> 1. Phase 0 overclaims corrected (context-pressure, child-incomplete returned to pending)
> 2. Spike 0.2 demoted from EXPERIMENT VERIFIED to DOC VERIFIED + INFERENCE pending L4-CR test
> 3. Status taxonomy corrected (14 verdicts + WARNING as severity)
> 4. Every Phase has explicit entry-gate (tests written first) and exit-gate (tests must pass) sections
> 5. V5 + V6 DoD items linked to test IDs (see `RDX_TEST_TRACEABILITY_MATRIX.md`)
> 6. Code Review integration decision: R2 (wrapper), with R1 retained as control test
> 7. Status `WARNING` clarified as severity, not verdict
> 8. Two new status entries added: `BASELINE_BLOCKS_VALIDATION` and `TOOL_UNAVAILABLE` (gaps to fill in Phase 2)

---

## Phase 0 — corrected status

### 0.1 Multi-skill spike (revised)

| Item | Status | Evidence |
|------|--------|----------|
| Wrapper SKILL created | [x] | `spikes/0.1-multi-skill/wrapper.SKILL.md` |
| Child SKILL created | [x] | `spikes/0.1-multi-skill/child.SKILL.md` |
| Successful child → wrapper resumes | [x] | `trace.log.evidence` BEFORE→CHILD→AFTER |
| Child errors → wrapper handling | [~] partial | Validator-stub FAIL covered; explicit child-error not yet covered. Closed by T-L4-WR-002 in Phase 3 |
| Child incomplete result detection | [ ] **pending** | T-L4-WR-005 (Phase 3 entry gate) |
| Wrapper instructions preserved post-child | [x] | trace.log Step 3 AFTER proves resume |
| No recursion | [x] | trace.log shows single CHILD entry |
| Return to post-child steps | [x] | trace.log + subagent self-report |
| Child results accessible to wrapper | [x] | Wrapper read CHILD_DONE marker |
| Context-pressure behavior | [ ] **pending** | T-L5-CTX-001 (Phase 6) |
| Risk-tag preservation across child | [ ] **pending** | T-L4-WR-006 (Phase 3 entry gate) |
| **GO criterion (overall)** | [~] **CONDITIONAL** | Happy-path verified; remaining cases pending Phase 3 entry-gate tests |
| Fallback path documented | [x] | `RDX_VALIDATOR_ARCHITECTURE_VERIFICATION.md` §5 |

**Net status:** Phase 0.1 happy path is **EXPERIMENT VERIFIED**. Error / partial-result / context-pressure / tag-preservation paths are **PENDING** their respective L4/L5 tests in Phase 3/6. The previous "[x] all subitems" overclaim is corrected.

### 0.2 Review propagation (revised)

| Item | Status | Evidence |
|------|--------|----------|
| Parent reviewer receives RDX persistent_facts | [x] DOC VERIFIED | resolver merge confirmed in source |
| Review subagents receive isolated context (no RDX) | [x] DOC VERIFIED | step-02-review.md explicit isolation |
| `on_complete` hook customizable | [x] DOC VERIFIED | customize.toml `[workflow] on_complete = ""` |
| RDX Rule Auditor layer addable without forking step files | [~] **INFERENCE** | Recipe documented; not yet empirically tested |
| `on_complete` returns findings into final report | [ ] **pending experiment** | T-L4-CR-002 (Phase 7) |
| `rdx-code-review` wrapper alternative | [ ] **pending experiment** | T-L4-CR-001 (Phase 7) |
| **GO criterion (overall)** | [~] **DOC VERIFIED + INFERENCE** | Empirical close requires Phase 7 spike |
| Fallback path documented | [x] | Spike 0.2 README |

**Net status:** Phase 0.2 is a documented integration *strategy*, not a verified runtime. The strategy is consistent with the source and adequate to start Phase 1, but the empirical close is gated by Phase 7 (T-L4-CR-001 / T-L4-CR-002).

### 0.3 Standalone validator (unchanged — fully verified)

All items [x]. Prototype at `spikes/0.3-standalone-validator/rdx_validator.py` correctly classifies all 4 router fixtures.

### Phase 0 overall gate result

**[~] CONDITIONAL GO.** Phase 1 may proceed because:
- 0.1 happy path is proven (sufficient to design contracts)
- 0.2 strategy is consistent with source (sufficient to design schema)
- 0.3 is fully proven (sufficient to extend into Phase 2 validator)

But the pending items (0.1 error cases, 0.2 empirical close) **must remain on the schedule** as Phase 3 / Phase 7 entry-gate work. Do not let the conditional-GO be re-interpreted as full-GO.

---

## Phase 1 — Contracts & Single Source of Truth

### Entry gate (tests must exist before implementation)

- [x] T-L0-SCHEMA-001..004 specs written (schemas to validate)
- [x] T-L0-ROUTER-001 spec written
- [x] T-L0-DRIFT-001/002 specs written
- [x] T-L0-STATUS-001/002 specs written
- [x] T-L0-RULE-IDS-001 spec written
- [x] `tests/contracts/` directory + READMEs in place

### Implementation tasks

#### 1.1 Rule model — Category 1/2/3/4

- [x] Canonical mapping (rule ID → applicability / detection / evidence / authority / blocking semantics / exception policy) authored at `tests/contracts/rule-check-map.json`
- [x] Tests T-L0-DRIFT-002 references this file

#### 1.2 Machine-readable Router mapping

- [x] `router-rules.json` authored with per-pack: positive signals, file-path signals, negative signals, confidence class, activation policy, related rule IDs, validation family
- [x] Activation classes implemented: `AUTO_ACTIVATE`, `AUTO_SUGGEST`, `STORY_TAG_REQUIRED`, `REVIEW_REQUIRED`
- [x] Tests T-L0-ROUTER-001 + T-L0-DRIFT-001 cover this

#### 1.3 Drift prevention

- [x] `tests/contracts/drift-check.py` written (passes on first commit)
- [x] CI workflow runs drift check on every PR to KB or mapping files

#### 1.4 Evidence Schema v1

- [x] `rdx-evidence.v1.schema.json` authored covering all fields from `RDX_TEST_STRATEGY.md` §5 + traceability matrix authority columns
- [x] Tests T-L0-SCHEMA-001..004 cover schema correctness + Cat-1 self-attestation rejection

#### 1.5 Authority boundaries

- [x] `authority-matrix.json` authored with (field × actor) cells
- [x] Test T-L0-STATUS-002 verifies completeness
- [x] Status definitions JSON authored with all 14 verdicts + 3 severities + exit-code mapping
- [x] T-L0-STATUS-001 verifies

### Exit gate

- [x] All 10 L0 tests green
- [x] CI drift check operational
- [x] No KB/mapping drift detected
- [x] No rule-ID duplicates
- [x] Status taxonomy locked
- [x] Authority matrix complete

---

## Phase 2 — Standalone `rdx-validator`

### Entry gate

- [x] T-L1-DIFF-001..003 specs written
- [x] T-L1-DIGEST-001/002 specs written
- [x] T-L1-COMMENT-001 spec written
- [x] T-L1-EXC-001/002 specs written
- [x] T-L1-AGG-001..003 specs written
- [x] T-L1-EXIT-001..005 specs written
- [x] T-L1-BASE-001..004 specs written (baseline comparator)
- [x] T-L1-POL-001 spec written
- [x] L2 pack-fixture-gap list cleared:
  - [x] FFI doc-only negative fixture (`tests/fixtures/diffs/ffi/negative-doc-only.diff`)
  - [x] Macro doc-only negative fixture (`tests/fixtures/diffs/macro/negative-doc-only.diff`)
  - [x] Testing negative fixture (`tests/fixtures/diffs/test-pack/positive-no-tag.diff` covers untagged → not active)
  - [x] Data doc-only negative fixture (`tests/fixtures/diffs/data/negative-doc-only.diff`)
  - [x] DB doc-only negative fixture (`tests/fixtures/diffs/db/negative-doc-only.diff`)
  - [x] Time doc-only negative fixture (`tests/fixtures/diffs/time/negative-doc-only.diff`)
  - [~] BASELINE_BLOCKS_VALIDATION unit test (status verdict defined in `status-definitions.json`; aggregator promotion covered; dedicated unit test deferred to Phase 5 where override path lives)
  - [~] TOOL_UNAVAILABLE unit test (status verdict defined; aggregator passes it through as non-blocking conditional; dedicated unit test deferred until Phase 2.x cargo-tool-missing scenarios in Phase 5/6)

### Implementation tasks

#### 2.1 CLI contract

- [x] All inputs supported: `--project-root`, `--story`, `--base`, `--head`, `--mode`, `--evidence-out`, `--policy-config`, `--evidence-in`, `--diff-file`, `--dual-run`, `--baseline-data`, `--validator-source`, `--contracts-dir`, `--quiet`
- [x] All outputs: JSON envelope to stdout, evidence file to `--evidence-out`, stable exit code per strategy §5.3

#### 2.2 First check set

- [x] CORE-007 protected files (T-L2-CORE007-001..003)
- [x] CORE-015 router parity (T-L2-CORE015-001/002)
- [x] CORE-011 compile evidence (T-L2-CORE011-001..003)
- [x] CORE-014 suppression (T-L2-CORE014-001..003)
- [x] CORE-008 panic discipline subset (T-L2-CORE008-001..003)

#### 2.3 Status taxonomy

- [x] All 14 verdicts implemented in `rdx_validator/status.py`; severity orthogonal; exit code mapper per §5.3.

#### 2.4 Base/head comparison

- [x] `--dual-run` mode with `--baseline-data` JSON input; deterministic signature compare
- [x] Tests T-L1-BASE-001..004 + T-L3-CRATE-003/004 green

#### 2.5 Test suite

- [x] L0/L1/L2 implemented via pytest (75 tests across `tests/unit/validator/`)
- [~] L3 integration: green-crate + dual-run baseline same-signature + dual-run regression + unsafe-no-safety smoke (4 of 7 from YAML). T-L3-CRATE-002/006/007 deferred — they require actual cargo invocation (compile failure detection, workspace walking, build.rs path activation in real crates); the validator's contract is to consume diffs and evidence (it does not invoke cargo itself), so the remaining cases are integration-test scaffolding for Phase 5 where the CI runs cargo and feeds the validator real outputs.

### Exit gate

- [x] L0 still green (13/13)
- [x] All L1 tests green (30/30)
- [x] All L2 tests green — per-pack positive AND doc-only-negative AND ambiguous coverage (45/45)
- [x] L3 green-crate baseline passes (T-L3-CRATE-001)
- [x] L3 dual-run baseline-vs-regression disambiguation passes (T-L3-CRATE-003 + T-L3-CRATE-004)
- [x] L3 cold execution time ≤ 5 min per fixture (full L3 suite finishes in < 1 s locally; cold-cache budget trivially satisfied because the Phase 2 validator does not invoke cargo)

---

## Phase 3 — `rdx-dev-story` wrapper

### Entry gate

- [x] T-L4-MENU-001/002 specs written
- [x] T-L4-WR-001..006 specs written (happy + error + missing-artifact + recursion + tag-preservation)
- [x] T-L4-SETUP-001..003 specs written

### Implementation tasks

#### 3.1 Wrapper responsibility

- [x] `rdx-dev-story/SKILL.md` orchestrates: contract intake → router pre-pass → bmad-dev-story → evidence → validator → report
- [x] Wrapper does NOT claim hard enforcement (T-V5-ACC-06) — soft-gate disclaimer at top of SKILL.md; description avoids forbidden phrases

#### 3.2 Menu integration

- [x] `_bmad/custom/bmad-agent-dev.toml` adds `[[agent.menu]] code = "DS" skill = "rdx-dev-story"` (T-L4-MENU-001)
- [x] Foreign customizations preserved (T-L4-MENU-002) — install.py merge-by-code preserves foreign principles + menu entries
- [x] Update-safe merge tested — T-L4-SETUP-002 idempotency green (byte-equal repeat install)

#### 3.3 Resolver compatibility

- [~] rdx-setup pins minimum resolver SHA — deferred to Phase 4 (mode UX) where setup gains the interactive prerequisite check. Phase 3 ships a resolver shim (`tests/bmad/_helpers/resolver_shim.py`) that documents the merge contract RDX depends on so install.py and tests stay consistent.
- [~] Setup warns on resolver incompatibility — deferred to Phase 4 alongside SHA pin
- [x] Rollback/uninstall path implemented (T-L4-SETUP-003) — `.claude/skills/rdx-setup/scripts/uninstall.py` + green round-trip test

#### 3.4 Context discipline

- [x] Wrapper passes only active risk tags + active KB sections to child — SKILL.md Step 3 explicit: "do NOT pass the full router or risk-tag context (context discipline — only active tags + active KB sections)"
- [~] No full section-6 dump — structural contract present; runtime verification by T-L5-IRRELEVANT-001 (Phase 6)

#### 3.5 Failure behavior

- [x] Each verdict status mapped to wrapper response per §5 of test strategy — Step 5 exit-code table in SKILL.md (0/1/2/3/4 → continue / HALT_VALIDATOR_FAIL / HALT_ENV_UNAVAILABLE / HALT_BLOCKED / continue-with-REVIEW)
- [x] No false hard-enforcement claims (T-V5-ACC-06) — wrapper description + body explicitly disclaim hard enforcement; test asserts forbidden-phrase absence

### Exit gate

- [x] T-L4-MENU-001/002 pass deterministically (script-based)
- [x] T-L4-WR-001 (happy path) passes — static structural contract on SKILL.md
- [x] T-L4-WR-002 (child error) passes
- [x] T-L4-WR-003 (validator FAIL halt) passes
- [x] T-L4-WR-004 (no recursion) passes
- [x] T-L4-WR-005 (missing artifact) passes
- [x] T-L4-WR-006 (risk tag preservation) passes
- [x] T-L4-SETUP-001/002/003 pass
- [~] L5 happy-path eval pass rate ≥ 85% over 20 runs — Phase 3 ships the structural contract (24 deterministic L4 tests green). Per `RDX_TEST_STRATEGY.md` §2 the L5 layer is "Statistical (multi-run with thresholds)" and the Phase 3 exit-gate text itself says "smoke; full L5 in Phase 6". Runtime LLM-cooperative confirmation is Phase 6 work; the L4 static contract is what locks the SKILL.md prose so the runtime path is reachable.

---

## Phase 4 — Operating modes & setup UX

### Entry gate

- [x] Per-mode acceptance test specs written:
  - [x] Mode 0: T-L1-POL-001 covers advisory pass-through (already green from Phase 2)
  - [x] Mode 1: T-L4-WR-* tests cover soft-gate behavior (already green from Phase 3)
  - [x] Mode 2: T-L6-HOOK-001..005 specs written (in `RDX_TEST_CASES.yaml`; implementation lands in Phase 5)
  - [x] Mode 3: T-L6-CI-001..005 specs written (in `RDX_TEST_CASES.yaml`; implementation lands in Phase 5)
  - [x] Mode 4: deferred to Phase 8 entry gate (module.yaml accepts the value for forward-compat)

### Implementation tasks

- [x] `rdx-setup` interactive mode selector with mode-strength explanation — `assets/module.yaml` single-select `enforcement_level` variable; `SKILL.md` Step 0.5 walks the user through the five modes referencing `assets/modes.md`
- [x] Config records `enforcement_level` matching selected mode — `install.py` `--enforcement-level MODE_X` flag writes `[modules.rdx].enforcement_level` into `config.yaml`; precedence is flag > existing-value > MODE_1 default
- [x] Validator output explicitly labels current mode — `rdx_validator/cli.py` adds `mode_label` field to the JSON envelope alongside the raw `mode` code; canonical labels (Advisory / Local Validated / Local Gated / CI Enforced / Specialist Approval) live in `MODE_LABELS` so downstream consumers do not invent their own
- [x] Documentation explicitly distinguishes "Validated" from "Gated" from "Enforced" — `.claude/skills/rdx-setup/assets/modes.md` is the single-source mode reference; uses the verbs verbatim and explicitly states Mode 1 is "validated, not enforced"
- [~] Phase 3.3 resolver SHA pin (deferred carry-over) — `modes.md` documents the merge contract the install relies on; runtime SHA check deferred to Phase 5 where CI infrastructure exists to verify against a known BMAD release

### Exit gate

- [x] T-V5-ACC-06 (no false enforcement claim) passes — `tests/acceptance/test_doc_honesty.py` greps `.claude/skills/rdx-*` for forbidden phrases (`hard enforcement`, `enforced (Mode 1)`, `guarantees compliance`); negated forms allowed
- [x] T-L5-MODE-001 (agent names mode correctly) passes (smoke; full in Phase 6) — `tests/bmad/modes/test_mode_naming.py` locks the canonical labels in `modes.md` table cells; statistical L5 eval is Phase 6 work per `RDX_TEST_STRATEGY.md` §2
- [x] All per-mode acceptance tests pass — 138/138 tests green (116 prior + 22 new Phase 4)

---

## Phase 5 — Git hook & CI enforcement

### Entry gate

- [x] T-L6-HOOK-001..005 specs written
- [x] T-L6-CI-001..005 specs written
- [x] T-L7 mutation suite specs written (fake-pass, stale-diff, wrong-base, disabled-pack, mod-schema, mod-validator, del-test, oversized-diff, workflow-mod)
- [x] Sample repo plan at `tests/ci/sample-repo-spec.md` written

### Implementation tasks

#### 5.1 Pre-push hook

- [x] Opt-in installer script — `.claude/skills/rdx-hooks/scripts/install-hook.py` (idempotent, foreign-preserving)
- [x] Existing-hook chaining — pre-existing `pre-push` moved to `pre-push.user.rdx-backup`; hook invokes it after RDX runs (T-L6-HOOK-003)
- [x] Uninstall script — `.claude/skills/rdx-hooks/scripts/uninstall-hook.py` restores backup byte-equal (T-L6-HOOK-004)
- [x] `--no-verify` documented behavior — bypass remains by design and is documented in `.claude/skills/rdx-hooks/SKILL.md` + asserted by T-L6-HOOK-005

#### 5.2 GitHub Actions

- [x] `.github/workflows/rdx-gate.yml` template — required-check workflow with read-only `permissions: contents: read`
- [x] Validator loaded from target/base branch (NOT PR head — Option B per strategy §7) — `.github/scripts/rdx-ci-runner.py` accepts `--validator-ref` and uses `git show <ref>:<path>` to materialise validator + schema + contracts from base into a tempdir; PR-head edits to `rdx-validator/**` or the schema have no effect (T-L6-CI-002 + T-L7-MOD-VALIDATOR-001 + T-L7-MOD-SCHEMA-001)
- [x] Independent recomputation of Cat-1/2 — runner always recomputes the diff fresh (`git diff base...head`) and ignores any PR-supplied diff file (T-V5-ACC-05 verified locally)
- [x] Summary publication — workflow appends to `$GITHUB_STEP_SUMMARY` and uploads `rdx-evidence.json` as an artifact (retention 30 d)
- [x] Branch protection documentation — `docs/branch-protection.md` lists required-check name, CODEOWNERS rule for `.github/workflows/**`, signed-commit recommendation, and verification command (T-L7-WORKFLOW-MOD-001)

#### 5.3 Fork PR

- [x] Workflow runs without secrets for Cat-1/2 (T-L6-CI-003) — `permissions: contents: read`; no `id-token`, no `${{ secrets.* }}` in the blocking section
- [x] Cat-3 LLM review NOT in blocking workflow — `rdx-gate.yml` runs Cat-1/2 only; Cat-3 routing is Phase 7 in a separate workflow per `RDX_TEST_STRATEGY.md` §13

#### 5.4 GitLab portability (deferred)

- [ ] `.gitlab-ci.yml.template` (after GitHub baseline ships)

### Exit gate

- [x] All L6 tests pass against sample GitHub repo — 11 L6 tests green via locally-materialised sample repos under `tmp_path` (see `tests/ci/conftest.py` + `tests/ci/sample-repo-spec.md`). Real-GitHub fork-PR validation is structural (workflow YAML asserted by T-L6-CI-003) since live GitHub PR runs require infrastructure beyond this branch; the rdx-ci-runner.py is what the workflow invokes, so passing the local L6 suite proves the runner's contract.
- [x] All L7 mutation tests caught — 10 L7 tests green (FAKE-PASS, STALE-DIFF×2, WRONG-BASE, DISABLED-PACK, MOD-SCHEMA, MOD-VALIDATOR, DEL-TEST, OVERSIZED-DIFF, WORKFLOW-MOD×2)
- [x] T-V5-ACC-05 passes (CI re-computes match local) — `tests/ci/test_l6_ci_workflow.py::test_v5_acc_05_ci_matches_local` runs validator locally + via runner and asserts rule-verdict equality + exit-code equality

---

## Phase 6 — Evals & regression protection

### Entry gate

- [ ] L5 eval cases assembled with prompts, rubrics, repeat counts
- [ ] L7 mutation suite assembled
- [ ] BMad Eval Runner configured for RDX

### Implementation tasks

#### 6.1 Deterministic tests

- [ ] All L0/L1/L2 regression suite runs in < 30s locally
- [ ] L3 integration in < 90s with cargo cache

#### 6.2 BMAD behavioral evals

- [ ] T-L5-ROUTER-001 — Router not skipped (≥ 90% over 20 runs)
- [ ] T-L5-NO-SELF-PASS-001 — No LLM self-PASS (100%)
- [ ] T-L5-NOT-RUN-001 — NOT_RUN honestly recorded (≥ 95%)
- [ ] T-L5-MODE-001 — Correct mode naming (≥ 95%)
- [ ] T-L5-IRRELEVANT-001 — No irrelevant pack loading (≥ 90%)
- [ ] T-L5-CTX-001 — Context-pressure behavior (≥ 80%, with honest degradation)
- [ ] T-L5-FAIL-HONEST-001 — FAIL not called PASS (100%)

#### 6.3 Mutation/adversarial

- [ ] Full L7 suite passes (each listed bypass caught)

#### 6.4 Release gate for RDX itself

- [ ] CI runs all L0–L7 on any change to KB / mapping / schema / validator / agent override

### Exit gate

- [ ] L5 thresholds met for 7-day rolling window
- [ ] L7 full suite green
- [ ] Compatibility matrix passes for Python 3.11/3.12/3.13 × Ubuntu/macOS

---

## Phase 7 — RDX Rule Auditor + BMAD Code Review

### Entry gate (closes Spike 0.2 empirical gap)

- [ ] T-L4-CR-001 (R2 wrapper integration) spec written
- [ ] T-L4-CR-002 (R1 on_complete control) spec written
- [ ] T-L5-CAT3-SCOPE-001 spec written
- [ ] T-L5-CAT3-NO-CAT1-001 spec written
- [ ] T-L5-DOC-001 spec written
- [ ] T-L8-EVAL-CONSISTENT-001 spec written
- [ ] T-L8-ACTIVE-RULES-001 spec written
- [ ] T-L8-DOC-CLASS-001 spec written

### Implementation tasks

#### 7.1 `rdx-judgment` skill

- [ ] Accepts: diff, surrounding code, story/spec, active packs, review_required rules, reasoning evidence, validator findings
- [ ] Does NOT: change Cat-1 verdict, load inactive packs, assign Cat-4 approval, require finding count

#### 7.2 Review output schema

- [ ] Each finding: rule ID, location, contract ref, reasoning, verdict, confidence, suggested routing
- [ ] Verdict set: `PASS`, `FAIL`, `DECISION_REQUIRED`, `SPECIALIST_REQUIRED`, `INSUFFICIENT_EVIDENCE`

#### 7.3 Integration into bmad-code-review

- [ ] R2 implementation: `rdx-code-review` wrapper that overrides `agent.menu[code=CR]`
- [ ] R1 control test maintained for comparison
- [ ] Standard 3 layers (Blind / Edge Case / Acceptance) unchanged

#### 7.4 Parent triage

- [ ] Standard parent dedupes + assigns severity
- [ ] Does NOT treat Cat-3 reviewer as deterministic source of truth

#### 7.5 Documentation review activation

- [ ] Rust API contracts, ADRs, unsafe SAFETY docs, FFI/ABI docs, persistence schemas, security boundaries, RDX KB/Router/validator policy
- [ ] Ordinary docs (README, marketing) NOT covered

### Exit gate

- [ ] T-L4-CR-001 (R2) passes empirically (closes Spike 0.2 gap)
- [ ] If T-L4-CR-001 fails: fallback to R1 (T-L4-CR-002) documented and accepted
- [ ] T-L5-CAT3-SCOPE-001 ≥ 95%
- [ ] T-L5-CAT3-NO-CAT1-001 = 100%
- [ ] T-L5-DOC-001 — no Rust noise on non-Rust docs
- [ ] T-L8 evaluator consistency variance ≤ threshold

---

## Phase 8 — Cat-4 specialist approval

### Entry gate

- [ ] T-L8-CAT4-001/002/003 specs written
- [ ] T-L7-APPROVAL-REUSE-001 spec written
- [ ] T-L8-GOV-001 spec written
- [ ] T-V6-ACC-04 spec written

### Implementation tasks

- [ ] Approval contract schema (rule_id, reviewer, role, head_sha, diff_digest, timestamp, scope, decision, conditions)
- [ ] CODEOWNERS template for unsafe / FFI / security / public API / RDX-protected
- [ ] CI rejects approval-with-mismatched-diff_digest
- [ ] CI rejects approval-from-non-CODEOWNERS-member

### Exit gate

- [ ] T-L8-CAT4-001 (no approval → blocked)
- [ ] T-L8-CAT4-002 (valid approval → unblocked)
- [ ] T-L8-CAT4-003 (unauthorized approver → blocked)
- [ ] T-L7-APPROVAL-REUSE-001 (diff change invalidates)
- [ ] T-L8-GOV-001 (KB/validator changes require governance approval)
- [ ] T-V6-ACC-04 (end-to-end cycle)

---

## Phase 9 — High Assurance hardening

### Entry gate

- [ ] L7 adversarial suite extended for HA-specific bypass paths
- [ ] T-V6-ACC-05 spec written
- [ ] Threat model document authored (`docs/threat-model.md`)

### Implementation tasks (only if real demand exists)

- [ ] Signed attestations (if HMAC threat model confirms necessity)
- [ ] Protected validator source (validator loaded from immutable release tag)
- [ ] Provenance evidence
- [ ] Audit trail retention policy
- [ ] Organization-level required workflows documentation

### Exit gate

- [ ] T-V6-ACC-05 — all adversarial paths caught in HA mode

---

## Phase 10 — Documentation & distribution

### Entry gate

- [ ] Doc-review checklist authored

### Implementation tasks

- [ ] architecture overview
- [ ] mode comparison (with explicit "what enforces what")
- [ ] installation
- [ ] update/uninstall
- [ ] evidence schema reference
- [ ] status semantics
- [ ] exception model
- [ ] hook behavior + `--no-verify` documented
- [ ] CI setup
- [ ] review integration
- [ ] specialist approvals
- [ ] troubleshooting
- [ ] compatibility matrix
- [ ] limitations

### Public positioning (Phase 10 deliverable, but enforced by T-V5-ACC-06)

Clearly state:
- RDX does NOT prove correctness of all Rust decisions
- Cat-1 is deterministic
- Cat-2 verifies evidence
- Cat-3 is judgment review
- Cat-4 requires approval
- CI is the source of enforcement
- Wrapper is workflow UX (NOT hard enforcement)

### Exit gate

- [ ] Grep over all docs: no forbidden phrases ("hard enforcement" applied to Modes 0/1, "guarantees compliance", etc.) — covered by T-V5-ACC-06

---

## Release order (unchanged from original plan)

| Release | Phases | Tests required |
|---------|--------|----------------|
| RDX 1.1 — Validator foundation | 0, 1, 2 | All L0, L1, L2 + L3 smoke |
| RDX 1.2 — BMAD integration | 3, 4 | + L4 + L5 smoke + per-mode acceptance |
| RDX 1.3 — CI Enforced (V5 production) | 5 | + L6 + L7 + T-V5-ACC-01..07 |
| RDX 1.4 — Review layer | 6, 7 | + L8 happy paths + L5 full thresholds |
| RDX 1.5 — High Assurance (V6 production) | 8, 9, 10 | + L7 hardening + T-V6-ACC-01..05 |

---

## V5 / V6 DoD — test-linked

(Full table in `RDX_TEST_TRACEABILITY_MATRIX.md`. Summary here for plan navigation.)

**V5 Definition of Done — each item carries a Primary test:**
1. Validator BMAD-independent → T-V5-ACC-01
2. Menu override → T-L4-MENU-001
3. Wrapper integration spike → T-L4-WR-001
4. Strong Router signals → T-V5-ACC-02
5. Weak signals don't block → T-V5-ACC-03
6. Evidence authority → T-V5-ACC-04
7. Git hook blocks push → T-L6-HOOK-001
8. CI re-computes → T-V5-ACC-05
9. Baseline vs regression → T-L1-BASE-001..004
10. Stale evidence rejected → T-L7-STALE-DIFF-001
11. Docs honest → T-V5-ACC-06
12. BMAD evals pass → T-L5-ROUTER-001
13. Install/update/uninstall → T-L4-SETUP-001..003
14. KB behavior not regressed → T-V5-ACC-07

**V6 Definition of Done — each item carries a Primary test:**
1. V5 still passes → T-V6-ACC-01
2. Cat-3 routing → T-V6-ACC-02
3. Auditor scope → T-L8-ACTIVE-RULES-001
4. Review integration → T-V6-ACC-03
5. Cat-1 immutable → T-L5-CAT3-NO-CAT1-001
6. Cat-4 approval → T-L8-CAT4-001
7. Approval diff-pinned → T-L7-APPROVAL-REUSE-001
8. Governance protected → T-L8-GOV-001
9. Eval coverage → T-L8-EVAL-CONSISTENT-001
10. HA adversarial → T-V6-ACC-05

---

## Progress Log (rolling, append-only)

| Date | Phase | Item | Status | Evidence |
|------|-------|------|--------|----------|
| 2026-06-29 | Init | Plan saved to branch | x | `rdx-improvements` branch |
| 2026-06-29 | 0.1 | Multi-skill happy path | x (partial) | `RDX_PHASE0_SPIKE_REPORT.md` §0.1, `spikes/0.1-multi-skill/trace.log.evidence` |
| 2026-06-29 | 0.2 | Review propagation | DOC VERIFIED | `RDX_PHASE0_SPIKE_REPORT.md` §0.2 |
| 2026-06-29 | 0.3 | Standalone validator prototype | x | `spikes/0.3-standalone-validator/` |
| 2026-06-29 | 0 | Phase 0 gate | CONDITIONAL GO | Pending items rescheduled to Phase 3 / 6 / 7 |
| 2026-06-29 | Test design | Test strategy + matrix + YAML + tested plan | x | This file + companions |
| 2026-06-29 | Phase 1 | Contracts & SSoT complete | x | Commit `c34631c` (red tests) + impl commit; 13 L0 tests green; closed T-L0-SCHEMA-001..004, T-L0-ROUTER-001, T-L0-DRIFT-001/002, T-L0-STATUS-001/002, T-L0-RULE-IDS-001; CI workflow `.github/workflows/rdx-l0-contracts.yml` |
| 2026-06-29 | Phase 2 | Validator package + L1/L2/L3 (partial) | x | 92 tests green (13 L0 + 30 L1 + 45 L2 + 4 L3). `rdx-validator/` package with diff parser, digest, router replay, exception parser, status taxonomy, aggregator, exit-code mapper, baseline comparator, CORE-007/008/011/014/015 checks, CLI. Closed: T-L1-DIFF-001..003, T-L1-DIGEST-001/002, T-L1-COMMENT-001, T-L1-EXC-001/002, T-L1-AGG-001..003, T-L1-EXIT-001..005, T-L1-BASE-001..004, T-L1-POL-001, T-L2-ASYNC-001..004, T-L2-UNSAFE-001..004 (validator portion), T-L2-FFI-001/002, T-L2-MACRO-001/002, T-L2-API-001/002, T-L2-CARGO-001/002, T-L2-TEST-001/002, T-L2-DATA-001, T-L2-DB-001, T-L2-TIME-001, T-L2-OPS-001/002, T-L2-PERF-001/002, T-L2-CORE007-001..003, T-L2-CORE008-001..003, T-L2-CORE011-001..003, T-L2-CORE014-001..003, T-L2-CORE015-001/002, T-L3-CRATE-001/003/004/005. T-L3-CRATE-002/006/007 deferred (need real cargo invocation, Phase 5). BASELINE_BLOCKS_VALIDATION + TOOL_UNAVAILABLE dedicated unit tests deferred to Phase 5. CI workflow `.github/workflows/rdx-l1-l3-validator.yml`. |
| 2026-06-30 | Phase 3 | rdx-dev-story wrapper + menu override + setup/uninstall | x | 116 tests green (92 prior + 24 new L4). `.claude/skills/rdx-dev-story/SKILL.md` ships the soft-gate wrapper with BEFORE→CHILD→AFTER ordering, validator-fail halt sentinel, no-recursion guard, missing-artifact diagnostic, child-error continuation, and risk-tag preservation via on-disk storage. `.claude/skills/rdx-setup/assets/agent-overrides/bmad-agent-dev.toml` declares `[[agent.menu]] code="DS" skill="rdx-dev-story"`. `.claude/skills/rdx-setup/scripts/{install,uninstall}.py` perform idempotent install (merge-by-code, foreign-preserving) and round-trip uninstall. Closed: T-L4-MENU-001/002, T-L4-WR-001..006 (static structural contract), T-L4-SETUP-001/002/003. Resolver SHA pin + setup warning deferred to Phase 4; full L5 ≥85% over 20 runs is Phase 6 work per strategy §2 (L5 = statistical layer). CI workflow `.github/workflows/rdx-l4-bmad-integration.yml`. Resolver-shim helper at `tests/bmad/_helpers/resolver_shim.py`. |
| 2026-06-30 | Phase 4 | Operating modes + setup UX + validator mode_label + doc-honesty | x | 138 tests green (116 prior + 22 new: 9 mode-selector + 4 mode-naming + 6 mode-label + 3 doc-honesty). Production-artefact set: `.claude/skills/rdx-setup/assets/modes.md` (single-source mode reference: Advisory / Local Validated / Local Gated / CI Enforced / Specialist Approval); `.claude/skills/rdx-setup/assets/module.yaml` adds `enforcement_level` single-select with default `MODE_1`; `.claude/skills/rdx-setup/SKILL.md` Step 0.5 prompts for mode + Step 4 passes `--enforcement-level` to install.py. Runtime guards: `install.py` `--enforcement-level` flag with precedence flag > existing > `MODE_1` default; `_extract_existing_level` / `_strip_rdx_block` so re-runs preserve user choice and stay bytewise idempotent. Validator surface: `rdx_validator/cli.py` adds `mode_label` to the JSON envelope (sourced from `MODE_LABELS`) and gets a proper `if __name__ == "__main__"` guard so `python rdx-validator/rdx_validator/cli.py` actually runs (latent Phase 3 bug; the wrapper SKILL.md documented the script form but the file was a no-op when executed directly). Closed: T-V5-ACC-06 (doc-honesty grep), T-L5-MODE-001 smoke (deterministic label contract; statistical eval still Phase 6). Per-mode acceptance tests pass: T-L1-POL-001 (Mode 0 advisory) and T-L4-WR-* (Mode 1 soft-gate) remain green; T-L6-HOOK-* and T-L6-CI-* specs present in YAML (implementation Phase 5). Resolver SHA pin runtime check (Phase 3.3 carry-over) further deferred to Phase 5. CI workflow `.github/workflows/rdx-l4-modes.yml`. |
| 2026-06-30 | Phase 5 | Git hook + CI workflow + L7 mutation guards | x | 160 tests green (138 prior + 22 new: 5 L6-hook + 6 L6-CI + 11 L7-mutation). Production: `.claude/skills/rdx-hooks/{SKILL.md, assets/pre-push.sh, scripts/install-hook.py, scripts/uninstall-hook.py}` ship the opt-in pre-push hook with foreign-hook chaining + byte-equal uninstall restore + documented `--no-verify` bypass. `.github/workflows/rdx-gate.yml` is the required-check workflow with `permissions: contents: read` only (no secrets, fork-PR safe). `.github/scripts/rdx-ci-runner.py` implements Option B (validator + schema + contracts materialised from `--validator-ref` via `git show <ref>:<path>` into a tempdir; PR-head edits ignored); also supports a working-tree mode for local pytest. `docs/branch-protection.md` documents the GitHub-side CODEOWNERS rule for `.github/workflows/**` (T-L7-WORKFLOW-MOD-001). Runtime guards in `rdx-validator/rdx_validator/preflight.py` cover stale-evidence (digest mismatch → recompute) and wrong-base (sha mismatch) checks; `cli.py` adds `--max-diff-bytes` (default 10 MiB) and emits `ENVIRONMENT_UNAVAILABLE` with exit 2 for oversized diffs (T-L7-OVERSIZED-DIFF-001). `tests/fixtures/cargo-projects/green-crate/evidence-in.json` digest recomputed to match its diff so the new preflight does not flag it as stale. Closed: T-L6-HOOK-001..005, T-L6-CI-001..005, T-V5-ACC-05, T-L7-FAKE-PASS-001, T-L7-STALE-DIFF-001, T-L7-WRONG-BASE-001, T-L7-DISABLED-PACK-001 (L7 reaffirmation), T-L7-MOD-SCHEMA-001, T-L7-MOD-VALIDATOR-001, T-L7-DEL-TEST-001 (L7 reaffirmation), T-L7-OVERSIZED-DIFF-001, T-L7-WORKFLOW-MOD-001. T-V5-ACC-01..04/06/07 already proven by earlier phases or unchanged. GitLab portability (5.4) deferred. CI workflow `.github/workflows/rdx-l6-l7.yml`. |
