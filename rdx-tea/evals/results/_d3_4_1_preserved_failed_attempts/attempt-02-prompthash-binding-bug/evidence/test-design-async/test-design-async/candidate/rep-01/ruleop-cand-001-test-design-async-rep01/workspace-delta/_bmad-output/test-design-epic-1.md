---
workflowStatus: 'completed'
totalSteps: 5
stepsCompleted: ['step-01-detect-mode', 'step-02-load-context', 'step-03-risk-and-testability', 'step-04-coverage-plan', 'step-05-generate-output']
lastStep: 'step-05-generate-output'
nextStep: ''
lastSaved: '2026-07-04'
---

# Test Design: Epic 1 - Background Task Runner

**Date:** 2026-07-04
**Author:** Test Architect
**Status:** Draft

---

## Executive Summary

**Scope:** Epic-level test design for background task runner (async job executor)

**Risk Summary:**

- Total risks identified: 4
- High-priority risks (≥6): 2 (CRITICAL blocks)
- Critical categories: TECH (async ownership, cancellation safety)

**Coverage Summary:**

- P0 scenarios: 4 (20–30 hours)
- P1 scenarios: 4 (15–25 hours)
- P2 scenarios: 3 (10–20 hours)
- **Total effort**: ~45–75 hours (~1–2 weeks)

---

## Not in Scope

| Item | Reasoning | Mitigation |
|------|-----------|-----------|
| **Public API / Crate Publication** | Internal type only; no external contract | Document as internal-only; no SemVer requirement |
| **Persistence / State Recovery** | Explicitly out of scope per requirements | Clear documentation of state loss on restart |
| **Performance Optimization** | No baseline performance requirement stated | If needed, add as separate story with CORE-017 profiling evidence |

---

## Risk Assessment

### High-Priority Risks (Score ≥6)

| Risk ID | Category | Description | Probability | Impact | Score | Mitigation | Owner | Timeline |
|---------|----------|-------------|-------------|--------|-------|-----------|-------|----------|
| R-001 | TECH | Async task ownership and lifecycle unclear; risk of unobserved panics, resource leaks, or detached work | 3 | 3 | 9 | Explicit task ownership model; supervised spawning (RP-ASYNC-006); shutdown tests; handle lifecycle audit | Implementation | v1 |
| R-002 | TECH | Cancellation safety during job suspension; partial progress loss or state corruption if future dropped | 2 | 3 | 6 | Document cancel-safe operations; test cancellation scenarios (RP-ASYNC-005); verify no orphaned state | Implementation | v1 |

### Medium-Priority Risks (Score 3-4)

| Risk ID | Category | Description | Probability | Impact | Score | Mitigation | Owner |
|---------|----------|-------------|-------------|--------|-------|-----------|-------|
| R-003 | BUS | Job abandonment: owner disconnects before job completes; invisible resource consumption | 2 | 2 | 4 | Test explicit shutdown path; define resource cleanup guarantees; monitor resource utilization | Implementation |
| R-004 | TECH | Send error handling: receiver closed during transmission; silent result loss or unhandled channel errors | 2 | 2 | 4 | Explicit channel lifecycle contract; log/handle closed-receiver errors (RP-ASYNC-009); test with forced closure | Implementation |

### Low-Priority Risks (Score 1-2)

*No low-priority risks identified for this epic.*

### Risk Category Legend

- **TECH**: Technical/Architecture (flaws, integration, async/concurrency safety)
- **SEC**: Security (access controls, auth, data exposure)
- **PERF**: Performance (SLA violations, degradation, resource limits)
- **DATA**: Data Integrity (loss, corruption, inconsistency)
- **BUS**: Business Impact (UX harm, logic errors, invisible failures)
- **OPS**: Operations (deployment, config, monitoring)

---

## NFR Planning

**Purpose:** Capture epic-specific NFR thresholds, planned validation, and evidence expected for later `nfr-assess`. This is not a final evidence audit.

