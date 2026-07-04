---
workflowStatus: 'completed'
totalSteps: 5
stepsCompleted: ['step-01-detect-mode', 'step-02-load-context', 'step-03-risk-and-testability', 'step-04-coverage-plan', 'step-05-generate-output']
lastStep: 'step-05-generate-output'
nextStep: ''
lastSaved: '2026-07-04'
inputDocuments:
  - story: '_bmad-run/story.md'
  - activeBundles: '_bmad/rdx-tea/runtime/test-design/ruleop-cand-001-test-design-async-rep01/active-context.md'
  - knowledgeFragments:
    - 'risk-governance.md'
    - 'probability-impact.md'
    - 'test-levels-framework.md'
    - 'test-priorities-matrix.md'
outputArtifacts:
  - '_bmad-output/test-design-epic-1.md'
---

# Test Design Workflow Progress

## Step 1: Mode Detection & Prerequisites

### Mode Selected: Epic-Level

**Rationale:** 
- Epic requirements provided with acceptance criteria
- No PRD/ADR present
- Focus is on single feature: background task runner for async job management

### Prerequisites Met
- ✅ Epic-level requirements (product context, acceptance criteria, scope)
- ✅ Architecture context (async task runner pattern)
- ✅ Risk context (job abandonment, service redeploy scenarios)

### Epic Summary
- **Goal:** Background task runner for long-running async work
- **Key Behaviors:** 
  - Job spawning and result awaiting
  - Handling owner disconnect
  - Service redeployment during job execution
- **Out of Scope:** Public API, persistence

**Status:** Ready to proceed to Step 2 (Load Context)

## Step 2: Load Context & Knowledge Base

**Configuration:**
- Rust backend project (Cargo.toml detected)
- Sequential execution mode
- No existing test directory found
- Stack type: backend (async infrastructure)

**Loaded Fragments:**
- risk-governance.md (risk scoring matrix, gatekeeping)
- probability-impact.md (1-9 scoring scale)
- test-levels-framework.md (unit/integration/E2E guidance)
- test-priorities-matrix.md (P0-P3 prioritization)

## Step 3: Risk & Testability Assessment

### High-Priority Risks

**Risk 2: Async Task Ownership & Cleanup (CRITICAL)**
- Score: 9/9 (BLOCK until resolved)
- Category: TECH
- Probability: 3 (Likely) × Impact: 3 (Critical)
- Mitigation: Explicit task ownership; supervised spawning (RP-ASYNC-006); shutdown tests
- Owner: Implementation team

**Risk 3: Cancellation Safety (MITIGATE)**
- Score: 6/9
- Category: TECH
- Probability: 2 (Possible) × Impact: 3 (Critical)
- Mitigation: Document cancel-safe operations; test cancellation scenarios (RP-ASYNC-005)
- Owner: Implementation team

**Risk 1: Job Abandonment (MONITOR)**
- Score: 4/9
- Category: BUS
- Probability: 2 (Possible) × Impact: 2 (Degraded)
- Mitigation: Test explicit shutdown path; define resource cleanup guarantees

**Risk 4: Send Error Handling (MONITOR)**
- Score: 4/9
- Category: TECH
- Probability: 2 (Possible) × Impact: 2 (Degraded)
- Mitigation: Explicit channel lifecycle contract; log/handle closed-receiver errors (RP-ASYNC-009)

## Step 4: Coverage Plan & Execution Strategy

### P0 Critical Tests (Async Ownership)
1. Task ownership explicitly initialized on spawn (Unit) — RP-ASYNC-006
2. Spawned task awaited or explicitly supervised (Integration) — RP-ASYNC-006
3. Panic in spawned task is observed/logged (Integration) — RP-ASYNC-006, CORE-008
4. Background job completes normally (Integration) — acceptance criterion

### P1 High-Priority Tests (Cancellation & Cleanup)
5. Dropped future doesn't leak state (Unit) — RP-ASYNC-005
6. Owner receives result when awaiting (Integration) — acceptance criterion
7. Owner disconnect → graceful cleanup (Integration) — story requirement
8. Spawned task halts on receiver close (Integration) — RP-ASYNC-009

### P2 Medium-Priority Tests (Resilience)
9. Service redeploy during job execution (Integration) — story requirement
10. Concurrent runner operations fairness (Stress) — RP-ASYNC-007
11. Resource cleanup under load (Stress) — RP-ASYNC-006

### Execution Strategy
- **PR Gate**: P0 + P1 tests (~10–15 min)
- **Nightly**: P2 stress tests (~30 min)

### Resource Estimates
- P0: ~20–30 hours
- P1: ~15–25 hours
- P2: ~10–20 hours
- **Total: ~45–75 hours**

### Quality Gates
✅ P0 pass = 100%
✅ P1 pass ≥ 95%
✅ Task ownership validated (RP-ASYNC-006)
✅ Cancellation safety tested (RP-ASYNC-005)
✅ Risk score ≥6 mitigations complete
