---
workflowStatus: 'completed'
totalSteps: 5
stepsCompleted: ['step-01-detect-mode', 'step-02-load-context', 'step-03-risk-and-testability', 'step-04-coverage-plan', 'step-05-generate-output']
lastStep: 'step-05-generate-output'
nextStep: ''
lastSaved: '2026-07-04'
---

# Test Design Progress

## Step 1: Detect Mode & Prerequisites

### Mode Detection Result
**Selected Mode: Epic-Level Test Design**

**Rationale:**
- Story describes a concrete epic: "background task runner for internal service"
- Acceptance criteria provided (3 bullet points)
- Risk scope: async lifecycle, spawn behavior, abandonment handling
- No PRD/ADR available; epic + acceptance criteria → Epic-Level Mode

### Prerequisite Validation
✓ Epic requirements present (story.md with acceptance criteria)
✓ Architecture context available (RDX-TEA async pack, CORE rules)
✓ Risk tags: async (from tags.txt)

### Confirmation
Proceeding with **Epic-Level Test Design** to produce a test plan validating the Runner type's async behavior under normal and abandoned-task conditions.

---

## Step 2: Load Context & Knowledge Base

### Configuration Loaded
- test_artifacts: `_bmad-output/test-artifacts`
- project_name: test-design-async
- tea_execution_mode: sequential ✓

### Project Artifacts (Epic-Level)
- ✓ Story: background task runner with acceptance criteria
- ✗ PRD: not present
- ✗ Architecture/tech-spec: not present (using RDX-TEA bundle instead)

### Knowledge Fragments Loaded (Core Tier)
1. **risk-governance.md** — Risk scoring, probability×impact matrix (1-9 scale)
2. **probability-impact.md** — Probability/impact definitions (1-3 scale)
3. **test-levels-framework.md** — Unit/integration/E2E decision criteria
4. **test-priorities-matrix.md** — P0-P3 prioritization criteria
5. **RDX-TEA Active Context** — 18 core rules + 9 async pack rules

### Existing Test Coverage
- No existing test directories found in repository
- Starting fresh test design

### Key Inputs Confirmed
✓ Epic requirements with acceptance criteria
✓ Risk governance framework for P0-P3 assignment
✓ Async-specific rules from RDX-TEA (RP-ASYNC-001 through RP-ASYNC-009)
✓ Core test design principles (CORE-001 through CORE-018)

---

## Step 3: Testability & Risk Assessment

### Risk Assessment Matrix

**High-Level Risks (Probability × Impact):**

| Risk | Category | P | I | Score | Action | Key Test Areas |
|------|----------|---|---|-------|--------|-----------------|
| Cancellation safety when owner drops future | TECH | 3 | 3 | **9** | **BLOCK** | Test dropped futures; verify cancel-safe implementation |
| Task cleanup on abandonment | TECH | 3 | 2 | **6** | **MITIGATE** | Test explicit cleanup; verify no resource leaks |
| Unclear task ownership/lifecycle | TECH | 2 | 3 | **6** | **MITIGATE** | Verify explicit owner, supervision, and completion contract |
| Service redeploy with running job | BUS | 2 | 3 | **6** | **MITIGATE** | Test restart/recovery semantics after redeploy |
| Async worker pool starvation | PERF | 2 | 2 | **4** | **MONITOR** | Verify non-blocking async APIs (no `block_on`) |
| Sync guard lifetimes across await | TECH | 2 | 2 | **4** | **MONITOR** | Verify borrow/lock scope around suspension points |

### Rationale (RDX-TEA Async Rules)

**Score 9 (CRITICAL - Blocks Release):**
- RP-ASYNC-005: Cancellation safety is explicit contract; dropped futures must not lose critical state
- CORE-009: Cleanup/cancellation/task ownership must be explicit

**Score 6 (HIGH - Mitigate Required):**
- R2: RP-ASYNC-005, RP-ASYNC-006 — explicit cleanup and task supervision
- R3: CORE-003, CORE-009 — ownership and lifecycle must be defined before implementation
- R5: Story acceptance criterion: "behave predictably if owner stops waiting"

**Score 4 (MEDIUM - Monitor):**
- R4: RP-ASYNC-003 — no blocking work on async workers
- R6: RP-ASYNC-004 — no sync guards across `.await`

### NFR Assessment

No explicit NFRs in story; acceptance criteria focus on correctness (cancellation, cleanup, predictability).

### Findings Summary

**Critical Path to Release:**
1. Design and test cancellation safety (R1 = score 9)
2. Define and test explicit task ownership/supervision (R3)
3. Test cleanup on abandon (R2)
4. Test service redeploy behavior (R5)

---

## Step 4: Coverage Plan & Execution Strategy

### Test Coverage Matrix

**P0 (CRITICAL - Blocks Release):**
- T1: Runner spawns background task successfully (Unit + Integration)
- T2: Owner receives result when task completes (Integration + E2E)
- T3: Dropped runner cancels background work (Integration) — **R1 score 9**
- T4: No resource leaks on abandon (Integration) — **R2 score 6**
- T5: Task has explicit owner/supervisor (Code Review) — **R3 score 6**

**P1 (HIGH - Should Test):**
- T6: Cleanup explicit on drop (Unit + Code Review)
- T7: Multiple concurrent runners isolated (Integration)
- T8: Runner returns Err on task failure (Integration)
- T9: Owner can abort waiting (Integration) — **R5 abandon semantics**
- T10: Task panic propagates (Unit)
- T11: No sync guards across await (Code Review) — **RP-ASYNC-004**

**P2 (MEDIUM - Nice to Test):**
- T12: Service redeploy with running job (E2E simulation) — **R5 score 6**
- T13: Minimal spawn overhead (Benchmark) — **R4 score 4**

**P3 (LOW - If Time Permits):**
- T14: Nested runners don't deadlock (Unit)

### Test Level Distribution
- **Unit Tests**: T1, T10, T14 (logic, errors, edge cases)
- **Integration Tests**: T2-T4, T7-T9, T12 (async/cancel/cleanup/isolation)
- **Code Review**: T5, T6, T11 (ownership, cleanup design, borrow safety)
- **Performance**: T13 (spawn overhead benchmark)

### Execution Strategy
- **PR Gate**: T1-T5 (P0) + T6-T9 (P1 core) — **~5–10 min**
- **Nightly**: T10-T14 (P2-P3) — **~2–5 min**

### Resource Estimates
- **P0 implementation & testing**: ~15–25 hours
- **P1 implementation & testing**: ~10–20 hours
- **P2-P3 implementation & testing**: ~5–10 hours
- **Code review & design verification**: ~5–10 hours
- **Total effort**: ~35–65 hours

### Quality Gates
✓ P0 pass rate = 100% (no exceptions)  
✓ P1 pass rate ≥ 95%  
✓ Code review confirms: ownership model (T5), cleanup design (T6), borrow safety (T11)  
✓ R1 mitigation (cancellation safety) complete and validated  
✓ R2 mitigation (cleanup) complete and validated  
✓ High-risk items (score ≥6) addressed before release
