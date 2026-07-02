# CURRENT_RDX_1_1_BASELINE — RDX 1.1 as it exists at `d8140a25…`

**Purpose:** Phase-0 output required by prompt §7. Establish that the shipped
RDX 1.1 test suite is green and enumerate the canonical facts, contracts, and
extension points every later phase must respect.

**Rule imposed by this document (per prompt §7 last paragraph):**
No later phase may plan a TEA extension until the shipped RDX suite has been
demonstrated green on the exact SHA in `SOURCE_LOCK.md §1`. This document
records that demonstration.

---

## 0. Provenance

| Field | Value |
|---|---|
| Working SHA | `d8140a25f8166bf0ca5ce5fc19f7cb1bd06a3d6d` |
| Branch | `rdx-tea-integration` |
| Date/time (UTC) | `2026-07-02T09:20:40Z` (baseline suite end) |
| Python venv | `rdx-tea/.venv-baseline/` (isolated, not committed) |
| Python | `3.14.4` from `/opt/homebrew/bin/python3` |
| pytest | `9.1.1` |
| jsonschema | `4.26.0` |
| PyYAML | `6.0.3` |
| Full evidence | `rdx-tea/evidence/logs/phase0_baseline_pytest.log` |

---

## 1. Baseline test suite result

### 1.1 Command

```
PYTHONPATH implicitly provided by tests/conftest.py (VALIDATOR_DIR = ./rdx-validator)
rdx-tea/.venv-baseline/bin/python -m pytest -v --tb=short --durations=15
```

Executed from repo root `/Users/m33tball/bmad_module_builder/rdx-workspace/Rust_bmad_dev`.
Isolated venv, no editable install of `rdx_validator`.

### 1.2 Aggregate outcome

- Collected: **307 tests** (pytest node count, includes parametrized invocations)
- Passed: **307**
- Failed: **0**
- Errored: **0**
- Skipped: **0**
- Wall-clock duration: **15.09 s**
- Process exit code: **0**

The number `307` matches the figure the RDX 1.1 CHANGELOG advertises and is
counted at the pytest-node level. See §1.5 for the file-vs-node distinction
that prompt §11.2 mandates.

### 1.3 Per-layer distribution

| Layer / directory | Test nodes | Notes |
|---|---:|---|
| `tests/unit/validator/` | 83 | L1 + L2 validator internals + L8 sync-codeowners |
| `tests/bmad/` | 49 | Modes, setup/uninstall, code-review wrappers, menu overrides |
| `tests/evals/` | 46 | L5 behavioral evals, L8 judgment eval cases |
| `tests/docs/` | 35 | L4 doc-honesty & README consistency |
| `tests/mutation/` | 31 | L7 adversarial mutation suite |
| `tests/contracts/` | 22 | L0 static contract tests (drift, router, status, schemas) |
| `tests/acceptance/` | 15 | L8 v6 acceptance + Cat-4 flow |
| `tests/ci/` | 11 | L6 hook + CI workflow |
| `tests/integration/` | 10 | L3 green-crate + L8 Cat-4 |
| `tests/compatibility/` | 5 | Version compat matrix |
| **Total** | **307** | — |

### 1.4 Timing (slowest, from `--durations=15`)

| Duration (s) | Test |
|---:|---|
| 5.62 | `tests/acceptance/test_v6_acceptance.py::test_t_v6_acc_01_v5_regression_pack_passes` |
| 1.15 | `tests/acceptance/test_regression_timing.py::test_l0_l1_l2_regression_under_30s` |
| 0.94 | `tests/acceptance/ha-adversarial-suite/test_v6_acc_05.py::test_t_v6_acc_05_full_mutation_suite_green` |
| 0.86 | `tests/ci/test_l6_hook.py::test_l6_hook_003_chains_existing_hook` |
| 0.42 | `tests/ci/test_l6_hook.py::test_l6_hook_005_no_verify_bypass` |
| 0.37 | `tests/ci/test_l6_hook.py::test_l6_hook_002_permits_clean_push` |
| 0.36 | `tests/ci/test_l6_hook.py::test_l6_hook_001_blocks_push_on_validator_fail` |
| 0.25 | `tests/acceptance/cat4-flow/test_v6_cat4_flow.py::test_t_v6_acc_04_cat4_full_cycle` |
| 0.25 | `tests/ci/test_l6_ci_workflow.py::test_v5_acc_05_ci_matches_local` |
| 0.20 | `tests/ci/test_l6_ci_workflow.py::test_l6_ci_002_validator_loaded_from_base` |

