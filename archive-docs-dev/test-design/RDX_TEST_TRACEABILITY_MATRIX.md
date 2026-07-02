# RDX Test Traceability Matrix

Maps every V5/V6 requirement to test IDs (`T-...`) from `RDX_TEST_CASES.yaml`.

**Reading the table:**
- A row is a single requirement (DoD item, CORE rule, or pack-level requirement)
- Tests listed cover the requirement at varying layers (L0..L8)
- `Primary` = first test that proves the requirement; `Coverage` = additional tests that strengthen confidence
- A requirement with no Primary test is a **gap** — must not exist at release

---

## V5 Definition of Done — full coverage map

| Req ID | Requirement | Phase | Primary test(s) | Coverage tests | Layer mix | Release gate |
|--------|-------------|-------|-----------------|----------------|-----------|--------------|
| R-V5-DoD-01 | Validator does not depend on BMAD | 2, 5 | T-V5-ACC-01 | T-L1-DIFF-001, T-L1-DIGEST-001, T-L3-CRATE-001 | L1, L3 | v5-release |
| R-V5-DoD-02 | Menu override works without BMAD core change | 3 | T-L4-MENU-001 | T-L4-MENU-002 | L4 | exit-phase-3 |
| R-V5-DoD-03 | Wrapper integration passed real-session spike | 3 | T-L4-WR-001 | T-L4-WR-002, T-L4-WR-003, T-L4-WR-004, T-L4-WR-005, T-L4-WR-006 | L4 | exit-phase-3 |
| R-V5-DoD-04 | Strong Router signals reproducibly detected | 2, 5 | T-V5-ACC-02 | T-L2-ASYNC-001/003, T-L2-UNSAFE-001/003, T-L2-FFI-001/002, T-L2-MACRO-001/002, T-L2-CARGO-001/002, T-L2-PERF-001, T-L2-CORE007-001, T-L2-CORE008-002, T-L2-CORE011-001/002, T-L2-CORE014-001/002/003, T-L2-CORE015-001/002 | L2, L3 | v5-release |
| R-V5-DoD-05 | Weak signals do not create unjustified blocking FAIL | 2, 5 | T-V5-ACC-03 | T-L2-ASYNC-002/004, T-L2-UNSAFE-002, T-L2-API-001/002, T-L2-TEST-001, T-L2-OPS-001, T-L2-PERF-002, T-L2-CORE008-001/003, T-L2-CORE007-003 | L2 | v5-release |
| R-V5-DoD-06 | Evidence schema separates authority | 1, 5 | T-V5-ACC-04 | T-L0-SCHEMA-001/002/003/004, T-L0-STATUS-001/002, T-L1-EXC-001/002, T-L1-AGG-001/002/003, T-L1-EXIT-001..005, T-L1-POL-001, T-L2-CORE011-003, T-L7-FAKE-PASS-001 | L0, L1, L7 | v5-release |
| R-V5-DoD-07 | Git hook really blocks push | 5 | T-L6-HOOK-001 | T-L6-HOOK-002, T-L6-HOOK-003, T-L6-HOOK-004, T-L6-HOOK-005 | L6 | exit-phase-5 |
| R-V5-DoD-08 | CI independently recomputes deterministic verdicts | 5 | T-V5-ACC-05 | T-L6-CI-001..005, T-L7-FAKE-PASS-001, T-L7-WRONG-BASE-001, T-L7-MOD-SCHEMA-001, T-L7-MOD-VALIDATOR-001, T-L7-WORKFLOW-MOD-001, T-L7-OVERSIZED-DIFF-001 | L6, L7 | v5-release |
| R-V5-DoD-09 | Baseline distinguished from regression | 2, 5 | T-L1-BASE-001..004 | T-L3-CRATE-003, T-L3-CRATE-004, T-L6-CI-004 | L1, L3, L6 | v5-release |
| R-V5-DoD-10 | Stale evidence rejected | 2, 5 | T-L1-DIGEST-001, T-L1-DIGEST-002 | T-L6-CI-005, T-L7-STALE-DIFF-001 | L1, L6, L7 | v5-release |
| R-V5-DoD-11 | Docs do not call wrapper hard enforcement | 5 | T-V5-ACC-06 | T-L5-MODE-001 | L4, L5 | v5-release |
| R-V5-DoD-12 | BMAD module evals pass | 6 | T-L5-ROUTER-001 | T-L5-NOT-RUN-001, T-L5-IRRELEVANT-001, T-L5-CTX-001, T-L5-FAIL-HONEST-001, T-L5-NO-SELF-PASS-001 | L5 | exit-phase-6 |
| R-V5-DoD-13 | Install/update/uninstall verified in clean project | 3 | T-L4-SETUP-001 | T-L4-SETUP-002, T-L4-SETUP-003, T-L4-MENU-002 | L4 | exit-phase-3 |
| R-V5-DoD-14 | Existing RDX KB behavior not regressed | 5 | T-V5-ACC-07 | (re-runs of current RDX integration tests) | L4 | v5-release |