| NFR Category | Requirement / Threshold | Risk Link | Planned Validation | Evidence Needed |
|--------------|-------------------------|-----------|-------------------|-----------------|
| Reliability | Background job completes without panic or data loss under normal conditions | R-001, R-002 | Integration tests: panic capture, cancellation safety, resource cleanup | Test pass/fail logs; resource profiles |
| Reliability | Owner disconnect results in predictable state (no orphaned tasks) | R-003 | Integration tests: explicit shutdown, resource audit | Shutdown test reports; memory/handle analysis |
| Maintainability | Code structure follows Rust async patterns (RP-ASYNC-006, RP-ASYNC-005 compliance) | R-001, R-002 | Code review + static analysis; compile/check with async lints | Code review checklist; clippy output |

**Unknown thresholds:** Performance targets (latency, throughput) not specified; acceptance criteria use qualitative language ("predictable behavior"). Recommend clarification: e.g., "job must complete within X seconds" or "at least 10 concurrent jobs per runner instance".

---

## Entry Criteria

- [ ] Story markdown with acceptance criteria agreed upon by Dev, QA, PM
- [ ] Rust environment set up (Cargo, rustc, async runtime)
- [ ] Test data factories or fixtures ready (background job payloads)
- [ ] Feature async `run` method deployed to test environment
- [ ] No blocking dependencies on external services

## Exit Criteria

- [ ] All P0 tests passing (task ownership, panic handling, job completion)
- [ ] All P1 tests passing (cancellation safety, shutdown, channel errors)
- [ ] No open high-priority bugs (score ≥6 risks mitigated)
- [ ] Test coverage ≥80% for changed code
- [ ] Code review confirms RP-ASYNC-006 and RP-ASYNC-005 compliance

---

## Test Coverage Plan

### P0 (Critical) - Blocks Core Functionality + High Risk (≥6) + No Workaround

| Requirement | Test Level | Risk Link | Test Count | Owner | Notes |
|-------------|-----------|-----------|-----------|-------|-------|
| Task ownership explicitly initialized on spawn | Unit | R-001 | 1 | Dev | Verify task handle returned and stored; no detached work |
| Spawned task awaited or explicitly supervised | Integration | R-001 | 2 | QA | Happy path + cancellation; confirm RP-ASYNC-006 pattern |
| Panic in spawned task is observed/logged | Integration | R-001 | 1 | QA | Panic must not silently leak; error visibility test |
| Background job completes normally and returns result | Integration | R-001 | 1 | QA | Owner awaits result; verify delivery; confirm no state loss |

**Total P0:** 5 tests, ~20–30 hours

### P1 (High) - Important Features + Medium Risk (3-4) + Common Workflows

| Requirement | Test Level | Risk Link | Test Count | Owner | Notes |
|-------------|-----------|-----------|-----------|-------|-------|
| Dropped future before completion doesn't leak state | Unit | R-002 | 1 | Dev | Cancel-safety validation per RP-ASYNC-005 |
| Owner disconnect results in graceful cleanup | Integration | R-003 | 1 | QA | Job abandonment scenario; verify resource release |
| Spawned task halts on receiver close | Integration | R-004 | 1 | QA | Channel lifecycle; receiver drop triggers cleanup per RP-ASYNC-009 |
| Runner can be awaited multiple times or stored for later polling | Integration | R-001 | 1 | QA | Verify future re-polling or cloning not broken |

**Total P1:** 4 tests, ~15–25 hours

### P2 (Medium) - Secondary Features + Low Risk (1-2) + Edge Cases

| Requirement | Test Level | Risk Link | Test Count | Owner | Notes |
|-------------|-----------|-----------|-----------|-------|-------|
| Concurrent runner operations (fairness, no race conditions) | Stress | R-001 | 1 | QA | Multiple concurrent jobs; verify isolation and fairness per RP-ASYNC-007 |
| Resource cleanup under load (no memory/handle leaks) | Stress | R-001, R-003 | 1 | QA | Spawn many jobs; measure resource release; confirm no leaks |
| Service redeployment during job execution (process restart simulation) | Integration | R-003 | 1 | QA | Simulate mid-job crash; verify state isolation and recovery path |