RDX enforces its own release-gate `test_l0_l1_l2_regression_under_30s` at
1.15 s (< 30 s threshold), so the L0/L1/L2 core stays fast.

### 1.5 Test-count discipline (prompt §11.2)

| Kind of count | Value |
|---|---:|
| Discrete Python test files (`test_*.py`) | 51 |
| pytest node count (functions × parametrizations) | 307 |
| Distinct test IDs at logical level | ≤ 51 — many tests carry ≥ 5 parametrized fixtures |

TEA-side test design (Phase 6 output) will keep these counts separate. `307`
alone is **not** evidence of 307 distinct logical scenarios.

---

## 2. Canonical contracts observed at this SHA

The tables below dereference the artefacts under `tests/contracts/`. Their
SHA-256 hashes are pinned in `SOURCE_LOCK.md §5` and
`rdx-tea/evidence/hashes/SOURCE_LOCK_files_sha256.txt`. Any adapter or
projection this task produces MUST re-read these files (not copy them) and
reproduce these facts byte-for-byte.

### 2.1 Status vocabulary (14 verdicts + 3 severities)

Source: `tests/contracts/status-definitions.json` (`rdx_status_version: v1`).

Verdicts — **the canonical spelling is `EVIDENCE_REQUIRED`, not
`EVIDENCE_MISSING`** (prompt §5.1 regression target):

```
PASS
FAIL
NOT_APPLICABLE
NOT_RUN
EVIDENCE_REQUIRED
REVIEW_REQUIRED
APPROVAL_REQUIRED
BASELINE_FAILURE_OBSERVED
BASELINE_BLOCKS_VALIDATION
REGRESSION_FAILURE
REGRESSION_FIXED
ENVIRONMENT_UNAVAILABLE
TOOL_UNAVAILABLE
BLOCKED
```

Severities: `INFO`, `WARNING`, `BLOCKING`.

Blocking behaviour per mode (excerpt):

| Verdict | Blocks in |
|---|---|
| FAIL / REGRESSION_FAILURE | MODE_1..MODE_4 |
| BLOCKED | MODE_1..MODE_4 |
| EVIDENCE_REQUIRED | MODE_2..MODE_4 |
| NOT_RUN | MODE_2..MODE_4 (conditional on `reason_not_on_approved_list`) |
| BASELINE_BLOCKS_VALIDATION | MODE_2..MODE_4 (conditional on `no_override_recorded`) |
| APPROVAL_REQUIRED | MODE_1..MODE_4 |
| REVIEW_REQUIRED | MODE_4 (informational in MODE_3) |
| ENVIRONMENT_UNAVAILABLE | MODE_2..MODE_4 (downgrade path `MODE_0_report_only`) |

Exit-code resolution order:
```
ENVIRONMENT_UNAVAILABLE → 2
FAIL or REGRESSION_FAILURE → 1
BLOCKED or BASELINE_BLOCKS_VALIDATION or APPROVAL_REQUIRED or EVIDENCE_REQUIRED → 3
REVIEW_REQUIRED → 4
otherwise → 0
```

### 2.2 Router (12 conditional packs)

Source: `tests/contracts/router-rules.json` (`rdx_router_version: v1`)  
KB source-of-truth: `.claude/skills/rdx-setup/assets/kb-sections/section-5-router.md`.

