# Phase 1 Explore agent — TEA extension surface enumeration

Independent Explore subagent, invoked at `d8140a25…`, `rdx-tea-integration`.

Working directory: `/Users/m33tball/bmad_module_builder/`  (host BMAD 6.8.0 install)
Not the RDX clone directory.

Model / tools: Explore subagent, read-only tools only (Bash, Read, Grep, Glob).
Instructions: enumerate `bmad-tea/`, `bmad-testarch-*/`, `_bmad/tea/`, `_bmad/custom/`, `_bmad/scripts/`.
Report format: strict, cited, no prose beyond section headers.

---

## 1. `bmad-tea` agent customize.toml

**File:** `/Users/m33tball/bmad_module_builder/.claude/skills/bmad-tea/customize.toml`

Top-level customization keys under `[agent]`:
- `name` = "Murat"
- `title` = "Master Test Architect and Quality Advisor"
- `icon` = "🧪"
- `activation_steps_prepend` = [] (array)
- `activation_steps_append` = [] (array)
- `persistent_facts` = [`"file:{project-root}/**/project-context.md"`] (array)
- `role` = "…"
- `identity` = "…"
- `communication_style` = "…"
- `principles` = [array of 7 items]

Menu items (all under `[[agent.menu]]`):
- TMT → bmad-teach-me-testing
- TD  → bmad-testarch-test-design
- TF  → bmad-testarch-framework
- CI  → bmad-testarch-ci
- AT  → bmad-testarch-atdd
- TA  → bmad-testarch-automate
- GATE → (inline prompt, no skill)
- RV  → bmad-testarch-test-review
- NR  → bmad-testarch-nfr
- TR  → bmad-testarch-trace

## 2. TEA workflow customize.toml (per workflow) — all 8 identical

Files: `bmad-testarch-{test-design, framework, ci, atdd, automate, test-review, nfr, trace}/customize.toml`.

All workflows under `[workflow]`:
- `activation_steps_prepend` = []
- `activation_steps_append` = []
- `persistent_facts` = [`"file:{project-root}/**/project-context.md"`]
- `on_complete` = ""

Differences from `bmad-tea` agent shape: workflows lack `name`, `title`, `icon`, `role`, `identity`, `communication_style`, `principles`. Only `activation_steps_*`, `persistent_facts`, `on_complete` are customizable.

## 3. TEA `workflow.yaml` shape (using test-design as canonical)

Top-level keys: `name`, `description`, `config_source`, `output_folder`, `test_artifacts`, `user_name`, `communication_language`, `document_output_language`, `date`, `installed_path`, `instructions`, `validation`, `template`, `variables`, `outputs`, `required_tools`, `tags`, `execution_hints`.

`config_source` = `"{project-root}/_bmad/tea/config.yaml"`.

`outputs[].path` templates (test-design):
- `"{test_artifacts}/test-design-architecture.md"` (mode `system-level`, audience `architecture`)
- `"{test_artifacts}/test-design-qa.md"` (mode `system-level`, audience `qa`)
- `"{test_artifacts}/test-design/{project_name}-handoff.md"` (mode `system-level`, audience `bmad-integration`)
- `"{test_artifacts}/test-design-epic-{epic_num}.md"` (mode `epic-level`)

`variables`: `design_level`, `mode`, `test_stack_type`.

All 7 other workflows share the same top-level shape (all have `config_source`, `variables`, `outputs`/`default_output_file`, `required_tools`, `tags`, `execution_hints`). Minor differences: template file names vary; `atdd` has `default_output_file`; `trace/nfr/test-review` have `outputs[]` with mode-specific paths.

## 4. Step-file structure (test-design as canonical)

Under `bmad-testarch-test-design/`:
- `steps-c/`: `step-01-detect-mode.md`, `step-01b-resume.md`, `step-02-load-context.md`, `step-03-risk-and-testability.md`, `step-04-coverage-plan.md`, `step-05-generate-output.md`.
- `steps-e/`: `step-01-assess.md`, `step-02-apply-edit.md`.
- `steps-v/`: `step-01-validate.md`.

All 7 other workflows follow the identical `steps-c/ | steps-e/ | steps-v/` layout with proportional file counts.

## 5. Knowledge / resources per workflow

