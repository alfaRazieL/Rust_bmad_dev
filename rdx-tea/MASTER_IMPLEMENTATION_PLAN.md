# RDX ↔ BMAD TEA — Master Implementation Plan (D4)

Stage: **D4.0 planning deliverable.** This document is the central,
wave-based plan for productionizing the RDX rule knowledge plane inside
real BMAD TEA workflows. It is written to be executed by CLI agents in
**separate fresh context windows**, one wave at a time.

- Branch: `rdx-tea-integration` (never touch `main`).
- START of D4: `1cd5b11b20ba8cea92101d47967665d44cea7e97`.
- `origin/main`: `d8140a25f8166bf0ca5ce5fc19f7cb1bd06a3d6d`.
- Basis: `D3_RULE_OPERATION_PROVEN` (D3.4.1). See §2.
- Companion artifacts: `implementation/WAVE_INDEX.md`,
  `implementation/PRODUCTION_EVAL_SPLIT.md`,
  `implementation/ACCEPTANCE_GATES.md`, `implementation/WAVE_PROMPTS.md`,
  `implementation/RISK_REGISTER.md`.
- Precondition audit: `research/D4_0_MASTER_PLAN_PRECONDITION_AUDIT.md`.

> This plan productionizes a **proven** path. It does NOT re-open the
> question of whether RDX is "better" than TEA (that comparative claim,
> G7, is deliberately out of scope). It productionizes the proven RDX
> rule-operation lifecycle so it can ship, install, and run reliably.

---

## 6.1 Executive summary

- **D3 rule-operation is proven.** The 12-run D3.4.1 pilot returned
  `RULE_OPERATION_PASS` (9/9 candidate, 3/3 control), Task dispatch 0,
  `OBSERVED_SEQUENTIAL`, verifier 9/9, CI 562/562, source-lock PASS.
- **D4 begins productionization.** No further proof-of-concept
  experiments are required before implementation. We are hardening,
  packaging, installing, and gating an already-validated runtime.
- **The production path is the wrapper-driven RDX→TEA non-interactive
  lifecycle** (`prepare-run` → child TEA Skill → `finalize-run`),
  sequential-only, auth-preserving. Bare child TEA workflows are
  interaction-gated; the wrapper is what makes them non-interactive and
  admissible.
- **Execution is wave-based.** Ten implementation waves (Wave 1–10) plus
  a validation wave (Wave 0). Knowledge-plane waves (2–5) precede
  admission/runtime hardening (6) which precedes installer/CI/docs/e2e
  (7–10), per the knowledge-plane-first guardrail.
- **The enforcement plane is explicitly deferred backlog** (§Deferred):
  `rdx-tea-validate` verdict, modes/hooks/CI-gate, subagent propagation,
  G7 behavioural benefit. None are D4 v1 waves.

---

## 6.2 Proof baseline

Exact identities (verified against `evidence/final/` at START_HEAD):

```
START of D4:          1cd5b11b20ba8cea92101d47967665d44cea7e97
origin/main:          d8140a25f8166bf0ca5ce5fc19f7cb1bd06a3d6d

D3.4.1: RULE_OPERATION_PASS / D3_RULE_OPERATION_PROVEN
        tested_subject 135b5ed  evidence 4be4d3e
        9/9 candidate pass, 3/3 control clean, 0 retries
        Task dispatch 0, OBSERVED_SEQUENTIAL 9/9, verifier 9/9
        workspace_delta 12/12, artifact_consistency 12/12
        CI 28698462520 success, 562/562 unique pass, source-lock PASS

D3.4.0: D3_4_0_PASS   tested f145c14  evidence fdbbb9a  CI 28694381995  561/561
        (rule-operation apparatus valid; 2 admissible live smokes)

D3.3.3: D3_3_3_PASS   tested 55451a6  evidence 33869ac  CI 28673519915
        (auth-preserving isolation; admissible v3 live smoke)
```

Upstream source lock (`poc/install-tree/_bmad/rdx-tea/bootstrap/sources.lock`):

```
RDX  rdx_source_sha  d8140a25…  tag v1.1.0   (== origin/main)
BMAD bmad_source_sha 3bcd6c3c…  tag v6.8.0
TEA  tea_source_sha  8734d51f…  tag v1.19.0
```

Governing decisions: ADR-001 (integration architecture, Variant D2),
ADR-002 (sequential active bundle, Variant D3, **supersedes** the
subagent-seed model of ADR-001), ADR-006 (auth-preserving runtime
isolation), ADR-007 (rule-operation pilot). The knowledge plane is at
"honest PASS at production layout" (D3.1 audit).

---

## 6.3 Production architecture target

Twelve components. Each row of the proven chain maps to owned files under
`poc/install-tree/_bmad/rdx-tea/` today. "Promote" = runtime code that
ships; "eval-only" = stays in `live-harness/` or `evals/`.

### 1. RDX rule knowledge base (KB)
- **Purpose:** the single canonical source of Rust rules, packs, router
  signals, verdict vocabulary, authority matrix.
- **Inputs:** none at runtime (static, source-locked).
- **Outputs:** consumed by parser/router/prepare.
- **Owned files:** `canonical/router-rules.json`,
  `canonical/authority-matrix.json`, `canonical/rule-check-map.json`,
  `canonical/status-definitions.json`,
  `canonical/kb-sections/section-{4,5,6,8}-*.md`,
  `canonical/rdx-tea-run.v1.schema.json`.
- **Failure modes:** KB drift vs RDX `origin/main`; hash mismatch;
  unpars­able rule body.
- **Test strategy:** source-lock hash tests; parser fail-closed tests;
  canonical snapshot hash pin.
- **Promote:** yes (whole `canonical/`).  **Eval-only:** none.

### 2. Rule router / pack activation
- **Purpose:** replay router rules over the diff + story tags to select
  active packs; apply story-tag and publish-flag gating.
- **Inputs:** diff text, story tags, `router-rules.json`.
- **Outputs:** `PackActivation[]` → active pack names.
- **Owned files:** `scripts/router.py` (vendored from RDX v1.1
  `rdx_validator/router.py`), `scripts/diff.py`.
