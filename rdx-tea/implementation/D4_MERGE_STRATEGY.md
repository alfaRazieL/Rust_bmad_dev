# D4 v1 — Proposed Merge Strategy (owner approval required)

**Status:** PROPOSED — not executed. This document does **not** authorize a
merge. No PR is opened, no branch is manipulated, `main` is untouched. The
owner must **explicitly** authorize any merge/PR in a later step.

Scope: promote the **proven** sequential wrapper-driven RDX→TEA lifecycle
(D3.4.1 `D3_RULE_OPERATION_PROVEN`), productionized across Waves 0–10, from
`rdx-tea-integration` into `main`. This is the **knowledge/packaging plane
only**. The enforcement plane stays deferred backlog (see §5).

---

## 1. Preconditions (all currently met on `rdx-tea-integration`)

Verified by the W10 acceptance ladder (`evidence/logs/W10/ACCEPTANCE_LADDER.json`)
and release-readiness verification (`evidence/final/D4_RELEASE_READINESS.json`):

- All D4 **blocking** acceptance gates PASS (`implementation/ACCEPTANCE_GATES.md`).
- Full `rdx-tea/tests` suite green (**363 passed, 0 failed, 0 skipped**).
- Deterministic ladder rungs 1–5 green before any smoke; the single bounded
  non-interactive E2E smoke is **admissible** (`evidence/live/W10_E2E_SMOKE.json`).
- Golden hashes stable (W2 canonical pin, W3 bundle golden) — no generator drift.
- G-AUTH: no auth material / no `CLAUDE_CONFIG_DIR` in the shipped surface.
- G-SPLIT-IMPORT: shipped surface imports no `live-harness`/`evals`, references
  no `evidence/`/`evals/` path.
- G-SCOPE: every changed path is under `rdx-tea/**` (this wave changed nothing
  in `rdx-validator/rdx_tea/**` or `.github/workflows/rdx-tea-*.yml`).
- The GitHub Actions `rdx-tea-integration branch check` is green on push
  (guard-not-main, source-lock `--verify-only`, canonical suite, boundary,
  auth, golden-hash, installer-surface, unique-count, no mandatory skips).

Merge is gated on the **owner** confirming these from the evidence and the
branch CI conclusion.

## 2. What merges (shipped surface only)

```
rdx-tea/poc/install-tree/_bmad/rdx-tea/{canonical,scripts,bootstrap,VERSION}
rdx-tea/poc/install-tree/.claude/skills/rdx-tea-{test-design,atdd}/SKILL.md
rdx-tea/installer/project_installer.py
rdx-tea/docs/**                      (operator docs)
.github/workflows/rdx-tea-integration-check.yml
```

Historical/eval/test planes (`evidence/**`, `research/**`, `evals/**`,
`live-harness/**`, `tests/**`, `implementation*/**`, `architecture/**`) travel
with the branch as project record but are **not** production runtime and are
covered by the boundary invariant.

## 3. Proposed mechanics (owner runs; recommended path first)

**Recommended — `--no-ff` merge preserving wave history:**

```bash
# OWNER-ONLY, after explicit authorization:
git switch main
git pull --ff-only origin main
git merge --no-ff rdx-tea-integration \
    -m "Merge D4 v1: productionize RDX->TEA sequential wrapper lifecycle"
# Re-run the full suite on the merge commit before pushing:
rdx-tea/.venv-baseline/bin/python -m pytest rdx-tea/tests -q   # expect 363 passed
git push origin main
```

Rationale: the wave-by-wave history (W0…W10 + owner checkpoints) is an audit
asset; `--no-ff` keeps it and records a single integrating commit on `main`.

**Alternative — curated squash:** if the owner prefers a single `main` commit,
squash `rdx-tea-integration` into one commit whose message references the D4
release-readiness SHA. Trade-off: loses per-wave granularity; keep the branch
un-deleted so the detailed history survives.

Either way: **no force-push**, **no rebasing `main`**, and the branch is not
deleted until the owner is satisfied.

## 4. Post-merge verification & rollback

- Post-merge: re-run `rdx-tea/tests` on the merge commit (expect 363 passed);
  confirm the `main` CI run is green.
- Rollback: because the merge is `--no-ff`, a single `git revert -m 1 <merge-sha>`
  cleanly removes the adapter from `main` without touching history. The project
  installer's `uninstall` independently reverses a *project* install
  (adapter files removed, `.user.toml` and user content preserved — proven by
  `tests/acceptance` rollback gate G-W10-ROLLBACK).

## 5. Explicitly NOT in this merge (deferred backlog)

- `rdx-tea-validate` enforcement verdict in `rdx-validator/rdx_tea/**` (STAGE-08).
- Modes `MODE_0..4` / hooks / `rdx-tea-gate.yml` required check / Cat-4 approval
  (STAGE-09).
- Subagent / agent-team worker propagation (`G6F`); sequential-only is the
  proven v1.
- **G7** behavioural benefit vs baseline — out of scope, **not claimed**.

The older `implementation-plan/FINAL_ACCEPTANCE_CHECKLIST.md` (G0–G11) is the
pre-D4 proof checklist; for D4 v1 the authoritative gate set is
`implementation/ACCEPTANCE_GATES.md`. Its G4 (safe lifecycle) is now covered by
W7 + W10; G5–G7 remain deferred/out-of-scope as above.

## 6. Authorization

This strategy is inert until the owner replies with explicit merge
authorization (naming the mechanics chosen in §3). Until then the assistant
performs **no** merge, **no** PR, and **no** branch manipulation on `main`.
