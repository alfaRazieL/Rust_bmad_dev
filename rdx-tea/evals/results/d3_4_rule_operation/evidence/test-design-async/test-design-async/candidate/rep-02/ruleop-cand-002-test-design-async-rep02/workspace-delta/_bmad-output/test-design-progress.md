---
workflowStatus: 'completed'
totalSteps: 5
stepsCompleted: ['step-01-detect-mode', 'step-02-load-context', 'step-03-risk-and-testability', 'step-04-coverage-plan', 'step-05-generate-output']
lastStep: 'step-05-generate-output'
nextStep: ''
lastSaved: '2026-07-04'
inputDocuments:
  - knowledge/risk-governance.md
  - knowledge/probability-impact.md
  - knowledge/test-levels-framework.md
  - knowledge/test-priorities-matrix.md
  - knowledge/webhook-risk-guidance.md
  - knowledge/timing-debugging.md
outputFile: test-artifacts/test-design-epic-1.md
---

# Step 1: Mode Detection & Prerequisites

## Mode Decision: Epic-Level

**Decision:** Epic-Level Test Design

**Reasoning:**
- Story provided: Background task runner feature with clear acceptance criteria
- No system-level PRD or ADR documents present
- Single epic feature with acceptance criteria
- Perfect fit for Epic-Level mode

## Prerequisites Check: ✅ Complete

**Epic-Level mode requires:**
- ✅ Epic and story requirements with acceptance criteria (provided in _bmad-run/story.md)
- ✅ Architecture context (available from story context)

**Available inputs:**
- Story: Background task runner with 3 acceptance criteria
- Tags: "async"
- Scope: Internal type, not public API

---

# Step 2: Context & Knowledge Loading

## Configuration Analysis

**Project Stack:** Rust backend library (Cargo.toml detected)
- Package: test-design-async-latent
- Edition: 2021
- No existing tests directory
- Internal library type

## Knowledge Fragments Loaded

**Core (Epic-Level Required):**
- ✅ risk-governance.md — Risk scoring and gatekeeping patterns
- ✅ probability-impact.md — P×I matrix (1-9 scale) for risk assessment
- ✅ test-levels-framework.md — Unit/Integration/E2E decision guidance
- ✅ test-priorities-matrix.md — P0-P3 priority levels and criteria

**Extended (Async-Specific):**
- ✅ webhook-risk-guidance.md — Async/event-driven risk patterns
- ✅ timing-debugging.md — Race condition and deterministic wait patterns

## Project Artifacts Summary

**Epic Requirements:**
- Background task runner with async `run` method
- Owner starts job and awaits result
- Must handle abandoned wait scenarios (service redeploy)

**Out of Scope:**
- Public API/crate publication
- Persistence

---

# Step 3: Testability & Risk Assessment

## Risk Assessment Matrix

### Background Task Runner Feature: Risk Breakdown

#### TECH-001: Async/Await Race Conditions
- **Description:** Timing issues between job completion and owner awaits; non-deterministic test failures in concurrent scenarios
- **Category:** TECH (Technical)
- **Probability:** 3 (High — async code inherently has race condition risks)
- **Impact:** 2 (Degraded — tests fail intermittently but core logic may work)
- **Score:** 3 × 2 = **6** → MITIGATE
- **Owner:** Implementation reviewer
- **Mitigation:** Deterministic test patterns with explicit state waits (no hard timeouts); defer-based cleanup verification
- **Timeline:** Design phase (tests before implementation)
- **Evidence sources:** Integration tests with concurrent worker scenarios; timing-sensitive negative paths

#### TECH-002: Abandoned Task Lifecycle (Service Redeploy)
- **Description:** Owner stops waiting before job completes; task leaks memory/resources; no cleanup contract
- **Category:** TECH (Technical)
- **Probability:** 3 (High — service deploys frequently per acceptance criteria)
- **Impact:** 3 (Critical — task continues consuming resources indefinitely)
- **Score:** 3 × 3 = **9** → BLOCK (automatic failure; must be resolved before release)
- **Owner:** Implementation owner
- **Mitigation:** Design contract for abandoned task cleanup; implement Drop/finalize semantics; test both graceful and abrupt abandonment
- **Timeline:** Design review before implementation
- **Evidence sources:** Integration tests for abandoned wait scenarios; resource monitoring; cleanup verification fixtures

#### TECH-003: Job Completion Notification Race
- **Description:** Job completes before owner calls `.await`; result may be lost if not stored
- **Category:** TECH (Technical)
- **Probability:** 2 (Medium — depends on job duration vs. owner timing)
- **Impact:** 3 (Critical — owner receives no result notification)
- **Score:** 2 × 3 = **6** → MITIGATE
- **Owner:** Implementation owner
- **Mitigation:** Store job result in shared state; verify result delivery independent of wait timing
- **Timeline:** Design phase
- **Evidence sources:** Unit tests for result storage; integration tests with zero-delay job completion; edge case scenarios

