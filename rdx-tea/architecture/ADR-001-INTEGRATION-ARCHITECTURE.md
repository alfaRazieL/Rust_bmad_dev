# ADR-001 — RDX × BMAD TEA integration (Variant D2)

**Status:** proposed  
**Depends on:** SOURCE_LOCK §1, CURRENT_RDX_1_1_BASELINE §7, BMAD_CORE_EXTENSION_SURFACE §7 + §11, BUILDER_TEA_RECONCILIATION §3.  
**Follow-on:** MASTER_TEST_STRATEGY, PROOF_COMPLETION_PLAN.

## 0. Framing

The prompt (§0) permits ADR-001 to *amend* the previously-proposed
"Variant D — Hybrid Adapter" if verification requires it. Phase 2 Builder
+ TEA reviews (independent, source-grounded) forced enough amendments that
we name the resulting design **Variant D2**. Variant D2 keeps the four
load-bearing ideas of D — canonical RDX contracts, deterministic projection
generator, per-workflow injection through official overlays, and an
enforcement-plane wrapper that re-uses `rdx-evidence.v1` — but corrects the
install path, the injection topology, the subagent propagation contract, and
the schema fusion policy.

Design order strictly follows the knowledge-plane-first memo
(`feedback_rdx_tea_knowledge_first.md`): items §2..§8 are all
knowledge-plane; the enforcement-plane items §9..§14 assume the
knowledge plane is proven first.

---

## KNOWLEDGE PLANE

### 1. Canonical source

Exactly the files hashed in `SOURCE_LOCK §5`:

- `tests/contracts/router-rules.json`
- `tests/contracts/status-definitions.json`
- `tests/contracts/rule-check-map.json`
- `tests/contracts/authority-matrix.json`
- `tests/contracts/schemas/rdx-evidence.v1.schema.json`
- `tests/contracts/schemas/rdx-judgment-finding.v1.schema.json`
- `.claude/skills/rdx-setup/assets/kb-sections/section-{4,5,6,8}-*.md`

The projection generator (§3) treats these as its **only** inputs, so any
drift is caught by an SOURCE_LOCK hash check (already implemented as
`test_l0_source_lock_hash[core|router|packs|gov]`).

### 2. Normalized intermediate representation (IR)

A single in-memory dict with three keys:

- `router: {pack_name: {activation_policy, confidence_class, positive_signals, negative_signals, path_signals, related_rule_ids, validation_family, escalation_triggers, kb_section}}`
- `status: {verdicts: [...], severities: [...]}`  (14 verdicts + 3 severities exactly)
- `rules: {rule_id: {category, applicability, detection, evidence, authority, blocking_semantics, exception_policy}}`

The IR is a strict subset-and-rearrangement of the canonical JSON. It
carries no free-form English, so byte-diffs against canonical are
detectable.

### 3. Projection generator

`rdx-tea/poc/adapter/projection.py` (PoC) → production
`_bmad/rdx-tea/scripts/generate.py`.

Behaviour:

1. Load IR from canonical files.
2. For every pack in the Router, compute the **workflow scope filter**
   (see `BUILDER_TEA_RECONCILIATION §3.3`) and emit at most one
   knowledge fragment per (pack × workflow-in-scope) combination.
3. Assign a `tier` (default `specialized`; `RP-TEST-*` may be `extended`;
   never `core`).
4. Emit an index CSV mirroring `tea-index.csv` schema
   (`id,name,description,tags,tier,fragment_file`).
5. Emit a small "subagent seed" fragment for each workflow that runs in
   subagent or agent-team mode (see §7).

Determinism: no wallclock, no randomness, sorted iteration. Proven by
`test_l0_projection_generator_is_deterministic` and
`test_l1_render_all_is_deterministic_across_processes`.

### 4. Fragment / index format for TEA

Per workflow the adapter installs:

- `{project-root}/_bmad/rdx-tea/knowledge/tea-{workflow}/*.md` — the
  filtered fragment set for that workflow.
- The overlay `_bmad/custom/bmad-testarch-{workflow}.toml` appends
  ```toml
  [workflow]
  persistent_facts = [
    "file:{project-root}/_bmad/rdx-tea/knowledge/tea-{workflow}/**/*.md",
  ]
  ```
- Index augmentation (§6) is done via an activation-prepend step that
  reads a companion CSV and merges it into the in-memory
  `tea-index.csv` — the physical `resources/tea-index.csv` in the skill
  root is never edited.

Fragment schema (front-matter):
```yaml
---
rule_ids: [RP-ASYNC-001, RP-ASYNC-004, ...]
pack_id: async
tier: specialized
source_of_truth: tests/contracts/router-rules.json
scope_filter: test-design
---
```

### 5. Agent-level minimal contract for `bmad-tea`

**None.** Rejected by both Builder and TEA reviews (agent-level overlay
fires for every menu item incl. TMT). `bmad-tea` receives no RDX overlay.

