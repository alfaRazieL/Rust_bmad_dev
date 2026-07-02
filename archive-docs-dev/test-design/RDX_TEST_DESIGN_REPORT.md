# RDX Test Design — Summary Report

**Date:** 2026-06-29
**Branch:** `rdx-improvements`
**Status:** Test architecture complete. Production implementation not yet started.

---

## 1. Documents created in this stage

| File | Purpose |
|------|---------|
| `RDX_TEST_STRATEGY.md` | Test architecture: 9 layers (L0–L8), determinism semantics, phase gates, status taxonomy, CI trust model, R1 vs R2 decision, metrics, flaky-test policy, artifact structure |
| `RDX_TEST_CASES.yaml` | Machine-readable catalog of ~135 test cases with full schema (ID, version, phase, requirement_ids, rule_ids, layer, fixture, steps, expected outputs, gate) |
| `RDX_TEST_TRACEABILITY_MATRIX.md` | Requirement-to-test mapping: every V5/V6 DoD item, every CORE rule, every pack, every status, every mode — with primary test and coverage tests |
| `RDX_IMPLEMENTATION_PLAN_TESTED.md` | Test-aware revision of the plan; phase-local entry/exit gates; Phase 0 overclaims corrected; status taxonomy clarified |
| `RDX_TEST_DESIGN_REPORT.md` | This document |
| `tests/` directory skeleton | Subdirectories per layer + READMEs explaining what goes where |

---

## 2. Requirement coverage

| Category | Total requirements | Tests with this as Primary | Tests covering | Gap |
|----------|--------------------|-----------------------------|-----------------|------|
| V5 DoD | 14 | 14 | 60+ (across layers) | **None** |
| V6 DoD | 10 | 10 | 30+ | **None** |
| CORE rules (MVP set: 007/008/011/014/015) | 5 | 5 | 18 fixture cases | Doc-only-negative fixtures for FFI/Macro/Test/Data/DB/Time packs (tracked in Phase 2 entry gate) |
| Risk Router packs | 12 | All have positive | All have at least one positive | 6 packs missing dedicated doc-only-negative fixture (tracked) |
| Status taxonomy | 14 verdicts + 3 severities | All verdicts have set-by test | Most have blocking + authority tests | `BASELINE_BLOCKS_VALIDATION` + `TOOL_UNAVAILABLE` need explicit L1 unit tests (tracked) |
| Operating modes | 5 (Mode 0–4) | All have acceptance tests | All have layer-appropriate coverage | None |

**Net coverage:** **No requirement is unmapped.** ~8 fixtures need to be authored at Phase 2 entry gate; all are listed in the tested plan.

---

## 3. Test counts by layer

| Layer | Count | Determinism | Phase concentration |
|-------|-------|-------------|----------------------|
| L0 — static contracts | 10 | Full | Phase 1 |
| L1 — unit | 20 | Full | Phase 2 |
| L2 — fixtures (per-pack + per-CORE) | 35 | Full | Phase 2 |
| L3 — Cargo integration | 7 | Toolchain-pinned | Phase 2 |
| L4 — BMAD integration | 12 | Mixed (scripted + LLM-cooperative) | Phase 3 + Phase 7 (CR) |
| L5 — behavioral evals | 10 | Statistical | Phase 6, 7 |
| L6 — hook/CI end-to-end | 10 | Full | Phase 5 |
| L7 — security/mutation | 10 | Full | Phase 5, 8 |
| L8 — V6 judgment + governance | 7 | Mixed | Phase 7, 8 |
| V5/V6 acceptance suites | 12 | Mixed | Release gates |
| **Total** | **~135** | | |

---

## 4. Gaps found in the old plan (and how each is fixed)

| Gap | Source | Fix in tested plan |
|-----|--------|---------------------|
| 0.1 "context pressure" checked off without a test | Original plan | Returned to `[ ]`; assigned test ID T-L5-CTX-001 (Phase 6) |
| 0.1 "child incomplete result" checked off | Original plan | Returned to `[ ]`; assigned T-L4-WR-005 (Phase 3 entry gate) |
| 0.1 "risk tag preservation" implicit | Original plan | Made explicit; assigned T-L4-WR-006 (Phase 3 entry gate) |
| 0.2 marked as confirmed via doc inspection only | Original plan | Demoted to DOC VERIFIED + INFERENCE; empirical close at T-L4-CR-001/002 (Phase 7) |
| "15 statuses" actually listed 14 + WARNING undefined | Original plan | Clarified: 14 verdicts + WARNING as severity (orthogonal); exit-code mapping locked |
| Tests appeared only in Phase 6 | Original plan | Each Phase 1–8 now has entry-gate (tests-first) + exit-gate (tests-pass) sections |
| Phase 2 didn't enumerate which packs need negative fixtures | Original plan | Phase 2 entry gate lists 6 specific doc-only-negative fixtures to author |
| `BASELINE_BLOCKS_VALIDATION` status defined but no test | Original plan | Added to Phase 2 entry gate as TODO |
| `TOOL_UNAVAILABLE` status defined but no test | Original plan | Added to Phase 2 entry gate as TODO |
| No CI trust model — could PR tamper with validator? | Original plan | New §7 in test strategy; Option B (validator from base branch) recommended for V5; T-L6-CI-002 + T-L7-MOD-* tests prove it |
| Authority matrix mentioned but not enumerated | Original plan | `authority-matrix.json` is a Phase 1 deliverable; T-L0-STATUS-002 verifies |
| "fault injection" / mutation tests in plan as concept only | Original plan | Concrete L7 suite of 10 specific bypass tests, each with fixture + expected outcome |
| Code Review integration left as "via on_complete + persistent_facts" — but timing not analyzed | Spike 0.2 finding | R1 vs R2 explicit comparison; **R2 recommended**; both kept as control tests |
| No flaky-test policy | Original plan | New §10 in test strategy with hard/statistical/environment flake categories |
| No ownership / review process | Original plan | New §11 in test strategy mapping layers to roles |

