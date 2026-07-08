# Acceptance Gates Matrix — RDX ↔ TEA Production Implementation

Every gate the D4 waves must satisfy. Columns: **Gate** · **Description**
· **Wave** · **Test command** · **Evidence path** · **Pass criteria** ·
**Blocking?**

Test commands run from the repo root
(`.../rdx-workspace/Rust_bmad_dev/`). Determinism, auth, split, and scope
gates are **cross-cutting** — re-checked by every wave that touches
runtime, and enforced in CI (Wave 8).

## Cross-cutting gates (apply to every runtime-touching wave)

| Gate | Description | Wave | Test command | Evidence path | Pass criteria | Blocking? |
|---|---|---|---|---|---|---|
| **G-AUTH** | No API key / OAuth token / setup-token / apiKeyHelper; `CLAUDE_CONFIG_DIR` never set or overridden by adapter/installer | W4,W7,all | `grep -rE "ANTHROPIC_API_KEY|CLAUDE_CODE_OAUTH_TOKEN|setup-token|apiKeyHelper|CLAUDE_CONFIG_DIR" rdx-tea/poc/install-tree rdx-tea/installer` | `evidence/auth-preflight/` | zero writes/overrides of auth env in shipped code | **YES** |
| **G-DET** | Generators byte-deterministic; golden hashes stable | W1,W2,W3 | run prepare twice, diff bundle bytes; compare to `evidence/hashes/` | `evidence/hashes/` | byte-identical across processes; golden hashes match | **YES** |
| **G-SPLIT-IMPORT** | Shipped surface imports no `live-harness`/`evals`; references no `evidence/`/`evals/` path | W1,W5,W8 | `grep -rE "import (live_harness|evals)|live-harness/|evals/|evidence/" rdx-tea/poc/install-tree rdx-tea/installer` | `ci-artifacts/boundary-report.txt` | zero hits | **YES** |
| **G-SCOPE** | Only `rdx-tea/**`, `rdx-validator/rdx_tea/**`, `.github/workflows/rdx-tea-*.yml` changed | all | `git diff --name-only origin/main..HEAD \| grep -Ev '^rdx-tea/\|^rdx-validator/rdx_tea/\|^\.github/workflows/rdx-tea-'` | CI `no-main-modifications` job | empty output | **YES** |

## Wave 0 — Plan validation

| Gate | Description | Wave | Test command | Evidence path | Pass criteria | Blocking? |
|---|---|---|---|---|---|---|
| **G-W0-HEAD** | HEAD/branch match expected START | W0 | `git rev-parse HEAD; git branch --show-current` | (log) | HEAD == `8b4ba3a…` (D4.0 plan-pack; `1cd5b11…` = historical pre-plan baseline), branch == `rdx-tea-integration` | **YES** |
| **G-W0-SPLIT** | PRODUCTION_EVAL_SPLIT matches disk | W0 | manual reconcile vs `find rdx-tea -maxdepth 2` | `implementation/PRODUCTION_EVAL_SPLIT.md` | every top dir classified; no unlisted runtime dir | **YES** |
| **G-W0-TESTS** | D4.0 artifact-presence + cheap harness test | W0 | presence check (§10 of the prompt) + `pytest rdx-tea/live-harness/tests/test_harness_v4.py -q` | `evidence/logs/` | presence check prints OK; harness test green | non-blocking (planning) |

## Wave 1 — Layout & boundaries

| Gate | Description | Wave | Test command | Evidence path | Pass criteria | Blocking? |
|---|---|---|---|---|---|---|
| **G-W1-VERSION** | `VERSION` == `sources.lock:adapter_version` | W1 | `diff <(cat rdx-tea/poc/install-tree/_bmad/rdx-tea/VERSION) <(grep adapter_version .../sources.lock)` | (log) | versions equal | **YES** |
| **G-W1-BOUNDARY** | Boundary/import test exists and passes | W1 | `pytest rdx-tea/tests/ -k boundary -q` | `ci-artifacts/boundary-report.txt` | new test green; G-SPLIT-IMPORT clean | **YES** |
| **G-W1-NOBEHAVIOUR** | No runtime behaviour change (golden hashes unchanged) | W1 | compare bundle golden hashes | `evidence/hashes/` | hashes byte-identical to pre-wave | **YES** |

