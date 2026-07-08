# Wave 0 — Plan Validation Evidence

**Wave:** W0 (plan validation & repository hygiene — NO production code)
**Date:** 2026-07-08
**Repo:** `rdx-workspace/Rust_bmad_dev`
**Branch:** `rdx-tea-integration`
**cwd for all commands:** repo root (`.../rdx-workspace/Rust_bmad_dev/`)
**START_HEAD == FINAL_HEAD (pre-commit):** `8b4ba3a53971f97b40cd997a77f019cf075c8ea8`
**Auth:** inherited OAuth session unchanged; `CLAUDE_CONFIG_DIR` not set/overridden; no API key / token / setup-token / apiKeyHelper used.

---

## 0. Git state (first action)

```
$ git fetch origin --prune
$ git rev-parse HEAD          -> 8b4ba3a53971f97b40cd997a77f019cf075c8ea8
$ git branch --show-current   -> rdx-tea-integration
$ git status --porcelain      -> ?? .agents/    (only untracked; acceptable)
```

Working tree clean within `rdx-tea/**` (only `.agents/` untracked). ✔

---

## 1. HEAD reconciliation (G-W0-HEAD)

The plan/spec docs literally assert Wave-0 `HEAD == 1cd5b11…`. That value is
**stale and self-contradictory**: Wave 0 validates the D4.0 planning pack,
which was itself committed *on top of* `1cd5b11`. A Wave-0 run therefore
necessarily executes at a HEAD that already contains the pack.

Proof (ancestry — `1cd5b11..HEAD`, 6 contiguous commits, all D4.0 planning):

```
$ git merge-base --is-ancestor 1cd5b11… HEAD  -> YES (1cd5b11 is ancestor of 8b4ba3a)
10fae61  rdx-tea: audit D4.0 master plan preconditions
c0e33fa  rdx-tea: add master implementation plan and wave index
79e8f69  rdx-tea: add production eval split and acceptance gates
5baa0d0  rdx-tea: add future wave prompt pack
f9b170e  rdx-tea: publish D4.0 master plan verification
8b4ba3a  rdx-tea: close D4.0 two-commit identity (fill evidence_commit_sha)  <- HEAD
```

- `1cd5b11` = D4 **pre-plan baseline** (D3.4.1 two-commit identity), correctly
  recorded by the HISTORICAL D4.0 audit and `evidence/final/…VERIFICATION.json`.
- `8b4ba3a` = D4.0 **plan-pack HEAD** = the true Wave-0 execution START.

Owner authoritatively confirmed expected `HEAD == 8b4ba3a…` in the wave prompt.
Actual `HEAD == 8b4ba3a…`, branch `rdx-tea-integration`.

**G-W0-HEAD: PASS** (against the reconciled/owner-authoritative START).
Doc drift recorded in §4 (recommended doc-sync — NOT edited in this wave, which
is scoped to `WAVE_INDEX.md` status + notes only).

---

## 2. Artifact-presence check (§10 / G-W0-TESTS) — 5 implementation artifacts + master plan, each > 500 chars

```
PASS   10465 chars  rdx-tea/implementation/ACCEPTANCE_GATES.md
PASS    7551 chars  rdx-tea/implementation/PRODUCTION_EVAL_SPLIT.md
PASS    6080 chars  rdx-tea/implementation/RISK_REGISTER.md
PASS    3749 chars  rdx-tea/implementation/WAVE_INDEX.md
PASS   17842 chars  rdx-tea/implementation/WAVE_PROMPTS.md
PASS   44158 chars  rdx-tea/MASTER_IMPLEMENTATION_PLAN.md
PRESENCE CHECK: OK (6/6 present, all > 500 chars)
```

## 2b. Cheap harness test (G-W0-TESTS)

```
$ rdx-tea/.venv-baseline/bin/python -m pytest rdx-tea/live-harness/tests/test_harness_v4.py -q
............................                                             [100%]
28 passed in 0.33s
```

(System `python3.14` has no `pytest`; used repo `.venv-baseline` (pytest 9.1.1).
`git status` identical before/after — no tracked source touched; `__pycache__`/
`.pytest_cache` are `.gitignore`d.)

**G-W0-TESTS: PASS** (presence OK; harness 28/28 green). *Non-blocking (planning).*

---

## 3. PRODUCTION_EVAL_SPLIT reconciliation vs disk (G-W0-SPLIT)

Compared `implementation/PRODUCTION_EVAL_SPLIT.md` §1 against
`find rdx-tea -maxdepth 2` and per-dir `git ls-files` counts.