**Gap check:** 14 DoD items, 14 primary tests assigned. **No V5 gaps.**

---

## V6 Definition of Done — full coverage map

| Req ID | Requirement | Phase | Primary test(s) | Coverage tests | Layer mix | Release gate |
|--------|-------------|-------|-----------------|----------------|-----------|--------------|
| R-V6-DoD-01 | All V5 criteria still pass | 7 | T-V6-ACC-01 | (entire V5 acceptance suite) | All | v6-release |
| R-V6-DoD-02 | Cat-3 rules routed to RDX Rule Auditor | 7 | T-V6-ACC-02 | T-L8-EVAL-CONSISTENT-001, T-L5-CAT3-SCOPE-001 | L5, L8 | v6-release |
| R-V6-DoD-03 | Auditor receives only active rules/packs | 7 | T-L8-ACTIVE-RULES-001 | T-L5-CAT3-SCOPE-001 | L5, L8 | exit-phase-7 |
| R-V6-DoD-04 | Findings integrated into code-review triage | 7 | T-V6-ACC-03 | T-L4-CR-001, T-L4-CR-002, T-L8-DOC-CLASS-001, T-L5-DOC-001 | L4, L5, L8 | v6-release |
| R-V6-DoD-05 | Cat-1 verdict cannot be changed by evaluator | 7 | T-L5-CAT3-NO-CAT1-001 | T-V6-ACC-02 | L5, L8 | exit-phase-7 |
| R-V6-DoD-06 | Cat-4 changes require named approval | 8 | T-L8-CAT4-001 | T-L8-CAT4-002, T-V6-ACC-04 | L8 | v6-release |
| R-V6-DoD-07 | Approvals pinned to diff | 8 | T-L7-APPROVAL-REUSE-001 | T-L8-CAT4-001/002/003, T-V6-ACC-04 | L7, L8 | v6-release |
| R-V6-DoD-08 | Governance-sensitive RDX artifacts protected | 8 | T-L8-GOV-001 | T-L7-MOD-SCHEMA-001, T-L7-MOD-VALIDATOR-001, T-L7-WORKFLOW-MOD-001, T-L7-APPROVAL-REUSE-001 | L7, L8 | v6-release |
| R-V6-DoD-09 | Review and approval flows have eval coverage | 7 | T-L8-EVAL-CONSISTENT-001 | T-L5-CAT3-SCOPE-001, T-L5-CAT3-NO-CAT1-001, T-L5-DOC-001 | L5, L8 | v6-release |
| R-V6-DoD-10 | High Assurance mode confirmed by adversarial tests | 9 | T-V6-ACC-05 | (all L7 mutation tests) | L7 | v6-release |

**Gap check:** 10 DoD items, 10 primary tests assigned. **No V6 gaps.**

---

## CORE rule → test coverage

| Rule | Description (short) | Tests proving deterministic compliance | Tests proving exception path | Tests proving false-positive avoidance |
|------|---------------------|----------------------------------------|------------------------------|---------------------------------------|
| CORE-007 | Protected boundaries | T-L2-CORE007-001 | T-L2-CORE007-002 | T-L2-CORE007-003 |
| CORE-008 | Panic discipline (subset) | T-L2-CORE008-002 | (story tag opt-in) | T-L2-CORE008-001, T-L2-CORE008-003 |
| CORE-011 | Compile evidence | T-L2-CORE011-001, T-L2-CORE011-002 | T-L2-CORE011-003, T-L1-AGG-002 | (NOT_RUN with reason path) |
| CORE-014 | Suppression / test weakening | T-L2-CORE014-001/002/003 | (authorization path — covered by exception parser tests) | (legitimate `#[allow(dead_code)]` — todo as Phase 2 entry-gate test) |
| CORE-015 | Router parity | T-L2-CORE015-001, T-L7-DISABLED-PACK-001 | T-L2-CORE015-002 | (no false-positive surface — replay is authoritative) |
| Other CORE-001..018 | Various | Indirectly via evidence-presence checks (Cat 2) | n/a | n/a |

