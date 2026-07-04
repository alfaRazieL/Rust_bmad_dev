# D4.0 — Master Implementation Plan Precondition Audit

Recorded before writing `rdx-tea/MASTER_IMPLEMENTATION_PLAN.md`. Every
value re-verified against the current Git HEAD and authoritative files —
not from prior-window memory. D4.0 is a **planning stage**: no production
code, no installer/hook/runtime change, no live pilot, no mass eval.

## 1. Repository identity

| Field | Value |
|---|---|
| Repository | https://github.com/alfaRazieL/Rust_bmad_dev |
| Branch | `rdx-tea-integration` |
| Actual START_HEAD | `1cd5b11b20ba8cea92101d47967665d44cea7e97` |
| Expected START_HEAD | `1cd5b11b20ba8cea92101d47967665d44cea7e97` — **MATCH** |
| `origin/rdx-tea-integration` | `1cd5b11b20ba8cea92101d47967665d44cea7e97` — MATCH (no drift) |
| `origin/main` | `d8140a25f8166bf0ca5ce5fc19f7cb1bd06a3d6d` — MATCH expected |
| Working tree | clean within `rdx-tea/**`; only untracked non-scope item: `.agents/` (session tooling, pre-existing, **not touched**) |

No unexpected commits ahead of the pinned START_HEAD. No reset / force
checkout performed. START_HEAD `1cd5b11` is the D3.4.1 two-commit
identity closure (`rdx-tea: close D3.4.1 two-commit identity`) directly
on top of `4be4d3e` (D3.4.1 evidence) → `135b5ed` (D3.4.1 tested
subject). Chain intact.

Because the only dirty item is the out-of-scope untracked `.agents/`
directory, a separate worktree is unnecessary: D4.0 stages files
explicitly by path under `rdx-tea/**` and never runs `git add -A`, so
`.agents/` is never captured.

## 2. Predecessor final-verification identity (authoritative chain)

Read directly from `rdx-tea/evidence/final/`:

| Stage | tested_subject_sha | evidence_commit_sha | verdict | CI run | pytest |
|---|---|---|---|---|---|
| D3.3.3 | `55451a6e015e3e955e545d1b09c1bfe35d3bfa40` | `33869ac9972c41d45402aecfb7d622cb3734d2b7` | `D3_3_3_PASS` | `28673519915` success | — |
| D3.4.0 | `f145c14bd7d3ec20143cb48ea76b9cab3feddb80` | `fdbbb9ac683527973e6ba4af50382c3fb859106f` | `D3_4_0_PASS` | `28694381995` success | 561/561 |
| D3.4.1 | `135b5ed24c419d8e135698bb3b41dd55b1a0c33d` | `4be4d3e1cff6f0b6ee8bacff11e1ee63c3525c94` | `D3_4_1_PASS` | `28698462520` success | 562/562 |

Upstream source lock (`bootstrap/sources.lock`, unchanged across the
chain):

- RDX `rdx_source_sha` = `d8140a25…` (tag `v1.1.0`; equals `origin/main`).
- BMAD-METHOD `bmad_source_sha` = `3bcd6c3c…` (tag `v6.8.0`).
- BMAD TEA `tea_source_sha` = `8734d51f…` (tag `v1.19.0`).

## 3. Final D3.4.1 verdict (authoritative basis for D4)

From `rdx-tea/evidence/final/D3_4_1_FINAL_VERIFICATION.json` and
`rdx-tea/research/D3_4_1_RULE_OPERATION_PILOT_REPORT.md`:

```
D3_4_1_PASS
RULE_OPERATION_PASS
D3_RULE_OPERATION_PROVEN
READY_FOR_D4_MASTER_IMPLEMENTATION_PLAN
```

Locked 12-run pilot facts (schedule v3 `0b2cd8ee…`, criteria v1
`3288de4f…`, both unchanged):

