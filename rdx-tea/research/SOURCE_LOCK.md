# SOURCE_LOCK — RDX + BMAD TEA integration research

**Status:** LOCKED  
**Document type:** Immutable source-of-truth record for this work window.  
**Governing prompt:** `RDX_TEA_variant_D_verification_and_implementation_plan_prompt.md` §2.2.

Nothing in `rdx-tea/` may claim provenance from RDX, BMAD Core, BMad Builder, or BMAD TEA without a matching row in one of the SHA/hash tables below (or a later, dated addendum to this file).

---

## 1. Working repository

| Field | Value |
|---|---|
| Upstream remote | `https://github.com/alfaRazieL/Rust_bmad_dev.git` |
| Clone parent directory | `/Users/m33tball/bmad_module_builder/rdx-workspace/` |
| Working tree path | `/Users/m33tball/bmad_module_builder/rdx-workspace/Rust_bmad_dev/` |
| Isolation mode | Fresh clone (not a `git worktree add`). Nothing outside this clone is touched by this task. |
| Working branch | `rdx-tea-integration` |
| Working branch base SHA (= `origin/main` at fetch time) | `d8140a25f8166bf0ca5ce5fc19f7cb1bd06a3d6d` |
| `main` HEAD SHA | `d8140a25f8166bf0ca5ce5fc19f7cb1bd06a3d6d` |
| `main` HEAD subject | `RDX 1.1 release: deterministic validator gate + Cat-3/4 layers` |
| `main` HEAD author | `alfaRazieL <alfaRazieL@users.noreply.github.com>` |
| `main` HEAD commit date | `2026-07-02T12:27:23+07:00` |
| `rdx-tea-integration` HEAD at lock time | `d8140a25f8166bf0ca5ce5fc19f7cb1bd06a3d6d` (branch created; no commits yet) |
| `git status --porcelain` at lock | `?? rdx-tea/` (only the new research directory is untracked) |
| Fetch date/time (UTC) | `2026-07-02T09:17:00Z` |
| Other local branches | `main` (unchanged, tracks `origin/main`) |
| Other remote branches | `origin/main`, `origin/rdx-improvements` (historical; not used as base per prompt §1) |

> The prompt (§1) reminded us not to treat any pre-recorded SHA as eternal. Both the value it recorded and the value we observed happen to coincide — the same commit `d8140a25…` was still the tip of `origin/main` at the time we ran `git fetch origin --prune`. Any subsequent addendum to this file must document a new fetch and a new SHA.

---

## 2. Sequence of Git operations performed to reach the locked state

Reproducible transcript (paths abbreviated for readability):

```
mkdir -p /Users/m33tball/bmad_module_builder/rdx-workspace
cd    /Users/m33tball/bmad_module_builder/rdx-workspace
git clone https://github.com/alfaRazieL/Rust_bmad_dev.git
cd Rust_bmad_dev
git status                 # clean, on main
git fetch origin --prune   # no updates
git branch -a              # confirmed no pre-existing rdx-tea* branch
git switch main
git pull --ff-only origin main   # already up to date
git switch -c rdx-tea-integration
mkdir -p rdx-tea/{research,architecture,poc/...,tests/...,fixtures/...,evals/...,evidence/...,test-design,implementation-plan/stages}
```

No `git reset --hard`, no stash, no force-checkout, no push, no rebase, no config change was performed. `main` remains untouched. The only file-system change under version control is the new (still untracked) `rdx-tea/` directory.

---

## 3. Environment

| Tool | Version | Location |
|---|---|---|
| macOS | 26.5.1 (build `25F80`) | `sw_vers` |
| Kernel | `Darwin 25.5.0 arm64` | `uname -a` |
| Shell | `zsh` (session default) | — |
| `git` | `2.51.1` | `/opt/homebrew/bin/git` |
| `python3` | `3.14.4` | `/opt/homebrew/bin/python3` |
| `pip` | `26.1` (site-packages `python3.14`) | `python3 -m pip` |
| `rustc` | `1.90.0 (1159e78c4 2025-09-14)` | rustup default toolchain |
| `cargo` | `1.90.0 (840b83a10 2025-07-30)` | `/Users/m33tball/.cargo/bin/cargo` |
| `node` | `v22.22.3` | `/opt/homebrew/opt/node@22/bin/node` |