| Pack | Confidence | Activation policy | Related rule IDs |
|---|---|---|---:|
| `async` | STRONG | AUTO_ACTIVATE | 9 |
| `unsafe` | STRONG | AUTO_ACTIVATE | 11 |
| `ffi` | STRONG | AUTO_ACTIVATE | 7 |
| `macro` | STRONG | AUTO_ACTIVATE | 4 |
| `api` | MEDIUM | STORY_TAG_REQUIRED | 18 |
| `cargo` | STRONG | AUTO_ACTIVATE | 9 |
| `testing` | MEDIUM | STORY_TAG_REQUIRED | 4 |
| `data-security-io` | MEDIUM | AUTO_SUGGEST | 23 |
| `db` | MEDIUM | AUTO_SUGGEST | 6 |
| `time-config-client` | MEDIUM | AUTO_SUGGEST | 7 |
| `ops` | WEAK | STORY_TAG_REQUIRED | 9 |
| `perf` | WEAK | STORY_TAG_REQUIRED | 8 |
| **Total** | — | — | **115 pack rules** |

Consequences that prompt §5.3 forces the adapter to preserve:

- Every pack carries `positive_signals`, `negative_signals`, `path_signals`,
  `activation_policy`, `confidence_class`, `related_rule_ids`,
  `validation_family`, and `escalation_triggers`. No Router
  reimplementation may hand-write these; a projection generator has to
  parse/compile them out of this JSON.
- `STORY_TAG_REQUIRED` is *the* mechanism used by `api`, `testing`, `ops`,
  and `perf`. Any projection or subagent payload that drops story-tag state
  will silently misroute these four packs.
- Weak signals (`ops`, `perf`) are precisely the ones the prompt §5.3 last
  paragraph called out for special attention — they trigger only under
  `STORY_TAG_REQUIRED`.

### 2.3 Rule authority (rule-check-map + authority-matrix)

Sources: `tests/contracts/rule-check-map.json`,
`tests/contracts/authority-matrix.json`.

`rule-check-map.json` covers **37 rules** — the deterministic + evaluator-
governed subset used by the shipped 1.1 validator:

| Prefix | Count |
|---|---:|
| `CORE-` | 18 (CORE-001..018) |
| `RP-` | 14 (a scoped subset of the 115 pack rules — the ones the validator has hard-coded checks or authority mappings for) |
| `GOV-` | 5 |

Category distribution across the same 37 rules:
- Category 1 (deterministic): 5
- Category 2 (evidence verification): 4
- Category 3 (judgment): 22
- Category 4 (specialist approval): 6

Authority distribution:
- Evaluator: 22
- Validator: 9
- Specialist: 6

Authority matrix actors:
`LLM`, `Validator`, `Evaluator`, `Specialist`, `CI` with levels
`WRITE / READ / VERIFY / FORBIDDEN`. Cat-1 verdict is `FORBIDDEN` for the LLM
and the Evaluator; `WRITE` only for the Validator (this is the invariant
prompt §5.7 flags as the "self-attested Cat-1 PASS" adversarial target).

The gap between `router-rules.json` (115 pack rules) and `rule-check-map.json`
(14 `RP-*` entries) is intentional and load-bearing: the Router recognises
many rules the shipped validator does not yet program. Any TEA adapter that
"projects" all 115 rules into TEA must reconcile this or it will overstate
enforceable coverage.

### 2.4 Evidence envelope schema (`rdx-evidence.v1`)

Source: `tests/contracts/schemas/rdx-evidence.v1.schema.json` (334 lines).
The schema is enforced by the validator on every emission — this is where the
"schema rejects LLM-set Cat-1 PASS" invariant referenced in the CHANGELOG
lives. Any TEA-side artefact emitter that wants to appear in the same
verdict trail must produce schema-conformant envelopes.

### 2.5 Judgment finding schema (`rdx-judgment-finding.v1`)

Source: `tests/contracts/schemas/rdx-judgment-finding.v1.schema.json`
(102 lines). Emitted by `rdx-judgment` (Cat-3). Cannot upgrade a Cat-1
verdict to PASS (schema-level constraint).

### 2.6 Modes

Source-of-truth file: `.claude/skills/rdx-setup/assets/modes.md`.
Modes are `MODE_0 Advisory`, `MODE_1 Local Validated`, `MODE_2 Local Gated`,
`MODE_3 CI Enforced`, `MODE_4 Specialist Approval`. Every emitted evidence
envelope is stamped with the mode label; downstream reviewers can therefore
tell "what gate produced the verdict" without re-running the validator.

