# PROOF_COMPLETION_PLAN

**SUPERSEDED — 2026-07-02.** Variant D2 has been amended into Variant
D3 (see `rdx-tea/architecture/ADR-002-SEQUENTIAL-ACTIVE-BUNDLE.md`)
after independent D3 correction audit and Phase B–H runtime proof.

**Active plan:** `rdx-tea/implementation-plan/D3_PROOF_PLAN.md`.

The stages, gates, and file lists below are retained for historical
audit. Do NOT execute them as-is; they encode the D2 assumptions that
were rejected. Every stage's intent has been re-encoded in the D3
plan under a stage of the same or higher discipline.

---

## Original body (D2-era, retained verbatim)



Verdict = `PARTIALLY_PROVEN`. Per prompt §15 second sub-section, the
prescribed follow-up is a proof-completion plan (not a production
implementation plan). This file lists the stages needed to close the
`NOT_RUN` and `BLOCKED` gates in
`rdx-tea/evidence/final/FINAL_VERIFICATION.json` before any production
implementation stage can be safely attempted.

Every stage is a self-contained work item designed to be executed in a
**separate fresh CLI context** (prompt §16.1). Stages that appear here
close knowledge-plane gates first, per the
`feedback_rdx_tea_knowledge_first` memo. Production stages (contracts
implementation, validator subcommand, hooks/CI) appear only after
`FINAL_VERIFICATION.json` shows G2..G7 PASS.

Stage IDs match filenames under `implementation-plan/stages/` and are
referenced by `TEST_CASES.yaml` `implementation_stage` field.

---

## Stage sequence

```
Stage-01 → Stage-02 → Stage-03 ┐
                              ├─→ Stage-06 → Stage-07 → Stage-08 → Stage-09
Stage-04 → Stage-05          ─┘
```

Stages 01–07 are **knowledge-plane** and must all show PASS before
Stage 08. Stages 08–09 are **enforcement-plane**.

---

## Stage 01 — Contracts & source lock refresh
**Entry gate:** `SOURCE_LOCK.md §1` SHA equals `origin/main` HEAD. If not,
regenerate hash manifest and record a `SOURCE_LOCK §9` addendum.

**Scope allowed:** `rdx-tea/research/`, `rdx-tea/evidence/hashes/`.
Nothing else. **Not allowed:** touching `rdx-tea/poc/` or any generator.

**Tests written first:**
- `test_l0_source_lock_hash[core|router|packs|gov]` (already green).
- Add: `test_l0_source_lock_hash_covers_all_authoritative_files` — read
  the manifest, assert every file under the four authoritative roots is
  hashed. Currently red (manifest omits some directories).

**Exit gate:** all Stage-01 tests green; new `SOURCE_LOCK §9` addendum
if any SHA changed.

**Handoff record:** `evidence/logs/stage01-*.log` + updated
`SOURCE_LOCK.md`.

## Stage 02 — Router replay + per-workflow scope filter
**Entry gate:** Stage-01 green. `rdx-tea/poc/adapter/projection.py`
exists and current 32 L0/L1 tests are green.

**Scope allowed:** `rdx-tea/poc/adapter/router_replay.py` (new),
`rdx-tea/poc/adapter/scope.py` (new),
`rdx-tea/tests/unit/test_l2_router_replay.py` (new),
`rdx-tea/fixtures/diffs/**` (may copy from `tests/fixtures/diffs/`).

**Tests written first (RED):**
- For each of the 12 packs and 13 fixture shapes
  (`strong-positive`, `strong-negative`, `ambiguous`, `doc-only-negative`,
  `path-only-signal`, `story-tag-required`, `missing-tag`,
  `multiple-packs`, `suppressed-pack`, `stale-fragment`,
  `malformed-artifact`, `missing-evidence`, `unrelated-non-Rust-change`),
  one parametrized test asserting the projection Router adapter reproduces
  the RDX validator's `router.replay()` result.
- `test_l2_scope_filter_test_design_includes_only_expected_packs` — assert
  the scope filter table from `BUILDER_TEA_RECONCILIATION §3.3`.
- `test_l2_scope_filter_ci_excludes_source_lint_packs` — assert `ci` drops
  `RP-UNSAFE-*`, `RP-FFI-*`, `RP-MACRO-*`, `RP-DATA-*`.

**Implementation tasks:**
- Wrap `rdx_validator/router.py`'s `replay()` as an import inside
  `router_replay.py` (do not fork the logic).
- Build the scope filter as a static dict (workflow → allow set of pack
  IDs).

**Exit gate:** 12 × 13 nodes PASS; scope filter tests PASS; G3 gate
becomes `PASS` in `FINAL_VERIFICATION.json`.

## Stage 03 — Lifecycle overlay installer
**Entry gate:** Stage-01 + Stage-02 green.