- candidate pass 9/9; control clean 3/3; total 12/12 SUCCESS admissible.
- retries in graded pilot: 0; finalize-run completion 9/9 (100%).
- Task/subagent dispatch: 0 across all 12 runs.
- observed mode: `OBSERVED_SEQUENTIAL` on all 9 candidates.
- runtime contamination: none; observed model == expected on all 12.
- verifier all-pass: 9/9 candidate; workspace_delta consistency PASS
  12/12; artifact_consistency PASS 12/12; schedule_binding PASS 12/12.
- expected_rule_condition PASS 9/9; forbidden_rule_condition PASS 9/9.
- latent-driven pack activation: `[async]` / `[api, async]` / `[]`
  (docs-only correctly activated **no** pack).
- CI green: 562 unique pass, 0 fail, 0 skip; source-lock PASS.
- Auth: existing CLI OAuth (claude 2.1.191); no API key; no
  `CLAUDE_CODE_OAUTH_TOKEN`; `CLAUDE_CONFIG_DIR` inherited, **not
  overridden**.

**Do not re-run the pilot.** It is authoritative evidence.

## 4. What is proven and must be carried into production

The proven, to-be-productionized chain (ADR-002 sequential active-bundle;
ADR-006 auth-preserving isolation; ADR-007 rule-operation):

```
Rust story/diff/tags
→ RDX rule selection (router replay on canonical rules)
→ active packs (obligation-matrix-filtered per workflow)
→ active-context bundle (deterministic prepare projection)
→ RDX wrapper Skill (non-interactive prepare-run / finalize-run)
→ real BMAD TEA child Skill (bmad-testarch-{test-design,atdd})
→ TEA artifacts
→ workspace delta (declared-file verified)
→ sidecars (one per artefact, bundle-tamper checked)
→ verifier (9 deterministic checks)
→ schema-valid admissible evidence
```

Load-bearing invariants proven and to be preserved verbatim:

1. **Sequential-only execution** (ADR-002 §0). The wrapper asserts
   `tea_execution_mode == "sequential"` and fails closed otherwise.
   Subagent/agent-team propagation is a *future* concern (`G6F`), not
   part of the proven path.
2. **Auth-preserving isolation** (ADR-006). Never override
   `CLAUDE_CONFIG_DIR`; isolate the project surface only
   (`.claude/settings.json` + `--setting-sources project` +
   `--strict-mcp-config --mcp-config <empty>` +
   `--disallowedTools Task TaskOutput TaskStop`); no API key / OAuth
   token / `setup-token` / `apiKeyHelper`.
3. **Deterministic projection** (guardrails). No wallclock, no random,
   sorted iteration, byte-identical bundle bytes, canonical snapshot
   hash pinned.
4. **Fail-closed admission** (ADR-006 §6/§8). Admissibility is recomputed
   from primitive fields; a dishonest bundle cannot self-admit; a failed
   run can never be a FINALIZED-admissible bundle.
5. **One sidecar per artefact** (D3.4.0 §2). Output roots are collapsed
   to canonical ancestors; artefacts deduped by resolved real path.
6. **Forbidden packs judged by ACTIVE packs, not prose** (ADR-007). A
   bundle may legitimately cross-reference other packs' rules.
7. **Workspace delta preserved AND verified** (ADR-007). A declared
   generated file that does not exist (and is not precommitted as
   `declarationPlannedNotGenerated`) is inadmissible.
8. **Strict git identity + source lock** (D3.1 §8/§10). Both base/head
   SHAs verified with `git cat-file -e`; no zero-SHA fallback; upstream
   tags/SHAs/file-hashes locked.

## 5. What is explicitly NOT claimed (do not overclaim in D4)

- **G7 behavioural benefit vs baseline is NOT claimed** and is out of
  scope. D3 proved rule-operation *correctness/stability*, not that RDX
  produces "better" artefacts than bare TEA (ADR-007 §2, D3.4.1 gate G7
  = `OUT_OF_SCOPE_NOT_CLAIMED`).
