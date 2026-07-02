# archive-docs-dev — Historical planning artifacts

This folder holds every planning, research, verification, and design document
that shaped **RDX 1.1** but is no longer a living document.

**Nothing here is required at runtime.** The validator, hooks, wrapper, CI
workflows, and skills all operate without reading any file below this
directory. This is a **read-only historical record**.

For active maintenance documents (how the codebase is organised, how to add
a check, how the test taxonomy works), see [`../docs/AGENT_MAINTENANCE_GUIDE.md`](../docs/AGENT_MAINTENANCE_GUIDE.md).

---

## Inventory

### `planning/` — pre-1.1 research and verification

| File | What it is | Superseded by |
|------|------------|----------------|
| `RDX improve research.md` | Initial architecture proposal (Variant A–E analysis) | Verification report below |
| `RDX_VALIDATOR_ARCHITECTURE_VERIFICATION.md` | Empirical verification of Variant E with 7 spikes; final `GO — Variant E with mandatory corrections` verdict | Realised as shipping code in `rdx-validator/`, `.claude/skills/rdx-*/`, `.github/workflows/rdx-gate.yml` |
| `RDX_PHASE0_SPIKE_REPORT.md` | Empirical closure of the three Phase 0 integration prerequisites | Superseded by shipped features (wrapper, validator, code review R2) |

### `test-design/` — test architecture frozen at 1.1

| File | What it is | Living successor |
|------|------------|-------------------|
| `RDX_TEST_STRATEGY.md` | Test layer taxonomy (L0–L8), determinism semantics, status taxonomy, R1 vs R2 decision, CI trust model | `docs/AGENT_MAINTENANCE_GUIDE.md` §"How the test taxonomy works" |
| `RDX_TEST_TRACEABILITY_MATRIX.md` | Requirement → test mapping for V5/V6 DoD items | Traceability is now enforced by `tests/contracts/rule-check-map.json` + drift-check |
| `RDX_TEST_CASES.yaml` | Machine-readable catalog of ~135 test cases with full schema | Still referenced by two mutation tests (`test_l7_full_suite.py`, `test_v6_acc_05.py`) via the archive path — those tests use it as a bypass-class catalogue |
| `RDX_TEST_DESIGN_REPORT.md` | Summary of the test-design stage before Phase 1 | `docs/AGENT_MAINTENANCE_GUIDE.md` |

### `implementation-plans/` — plans, both frozen and completed

| File | What it is | Status |
|------|------------|--------|
| `RDX_IMPLEMENTATION_PLAN.md` | Original plan authored at task start | Frozen historical — never updated |
| `RDX_IMPLEMENTATION_PLAN_TESTED.md` | Working plan with entry/exit gates, phase progress log, all `[x]` after Phase 10 | Completed — read for context on why each phase was scoped the way it was |

### `phase-runner/` — the tool used to build 1.1

| File | What it is |
|------|------------|
| `PHASE_RUNNER_PROMPT.md` | Universal template pasted into fresh Claude Code / Codex CLI sessions to execute one implementation phase. Retained as the template for future release cycles (RDX 1.2+). |

### `spikes/` — Phase 0 empirical proofs

| Folder | What it proved |
|--------|----------------|
| `spikes/0.1-multi-skill/` | Wrapper skill can invoke a child skill via the Skill tool and reliably resume its post-child steps (`trace.log.evidence` captures BEFORE→CHILD→AFTER ordering) |
| `spikes/0.2-review-propagation/` | RDX Rule Auditor can be added to `bmad-code-review` via `on_complete` + `persistent_facts` without forking step files (DOC VERIFIED; empirically closed at Phase 7 T-L4-CR-001) |
| `spikes/0.3-standalone-validator/` | Standalone Python CLI (stdlib only, no BMAD imports) can perform router replay + digest computation deterministically. Prototype `rdx_validator.py` was extended into today's `rdx-validator/` package. |

---

## How to use this archive

- **Question about why a decision was made?** Start with `planning/RDX_VALIDATOR_ARCHITECTURE_VERIFICATION.md` — it contains the empirical evidence and reasoning for every architectural choice in 1.1.
- **Question about what a test ID means?** Look in `test-design/RDX_TEST_CASES.yaml`. The YAML is authoritative for test-ID conventions used throughout the codebase.
- **Question about how a phase was structured?** `implementation-plans/RDX_IMPLEMENTATION_PLAN_TESTED.md` has phase-by-phase entry/exit gates plus a progress log showing what closed each phase.
- **Question about how to run a new phase for 1.2?** Take `phase-runner/PHASE_RUNNER_PROMPT.md` as a template and adapt.

## What NOT to do

- Do not update files in this folder. If a design or test policy needs to change for 1.2+, create a new document in `docs/` or extend `docs/AGENT_MAINTENANCE_GUIDE.md`. This folder is frozen at the 1.1 release.
- Do not import files from this folder into production code (`rdx-validator/`, `.claude/skills/`). Only test infrastructure references it (specifically the two mutation tests that use `RDX_TEST_CASES.yaml` as a bypass-class catalogue).