## Wave 2 — KB & router

| Gate | Description | Wave | Test command | Evidence path | Pass criteria | Blocking? |
|---|---|---|---|---|---|---|
| **G-W2-PARITY** | Router = obligation-matrix ∩ router, exact set equality; no fork | W2 | `pytest rdx-tea/tests -k router_parity -q` | `evidence/logs/` | exact set equality on all fixtures | **YES** |
| **G-W2-FORBIDDEN** | Forbidden packs judged by ACTIVE packs, not prose; docs-only → no pack | W2 | `pytest rdx-tea/tests -k "forbidden or docs_only" -q` | `evidence/logs/` | docs-only activates `[]`; no prose-based activation | **YES** |
| **G-W2-CANON** | Canonical snapshot hash pinned | W2 | recompute canonical snapshot vs pin | `evidence/hashes/` | recomputed == pinned | **YES** |

## Wave 3 — Bundle builder

| Gate | Description | Wave | Test command | Evidence path | Pass criteria | Blocking? |
|---|---|---|---|---|---|---|
| **G-W3-DETERMINISM** | Bundle bytes identical across processes | W3 | run prepare in 2 processes; `sha256` compare | `evidence/hashes/` | identical sha256 | **YES** |
| **G-W3-IDENTITY** | Identity fail-closed (mandatory SHAs; reject all-zero; diff-digest agreement) | W3 | `pytest rdx-tea/tests -k identity -q` | `evidence/logs/` | prepare refuses missing/zero/mismatched identity | **YES** |
| **G-W3-SCHEMA** | Manifest + sidecar validate against `rdx-tea-run.v1` | W3 | `pytest rdx-tea/tests -k schema -q` | `evidence/logs/` | schema-valid; docs-only → empty bundle | **YES** |

## Wave 4 — Wrapper & lifecycle

| Gate | Description | Wave | Test command | Evidence path | Pass criteria | Blocking? |
|---|---|---|---|---|---|---|
| **G-W4-LIFECYCLE** | prepare-run → child → finalize-run end-to-end (deterministic slice) | W4 | `pytest rdx-tea/tests/bmad-tea -q` | `evidence/artifacts/` | slice green; run-report written | **YES** |
| **G-W4-SEQUENTIAL** | Non-`sequential` mode fails closed | W4 | `pytest rdx-tea/tests -k sequential -q` | `evidence/logs/` | wrapper HALTs on non-sequential | **YES** |
| **G-W4-NOTASK** | No Task/subagent dispatch; test-only flags stay env-gated | W4 | `pytest rdx-tea/tests/lifecycle -q`; grep SKILL.md for forbidden flags | `evidence/logs/` | Task 0; prod path never uses `--simulate-child`/`--test-write-fake-artefact` | **YES** |

## Wave 5 — Binder, sidecars, delta, consistency

| Gate | Description | Wave | Test command | Evidence path | Pass criteria | Blocking? |
|---|---|---|---|---|---|---|
| **G-W5-SIDECAR** | One sidecar per artefact (canonical output roots) | W5 | `pytest rdx-tea/tests -k "sidecar or dedupe" -q` | `evidence/artifacts/` | 1 sidecar/artefact; bundle-tamper fails closed | **YES** |
| **G-W5-DELTA** | Declared generated files verified; missing → fail | W5 | `pytest rdx-tea/tests -k delta -q` | `evidence/artifacts/` | declared-but-missing fails; delta preserved | **YES** |
| **G-W5-CONSISTENCY** | Phantom claims fail; duplicate frontmatter = warning | W5 | `pytest rdx-tea/tests -k consistency -q` | `evidence/logs/` | phantom fail; duplicate warn-not-fail; no `live-harness` import | **YES** |

## Wave 6 — Verifier & admission

| Gate | Description | Wave | Test command | Evidence path | Pass criteria | Blocking? |
|---|---|---|---|---|---|---|
| **G-W6-VERIFIER** | 9 checks each fail-close on a mutated input | W6 | `pytest rdx-tea/tests -k verifier -q` | `evidence/logs/` | mutating each hashed input flips exactly that check | **YES** |
| **G-W6-ADMISSION** | Admission recomputed from primitives; not from recorded flag | W6 | `pytest rdx-tea/tests -k admission -q` | `evidence/logs/` | dishonest bundle cannot self-admit | **YES** |
| **G-W6-FAILCLOSED** | Failed run never FINALIZED-admissible | W6 | `pytest rdx-tea/tests -k failclosed -q` | `evidence/logs/` | failed/partial run inadmissible | **YES** |

