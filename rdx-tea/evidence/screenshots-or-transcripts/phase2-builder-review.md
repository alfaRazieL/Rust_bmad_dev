# Phase 2 — BMad Builder Independent Review of RDX × TEA Variant D

Reviewer role: BMad Module/Agent/Workflow Builder maintainer. No prior exposure to the proposal. Source-grounded.

## 1. Standalone `rdx-tea` module vs. sparse override set?
Partially. The customize surface is narrow: `[agent]`/`[workflow]` with `activation_steps_*`, `persistent_facts`, `principles`, `on_complete`, keyed menus (`bmad-customize/SKILL.md:62-71`). Out-of-surface intent is explicitly routed to `bmad-builder` (`bmad-customize/SKILL.md:107-111`). A pure sparse override set can only append facts and prepend steps — no generator, no lifecycle, no registered skills. A full module is defensible *only* on the generator + validator adapter, not on the overlays alone.

## 2. Official extension surface for Rust knowledge injection?
For workflows: `[workflow].persistent_facts` and `[workflow].activation_steps_prepend/append` — verified in `bmad-testarch-atdd/customize.toml:14-34` and merged by `resolve_customization.py:150-166`. For the TEA agent: `bmad-tea/customize.toml:38-40` (append arrays) and `[[agent.menu]]` (keyed by `code`). `persistent_facts` accepts `file:` globs (`bmad-tea/customize.toml:38-40`) — the intended injection point.

## 3. Avoid patching TEA core?
Yes, and required. Every TEA `customize.toml` opens with `# DO NOT EDIT -- overwritten on every update.` (`bmad-tea/customize.toml:1`, `bmad-testarch-atdd/customize.toml:1`). `resolve_customization.py:31-33`: "No removal — overrides cannot delete base items." Overlays may only append/replace by `code`; they cannot rewrite the tiered loader in `bmad-testarch-atdd/steps-c/step-01-preflight-and-context.md:105-193`.

## 4. Safe TOML merge shape
`resolve_customization.py:150-166` (`deep_merge`): tables deep-merge, scalars override, arrays via `_merge_arrays`. `_merge_arrays` (lines 139-147) does keyed merge only when *every* item — base + override combined — shares `code` or `id` (`_KEYED_MERGE_FIELDS`, line 53); mixed arrays append (lines 96-110). Consequences: (a) `persistent_facts`, `activation_steps_*`, `principles` → append; (b) `[[agent.menu]]` keyed by `code` → replace matching, append new; (c) comments are not preserved (tomllib parses only tables — line 42), so no comment-preservation concern at runtime. Overlays must be sparse (`bmad-customize/SKILL.md:71`).

## 5. Install / update / uninstall pattern for `_bmad/custom/` overlays
The Module Builder does not treat `_bmad/custom/` as installable payload. Modules ship `assets/module.yaml` + `module-help.csv` (`bmad-module-builder/references/create-module.md:96-116`); `bmad-bmb-setup/SKILL.md:10-16` writes only to `_bmad/config.yaml`, `_bmad/config.user.yaml`, `_bmad/module-help.csv`. Overlays are a *user* artefact. There is no documented pattern for a module to write `_bmad/custom/*.toml`. If RDX ships them, `rdx-tea-setup` must implement anti-zombie merge (mirror `bmad-bmb-setup/scripts/merge-help-csv.py:201-207`) and refuse to clobber user-authored overrides.

## 6. Documented seam for knowledge to TEA sub-workers?
None. Worker context is a JS payload assembled in `bmad-testarch-atdd/steps-c/step-04-generate-tests.md:56-83` (`subagentContext = { … knowledge_fragments_loaded, config }`); workers only receive `subagentContext` (lines 172, 194). No third-party injection hook. The only Builder-sanctioned fallback is `[workflow].persistent_facts` (activated at the parent step and materialised into `knowledge_fragments_loaded` at `step-01-preflight-and-context.md:143-193`) — Rust fragments reach workers *only* transitively through that list, and only if the parent step actually forwards them. That forwarding is not guaranteed by any published contract.