#### TECH-004: Concurrent Worker Isolation
- **Description:** Multiple concurrent Runner instances may interfere (shared state, leaked handles); tests need parallel safety
- **Category:** TECH (Technical)
- **Probability:** 2 (Medium — depends on architecture)
- **Impact:** 2 (Degraded — flaky tests or subtle cross-contamination)
- **Score:** 2 × 2 = **4** → MONITOR
- **Owner:** Test architect
- **Mitigation:** Scoped test fixtures; parallel-safe task ID isolation; fixture cleanup with verification
- **Timeline:** Test design phase
- **Evidence sources:** Tests with `fullyParallel: true`; worker isolation verification

#### BUS-001: Unclear Acceptance Criteria: "Predictable Behavior"
- **Description:** AC#2 states "behave predictably if owner stops waiting" — no definition of "predictable"; leaves implementation contract ambiguous
- **Category:** BUS (Business)
- **Probability:** 2 (Medium — likely to cause rework during review)
- **Impact:** 2 (Degraded — scope creep and test rework)
- **Score:** 2 × 2 = **4** → MONITOR
- **Owner:** Product owner + implementation owner
- **Mitigation:** Clarify AC#2 with explicit scenarios: "task continues (Fire-and-Forget)" vs. "task cleaned up immediately (Cancellation)" vs. "task completes but owner never knows"
- **Timeline:** Pre-implementation clarification
- **Evidence sources:** Acceptance criteria refinement; documented behavior contract

### Risk Summary

**Critical Risks (Score = 9):**
- TECH-002: Abandoned task lifecycle — **BLOCKS RELEASE** until design contract exists

**High Risks (Score = 6):**
- TECH-001: Async race conditions (mitigation: deterministic tests)
- TECH-003: Job completion notification (mitigation: shared state + result storage)

**Medium Risks (Score = 4):**
- TECH-004: Concurrent worker isolation (mitigation: test fixture design)
- BUS-001: Acceptance criteria clarity (mitigation: AC refinement pre-implementation)

## Testability Assessment (Epic-Level)

### ✅ Strong Points

1. **Clear Requirements:** Story provides acceptance criteria (three clear statements)
2. **Internal Scope:** No public API — easier to refactor for testability without breaking consumers
3. **Async Pattern:** Well-understood patterns exist (Rust futures, tokio, async/await)
4. **Integration Testing Opportunity:** Can test with realistic async scenarios (timing, cancellation, redeploy simulation)

### 🚨 Testability Concerns

1. **Abandoned Wait Ambiguity:** AC#2 doesn't specify cleanup behavior — creates testing uncertainty
   - **Impact:** Can't write precise tests until contract is defined
   - **Action:** Clarify "predictable behavior" definition with examples

2. **Service Redeploy Simulation:** Testing the "redeploy" scenario requires architecture knowledge
   - **Impact:** May need test helpers for task state inspection and cleanup verification
   - **Action:** Plan fixture design to simulate abandon scenarios (drop Runner without await)

3. **Race Condition Coverage:** Async patterns are inherently non-deterministic
   - **Impact:** Tests need explicit state waits, not time-based waits
   - **Action:** Use timing-debugging patterns (state polling, signal channels)

4. **Result Capture Timing:** Job completion before owner awaits requires shared state verification
   - **Impact:** Need tests at different job-completion timings (immediate, delayed, timeout)
   - **Action:** Design parametrized tests with variable job durations

---

# Step 4: Coverage Plan & Execution Strategy

## Test Coverage Matrix

### P0: Critical Path Tests (Blocks Release if Failed)

#### AC-001: Runner Provides `run` Method
| Scenario | Test Level | Description | Risk Addressed | Evidence |
|----------|-----------|-------------|-----------------|----------|
| U-001: Valid async method signature | Unit | Type-check that `Runner::run()` exists, is async, returns appropriate type | TECH-001 (race condition baseline) | Compilation + unit test |
| I-001: Happy path — job starts and completes | Integration | Owner calls `.await`, job runs to completion, result is returned | TECH-003 (result delivery) | Integration test with mock job |
| I-002: Result available regardless of timing | Integration | Job completes before owner calls `.await`; result still captured | TECH-003 (completion race) | Parametrized test: job duration variants (0ms, 100ms, 5s) |
| I-003: Multiple concurrent runners | Integration | 2+ Runner instances run concurrently; results isolated | TECH-004 (worker isolation) | Parametrized test: N=2,5,10 concurrent jobs |

