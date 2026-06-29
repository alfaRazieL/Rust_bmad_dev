# L4 — BMAD Workflow Integration Tests

Phase 3 + Phase 7 deliverable.

## Layout

```
bmad/
├── menu-override/      # T-L4-MENU-001/002 — scripted resolver merge tests
├── wrapper-resume/     # T-L4-WR-001..006 — wrapper-child-resume scenarios
├── setup-uninstall/    # T-L4-SETUP-001..003 — install lifecycle
└── code-review/        # T-L4-CR-001 (R2 wrapper) + T-L4-CR-002 (R1 control)
```

## Automation level

- **menu-override/**: fully scripted (driver calls `resolve_customization.py`, asserts on JSON output)
- **wrapper-resume/**: SEMI-automated — driver provisions skill SKILL.md files, then spawns subagent with prompt; subagent self-reports; driver inspects `trace.log`
- **setup-uninstall/**: scripted — driver runs `rdx-setup`/`rdx-uninstall`, asserts on filesystem state
- **code-review/**: SEMI-automated — same pattern as wrapper-resume but for `rdx-code-review`

## Conventions

- Skills created for tests are named with `zz-` prefix (Phase 0.1 convention) and CLEANED UP after each test run
- Cleanup is a hard requirement; leaving test skills in `.claude/skills/` pollutes the project
