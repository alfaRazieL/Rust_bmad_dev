# VARIANT_D_VERIFICATION_REPORT — targeted evaluation of the previous spike

**Purpose:** answer prompt §5.1..§5.9 verbatim — the nine ways the previous
"Variant D" PoC was known to be wrong. For each, record whether Variant D2
(this task's amended candidate) still fails, or has resolved the concern,
and cite where.

Read alongside:
- `rdx-tea/research/CURRENT_RDX_1_1_BASELINE.md §6` (baseline observations)
- `rdx-tea/research/BMAD_CORE_EXTENSION_SURFACE.md §11` (Builder addendum)
- `rdx-tea/research/BUILDER_TEA_RECONCILIATION.md`
- `rdx-tea/architecture/ADR-001-INTEGRATION-ARCHITECTURE.md`
- `rdx-tea/evidence/final/FINAL_VERIFICATION.json`

---

## 5.1 Canonical status drift

Previous spike may have used `EVIDENCE_MISSING`. Canonical value is
`EVIDENCE_REQUIRED`.

**Variant D2 outcome:** RESOLVED (contract layer).

Evidence:
- `test_l0_status_vocabulary_complete` asserts full 14-verdict set from
  `status-definitions.json` and explicitly `assert "EVIDENCE_MISSING" not in
  verdicts`.
- Projection generator imports vocabulary via `_load_status()` and threads
  the sorted list into every fragment
  (`test_l1_load_status_has_full_vocabulary`,
  `test_l1_pack_fragment_lists_all_verdicts_alphabetically`).

Remaining risk: only asserts spelling at contract layer. A TEA artefact
that carries a hand-written `verdict:` field could still drift — L4/L5
tests must extend the check to the emitted artefact.

## 5.2 Wrong rule IDs

Previous spike may have used old `RUST-*` IDs.

**Variant D2 outcome:** RESOLVED (contract layer).

Evidence:
- `test_l0_router_rule_ids_prefixes` asserts every pack `related_rule_ids`
  entry begins with `RP-`.
- Rule check map covered by `test_l0_rule_check_map_prefixes` (18 CORE, 14
  RP, 5 GOV) — the same distribution the shipped RDX 1.1 validator uses.
- Projection generator writes rule IDs verbatim without translation
  (`_render_pack_fragment` — no dict lookup).

Remaining risk: nothing prevents a manually-written TEA output from
inventing `RUST-*` IDs. L4/L5 tests must include a diff-based check on
emitted artefacts.

## 5.3 Router hand-copy

Previous PoC hand-copied Router signals.

**Variant D2 outcome:** RESOLVED (generator-level).

Evidence:
- `projection.py:CANONICAL_INPUTS` lists `tests/contracts/router-rules.json`.
  `test_l1_canonical_inputs_are_only_repo_files` asserts every input is
  under `tests/contracts/` or the KB directory.
- `test_l0_router_packs_canonical` asserts every (confidence_class,
  activation_policy, related_rule_ids count) tuple matches canonical.
- `test_l0_story_tag_required_packs_preserved` asserts the exact
  `{api, testing, ops, perf}` set of `STORY_TAG_REQUIRED` packs.

Remaining risk: contract-only. Router replay against the 13 fixture
shapes required by prompt §12 L2 (strong positive, strong negative,
ambiguous, doc-only negative, path-only signal, story-tag-required,
missing tag, multiple packs, suppressed pack, stale fragment, malformed
artifact, missing evidence, unrelated non-Rust change) NOT yet
implemented. PROOF_COMPLETION_PLAN Stage 2 covers this.

## 5.4 No real generator

Previous PoC wrote projections by hand.

**Variant D2 outcome:** RESOLVED (basic PoC).

Evidence:
- `rdx-tea/poc/adapter/projection.py` — deterministic, 175 lines.
- `test_l1_render_all_is_deterministic_across_processes` — byte-identical
  re-run.
- `test_l1_render_all_no_wallclock_or_random_content` — no timestamps.
- Hashes of the 12 emitted fragments + 1 index in
  `rdx-tea/evidence/hashes/PHASE4_projection_output.txt`.

Remaining risk: PoC does not yet apply the per-workflow scope filter of
BUILDER_TEA_RECONCILIATION §3.3 — currently it emits one uniform
fragment per pack. That table needs to be encoded and its filtering
tested. PROOF_COMPLETION_PLAN Stage 2 covers this.

## 5.5 Unsafe TOML merge

Previous installer might create a second `[agent]` section.

**Variant D2 outcome:** PARTIALLY_RESOLVED (design-level).

Evidence:
- Merge semantics reverse-engineered from
  `_bmad/scripts/resolve_customization.py` (three-layer, structural,
  keyed-array support, no-removal) — captured in
  `BMAD_CORE_EXTENSION_SURFACE §1`. Both reviews cite the same file and
  line ranges (`:31-33`, `:139-166`).
- Adapter uses `resolve_customization.py` at *load time*; it does not
  string-concatenate TOML.
- Idempotent install semantics stated in ADR-001 §14.

Remaining risk: no adversarial installer test yet
(existing `[agent]`, comments, nested tables, duplicate entries,
custom user content, bytewise restore). PROOF_COMPLETION_PLAN Stage 3.

## 5.6 Agent-only vs workflow integration

Previous PoC changed only `bmad-tea.toml`; no workflow-step wiring.

**Variant D2 outcome:** RESOLVED (design-level).

Evidence:
- ADR-001 §5 explicitly REJECTS agent-level `bmad-tea` overlay
  (both reviews cited this as blocking).
- ADR-001 §6 wires 6 of 8 workflows via `[workflow].persistent_facts`.
- ADR-001 §6 wires the remaining 2 (`framework`, `ci`) via
  step-c-injection because they branch on `{detected_stack}`.

Remaining risk: only DESIGNED. No overlay is installed and no workflow
run has been observed to load a fragment. PROOF_COMPLETION_PLAN Stage 4.

## 5.7 Non-functional mode tests

Previous tests parametrised MODE_0..MODE_4 without behavioural
differentiation.

**Variant D2 outcome:** RESOLVED at baseline; PENDING for adapter side.

Evidence:
- Existing RDX suite has real mode-differentiating tests
  (`tests/bmad/modes/test_mode_selector.py`, `test_mode_naming.py`,
  `tests/ci/test_l6_hook.py` — each with mode-specific expected
  outcomes). Green at baseline.
- Adapter side (MODE_0..MODE_4 tie-in from ADR-001 §13) not yet tested.
  Mode-differentiating tests specified in PROOF_COMPLETION_PLAN Stage 9.

## 5.8 No real TEA runs

Previous PoC did not run TEA workflows and lacked baseline / subagent /
agent-team / output-quality / live validator / live hook.

**Variant D2 outcome:** NOT_RUN — this is the primary open item.

Evidence: G5, G6, G7 all `NOT_RUN` in `FINAL_VERIFICATION.json`.

PROOF_COMPLETION_PLAN Stages 5, 6, 7 close this.

## 5.9 Artificial candidate scores

Previous PoC used prescribed weights and numbers as "evidence".

**Variant D2 outcome:** RESOLVED for what has been tested.

Evidence:
- No numeric score appears in any Phase-0..Phase-3 verdict here.
- Boolean/set assertions on canonical facts only.
- FINAL_VERIFICATION.json uses status labels
  (`PASS/PARTIAL_PASS/NOT_RUN/BLOCKED`), not scores.
- Behavioural eval design in ADR-001 references `bmad-eval-runner`
  baseline/variant modes with explicit statistical thresholds
  (prompt §12 L5 N>=10 / N>=20). No fake score has been produced.

Remaining risk: the eventual behavioural eval (Stage 7) must obey these
same rules. PROOF_COMPLETION_PLAN Stage 7 records the discipline verbatim.

---

## Summary table

| §  | Concern | Status | Evidence anchor |
|----|---------|--------|-----------------|
| 5.1 | Status drift (EVIDENCE_MISSING) | RESOLVED at contract | `test_l0_status_vocabulary_complete` |
| 5.2 | Wrong rule IDs (RUST-*) | RESOLVED at contract | `test_l0_router_rule_ids_prefixes` |
| 5.3 | Router hand-copy | RESOLVED at contract; L2 fixture replay pending | ADR-001 §3; PROOF_COMPLETION_PLAN Stage 2 |
| 5.4 | No real generator | RESOLVED (PoC) | `projection.py`, L0/L1 suite |
| 5.5 | Unsafe TOML merge | PARTIALLY_RESOLVED (design) | Reverse-engineered `resolve_customization.py`; Stage 3 pending |
| 5.6 | Agent-only overlay | RESOLVED (design) | ADR-001 §5–§6 |
| 5.7 | Non-functional mode tests | Baseline green; adapter Stage 9 pending | Existing mode-differentiating tests |
| 5.8 | No real TEA runs | NOT_RUN | Stages 5, 6, 7 |
| 5.9 | Fake candidate scores | RESOLVED | FINAL_VERIFICATION.json uses labels only |
