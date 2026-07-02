# BMAD_CORE_EXTENSION_SURFACE — official extension points, source-verified

**Prompt section:** §8 (Phase 1).  
**Rule inherited from Phase 0:** knowledge-plane first — this document explicitly
classifies every extension point by whether it belongs to the *knowledge plane*
or the *enforcement plane*, so later phases wire knowledge before gates.

## 0. Provenance and independence

- Working RDX SHA: `d8140a25f8166bf0ca5ce5fc19f7cb1bd06a3d6d` (see `SOURCE_LOCK.md §1`).
- Host BMAD installation inspected: `/Users/m33tball/bmad_module_builder/`
  - Not a git repository. Version identifiers are read from `_bmad/*/config.yaml`
    (`Version: 6.8.0`, generated `2026-06-14T06:40:10.849Z`) and from file hashes.
  - This is **not** the upstream `bmad-code-org` source; it is a locally installed
    copy. Upstream SHAs remain `PENDING` per `SOURCE_LOCK §4`. This means every
    "official" claim below is conditional on: (a) the installed copy corresponds
    to unmodified upstream 6.8.0, and (b) the local hashes in
    `rdx-tea/evidence/hashes/PHASE1_HOST_BMAD_files_sha256.txt` are reproduced
    from that source.
- Independent Explore subagent transcript that enumerates the surface:
  `rdx-tea/evidence/screenshots-or-transcripts/phase1-explore-tea-surface.md`
  (invoked with read-only tools, in its own context; did not see the RDX
  clone).
- Every "official" verdict below is grounded in *source*. "Documentation-only"
  claims are called out.

The claims table at §7 is the shortest way to consume this file.

---

## 1. The three-layer TOML customization contract (KNOWLEDGE PLANE)

Source of truth: `/Users/m33tball/bmad_module_builder/_bmad/scripts/resolve_customization.py`.

**Layers (highest priority first):**

1. `{project-root}/_bmad/custom/{skill-name}.user.toml` — personal, gitignored.
2. `{project-root}/_bmad/custom/{skill-name}.toml` — team/org, committed.
3. `{skill-root}/customize.toml` — skill defaults (marked "DO NOT EDIT -- overwritten on every update").

**Merge rules (source-verbatim, no field-name special-casing):**

- Scalars (string, int, bool, float): override wins.
- Tables: deep merge (recursively apply these rules).
- Arrays of tables where every item shares the same identifier field (every
  item has `code`, or every item has `id`): merge by that key (matching keys
  replace, new keys append).
- All other arrays — including mixed `code`/`id` arrays, or arrays where only
  some items have those keys: **append** (base items followed by override items).
- **No removal mechanism** — overrides cannot delete base items. To suppress a
  default, fork the skill or override the item by code with a no-op.

**Executed by:** each skill's `SKILL.md` "On Activation" Step 1 runs
`python3 {project-root}/_bmad/scripts/resolve_customization.py --skill {skill-root} --key agent` (or `--key workflow`) and applies the merged result. If the script fails, the SKILL.md documents a manual fallback with the identical merge rules — see `bmad-tea/SKILL.md` §"On Activation" Step 1 verbatim.

**Consequences for the RDX-TEA adapter:**

- The adapter's *only* required overlay files are `_bmad/custom/bmad-tea.toml`,
  `_bmad/custom/bmad-testarch-*.toml` (one per testarch workflow it targets),
  and optionally `_bmad/custom/bmad-testarch-*.user.toml` for developer-local
  tuning. Nothing under `.claude/skills/**` needs to be patched.
- Because arrays without `code`/`id` **append**, RDX overrides *cannot break*
  the base `persistent_facts` reference to `file:{project-root}/**/project-context.md`
  — they can only extend it. This is the correctness invariant that lets us
  co-exist with any other module that also uses this glob.
- Because arrays keyed by `code` merge, RDX cannot silently duplicate menu
  items — an RDX entry with a fresh code (say `RUST`) appends cleanly; an entry
  reusing `TD` would *replace* the base TD entry (audit-required).
- **This resolves prompt §5.5** (unsafe TOML merge — "second `[agent]`" bug):
  the official installer is not string-concatenation, it is a structural merge
  driven by TOML parsing.

Extension-point classification: **OFFICIAL, KNOWLEDGE PLANE.**

---

## 2. `persistent_facts` glob loader (KNOWLEDGE PLANE — primary injection point)

Source: `.claude/skills/bmad-tea/SKILL.md` §"On Activation" Step 4 (verbatim
in `phase1-explore-tea-surface.md §6`), plus the identical Step 4 in each
`bmad-testarch-*/SKILL.md`.