#### AC-002: Predictable Behavior When Owner Stops Waiting
| Scenario | Test Level | Description | Risk Addressed | Evidence |
|----------|-----------|-------------|-----------------|----------|
| **[BLOCKER]** I-004: Drop-without-await cleanup | Integration | Owner drops Runner without calling `.await`; verify cleanup (no leaks, finalize runs) | TECH-002 (abandoned task = risk 9) | Test: drop() semantics; resource inspection (task count, heap) |
| I-005: Task continues execution after drop | Integration | Verify whether task is cancelled or continues; document behavior | TECH-002 (clarify AC#2) | Test: background state inspection post-drop |
| I-006: No panic on dropped Runner | Unit/Integration | Ensure drop doesn't panic or leave inconsistent state | TECH-002 (safety) | Test: drop() under various states (pending, in-progress, completed) |

#### AC-003: Handle Service Redeploy While Running
| Scenario | Test Level | Description | Risk Addressed | Evidence |
|----------|-----------|-------------|-----------------|----------|
| I-007: Task lifecycle survives mock redeploy | Integration | Simulate redeploy (stop accepting new runs, drain in-flight); verify cleanup | TECH-002 (redeploy scenario) | Integration test with simulated shutdown signal |
| I-008: No resource leak during redeploy | Integration | Monitor memory/task count before, during, and after redeploy simulation | TECH-002 (lifecycle) | Resource profiling test |

### P1: High-Priority Edge Cases

| Scenario | Test Level | Description | Risk Addressed | Evidence |
|----------|-----------|-------------|-----------------|----------|
| I-009: Job panics during execution | Integration | Runner handles panicked job; owner receives error or panic info | TECH-001 (error propagation) | Test: job that panics; verify error is captured |
| I-010: Job times out / takes very long | Integration | Runner handles job exceeding timeout; cancellation/timeout semantics | TECH-001 (timeout handling) | Test: job with 30s+ delay; verify timeout behavior |
| I-011: Owner cancellation via drop while in-progress | Integration | Job in flight, owner drops Runner; verify graceful cancellation | TECH-001 (async cancellation) | Test: cancel mid-job; verify cleanup |
| I-012: Rapid fire: new run called before prior completes | Integration | Multiple `.run()` calls queued; verify no cross-contamination | TECH-004 (worker isolation) | Test: fire 10 jobs in rapid succession; verify results isolation |

### P2: Extended Coverage & Stress

| Scenario | Test Level | Description | Risk Addressed | Evidence |
|----------|-----------|-------------|-----------------|----------|
| I-013: High concurrency stress (50+ tasks) | Integration | Verify no deadlocks, panics, or resource exhaustion under load | TECH-001 (concurrency stress) | Stress test: N=50 concurrent; resource monitor |
| I-014: Result type correctness | Unit | Verify result type matches contract; successful and error variants | TECH-001 (type safety) | Unit test with type inspection |
| I-015: Documentation example correctness | Unit | Code in docs/examples compiles and runs | TECH-001 (maintenance) | Compile and execute doc examples |

### P3: Future & Exploratory

| Scenario | Test Level | Description | Risk Addressed | Evidence |
|----------|-----------|-------------|-----------------|----------|
| E2E-001: Integration with real tokio runtime | E2E | Full integration with production tokio; no mock scheduler | Validation | Tokio-based integration test |

## Execution Strategy

### PR (Block on Failure)
- P0 tests (U-001, I-001 through I-008)
- P1 core tests (I-009, I-010, I-011)
- Target: ~10-15 minutes
- Threshold: 100% pass

### Nightly (Informational)
- P1 extended (I-012)
- P2 stress tests (I-013)
- Target: ~30-45 minutes
- Threshold: ≥95% pass (may allow flaky stress tests with investigation logs)

### Manual / Release (On-Demand)
- P3 exploratory (E2E-001)
- Performance regression benchmarks

## Resource Estimates

| Priority | Effort | Timeline |
|----------|--------|----------|
| P0 | 25–40 hours | 2–3 weeks (async complexity, redeploy simulation) |
| P1 | 20–35 hours | 2–3 weeks (parallel to P0) |
| P2 | 10–30 hours | 1–2 weeks (post-P0/P1 stabilization) |
| P3 | 2–5 hours | Optional, post-release |
| **Total** | **57–110 hours** | **4–6 weeks (with parallel work)** |

**Notes:**
- P0 blocker (TECH-002 cleanup/drop semantics) is critical path; needs architecture clarity first
- Async testing adds complexity (race conditions, deterministic waits); plan for debugging overhead
- Stress tests may be automated post-initial implementation

## Quality Gates

| Gate | Threshold | Enforced | Owner |
|------|-----------|----------|-------|
| P0 tests | 100% pass | PR mandatory | Eng + code review |
| P1 tests | ≥95% pass | PR mandatory | Eng + code review |
| Coverage | ≥80% line coverage | Pre-merge check | CI + code review |
| TECH-002 mitigation | Design review PASS | Pre-implementation | Implementation owner |
| BUS-001 clarity | AC#2 refined with scenarios | Pre-implementation | Product + Eng |
| High-risk (score ≥6) | Mitigation documented | Pre-release | QA + Product |
| Zero panics | 100% panic-safe | Pre-release | Eng + static analysis |