- The baseline/control arm is an **isolation control only**; it does not
  demonstrate full child-artefact production (see §6 caveat 1).
- **Subagent / agent-team worker propagation is NOT proven live.** The
  proven path is sequential; the subagent-seed contract (ADR-001 §7) was
  superseded by ADR-002 and remains a future `G6F` item.
- The production **enforcement verdict** (`rdx-tea-validate` inside
  `rdx-validator/rdx_tea/`) is **not yet built**; the install-tree ships
  a self-contained *behavioural* verifier stub, not the enforcement
  plane (D3.1 "What D3.1 does NOT close"; STAGE-08).
- **Modes / hooks / CI-gate / judgment / Cat-4 approval** (ADR-001 §9–15,
  STAGE-09) are not implemented and remain enforcement-plane backlog.

## 6. Non-blocking caveats carried from D3.4.1 (must survive into D4)

From `rdx-tea/research/D3_4_1_BLOCKERS.md` (all "Open / non-blocking"):

1. **Baseline artefact production is interaction-gated.** The bare child
   `bmad-testarch-*` workflow is interactive; without the wrapper's
   non-interactive prepare/finalize scaffolding it stops at
   greeting/elicitation and emits 0 artefacts. Acceptable for the
   control's isolation role; **artefacts are not a baseline admission
   requirement.** Production must not make baseline artefact production a
   requirement.
2. **`prompt_hash` is really a prompt *template* hash.** The eval
   schedule field pins `sha256(arm_prompt(arm, wf, "__RUN_ID__"))`, not
   the per-run prompt hash. This is an **eval-harness** concern only;
   consider recording it explicitly as `prompt_template_hash` in a future
   schedule version (changes the schedule SHA — out of scope for D4.0).
3. **LLM diagnostic layer is DRY_RUN_ONLY / optional** and cannot
   override the deterministic verdict. Never promote it to a gate.
4. **Absolute machine paths embedded in evidence bundles** are cosmetic
   (paths only; no secrets). Production evidence should prefer
   project-relative paths where practical.

## 7. Production constraints inferred from the proofs

- Production runtime is **wrapper-driven and non-interactive** by design.
  Bare child TEA workflows are interaction-gated, so the production path
  MUST retain the prepare-run/finalize-run lifecycle to drive the child
  to completion (D3.4.1 §4 honest characterization).
- Production must remain **fail-closed** at every seam: missing manifest,
  bundle tamper, missing artefact, unchanged artefact SHA, non-sequential
  mode, missing identity, symlink/traversal artefact, source-lock drift.
- Production must keep the **`_bmad/rdx-tea/runtime/<workflow>/<run_id>/`**
  run-scoped layout and the structured JSON active-run lock so concurrent
  runs never collide.
- Production must keep **canonical KB as the only projection input** and
  keep the router **vendored/pinned** with parity coverage (no manual
  Router drift; D3.2 §3 / router parity test).
- The **verifier** ships as a behavioural check; the **enforcement
  verdict** stays deferred to `rdx-tea-validate` and must reuse the RDX
  `rdx-evidence.v1` verdict enum and Cat-1..Cat-4 authority matrix
  unchanged (ADR-001 §10/§11).

## 8. Research-only components that must NOT be shipped as runtime

- `rdx-tea/live-harness/**` — the live pilot harness (`run_live.py`
  ~100 KB, `rule_operation.py`, `invoke_runtime.py`,
  `prepare_workspace.py`, `collect_evidence.py`, `ci_check.py`,
  `runtime_discovery.py`, `schemas/live-evidence.v{1..4}.schema.json`,
  `policies/tea-tools-v1.json`, `tests/`).
- `rdx-tea/evals/**` — schedules (`runs/*.json`), criteria/rubrics,
  `run_pilot.py`, `run_rule_operation.py`, `grading/*.py`, `results/`
  (including `_d3_4_1_preserved_failed_attempts/`).