---

## 5. R1 vs R2 — Code Review integration decision

After designing test cases for both:

**Recommendation: R2 (wrapper)** — `rdx-code-review` overrides `agent.menu[code=CR]` and orchestrates `bmad-code-review` → `rdx-judgment` → unified finalization.

Why R2 wins:
- **Timing**: R2 lets RDX Rule Auditor influence the verdict BEFORE story status update. R1's `on_complete` fires after presentation and sprint sync, making high-severity findings hard to act on.
- **Pattern reuse**: R2 is structurally identical to the proven Phase 0.1 wrapper-resume pattern (`rdx-dev-story` → `bmad-dev-story` → validator). Same enforcement class users already accept.
- **Single source of truth for final verdict**: R2 produces one unified report; R1 produces standard report + RDX appendix that may contradict the already-stored verdict.

R1 is retained as **control test** T-L4-CR-002. If R2 fails empirical validation in Phase 7 (T-L4-CR-001), R1 becomes the fallback with documented timing limitation.

Status until Phase 7 empirical close: **DOC VERIFIED + INFERENCE**.

---

## 6. Tests to write first (Phase 1 entry gate)

The first batch of tests to author, before any production code:

1. **`tests/contracts/schemas/rdx-evidence.v1.schema.json`** — the schema itself (the test of the schema is that it validates known-good fixtures)
2. **`tests/contracts/schemas/router-rules.schema.json`** — meta-schema for router mapping
3. **`tests/contracts/status-definitions.json`** — frozen list of 14 verdicts + 3 severities + exit-code mapping
4. **`tests/contracts/authority-matrix.json`** — (field × actor) authority cells
5. **`tests/contracts/drift-check.py`** — KB ↔ router mapping drift verifier
6. **`tests/fixtures/evidence/valid-minimal.json`** — golden good
7. **`tests/fixtures/evidence/invalid-missing-diff-digest.json`** — golden bad #1
8. **`tests/fixtures/evidence/invalid-cat1-pass-no-command.json`** — golden bad #2 (no LLM self-PASS)
9. **Initial pytest scaffold** at `tests/contracts/test_schema.py`

These materialize T-L0-SCHEMA-001..004, T-L0-DRIFT-001/002, T-L0-STATUS-001/002 from the YAML catalog.

After this batch, the deterministic gate "Phase 1 exit" can be measured.

---

## 7. Tests-first development flow

For every new check in Phase 2:

1. Pick a rule (e.g., CORE-007 protected files)
2. Read the rule's "Validation:" field from the KB
3. Find or write its YAML entry in `RDX_TEST_CASES.yaml`
4. Author fixtures under `tests/fixtures/diffs/` (or similar) with explicit expected verdicts in sibling `.expected.json` files
5. Author the pytest module that executes those fixtures against the (not-yet-implemented) check function
6. Run pytest — tests fail (red)
7. Implement the check in `rdx-validator/scripts/`
8. Run pytest — tests pass (green)
9. Refactor if needed; tests stay green
10. Commit with reference to the YAML test IDs

This applies to all Phase 1–8 work. No production code is committed without a corresponding YAML entry.

---

## 8. What this round did NOT do (intentional, per task constraints)

- **No production `rdx-validator`** was created. The Phase 0.3 prototype at `spikes/0.3-standalone-validator/rdx_validator.py` is the only validator code so far; it has spike scope, not production scope.
- **No production `rdx-dev-story` wrapper** was created. Phase 0.1 spike skills were created and then deleted from the active skills folder.
- **No production agent overrides** were modified. RDX v1.0 `_bmad/custom/bmad-agent-*.toml` files are untouched.
- **No pre-push hooks installed.** Only Spike 0.1 test fixtures using local /tmp.
- **No CI required checks** turned on. Sample-repo CI design is documented but not yet provisioned.
- **No production `rdx-judgment` skill** was created.

All of the above are deferred to their respective phases (2, 3, 5, 7) following test-first methodology.

---

## 9. Outstanding open questions (not blocking)

1. **BMAD resolver stability commitment** (`bmad-code-org/BMAD-METHOD` issue) — file after V5 release.
2. **HMAC necessity** — re-examine when first abuse vector emerges.
3. **GitLab template** — defer until first non-GitHub user requests.
4. **Codex/Cursor `AGENTS.md` packaging** — V7 spin-off, post-V6.
5. **Performance targets** — defer until V5 ships and real workloads exist.

None block Phase 1 start.

---

## 10. Final verdict

```
READY_FOR_TEST_FIRST_IMPLEMENTATION
```

The branch contains:
- ✓ Full test architecture (`RDX_TEST_STRATEGY.md`)
- ✓ ~135 test cases catalogued (`RDX_TEST_CASES.yaml`)
- ✓ Full requirement traceability (`RDX_TEST_TRACEABILITY_MATRIX.md`)
- ✓ Test-aware implementation plan with phase-local gates (`RDX_IMPLEMENTATION_PLAN_TESTED.md`)
- ✓ Phase 0 overclaims corrected
- ✓ Status taxonomy locked
- ✓ R1 vs R2 decision (R2 recommended)
- ✓ CI trust model designed
- ✓ Adversarial / mutation suite designed
- ✓ `tests/` directory skeleton with per-layer READMEs

The next session can start Phase 1 by authoring the first batch of test fixtures and schemas listed in §6 of this report. Each subsequent commit must reference a YAML test ID.

**Do not start production implementation outside the test-first cycle described in §7.**