| Top-level entry | Classified in split? | Class | Disk | Verdict |
|---|---|---|---|---|
| `poc/install-tree/**` | yes | PRODUCTION | present | ✔ |
| `poc/adapter` | yes | TO-MIGRATE | present | ✔ |
| `poc/projections` | yes | TO-MIGRATE | present | ✔ |
| `poc/overlays` `poc/patches` `poc/schemas` | yes | TO-RETIRE-LATER | 0/0/0 tracked | ✔ (empty as stated) |
| `live-harness` | yes | EVAL-ONLY | present | ✔ |
| `evals` | yes | EVAL-ONLY | 401 tracked | ✔ (split says 401) |
| `evidence` | yes | HISTORICAL | **101 tracked** | ⚠ split says 100 (+1) |
| `research` | yes | HISTORICAL | **33 tracked** | ⚠ split says 32 (+1) |
| `architecture` | yes | HISTORICAL(+1 prod mirror) | 9 tracked | ✔ |
| `implementation-plan` | yes | HISTORICAL | present | ✔ |
| `implementation` | yes | HISTORICAL (planning) | present | ✔ |
| `test-design` | yes | HISTORICAL | present | ✔ |
| `tests` | yes | TEST-ONLY | 14 tracked | ✔ (split says 14) |
| `fixtures` | yes | TEST-ONLY | 0 tracked | ✔ |
| `README.md`, `MASTER_IMPLEMENTATION_PLAN.md` | yes | HISTORICAL(docs) | present | ✔ |
| `.venv-baseline/` | yes | not tracked | untracked | ✔ |
| `.gitignore` | **no** | — | tracked | ⚠ omitted (non-runtime hygiene file) |

**Classification is correct.** Every runtime dir (`poc/install-tree/**`) is
classified PRODUCTION; no runtime dir is unlisted.

**G-W0-SPLIT: PASS** (pass criterion "every top dir classified; no unlisted
runtime dir" met). Benign count/coverage drifts noted below.

---

## 4. Drift register (recorded, not auto-fixed — for owner / doc-sync)

1. **Stale Wave-0 START SHA `1cd5b11` in plan/spec docs.** Operationally wrong
   ("verify HEAD == 1cd5b11" cannot hold once the plan is committed). Locations:
   - `implementation/ACCEPTANCE_GATES.md:25` (G-W0-HEAD pass criterion)
   - `implementation/WAVE_PROMPTS.md:52,73` (Wave-0 prompt)
   - `MASTER_IMPLEMENTATION_PLAN.md:405` (Wave-0 task)
   - `implementation/WAVE_INDEX.md:8,15` — **reconciled in this wave** (index is
     in Wave-0 change scope).
   Recommended: fix G-W0-HEAD criterion to `8b4ba3a…` (plan-pack HEAD) with
   `1cd5b11` retained as the pre-plan D3.4.1 baseline. HISTORICAL records
   (`research/D4_0_MASTER_PLAN_PRECONDITION_AUDIT.md`,
   `evidence/final/D4_0_MASTER_PLAN_FINAL_VERIFICATION.json`) are correct
   as-of-their-time and must NOT be rewritten.
2. **`evidence` count 100 → 101 (+1)** and **`research` count 32 → 33 (+1)** in
   split §1. Both caused by the D4.0 planning commits (`f9b170e`/`8b4ba3a`)
   adding the final-verification JSON + audit AFTER the split file (`79e8f69`)
   was written. Class unchanged (HISTORICAL). Cosmetic; refresh counts in W1.
3. **`.gitignore` not enumerated** in split §1. Tracked top-level file, purely
   ignore rules (`.venv-baseline/`, `__pycache__/`, `*.pyc`, `.pytest_cache/`);
   non-runtime. Add a one-line "config/hygiene" classification in W1.

---

## 5. Gate verdicts (from ACCEPTANCE_GATES.md)

| Gate | Verdict | Basis |
|---|---|---|
| **G-W0-HEAD** | **PASS** | HEAD `8b4ba3a` == owner-authoritative START; branch `rdx-tea-integration`; doc's `1cd5b11` reconciled as stale (see §1/§4). |
| **G-W0-SPLIT** | **PASS** | every top dir classified; no unlisted runtime dir; only benign count/`.gitignore` drift (§3/§4). |
| **G-W0-TESTS** | **PASS** (non-blocking) | presence 6/6 >500 chars; `test_harness_v4.py` 28/28 green. |
| **G-SCOPE** | **PASS** | changes confined to `rdx-tea/implementation/WAVE_INDEX.md` + `rdx-tea/evidence/logs/W0_VALIDATION.md`; `.agents/` untracked/never staged. |

STOP conditions (HEAD ≠ expected; split classification wrong): **none hit.**
