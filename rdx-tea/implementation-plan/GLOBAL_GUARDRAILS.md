# GLOBAL_GUARDRAILS

Rules every stage MUST obey.

## Repository

- Working branch: `rdx-tea-integration`. Never touch `main`.
- Never `git reset --hard`, `git push --force`, or open a PR.
- Never modify files outside `rdx-tea/` or `rdx-validator/rdx_tea/`.
- Never edit `.claude/skills/**` (RDX) or the host's
  `.claude/skills/**` (BMAD/TEA).
- Never edit `_bmad/custom/**` in the RDX repo (those are user
  artefacts; the adapter writes to the *host* project when installed).

## Test discipline

- Write failing test first, save RED log, then implement, save GREEN log.
- Every executed run saves: command, cwd, env, git SHA, start/end,
  exit code, stdout, stderr, artefact hashes — under
  `rdx-tea/evidence/`.
- Never delete a failing test to bypass its assertion. If the test is
  wrong, replace it with a corrected failing test first.
- Never conflate `pytest node count` with `unique test intent count`
  (prompt §11.2).

## Verdicts

- Never promote `NOT_RUN`, `BLOCKED`, or `INCONCLUSIVE` to `PASS`.
- Never emit a numeric quality score without a measurement rubric that
  was fixed before the run.
- `PROVEN` is only permitted when every G-gate G0..G11 is `PASS`.

## Knowledge-plane-first

- Do not attempt G8..G11 while any of G2..G7 is not `PASS`.
- Enforcement-plane changes are irrelevant if the knowledge plane they
  claim to enforce isn't proven yet.

## Determinism

- Projection generator: no wallclock, no random, sorted iteration.
- Byte-identical output across identical inputs.
- Any change to generator behaviour requires a new golden-hash pin in
  `evidence/hashes/`.

## Secrets

- Never include credentials, tokens, `.env`, huge caches, `target/`,
  dependencies, or sensitive host data in `evidence/` (prompt §20).
