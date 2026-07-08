# Wave Prompt Pack — RDX ↔ TEA Production Implementation

Copy-ready prompts for future CLI agents. Each is **self-contained for a
fresh context window**: it re-establishes identity, references the master
plan, restates the non-negotiable rules, and ends with the required
response format. Run exactly one wave per context.

**Before running any wave prompt, confirm the repo:**
`.../rdx-workspace/Rust_bmad_dev`, branch `rdx-tea-integration`.

---

## Shared preamble (every wave inlines this)

```
You are executing ONE wave of RDX↔BMAD TEA production implementation in a
fresh CLI context. Do not rely on prior chat memory.

Repo:   rdx-workspace/Rust_bmad_dev
Branch: rdx-tea-integration   (NEVER touch main)
Basis:  D3_RULE_OPERATION_PROVEN (D3.4.1). This is productionization of a
        PROVEN sequential wrapper-driven RDX→TEA lifecycle, NOT a new
        experiment and NOT a "better than TEA" benchmark (G7 is out of
        scope, not claimed).

Read FIRST (authoritative, do not skip):
  - rdx-tea/MASTER_IMPLEMENTATION_PLAN.md   (esp. §6.3, §6.6 your wave, §6.11)
  - rdx-tea/implementation/ACCEPTANCE_GATES.md  (your wave's gates + cross-cutting)
  - rdx-tea/implementation/PRODUCTION_EVAL_SPLIT.md
  - rdx-tea/research/D4_0_MASTER_PLAN_PRECONDITION_AUDIT.md

Non-negotiable rules (all waves):
  - Only change: rdx-tea/**, rdx-validator/rdx_tea/** (enforcement plane
    only; deferred), .github/workflows/rdx-tea-*.yml.
  - NEVER: touch main, open a PR, merge, force push, git reset --hard,
    git add -A (stage by explicit path; never capture .agents/).
  - AUTH: never set/override CLAUDE_CONFIG_DIR; never use ANTHROPIC_API_KEY,
    CLAUDE_CODE_OAUTH_TOKEN, setup-token, or apiKeyHelper. Inherit the
    existing OAuth session unchanged.
  - Determinism: no wallclock/random in generators; sorted iteration;
    re-pin golden hashes in rdx-tea/evidence/hashes/ on any generator change.
  - Test-first (RED→GREEN); save command/cwd/env/SHA/exit/stdout/stderr/
    hashes under rdx-tea/evidence/.
  - Production runtime must NOT import live-harness/* or evals/* or
    reference any evidence/ or evals/ path (G-SPLIT-IMPORT).
  - Do NOT re-run the 12-run pilot or any mass eval. Cite D3.4.1 evidence.
  - No live Claude model calls unless this wave explicitly authorizes ONE
    bounded smoke.

First action: `git fetch origin --prune; git rev-parse HEAD;
git branch --show-current; git status --porcelain` and confirm HEAD is
the previous wave's FINAL_HEAD / owner-authoritative handoff SHA (Wave 0
starts from the D4.0 plan final head 8b4ba3a…; `1cd5b11…` is the historical
pre-plan / D3.4.1 proof baseline, never a wave execution start).

Final response format (end of wave):
  WAVE: <id>
  BRANCH / START_HEAD / FINAL_HEAD
  GATES: <gate-id: PASS/FAIL ...>   (from ACCEPTANCE_GATES.md)
  TESTS_RUN: <commands + counts>
  FILES_CREATED / FILES_MODIFIED
  COMMITS: <sha + message ...>
  STOP_CONDITIONS_HIT: <none | ...>
  NEXT_WAVE_HANDOFF: <notes + FINAL_HEAD for the next wave>
```

---

## WAVE_0_PROMPT — Plan validation & repository hygiene