**Total P2:** 3 tests, ~10–20 hours

### P3 (Low) - Nice-to-Have + Exploratory + Benchmarks

| Requirement | Test Level | Test Count | Owner | Notes |
|-------------|-----------|-----------|-------|-------|
| Documentation and example integration patterns | Documentation | 1 | Dev | Code examples for usage; async lifetimes clarity |
| Performance baseline under normal load | Benchmark | 1 | Optional | Only if CORE-017 profiling evidence requested |

**Total P3:** 2 scenarios, ~2–5 hours (optional)

---

## Execution Order

**Philosophy:** Run all functional tests in PR gate if <15 minutes. Defer only expensive tests (stress, load, chaos) to nightly/weekly.

### PR Gate (~10–15 min)

- **All P0 + P1 tests** (unit + integration): Task ownership, panic handling, cancellation safety, shutdown, receiver close
- Parallelization: Rust test parallelization on stable (default `--test-threads=num_cpus`)

### Nightly/Weekly (~30–60 min)

- **P2 stress tests**: Concurrent operations, resource cleanup under load
- **Service redeploy scenario**: Optional if infrastructure available
- **P3 benchmarks**: If performance baseline is requested

---

## Resource Estimates

### Test Development Effort

| Priority | Count | Hours/Test | Total Hours | Notes |
|----------|-------|-----------|------------|-------|
| P0 | 5 | 4–6 | 20–30 | Complex async patterns, panic tracing, result verification |
| P1 | 4 | 3–6 | 15–25 | Cancellation safety, channel lifecycle, stress scenarios |
| P2 | 3 | 3–7 | 10–20 | Concurrent operations, resource profiling, service restart |
| P3 | 2 | 1–2 | 2–5 | Documentation and optional benchmarks |
| **Total** | **14** | **–** | **~45–75** | **~1–2 weeks** |

### Prerequisites

**Test Fixtures:**
- `BackgroundJobPayload` factory (deterministic test data)
- `MockAsyncRuntime` fixture (local executor for unit tests)
- Resource leak detector (memory/handle tracking)

**Tooling:**
- Rust `#[tokio::test]` macro for async tests
- `tokio-test` for time simulation and race condition detection
- Tracing/logging for panic and error observability
- Optional: `criterion` for benchmarking baseline

**Environment:**
- Local Rust environment (Cargo, rustc 1.70+)
- Tokio async runtime or compatible
- CI environment with time budget for stress tests

---

## Quality Gate Criteria

### Pass/Fail Thresholds

- **P0 pass rate:** 100% (no exceptions; blocks core functionality)
- **P1 pass rate:** ≥95% (triaged failures require waivers)
- **P2 pass rate:** ≥90% (informational; stress tests may be noisy)
- **High-risk mitigations:** 100% complete or approved waivers before merge

### Coverage Targets

- **Critical paths:** ≥80% (task ownership, job completion, panic handling)
- **Async safety patterns:** ≥70% (cancellation, channel closure, resource cleanup)
- **Business logic:** ≥70% (result delivery, error propagation)

### Non-Negotiable Requirements