Mode 2 is documented as release-quality (not a stepping stone to Mode 3) in
the README, and there is a dedicated test
`tests/docs/test_l4_readme_mode2_positioning.py` guarding that positioning.

---

## 3. Extension points already installed in RDX 1.1

These are the mechanisms the shipped code actually uses. Phase 1 will
reverse-engineer which of them are *official* BMAD extension points and which
are RDX-local. This section only records what is used *right now*.

### 3.1 Agent overrides

Location: `.claude/skills/rdx-setup/assets/agent-overrides/`

| File | Target agent | Purpose |
|---|---|---|
| `bmad-agent-dev.toml` | Amelia (Developer) | Loads 18 Always-on Core rules + Risk Router before every story |
| `bmad-agent-architect.toml` | Winston (Architect) | Loads CORE-001/005/006 + Governance |
| `bmad-agent-pm.toml` | John (PM) | Loads Governance, enforces contract-before-code |

The installer writes these into `_bmad/custom/bmad-agent-*.toml` (per
CHANGELOG "1.0 Added" section) using the BMAD "team-override mechanism".
Phase 1 must confirm the exact merge semantics BMAD uses here.

### 3.2 Workflow override (single example)

Location: `.claude/skills/rdx-setup/assets/workflow-overrides/bmad-code-review.toml`

This is the file that lets `rdx-code-review` wrap the upstream
`bmad-code-review` workflow. It is a first concrete precedent for
workflow-level override — this is the pattern the TEA adapter will need to
generalise for `bmad-tea` workflows.

### 3.3 Skill wrappers

`.claude/skills/rdx-setup/`, `.claude/skills/rdx-dev-story/`,
`.claude/skills/rdx-code-review/`, `.claude/skills/rdx-judgment/`,
`.claude/skills/rdx-hooks/`. Every skill has a `SKILL.md` plus assets and
scripts. Skills are discovered through `.claude/skills/.claude-plugin/marketplace.json`.

### 3.4 Installer / uninstaller / merge

`.claude/skills/rdx-setup/scripts/install.py`,
`.claude/skills/rdx-setup/scripts/uninstall.py`,
`.claude/skills/rdx-setup/scripts/merge-config.py`,
`.claude/skills/rdx-setup/scripts/merge-help-csv.py`,
`.claude/skills/rdx-setup/scripts/sync_codeowners.py`.

The presence of `merge-config.py` (separate from `install.py`) is important:
prompt §5.5 warns against "duplicate `[agent]` section" bugs. Phase 4 must
exercise this merger on adversarial fixtures.

### 3.5 Validator package

`rdx-validator/rdx_validator/` (BMAD-independent Python package).

Public modules observed: `baseline.py`, `diff.py`, `router.py`, `status.py`,
`policy.py`, `approvers.py`, `preflight.py`, `judgment.py`, `exceptions.py`,
`cli.py`, `__main__.py`, plus `checks/core_00{7,8}.py`,
`checks/core_01{1,4,5}.py`, and an `evals/` submodule.

CLI verified during Phase 0 by running `python -m rdx_validator --help` with
`PYTHONPATH=./rdx-validator`. It accepts, inter alia,
`--project-root`, `--story`, `--base`, `--head`, `--diff-file`, `--mode`,
`--policy-config`, `--evidence-in`, `--evidence-out`, `--dual-run`,
`--baseline-data`, `--validator-source`, `--contracts-dir`,
`--max-diff-bytes` (default 10 MiB — DoS guard), `--quiet`.

`--validator-source` and `--contracts-dir` are the flags a TEA-side wrapper
would use to pin trusted code + trusted contracts — Phase 1 must confirm
whether they satisfy the "target-branch validator" pattern the CI workflow
uses.

### 3.6 Hooks

`.claude/skills/rdx-hooks/scripts/install-hook.py`,
`uninstall-hook.py`, `assets/pre-push.sh`. Documented `--no-verify` bypass is
tested at `tests/ci/test_l6_hook.py::test_l6_hook_005_no_verify_bypass`.

### 3.7 CI workflows

`.github/workflows/`:

