---
workflowStatus: 'completed'
totalSteps: 5
stepsCompleted: ['step-01-detect-mode', 'step-02-load-context', 'step-03-risk-and-testability', 'step-04-coverage-plan', 'step-05-generate-output']
lastStep: 'step-05-generate-output'
nextStep: ''
lastSaved: '2026-07-04'
---

# Test Design: Epic 001 - Background Task Runner (Async)

**Date:** 2026-07-04  
**Author:** alfaRazieL  
**Status:** Draft

---

## Executive Summary

**Scope:** Epic-level test design for async background task runner with focus on cancellation safety and abandonment handling.

**Risk Summary:**

- Total risks identified: 6
- High-priority risks (≥6): 4 (R1, R2, R3, R5)
- Critical categories: TECH (cancellation safety), Task lifecycle, Cleanup

**Coverage Summary:**

- P0 scenarios: 5 (15–25 hours)
- P1 scenarios: 6 (10–20 hours)
- P2/P3 scenarios: 3 (5–10 hours)
- **Total effort**: ~35–65 hours (~1–2 weeks)

---

## Not in Scope

| Item | Reasoning | Mitigation |
|------|-----------|-----------|
| Public API / crate publication | Story specifies internal type only | Document as internal; skip public semver validation |
| Persistence / job recovery | Out of scope per acceptance criteria | Test assumes stateless runner; document restart semantics |
| Load testing with 1000+ concurrent runners | Nice-to-have optimization | Defer to P2; baseline perf suffices for MVP |

---

## Risk Assessment

### High-Priority Risks (Score ≥6)

| Risk ID | Category | Description | Probability | Impact | Score | Mitigation | Owner | Timeline |
|---------|----------|-------------|-------------|--------|-------|-----------|-------|----------|
| R1 | TECH | Cancellation safety when owner drops future | 3 | 3 | **9** | Test cancellation with dropped futures; verify no partial progress loss; validate RP-ASYNC-005 compliance | Dev Lead | Pre-release |
| R2 | TECH | Task cleanup on abandonment | 3 | 2 | **6** | Test explicit cleanup paths; verify resources freed; validate RP-ASYNC-006 task supervision | QA Lead | Pre-release |
| R3 | TECH | Unclear task ownership/lifecycle | 2 | 3 | **6** | Define explicit owner, supervision strategy, completion contract; verify CORE-003/CORE-009 compliance via code review | Architect | Design phase |
| R5 | BUS | Service redeploy with running job | 2 | 3 | **6** | Test restart/recovery semantics; document expected behavior on redeploy; verify idempotency | QA Lead | Integration testing |

### Medium-Priority Risks (Score 3-4)

| Risk ID | Category | Description | Probability | Impact | Score | Mitigation | Owner |
|---------|----------|-------------|-------------|--------|-------|-----------|-------|
| R4 | PERF | Async worker pool starvation (blocking work) | 2 | 2 | **4** | Verify non-blocking async APIs (no `block_on`); check RP-ASYNC-003 compliance | Dev Lead |
| R6 | TECH | Sync guard lifetimes across await | 2 | 2 | **4** | Verify borrow/lock scope around suspension points; check RP-ASYNC-004 compliance | Dev Lead |

### Risk Category Legend

- **TECH**: Technical/Architecture (design flaws, integration, cancellation, lifecycle)
- **SEC**: Security (access controls, auth, data exposure)
- **PERF**: Performance (SLA violations, degradation, resource limits)
- **DATA**: Data Integrity (loss, corruption, inconsistency)
- **BUS**: Business Impact (UX harm, logic errors, revenue)
- **OPS**: Operations (deployment, config, monitoring)

---

## NFR Planning

**Purpose:** Capture epic-specific NFR thresholds and planned validation. Story focuses on correctness (cancellation safety, cleanup, predictability) rather than explicit NFRs.

| NFR Category | Requirement / Threshold | Risk Link | Planned Validation | Evidence Needed |
|---|---|---|---|---|
| Reliability | Cancellation must be safe; no partial progress loss | R1 | Integration tests: dropped futures, cancel signals | Test report (T3, T4) |
| Reliability | Cleanup must be explicit; no resource leaks | R2 | Integration tests: resource tracking, abandon scenarios | Test report + leak detector logs (T4) |
| Correctness | Task ownership explicit; predictable behavior | R3 | Code review: CORE-003/CORE-009 compliance | Design review + code audit (T5) |
| Reliability | Predictable behavior on service redeploy | R5 | E2E simulation: restart with running job | Test report (T12) |