**Scope allowed:** `rdx-tea/poc/adapter/installer.py`,
`rdx-tea/tests/lifecycle/test_l4_lifecycle.py`,
`rdx-tea/fixtures/existing-customizations/`.

**Tests written first:**
- 12 lifecycle scenarios per prompt §12 lifecycle list.
- Adversarial TOML fixtures for `merge-config.py` re-use: existing
  `[agent]`, arrays, comments, nested tables, menu items, workflow
  overrides, duplicate entries, custom user content, bytewise restore.

**Implementation:** `installer.py` calls the vendored `merge-config.py`
(or the vendored `resolve_customization.py`) and writes to a temp dir
during tests.

**Exit gate:** G4 PASS.

## Stage 04 — Rust project fixtures + L3 probe
**Entry gate:** Stages 01–03 green. Cargo/rustc verified.

**Scope allowed:** `rdx-tea/fixtures/rust-projects/**`,
`rdx-tea/tests/integration/test_l3_cargo.py`,
`rdx-tea/scripts/run-l3-cargo.sh`.

**Tests written first:** for each of the 15 Rust projects (per
BEHAVIORAL_EVAL_PLAN "Fixture set"), one PoC test: run the projection
Router adapter over a real diff and assert the expected packs activate.

**Exit gate:** all 15 × 2 nodes PASS; refines G3.

## Stage 05 — Real BMAD/TEA workflow runs (sequential + fallback)
**Entry gate:** Stages 01–04 green. Adapter installer works on a
disposable copy of the host BMAD 6.8.0 install.

**Scope allowed:** `rdx-tea/tests/bmad-tea/`,
`rdx-tea/scripts/run-l4-tea.sh`, `rdx-tea/evidence/artifacts/stage05-*/`.

**Tests written first:** for each of the 8 workflows in sequential mode,
run against a Rust story fixture; assert the emitted artefact contains
the expected `active_packs` and matching rule IDs in front-matter.

**Exit gate:** G5 PASS (sequential mode at minimum).

## Stage 06 — Subagent seed + payload spy
**Entry gate:** Stage-05 sequential green.

**Scope allowed:** `rdx-tea/poc/adapter/subagent_seed.py`,
`rdx-tea/tests/bmad-tea/test_subagent_propagation.py`.

**Tests written first:** for `bmad-testarch-atdd`, run in
subagent-execution mode; instrument the parent step so
`subagentContext.knowledge_fragments_loaded` is emitted to a spy file;
assert the seed fragment ID is present.

**Exit gate:** G6 PASS. If subagent mode is unavailable in the runtime,
record `NOT_RUN` and freeze downstream stages.

## Stage 07 — Behavioural evals (baseline vs candidate)
**Entry gate:** Stages 05 + 06 green.

**Scope allowed:** `rdx-tea/evals/**`, grading harness.

**Tests written first:** rubric-first — encode
`BEHAVIORAL_EVAL_PLAN.md` metrics as JSON schemas; write the grader as
a pytest that reads transcripts.

**Runs:** per fixture × per workflow × N=10 (or N=20 for critical
scenarios) for both arms.

**Exit gate:** G7 PASS with statistical improvement documented.

## Stage 08 — Validator extension (`rdx-tea-validate`)
**Entry gate:** G0..G7 all PASS. **Do not begin earlier.**

**Scope allowed:** `rdx-validator/rdx_tea/**` (new subpackage),
`rdx-tea/tests/ci/test_l6_validator_extension.py`,
`rdx-tea/tests/mutation/test_l7_*.py`.

**Tests written first:** 24 mutation scenarios (prompt §12 L7)
against `rdx-tea-validate`; Cat-1 authority preservation regressions;
verdict enum reuse.

**Exit gate:** G8 PASS.

## Stage 09 — Modes, hook, CI, judgment
**Entry gate:** G8 PASS.

**Scope allowed:** `rdx-tea/tests/ci/`, `rdx-tea/tests/acceptance/`,
`rdx-tea/implementation-plan/stages/STAGE-09-*.md`.

**Tests written first:** mode-differentiating tests reused from RDX
baseline pattern; Cat-4 approval binding for adapter-generated
artefacts.

**Exit gate:** G9, G10, G11 PASS. Verdict may be upgraded to `PROVEN`.

---

## What is BLOCKED right now

- Full MASTER_IMPLEMENTATION_PLAN.md — waits for verdict `PROVEN`.
- Any production RDX file change outside `rdx-tea/` — waits for
  Stage 08 sign-off.
- Any BMAD host modification — never; adapter is overlay-only.

## Rollback

Each stage ends with a git commit inside `rdx-tea-integration`.
Rollback = `git reset` to the previous stage commit. No production file
outside `rdx-tea/` is ever changed by any of these stages, so no
system-level rollback is required.
