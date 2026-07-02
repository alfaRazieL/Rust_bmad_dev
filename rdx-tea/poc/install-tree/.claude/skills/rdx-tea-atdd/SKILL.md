---
name: rdx-tea-atdd
description: RDX wrapper for the BMad TEA `bmad-testarch-atdd` workflow. Runs the D3.2 two-phase orchestration — deterministic prepare (active-context bundle, sequential-mode assertion), invokes the original bmad-testarch-atdd child skill, then deterministic finalize/bind/verify. Mirrors the rdx-dev-story pattern; direct TEA invocation without this wrapper is UNVALIDATED.
---

# rdx-tea-atdd — Wrapper for BMad TEA `bmad-testarch-atdd`

You are the RDX-TEA wrapper for TEA's `bmad-testarch-atdd` workflow.

## Contract

Identical to `rdx-tea-test-design` (see that SKILL.md) with `--workflow atdd` and `--skill-dir …/bmad-testarch-atdd`. ATDD normally uses subagent orchestration; the wrapper collapses it to `sequential` by asserting `tea_execution_mode: sequential` in `_bmad/tea/config.yaml`. If ATDD's runtime probe suggests otherwise, HALT.

## Activation

Follow the seven steps in `rdx-tea-test-design/SKILL.md`, substituting:

- Workflow: `atdd`
- Skill dir: `{project-root}/.claude/skills/bmad-testarch-atdd`
- Run-id prefix: `atdd-YYYYMMDD-HHMMSS`

## Sequential-only guard

D3.2 rejects `auto` mode for ATDD explicitly because ATDD's step-c files include subagent-payload construction (`bmad-testarch-atdd/steps-c/step-04-generate-tests.md:56-83`). The wrapper's assertion is: the resolved `tea_execution_mode` MUST be the literal `sequential`.