- **Failure modes:** manual router drift vs RDX; over-broad `**/*.rs`
  activation; comment/doc lines falsely activating packs.
- **Test strategy:** router parity test (exact set equality with
  obligation-matrix ∩ router); per-pack × per-fixture activation matrix.
- **Promote:** yes.  **Eval-only:** none. Keep vendored + pinned; never
  fork logic.

### 3. Active-context bundle builder (projection)
- **Purpose:** deterministic projection of active rules into the
  `active-context.md` bundle + `run-manifest.json`; obligation-matrix
  filtering (packs, CORE rules, allowed IR fields per workflow); rust
  scope detection.
- **Inputs:** project-root, workflow, identity (base/head/rdx/tea SHAs),
  story/diff/tags, run_id.
- **Outputs:** run-scoped `active-context.md`, `run-manifest.json`
  (with `bundle_sha256`, `rdx_canonical_snapshot_sha256`, identity).
- **Owned files:** `scripts/prepare.py`, `scripts/obligation_matrix.py`,
  `scripts/rdx_parser.py`.
- **Failure modes:** non-determinism (wallclock/random/unsorted);
  identity missing / all-zero SHA; diff-digest disagreement; stray CORE
  dump when no pack active; wrong rust-scope on docs-only diffs.
- **Test strategy:** byte-determinism across processes; identity
  fail-closed; docs-only → empty bundle; golden bundle hashes in
  `evidence/hashes/`.
- **Promote:** yes.  **Eval-only:** none.

### 4. TEA wrapper Skill layer
- **Purpose:** LLM-facing contract that runs the two-phase lifecycle and
  invokes the real child TEA Skill in between (never simulates it).
- **Inputs:** `_bmad-run/story.md`, `tags.txt`, `rdx-tea-invocation.json`.
- **Outputs:** invokes prepare-run, dispatches child Skill, invokes
  finalize-run, prints `run-report.json`.
- **Owned files:** `.claude/skills/rdx-tea-test-design/SKILL.md`,
  `.claude/skills/rdx-tea-atdd/SKILL.md`.
- **Failure modes:** child simulation; use of test-only flags in
  production; `--run-id` not taken verbatim from the invocation contract;
  Task/subagent dispatch; touching upstream skill dirs.
- **Test strategy:** skill-contract lint; smoke that the wrapper never
  emits `--simulate-child` / `--test-write-fake-artefact`; dispatch-count
  assertion (Task 0).
- **Promote:** yes.  **Eval-only:** none.

### 5. Child BMAD TEA Skill invocation
- **Purpose:** run the unmodified upstream `bmad-testarch-{test-design,
  atdd}` Skill, driven non-interactively by the wrapper's overlay +
  persistent_facts.
- **Inputs:** the wrapper's run-specific overlay
  (`_bmad/custom/bmad-testarch-<workflow>.toml`) + active-context bundle.
- **Outputs:** TEA artefacts under `_bmad-output/**`.
- **Owned files:** none (upstream; installed via bootstrap/source-lock).
  The **overlay generator** in `rdx_tea_wrapper._write_run_specific_overlay`
  is owned.
- **Failure modes:** overlay not merged by upstream resolver; upstream
  version drift breaking `persistent_facts`/`on_complete` seams;
  interactive gating (no artefact emitted).
- **Test strategy:** overlay round-trip test; upstream file-hash lock;
  non-interactive completion smoke.
- **Promote:** overlay generator yes; child code stays upstream.

### 6. Workspace prepare/finalize lifecycle
- **Purpose:** run-scoped orchestration: acquire lock, resolve identity,
  assert sequential mode, snapshot outputs (prepare); compute delta,
  bind sidecars, verify, write run-report, restore overlay, release lock
  (finalize).
- **Inputs:** workflow, project-root, run_id, skill-dir.
- **Outputs:** `_bmad/rdx-tea/runtime/<workflow>/<run_id>/` state,
  manifest, diff, run-report; sidecars next to artefacts.
- **Owned files:** `scripts/rdx_tea_wrapper.py`.
- **Failure modes:** concurrent-run collision; no new artefact discovered;
  unchanged artefact SHA (LLM never wrote); non-sequential resolved mode;
  overlay not restored; lock leak.
- **Test strategy:** end-to-end external-project slice; lock refusal;
  fail-closed on empty delta; sequential-mode flip test.
- **Promote:** yes.  **Eval-only:** the `--test-write-fake-artefact`
  path (gated by `RDX_TEA_ALLOW_TEST_ARTEFACT=1`; must stay test-only).

### 7. Sidecar binder
- **Purpose:** write one `rdx-tea-run.v1` sidecar per real artefact,
  cross-checking bundle-on-disk vs `manifest.bundle_sha256`, hashing the
  artefact, enforcing artefact boundary (in project-root, not symlink,
  inside declared output roots).
- **Inputs:** artefact path, run manifest, declared output roots.
- **Outputs:** `<artefact>.rdx-tea.json`.
- **Owned files:** `scripts/binder.py`.
- **Failure modes:** missing manifest; bundle tamper; missing mandatory
  identity; symlink/traversal artefact; duplicate sidecar (nested roots).
- **Test strategy:** bundle-tamper fail-closed; boundary rejection;
  one-sidecar-per-artefact (canonical output roots).
- **Promote:** yes.  **Eval-only:** none.

### 8. Validator / verifier
- **Purpose:** behavioural integrity eval of a sidecar (9 checks: schema,
  manifest_hash, bundle_hash, artifact_hash, base_head_exist,
  diff_digest_recomputed, canonical_snapshot, source_lock,
  artifact_boundary).
- **Inputs:** sidecar, project-root, workflow, run_id, source-lock.
- **Outputs:** per-check `{status, detail}`, verdict PASS/FAIL.
- **Owned files:** `scripts/rdx_tea_validator.py`.
- **Failure modes:** schema drift; hash disagreements; missing canonical
  snapshot; source-lock drift.
- **Test strategy:** per-check pass/fail unit tests; mutation of each
  hashed input flips exactly that check.