## Wave 7 — Installer & settings

| Gate | Description | Wave | Test command | Evidence path | Pass criteria | Blocking? |
|---|---|---|---|---|---|---|
| **G-W7-INSTALL** | install/update/uninstall smoke on temp dir | W7 | `pytest rdx-tea/tests/lifecycle -k install -q` | `evidence/logs/` | files placed/updated/removed correctly | **YES** |
| **G-W7-NOAUTH** | No auth material written/read; no `CLAUDE_CONFIG_DIR` override (see G-AUTH) | W7 | `pytest rdx-tea/tests/lifecycle -k noauth -q` | `evidence/auth-preflight/` | zero auth env touched | **YES** |
| **G-W7-IDEMPOTENT** | Re-install idempotent; `.user.toml` preserved | W7 | `pytest rdx-tea/tests/lifecycle -k idempot -q` | `evidence/logs/` | second install no-op; user content kept | **YES** |

## Wave 8 — CI & source-lock

| Gate | Description | Wave | Test command | Evidence path | Pass criteria | Blocking? |
|---|---|---|---|---|---|---|
| **G-W8-CI** | Branch CI green (guard-not-main + scope + boundary jobs) | W8 | GitHub Actions `rdx-tea-integration branch check` | `ci-artifacts/run-metadata.json` | conclusion `success` | **YES** |
| **G-W8-SOURCELOCK** | `bootstrap.py --verify-only` passes | W8 | `python rdx-tea/poc/install-tree/_bmad/rdx-tea/bootstrap/bootstrap.py --target-dir <upstream> --verify-only` | `ci-artifacts/source-lock-report.json` | status PASS; hashes verified | **YES** |
| **G-W8-NOSKIP** | No mandatory skips; unique count reported | W8 | `python rdx-tea/live-harness/ci_check.py refuse-skips <junit>` | `ci-artifacts/unique-count.json` | 0 skips; count reported | **YES** |

## Wave 9 — Docs

| Gate | Description | Wave | Test command | Evidence path | Pass criteria | Blocking? |
|---|---|---|---|---|---|---|
| **G-W9-DOCS** | Operator docs present & copy-runnable | W9 | doc-command copy-run check | `rdx-tea/docs/` | install/run/inspect commands succeed | **YES** |
| **G-W9-NOEVALFLAGS** | Operator docs never present eval/test-only flags as steps | W9 | `grep -rE "simulate-child|test-write-fake-artefact|allow-fixture-diff" rdx-tea/docs` | (log) | zero hits | **YES** |

## Wave 10 — E2E & release

| Gate | Description | Wave | Test command | Evidence path | Pass criteria | Blocking? |
|---|---|---|---|---|---|---|
| **G-W10-E2E** | Clean install + 1 bounded non-interactive smoke (NOT the pilot) | W10 | `pytest rdx-tea/tests/acceptance -q` (+ 1 authorized run) | `evidence/live/` | install clean; smoke admissible | **YES** |
| **G-W10-ROLLBACK** | Uninstall restores user content | W10 | `pytest rdx-tea/tests/acceptance -k rollback -q` | `evidence/logs/` | `.user.toml` restored; adapter files gone | **YES** |
| **G-W10-RELEASE** | D4 release-readiness verification committed; merge proposal ready | W10 | write `evidence/final/D4_RELEASE_READINESS.json` | `evidence/final/` | honest verification (no PENDING); merge awaits owner | **YES** |

## Gate accounting

- Cross-cutting: 4 (G-AUTH, G-DET, G-SPLIT-IMPORT, G-SCOPE).
- Per-wave: W0×3, W1×3, W2×3, W3×3, W4×3, W5×3, W6×3, W7×3, W8×3,
  W9×2, W10×3 = 32.
- **Total: 36 gates** (34 blocking, 2 non-blocking/planning).

Blocking gates must be PASS before the dependent wave starts. A gate that
cannot pass halts the wave with an honest status — never promoted to PASS.
