# BUILDER_TEA_RECONCILIATION — resolving the two independent reviews

**Sources:**
- `rdx-tea/evidence/screenshots-or-transcripts/phase2-builder-review.md` — Builder-role review (827 w).
- `rdx-tea/evidence/screenshots-or-transcripts/phase2-tea-review.md` — TEA-role review (899 w).

Both reviews were performed by independent subagents in fresh contexts (no
knowledge of each other), reading only host BMAD 6.8.0 source + the RDX
canonical contracts. Each ended with a "blocking objections" block. This
document merges their findings into a single truth used by ADR-001.

---

## 1. Where Builder and TEA AGREE (11 confirmed constraints)

| # | Agreed constraint | Builder anchor | TEA anchor |
|---|---|---|---|
| A1 | Skill roots are "DO NOT EDIT" — no direct patching of `.claude/skills/bmad-testarch-*/**` or `bmad-tea/**` | `bmad-tea/customize.toml:1`, `bmad-testarch-atdd/customize.toml:1` | Same line-1 comment, cited in §2 and §10(e) |
| A2 | Overlays go through `resolve_customization.py` three-layer merge | `resolve_customization.py:150-166` | `test-design/customize.toml:32-34` resolver Step 4 |
| A3 | `persistent_facts` accepts `file:` globs; arrays without `code`/`id` append | `resolve_customization.py:139-147` | Every `bmad-testarch-*/SKILL.md` Step 4 |
| A4 | Agent-level overlay is too broad — fires for every menu item | Implicit (Q1: "sparse override set alone cannot"...) | Explicit: "wrong seam" §2, "fires for every menu item incl. Teach-Me-Testing" |
| A5 | Sub-worker payload is a JS literal — not TOML-extensible | `step-04-generate-tests.md:56-83` | `step-04-analyze-gaps.md:95-110` |
| A6 | **Subagent context does NOT inherit `persistent_facts`** — parent fragments must be re-declared inside each subagent step-c | Implicit (Q6 "transitivity is not a published contract") | Explicit in §3 with per-workflow subagent step enumeration |
| A7 | Generated RDX-owned files must live under `_bmad/` outside skill roots | `_bmad/{module-code}/…` convention (`bmad-bmb-setup/SKILL.md:24-27`) | `{project-root}/_bmad/custom/rdx-tea/knowledge/` (§10(e)) |
| A8 | `rdx-evidence.v1` schema fusion with TEA artefacts is unsound as-is | "unproven" (Q9) | "reject; share `verdict` enum only" (§6) |
| A9 | An eval gate is missing and required | "empty evals/baseline and evals/variant-d — blocking" (BO#6) | "no `evals/` exists under any `bmad-testarch-*`" (§8) |
| A10 | Every override needs per-workflow justification (no uniform 8-way overlay) | Q9 "enumerate and justify" | §10(c) "REJECT uniform overlay" |
| A11 | Frontmatter binding for machine consumption is missing on TEA outputs | Implicit (Q10 "PoC transcript proving…") | Explicit list `storyId,storyKey,headSha,diffDigest` (§9) |

---

## 2. Where Builder and TEA DISAGREE (1 open item)

| # | Item | Builder | TEA | Resolution |
|---|---|---|---|---|
| D1 | Exact path under `_bmad/` for generated fragments | `_bmad/rdx-tea/knowledge/` (module code convention) | `_bmad/custom/rdx-tea/knowledge/` ("survives skill updates") | **Adopt Builder's `_bmad/rdx-tea/knowledge/`.** TEA's justification (survives skill updates) is satisfied by *any* path outside skill roots. Builder cites the specific "`_bmad/custom/` is `<skill>.toml`/`.user.toml` only" restriction (`bmad-customize/SKILL.md:77-79`). Putting an entire subtree with generated `.md` files under `_bmad/custom/` violates that restriction. `_bmad/rdx-tea/` follows the module-code convention `_bmad/{code}/…` established by `bmb`, `bmm`, `cis`, `tea`, `wds`. |

---

## 3. Consolidated "Variant D2" constraints

Merging the two reviews yields the following non-negotiable design points.
These become the acceptance criteria of ADR-001.

### 3.1 Overlay topology

- Overlays live under `_bmad/custom/bmad-testarch-{name}.toml` for the
  seven workflows that receive Rust context, plus optionally
  `bmad-testarch-{name}.user.toml` for developer-local extras.
- NO overlay for `bmad-tea` agent (agent-level overlay is over-broad; TEA §10(a)).
- NO overlay for `bmad-testarch-framework/customize.toml` or
  `bmad-testarch-ci/customize.toml` — these workflows branch on
  `{detected_stack}` and would inject Rust context into JS/Python projects.
  Framework and CI Rust knowledge is loaded via *a step-c injection file*
  that only runs when the resolver reports Rust stack.

### 3.2 Install target for generated files

- Generated RDX-owned Rust knowledge fragments:
  `{project-root}/_bmad/rdx-tea/knowledge/*.md`.
- Referenced from overlay `persistent_facts` with absolute
  `file:{project-root}/_bmad/rdx-tea/knowledge/**/*.md` glob (per-workflow
  subset).
- Generated adjunct index rows (see §3.3) placed into each workflow's
  existing `resources/tea-index.csv` **only via an overlay-driven post-load
  step**, not by editing the skill file. (Rationale: skill root is
  "DO NOT EDIT"; TEA §10(b) requires the index to be augmented; an
  activation-prepend step that reads a second CSV and merges into the
  in-memory index is the only compatible route.)

### 3.3 Per-workflow scope (rules × workflows)

Only rules whose scope-of-concern intersects the workflow are projected.
Union of Builder Q9 + TEA §7:

| Workflow | Rules IN | Rules OUT |
|---|---|---|
| test-design | `CORE-*`, `RP-ASYNC-*`, `RP-UNSAFE-*`, `RP-FFI-*`, `RP-MACRO-*`, `RP-API-*`, `RP-TEST-*`, `RP-DATA-*`, `RP-DB-*`, `RP-TIME-*` | `RP-CARGO-*`, `RP-OPS-*`, `GOV-*` |
| framework | `RP-CARGO-*` (test-scaffolding pieces), `RP-TEST-*` | `RP-ASYNC-*`, `RP-DB-*`, `RP-API-*`, `RP-PERF-*`, `RP-TIME-*`, `RP-UNSAFE-*`, `RP-FFI-*`, `RP-MACRO-*`, `RP-DATA-*` |
| ci | (`GOV-*` project-policy hooks only) `RP-TEST-*` `RP-CARGO-*` runners section | `RP-UNSAFE-*`, `RP-FFI-*`, `RP-MACRO-*`, `RP-DATA-*` — CI writes pipelines, not source lints |
| atdd | `RP-ASYNC-*`, `RP-API-*`, `RP-TEST-*` | `RP-UNSAFE-*`, `RP-FFI-*`, `RP-MACRO-*` |
| automate | `RP-TEST-*`, `RP-ASYNC-*`, `RP-API-*` | `RP-OPS-*`, `RP-CARGO-*` |
| test-review | `RP-TEST-*`, `RP-API-*` | `RP-CARGO-*`, `RP-OPS-*`, `RP-DB-*` |
| nfr | `RP-UNSAFE-*`, `RP-DATA-*`, `RP-PERF-*`, `RP-DB-*`, `RP-TIME-*`, `RP-OPS-*` | `RP-CARGO-*`, `RP-TEST-*` |
| trace | `RP-TEST-*` only (AC ↔ test mapping) | all other `RP-*` |

Universally: `GOV-*` stays inside RDX governance, is not pushed into
TEA workflows.

Also: every appended row in each `tea-index.csv` defaults to `tier=specialized`
(TEA §11). Only rows for `RP-TEST-*` may be `extended`; nothing is `core`.

### 3.4 Subagent propagation contract

Because subagent boundaries reset context (TEA §3, Builder BO#1):

- The projection generator emits, per-workflow, **also** a "subagent seed"
  fragment. It's small (≤ 512 bytes) and contains just the tag-selectable
  rule IDs the subagent needs.
- Every workflow overlay adds an `activation_steps_prepend` entry that,
  when the parent hits a subagent step, injects the seed into
  `subagentContext.knowledge_fragments_loaded` *by name*. This is the
  only publicly-observable seam.
- L4 tests must instrument at least one subagent-mode run and assert
  the seed appears in the payload the child receives.

### 3.5 Schema policy

- TEA does NOT emit `rdx-evidence.v1` envelopes.
- TEA output frontmatter carries `storyId`, `storyKey`, `headSha`,
  `diffDigest`, `mode` (verdict enum subset), `active_packs`. `mode` uses
  the 14-value verdict enum from `rdx-evidence.v1.schema.json:120-138`
  verbatim — this is the only shared field.
- RDX-side validator reads the frontmatter block, projects it into a
  full `rdx-evidence.v1` envelope, and completes the enforcement side
  independently.

### 3.6 Module-level artefacts

For `rdx-tea` to pass `validate-module.py`:

- `rdx-tea/assets/module.yaml` (fields per `bmad-bmb-setup/assets/module.yaml`)
- `rdx-tea/assets/module-help.csv`
- `rdx-tea/assets/module-setup.md`
- `rdx-tea/scripts/merge-config.py`
- `rdx-tea/scripts/merge-help-csv.py`
- `rdx-tea/evals/baseline/cases.yaml` (baseline mode)
- `rdx-tea/evals/variant-d/cases.yaml` (variant mode) referencing the
  overlay set as `--variant-path`

### 3.7 What was UNAMBIGUOUSLY REJECTED in Variant D

- Agent-level `bmad-tea` overlay for Rust knowledge injection.
- Uniform 8-way overlay across all `bmad-testarch-*` workflows.
- Parallel RDX-owned `rdx-tea-index.csv` that "replaces" TEA's tea-index.csv.
- Assumption that `persistent_facts` propagate into subagents.
- Writing generated files into skill-owned `resources/knowledge/`.
- Full `rdx-evidence.v1` schema fusion for TEA artefacts.

---

## 4. Impact on the running L0/L1 PoC

The PoC in `rdx-tea/poc/adapter/projection.py` and the 32 green tests
(L0 + L1) verify contract-level invariants that survive Variant D2:

- Canonical hashes match SOURCE_LOCK.
- 14-verdict vocabulary preserved.
- 12 Router packs, activation policies, confidence classes preserved.
- Canonical rule ID prefixes preserved (no `RUST-*`).
- Story-tag-required packs preserved.
- Projection generator reads only canonical inputs.
- Projection generator is deterministic (byte-identical re-run).
- Projection covers all 12 packs.
- Index CSV mirrors `tea-index.csv` schema.

Variant D2 changes the *filtering* and *installation* logic (per-workflow
scope, install path, subagent seed) but leaves the projection generator's
contract-level guarantees intact. Those tests remain valid Phase-4 L0/L1
evidence for the knowledge-plane G2 and G3 gates *at the contract layer*.

What the PoC does **not** prove (and Variant D2 does not turn this into
proof either — real integration work is required):

- G5 (real TEA workflows): no real TEA run happened.
- G6 (worker propagation): subagent seed mechanism is designed, not tested.
- G7 (measured quality benefit): no baseline eval yet.
- G4 (safe lifecycle): no install/uninstall/update test.
- All enforcement-plane gates G8..G11 are not attempted yet
  (correct — knowledge-plane-first rule).
