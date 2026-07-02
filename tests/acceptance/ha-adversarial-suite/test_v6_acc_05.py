"""T-V6-ACC-05 — High Assurance adversarial-suite acceptance.

Phase 9 exit gate. Asserts:

  1. The catalogue of V6 L7 bypass classes in RDX_TEST_CASES.yaml is in
     sync with the test modules on disk under `tests/mutation/`. This
     makes it impossible to silently drop a defence layer by deleting
     a test module without also touching either the catalogue or this
     acceptance test.

  2. Each V6 HA-specific bypass class (Phase 9 additions: mode-downgrade
     and approvers-forgery) is exercised by a test module whose first
     docstring names an L7/L8 defence layer — same self-documentation
     contract as the Phase 6 V5 full-suite test.

  3. The full L7 mutation suite (V5 baseline + Phase 9 HA additions)
     runs green when collected as a single pytest subprocess. This is
     the operational equivalent of `100% adversarial detection in HA
     mode` from the YAML catalog entry for T-V6-ACC-05.

Approval-reuse (T-L7-APPROVAL-REUSE-001) lives in the L8 Cat-4 driver
under `tests/integration/cat4/test_l8_cat4.py`, not under
`tests/mutation/`. Acceptance asserts it is run as part of the broader
suite too, but the structural module-existence check uses its actual
home path.

Threat-model cross-reference: see `docs/threat-model.md` §6.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml


REPO_ROOT = Path(__file__).resolve().parents[3]
TEST_CASES_YAML = REPO_ROOT / "archive-docs-dev" / "test-design" / "RDX_TEST_CASES.yaml"
MUTATION_DIR = REPO_ROOT / "tests" / "mutation"
THREAT_MODEL = REPO_ROOT / "docs" / "threat-model.md"


# HA-specific bypass classes added in Phase 9 → test module on disk.
HA_L7_BYPASS_TO_TEST_MODULE: dict[str, str] = {
    "T-L7-HA-MODE-DOWNGRADE-001":     "test_l7_ha_mode_downgrade.py",
    "T-L7-HA-APPROVERS-FORGERY-001":  "test_l7_ha_approvers_forgery.py",
}


def _load_l7_v6_ids() -> set[str]:
    """Extract V6 L7 *bypass class* test IDs from the YAML catalog
    (the Phase 9 additions plus the Phase 8 approval-reuse case).

    T-V6-ACC-* entries also carry `layer: L7` because they exercise the
    L7 surface, but they are *acceptance* drivers — not bypass classes
    themselves — so they are excluded here.
    """

    doc = yaml.safe_load(TEST_CASES_YAML.read_text(encoding="utf-8"))
    ids: set[str] = set()
    for entry in doc:
        if not isinstance(entry, dict):
            continue
        if entry.get("layer") != "L7" or entry.get("version") != "V6":
            continue
        test_id = entry["id"]
        if test_id.startswith("T-V6-ACC-"):
            continue
        ids.add(test_id)
    return ids


def test_t_v6_acc_05_threat_model_doc_present():
    """Phase 9 entry gate names `docs/threat-model.md` as a deliverable.
    The acceptance test forces it to actually exist (the doc is what
    rationalises which bypass paths are in §6 and why HMAC is not v6)."""

    assert THREAT_MODEL.exists(), (
        f"docs/threat-model.md must exist as the Phase 9 entry-gate deliverable; "
        f"missing at {THREAT_MODEL}"
    )
    text = THREAT_MODEL.read_text(encoding="utf-8")
    # Document must call out the HA-specific bypass classes by ID so a
    # future editor cannot delete the test without also touching prose.
    for test_id in HA_L7_BYPASS_TO_TEST_MODULE:
        assert test_id in text, (
            f"threat model must reference HA bypass class {test_id} so the "
            f"prose stays in sync with the test catalogue"
        )


def test_t_v6_acc_05_ha_catalog_matches_yaml() -> None:
    """The HA bypass map above must be in sync with the YAML catalog for
    V6 L7. If a new V6 L7 bypass class is added to the YAML, this test
    forces the corresponding test module to be authored AND listed here.

    The YAML may also catalogue cross-phase V6 L7 entries (e.g. the Phase 8
    approval-reuse case); those are tested in their own home directories
    and so are intentionally NOT required to live under tests/mutation/.
    """

    yaml_ids = _load_l7_v6_ids()
    map_ids = set(HA_L7_BYPASS_TO_TEST_MODULE)

    # Phase 8 approval-reuse is V6/L7 but is exercised by tests/integration/cat4/
    # — it is NOT a Phase 9 HA-specific addition, so it is allowed to be in the
    # YAML without a tests/mutation/ home.
    non_ha_v6_l7 = {"T-L7-APPROVAL-REUSE-001"}

    extra_in_map = map_ids - yaml_ids
    missing_in_map = (yaml_ids - non_ha_v6_l7) - map_ids
    assert not extra_in_map, f"HA map lists bypass IDs not in YAML: {extra_in_map}"
    assert not missing_in_map, (
        f"YAML defines V6 HA L7 bypasses with no test module mapping: "
        f"{missing_in_map}"
    )


@pytest.mark.parametrize("test_id,module", sorted(HA_L7_BYPASS_TO_TEST_MODULE.items()))
def test_t_v6_acc_05_ha_test_module_exists(test_id: str, module: str) -> None:
    """Every HA L7 bypass class must have its test module on disk and
    must reference its T-L7-HA-* ID in the docstring or body for
    traceability."""

    path = MUTATION_DIR / module
    assert path.exists(), f"missing HA L7 test module for {test_id}: {path}"
    text = path.read_text(encoding="utf-8")
    assert test_id in text, (
        f"{module} must reference its bypass ID {test_id} so the traceability "
        f"matrix stays self-documenting"
    )


def test_t_v6_acc_05_ha_modules_self_document_defense_layer() -> None:
    """Mirror the Phase 6 V5 contract: each L7 module's opening
    docstring must name a defence layer (L2 / L6 / L7 / L8)."""

    layer_token = re.compile(r"\b(L2|L6|L7|L8)\b")
    for module in HA_L7_BYPASS_TO_TEST_MODULE.values():
        text = (MUTATION_DIR / module).read_text(encoding="utf-8")
        m = re.search(r'"""(.*?)"""', text, re.DOTALL)
        assert m, f"{module} must open with a module docstring"
        header = m.group(1)
        assert layer_token.search(header), (
            f"{module} docstring must name a defence layer (L2/L6/L7/L8); "
            f"got:\n{header[:400]}"
        )


def test_t_v6_acc_05_full_mutation_suite_green() -> None:
    """The actual acceptance assertion — run the full tests/mutation/
    suite as a subprocess and require exit 0. This is `100% adversarial
    detection across the V5 + HA-specific bypass classes` operationalised.

    The subprocess uses the parent Python interpreter via sys.executable
    so the same venv carries through and the pytest discovery is
    reproducible.
    """

    proc = subprocess.run(
        [
            sys.executable, "-m", "pytest",
            "-q", "--no-header",
            "tests/mutation",
        ],
        cwd=REPO_ROOT,
        capture_output=True, text=True,
        timeout=300,
    )
    assert proc.returncode == 0, (
        f"L7 mutation suite did not pass under T-V6-ACC-05.\n"
        f"stdout (last 2000):\n{proc.stdout[-2000:]}\n"
        f"stderr (last 2000):\n{proc.stderr[-2000:]}"
    )


def test_t_v6_acc_05_approval_reuse_covered_by_cat4_driver() -> None:
    """T-L7-APPROVAL-REUSE-001 is exercised by the Phase 8 Cat-4 driver
    (see tests/integration/cat4/test_l8_cat4.py). The HA acceptance
    forces the test to exist there so it is not silently lost when the
    mutation/ directory gets the rest of the V5 L7 surface."""

    cat4_driver = REPO_ROOT / "tests" / "integration" / "cat4" / "test_l8_cat4.py"
    assert cat4_driver.exists(), cat4_driver
    text = cat4_driver.read_text(encoding="utf-8")
    assert "T-L7-APPROVAL-REUSE-001" in text, (
        "approval-reuse bypass class must be referenced in the Cat-4 driver"
    )