### 6. Workflow-level loading

Six of the eight workflows load Rust knowledge unconditionally via
`persistent_facts` overlay (§4):

- `bmad-testarch-test-design`
- `bmad-testarch-atdd`
- `bmad-testarch-automate`
- `bmad-testarch-test-review`
- `bmad-testarch-nfr`
- `bmad-testarch-trace`

Two workflows (`framework`, `ci`) DO NOT get a `persistent_facts` overlay
because their step-c files branch on `{detected_stack}`. Instead they
receive an `activation_steps_prepend` entry that runs a tiny helper
step-c file **only when the resolver reports Rust stack**. This step-c
reads the fragment set and pushes it into the workflow's own runtime
context (§7 mirrors the same mechanism for subagent seeds).

### 7. Subagent / worker payload contract

The single hardest point (both reviews flag it).

- Subagent step-c files (`nfr/step-04a..04e`, `test-review/step-03a..03f`,
  `automate/step-03a..03c`, `atdd/step-04a..04c`, `trace/step-04*`) run
  in a fresh context: `persistent_facts` are NOT inherited.
- The adapter emits a per-workflow **subagent seed** fragment
  (~ ≤ 512 bytes) that names only the rule IDs the subagent needs.
- Every workflow overlay adds an `activation_steps_prepend` step that,
  when the parent step composes `subagentContext = { … }`, appends the
  seed's filename to `subagentContext.knowledge_fragments_loaded`. This
  is the ONLY publicly-observable seam.
- L4 test must instrument at least one subagent-mode run of `atdd`
  (which has the most explicit `subagentContext = { … }` literal at
  `atdd/steps-c/step-04-generate-tests.md:56-83`) and assert the seed
  appears in the payload the child receives.
- Explicit fallback: when `tea_execution_mode: auto` degrades to
  `sequential`, the seed still lands in `persistent_facts` — no
  functional difference from the L4 sequential test in prompt §12.

### 8. Active-pack trace

Every TEA output the adapter targets gains a machine block:

```yaml
---
active_packs:
  - pack_id: async
    rule_ids: [RP-ASYNC-001, RP-ASYNC-004]
  - pack_id: unsafe
    rule_ids: [RP-UNSAFE-001, ...]
mode: <verdict enum value>
storyId: ...
storyKey: ...
headSha: ...
diffDigest: ...
---
```

`active_packs` is the machine trail that lets the RDX validator answer
"which packs did the workflow actually consider?" — the single most
important invariant against prompt §5.6 (agent-only vs workflow
integration).

---

## ENFORCEMENT PLANE (only after knowledge plane is proven)

### 9. TEA artefact / evidence schema

TEA artefacts stay in their existing free-form markdown format for
human use but add the YAML front-matter block from §8. RDX validator
reads only that block. This resolves TEA §6 + Builder-review §5:
schema fusion is limited to the 14-value verdict enum, not to the
whole Cat-1 conditional apparatus.

### 10. RDX validator extension

`rdx-validator` gains a new subcommand (`rdx-tea-validate`) that:

1. Reads TEA output(s) at the paths declared by `workflow.yaml:outputs[].path`.
2. Parses the front-matter block; refuses to emit `PASS` if any
   required field is missing.
3. Projects `active_packs` + `mode` into a full `rdx-evidence.v1`
   envelope. `active_packs` populates `activation.packs`; `mode`
   contributes to the aggregate verdict.
4. Enforces Cat-1 authority: an artefact claiming Cat-1 PASS is rejected
   before the envelope is written (schema-level constraint reused).

### 11. Cat-1..Cat-4 boundaries

Unchanged from RDX 1.1. TEA workflows may only WRITE fields that fall
under Cat-3 (`verdict_cat3`); Cat-1 and Cat-2 remain
`Evaluator: FORBIDDEN`, `Validator: WRITE` per
`tests/contracts/authority-matrix.json:32-46`. This is the invariant
adversarial tests (Phase-4 L7) target.

### 12. TEA gate vs RDX verdict

Separated. TEA's own gate vocabulary (`PASS/CONCERNS/FAIL/WAIVED`,
`trace/checklist.md:12`) stays inside TEA outputs. The RDX validator
consumes it only as an *input signal*; the RDX verdict is the schema
value emitted by the validator. No path exists for a TEA workflow to
mutate an RDX verdict directly.

### 13. Modes and CI

- MODE_0 (Advisory): TEA validator runs; verdicts recorded; no block.
- MODE_1 (Local Validated): `rdx-tea-validate` runs after `rdx-tea-*`
  wrapper skills; halts flow on FAIL.
- MODE_2 (Local Gated): pre-push hook picks up TEA validator alongside
  the existing RDX validator; no PR / no CI required.