Each workflow has `resources/knowledge/` (~50 `.md` fragments) and `resources/tea-index.csv`.
Line counts of the 8 `tea-index.csv` files:
```
52 bmad-testarch-atdd
51 bmad-testarch-automate
51 bmad-testarch-ci
51 bmad-testarch-framework
51 bmad-testarch-nfr
51 bmad-testarch-test-design
51 bmad-testarch-test-review
51 bmad-testarch-trace
```

`tea-index.csv` schema (verbatim first header row of `bmad-testarch-test-design`):
```
id,name,description,tags,tier,fragment_file
```
Tier values observed: `core`, `extended`, `specialized`.

`persistent_facts` references the glob `file:{project-root}/**/project-context.md` — no other glob is currently used by any TEA workflow.

## 6. Where `persistent_facts` is actually loaded

Declarative loading, executed by `bmad-tea/SKILL.md` §"On Activation" Step 4:
> "Treat every entry in `{agent.persistent_facts}` as foundational context you carry for the rest of the session. Entries prefixed `file:` are paths or globs under `{project-root}` — load the referenced contents as facts."

Same-shaped Step 4 exists in each `bmad-testarch-*/SKILL.md` referring to `{workflow.persistent_facts}`.

Grep for `persistent_facts` in step files returned no runtime references — loading is declarative in SKILL.md activation, not imperative in `steps-c/*.md`.

## 7. Existing `_bmad/custom/` overrides

1. `_bmad/custom/.gitignore`
2. `_bmad/custom/bmad-agent-architect.toml` — `[agent]` with `persistent_facts`, `principles`
3. `_bmad/custom/bmad-agent-dev.toml` — `[agent]` with `persistent_facts`, `principles`
4. `_bmad/custom/bmad-agent-pm.toml` — `[agent]` with `persistent_facts`, `principles`
5. `_bmad/custom/config.toml` — empty template, no sections
6. `_bmad/custom/config.user.toml` — empty template, no sections

No workflow-level override files (`bmad-testarch-*.toml`) exist. This is the *unclaimed* extension slot the RDX-TEA adapter needs.

## 8. Subagent / worker payload mechanism (10 hits)

1. `bmad-testarch-atdd/steps-c/step-04-generate-tests.md:11` — "Select execution mode deterministically … agent-team, subagent, or sequential execution."
2. `bmad-testarch-atdd/steps-c/step-04-generate-tests.md:67` — `const subagentContext = {`
3. `bmad-testarch-atdd/steps-c/step-04c-aggregate.md:12` — "Read outputs from parallel subagents (API + E2E red-phase test generation), aggregate results, verify TDD red phase compliance"
4. `bmad-testarch-atdd/steps-c/step-04c-aggregate.md:50` — "**Read API test subagent output:**"
5. `bmad-testarch-test-review/steps-c/step-03c-subagent-maintainability.md:4` — `subagent: true` (step frontmatter flag)
6. `bmad-testarch-test-review/steps-c/step-03e-subagent-performance.md:4` — `subagent: true`
7. `bmad-testarch-test-review/steps-c/step-03f-aggregate-scores.md:12` — "Read outputs from 4 quality subagents, calculate weighted overall score (0–100)…"
8. `bmad-testarch-trace/steps-c/step-04-analyze-gaps.md:3` — "Complete Phase 1 with adaptive orchestration (agent-team, subagent, or sequential)"
9. `bmad-testarch-trace/steps-c/step-04-analyze-gaps.md:71` — `if (normalized === 'subagent' …)`
10. `bmad-testarch-trace/steps-c/step-04-analyze-gaps.md:97` — `supports.subagent = runtime.canLaunchSubagents?.() === true;`

Patterns: execution modes `agent-team`, `subagent`, `sequential` resolved from `tea_execution_mode` config (present in `_bmad/tea/config.yaml`). Subagent-eligible steps carry `subagent: true` in frontmatter. Payload composition uses a JS-object literal (`subagentContext = { … }`).

## 9. `bmad-tea` SKILL.md contract

File: `/Users/m33tball/bmad_module_builder/.claude/skills/bmad-tea/SKILL.md`, lines 1–4:
- `name`: `bmad-tea`
- `description`: "Master Test Architect and Quality Advisor. Use when the user asks to talk to Murat or requests the Test Architect."

No `model` or `tools` keys in the frontmatter; the activation contract is prose (Steps 1–8) inside the SKILL body.
