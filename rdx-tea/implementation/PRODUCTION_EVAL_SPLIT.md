# Production / Eval Inventory & Classification

Classifies every current `rdx-tea/**` file/directory so future waves know
what **ships as runtime**, what stays **eval-only**, what is **historical
evidence**, what is **test-only**, and what must be **migrated**. This is
the guard against shipping research evidence as production code
(`MASTER_IMPLEMENTATION_PLAN.md` §6.4).

**D4.0 deletes nothing.** This file only classifies. Deletion/retirement,
if any, is a justified future-wave decision.

Classes: `PRODUCTION` · `EVAL-ONLY` · `HISTORICAL` · `TEST-ONLY` ·
`TO-MIGRATE` · `TO-RETIRE-LATER`.

## 1. Directory-level classification

| Path | Class | Notes |
|---|---|---|
| `poc/install-tree/_bmad/rdx-tea/canonical/**` | **PRODUCTION** | RDX rule KB; source-locked; sole projection input. |
| `poc/install-tree/_bmad/rdx-tea/scripts/**` | **PRODUCTION** | parser, router (vendored), diff, obligation_matrix, prepare, wrapper, binder, validator. |
| `poc/install-tree/_bmad/rdx-tea/bootstrap/**` | **PRODUCTION** | `bootstrap.py` + `sources.lock`; upstream source bootstrap + `--verify-only`. |
| `poc/install-tree/_bmad/rdx-tea/VERSION` | **PRODUCTION** | reconcile `0.3.1` vs `sources.lock:adapter_version 0.3.2` (Wave 1). |
| `poc/install-tree/.claude/skills/rdx-tea-*/SKILL.md` | **PRODUCTION** | wrapper Skills (LLM-facing contract). |
| `poc/adapter/**` | **TO-MIGRATE** | legacy dev-coupled PoC (imports `rdx_validator` directly). Superseded by install-tree (self-contained, vendored router). Classify keep-as-reference or retire-later in Wave 1; **not deleted in D4.0**. |
| `poc/projections/**` (`knowledge/`, `rdx-tea-index.csv`) | **TO-MIGRATE** | early metadata-only projection PoC; superseded by `prepare.py` semantic bundle (ADR-002). Reference only. |
| `poc/overlays/`, `poc/patches/`, `poc/schemas/` | **TO-RETIRE-LATER** | empty (0 tracked files). Confirm empty and retire in a future cleanup. |
| `live-harness/**` | **EVAL-ONLY** | live pilot harness (`run_live.py` ~100 KB, `rule_operation.py`, `invoke_runtime.py`, `prepare_workspace.py`, `collect_evidence.py`, `runtime_discovery.py`, `schemas/live-evidence.v{1..4}`, `policies/`, `fixtures/`, `tests/`). **Never installed.** |
| `live-harness/ci_check.py` | **EVAL-ONLY (CI tooling)** | repo-side CI helper (refuse-skips, unique-count). Runs in CI, not installed into a user project. |
| `live-harness/rule_operation.py` | **EVAL-ONLY → source for TO-MIGRATE** | `collect_workspace_delta` / `check_artifact_consistency` are the *reference* logic to **re-implement** in production finalize (Wave 5). Do not import this module from runtime. |
| `evals/**` | **EVAL-ONLY** | schedules (`runs/*.json`), criteria (`D3_4_RULE_OPERATION_CRITERIA.v1.yaml`), rubrics, `run_pilot.py`, `run_rule_operation.py`, `grading/**`, `results/**` (incl. `_d3_4_1_preserved_failed_attempts/`). 401 tracked files. |
| `evidence/**` | **HISTORICAL** | 100 tracked files: `final/` verifications, `live/` smokes, `hashes/`, `logs/`, `commands/`, `artifacts/`. Read-only audit trail. |
| `research/**` | **HISTORICAL** | 32 D-stage reports/audits/blockers incl. `D4_0_MASTER_PLAN_PRECONDITION_AUDIT.md`. |
| `architecture/**` | **HISTORICAL (+1 PRODUCTION mirror)** | ADR-001/002/004/005/006/007, `WORKFLOW_OBLIGATION_MATRIX.csv`, schemas. `rdx-tea-run.v1.schema.json` here mirrors the **PRODUCTION** copy in `canonical/`; keep one canonical (Wave 3 decides which is authoritative). |
| `implementation-plan/**` | **HISTORICAL** | D3-era proof plan (STAGE-01..09, guardrails); superseded but retained. |
| `implementation/**` | **HISTORICAL (planning)** | this D4.0 wave pack. |
| `test-design/**` | **HISTORICAL (test strategy)** | `MASTER_TEST_STRATEGY.md`, `BEHAVIORAL_EVAL_PLAN.md`, `RELEASE_GATES.md`, `TEST_CASES.yaml`, `TEST_TRACEABILITY_MATRIX.md`. Planning/reference. |
| `tests/**` | **TEST-ONLY** | 14 tracked: `unit/`, `integration/`, `lifecycle/`, `bmad-tea/`, `contracts/`, `mutation/`, plus empty `acceptance/`, `ci/`, `evals/`, `fixtures/` (to fill in Waves 8/10). Repo tests, not installed. |
| `fixtures/**` | **TEST-ONLY** | 0 tracked files on disk (real fixtures live under `live-harness/fixtures/` (eval) and `tests/fixtures/` (test)). Confirm/consolidate in Wave 1. |
| `README.md`, `MASTER_IMPLEMENTATION_PLAN.md` | **HISTORICAL (docs)** | repo-level docs. |
| `.venv-baseline/` | **not tracked** | local venv; untracked/ignored; never committed or shipped. |