BMAD/Builder/TEA CLI tooling versions and installation state are **NOT** yet recorded here. They will be locked separately in the Phase 1/2 documents (`BMAD_CORE_EXTENSION_SURFACE.md`, `BMAD_BUILDER_CONFIRMATION.md`, `BMAD_TEA_CONFIRMATION.md`) at the moment each of those tools is actually exercised, together with the exact SHA of the source repository from which the tool was installed. Recording a BMAD SHA here without having actually installed or invoked BMAD tooling would be a fabricated attestation.

---

## 4. Upstream (non-RDX) source SHAs

Per prompt §2.2 we must record BMAD/Builder/TEA SHAs. However, per prompt §3 ("Deterministic runtime proof" and "Real BMAD/TEA workflow proof"), only SHAs of repositories we have **actually inspected or executed** count as evidence. Recording a value we did not fetch would violate §5.8 and §19.

The following table therefore records only what was verified during Phase 0; other rows remain `PENDING` and will be filled by their owning phase before that phase's evidence is signed.

| Project | Source URL | SHA | How verified | Phase that will fill |
|---|---|---|---|---|
| RDX | `https://github.com/alfaRazieL/Rust_bmad_dev` | `d8140a25f8166bf0ca5ce5fc19f7cb1bd06a3d6d` | `git rev-parse origin/main` in local clone | Phase 0 (this file) |
| BMAD Method (core) | `https://github.com/bmad-code-org/BMAD-METHOD` (candidate — to be confirmed) | PENDING | To be captured at Phase 1 into `BMAD_CORE_EXTENSION_SURFACE.md` | Phase 1 |
| BMad Builder | `https://github.com/bmad-code-org/bmad-method-builder` (candidate — to be confirmed) | PENDING | To be captured at Phase 2 into `BMAD_BUILDER_CONFIRMATION.md` | Phase 2 |
| BMAD TEA | `https://github.com/bmad-code-org/bmad-method-test-architecture-enterprise` | PENDING | To be captured at Phase 2 into `BMAD_TEA_CONFIRMATION.md` | Phase 2 |

Phase-1/2 documents must both (a) confirm the correct upstream URL by dereferencing the docs referenced in prompt §4 and (b) record the observed HEAD SHA at the moment of inspection. If a Phase 2 review is not actually executed against a real installed copy of the tool, the row must remain `PENDING` and the verdict cannot be `PROVEN` (per prompt §9.3 last paragraph and §14 G1).

---

## 5. Hash manifest of authoritative RDX files

Full SHA-256 hashes of all files under `README.md`, `CHANGELOG.md`, `docs/`, `.claude/skills/`, `_bmad/`, `rdx-validator/`, `.github/` and `tests/` are stored — with cwd, generation time, and the git SHA they belong to — at:

```
rdx-tea/evidence/hashes/SOURCE_LOCK_files_sha256.txt
```

At lock time this manifest covered `179` hashed rows (files + section headers). Highlights below; the full list is authoritative:

| File | SHA-256 |
|---|---|
| `README.md` | `3977508f1e12375c68671667c407d61112c06b7e8d56428cd3fc6cfc5f977fb3` |
| `CHANGELOG.md` | `303a652668dcd497a3d9bed0131151bb6dc9d4d43513a38c6d6411e46a874ae2` |
| `docs/AGENT_MAINTENANCE_GUIDE.md` | `7bb90f7aba975c0d730ad87659c6375b8dc01eb87c368c267b04b653f69f5002` |
| `docs/threat-model.md` | `9d25579261e92370d75193cff1ce2b8be6a406719a8004bde1921c742f071b4f` |
| `docs/branch-protection.md` | `7d1a33b3ddf309cef997b204470c3cef5c21f3c2fd57a5776e66aa8585f4de16` |
| `.claude/skills/rdx-setup/SKILL.md` | `21960298854847ac536b8e4aab2916ee14c4098cdb31b32b47012840ae88f7eb` |
| `.claude/skills/rdx-dev-story/SKILL.md` | `626c348aa0eb92ecb7427e8a1bc2014cc8fbde5d1d12c78a1622da531ff71052` |
| `.claude/skills/rdx-code-review/SKILL.md` | `780a85436746ccbe8e035deab1edd345deae4cbca18224ab15e284e7f55eb528` |
| `.claude/skills/rdx-judgment/SKILL.md` | `8ee9041a8918f61c7688a0a28458bd14942f22022e096ad14b6f8a237909b686` |
| `.claude/skills/rdx-hooks/SKILL.md` | `aa20c1d4ad43e30f83d7f46fbd1d4de79655252b5254d6ea16c92a29e0b8258f` |
| `.claude/skills/rdx-setup/assets/modes.md` | `f5032cef2f0315858e5fe69b52b3471023684cd5802cb9cc25effd43159971f4` |
| `.claude/skills/rdx-setup/assets/module.yaml` | `8cfafdf07badda724932952dde5e0f53006fa79422a6aa4db1bb792064f7a6f6` |
| `.claude/skills/rdx-setup/assets/kb-sections/section-4-core.md` | `aa419c1a76551b8aa6248fad6a7f1cdafc8bcfeae7251e8f4fc4f3fa6a30c876` |
| `.claude/skills/rdx-setup/assets/kb-sections/section-5-router.md` | `579a890cc1065fbcca112a786ebda8e938869383338ef3755fea9671b65ee776` |
| `.claude/skills/rdx-setup/assets/kb-sections/section-6-packs.md` | `d4665fc9351164ce6744620a2c25c6e1c3ecb9fe0852307d164b4ddabaafa270` |
| `.claude/skills/rdx-setup/assets/kb-sections/section-8-governance.md` | `4d683f87054f940d9398bef4b86705063a721975adbe8a43caeb60c78981a07f` |
| `.github/workflows/rdx-gate.yml` | `ffbc53b9f7217f2563984cee4ae9a73b3c841f0fffe52c464cb305d6be5945f6` |
| `.github/workflows/rdx-full-regression.yml` | `d4387c1fc0faa4aaca101b73f19287fec6057538459e73a1d0cae74eed249e7d` |
| `.github/scripts/rdx-ci-runner.py` | `2070ed0eb80aad96e564bb0c1072d71eddffcb79b530ccfddb71aa1f60e75f98` |