```
[Inline the shared preamble.]

WAVE 0 GOAL: Validate this plan against the repo. Produce NO production
code. Confirm HEAD == 8b4ba3a53971f97b40cd997a77f019cf075c8ea8 (D4.0 plan
final head; `1cd5b11…` is the historical pre-plan / D3.4.1 proof baseline,
not the execution start) and branch == rdx-tea-integration. Confirm the
working tree is clean within rdx-tea/**
(only .agents/ untracked is acceptable). Reconcile
implementation/PRODUCTION_EVAL_SPLIT.md against `find rdx-tea -maxdepth 2`.

TASKS:
  1. Run the D4.0 artifact-presence check (prompt §10) — all five
     implementation artifacts + master plan present, each >500 chars.
  2. Run: pytest rdx-tea/live-harness/tests/test_harness_v4.py -q
  3. Verify PRODUCTION_EVAL_SPLIT classification matches disk; note drift.
  4. Update implementation/WAVE_INDEX.md status cell for W0.

DO NOT TOUCH: any file under poc/install-tree, live-harness, evals.
GATES: G-W0-HEAD, G-W0-SPLIT, G-W0-TESTS, G-SCOPE.
STOP IF: HEAD ≠ expected; split classification wrong.
COMMIT (≤1): "rdx-tea: validate D4 plan and wave index".
```

---

## WAVE_1_PROMPT — Production layout & source boundaries

```
[Inline the shared preamble.]

WAVE 1 GOAL: Make the production/eval boundary explicit and enforceable
WITHOUT changing runtime behaviour. Reconcile the adapter version drift.

READ ALSO: rdx-tea/research/D3_1_PRODUCTION_LAYOUT_AUDIT.md;
poc/install-tree/**; poc/adapter/**.

TASKS:
  1. Pin VERSION == sources.lock:adapter_version (currently 0.3.1 vs 0.3.2).
  2. Add a boundary/import test (rdx-tea/tests/…): fail if any file under
     poc/install-tree imports live-harness/evals or references an
     evidence/ or evals/ path.
  3. Classify poc/adapter/ as keep-reference or retire-later (document in a
     README; DO NOT delete).
  4. (Recommended) add a top-level pointer/README to the install-tree
     instead of moving it. Do NOT physically move the install-tree in v1.

DO NOT: change any generator logic; alter bundle output. If any golden
bundle hash changes, you changed behaviour — revert.
GATES: G-W1-VERSION, G-W1-BOUNDARY, G-W1-NOBEHAVIOUR, G-SPLIT-IMPORT,
G-DET, G-SCOPE.
STOP IF: golden bundle hash changes; a move breaks CI paths.
COMMIT: "rdx-tea: reconcile adapter version and pin production/eval boundary".
```

---

## WAVE_2_PROMPT — Rule KB & router productionization  (knowledge plane)

