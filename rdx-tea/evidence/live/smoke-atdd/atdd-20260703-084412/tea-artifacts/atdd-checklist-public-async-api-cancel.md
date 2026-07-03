---
stepsCompleted: ['step-01-preflight-and-context', 'step-02-generation-mode', 'step-03-test-strategy', 'step-04-generate-tests', 'step-04c-aggregate', 'step-05-validate-and-complete']
lastStep: 'step-05-validate-and-complete'
lastSaved: '2026-07-03T08:48:30Z'
storyId: 'public-async-api-cancel'
storyKey: 'public-async-api-cancel'
storyFile: '/private/tmp/rdx-tea-live-B2/_bmad-run/story.md'
atddChecklistPath: '/private/tmp/rdx-tea-live-B2/_bmad-output/test-artifacts/atdd-checklist-public-async-api-cancel.md'
generatedTestFiles: ['src/lib.rs']
inputDocuments: ['_bmad-run/story.md', 'story-tags.txt', '_bmad/tea/config.yaml', 'knowledge/test-quality.md', 'knowledge/test-levels-framework.md', 'knowledge/test-priorities-matrix.md']
---

# ATDD Checklist: Public Async API with Cancellation Semantics

## Story Summary

**Story**: Expose `create_user(name)` as a public async API in `src/api.rs`

**Tags**: `api`, `async`

**Story File**: `_bmad-run/story.md`

**Test Stack**: Backend (Rust/tokio)

---

## TDD Red Phase Status ✅

### Test Generation Complete

- **API Tests**: 8 red-phase scaffolds generated (all with `#[ignore]`)
- **E2E Tests**: N/A (backend-only project)
- **Total Test Count**: 8
- **TDD Phase**: RED (tests use `#[ignore]` and will FAIL until feature implemented)

### Test Location

- **File**: `src/lib.rs`
- **Module**: `tests_create_user_api`
- **Status**: All tests marked with `#[ignore = "RED PHASE: Scaffold test..."]`

---

## Acceptance Criteria Coverage

### ✅ Criterion 1: API Signature and Return Type

**Expected**: The public function returns `Result<u64, String>` and is `pub async fn`.

**Tests Covering This**:
1. `test_create_user_signature_is_public_async` [P0] — Verifies return type and Ok/Err variants
2. `test_create_user_happy_path_valid_name` [P0] — Happy path returns Ok(user_id)
3. `test_create_user_validation_empty_name` [P0] — Validation returns Err(String)

**RDX Rules Applied**: CORE-001 (Contract before code)

---

### ✅ Criterion 2: Cancellation Semantics Explicit

**Expected**: Cancellation semantics are explicit (per Core-009 and RP-ASYNC-006).

**Tests Covering This**:
1. `test_create_user_cancellation_on_drop` [P1] — Task lifecycle and cancellation behavior
2. `test_create_user_handles_spawn_errors` [P0] — Error propagation from spawned task
3. `test_create_user_concurrent_calls` [P1] — Concurrent task safety

**RDX Rules Applied**:
- CORE-009: Make cleanup, cancellation, task ownership explicit
- RP-ASYNC-006: Spawned tasks have owners and supervision
- RP-ASYNC-001: Async trait future contract

---

### ✅ Criterion 3: Timeouts Respected

**Expected**: Operations respect timeout boundaries.

**Tests Covering This**:
1. `test_create_user_respects_deadline` [P1] — Timeout enforcement and graceful handling
2. `test_create_user_cancellation_on_drop` [P1] — Cancellation/timeout under deadline pressure

**RDX Rules Applied**: RP-ASYNC-005 (Cancellation safety and async cleanup)

---

### ✅ Criterion 4: Test Coverage

**Expected**: Tests cover API boundary, async cancel, API validation failure.

**Tests Addressing Boundary Validation**:
1. `test_create_user_validation_empty_name` [P0] — Empty input validation
2. `test_create_user_validation_name_too_long` [P1] — Boundary input validation
3. `test_create_user_handles_spawn_errors` [P0] — Error propagation

---

## Priority Distribution

| Priority | Count | Rationale |
|----------|-------|-----------|
| **P0**   | 5     | API contract, signature, error handling, validation — critical path |
| **P1**   | 3     | Cancellation semantics, timeouts, concurrency — async governance (RDX) |
| **P2**   | 0     | N/A for red phase |
| **P3**   | 0     | N/A for red phase |

---

## RDX Governance Applied

### Core Rules (Always-On)

| Rule | Application |
|------|-------------|
| **CORE-001** | API contract verified: `pub async fn(String) -> Result<u64, String>` |
| **CORE-004** | Async boundary handling (spawn/join error propagation) |
| **CORE-009** | Explicit task ownership, cancellation, cleanup — 3 tests dedicated |

### Async Pack Rules (RP-ASYNC-*)

| Rule | Application |
|------|-------------|
| **RP-ASYNC-001** | Async future contract (public async fn signature) |
| **RP-ASYNC-005** | Cancellation safety and deadline respect (test #7) |
| **RP-ASYNC-006** | Spawned task ownership and supervision (test #6, #8) |

---

## Test Files Generated

### `src/lib.rs`

```rust
pub mod api;
pub use api::create_user;

#[cfg(test)]
mod tests_create_user_api {
    // 8 red-phase integration tests, all with #[ignore]
    // Test numbers: 1-8
}
```

**All 8 tests use `#[ignore]` attribute** — equivalent to `test.skip()` in TypeScript.

**Tests will FAIL when run** (red phase) until the implementation satisfies the assertions.

---

## Fixture Needs

None for red phase. Fixtures (test data, mocks) will be created during green phase when tests are activated.

---

## Knowledge Fragments Applied

- `test-quality` — Red-phase scaffolding rules
- `test-levels-framework` — Unit vs. integration selection
- `test-priorities-matrix` — P0/P1 prioritization
- `test-healing-patterns` — Async test patterns

---

## Next Steps (Task-by-Task Activation)

### Step 5: Validate and Complete

- ✅ TDD red phase validation (all tests marked `#[ignore]`)
- Run lint checks on generated test code
- Confirm acceptance criteria coverage complete

### After Red Phase Passes

1. Implement `create_user` function in `src/api.rs` to satisfy acceptance criteria
2. Remove `#[ignore]` from tests as they pass (task-by-task activation)
3. Update test file as implementation details emerge (green phase)
4. Refactor if needed (refactor phase)

### Acceptance Criteria for Completion

- [ ] All 8 red-phase tests in `src/lib.rs` pass with assertions checking expected behavior
- [ ] Signature: `pub async fn create_user(name: String) -> Result<u64, String>`
- [ ] Cancellation semantics explicit (no orphaned spawns, graceful shutdown)
- [ ] Timeout behavior tested and working
- [ ] Validation logic rejects empty/oversized names with descriptive errors

---

## Summary

**Red-phase ATDD workflow complete.** 8 integration test scaffolds generated for Rust async API, covering all acceptance criteria with explicit RDX governance rules (Core-001, Core-004, Core-009, RP-ASYNC-*). Tests use `#[ignore]` and are ready for task-by-task activation during development.

**Status**: 🔴 TDD RED — Ready for implementation and green phase.