Any subsequent projection generator, adapter, or PoC that claims to consume these files as "canonical" must reproduce these hashes byte-for-byte from a fresh checkout at SHA `d8140a25…`, or it is not consuming canonical RDX.

---

## 6. Test inventory at lock time

Enumeration of the RDX test tree:

| Layer | Directory | Test files (`test_*.py`) |
|---|---|---|
| L0 Contracts | `tests/contracts/` | 5 |
| L1 Unit (validator) | `tests/unit/validator/` | 9 |
| L3 Integration | `tests/integration/` | 2 |
| L4 BMAD integration | `tests/bmad/` | 6 |
| L4 Docs honesty | `tests/docs/` | 5 |
| L5 Behavioral evals | `tests/evals/` | 4 |
| L6 CI/hook | `tests/ci/` | 2 |
| L7 Mutation | `tests/mutation/` | 12 |
| L8 Acceptance | `tests/acceptance/` | 5 |
| L8 Compatibility | `tests/compatibility/` | 1 |
| **Total** | — | **51** discrete test files |

CHANGELOG claims a "307-test regression suite". The number of Python **files** is 51; the "307" figure therefore counts individual test functions and/or parametrized invocations, not files. This distinction is exactly the kind of test-inflation caveat that prompt §11.2 warns against, and it must be reproduced with pytest's `--collect-only` count in `CURRENT_RDX_1_1_BASELINE.md`.

---

## 7. Constraints imposed by this lock

While this document is in force:

1. No file under `.claude/skills/`, `_bmad/`, `rdx-validator/`, `docs/`, `.github/`, `README.md` or `CHANGELOG.md` may be modified as part of this task. Any change to those paths must be re-hashed and a new addendum written **before** the change is committed. This satisfies prompt §2.3 (no production RDX edits outside `rdx-tea/`).
2. No commit, push, or PR touching `main` is allowed.
3. `rdx-improvements` is treated as an archival branch and not used as a base (prompt §1).
4. All PoC code, generators, overlays, patches, and test fixtures created during this task live under `rdx-tea/` (prompt §2.3).
5. Every executed test/run under `rdx-tea/tests/` or `rdx-tea/evals/` must save its command line, cwd, env vars, git SHA, start/end time, exit code, stdout, stderr, and generated artifact hashes into `rdx-tea/evidence/` (prompt §20). A runner will be built for this in Phase 4 and the runner itself will be tested.
6. Secrets, `.env`, and Cargo `target/` outputs must never enter `rdx-tea/evidence/` (prompt §20 explicit exclusions).

---

## 8. How this lock is broken

The lock is broken deliberately, once, per work window, only if:

- A newer `origin/main` is pulled (record new fetch date, new SHA, `git status` and reason);
- A new authoritative RDX file appears or an existing one is modified upstream (regenerate the hash manifest);
- A BMAD/Builder/TEA SHA is verified and enters §4;
- The working branch changes name.

In every such case, append a dated addendum to §9 (see below). Do not silently overwrite §1–§7.

---

## 9. Addenda

*(none yet)*