**Unknown thresholds:** None specified in story; acceptance criteria focus on behavior correctness rather than quantitative SLAs.

---

## Entry Criteria

- [x] Requirements and assumptions agreed upon (story.md provided)
- [x] Async design patterns (CORE rules, RP-ASYNC pack) loaded from RDX-TEA
- [ ] Test environment provisioned
- [ ] Feature code skeleton available
- [x] Risk assessment complete (6 risks identified, 4 high-priority)

## Exit Criteria

- [ ] All P0 tests passing (T1–T5)
- [ ] All P1 tests passing (T6–T11)
- [ ] No open high-priority bugs (R1, R2, R3, R5 mitigated)
- [ ] Code review confirms: ownership (T5), cleanup design (T6), borrow safety (T11)
- [ ] High-risk items (score ≥6) validated or approved waivers

## Project Team (Optional)

| Name | Role | Testing Responsibilities |
|------|------|--------------------------|
| alfaRazieL | Dev Lead | Implement Runner type; ensure RP-ASYNC compliance; code review for cancellation safety |
| (QA Lead TBD) | QA Lead | Test abandonment, cleanup, concurrent isolation; P0/P1 validation |
| (Architect TBD) | Architect | Ownership/lifecycle design; CORE-003/CORE-009 review |

---

## Test Coverage Plan

### P0 (Critical) - Run on every commit

**Criteria**: Blocks core functionality + Score ≥6 + No workaround

| Requirement | Test Level | Risk Link | Scenario ID | Test Focus | Owner |
|---|---|---|---|---|---|
| Runner spawns task successfully | Unit + Integration | - | T1 | Basic spawn, no errors | Dev |
| Owner receives result on normal completion | Integration + E2E | - | T2 | Happy path: spawn → complete → result | QA |
| Dropped runner cancels background work | Integration | R1 (score 9) | T3 | **CRITICAL**: cancel safety, RP-ASYNC-005 | QA |
| No resource leaks on abandon | Integration | R2 (score 6) | T4 | Cleanup, resource tracking, explicit drop | QA |
| Task ownership explicit (design review) | Code Review | R3 (score 6) | T5 | CORE-003/CORE-009 compliance | Arch + Dev |

**Total P0**: 5 scenarios, **15–25 hours**

### P1 (High) - Run on PR to main

**Criteria**: Important features + Medium/high risk (4-6) + Common workflows

| Requirement | Test Level | Risk Link | Scenario ID | Test Focus | Owner |
|---|---|---|---|---|---|
| Cleanup explicit on drop (design) | Unit + Code Review | R2, R3 | T6 | Verify drop semantics, RP-ASYNC-005 | Dev + Arch |
| Multiple concurrent runners isolated | Integration | - | T7 | No cross-runner interference | QA |
| Runner returns Err on task failure | Integration | - | T8 | Error propagation, CORE-008 | QA |
| Owner can abort waiting (early drop) | Integration | R3, R5 | T9 | Abandon semantics, cancel-safe | QA |
| Task panic propagates correctly | Unit | - | T10 | Error spec, no silent panic swallowing | Dev |
| No sync guards across await | Code Review | R6 | T11 | RP-ASYNC-004 compliance, borrow safety | Dev |

**Total P1**: 6 scenarios, **10–20 hours**

### P2 (Medium) - Run nightly/weekly

**Criteria**: Secondary features + Low risk + Edge cases

| Requirement | Test Level | Risk Link | Scenario ID | Test Focus | Owner |
|---|---|---|---|---|---|
| Service redeploy with running job | E2E (simulation) | R5 (score 6) | T12 | Restart semantics, idempotency | QA |
| Minimal spawn overhead | Benchmark | R4 (score 4) | T13 | Perf baseline, RP-ASYNC-003 check | Dev |

**Total P2**: 2 scenarios, **5–10 hours**

### P3 (Low) - Run on-demand

**Criteria**: Nice-to-have + Exploratory + Edge cases

| Requirement | Test Level | Scenario ID | Test Focus | Owner |
|---|---|---|---|---|
| Nested runners don't deadlock | Unit | T14 | Rare scenario, edge case | Dev |

**Total P3**: 1 scenario, **2–5 hours**

---

## Execution Order

### P0 Tests (Critical Path)

**Purpose**: Validate acceptance criteria and block release-critical risks

