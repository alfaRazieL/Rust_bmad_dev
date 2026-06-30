"""Phase 4 — T-L5-MODE-001 smoke (deterministic structural part).

The full T-L5-MODE-001 is a statistical L5 behavioral eval scheduled for
Phase 6 (≥ 95% over 20 runs that an agent answers "what mode is RDX in?"
correctly for Mode 1).

Phase 4 owns the *deterministic* prerequisite: the documentation and the
validator output must NAME Mode 1 with a non-enforcement label. If the
SKILL.md prose itself says "Mode 1 — Enforced", no behavioral eval will
ever recover. So we lock the structural contract first; the runtime eval
runs in Phase 6.

This is the smoke half explicitly called out in the Phase 4 exit gate:
  T-L5-MODE-001 (agent names mode correctly) passes (smoke; full in Phase 6)
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
RDX_SETUP_SKILL = REPO_ROOT / ".claude" / "skills" / "rdx-setup" / "SKILL.md"
RDX_SETUP_ASSET = REPO_ROOT / ".claude" / "skills" / "rdx-setup" / "assets" / "modes.md"
MODULE_YAML = REPO_ROOT / ".claude" / "skills" / "rdx-setup" / "assets" / "module.yaml"

# Canonical labels per Phase 4 plan + RDX_TEST_STRATEGY.md §5 mode → label
# mapping. Mode 1 MUST NOT use "Enforced" (T-L5-MODE-001).
EXPECTED_MODE_LABELS = {
    "MODE_0": "Advisory",
    "MODE_1": "Local Validated",
    "MODE_2": "Local Gated",
    "MODE_3": "CI Enforced",
    "MODE_4": "Specialist Approval",
}


def _read_modes_doc() -> str:
    """The mode documentation lives in a dedicated asset so module-setup.md
    can include it and the SKILL.md prose can reference it. Phase 4 will
    create the file."""
    assert RDX_SETUP_ASSET.exists(), (
        f"Phase 4 must ship a modes reference at {RDX_SETUP_ASSET}"
    )
    return RDX_SETUP_ASSET.read_text(encoding="utf-8")


def test_modes_doc_names_every_mode():
    text = _read_modes_doc()
    for mode_id, label in EXPECTED_MODE_LABELS.items():
        assert mode_id in text, f"modes doc must mention {mode_id}"
        assert label in text, f"modes doc must use canonical label {label!r} for {mode_id}"


def test_mode_1_never_called_enforced():
    """The single most important T-L5-MODE-001 invariant: the Mode 1 section
    must NOT call itself 'Enforced'.

    We grep the line that introduces MODE_1 (or 'Mode 1') and assert the
    label on that line is 'Local Validated' (the canonical), or some clearly
    cooperative/soft-gate descriptor — never 'Enforced'."""
    text = _read_modes_doc().lower()
    # Walk every line that mentions mode 1 / MODE_1 and assert no "enforced".
    for line in text.splitlines():
        if "mode 1" in line or "mode_1" in line:
            assert "enforced" not in line, (
                f"Mode 1 line uses forbidden 'enforced' label: {line.strip()!r}"
            )


def test_module_yaml_offers_mode_choice():
    """The interactive mode selector lives in module.yaml as a single-select
    variable named `enforcement_level`. The selector exposes at least the
    four modes Phase 4 supports (MODE_0..MODE_3); MODE_4 is permitted but
    not required since its full wiring is Phase 8."""
    import yaml

    doc = yaml.safe_load(MODULE_YAML.read_text(encoding="utf-8"))
    var = doc.get("enforcement_level")
    assert isinstance(var, dict), "module.yaml must define enforcement_level variable"
    choices = var.get("single-select")
    assert isinstance(choices, list) and choices, (
        "enforcement_level must be a single-select with at least one option"
    )
    values = {c.get("value") for c in choices if isinstance(c, dict)}
    for required in ("MODE_0", "MODE_1", "MODE_2", "MODE_3"):
        assert required in values, f"enforcement_level must offer {required}"


def test_module_yaml_default_is_mode_1():
    """The default selection must be MODE_1 — matches install.py default
    (see test_mode_selector.test_install_default_is_mode_1_local_validated)."""
    import yaml

    doc = yaml.safe_load(MODULE_YAML.read_text(encoding="utf-8"))
    var = doc.get("enforcement_level", {})
    assert var.get("default") == "MODE_1", (
        f"enforcement_level default must be MODE_1; got {var.get('default')!r}"
    )
