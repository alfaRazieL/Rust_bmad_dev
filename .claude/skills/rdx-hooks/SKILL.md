---
name: rdx-hooks
description: Install / uninstall the RDX pre-push git hook so local `git push` runs the standalone rdx-validator and refuses pushes that fail Mode 2 / Mode 3 gates. Opt-in (the hook is not installed by `rdx-setup` automatically); deterministic; chains with any pre-existing pre-push hook; the documented `git push --no-verify` bypass remains available and is recorded in evidence so auditors can see when it was used.
---

# RDX pre-push hook — local gate (Phase 5)

This skill installs the opt-in pre-push hook that makes Mode 2 ("Local
Gated") and Mode 3 ("CI Enforced") meaningful at the developer
machine. CI is still the source of truth (per
`RDX_TEST_STRATEGY.md` §7), but the hook is what gives the developer
fast feedback before they push.

**Soft-gate disclaimer.** This hook can be bypassed with
`git push --no-verify`. That is by design — see §5.3 of the test
strategy. The bypass is observable: a sentinel file is left under
`.git/hooks/.rdx-bypass.log` so subsequent CI runs can flag bypassed
pushes. The hook **is not** "hard enforcement". Hard enforcement
lives in the CI required check + branch protection (Phase 5.2).

## Install

```
python .claude/skills/rdx-hooks/scripts/install-hook.py --project-root <PATH>
```

Effects:

1. Creates `<project>/.git/hooks/pre-push` if missing, or wraps a
   pre-existing hook (the original is preserved at
   `pre-push.user.rdx-backup`).
2. The installed hook is a small shell script that:
   - locates the rdx-validator (via `RDX_VALIDATOR` env var if set,
     otherwise looks under `<project>/rdx-validator/` for a local
     check-out, or falls back to `python -m rdx_validator` if
     installed).
   - reads the pushed ref's diff (`git diff <base>..<head>`) and pipes
     it into the validator.
   - chains the user's pre-existing pre-push hook (if any) AFTER the
     RDX hook, so both run.
   - exits non-zero if validator exits 1 or 3.

## Uninstall

```
python .claude/skills/rdx-hooks/scripts/uninstall-hook.py --project-root <PATH>
```

Restores `.git/hooks/pre-push.user.rdx-backup` to `pre-push` (if it
existed), or removes the RDX hook entirely (if no user hook was
present at install time).

## Idempotency

Re-running install does not duplicate the chain wrapper. Re-running
uninstall on a clean state is a no-op (exit 0).

## What this skill does NOT do

- It does not guarantee that every developer has the hook installed.
  That is impossible at the git-hook layer — branch protection +
  required CI check (`.github/workflows/rdx-gate.yml`) is the actual
  enforcement floor.
- It does not block `--no-verify`. That bypass is documented and
  recorded but not prevented.
- It does not run Cat-3 evaluators (those need an LLM round-trip; CI
  handles them).