## 7. Where do generated fragments live?
Not under `.claude/skills/bmad-testarch-*/` (DO NOT EDIT). Not under `_bmad/custom/` — `bmad-customize/SKILL.md:77-79` restricts that path to `<skill>.toml`/`.user.toml`. The Builder's convention for module-owned files is `_bmad/{module-code}/…` (implicit in `bmad-bmb-setup/SKILL.md:24-27`). Correct home: `{project-root}/_bmad/rdx-tea/knowledge/*.md`, referenced by an overlay `persistent_facts` entry `file:{project-root}/_bmad/rdx-tea/knowledge/**/*.md`. Skill-local `assets/` is wrong for generated content — overwritten on install.

## 8. Module validation
`bmad-module-builder/references/validate-module.md:19-27` runs `scripts/validate-module.py`. Structural checks: `module.yaml` completeness, CSV integrity, orphans, duplicate menu codes, broken before/after refs, agent-roster drift vs. each agent's `customize.toml`. Quality pass (`validate-module.md:29-56`). Required artefacts: `assets/module.yaml`, `assets/module-help.csv`; for standalone: `assets/module-setup.md`, `scripts/merge-config.py`, `scripts/merge-help-csv.py` (`validate-module.md:14-17`). Headless JSON: `structural_issues`, `quality_findings` (`validate-module.md:73-84`).

## 9. Variant D claims to REJECT or MODIFY
- **Reject:** "adapter appends to `activation_steps_prepend` to bend TEA's tiered loader." The loader is JS-driven (`bmad-testarch-atdd/steps-c/step-01-preflight-and-context.md:105-193`), not TOML-driven, and no removal is available (`resolve_customization.py:31-33`).
- **Reject:** shipping generated fragments under `_bmad/custom/` — contradicted by `bmad-customize/SKILL.md:77-79`.
- **Modify:** "workers consume the RDX overlay directly." Per `step-04-generate-tests.md:56-83`, only `subagentContext.knowledge_fragments_loaded` reaches workers. Adapter must state this transitivity and prove it.
- **Modify:** `bmad-testarch-*.toml` plural — eight testarch skills exist; each override needs enumeration and justification. Menu changes go on `bmad-tea.toml` (agent); per-workflow customization is per-skill (`bmad-customize/SKILL.md:44-58`).
- **Reject without evidence:** `rdx-evidence.v1` compatibility with TEA artefacts. No TEA step emits that envelope; RDX must map it under `tests/contracts/schemas/`.

## 10. Required artefacts before sign-off
- `assets/module.yaml` matching `bmad-bmb-setup/assets/module.yaml` shape (`code`, `name`, `module_version`, `module_greeting`, prompts with `result:` templates).
- `assets/module-help.csv` with `menu-code`, `action`, `phase`, `after`/`before`, `required`, `output-location`, `outputs` (`create-module.md:64-92`).
- Standalone-mode files: `assets/module-setup.md`, `scripts/merge-config.py`, `scripts/merge-help-csv.py`.
- `evals.json`-shape cases per `bmad-eval-runner/references/eval-format.md:7-19` with strong rubrics (§"Strong versus weak expectations"). `rdx-tea/evals/{baseline,variant-d}/` are currently empty — blocking.
- `triggers.json` if description/routing evaluation is planned (`eval-format.md:86-87`).
- PoC transcript proving: (a) sparse overlay lands via `resolve_customization.py --key workflow`; (b) `knowledge_fragments_loaded` in a real TEA worker payload contains RDX paths; (c) `validate-module.py` returns `status=pass`.
- Explicit enumeration of every overridden `bmad-testarch-*` skill.

## Blocking objections (points 6 and 9)
1. **No documented sub-worker knowledge seam.** Variant D assumes direct worker consumption; only `subagentContext.knowledge_fragments_loaded` reaches workers (`step-04-generate-tests.md:56-83`). PoC forwarding required.
2. **Wrong home for generated fragments.** `_bmad/custom/` is reserved for override TOMLs (`bmad-customize/SKILL.md:77-79`). Move to `_bmad/rdx-tea/knowledge/…`.
3. **"Overlays bend the loader" unsupported.** Loader is JS (`step-01-preflight-and-context.md:105-193`); append cannot remove or reorder (`resolve_customization.py:31-33`).
4. **Missing enumeration of `bmad-testarch-*` overlays.** Eight candidates; proposal must list each and justify.
5. **`rdx-evidence.v1` compatibility unproven.** No TEA step emits it; show mapping or drop.
6. **Empty `evals/baseline/` and `evals/variant-d/`.** No cases → no gate (`eval-format.md`). Blocking.
