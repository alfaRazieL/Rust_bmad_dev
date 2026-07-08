# Pre-W2 Handoff Hygiene — evidence log

Mandatory hygiene step performed **before** any W2 KB/router work, in a
fresh CLI context. Doc-only + evidence; no runtime/generator change.

- Branch: `rdx-tea-integration` (never `main`).
- START_HEAD for this hygiene step: `b56e9e0c18be5583643327612744054516b7cf8e`
  (W1 FINAL_HEAD; owner-authoritative local chain, NOT `origin/rdx-tea-integration`).
- Working tree at entry: clean except untracked `.agents/`.
- No reset / rebase / pull / align-to-origin performed.

## 0. Handoff confirmation (required gate)

```
$ git branch --show-current      -> rdx-tea-integration
$ git rev-parse HEAD             -> b56e9e0c18be5583643327612744054516b7cf8e
$ git status --porcelain         -> ?? .agents/   (only untracked artefact)
$ git log --oneline -5
b56e9e0 rdx-tea: reconcile adapter version and pin production/eval boundary
bed1b30 rdx-tea: validate D4 plan and wave index
8b4ba3a rdx-tea: close D4.0 two-commit identity (fill evidence_commit_sha)
f9b170e rdx-tea: publish D4.0 master plan verification
5baa0d0 rdx-tea: add future wave prompt pack
```

HEAD == required `b56e9e0…`. Proceeded.

## 1. Stale wave-start SHA sync (planning docs only)

Canonical wording rule applied:

- Wave 0 expected start = D4.0 plan final head `8b4ba3a…`.
- Later waves expected start = previous wave FINAL_HEAD / owner-authoritative handoff SHA.
- Historical D4 pre-plan / D3.4.1 proof baseline = `1cd5b11…` (never a wave execution start).

Edited (planning/handoff files only; historical evidence/audit files untouched):

| File | Change |
|---|---|
| `implementation/ACCEPTANCE_GATES.md` | `G-W0-HEAD` pass-criteria `HEAD == 1cd5b11…` → `HEAD == 8b4ba3a…` (+ `1cd5b11…` relabelled historical pre-plan baseline). |
| `implementation/WAVE_PROMPTS.md` | Shared-preamble first-action + `WAVE_0_PROMPT` no longer say Wave 0/1 starts from `1cd5b11…`; Wave 0 → `8b4ba3a…`, later waves → previous FINAL_HEAD. |
| `MASTER_IMPLEMENTATION_PLAN.md` | Header + §6.2 proof-baseline block relabel `START of D4 = 1cd5b11` → pre-plan baseline `1cd5b11` (historical) **and** Wave-0 exec START `8b4ba3a`; Wave-0 task `verify HEAD == 1cd5b11…` → `8b4ba3a…`. |
| `implementation/WAVE_INDEX.md` | See §2. |

Verification — required stale-instruction grep returns **no active execution instruction**:

```
$ grep -RnE "HEAD == 1cd5b11|Wave 0/1.*1cd5b11|or 1cd5b11.*Wave 0" \
    rdx-tea/MASTER_IMPLEMENTATION_PLAN.md \
    rdx-tea/implementation/WAVE_PROMPTS.md \
    rdx-tea/implementation/ACCEPTANCE_GATES.md \
    rdx-tea/implementation/WAVE_INDEX.md
(exit 1 — no match)
```

All remaining `1cd5b11…` mentions are explicitly labelled "historical /
pre-plan / D3.4.1 proof baseline".

## 2. WAVE_INDEX owner checkpoint

- W0 = ☑ complete (unchanged).
- W1 = ☐ pending → **☑ complete** (FINAL_HEAD `b56e9e0`; all W1 gates PASS).
- W2 = ☐ pending (**left pending — not marked complete**).
- Added owner-authoritative handoff chain: W0 FINAL_HEAD `bed1b30`,
  W1 FINAL_HEAD / W2 required START `b56e9e0`, W2 starts from the pre-W2
  hygiene commit layered on `b56e9e0`.

## 3. PRODUCTION_EVAL_SPLIT drift refresh (as of `b56e9e0`)

- Counts made non-fragile ("~N as of `b56e9e0`"): evidence ~107 (was 100),
  research ~33 (was 32), tests ~15 (was 14), evals ~401 (unchanged).
- Classified new W0/W1 artefacts:
  - `evidence/logs/W0_VALIDATION.md`, `W1_VERIFICATION.md`,
    `W1_boundary-report.txt`, `W1_full_suite_GREEN.log` → HISTORICAL (evidence).
  - `evidence/hashes/w1_bundle_golden.{py,txt}` → HISTORICAL; eval/verification
    tooling — never shipped, never imported by runtime.
  - `tests/contracts/test_l0_boundary_split_import.py` → TEST-ONLY (executable G-SPLIT-IMPORT).
  - `poc/install-tree/README.md` → NON-SHIPPED (repo pointer).
  - `poc/adapter/**` → TO-MIGRATE **(keep-as-reference)**, W1 decision recorded.
- Classified hygiene files: `rdx-tea/.gitignore`, `evals/results/.gitignore`
  → NON-SHIPPED (repo hygiene); boundary-irrelevant.
- Production/eval boundary (§5) **unchanged**. Nothing deleted.

## 4. W1 `sources.lock` comment-only edit — validation (ACCEPTED)

Target: `poc/install-tree/_bmad/rdx-tea/bootstrap/sources.lock`.

Compared parsed (non-comment, non-blank) values across the W1 boundary
(`bed1b30` → `b56e9e0`):

```
$ diff <(git show bed1b30:$LOCK | grep -vE '^\s*#' | grep -vE '^\s*$') \
       <(git show b56e9e0:$LOCK | grep -vE '^\s*#' | grep -vE '^\s*$')
(no output — IDENTICAL_PARSED_VALUES)
```

- `rdx_source_sha`/`tag`, `bmad_source_sha`/`tag`, `tea_source_sha`/`tag`,
  `expected_file_hashes.*`, `adapter_version` → all **unchanged**.
- Source SHAs/tags for RDX/BMAD/TEA are byte-identical. `adapter_version`
  stayed `"0.3.2"` (the W1 version alignment was in the `VERSION` file, not here).
- The W1 edit is truly **comment-only / YAML-inert**: it reworded the
  "when bumping any SHA" comment to drop `evidence/`/`research/` path
  literals from the shipped surface.

**Accepted** because it enables a literal **zero-hit `G-SPLIT-IMPORT`**
boundary check (the shipped surface no longer names eval/audit paths even
in comments). No further `sources.lock` modification made.

## 5. Hygiene validation runs

Env: `rdx-tea/.venv-baseline/bin/python` (CPython 3.14.4, pytest 9.1.1);
cwd = repo root `.../rdx-workspace/Rust_bmad_dev`.

```
$ python -m pytest rdx-tea/tests/ -k boundary -q
11 passed, 126 deselected in 0.10s        (exit 0)

$ python -m pytest rdx-tea/tests -q
137 passed in 8.38s                        (exit 0)
```

Identical to the W1 baseline (11 boundary / 137 full). Hygiene edits are
documentation-only → no runtime/behaviour change, golden hashes untouched.

## 6. Result

Pre-W2 hygiene complete. Next: commit `rdx-tea: sync wave handoff docs
after W0 W1` — its SHA becomes the actual W2 START_HEAD.
