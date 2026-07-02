"""L4 menu-override tests — T-L4-MENU-001 and T-L4-MENU-002.

These tests verify the BMad `agent.menu` merge-by-`code` semantics that the
RDX wrapper depends on for menu integration. They use the resolver shim
(`tests/bmad/_helpers/resolver_shim.py`) which faithfully reproduces the
documented BMad merge contract.

Coverage:
- T-L4-MENU-001 — rdx-setup's `_bmad/custom/bmad-agent-dev.toml` reassigns
  the DS menu code to the rdx-dev-story wrapper while preserving other
  codes (QD / CR / RF) in base order.
- T-L4-MENU-002 — a pre-existing foreign user customization (XX code, plus
  a custom principle) is preserved when RDX adds its DS override on top.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.bmad._helpers.resolver_shim import resolve

HERE = Path(__file__).resolve().parent
BASE = HERE / "fixture-base" / "bmad-agent-dev.toml"
RDX_OVERRIDE = HERE / "fixture-replace-ds" / "bmad-agent-dev.toml"
FOREIGN_OVERRIDE = HERE / "fixture-foreign-preserved" / "bmad-agent-dev.toml"
REPO_ROOT = HERE.parent.parent.parent
RDX_INSTALLED_OVERRIDE = (
    REPO_ROOT
    / ".claude"
    / "skills"
    / "rdx-setup"
    / "assets"
    / "agent-overrides"
    / "bmad-agent-dev.toml"
)


def _menu_codes(menu: list[dict]) -> list[str]:
    return [entry.get("code") for entry in menu]


def test_t_l4_menu_001_ds_replaced_others_preserved():
    """T-L4-MENU-001 — DS reassigned to rdx-dev-story; QD/CR/RF preserved."""
    expected = json.loads((HERE / "fixture-replace-ds" / "expected.json").read_text())
    merged = resolve(BASE, RDX_OVERRIDE)
    menu = merged["menu"]

    # DS entry must now point to rdx-dev-story.
    ds_entries = [e for e in menu if e["code"] == "DS"]
    assert len(ds_entries) == 1, f"DS must appear exactly once, got {len(ds_entries)}"
    assert ds_entries[0]["skill"] == "rdx-dev-story"

    # Other base codes unchanged.
    assert _menu_codes(menu) == _menu_codes(expected["expected_menu"])
    for got, want in zip(menu, expected["expected_menu"], strict=True):
        assert got["code"] == want["code"]
        assert got["skill"] == want["skill"]


def test_t_l4_menu_002_foreign_customization_preserved():
    """T-L4-MENU-002 — foreign XX entry + custom principle survive RDX install.

    Models the resolver chain: base agent + user's existing custom override
    + RDX's override merged on top. Order: base entries first (DS replaced),
    foreign XX appended.
    """
    expected = json.loads(
        (HERE / "fixture-foreign-preserved" / "expected.json").read_text()
    )
    # First merge: base + foreign user customization.
    after_user = resolve(BASE, FOREIGN_OVERRIDE)
    assert "XX" in _menu_codes(after_user["menu"])
    assert any(
        expected["expected_principles_contain_substring"] in p
        for p in after_user["principles"]
    )

    # Second merge: RDX override applied on top of (base + user).
    # Order matters — RDX is the LAST override so its DS entry wins.
    from tests.bmad._helpers.resolver_shim import _load, _merge_menu, _merge_string_array

    rdx_doc = _load(RDX_OVERRIDE)
    rdx_agent = rdx_doc.get("agent", {})
    merged_menu = _merge_menu(after_user.get("menu", []), rdx_agent.get("menu", []))
    merged_principles = _merge_string_array(
        after_user.get("principles", []), rdx_agent.get("principles", [])
    )

    assert _menu_codes(merged_menu) == _menu_codes(expected["expected_menu"])
    # DS still points to RDX wrapper, not foreign or base.
    ds = next(e for e in merged_menu if e["code"] == "DS")
    assert ds["skill"] == "rdx-dev-story"
    # Foreign code XX is intact.
    xx = next(e for e in merged_menu if e["code"] == "XX")
    assert xx["skill"] == "user-custom-skill"
    # Foreign principle survives.
    assert any(
        expected["expected_principles_contain_substring"] in p for p in merged_principles
    )


def test_rdx_installed_override_declares_ds_to_rdx_dev_story():
    """The shipped RDX override template (.claude/skills/rdx-setup/assets/...)
    must declare an [[agent.menu]] block that points DS → rdx-dev-story.
    This is the file that rdx-setup actually copies into user projects.
    """
    assert RDX_INSTALLED_OVERRIDE.exists(), (
        f"RDX override template missing at {RDX_INSTALLED_OVERRIDE}"
    )
    merged = resolve(BASE, RDX_INSTALLED_OVERRIDE)
    menu = merged.get("menu", [])
    ds_entries = [e for e in menu if e.get("code") == "DS"]
    assert len(ds_entries) == 1, (
        "RDX-installed override must declare exactly one DS menu entry"
    )
    assert ds_entries[0]["skill"] == "rdx-dev-story"


@pytest.mark.parametrize("missing_code", ["QD", "CR", "RF"])
def test_t_l4_menu_001_non_ds_codes_unchanged(missing_code: str):
    """Regression: non-DS base codes must keep their original skill mappings."""
    merged = resolve(BASE, RDX_OVERRIDE)
    matches = [e for e in merged["menu"] if e["code"] == missing_code]
    assert len(matches) == 1
    assert matches[0]["skill"].startswith("bmad-"), (
        f"Code {missing_code} must keep its base bmad-* skill mapping"
    )