---

## Risk Router packs → fixture coverage

| Pack | Positive (true) | Negative (doc-only) | Story-tag gating | Path-signal | Notes |
|------|-----------------|---------------------|------------------|-------------|-------|
| async | T-L2-ASYNC-001, T-L2-ASYNC-003 | T-L2-ASYNC-002, T-L2-ASYNC-004 | — | — | Strong signal; AUTO_ACTIVATE |
| unsafe | T-L2-UNSAFE-001, T-L2-UNSAFE-003 | T-L2-UNSAFE-002 | (Cat-4 always required) | — | Strong signal; auto-escalates to Cat-4 |
| ffi | T-L2-FFI-001, T-L2-FFI-002 | (no doc-only fixture yet — Phase 2 gap to fill) | (Cat-4 escalation) | T-L2-FFI-002 | Add fixture in Phase 2 |
| macro | T-L2-MACRO-001, T-L2-MACRO-002 | (gap — Phase 2 fill) | — | T-L2-MACRO-002 | Add doc-only macro fixture |
| api | T-L2-API-001 | T-L2-API-002 | T-L2-API-002 | — | Requires publish=true detection |
| cargo | T-L2-CARGO-001, T-L2-CARGO-002 | (no doc-only — Cargo.toml IS the signal) | — | T-L2-CARGO-001/002 | Path-only |
| testing | T-L2-TEST-002 | (gap — fill in Phase 2) | T-L2-TEST-001 | — | STORY_TAG_REQUIRED |
| data | T-L2-DATA-001 | (gap — fill in Phase 2) | — | — | AUTO_SUGGEST |
| db | T-L2-DB-001 | (gap — fill in Phase 2) | — | T-L2-DB-001 (path: migrations/) | AUTO_SUGGEST |
| time | T-L2-TIME-001 | (gap — fill in Phase 2) | — | — | AUTO_SUGGEST |
| ops | T-L2-OPS-002 | T-L2-OPS-001 | T-L2-OPS-001/002 | — | STORY_TAG_REQUIRED |
| perf | T-L2-PERF-001 | T-L2-PERF-002 | T-L2-PERF-002 | T-L2-PERF-001 | STORY_TAG_REQUIRED for perf claims; AUTO_ACTIVATE for no_std |

**Pack fixture gaps (Phase 2 entry gate to close):**
- FFI doc-only negative
- Macro doc-only negative
- Testing negative
- Data doc-only negative
- DB doc-only negative
- Time doc-only negative

These are tracked in Phase 2 entry-gate tasks (`RDX_IMPLEMENTATION_PLAN_TESTED.md`).

---

## Status taxonomy → transition coverage

| Status | Set-by test | Blocking-true test | Blocking-false test | Authority test |
|--------|-------------|--------------------|--------------------|-----------------|
| PASS | T-L1-AGG-002, T-L2-CORE007-002 | — | — | T-V5-ACC-04 (no LLM Cat-1 PASS) |
| FAIL | T-L1-AGG-001, T-L2-CORE007-001 | T-L6-CI-001 | — | T-L5-FAIL-HONEST-001 |
| NOT_APPLICABLE | T-L2-CORE007-003 | — | (always non-blocking) | — |
| NOT_RUN (with reason) | T-L1-AGG-002 | T-L1-AGG-003 (without reason) | T-L1-AGG-002 (with reason) | T-L5-NOT-RUN-001 |
| EVIDENCE_REQUIRED | T-L2-CORE011-001, T-L2-CORE014-001 | T-L2-CORE011-001 | — | — |
| REVIEW_REQUIRED | T-L2-API-001, T-L2-DATA-001 | T-L1-EXIT-003 (exit 4) | (exit 0 in Mode 0/1) | T-L8-EVAL-CONSISTENT-001 |
| APPROVAL_REQUIRED | T-L2-UNSAFE-001, T-L8-CAT4-001 | T-L8-CAT4-001 | — | T-L7-APPROVAL-REUSE-001 |
| BASELINE_FAILURE_OBSERVED | T-L1-BASE-001 | — | T-L1-BASE-001 (non-blocking) | T-L6-CI-004 |
| BASELINE_BLOCKS_VALIDATION | (gap — needs fixture in Phase 2) | — | — | — |
| REGRESSION_FAILURE | T-L1-BASE-002, T-L1-BASE-003 | T-L3-CRATE-004 | — | — |
| REGRESSION_FIXED | T-L1-BASE-004 | — | T-L1-BASE-004 (bonus, non-blocking) | — |
| ENVIRONMENT_UNAVAILABLE | T-L1-EXIT-005 | T-L7-OVERSIZED-DIFF-001 | — | — |
| TOOL_UNAVAILABLE | (gap — needs L1 test) | — | — | — |
| BLOCKED | T-L1-AGG-001 | T-L1-AGG-001 | — | — |
| WARNING (severity) | T-L2-CORE008-001 | — | T-L2-CORE008-001 (severity, not verdict) | — |

