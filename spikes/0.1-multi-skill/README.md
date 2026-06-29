# Spike 0.1 — Multi-skill wrapper-resume

**Question:** Can a wrapper SKILL invoke a child SKILL via the Skill tool and reliably resume to run post-child steps?

**Verdict:** EXPERIMENT VERIFIED — yes (LLM-cooperative).

## How to reproduce

1. Copy `wrapper.SKILL.md` → `<project>/.claude/skills/zz-spike-wrapper/SKILL.md`
2. Copy `child.SKILL.md` → `<project>/.claude/skills/zz-spike-child/SKILL.md`
3. Copy `validator-stub.sh` → `/tmp/rdx-phase0/spike-0.1/validator-stub.sh` (`chmod +x`)
4. Open a fresh Claude Code session (or spawn a subagent)
5. Tell it: "Use the Skill tool to invoke `zz-spike-wrapper`. Follow its instructions exactly."
6. Observe `/tmp/rdx-phase0/spike-0.1/trace.log` — it should contain three lines in order: BEFORE → CHILD → AFTER

## Evidence

`trace.log.evidence` is the actual trace captured during the verification run:

```
BEFORE wrapper-step-1 ts=1782711396
CHILD child-step-1 ts=1782711404
AFTER wrapper-step-3 ts=1782711407
```

The 8-second gap (BEFORE→CHILD) is wrapper invoking child via Skill tool. The 3-second gap (CHILD→AFTER) is wrapper resuming and writing its own post-child marker.

## Critical nuance

Wrapper halts at Step 4 (validator exit 1) **only because the SKILL.md text says to halt**. The halt is convention-level, not technical enforcement. Production `rdx-dev-story` will rely on this convention for in-loop UX, with git hooks / CI providing the actual hard enforcement.