- `rdx-tea/evidence/**` — all historical evidence, final verifications,
  live smokes, hashes, logs.
- `rdx-tea/research/**`, `rdx-tea/architecture/**`,
  `rdx-tea/implementation-plan/**` — documentation/audit trail.

The deterministic detectors in `live-harness/rule_operation.py`
(`collect_workspace_delta`, `check_artifact_consistency`) are eval-side
today; whether to **promote** equivalents into the production finalize/
verifier path is an explicit Wave-5/Wave-6 decision, not a blind copy.

## 9. Known inconsistencies to reconcile during productionization

- **Adapter version drift:** `poc/install-tree/_bmad/rdx-tea/VERSION`
  says `0.3.1` while `bootstrap/sources.lock:adapter_version` says
  `0.3.2`. Reconcile in Wave 1/2 and pin.
- **Two PoC code trees:** `poc/adapter/` (dev-coupled: imports
  `rdx_validator` directly) vs `poc/install-tree/_bmad/rdx-tea/scripts/`
  (self-contained: vendored `router.py`). The install-tree is the
  production candidate; `poc/adapter/` is legacy PoC to be classified
  (keep-as-reference or retire) — **not deleted in D4.0**.
- **Directory naming:** an existing `rdx-tea/implementation-plan/`
  (D3-era proof plan, superseded stages) is distinct from the new
  `rdx-tea/implementation/` created by D4.0. Keep both; do not conflate.

## 10. Initial proposed implementation wave list (knowledge-plane first)

Per `feedback_rdx_tea_knowledge_first` and GLOBAL_GUARDRAILS
("Knowledge-plane-first: do not attempt enforcement while the knowledge
plane isn't proven"), the productionization proceeds:

```
Wave 0  — Plan validation & repository hygiene            (no code)
Wave 1  — Production layout & source boundaries           (move/classify only)
─ knowledge plane ─
Wave 2  — Rule KB & router productionization
Wave 3  — Active-context bundle builder
Wave 4  — TEA wrapper Skills & non-interactive lifecycle
Wave 5  — Binder, sidecars, workspace delta, artifact consistency
─ admission/runtime hardening ─
Wave 6  — Verifier / admission & failure semantics
Wave 7  — Installer / bootstrap & project settings
Wave 8  — CI gates & source-lock
Wave 9  — Documentation & operator workflows
Wave 10 — End-to-end acceptance & release/merge plan
```

Deferred (explicitly OUT of D4 v1 scope; separate future stage): the
enforcement plane — `rdx-tea-validate` verdict (STAGE-08), modes/hooks/
CI-gate/judgment/Cat-4 (STAGE-09), subagent propagation (`G6F`), and G7
behavioural benefit. These are documented as backlog in the master plan,
not scheduled as D4 waves.

## 11. Precondition verdict

```
START_HEAD .............. 1cd5b11 (matches expected)
origin/main ............. d8140a25 (matches expected)
D3.4.1 basis ............ RULE_OPERATION_PASS / D3_RULE_OPERATION_PROVEN
D3.4.1 identity ......... 135b5ed / 4be4d3e / CI 28698462520 success / 562 pass
source lock ............. RDX d8140a25 (v1.1.0) / BMAD 3bcd6c3c (v6.8.0) / TEA 8734d51f (v1.19.0)
proven path ............. sequential wrapper-driven prepare/finalize (ADR-002/006/007)
scope ................... rdx-tea/** (+ future rdx-validator/rdx_tea/**, .github/workflows/rdx-tea-*.yml)
forbidden ............... prod code, installer/hook change, main change, PR/merge, force push, live pilot, mass eval, API key, CLAUDE_CONFIG_DIR override
```

**PRECONDITION_AUDIT: PASS → cleared to author the D4.0 master
implementation plan and supporting wave artifacts.**
