# CLAIM_EVIDENCE_MATRIX

Per prompt §19: one row per load-bearing claim about Variant D2, with
source, official confirmation, tests, runtime result, and confidence.
Rows with `Runtime = —` are architectural claims that have no runtime
signal yet (their confidence therefore does not exceed MEDIUM).

Legend: `Test IDs` → pytest node identifier fragments.
`Confidence` ∈ HIGH (source + official + green test), MEDIUM
(source + official OR source + green test), LOW (source only),
UNCERTAIN (no source, only proposal).

| # | Claim | Source | Official confirmation | Test IDs | Runtime | Evidence path | Confidence | Limits |
|---|---|---|---|---|---|---|---|---|
| C1 | Canonical status vocabulary is exactly the 14-verdict + 3-severity set with `EVIDENCE_REQUIRED` spelling | `tests/contracts/status-definitions.json` | Explore §1 confirms host BMAD 6.8.0 does not clash | `test_l0_status_vocabulary_complete`, `test_l1_load_status_has_full_vocabulary` | PASS | `phase4_l0_projection_GREEN.log` | HIGH | Applies only at SHA `d8140a25` |
| C2 | Canonical rule ID prefixes are `CORE-`, `RP-`, `GOV-`; no `RUST-*` | `tests/contracts/rule-check-map.json`, KB `section-4-core.md` / `section-6-packs.md` | Builder Q9 accepts | `test_l0_router_rule_ids_prefixes`, `test_l0_rule_check_map_prefixes` | PASS | Same | HIGH | Same |
| C3 | Canonical Router has exactly 12 packs with the (confidence_class, activation_policy, rule_count) tuples listed in CURRENT_RDX_1_1_BASELINE §2.2 | `tests/contracts/router-rules.json` | Builder Q2/Q4 accepts | `test_l0_router_packs_canonical` | PASS | Same | HIGH | Contract only; L2 fixture replay pending |
| C4 | `STORY_TAG_REQUIRED` packs are exactly `{api, testing, ops, perf}` | Same | Both reviews accept (TEA §7 uses story-tag logic) | `test_l0_story_tag_required_packs_preserved` | PASS | Same | HIGH | — |
| C5 | RDX 1.1 shipped suite is green (307/0/0) at `d8140a25…` | Repo test suite | — | Every RDX test | 307 PASS | `phase0_baseline_pytest.log` | HIGH | Isolated venv (`rdx-tea/.venv-baseline`), Python 3.14.4 |
| C6 | Adding 32 knowledge-plane tests keeps existing suite green | Same | — | Aggregate | 339 PASS in 14.26s | Same | HIGH | Same env |
| C7 | Three-layer TOML merge exists and is structural (no field-name special-casing) | `_bmad/scripts/resolve_customization.py:31-33`, `:150-166` | Builder Q4 explicit, TEA §2 implicit | — | (no automated test yet against real installer; source read only) | `BMAD_CORE_EXTENSION_SURFACE §1`, `phase1-explore-tea-surface.md §7` | MEDIUM | Host 6.8.0; upstream SHA PENDING (SOURCE_LOCK §4) |
| C8 | `persistent_facts` supports `file:` glob and is loaded by SKILL.md Step 4 | `bmad-tea/SKILL.md` "On Activation" Step 4, every `bmad-testarch-*/SKILL.md` Step 4 | Builder Q2, TEA §2, TEA §4 | — | — | Same | MEDIUM | Same |
| C9 | Every TEA workflow has a `tea-index.csv` with schema `id,name,description,tags,tier,fragment_file` and `tier ∈ {core, extended, specialized}` | `bmad-testarch-*/resources/tea-index.csv` | TEA §4, TEA §11 | — | — | Same, plus `PHASE1_HOST_BMAD_files_sha256.txt` | MEDIUM | Same |
| C10 | Subagent context does NOT inherit `persistent_facts`; parent must forward fragments via `subagentContext.knowledge_fragments_loaded` | `bmad-testarch-atdd/steps-c/step-04-generate-tests.md:56-83`, `bmad-testarch-trace/steps-c/step-04-analyze-gaps.md:95-110` | Builder Q6 + TEA §3 both explicit | — | — (design in ADR-001 §7; no spy yet) | `BUILDER_TEA_RECONCILIATION §1 A6` | MEDIUM | The most consequential design risk in Variant D2 |
| C11 | The correct install path for generated RDX-owned fragments is `{project-root}/_bmad/rdx-tea/knowledge/`, NOT `_bmad/custom/**` | `bmad-customize/SKILL.md:77-79` (custom is for `.toml` overlays only); module-code convention `_bmad/{code}/…` | Builder Q7 explicit; TEA §10(e) agrees on principle | — | — | `BUILDER_TEA_RECONCILIATION §2 D1` | MEDIUM | Resolved by choosing Builder's convention |
| C12 | Per-workflow scope filter must be applied (not uniform 8-way overlay) | Both reviews (Builder Q9, TEA §10(c)) | Same | — | — | `BUILDER_TEA_RECONCILIATION §3.3` table | MEDIUM | Filter table encoded in ADR-001; scope-filter code TODO |
| C13 | `rdx-evidence.v1` schema fusion is NOT the correct integration point; share the 14-verdict enum only | `tests/contracts/schemas/rdx-evidence.v1.schema.json:120-138`, `trace/checklist.md:12` (`PASS/CONCERNS/FAIL/WAIVED` subset) | TEA §6 explicit; Builder Q9 concurs | — | — | ADR-001 §9 | MEDIUM | — |
| C14 | Projection generator is deterministic (byte-identical re-run) | `rdx-tea/poc/adapter/projection.py` | — | `test_l0_projection_generator_is_deterministic`, `test_l1_render_all_is_deterministic_across_processes`, `test_l1_render_all_no_wallclock_or_random_content` | PASS | `phase4_l0_projection_GREEN.log`, `PHASE4_projection_output.txt` | HIGH | PoC scope; production version must repeat the guarantee |
| C15 | The generator emits at least one fragment per Router pack and an index row per pack | Same | — | `test_l0_projection_generator_covers_all_packs`, `test_l0_projection_generator_emits_rdx_tea_index_row_per_pack`, `test_l1_index_csv_has_one_row_per_pack_and_no_duplicates` | PASS | Same | HIGH | Same |
| C16 | Skill roots are "DO NOT EDIT — overwritten on every update" | Every `customize.toml` line 1 | Both reviews explicit (Builder Q3, TEA §10(e)) | — | — | Same evidence | HIGH | — |
| C17 | Subagent seed mechanism will land the fragment ID in `subagentContext.knowledge_fragments_loaded` | Design only | — | — | — | ADR-001 §7 | UNCERTAIN | Requires L4 spy test (PROOF_COMPLETION_PLAN Stage 6) |
| C18 | RDX validator can consume front-matter block (`active_packs`, `mode`, `storyId`, `headSha`, `diffDigest`) and emit `rdx-evidence.v1` envelope | Design only | — | — | — | ADR-001 §10 | UNCERTAIN | Requires validator subcommand (PROOF_COMPLETION_PLAN Stage 8) |
| C19 | Adapter install / update / uninstall preserves user `.user.toml` overrides | Design only | — | — | — | ADR-001 §14 | UNCERTAIN | Requires L4 lifecycle test (PROOF_COMPLETION_PLAN Stage 3) |
| C20 | Behavioural eval will show measurable improvement over BMAD+TEA baseline | Design only | — | — | — | ADR-001 §7.8, `bmad-eval-runner/SKILL.md:14-23` | UNCERTAIN | Requires baseline+variant run with N≥10 (PROOF_COMPLETION_PLAN Stage 7) |

## Summary

- HIGH confidence: 8 claims (C1–C6, C14, C15, C16).
- MEDIUM confidence: 7 claims (C7–C13).
- UNCERTAIN: 4 claims (C17–C20).

Every UNCERTAIN or MEDIUM claim is addressed in PROOF_COMPLETION_PLAN by
a specific stage that produces the missing runtime evidence.