- Every entry is either a literal sentence, or a `file:` path/glob under
  `{project-root}`.
- Glob expansion is done at activation time; matched files are loaded "in
  lexical path order as facts".
- The base value for every TEA workflow is
  `file:{project-root}/**/project-context.md` — a single, deliberately wide
  glob that lets other BMAD modules inject knowledge without editing TEA.

**Adapter usage:**

- Overlay `_bmad/custom/bmad-testarch-{workflow}.toml` with
  ```toml
  [workflow]
  persistent_facts = [
    "file:{project-root}/_bmad/rdx-tea/fragments/tea-{workflow}.md",
  ]
  ```
  and the file appears in every activation of that workflow after the base
  glob, in lexical order.
- Because the source of truth for `persistent_facts` **loading** is the skill
  activation (Step 4), and because loading happens *before* the workflow's
  `steps-c/` are executed, there is a mechanically-verifiable pre-condition:
  by the time any TEA step file runs, the fragment is in context.
- For **subagent** propagation this is not automatic — see §5.

**Consequence for prompt §5.3 / §5.4:** the projection generator we build in
Phase 3 must emit *actual* files at the paths referenced by the overlay,
byte-for-byte reproducible from `tests/contracts/router-rules.json` etc. of
the canonical RDX SHA. Anything hand-written would drift from the Router and
would violate G2 (canonical projection).

Extension-point classification: **OFFICIAL, KNOWLEDGE PLANE, primary knowledge
injection channel.**

---

## 3. `tea-index.csv` — workflow-local knowledge registry (KNOWLEDGE PLANE)

Source: `bmad-testarch-*/resources/tea-index.csv` (one per workflow, 8 files,
51–52 rows each, total 409 rows across the 8 workflows).

**Schema (header row of `bmad-testarch-test-design/resources/tea-index.csv`):**

```
id,name,description,tags,tier,fragment_file
```

- `id` — stable slug, e.g. `fixture-architecture`.
- `name` — human title.
- `description` — one-line context.
- `tags` — comma-separated selectors used by workflow steps for JIT loading.
- `tier` ∈ `core`, `extended`, `specialized` — three-level knowledge tiering.
- `fragment_file` — relative path to `resources/knowledge/<slug>.md`.

**Loading contract:** `bmad-tea/SKILL.md` §"Critical Actions" — verbatim:

> "Consult `./resources/tea-index.csv` to select knowledge fragments under
> `resources/knowledge/` and load only the files needed for the current task.
> Load the referenced fragment(s) from `./resources/knowledge/` before giving
> recommendations."

This is the JIT loading policy the prompt §4.4 calls out. It is a *per-skill*
CSV registry with declared tiers — the exact shape the RDX-TEA projection
needs to mirror.

**Adapter usage:**

- The projection generator emits an `rdx-tea-index.csv` next to a
  `knowledge/rdx-*.md` fragment set inside the installed overlay.
- Because `tea-index.csv` is a *skill-local* file, adding to it directly at
  `.claude/skills/bmad-testarch-*/resources/tea-index.csv` would be an
  *upgrade-fragile* patch (the installer overwrites the skill directory on
  update). The **correct** channel is either:
  - `_bmad/custom/bmad-testarch-{name}.toml` with a workflow-level activation
    hook that reads a second CSV, or
  - a `persistent_facts` entry pointing at an RDX-owned index and a fragment
    directory, letting the workflow step files pick fragments from either
    index via tag matching (the tag column is orthogonal).
- The second path is the only *documented* extension mechanism; the first
  would require a change to the workflow step file, which is not customizable
  by design.

Extension-point classification: **OFFICIAL loading contract, but the CSV
itself is inside skill roots and therefore NOT DIRECTLY EXTENSIBLE.** RDX must
provide its own parallel index/fragments and hook them via `persistent_facts`.

---

## 4. `activation_steps_prepend` / `activation_steps_append` (KNOWLEDGE PLANE)

Source: `bmad-tea/customize.toml` under `[agent]`, and every
`bmad-testarch-*/customize.toml` under `[workflow]`. All defaults are `[]`.

**Semantics:**

- Arrays without `code`/`id` → **append merge**.
- Executed by SKILL.md Steps 2 and 7 respectively (in `bmad-tea/SKILL.md`).

**Adapter usage:**