- **Promote:** yes as a **behavioural verifier**. **Deferred:** the
  production **enforcement verdict** `rdx-tea-validate` in
  `rdx-validator/rdx_tea/` (STAGE-08) — NOT built in D4 v1.

### 9. Evidence / admission model
- **Purpose:** define what a run must satisfy to be admissible;
  fail-closed; recompute admissibility from primitive fields.
- **Inputs:** run-report, sidecars, verifier results, workspace delta,
  artifact consistency.
- **Outputs:** admissibility decision + reasons.
- **Owned files (production):** `scripts/rdx_tea_wrapper.py` run-report;
  the `rdx-tea-run.v1` schema. **Owned files (eval, for reference only):**
  `live-harness/schemas/live-evidence.v4.schema.json`,
  `live-harness/rule_operation.py` (delta + consistency detectors).
- **Failure modes:** trusting a recorded `admissible` flag; admitting a
  failed run; phantom file claims passing.
- **Test strategy:** admission recompute tests; "failed run is never
  FINALIZED-admissible" invariant.
- **Promote:** the *production* admission (run-report fail-closed) yes;
  the *v4 live-evidence* schema stays eval. Decision point: promote
  `collect_workspace_delta`/`check_artifact_consistency` equivalents into
  the production finalize path (Wave 5/6) — do NOT blindly copy the
  eval module.

### 10. Installer / bootstrapper
- **Purpose:** (a) upstream **source bootstrap** — clone/verify
  BMAD-METHOD + TEA at locked tags/hashes; (b) **project installer** —
  install `_bmad/rdx-tea/**`, wrapper Skills, and `_bmad/custom/*.toml`
  overlays into a user project without copying auth material or
  overriding `CLAUDE_CONFIG_DIR`.
- **Inputs:** target dir / project root; `sources.lock`.
- **Outputs:** verified upstream worktrees; installed adapter tree +
  overlays + project `.claude/settings.json` template.
- **Owned files (exists):** `bootstrap/bootstrap.py`, `bootstrap/sources.lock`.
  **Owned files (to build):** a project-install/lifecycle entrypoint
  (`rdx-tea-setup`-style install/update/uninstall) — ADR-001 §14.
- **Failure modes:** overwriting user config / `.user.toml`; copying
  credentials; overriding `CLAUDE_CONFIG_DIR`; version-range mismatch;
  non-idempotent update.
- **Test strategy:** install/update/uninstall smoke on temp dir;
  no-auth-material assertion; idempotency; version-range refusal.
- **Promote:** yes.  Project installer is **new production work** (Wave 7).

### 11. CI / source-lock / acceptance gates
- **Purpose:** branch-scoped fail-closed CI: guard-not-main, upstream
  bootstrap, `--verify-only` source-lock, canonical + live-harness pytest,
  refuse-mandatory-skips, unique-count, scope guard.
- **Inputs:** repo at HEAD on `rdx-tea-integration`.
- **Outputs:** JUnit XML, source-lock report, unique-count, sha256
  manifest, run-metadata.
- **Owned files:** `.github/workflows/rdx-tea-integration-check.yml`,
  `live-harness/ci_check.py`.
- **Failure modes:** running on main; masked skips; conflating node count
  with intent count; scope escape (changes outside rdx-tea/).
- **Test strategy:** the workflow itself is the gate; local `ci_check.py`
  unit tests.
- **Promote:** yes. `ci_check.py` is CI tooling (keep under live-harness).

### 12. Documentation & operator workflows
- **Purpose:** how to install, run, inspect evidence, and troubleshoot
  RDX-TEA workflows.
- **Inputs:** the shipped runtime + skills.
- **Outputs:** operator docs.
- **Owned files:** `docs/` under `rdx-tea/` (to create in Wave 9).
- **Failure modes:** doc drift vs commands; documenting eval flags as
  operator flags.
- **Test strategy:** doc commands are copy-runnable; a doc-lint that
  forbids `--test-write-fake-artefact`/`--allow-fixture-diff` in operator
  docs.
- **Promote:** yes (docs).

---

## 6.4 Production vs eval split

The single most important discipline: **never ship research evidence as
runtime code.** Full file-level classification is in
`implementation/PRODUCTION_EVAL_SPLIT.md`. Summary:

**PRODUCTION RUNTIME** (ships / installs / executes on the user's machine):
- `poc/install-tree/_bmad/rdx-tea/canonical/**` (KB)
- `poc/install-tree/_bmad/rdx-tea/scripts/**` (parser, router, diff,
  obligation_matrix, prepare, wrapper, binder, validator)
- `poc/install-tree/_bmad/rdx-tea/bootstrap/**` (bootstrap + sources.lock)
- `poc/install-tree/.claude/skills/rdx-tea-*/SKILL.md` (wrapper Skills)
- `poc/install-tree/_bmad/rdx-tea/VERSION`
- project `.claude/settings.json` template + `_bmad/custom/*.toml`
  overlay generator
- (future) project installer/lifecycle entrypoint

**EVAL / RESEARCH HARNESS** (never installed into a user project):
- `live-harness/**` (run_live, rule_operation, invoke_runtime,
  prepare_workspace, collect_evidence, runtime_discovery, schemas,
  policies, tests)
- `evals/**` (schedules, criteria, rubrics, run_pilot,
  run_rule_operation, grading, results incl. preserved failed attempts)
- `live-harness/ci_check.py` is CI tooling (repo-side, not installed).

**HISTORICAL EVIDENCE** (read-only audit trail; never runtime):
- `evidence/**`, `research/**`, `architecture/**`,
  `implementation-plan/**`, `implementation/**`.

**Guard:** Wave 1 establishes the boundary; Wave 8 CI adds a check that
the install-tree contains no import of `live-harness`/`evals`, and that
no eval/evidence path is referenced by shipped runtime code.

---

## 6.5 File layout target

Base the layout on the **existing** PoC install-tree (do not invent). The
production runtime already lives under
`poc/install-tree/_bmad/rdx-tea/`. The target is to **stabilize and
name** this as the shipped tree, keep eval/evidence separate, and add the
project-installer.

```
rdx-tea/
  poc/
    install-tree/              # PRODUCTION runtime (shipped/installed)
      _bmad/rdx-tea/
        canonical/             # KB (keep)
        scripts/               # runtime scripts (keep)
        bootstrap/             # upstream source bootstrap + sources.lock (keep)
        VERSION                # reconcile 0.3.1 vs sources.lock 0.3.2 (fix)
      .claude/skills/rdx-tea-*/ # wrapper Skills (keep)
    adapter/                   # legacy dev-coupled PoC (classify: keep-ref or retire — NOT deleted in D4)
    projections/ overlays/ patches/ schemas/  # PoC scratch (classify)
  installer/                   # NEW (Wave 7): project install/update/uninstall entrypoint + settings template
  live-harness/                # EVAL only (keep, never install)
  evals/                       # EVAL only (keep, never install)
  evidence/                    # historical evidence (keep, read-only)
  research/                    # audits/reports (keep) + D4_0 audit
  architecture/                # ADRs + schemas (keep)
  implementation-plan/         # D3-era proof plan (keep, superseded)
  implementation/              # NEW (D4.0): WAVE_INDEX, PRODUCTION_EVAL_SPLIT, ACCEPTANCE_GATES, WAVE_PROMPTS, RISK_REGISTER
  fixtures/ test-design/ tests/ # test assets (classify test-only vs eval-only)
  docs/                        # NEW (Wave 9): operator documentation
  MASTER_IMPLEMENTATION_PLAN.md
```

Per-directory disposition (create / keep / move / rename), rationale,
migration risk, and required tests are enumerated in
`implementation/PRODUCTION_EVAL_SPLIT.md` §"Layout disposition".

**Decision deferred to Wave 1:** whether to hoist
`poc/install-tree/_bmad/rdx-tea/` to a top-level `rdx-tea/runtime/` (as
the prompt's illustrative layout suggests). **Recommendation: do NOT
move it in v1** — the install-tree path is embedded in the CI workflow,
the bootstrap, tests, and the proven pilot. A rename is a high-risk,
zero-behaviour-value change. Wave 1 may add a top-level symlink/README
pointer instead, and defer any physical move to a post-v1 cleanup with
its own golden-hash re-pin.

---

## 6.6 Implementation waves

Global rules for **every** wave:
- Branch `rdx-tea-integration` only. Never `main`, no PR, no merge, no
  force push, no `git reset --hard`.
- Only touch `rdx-tea/**`, `rdx-validator/rdx_tea/**` (enforcement plane
  only, deferred), and `.github/workflows/rdx-tea-*.yml`.
- Never override `CLAUDE_CONFIG_DIR`; never use API key / OAuth token /
  `setup-token` / `apiKeyHelper`.
- Test-first (RED → GREEN); save command/cwd/env/SHA/exit/stdout/stderr/
  hashes under `evidence/`.
- Determinism: no wallclock/random; sorted iteration; re-pin golden
  hashes in `evidence/hashes/` on any generator change.
- No live Claude model calls except where a wave explicitly authorizes a
  single bounded smoke; **never** re-run the 12-run pilot or a mass eval.
- End each wave: commit(s) on the branch + a final-response block (below).

Copy-ready per-wave prompts are in `implementation/WAVE_PROMPTS.md`
(§6.7). Gate IDs referenced below are defined in
`implementation/ACCEPTANCE_GATES.md`.

---

### Wave 0 — Plan validation & repository hygiene
- **Wave ID:** W0 (no production code).
- **Goal:** validate this plan against the repo, confirm HEAD/branch,
  inventory the production/eval/evidence split, set branch discipline.
- **Scope:** read-only + optional notes under `implementation/`.
- **Read first:** this plan; `research/D4_0_MASTER_PLAN_PRECONDITION_AUDIT.md`;
  `implementation/PRODUCTION_EVAL_SPLIT.md`; `evidence/final/D3_4_1_FINAL_VERIFICATION.json`.
- **Allowed to change:** `implementation/WAVE_INDEX.md` (status),
  optional `implementation/*` notes. No runtime files.
- **Tasks:** verify `git rev-parse HEAD == 1cd5b11…`; confirm working
  tree clean within `rdx-tea/**`; run the D4.0 artifact-presence check;
  run `pytest rdx-tea/live-harness/tests/test_harness_v4.py -q`; confirm
  the PRODUCTION_EVAL_SPLIT classification matches disk.
- **Acceptance gates:** G-W0-HEAD, G-W0-SPLIT, G-W0-TESTS.
- **Required tests:** artifact-presence check; the single v4 harness test
  (cheap).
- **Expected commits:** at most one (`rdx-tea: validate D4 plan and wave index`).
- **Stop conditions:** HEAD ≠ expected; split classification wrong;
  scope guard would be violated.
- **Final response format:** the standard block (see end of §6.6).
- **Handoff:** confirm Wave 1 can proceed; note any layout surprises.

### Wave 1 — Production layout & source boundaries
- **Wave ID:** W1.
- **Goal:** make the production/eval boundary explicit and enforceable
  **without changing runtime behaviour**. Reconcile version drift.
- **Scope:** classification, READMEs, boundary tests; no logic change.
- **Read first:** `research/D3_1_PRODUCTION_LAYOUT_AUDIT.md`;
  `implementation/PRODUCTION_EVAL_SPLIT.md`; `poc/install-tree/**`;
  `poc/adapter/**`.
- **Allowed to change:** `poc/install-tree/_bmad/rdx-tea/VERSION`
  (reconcile with `sources.lock:adapter_version`); new
  `poc/install-tree/README.md`; new boundary test under `tests/`;
  classification README for `poc/adapter/`. **Do not delete** anything.
- **Tasks:** pin `VERSION == adapter_version`; add a boundary test that
  fails if any file under `install-tree/` imports `live-harness`/`evals`
  or references an `evidence/`/`evals/` path; classify `poc/adapter/` as
  keep-ref or retire-later (documented, not deleted); (recommended) add a
  top-level pointer to the install-tree rather than moving it.
- **Acceptance gates:** G-SPLIT-IMPORT, G-DET (unchanged hashes),
  G-W1-VERSION.
- **Required tests:** new boundary/import test; full canonical suite
  unchanged (byte-identical golden bundle hashes).
- **Expected commits:** `rdx-tea: reconcile adapter version and pin production/eval boundary`.
- **Stop conditions:** any golden bundle hash changes (that means you
  changed behaviour — revert); a move breaks CI paths.
- **Handoff:** boundary is enforceable; hashes unchanged; Wave 2 can
  harden the KB.

### Wave 2 — Rule KB & router productionization  *(knowledge plane)*
- **Wave ID:** W2.
- **Goal:** harden the KB + router: pack activation from tags/diff,
  forbidden-pack logic by ACTIVE packs, canonical hashes, no router drift.
- **Read first:** `canonical/router-rules.json`; `scripts/router.py`;
  `scripts/diff.py`; `evals/D3_4_RULE_OPERATION_CRITERIA.v1.yaml`;
  ADR-002 §3–4.
- **Allowed to change:** `scripts/router.py`, `scripts/diff.py`,
  `canonical/**` (only with a source-lock re-pin + addendum), tests under
  `tests/unit/`.
- **Tasks:** confirm router parity (exact set equality vs
  obligation-matrix ∩ router); lock the `**/*.rs` over-broad guard;
  confirm docs-only → no pack; pin `canonical_snapshot` hash; add/extend
  per-pack × per-fixture activation matrix tests (async / api / docs-only
  at minimum, matching criteria v1 expected packs `[async]`,
  `[api, async]`, `[]`).
- **Acceptance gates:** G-W2-PARITY, G-W2-FORBIDDEN, G-DET.
- **Required tests:** router-parity; activation matrix; canonical hash pin.
- **Expected commits:** `rdx-tea: harden rule KB and router pack activation`.
- **Stop conditions:** router logic forks from RDX; forbidden pack judged
  from prose; canonical hash changes without a source-lock addendum.
- **Handoff:** active-pack selection is deterministic and parity-checked;
  Wave 3 can rely on it.

### Wave 3 — Active-context bundle builder  *(knowledge plane)*
- **Wave ID:** W3.
- **Goal:** productionize bundle generation, bundle schema, bundle
  hashes, rule projection, rust-scope, source-lock stamping.
- **Read first:** `scripts/prepare.py`, `scripts/obligation_matrix.py`,
  `scripts/rdx_parser.py`, `architecture/WORKFLOW_OBLIGATION_MATRIX.csv`,
  `canonical/rdx-tea-run.v1.schema.json`.
- **Allowed to change:** `scripts/prepare.py`,
  `scripts/obligation_matrix.py`, `scripts/rdx_parser.py`,
  `evidence/hashes/**` (golden re-pin), `tests/unit/`,
  `tests/integration/`.
- **Tasks:** enforce byte-determinism (no wallclock/random, sorted);
  identity fail-closed (mandatory SHAs, reject all-zero, diff-digest
  agreement); docs-only diff → empty bundle even for "all"-CORE
  workflows; obligation-matrix field filtering; pin golden bundle hashes
  per scenario in `evidence/hashes/`.
- **Acceptance gates:** G-W3-DETERMINISM, G-W3-IDENTITY, G-W3-SCHEMA, G-DET.
- **Required tests:** cross-process byte-identity; identity fail-closed;
  empty-bundle-on-docs-only; schema-valid manifest; golden hashes.
- **Expected commits:** `rdx-tea: productionize active-context bundle builder`.
- **Stop conditions:** bundle bytes vary across runs; identity accepted
  when missing/zero; schema regression.
- **Handoff:** bundle is deterministic, schema-valid, source-stamped;
  Wave 4 can wrap it.

### Wave 4 — TEA wrapper Skills & non-interactive lifecycle  *(knowledge plane)*
- **Wave ID:** W4.
- **Goal:** productionize the wrapper Skills + prepare-run/finalize-run,
  exact child-invocation semantics, sequential-only, no Task/subagents.
- **Read first:** `scripts/rdx_tea_wrapper.py`;
  `.claude/skills/rdx-tea-test-design/SKILL.md`;
  `.claude/skills/rdx-tea-atdd/SKILL.md`; ADR-002 §5–…; ADR-006.
- **Allowed to change:** `scripts/rdx_tea_wrapper.py`, the two
  `SKILL.md` files, `tests/lifecycle/`, `tests/bmad-tea/`.
- **Tasks:** confirm the invocation-contract handshake (run_id verbatim;
  candidate-only); sequential-mode fail-closed; overlay
  generate/backup/restore; active-run lock acquire/release; empty-delta
  fail-closed; ensure production paths never accept
  `--simulate-child`/`--test-write-fake-artefact` (keep them env-gated
  test-only); assert Task-dispatch surface removed via
  `--disallowedTools Task TaskOutput TaskStop` in the documented invoke.
- **Acceptance gates:** G-W4-LIFECYCLE, G-W4-SEQUENTIAL, G-W4-NOTASK,
  G-AUTH.
- **Required tests:** external-project end-to-end slice (deterministic,
  no live model — uses the env-gated fake-artefact path in tests only);
  sequential-flip refusal; lock refusal; overlay round-trip.
- **Expected commits:** `rdx-tea: productionize wrapper Skills and non-interactive lifecycle`.
- **Stop conditions:** wrapper simulates the child in production; Task
  dispatch appears; non-sequential mode admitted; overlay not restored.
- **Handoff:** the lifecycle drives the real child to completion
  sequentially; Wave 5 can bind its outputs.

### Wave 5 — Binder, sidecars, workspace delta, artifact consistency  *(knowledge plane)*
- **Wave ID:** W5.
- **Goal:** productionize sidecars (one per artefact), workspace delta,
  declared-file checks, and artifact-consistency detectors in the
  production finalize path.
- **Read first:** `scripts/binder.py`; wrapper `_delta_outputs` /
  `_canonical_output_roots`; `live-harness/rule_operation.py`
  (`collect_workspace_delta`, `check_artifact_consistency`) — as the
  *reference* logic to promote; ADR-007 rationale.
- **Allowed to change:** `scripts/binder.py`, `scripts/rdx_tea_wrapper.py`
  (finalize), a **new** production module for delta/consistency (e.g.
  `scripts/workspace_delta.py`) if promoting, `tests/`.
- **Tasks:** enforce one-sidecar-per-artefact via canonical output roots;
  bundle-tamper fail-closed; artefact boundary (symlink/traversal/outside
  project); **decide + implement** promotion of declared-file validation
  and artifact-consistency detectors into the production finalize path
  (do not import `live-harness`); duplicate-frontmatter = warning,
  phantom file claim / missing declared file = fail-closed.
- **Acceptance gates:** G-W5-SIDECAR, G-W5-DELTA, G-W5-CONSISTENCY,
  G-SPLIT-IMPORT.
- **Required tests:** one-sidecar-per-artefact; bundle-tamper; boundary
  rejection; phantom-claim fail; declared-but-missing fail;
  duplicate-frontmatter-warning-not-fail.
- **Expected commits:** `rdx-tea: productionize sidecars, workspace delta and artifact consistency`.
- **Stop conditions:** duplicate sidecars regress; production imports the
  eval module; phantom claims pass.
- **Handoff:** finalize output is consistent and reality-checked; Wave 6
  can define admission on top.

### Wave 6 — Verifier / admission & failure semantics
- **Wave ID:** W6.
- **Goal:** productionize the behavioural verifier + fail-closed admission
  model, run outcomes, cleanup, retry policy — **without** building the
  deferred `rdx-tea-validate` enforcement verdict.
- **Read first:** `scripts/rdx_tea_validator.py`; ADR-006 §5–9;
  `live-harness/schemas/live-evidence.v4.schema.json` (reference only).
- **Allowed to change:** `scripts/rdx_tea_validator.py`, wrapper
  run-report/admission, `tests/`.
- **Tasks:** confirm the 9 checks each fail-close on a mutated input;
  recompute admission from primitive fields (never trust a recorded
  flag); define run outcomes (SUCCESS / WORKFLOW_FAILURE /
  VERIFIER_FAILURE / SCHEMA_FAILURE / …) in fixed order; document
  cleanup + a bounded retry policy for INFRA/RUNTIME only (never convert
  a rule-operation/verifier failure into an infra retry).
- **Acceptance gates:** G-W6-VERIFIER, G-W6-ADMISSION, G-W6-FAILCLOSED.
- **Required tests:** per-check mutation; admission recompute;
  "failed run never admissible" invariant.
- **Expected commits:** `rdx-tea: productionize verifier and fail-closed admission`.
- **Stop conditions:** any check can be bypassed; a failed run becomes
  admissible; admission trusts a self-reported flag.
- **Handoff:** admission is honest and fail-closed; installer (Wave 7)
  can package it.

### Wave 7 — Installer / bootstrap & project settings
- **Wave ID:** W7.
- **Goal:** productionize the install flow: version pinning, project-local
  settings, MCP isolation, skill installation — **no auth material
  copied, no `CLAUDE_CONFIG_DIR` override**.
- **Read first:** `bootstrap/bootstrap.py`; `bootstrap/sources.lock`;
  ADR-006 §1–3; ADR-001 §14 (lifecycle);
  `live-harness/prepare_workspace.py` (reference for arm-specific skill
  install + project settings).
- **Allowed to change:** `bootstrap/**`, new `installer/**` (project
  install/update/uninstall + `.claude/settings.json` template + overlay
  writer), `tests/lifecycle/`, `tests/acceptance/`.
- **Tasks:** build an idempotent project installer that writes
  `_bmad/rdx-tea/**`, the wrapper Skills, `_bmad/custom/*.toml` overlays,
  and a project `.claude/settings.json` (`disableBundledSkills`,
  `disableClaudeAiConnectors`, `autoMemoryEnabled:false`); update path
  refuses to overwrite `*.user.toml`; uninstall removes adapter files but
  keeps user content; assert **no** credential/token/config-dir env is
  ever written or read; version-range refusal against
  `_bmad/tea/config.yaml`.
- **Acceptance gates:** G-W7-INSTALL, G-W7-NOAUTH, G-AUTH, G-W7-IDEMPOTENT.
- **Required tests:** install/update/uninstall smoke on temp dir;
  no-auth-material assertion; idempotency; `.user.toml` preservation;
  version-range refusal.
- **Expected commits:** `rdx-tea: add project installer and settings template`,
  `rdx-tea: installer lifecycle and idempotency tests`.
- **Stop conditions:** installer copies auth material; overrides
  `CLAUDE_CONFIG_DIR`; clobbers user config.
- **Handoff:** clean install works on a temp project; Wave 8 can gate it
  in CI.

### Wave 8 — CI gates & source-lock
- **Wave ID:** W8.
- **Goal:** production CI: no mandatory skips, source-lock verify,
  deterministic tests, golden fixtures, branch guards, boundary check.
- **Read first:** `.github/workflows/rdx-tea-integration-check.yml`;
  `live-harness/ci_check.py`; the CI section of D3.1 audit §10.
- **Allowed to change:** `.github/workflows/rdx-tea-*.yml`,
  `live-harness/ci_check.py`, CI-support tests under `tests/ci/`.
- **Tasks:** keep guard-not-main + scope-guard; add a **production/eval
  boundary check** job (no install-tree import of `live-harness`/`evals`;
  no evidence path in shipped code); add golden-hash verification of
  bundle/canonical snapshots; keep `--verify-only` source-lock; keep
  refuse-mandatory-skips + unique-count.
- **Acceptance gates:** G-W8-CI, G-W8-SOURCELOCK, G-W8-NOSKIP,
  G-SPLIT-IMPORT, G-SCOPE.
- **Required tests:** the workflow run (green); `ci_check.py` unit tests.
- **Expected commits:** `rdx-tea: add CI boundary and golden-hash gates`.
- **Stop conditions:** CI can run on main; skips masked; scope escape
  allowed; boundary check missing.
- **Handoff:** CI enforces the invariants; Wave 9 documents them.

### Wave 9 — Documentation & operator workflows
- **Wave ID:** W9.
- **Goal:** operator docs: install, run RDX-TEA workflows, inspect
  evidence, troubleshoot.
- **Read first:** the two `SKILL.md`; installer (Wave 7); wrapper CLI
  surface; this plan §6.3.
- **Allowed to change:** new `rdx-tea/docs/**`, `poc/install-tree/README.md`.
- **Tasks:** write install guide, run guide (prepare/finalize via the
  wrapper Skill, sequential requirement), evidence-inspection guide
  (run-report, sidecars, verifier), troubleshooting (auth preserved, mode
  not sequential, empty delta); a doc-lint that forbids eval/test-only
  flags in operator docs.
- **Acceptance gates:** G-W9-DOCS, G-W9-NOEVALFLAGS.
- **Required tests:** doc-command copy-run check; doc-lint.
- **Expected commits:** `rdx-tea: operator documentation and troubleshooting`.
- **Stop conditions:** docs reference `--test-write-fake-artefact` /
  `--allow-fixture-diff` as operator steps.
- **Handoff:** operators can run the system from docs alone; Wave 10 can
  acceptance-test end to end.

### Wave 10 — End-to-end acceptance & release/merge plan
- **Wave ID:** W10.
- **Goal:** clean-install test, real-project fixture test, rollback,
  release checklist, and a **proposed** merge-to-main strategy (proposed,
  not executed).
- **Read first:** installer (W7); CI (W8); `fixtures/rust-projects/**`;
  `implementation/ACCEPTANCE_GATES.md`; `implementation-plan/FINAL_ACCEPTANCE_CHECKLIST.md`.
- **Allowed to change:** `tests/acceptance/`, `evidence/final/**` (a D4
  release-readiness verification), `implementation/` (release checklist).
- **Tasks:** clean install into a disposable project + one bounded
  non-interactive smoke (authorized single run, NOT the pilot); rollback
  (uninstall restores `.user.toml`); assemble the release checklist and a
  written merge strategy for owner approval (no merge performed).
- **Acceptance gates:** G-W10-E2E, G-W10-ROLLBACK, G-W10-RELEASE.
- **Required tests:** clean-install acceptance; rollback smoke;
  full acceptance ladder green (§6.9).
- **Expected commits:** `rdx-tea: end-to-end acceptance and release readiness`.
- **Stop conditions:** install not clean; rollback loses user content;
  any prior gate red.
- **Handoff:** D4 v1 productionization is release-ready **pending owner
  review and explicit merge authorization**.

**Standard final-response block (every wave):**
```
WAVE: <id>
BRANCH: rdx-tea-integration
START_HEAD: <sha>   FINAL_HEAD: <sha>
GATES: <gate-id: PASS/FAIL ...>
TESTS_RUN: <cmds + counts>
FILES_CREATED / FILES_MODIFIED:
COMMITS:
STOP_CONDITIONS_HIT: <none|...>
NEXT_WAVE_HANDOFF: <notes>
```

---

## 6.7 Per-wave prompt template

Ready-to-copy, self-contained prompts for each wave live in
`implementation/WAVE_PROMPTS.md` (`WAVE_0_PROMPT` … `WAVE_10_PROMPT`).
Each prompt: (a) states the wave goal; (b) lists read-first files;
(c) lists do-not-touch; (d) restates the global rules (branch, auth,
scope, determinism); (e) states acceptance gates; (f) gives the final
response format; (g) references this master plan and the acceptance
matrix. The owner runs each in a fresh CLI context.

---

## 6.8 Risk register (summary)

Full register with likelihood/impact/mitigation/owner-wave in
`implementation/RISK_REGISTER.md`. Top risks:

1. **Auth isolation breakage** — any override of `CLAUDE_CONFIG_DIR` or
   introduction of API key/token. *Mitigation:* G-AUTH gate + installer
   no-auth assertion (W4, W7).
2. **Shipping eval artifacts as production** — install-tree importing
   `live-harness`/`evals` or bundling evidence. *Mitigation:*
   G-SPLIT-IMPORT boundary test + CI job (W1, W8).
3. **prompt_hash vs prompt_template_hash confusion** — eval schedule
   field naming. *Mitigation:* keep eval-only; document; optional rename
   in a future schedule version (not D4).
4. **Baseline child interactive gating misread as a production
   requirement** — *Mitigation:* production admission never requires
   baseline artefacts (W6 doc + gate).
5. **Duplicate artefacts/sidecars regression** — nested output roots.
   *Mitigation:* canonical-output-roots test (W5).
6. **Task/subagent dispatch regression** — *Mitigation:* `--disallowedTools`
   in the documented invoke + Task-0 assertion (W4, W8).
7. **Forbidden packs detected from prose** — *Mitigation:* judge by
   ACTIVE packs only (W2).
8. **Missed workspace delta / declared generated files** —
   *Mitigation:* declared-file verification fail-closed (W5).
9. **Absolute path leakage in evidence** — cosmetic. *Mitigation:* prefer
   project-relative paths where practical (W6/W9).
10. **Source-lock drift** — upstream tag/hash change. *Mitigation:*
    `--verify-only` in CI + addendum discipline (W2, W8).
11. **Installer overwriting user config** — *Mitigation:* `.user.toml`
    preservation + idempotency tests (W7).
12. **Unclear rollback** — *Mitigation:* uninstall smoke restoring user
    content (W7, W10).
13. **Non-determinism creep** — wallclock/random in generators.
    *Mitigation:* byte-identity tests + golden re-pin (W3).
14. **Layout move breaking CI/tests** — *Mitigation:* recommend NOT
    moving the install-tree in v1; pointer only (W1).

---

## 6.9 Acceptance model

The acceptance ladder (bottom rungs gate the rungs above):

```
1. unit tests            (parser, router, obligation matrix, binder, verifier)
2. schema tests          (rdx-tea-run.v1 sidecar + manifest)
3. golden fixtures       (byte-identical bundle + canonical snapshot hashes)
4. wrapper smoke         (deterministic external-project slice; no live model)
5. installer dry-run     (install/update/uninstall on temp dir; no auth material)
6. end-to-end project    (clean install + one bounded non-interactive smoke)
7. CI                    (green: source-lock, no skips, unique count, scope, boundary)
8. owner review          (human sign-off on evidence + release checklist)
9. merge readiness       (proposed strategy; merge only on explicit owner authorization)
```

Rungs 1–5 are deterministic and must be green before any live smoke.
Rung 6's live smoke is a single bounded authorized run — **never** the
12-run pilot or a mass eval.

---

## 6.10 Branch & commit discipline

- **Branch:** all D4 work on `rdx-tea-integration`. `main` is never
  modified until an explicit, owner-authorized merge stage (post-D4).
- **Commit granularity:** one focused commit per logical step; the
  recommended messages per wave are in §6.6. Evidence commits are
  separate from code commits.
- **No force push. No PR. No merge. No `git reset --hard`.**
- **Two-commit identity** where a wave publishes a final verification
  that must reference its own evidence commit: write the verification
  with the tested-subject SHA, commit it, then a follow-up commit fills
  `evidence_commit_sha` (pointer closure) — mirroring the D3.4.x pattern.
  No `PENDING` sentinel survives in the final HEAD.
- **Fresh-context alignment:** each wave's first act is to re-verify HEAD
  and read this plan + the wave's read-first list, so no context depends
  on prior chat memory.
- **Scope staging:** stage files explicitly by path (never `git add -A`)
  so out-of-scope untracked items (e.g. `.agents/`) are never committed.

---

## 6.11 What NOT to do

- Do **not** re-run the D3 pilot (or any mass eval) as "implementation".
  It is authoritative evidence; cite it, don't repeat it.
- Do **not** use an API key, `CLAUDE_CODE_OAUTH_TOKEN`, `setup-token`, or
  `apiKeyHelper`. Do **not** copy or read auth/Keychain material.
- Do **not** set or override `CLAUDE_CONFIG_DIR`. Inherit the existing
  OAuth session unchanged.
- Do **not** ship live transcripts, evidence, schedules, or grading code
  as production runtime.
- Do **not** make baseline (control) artefact production a production
  requirement — the bare child is interaction-gated by design.
- Do **not** replace deterministic gates with LLM grading. The LLM
  diagnostic is optional and can never override a deterministic verdict.
- Do **not** weaken fail-closed admission (missing manifest, bundle
  tamper, empty delta, non-sequential mode, missing identity, phantom
  claim must all fail closed).
- Do **not** hide or overwrite failed attempts. Preserve them.
- Do **not** claim G7 (behavioural benefit vs baseline). It is out of
  scope and not claimed.
- Do **not** touch `main`, upstream `.claude/skills/**`, or files outside
  `rdx-tea/` / `rdx-validator/rdx_tea/` / `.github/workflows/rdx-tea-*.yml`.

---

## 6.12 Definition of done for D4 implementation

D4 v1 production integration is **done** when all of the following hold
on `rdx-tea-integration` (and only then is a merge proposal put to the
owner):

1. Waves 1–10 complete; every acceptance gate in
   `implementation/ACCEPTANCE_GATES.md` is PASS (or explicitly
   non-blocking with justification).
2. The production runtime (`poc/install-tree/_bmad/rdx-tea/**` + wrapper
   Skills + installer) ships **no** import of `live-harness`/`evals` and
   references **no** evidence/eval path (boundary check green).
3. Bundle + canonical-snapshot golden hashes are pinned and verified in
   CI; generators are byte-deterministic.
4. The wrapper lifecycle drives the real child TEA Skill to completion
   **sequentially** with Task dispatch 0, one sidecar per artefact,
   verifier PASS, fail-closed admission.
5. A clean install into a disposable project succeeds with **no** auth
   material written and **no** `CLAUDE_CONFIG_DIR` override; uninstall
   restores user content.
6. CI is green (guard-not-main, source-lock `--verify-only`, no mandatory
   skips, unique-count, scope guard, boundary check).
7. Operator docs let a new operator install, run, and inspect evidence
   without reading the source.
8. A D4 release-readiness verification is committed under
   `evidence/final/` with honest status (no `PENDING`, no overclaim), and
   a written merge strategy awaits explicit owner authorization.

Enforcement-plane items (below) are **not** required for D4 v1 done.

---

## Deferred — enforcement-plane backlog (NOT D4 v1 waves)

Documented so future contexts don't mistake them for in-scope work. Each
is a separate future stage after v1 ships and the owner authorizes it:

- **`rdx-tea-validate` enforcement verdict** in `rdx-validator/rdx_tea/**`
  (STAGE-08): projects `active_packs`+`mode` into an `rdx-evidence.v1`
  envelope, reuses the 14-value verdict enum and Cat-1..Cat-4 authority
  matrix, rejects Cat-1 PASS from artefacts. The install-tree ships only
  a behavioural verifier today.
- **Modes / hooks / CI-gate / judgment / Cat-4 approval** (STAGE-09,
  ADR-001 §9–15): MODE_0..4, pre-push hook, `rdx-tea-gate.yml` required
  check with target-branch validator trust, `approvers.yaml` binding.
- **Subagent / agent-team worker propagation** (`G6F`, ADR-001 §7): the
  proven v1 is sequential-only with a fail-closed guard; subagent
  propagation was never live-exercised.
- **G7 behavioural benefit vs baseline:** deliberately not pursued; if
  ever wanted, it needs a non-interactive RDX-free baseline and a
  pre-registered rubric — and still cannot gate correctness.

---

*End of Master Implementation Plan. Waves are indexed in
`implementation/WAVE_INDEX.md`; copy-ready prompts in
`implementation/WAVE_PROMPTS.md`; gates in
`implementation/ACCEPTANCE_GATES.md`; file classification in
`implementation/PRODUCTION_EVAL_SPLIT.md`; risks in
`implementation/RISK_REGISTER.md`.*