```
[Inline the shared preamble.]

WAVE 2 GOAL: Harden the KB + router. Deterministic pack activation from
tags/diff; forbidden packs judged by ACTIVE packs (never prose);
canonical snapshot hash pinned; NO router logic fork.

READ ALSO: poc/install-tree/_bmad/rdx-tea/canonical/router-rules.json;
scripts/router.py; scripts/diff.py;
evals/D3_4_RULE_OPERATION_CRITERIA.v1.yaml; architecture/ADR-002 §3-4.

TASKS:
  1. Confirm router parity: (router ∩ obligation-matrix) == prepare's
     emitted packs, EXACT set equality on all fixtures. No subset slack.
  2. Keep the over-broad `**/*.rs` guard (must not activate every pack).
  3. Confirm docs-only diff activates [] (forbidden RP- prefix respected).
  4. Extend the per-pack × per-fixture activation matrix to cover criteria
     v1: [async], [api, async], [] .
  5. Pin canonical snapshot hash in evidence/hashes/.

Any canonical/ change REQUIRES a source-lock re-pin + a SOURCE_LOCK addendum.
GATES: G-W2-PARITY, G-W2-FORBIDDEN, G-W2-CANON, G-DET, G-SCOPE.
STOP IF: router forks from RDX; forbidden judged from prose; canonical hash
changes without an addendum.
COMMIT: "rdx-tea: harden rule KB and router pack activation".
```

---

## WAVE_3_PROMPT — Active-context bundle builder  (knowledge plane)

```
[Inline the shared preamble.]

WAVE 3 GOAL: Productionize bundle generation — byte-determinism, identity
fail-closed, schema-valid manifest, obligation-matrix field filtering,
rust-scope, source-lock stamping, golden bundle hashes.

READ ALSO: scripts/prepare.py; scripts/obligation_matrix.py;
scripts/rdx_parser.py; architecture/WORKFLOW_OBLIGATION_MATRIX.csv;
canonical/rdx-tea-run.v1.schema.json.

TASKS:
  1. Enforce byte-determinism: no wallclock/random; sorted iteration;
     identical bundle bytes across two processes.
  2. Identity fail-closed: mandatory base/head/rdx/tea SHAs; reject
     all-zero; diff_digest must agree or prepare refuses.
  3. Docs-only diff → EMPTY bundle even for "all"-CORE workflows.
  4. Field filtering per fields_allowed(workflow).
  5. Pin golden bundle hashes per scenario in evidence/hashes/.

Decide + document which rdx-tea-run.v1.schema.json copy is authoritative
(canonical/ is the shipped one; architecture/ is a mirror).
GATES: G-W3-DETERMINISM, G-W3-IDENTITY, G-W3-SCHEMA, G-DET, G-SCOPE.
STOP IF: bundle bytes vary; identity accepted when missing/zero; schema
regression.
COMMIT: "rdx-tea: productionize active-context bundle builder".
```

---

## WAVE_4_PROMPT — Wrapper Skills & non-interactive lifecycle  (knowledge plane)

```
[Inline the shared preamble.]

WAVE 4 GOAL: Productionize the wrapper Skills + prepare-run/finalize-run.
Sequential-only, fail-closed. Exact child invocation (never simulate).
No Task/subagent dispatch. Overlay generate/backup/restore. Active-run lock.

READ ALSO: scripts/rdx_tea_wrapper.py;
.claude/skills/rdx-tea-test-design/SKILL.md;
.claude/skills/rdx-tea-atdd/SKILL.md; architecture/ADR-002, ADR-006.

TASKS:
  1. Confirm invocation-contract handshake (run_id verbatim; candidate-only;
     _bmad-run/rdx-tea-invocation.json).
  2. Sequential-mode fail-closed (tea_execution_mode must be literal
     "sequential").
  3. Overlay: back up any pre-existing _bmad/custom/bmad-testarch-*.toml;
     restore/remove on finalize.
  4. Active-run lock acquire/release (structured JSON).
  5. Empty-delta fail-closed (no new artefact → error).
  6. Production paths must NEVER accept --simulate-child /
     --test-write-fake-artefact (keep env-gated: RDX_TEA_ALLOW_TEST_ARTEFACT
     / RDX_TEA_ALLOW_FIXTURE_DIFF — tests only).
  7. Document the invoke with --disallowedTools Task TaskOutput TaskStop
     (Task dispatch must be 0).

Tests use the env-gated fake-artefact path (deterministic, NO live model).
GATES: G-W4-LIFECYCLE, G-W4-SEQUENTIAL, G-W4-NOTASK, G-AUTH, G-SCOPE.
STOP IF: wrapper simulates the child in production; Task dispatch appears;
non-sequential admitted; overlay not restored.
COMMIT: "rdx-tea: productionize wrapper Skills and non-interactive lifecycle".
```

---

## WAVE_5_PROMPT — Binder, sidecars, workspace delta, artifact consistency  (knowledge plane)

```
[Inline the shared preamble.]

WAVE 5 GOAL: Productionize sidecars (one per artefact), workspace delta,
declared-file checks, and artifact-consistency detectors in the PRODUCTION
finalize path (re-implement; do NOT import the eval module).

READ ALSO: scripts/binder.py; wrapper _delta_outputs /
_canonical_output_roots; live-harness/rule_operation.py (REFERENCE ONLY —
collect_workspace_delta, check_artifact_consistency); architecture/ADR-007.

TASKS:
  1. One-sidecar-per-artefact via canonical output roots (collapse nested
     roots; dedupe by resolved real path).
  2. Bundle-tamper fail-closed (binder recomputes sha256(active-context.md)
     vs manifest.bundle_sha256).
  3. Artefact boundary: reject symlink / path-traversal / outside project.
  4. PROMOTE declared-file validation + artifact-consistency into a NEW
     production module (e.g. scripts/workspace_delta.py). Duplicate
     frontmatter = warning; phantom claim / declared-but-missing file =
     fail-closed. Judge against reality (the delta).

GATES: G-W5-SIDECAR, G-W5-DELTA, G-W5-CONSISTENCY, G-SPLIT-IMPORT, G-SCOPE.
STOP IF: duplicate sidecars regress; production imports live-harness;
phantom claims pass.
COMMIT: "rdx-tea: productionize sidecars, workspace delta and artifact consistency".
```

---

## WAVE_6_PROMPT — Verifier / admission & failure semantics

```
[Inline the shared preamble.]

WAVE 6 GOAL: Productionize the behavioural verifier + fail-closed admission
model, run outcomes, cleanup, retry policy. DO NOT build the deferred
rdx-tea-validate enforcement verdict (that is STAGE-08 backlog).

READ ALSO: scripts/rdx_tea_validator.py; architecture/ADR-006 §5-9;
live-harness/schemas/live-evidence.v4.schema.json (REFERENCE ONLY).

TASKS:
  1. Confirm the 9 verifier checks each fail-close when their hashed input
     is mutated (schema, manifest_hash, bundle_hash, artifact_hash,
     base_head_exist, diff_digest_recomputed, canonical_snapshot,
     source_lock, artifact_boundary).
  2. Admission recomputed from primitive fields — never trust a recorded
     admissible flag; a dishonest bundle cannot self-admit.
  3. Run outcomes in fixed order (AUTH→…→SUCCESS); a failed/partial run is
     never FINALIZED-admissible.
  4. Document cleanup + a bounded retry policy for INFRA/RUNTIME ONLY;
     never convert a rule-operation/verifier failure into an infra retry;
     never overwrite a preserved failed attempt.

GATES: G-W6-VERIFIER, G-W6-ADMISSION, G-W6-FAILCLOSED, G-SCOPE.
STOP IF: a check can be bypassed; a failed run becomes admissible; admission
trusts a self-reported flag.
COMMIT: "rdx-tea: productionize verifier and fail-closed admission".
```

---

## WAVE_7_PROMPT — Installer / bootstrap & project settings

```
[Inline the shared preamble.]

WAVE 7 GOAL: Productionize the install flow. Idempotent project installer
that writes the shipped surface (see PRODUCTION_EVAL_SPLIT §2). NO auth
material copied. NO CLAUDE_CONFIG_DIR override. Project-surface isolation.

READ ALSO: bootstrap/bootstrap.py; bootstrap/sources.lock;
architecture/ADR-006 §1-3; architecture/ADR-001 §14;
live-harness/prepare_workspace.py (REFERENCE ONLY — arm-specific skill
install + project settings pattern).

TASKS:
  1. Build installer/ (project install/update/uninstall) writing:
     _bmad/rdx-tea/{canonical,scripts,bootstrap/sources.lock,VERSION},
     .claude/skills/rdx-tea-*/SKILL.md,
     .claude/settings.json (disableBundledSkills, disableClaudeAiConnectors,
       autoMemoryEnabled:false),
     and the _bmad/custom/*.toml overlay writer.
  2. Update refuses to overwrite *.user.toml. Uninstall removes adapter
     files but KEEPS user content.
  3. Assert NO credential/token/config-dir env is ever written or read.
  4. Version-range refusal against _bmad/tea/config.yaml.

GATES: G-W7-INSTALL, G-W7-NOAUTH, G-W7-IDEMPOTENT, G-AUTH, G-SCOPE.
STOP IF: installer copies auth material; overrides CLAUDE_CONFIG_DIR;
clobbers user config.
COMMITS: "rdx-tea: add project installer and settings template";
"rdx-tea: installer lifecycle and idempotency tests".
```

---

## WAVE_8_PROMPT — CI gates & source-lock

```
[Inline the shared preamble.]

WAVE 8 GOAL: Production CI — guard-not-main, upstream bootstrap,
--verify-only source-lock, canonical + live-harness pytest,
refuse-mandatory-skips, unique-count, scope guard, and a NEW
production/eval boundary check + golden-hash verification.

READ ALSO: .github/workflows/rdx-tea-integration-check.yml;
live-harness/ci_check.py; research/D3_1_PRODUCTION_LAYOUT_AUDIT.md §10.

TASKS:
  1. Keep guard-not-main + no-main-modifications (scope) jobs.
  2. Add a boundary job: grep the shipped surface for
     `import live_harness|import evals|live-harness/|evals/|evidence/` →
     fail on any hit (G-SPLIT-IMPORT).
  3. Add golden-hash verification of bundle + canonical snapshots.
  4. Keep --verify-only source-lock, refuse-mandatory-skips, unique-count.

GATES: G-W8-CI, G-W8-SOURCELOCK, G-W8-NOSKIP, G-SPLIT-IMPORT, G-SCOPE.
STOP IF: CI can run on main; skips masked; scope escape allowed; boundary
check missing.
COMMIT: "rdx-tea: add CI boundary and golden-hash gates".
```

---

## WAVE_9_PROMPT — Documentation & operator workflows

```
[Inline the shared preamble.]

WAVE 9 GOAL: Operator docs under rdx-tea/docs/. Install, run RDX-TEA
workflows, inspect evidence, troubleshoot. A doc-lint forbids eval/test-only
flags in operator docs.

READ ALSO: the two SKILL.md; the Wave 7 installer; the wrapper CLI surface;
MASTER_IMPLEMENTATION_PLAN.md §6.3.

TASKS:
  1. Install guide (installer usage; project-surface isolation; auth is
     preserved, no API key).
  2. Run guide (invoke the wrapper Skill; sequential requirement;
     prepare→child→finalize; run-report).
  3. Evidence-inspection guide (run-report.json, sidecars, verifier checks).
  4. Troubleshooting (auth preserved; mode not sequential; empty delta;
     lock held).
  5. Doc-lint: grep docs for simulate-child / test-write-fake-artefact /
     allow-fixture-diff → must be zero.

GATES: G-W9-DOCS, G-W9-NOEVALFLAGS, G-SCOPE.
STOP IF: docs present eval/test-only flags as operator steps.
COMMIT: "rdx-tea: operator documentation and troubleshooting".
```

---

## WAVE_10_PROMPT — End-to-end acceptance & release/merge plan

```
[Inline the shared preamble.]

WAVE 10 GOAL: Clean-install E2E, real-project fixture test, rollback,
release checklist, and a PROPOSED (not executed) merge-to-main strategy.

READ ALSO: the Wave 7 installer; the Wave 8 CI; fixtures/rust-projects/**;
implementation/ACCEPTANCE_GATES.md;
implementation-plan/FINAL_ACCEPTANCE_CHECKLIST.md.

TASKS:
  1. Clean install into a disposable project + ONE bounded non-interactive
     smoke (a single authorized run — NOT the 12-run pilot, NOT a mass
     eval). Preserve evidence honestly.
  2. Rollback: uninstall restores .user.toml; adapter files removed.
  3. Run the full acceptance ladder (MASTER_IMPLEMENTATION_PLAN §6.9);
     confirm every blocking gate PASS.
  4. Write evidence/final/D4_RELEASE_READINESS.json (honest; no PENDING;
     tested_subject + evidence_commit two-commit identity).
  5. Write a merge strategy for owner approval. DO NOT merge or open a PR.

GATES: G-W10-E2E, G-W10-ROLLBACK, G-W10-RELEASE, G-AUTH, G-SCOPE.
STOP IF: install not clean; rollback loses user content; any prior gate red.
COMMIT: "rdx-tea: end-to-end acceptance and release readiness".
FINAL: report D4 v1 as release-ready PENDING explicit owner merge
authorization. The enforcement plane (rdx-tea-validate, modes/hooks/CI-gate,
subagent propagation, G7) remains separate future backlog.
```

---

## Deferred backlog prompts (NOT D4 v1 — do not run without owner sign-off)

These correspond to the enforcement plane. They are listed so a future
owner can schedule them deliberately, each in its own stage:

- **STAGE-08 / rdx-tea-validate:** build the enforcement verdict in
  `rdx-validator/rdx_tea/**` (project active_packs+mode into
  rdx-evidence.v1; reuse verdict enum + Cat-1..Cat-4 authority; reject
  Cat-1 PASS). Pre-read: ADR-001 §10-11, implementation-plan STAGE-08.
- **STAGE-09 / modes-hooks-CI-judgment:** MODE_0..4, pre-push hook,
  rdx-tea-gate.yml required check, Cat-4 approver binding. Pre-read:
  ADR-001 §9-15, implementation-plan STAGE-09.
- **G6F / subagent propagation:** only after sequential v1 ships; requires
  a real subagent-mode run + payload spy. Pre-read: ADR-001 §7 (note it was
  superseded by ADR-002 for v1).