- [x] T1: Basic spawn (Unit) — 30 min
- [x] T2: Normal completion (Integration) — 1.5 hours
- [x] T3: Cancellation safety (Integration) — **2 hours** (most complex, R1 score 9)
- [x] T4: Cleanup on abandon (Integration) — 1.5 hours
- [x] T5: Ownership design review (Code Review) — 1 hour

**Total P0**: ~6.5 hours (run in parallel after dev completes skeleton)

### P1 Tests (Core Coverage)

**Purpose**: Validate important workflows and medium-risk scenarios

- [x] T6: Cleanup design (Code Review) — 1 hour
- [x] T7: Concurrent isolation (Integration) — 1.5 hours
- [x] T8: Error propagation (Integration) — 1 hour
- [x] T9: Abandon semantics (Integration) — 1.5 hours
- [x] T10: Panic handling (Unit) — 30 min
- [x] T11: Borrow safety review (Code Review) — 1 hour

**Total P1**: ~6.5 hours

### P2/P3 Tests (Extended Coverage)

**Purpose**: Edge cases, performance baseline, restart validation

- [x] T12: Redeploy scenario (E2E) — 1.5 hours
- [x] T13: Performance baseline (Benchmark) — 1 hour
- [x] T14: Nested runners (Unit) — 30 min

**Total P2/P3**: ~3 hours

---

## Resource Estimates

### Test Development Effort

| Priority | Count | Hours/Test | Total Hours | Notes |
|----------|-------|------------|-------------|-------|
| P0 | 5 | 3–5 | 15–25 | Complex: cancellation, design review |
| P1 | 6 | 1.5–2 | 10–20 | Standard: happy paths, error cases, isolation |
| P2 | 2 | 2–3 | 5–10 | Perf baseline, redeploy simulation |
| P3 | 1 | 2–5 | 2–5 | Exploratory edge case |
| **Total** | **14** | **–** | **32–60** | **~1–1.5 weeks (2 devs)** |

### Prerequisites

**Test Data:**
- Result type factory (customizable success/error)
- Simulated background work (configurable delay, success/panic)

**Tooling:**
- Rust test framework (tokio or async-std for async runtime)
- Resource leak detector (valgrind or custom drop tracking)
- Concurrency tester (test multiple runners, loom if available)

**Environment:**
- Local dev environment with async runtime
- CI job for running P0/P1 on every PR

---

## Quality Gate Criteria

### Pass/Fail Thresholds

- **P0 pass rate**: 100% (no exceptions; blocks release)
- **P1 pass rate**: ≥95% (waiver required for failures)
- **P2/P3 pass rate**: ≥80% (informational)
- **High-risk mitigations**: 100% complete or approved waivers before release

### Coverage Targets

- **Critical paths** (T1, T2, T3): 100%
- **Cancellation/cleanup** (T3, T4, T6): 100%
- **Concurrent scenarios** (T7): ≥95%
- **Error cases** (T8, T10): ≥90%
- **Design compliance** (T5, T6, T11): 100% via code review

### Non-Negotiable Requirements

- [ ] All P0 tests pass (T1–T5)
- [ ] No high-risk (≥6) items unmitigated: R1, R2, R3, R5
- [ ] Code review confirms ownership/lifecycle design (T5)
- [ ] Cancellation safety validated (T3)
- [ ] Resource cleanup validated (T4)
- [ ] No unvetted assumptions; all unknowns documented

---

## Mitigation Plans

### R1: Cancellation Safety When Owner Drops Future (Score: 9 — CRITICAL)

**Mitigation Strategy:**
1. Design Runner to implement cancel-safe Drop semantics
2. Test T3: Drop future at each suspension point; verify no lost work
3. Validate against RP-ASYNC-005: "Cancellation safety and async cleanup are explicit"
4. Code review ensures no `task::spawn` without explicit cancellation handling

**Owner:** Dev Lead  
**Timeline:** Design phase + Pre-release  
**Status:** Planned  
**Verification:** T3 integration test; code review sign-off

### R2: Task Cleanup on Abandonment (Score: 6 — MITIGATE)

**Mitigation Strategy:**
1. Implement explicit Drop for Runner that cancels background work
2. Test T4: Verify no resource leaks when runner dropped mid-execution
3. Validate against RP-ASYNC-006: "Spawned tasks have owners and supervision"
4. Document expected behavior in docstring

**Owner:** QA Lead  
**Timeline:** Implementation + Integration testing  
**Status:** Planned  
**Verification:** T4 integration test + resource leak detector