- RDX overlay can register a prepend step for the workflow that loads the
  Rust-specific fragment index conditionally (e.g. "if the story mentions
  Rust or a `Cargo.toml` sits at project root, add these fragments to
  context").
- Because prepend runs before the workflow's own `steps-c/`, this is where
  Router replay would happen.

Extension-point classification: **OFFICIAL, KNOWLEDGE PLANE, secondary
injection channel — used for conditional / dynamic behaviour that a static
`persistent_facts` cannot express.**

---

## 5. Subagent orchestration (KNOWLEDGE PLANE, adapter-owned)

Sources (Explore transcript §8, 10 hits):

- `bmad-testarch-atdd/steps-c/step-04-generate-tests.md` — declares
  execution modes `agent-team`, `subagent`, `sequential`; builds a literal
  JS-shaped `subagentContext = { … }` payload at line 67.
- `bmad-testarch-atdd/steps-c/step-04c-aggregate.md` — reads outputs from
  parallel subagents (API + E2E) and aggregates.
- `bmad-testarch-test-review/steps-c/step-03{c,e}-subagent-*.md` — sub-steps
  marked with `subagent: true` in front-matter.
- `bmad-testarch-trace/steps-c/step-04-analyze-gaps.md` — runtime probe
  `runtime.canLaunchSubagents?.()` to decide execution mode.
- Execution-mode resolution is driven by `_bmad/tea/config.yaml`'s
  `tea_execution_mode: auto`.

**Findings:**

- The subagent-payload contract is **not** a documented TOML surface. It is
  an *inlined literal* inside step files (`const subagentContext = { … }`).
  That means RDX cannot inject Rust knowledge into the subagent payload via
  `customize.toml` alone. This is exactly the failure the prompt §5.6 warns
  against ("agent-only vs workflow integration") and prompt §5.8 ("no real
  TEA runs").
- The only extension routes for subagent knowledge are:
  1. Enrich the *parent* workflow's context with Rust facts (via
     `persistent_facts` + workflow-local prepend), so the parent literally
     includes those facts into `subagentContext` when it composes the payload
     — this is workflow-file-dependent and needs a test that spies on the
     payload.
  2. Have RDX ship a *fragment naming convention* so the parent workflow's
     built-in "select fragments by tag" logic naturally picks Rust ones — this
     works only when the tag vocabulary in the parent's `tea-index.csv` is
     rich enough.
- The aggregator step (`step-04c-aggregate.md`) is the natural anti-drift
  point for RDX: it reads subagent outputs and can be extended (via prepend/
  persistent-facts) to check that a `active_packs: [...]` trace exists.
- **Runtime probe** `runtime.canLaunchSubagents?.()` means the workflow
  gracefully falls back to sequential mode when a runtime cannot spawn
  subagents. The RDX adapter must not assume `subagent` mode is always
  available — L3 tests must include a "sequential" run.

Extension-point classification: **OFFICIAL execution mode selector; UNOFFICIAL
subagent payload contract.** The adapter has to work *around* the payload
contract using `persistent_facts` propagation + naming convention.

---

## 6. `workflow.yaml`, outputs, and `config_source` (KNOWLEDGE PLANE inputs)

Source: `bmad-testarch-test-design/workflow.yaml` (representative). Its keys
are: `name`, `description`, `config_source`, `output_folder`, `test_artifacts`,
`user_name`, `communication_language`, `document_output_language`, `date`,
`installed_path`, `instructions`, `validation`, `template`, `variables`,
`outputs`, `required_tools`, `tags`, `execution_hints`.

- `config_source` = `{project-root}/_bmad/tea/config.yaml` (host file present,
  hashed in evidence).
- All `outputs[].path` templates land under `{test_artifacts}` (defaults to
  `{project-root}/_bmad-output/test-artifacts`). This is where the RDX
  artefact reader will look.

`workflow.yaml` itself is not user-editable by design (it lives in the
skill root and gets overwritten on install). It **defines** the outputs
schema and the config source, so the adapter reads it (not writes it) when
computing the artefact paths RDX will validate.

Extension-point classification: **NOT USER-EDITABLE.** Read-only for the
adapter. This is *good* — it means the outputs schema is stable across
customizations and can be relied upon by an RDX-side validator.

---

## 7. Summary claim table

| # | Point | Source of truth | Merge / merge? | Adapter can use? | Plane |
|---|---|---|:-:|:-:|:-:|
| A | Three-layer TOML customization | `_bmad/scripts/resolve_customization.py` | Structural (deep + keyed) | **YES** — primary overlay channel | KNOW |
| B | `persistent_facts` glob loader | `bmad-tea/SKILL.md` Step 4 + all testarch `SKILL.md` Step 4 | Array append | **YES** — primary knowledge injection | KNOW |
| C | `tea-index.csv` local registry | `bmad-testarch-*/resources/tea-index.csv` | N/A (skill-local file) | **INDIRECT** — mirror pattern via own index | KNOW |
| D | `activation_steps_{prepend,append}` | `customize.toml` `[agent]` / `[workflow]` | Array append | **YES** — dynamic hooks | KNOW |
| E | Subagent payload | `steps-c/step-04*` inlined `subagentContext = {…}` | Not customizable | **INDIRECT** — via facts+tag naming | KNOW |
| F | `workflow.yaml` outputs schema | `bmad-testarch-*/workflow.yaml` | Not customizable | **READ-ONLY** — artefact paths | KNOW |
| G | Skill wrapper pattern | precedent: RDX `rdx-code-review` wraps `bmad-code-review` | N/A | **YES** — pattern only | KNOW→ENF |
| H | RDX evidence schema | `tests/contracts/schemas/rdx-evidence.v1.schema.json` | Not customizable | **READ-ONLY** — target schema | ENF |
| I | `--validator-source` / `--contracts-dir` | `rdx-validator/rdx_validator/cli.py` | CLI args | **YES** — CI trust boundary | ENF |
| J | CI workflow shape (`rdx-gate.yml`, `rdx-ci-runner.py`) | `.github/workflows/`, `.github/scripts/` | Copy-and-adapt | **YES** — precedent | ENF |
| K | Pre-push hook | `.claude/skills/rdx-hooks/assets/pre-push.sh` | Copy-and-adapt | **YES** — precedent | ENF |
| L | `_bmad/rdx/approvers.yaml` | `_bmad/rdx/approvers.schema.json` | Schema-driven | **YES** — extension by role | ENF |

Legend: `KNOW` = knowledge plane; `ENF` = enforcement plane;
`KNOW→ENF` = knowledge-facing precedent used by an enforcement wrapper (e.g. `rdx-code-review`).

---

## 8. Extension gaps the adapter must build (KNOWLEDGE PLANE first)

Ordered by the knowledge-plane-first rule (§0):

1. **Projection generator** (`rdx-tea/poc/adapter/` in Phase 4). Reads
   the RDX contracts from §5 of `SOURCE_LOCK.md`, emits Rust knowledge
   fragments and an RDX-side index in a format compatible with §2 (`file:`
   glob) and §3 (mirror `tea-index.csv` shape).
2. **Router adapter**. Consumes `tests/contracts/router-rules.json`
   verbatim; emits an activation report (`active_packs: [...]` with source
   `rule_id`s) that survives subagent propagation (§5).
3. **Workflow overlay set** — one `_bmad/custom/bmad-testarch-*.toml` per
   TEA workflow the adapter targets, each appending to `persistent_facts`
   and optionally to `activation_steps_prepend`.
4. **Worker propagation aid** — since the subagent payload contract is not
   customizable (§5), the adapter's fragments must be tagged so the parent
   workflow's own selector logic picks them naturally.
5. **Artefact reader** — parses `{test_artifacts}/*.md` written by the TEA
   workflow (§6) and re-emits an `rdx-evidence.v1`-compatible envelope. This
   is the boundary where the enforcement plane will later plug in.

Only after 1–5 pass their L0–L5 layered tests can the following enforcement
gaps be designed and closed:

6. **RDX validator extension** — new deterministic checks that read the
   artefact envelope (item 5).
7. **TEA gate vs RDX verdict split** — reuse `rdx-evidence.v1` mode label
   without conflating TEA's own gate output.
8. **CI trust model** — reuse `--validator-source` (item I) so PR head cannot
   ship its own validator or its own adapter policy.

## 9. What Phase 1 rules OUT as "not an extension point"

- Editing skill files under `.claude/skills/bmad-tea/**` or
  `.claude/skills/bmad-testarch-*/**` directly. These are declared "DO NOT
  EDIT — overwritten on every update" in every `customize.toml` header and
  will be regenerated by the installer.
- Editing `workflow.yaml`. Read-only by design (§6).
- Editing `tea-index.csv` files inside skill roots (§3). Only own registries.
- Editing `steps-c/*.md` step files. Not customizable; any dynamic behaviour
  must come from `activation_steps_prepend` / `activation_steps_append`.

## 10. Open items for Phase 2 (Builder + TEA official reviews)

Phase 2 must independently confirm from *upstream source*:

- The exact `resolve_customization.py` at upstream 6.8.0 (host copy may or
  may not diverge; hash mismatch triggers a §8 addendum to `SOURCE_LOCK.md`).
- Whether upstream ships a *documented* subagent-payload extension we missed.
- Whether `tea-index.csv` will remain the resource-registry format in newer
  BMAD releases, or whether it moves to JSON / SQLite / a manifest — this
  determines the RDX-side format we should mirror.
- Whether the installer's TOML merger honors comment preservation
  (prompt §5.5 "arrays, comments, nested tables"). Local test in Phase 4.

Until Phase 2 confirms these, treat every "OFFICIAL" verdict above as
"OFFICIAL (host-6.8.0 only, upstream SHA PENDING)".

---

## 11. Addendum after Phase 2 Builder review

Full transcript: `rdx-tea/evidence/screenshots-or-transcripts/phase2-builder-review.md`.

The independent Builder-role subagent, given only the host BMAD 6.8.0 source,
confirmed points A/B/C/D/F/H in §7 and CORRECTED four assumptions this file
made. Recorded here so downstream ADR reads a single truth:

1. **Install target for generated fragments is WRONG in §2 above.**
   `_bmad/custom/` is reserved for `_bmad/custom/<skill>.toml` /
   `_bmad/custom/<skill>.user.toml` override files only (per
   `bmad-customize/SKILL.md:77-79`). Generated RDX-owned knowledge files
   must live at **`{project-root}/_bmad/rdx-tea/knowledge/*.md`** and be
   referenced from the overlay with
   `persistent_facts = ["file:{project-root}/_bmad/rdx-tea/knowledge/**/*.md"]`.
   The PoC at `rdx-tea/poc/projections/` uses that layout in disposable
   form; production install must write to `{project-root}/_bmad/rdx-tea/`.

2. **Subagent knowledge seam is transitive-only, not direct** (§5 stated
   this; Builder review pinpointed the exact code path):
   `bmad-testarch-atdd/steps-c/step-04-generate-tests.md:56-83` assembles
   `subagentContext = { …, knowledge_fragments_loaded, config }` and passes
   only `subagentContext` to workers (lines 172, 194). Rust fragments reach
   workers *only if the parent step forwards them* by putting them in
   `knowledge_fragments_loaded`, and that forwarding is not a published
   contract. Phase-4 L4 test MUST spy on `subagentContext` in a real
   workflow run and assert the projection appears there.

3. **The tiered loader in steps is JS, not TOML.**
   `bmad-testarch-atdd/steps-c/step-01-preflight-and-context.md:105-193`
   contains the JS-driven tier resolution that computes which fragments to
   load. Neither `activation_steps_prepend` nor any `[workflow]` override
   can *remove* an already-tiered fragment. Overlays can only *append*.
   Any earlier claim that RDX "bends the loader" via TOML is rejected.

4. **Module-level artefacts are required by `validate-module.py`.**
   `bmad-module-builder/references/validate-module.md:19-27`. For a
   standalone `rdx-tea` module: `assets/module.yaml`, `assets/module-help.csv`,
   `assets/module-setup.md`, `scripts/merge-config.py`,
   `scripts/merge-help-csv.py`, `evals.json` with strong rubrics,
   optional `triggers.json`. `rdx-tea/evals/baseline/` and
   `rdx-tea/evals/variant-d/` are currently empty → **module cannot pass
   `validate-module.py` yet**. Phase 3 ADR must add these to the required
   deliverable list before verdict `PROVEN` is possible.

5. **`rdx-evidence.v1` compatibility with TEA artefacts is UNPROVEN.**
   No TEA step (`bmad-testarch-*/steps-c/*.md`) emits an envelope
   matching `tests/contracts/schemas/rdx-evidence.v1.schema.json`. Phase 3
   must design a mapping (or extend the schema with a TEA-specific `oneOf`
   branch); until then G8 (validator integration) is `BLOCKED` on this
   mapping.

6. **Every override skill must be enumerated by name.** The Builder review
   correctly points out that "8 `bmad-testarch-*` overlays" is not a
   concrete plan. Phase 3 ADR must list each of the 8 workflows
   (test-design, framework, ci, atdd, automate, test-review, nfr, trace)
   and, for each, state whether the RDX-TEA adapter installs an overlay
   and why.

### Blocking objections still open after Builder review

The Builder review left 6 blocking objections open (see Blocking Objections
block of `phase2-builder-review.md`). Downstream phases must either close
each objection with source-cited evidence or downgrade the verdict.