**Status gaps:** `BASELINE_BLOCKS_VALIDATION` and `TOOL_UNAVAILABLE` need explicit unit tests in Phase 2. Added to plan.

---

## Operating mode → acceptance test coverage

| Mode | Description | Acceptance test(s) | Notes |
|------|-------------|--------------------|-------|
| 0 — Advisory | KB only, no enforcement | T-L1-POL-001 | Validator runs in report-only; exit 0 even on FAIL |
| 1 — Local Validated | + wrapper + validator | T-L4-WR-001..006, T-L5-MODE-001 | Soft gate; LLM-cooperative |
| 2 — Local Gated | + pre-push hook | T-L6-HOOK-001..005 | Hook is the hard gate |
| 3 — CI Enforced | + GitHub Actions required check | T-L6-CI-001..005, T-V5-ACC-05 | Server-side block |
| 4 — High Assurance | + Cat-3 + Cat-4 + governance | T-V6-ACC-04, T-V6-ACC-05, T-L8-CAT4-001..003, T-L8-GOV-001 | Multi-party + diff-pinned |

---

## Cross-cutting concerns → test coverage

| Concern | Tests |
|---------|-------|
| Setup / re-setup / uninstall | T-L4-SETUP-001/002/003 |
| Foreign customizations preserved | T-L4-MENU-002 |
| Schema authority (no LLM Cat-1 PASS) | T-L0-SCHEMA-004, T-V5-ACC-04, T-L5-NO-SELF-PASS-001 |
| Trusted CI source (PR can't tamper with validator) | T-L6-CI-002, T-L7-MOD-VALIDATOR-001, T-L7-MOD-SCHEMA-001 |
| Fork PR safety | T-L6-CI-003 |
| Branch protection on workflow files | T-L7-WORKFLOW-MOD-001 |
| Doc honesty (no "enforced" claim for soft gates) | T-V5-ACC-06, T-L5-MODE-001 |
| KB ↔ mapping drift | T-L0-DRIFT-001, T-L0-DRIFT-002 |
| Rule ID stability | T-L0-RULE-IDS-001 |
| Compatibility matrix | (Phase 6 — to be added per OS × Python × Rust matrix) |

---

## Tests-without-requirements check

Every test in the YAML traces back to at least one `requirement_ids` entry. Spot check of L7 entries:

- T-L7-FAKE-PASS-001 → R-V5-DoD-06, R-V5-DoD-08 ✓
- T-L7-WORKFLOW-MOD-001 → R-V5-DoD-08 ✓
- T-L7-APPROVAL-REUSE-001 → R-V6-DoD-07, R-V6-DoD-08 ✓

(Full audit covered by automated script `tests/contracts/verify-traceability.py` — Phase 1 deliverable.)

---

## Release gate summary

| Gate | What must be green |
|------|--------------------|
| exit-phase-1 | All L0 tests + traceability auto-check |
| exit-phase-2 | All L1 + L2 + L3-smoke; pack-fixture gap list cleared |
| exit-phase-3 | All L4 except CR tests; setup/uninstall verified |
| exit-phase-5 | All L6 + L7 (validator-side); CI sample repo green |
| exit-phase-6 | L5 evals at threshold for 14 days rolling |
| exit-phase-7 | L4-CR + L5-CAT3-* + L8-EVAL-CONSISTENT |
| exit-phase-8 | L7-APPROVAL-REUSE + L8-CAT4-* + L8-GOV |
| v5-release | T-V5-ACC-01..07 all pass; rolling L5 thresholds met |
| v6-release | T-V6-ACC-01..05 all pass; V5-release re-verified |