## 2. What installs into a user project (the shipped surface)

Only these become files in a user's project via the installer (Wave 7):

```
<project>/_bmad/rdx-tea/canonical/**          (from install-tree)
<project>/_bmad/rdx-tea/scripts/**            (from install-tree)
<project>/_bmad/rdx-tea/bootstrap/sources.lock (identity stamp; bootstrap.py optional)
<project>/_bmad/rdx-tea/VERSION
<project>/.claude/skills/rdx-tea-test-design/SKILL.md
<project>/.claude/skills/rdx-tea-atdd/SKILL.md
<project>/.claude/settings.json               (project-surface isolation template)
<project>/_bmad/custom/bmad-testarch-*.toml   (overlay; generated per run by the wrapper)
```

Nothing from `live-harness/`, `evals/`, `evidence/`, `research/`,
`architecture/`, `implementation*/`, `test-design/`, or `tests/` is ever
copied into a user project.

## 3. Promotion decisions (TO-MIGRATE detail)

| Item | Current home (eval/PoC) | Target (production) | Wave | Rule |
|---|---|---|---|---|
| Declared-file validation + artifact-consistency detectors | `live-harness/rule_operation.py` | new `scripts/workspace_delta.py` (re-implemented, not imported) | W5 | production must not import `live-harness`. |
| Arm-specific skill install + project `.claude/settings.json` | `live-harness/prepare_workspace.py` (reference) | `installer/**` | W7 | reuse the *pattern*, not the eval module. |
| `poc/adapter/` logic | dev-coupled PoC | none (install-tree is canonical) | W1 | keep as reference or retire-later; document. |

## 4. Layout disposition (create / keep / move / rename)

| Directory | Disposition | Rationale | Migration risk | Tests required |
|---|---|---|---|---|
| `poc/install-tree/_bmad/rdx-tea/` | **keep** | proven production layout; embedded in CI/bootstrap/tests/pilot. | HIGH if moved | full canonical suite byte-identical. |
| top-level `runtime/` (prompt's illustration) | **do NOT create in v1** | a physical move is high-risk, zero behaviour value; CI paths would break. | HIGH | n/a (deferred). Add a pointer/README only. |
| `installer/` | **create (W7)** | project install/update/uninstall is new production work. | LOW | lifecycle + no-auth + idempotency. |
| `docs/` | **create (W9)** | operator docs. | LOW | doc-lint + copy-run. |
| `poc/adapter/` | **keep + classify** | legacy PoC; decide keep-ref/retire. | LOW | none (no runtime dependency). |
| `implementation/` | **keep** | D4 wave pack. | none | artifact-presence check. |
| `live-harness/`, `evals/`, `evidence/`, `research/`, `architecture/`, `implementation-plan/`, `test-design/` | **keep as-is** | eval/historical; never installed. | none | boundary check (no runtime import). |

## 5. Boundary invariant (enforced W1 + W8)

```
PRODUCTION (install-tree + installer + wrapper Skills)
    MUST NOT import  live-harness/*  or  evals/*
    MUST NOT reference any path under  evidence/  evals/  research/
EVAL / HISTORICAL
    MAY read production runtime (to exercise/grade it)
```

A CI job (Wave 8) greps the shipped surface for `import live-harness`,
`import evals`, and `evidence/`/`evals/` path literals and fails closed on
any hit.