### R3: Unclear Task Ownership/Lifecycle (Score: 6 — MITIGATE)

**Mitigation Strategy:**
1. Architect designs explicit ownership model: Runner owns the task, drop cancels it
2. Document in code: "Owner may await result or drop to cancel; both are safe"
3. Test T5: Code review validates CORE-003 (ownership/lifecycle) and CORE-009 (explicit cleanup)
4. Confirm no implicit task detachment or zombie tasks

**Owner:** Architect  
**Timeline:** Design phase  
**Status:** Planned  
**Verification:** Code review; design document; T5 checklist

### R5: Service Redeploy with Running Job (Score: 6 — MITIGATE)

**Mitigation Strategy:**
1. Document expected behavior: runner is in-memory; redeploy loses running jobs
2. Test T12: E2E simulation of redeploy with active runner (verify graceful shutdown)
3. Assess against AC2: "behave predictably if owner stops waiting"
4. No persistence layer required; job loss on redeploy is acceptable

**Owner:** QA Lead  
**Timeline:** Integration testing  
**Status:** Planned  
**Verification:** T12 E2E test; deployment documentation

---

## Assumptions and Dependencies

### Assumptions

1. Runner is single-threaded cooperative (async/await, no thread::spawn)
2. Background work is CPU-bound or I/O-bound async code (not blocking syscalls)
3. Service has async runtime (tokio or similar) already available
4. "Abandon" means dropping the future; no explicit cancel API needed (Drop suffices)
5. No persistence; job loss on service restart is acceptable

### Dependencies

1. Feature code skeleton available — Required for T1 (sprint start)
2. Async runtime environment (tokio/async-std) — Required for all async tests
3. Code review process — Required for T5, T6, T11 (design validation)
4. CI job for running P0 tests — Required before merge to main

### Risks to Plan

- **Risk**: Async design complexity may uncover cancellation bugs late
  - **Impact**: Delays release; potential production outages
  - **Contingency**: T3 runs early and frequently; code review for each change

- **Risk**: Redeploy behavior might not be acceptable to product
  - **Impact**: May require persistence layer (out of scope)
  - **Contingency**: Document clearly in story; get PM sign-off early

---

## Follow-on Workflows (Manual)

- Run `bmad-atdd` to generate failing P0 tests (once design approved)
- Run `bmad-automate` for broader test coverage once implementation exists
- Run `nfr-assess` after implementation to validate reliability/performance thresholds

---

## Approval

**Test Design Approved By:**

- [ ] Product Manager: (TBD) Date: (TBD)
- [ ] Tech Lead: (TBD) Date: (TBD)
- [ ] QA Lead: (TBD) Date: (TBD)

**Comments:**

---

## Interworking & Regression

| Service/Component | Impact | Regression Scope |
|---|---|---|
| Service deployment pipeline | Startup/shutdown behavior on redeploy | Verify existing shutdown tests still pass with Runner cleanup |
| Async runtime (tokio) | Async work spawning | Verify no new blocking calls starve executor |
| Logging/monitoring | Task lifecycle visibility | Ensure task start/cancel/complete events are observable |

---

## Appendix

### Knowledge Base References

- `risk-governance.md` — Risk classification framework (probability × impact matrix)
- `probability-impact.md` — Risk scoring methodology (1-9 scale)
- `test-levels-framework.md` — Test level selection (Unit/Integration/E2E)
- `test-priorities-matrix.md` — P0-P3 prioritization criteria

### RDX-TEA Async Rules Applied

- **RP-ASYNC-005**: Cancellation safety and async cleanup are explicit (R1, R2)
- **RP-ASYNC-006**: Spawned tasks have owners and supervision (R2, R3)
- **RP-ASYNC-003**: Keep blocking work off async workers (R4)
- **RP-ASYNC-004**: Do not carry sync guards across await (R6)
- **CORE-003**: Ownership and lifecycle before implementation (R3)
- **CORE-009**: Make cleanup, cancellation, and task ownership explicit (R2, R3)
- **CORE-008**: Errors are part of the specification (T8, T10)

### Related Documents

- Story: `_bmad-run/story.md`
- RDX-TEA Active Context: `_bmad/rdx-tea/runtime/test-design/ruleop-cand-003-test-design-async-rep03/active-context.md`

---

**Generated by**: BMad TEA Agent - Master Test Architect  
**Workflow**: `bmad-testarch-test-design` (Epic-Level Mode)  
**Version**: 4.0 (BMad v6 + RDX-TEA)
