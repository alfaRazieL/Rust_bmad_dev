"""Resolver shim — emulates the BMAD `_bmad/scripts/resolve_customization.py`
merge semantics for the keys RDX touches.

The real resolver lives in the user's project under `_bmad/scripts/`. This
shim implements the documented subset so Phase 3 menu-override tests are
fully deterministic and runnable in CI without requiring a user environment.

Merge rules (matching the BMAD documented contract — see
`RDX_VALIDATOR_ARCHITECTURE_VERIFICATION.md` §6 "agent.menu merge-by-code"):

1. `[agent]` scalar keys (description, etc.) → custom overrides base.
2. `agent.persistent_facts` (array of strings) → custom appended after base
   (deduplicated, preserving first-seen order).
3. `agent.principles` (array of strings) → custom appended after base
   (deduplicated, preserving first-seen order).
4. `[[agent.menu]]` (array of tables) → merge by `code` field:
   - if a custom entry has the same `code` as a base entry, the custom
     entry REPLACES the base entry in-place;
   - if the `code` is new, the custom entry is APPENDED;
   - order of base entries is preserved.

This shim is intentionally narrow — it does NOT attempt to be a general
TOML merge engine.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:  # pragma: no cover - we require 3.11+
    import tomli as tomllib  # type: ignore[no-redef]


def _load(path: Path) -> dict[str, Any]:
    with path.open("rb") as fh:
        return tomllib.load(fh)


def _merge_string_array(base: list[str], custom: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in list(base) + list(custom):
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def _merge_menu(base: list[dict], custom: list[dict]) -> list[dict]:
    by_code: dict[str, dict] = {}
    order: list[str] = []
    for entry in base:
        code = entry.get("code")
        if code is None:
            continue
        if code not in by_code:
            order.append(code)
        by_code[code] = dict(entry)
    for entry in custom:
        code = entry.get("code")
        if code is None:
            continue
        if code not in by_code:
            order.append(code)
        by_code[code] = dict(entry)
    return [by_code[c] for c in order]


def resolve(base_path: Path, custom_path: Path | None) -> dict[str, Any]:
    """Resolve a base agent TOML against an optional custom override.

    Returns the merged `agent` table as a dict.
    """
    base_doc = _load(base_path)
    base_agent = dict(base_doc.get("agent", {}))

    if custom_path is None or not custom_path.exists():
        return base_agent

    custom_doc = _load(custom_path)
    custom_agent = dict(custom_doc.get("agent", {}))

    merged = dict(base_agent)
    for key, custom_val in custom_agent.items():
        base_val = base_agent.get(key)
        if key == "menu" and isinstance(base_val, list) and isinstance(custom_val, list):
            merged[key] = _merge_menu(base_val, custom_val)
        elif key in {"persistent_facts", "principles"} and isinstance(base_val, list) and isinstance(custom_val, list):
            merged[key] = _merge_string_array(base_val, custom_val)
        else:
            merged[key] = custom_val
    return merged