- MODE_3 (CI Enforced): new required check
  `.github/workflows/rdx-tea-gate.yml` mirrors `rdx-gate.yml` and loads
  the RDX-TEA validator from the target branch (Option B, same
  trust-model as RDX 1.1).
- MODE_4 (Specialist Approval): unchanged — `approvers.yaml` +
  `approvals/<diff_digest>.json` gate Cat-4 rules that TEA workflows
  themselves cannot answer (unsafe / FFI / SemVer specialists).

### 14. Lifecycle

- Fresh install: `rdx-tea-setup` writes `_bmad/rdx-tea/**` and the seven
  `_bmad/custom/bmad-testarch-*.toml` overlays.
- Update: idempotent — re-generates fragments from canonical, refuses
  to overwrite `_bmad/custom/bmad-testarch-*.user.toml`.
- Uninstall: removes `_bmad/rdx-tea/**` and `_bmad/custom/bmad-testarch-*.toml`
  (but keeps `.user.toml` — user content).
- Compatibility: pinned to BMAD 6.8.0 initially; adapter refuses
  to install if `_bmad/tea/config.yaml` reports a Version outside the
  supported range.

### 15. CI trust model

Adapter and validator sources live in `rdx-validator/rdx_tea/` (new
subpackage). The CI workflow loads the validator from the target branch
via `--validator-source ref://main:rdx-validator/rdx_tea/`. PR-head
tampering is blocked by the same Option B mechanism RDX 1.1 already ships.

### 16. Rollback

`_bmad/rdx-tea/` and `_bmad/custom/bmad-testarch-*.toml` are the only
adapter-owned files. Rollback = uninstall + restore user overrides from
`.user.toml`.

### 17. Upgrade strategy

New BMAD version → SOURCE_LOCK update → hash mismatch triggers a full
regeneration + a compatibility check on `resolve_customization.py`
schema (script hash is one of the SOURCE_LOCK-tracked files).

---

## Test-first hooks per section

| §  | Failing tests written first | Currently green? |
|----|-----------------------------|:-:|
| 1  | `test_l0_source_lock_hash[core|router|packs|gov]`, `test_l0_status_vocabulary_complete` | ✅ |
| 2  | `test_l1_load_router_shape`, `test_l1_load_router_uses_canonical_file`, `test_l1_load_status_has_full_vocabulary` | ✅ |
| 3  | `test_l0_projection_generator_reads_only_canonical_inputs`, `test_l0_projection_generator_is_deterministic`, `test_l0_projection_generator_covers_all_packs`, `test_l0_projection_generator_emits_rdx_tea_index_row_per_pack`, `test_l1_render_all_no_wallclock_or_random_content` | ✅ |
| 4  | `test_l1_pack_fragment_contains_frontmatter`, `test_l1_pack_fragment_includes_every_related_rule_id` | ✅ |
| 5  | Explicit no-agent-overlay test | 🔴 (to write) |
| 6  | Per-workflow scope filter test | 🔴 (to write) |
| 7  | Subagent-seed presence + payload spy | 🔴 (to write; requires real TEA run) |
| 8  | Active-pack trace shape test on emitted TEA artefact | 🔴 (to write; requires real TEA run) |
| 9  | Front-matter parser test | 🔴 |
| 10 | Validator subcommand behaviour + Cat-1 authority preservation | 🔴 |
| 11 | Cat-1 authority regression from existing RDX suite | ✅ (via `tests/unit/validator/test_l2_core_checks.py` at head) |
| 12 | TEA gate ≠ RDX verdict test | 🔴 |
| 13 | Mode selector regression from existing RDX suite | ✅ (via `tests/bmad/modes/`) |
| 14 | Install/uninstall smoke on temp dir | 🔴 |
| 15 | `--validator-source` propagation test | 🔴 (extends existing L6 CI tests) |
| 16 | Rollback smoke | 🔴 |
| 17 | Hash-mismatch upgrade test | 🔴 |

The 🔴 rows enumerate the write-order for PROOF_COMPLETION_PLAN.md.

## Consequences

- Cost: developer builds one Python subpackage (`rdx_tea`), seven overlay
  TOMLs, and one JS-shaped subagent-seed helper. The projection generator
  is already at PoC level (~200 lines).
- Blast radius: overlays are `_bmad/custom/*.toml` files; uninstall is
  file-delete. No production RDX or BMAD file is patched.
- Fragility: subagent propagation depends on TEA workflow step files
  faithfully composing `subagentContext.knowledge_fragments_loaded`. A
  future TEA update that changes that variable name breaks the seam.
  L7 mutation tests must include this scenario.

## Open items requiring PROOF_COMPLETION_PLAN work

- G5 real TEA workflow runs
- G6 subagent propagation payload spy
- G7 behavioural baseline vs candidate eval
- G4 lifecycle install/update/uninstall
- G8..G11 enforcement-plane gates (blocked on knowledge-plane closure)