- [ ] All P0 tests pass (task ownership, panic visibility, job completion)
- [ ] No high-risk (≥6) items unmitigated (R-001 and R-002 verified by tests)
- [ ] Async safety tests pass 100% (RP-ASYNC-006, RP-ASYNC-005 compliance)
- [ ] Cancellation safety validated (dropped futures don't leak state)
- [ ] Code review confirms RP-ASYNC-009 channel error handling

---

## Mitigation Plans

### R-001: Async Task Ownership and Lifecycle (Score: 9 – CRITICAL BLOCKER)

**Mitigation Strategy:**

1. Define explicit task ownership model in type system (e.g., `Runner` type manages handle)
2. Implement supervised spawning: Use `JoinHandle` or similar; never spawn without storing/awaiting
3. Add panic capture: Log panics from spawned tasks to observability system
4. Write P0 tests: Task ownership initialization, panic propagation, cleanup on drop
5. Code review checklist: Verify no detached spawning (RP-ASYNC-006 compliance)

**Owner:** Implementation team

**Timeline:** v1 (must resolve before shipping)

**Status:** Planned

**Verification:** P0 tests (R-001-T001 through R-001-T004) must pass; code review sign-off on RP-ASYNC-006 compliance

### R-002: Cancellation Safety and Partial Progress Loss (Score: 6 – MITIGATE)

**Mitigation Strategy:**

1. Document which operations are cancel-safe (e.g., checkpoint before await)
2. Design partial-progress handling: State updates only after explicit completion checkpoint
3. Write P1 tests: Drop future before completion; verify no orphaned state
4. Test cancellation timeout scenarios: Ensure graceful halt, no resource leaks
5. API guidance: Document cancel-safe contract in Rust doc comments

**Owner:** Implementation team

**Timeline:** v1 (before shipping)

**Status:** Planned

**Verification:** P1 tests (R-002-T001) pass; RP-ASYNC-005 compliance checklist signed off

---

## Assumptions and Dependencies

### Assumptions

1. Tokio async runtime is the primary target (single-threaded or multi-threaded variants supported)
2. Service restart is out of scope for v1; redeploy scenario tested but not guaranteed recovery
3. No persistence layer; job state is in-memory only
4. Owner code is responsible for retrying on result-fetch timeout (no automatic retry)
5. Panic in spawned job is acceptable; captured via logging/observability

### Dependencies

1. Rust async runtime (`tokio` or compatible) — Required for dev env setup
2. Observability/logging system — Required to observe panics and errors
3. CI environment with async-safe test harness — Required for P2 stress tests

### Risks to Plan

- **Risk:** Service redeploy during job leaves orphaned tasks; no recovery mechanism defined
  - **Impact:** Resource waste; potential daemon leaks if service doesn't clean up on shutdown
  - **Contingency:** Document shutdown contract (caller must stop sending jobs before restart); add cleanup hook in `Drop` impl

- **Risk:** Channel closure errors are silently dropped (RP-ASYNC-009 violation)
  - **Impact:** Result loss; owner never sees completion
  - **Contingency:** P1 tests verify closed-receiver behavior; error handling must be explicit and logged

---

## Appendix

### Knowledge Base References

- `risk-governance.md` - Risk classification framework (TECH, SEC, PERF, DATA, BUS, OPS)
- `probability-impact.md` - Risk scoring: probability (1–3) × impact (1–3) = score (1–9)
- `test-levels-framework.md` - Unit (algorithms, logic), Integration (component interaction), E2E (full workflows)
- `test-priorities-matrix.md` - P0 (critical), P1 (high), P2 (medium), P3 (low)

### Related RDX-TEA Active Rules

- **RP-ASYNC-005:** Cancellation safety and async cleanup are explicit
- **RP-ASYNC-006:** Spawned tasks have owners and supervision
- **RP-ASYNC-007:** Bound async queues and fan-out
- **RP-ASYNC-009:** Channel send errors are lifecycle outcomes
- **CORE-008:** Errors are part of the specification
- **CORE-009:** Make cleanup, cancellation, and task ownership explicit

### Related Documents

- Story: `_bmad-run/story.md` (background task runner requirements)
- Active Context Bundle: `_bmad/rdx-tea/runtime/test-design/ruleop-cand-001-test-design-async-rep01/active-context.md`

---

**Generated by:** BMad TEA Test Architect Module
**Workflow:** `bmad-testarch-test-design` + `rdx-tea-test-design` wrapper
**Version:** 4.0 (BMad TEA / RDX v1)
**Run ID:** ruleop-cand-001-test-design-async-rep01
