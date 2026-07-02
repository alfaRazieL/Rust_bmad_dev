"""Shared helpers for L4 BMAD-integration tests (Phase 3).

Modules:
- resolver_shim: emulates `_bmad/scripts/resolve_customization.py` merge semantics
  for the subset RDX relies on (arrays append; `[[agent.menu]]` merges by `code`).
- skill_parser: minimal SKILL.md front-matter + step extractor used by
  wrapper-resume static checks.
"""