| File | Purpose |
|---|---|
| `rdx-gate.yml` | Required-check that loads validator from base branch (trust boundary; Mode 3) |
| `rdx-full-regression.yml` | Full pytest matrix |
| `rdx-l0-contracts.yml` | L0 contract drift |
| `rdx-l1-l3-validator.yml` | L1..L3 validator layers |
| `rdx-l4-bmad-integration.yml` | L4 BMAD integration |
| `rdx-l4-modes.yml` | L4 mode behaviour |
| `rdx-l4-l8-judgment.yml` | L4/L8 judgment (Cat-3) |
| `rdx-l6-l7.yml` | L6/L7 hook + mutation |
| `rdx-l8-cat4.yml` | L8 Cat-4 specialist approvals |
| `rdx-compat-matrix.yml` | Compatibility matrix |
| `rdx-docs.yml` | Doc-honesty tests |
| `.github/scripts/rdx-ci-runner.py` | The shim CI actually invokes |

### 3.8 Cat-4 approver plumbing

`_bmad/rdx/approvers.schema.json`, `_bmad/rdx/approvers.yaml.example`,
`_bmad/rdx/approval.v1.schema.json`, and `sync_codeowners.py` (renders
`.github/CODEOWNERS` from the canonical `approvers.yaml`).

---

## 4. Extension points RDX 1.1 does **NOT** currently use

Things prompt §8 says a TEA adapter might need, that we did **not** find in
this SHA (Phase 1 will confirm each in official BMAD / TEA source):

- `persistent_facts` — no occurrences in the RDX tree at this SHA.
- Activation-prepend/append hooks other than the KB-load convention embedded
  in `bmad-agent-*.toml` overrides.
- `on_complete` hooks — not exercised by any RDX skill in this SHA.
- Skill-level workflow-local resources beyond the `assets/` convention.
- A "knowledge index" or "workflow-local resource" registry — nothing under
  `.claude/skills/*/assets/` looks like the TEA `tea-index.csv` prompt §4.4
  refers to. The TEA-side registry (if it exists) is **outside** this repo.
- Any TOML-AST-aware merger — `merge-config.py` is the local answer; whether
  BMAD ships an official parser-based merger is Phase 1 work.

Recording these gaps here is what lets Phase 3 tell "we need to build X"
apart from "BMAD already ships X and we should use it".

---

## 5. Existing RDX extension points reusable by the TEA adapter

Ranked from lowest-risk (already exercised by the shipped test suite) to
highest-risk (requires new plumbing).

| # | Point | Reuse case for TEA adapter | Risk |
|---|---|---|---|
| 1 | Canonical JSON contracts under `tests/contracts/` | Read Router + status + rule-check-map + schemas directly as the projection generator's *only* input. | LOW — schemas already versioned, drift-checked. |
| 2 | `rdx-evidence.v1` schema | TEA artefact envelopes conform to (a superset of) this schema so the same validator can consume them. | LOW — schema is a contract, TEA can add its own required fields via `oneOf`/`allOf`. |
| 3 | Agent override files (`bmad-agent-{dev,architect,pm}.toml`) | Precedent for the shape of a `bmad-tea.toml` override. | MED — merge semantics need Phase 1 confirmation. |
| 4 | Workflow override precedent (`bmad-code-review.toml`) | Blueprint for per-workflow TEA overrides. | MED — only one exemplar exists so far. |
| 5 | Skill-wrapper pattern (`rdx-dev-story` around `bmad-dev-story`) | Blueprint for a `rdx-tea-*` skill that wraps a TEA workflow entry point. | MED — depends on whether TEA workflows are wrappable at all. |
| 6 | `merge-config.py` + `sync_codeowners.py` | Baseline installer plumbing to extend for TEA overlays. | MED — must add AST-aware merging (§5.5). |
| 7 | `--validator-source` + `--contracts-dir` CLI flags | Trust-boundary hooks for CI: TEA gate can load validator + contracts from target branch. | LOW — flags already tested. |
| 8 | CI workflow shape (`rdx-gate.yml`, `.github/scripts/rdx-ci-runner.py`) | Precedent for a `rdx-tea-gate.yml` that composes atop TEA outputs. | MED — depends on TEA CI convention. |
| 9 | pytest-node-level parametrized fixtures (`tests/unit/validator/test_l2_router_packs.py`) | Reuse `tests/fixtures/diffs/**` fixture layout for Router replay tests. | LOW — already scales to 35+ Router cases at ~2 ms each. |

Everything else needs new construction under `rdx-tea/`.

---

## 6. Baseline validation of §5 regression targets

Prompt §5.1..§5.9 lists nine ways the previous "Variant D" PoC was wrong.
Baseline observations relevant to each:

| §5 topic | Canonical fact from this SHA | Direct consequence for adapter design |
|---|---|---|
| 5.1 Status drift | 14 verdicts, spelling `EVIDENCE_REQUIRED` | Projection must import the full JSON, not paraphrase it. |
| 5.2 Rule-ID scheme | Canonical prefixes are `CORE-*` (18), `RP-*` (115 pack rules of which 14 are in rule-check-map), `GOV-*` (5). No `RUST-*` prefix. | Any projection that renames an ID emits a drift-detectable artefact. |
| 5.3 Router hand-copy | `router-rules.json` carries `positive_signals`, `negative_signals`, `path_signals`, `activation_policy`, `confidence_class`, `related_rule_ids`, `validation_family`, `escalation_triggers` for all 12 packs; `STORY_TAG_REQUIRED` policies are non-trivial. | Adapter must compile the router from the canonical JSON. |
| 5.4 No real generator | Nothing under this SHA generates TEA-side projections. | Confirmed missing feature; Phase 3 must design one. |
| 5.5 TOML merger | `merge-config.py` exists, but the current bmad-agent overrides are shipped whole. AST awareness not proven. | Phase 4 must fuzz `merge-config.py` on `existing [agent]`, arrays, comments, nested tables. |
| 5.6 Agent-only integration | The shipped RDX 1.1 wires knowledge in via `agent.toml` + `SKILL.md` bodies; no workflow-step-level fragment loader exists. | Adapter must add workflow-level (or step-level) loading of TEA fragments. |
| 5.7 Mode tests | `tests/bmad/modes/test_mode_selector.py`, `test_mode_naming.py`, plus `tests/ci/test_l6_hook.py` and `tests/ci/test_l6_ci_workflow.py` do run mode-parameterised assertions with different expected outcomes. | Existing modes suite is a reusable adversarial target. |
| 5.8 Real TEA runs missing | No TEA integration is exercised in the shipped tests. | Confirmed — must build in Phase 4. |
| 5.9 Fake candidate scores | Baseline suite has no unmeasured "score" comparisons; only booleans and JSON diffs. | Behavioral evals must follow the same pattern. |

---

## 7. Exit — Phase-0 hand-off contract

Downstream phases inherit these facts:

- The suite is **green** at `d8140a25…` and this document is the proof.
- Any regression in the shipped `pytest` result during later phases is a
  Phase-0 violation and stops the task (prompt §24 "existing RDX regression
  падает").
- Canonical hashes in `SOURCE_LOCK.md §5` are the authoritative pin.
- Contracts to consume as the projection input: `tests/contracts/router-rules.json`,
  `status-definitions.json`, `rule-check-map.json`, `authority-matrix.json`,
  `schemas/rdx-evidence.v1.schema.json`,
  `schemas/rdx-judgment-finding.v1.schema.json`, and the four KB sections
  under `.claude/skills/rdx-setup/assets/kb-sections/`.
- Extension-point candidates to keep in Phase 1 focus: agent-override
  precedent, workflow-override precedent, skill-wrapper precedent,
  `merge-config.py`, `rdx-ci-runner.py`, evidence schema, `--validator-source`.
- Extension gaps to close before enforcement work begins (per
  knowledge-plane-first memo): projection generator, workflow-step-level
  loader, worker payload propagation into subagents/agent-teams, TEA artefact
  emission conforming to `rdx-evidence.v1` (or a schema-extended variant).

Phase 1 (`BMAD_CORE_EXTENSION_SURFACE.md`) will now check every one of the
above against actual BMAD / Builder / TEA source and mark each as
`OFFICIAL`, `RDX_LOCAL_ONLY`, or `NEEDS_NEW_BUILD`.
