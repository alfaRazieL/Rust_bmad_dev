"""Phase 6 §6.3 — Full L7 suite gate.

RDX_IMPLEMENTATION_PLAN_TESTED.md §6.3 requires:
  "Full L7 suite passes (each listed bypass caught)"

This test asserts that every V5 L7 bypass class enumerated in
RDX_TEST_CASES.yaml has a matching test module on disk under
tests/mutation/ and is collected by pytest. Approval-reuse
(T-L7-APPROVAL-REUSE-001) is Phase 8 and is intentionally NOT in
the V5 release gate.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
TEST_CASES_YAML = REPO_ROOT / "archive-docs-dev" / "test-design" / "RDX_TEST_CASES.yaml"
MUTATION_DIR = REPO_ROOT / "tests" / "mutation"


# Each V5 L7 bypass class -> the test module that proves it is caught.
# Locked here so a future PR cannot silently drop a defense layer by
# deleting the test module without also editing this map (which itself
# is protected by L0 drift checks against the YAML).
V5_L7_BYPASS_TO_TEST_MODULE = {
    "T-L7-FAKE-PASS-001":     "test_l7_fake_pass.py",
    "T-L7-STALE-DIFF-001":    "test_l7_stale_diff.py",
    "T-L7-WRONG-BASE-001":    "test_l7_wrong_base.py",
    "T-L7-DISABLED-PACK-001": "test_l7_disabled_pack.py",
    "T-L7-MOD-SCHEMA-001":    "test_l7_mod_schema.py",
    "T-L7-MOD-VALIDATOR-001": "test_l7_mod_validator.py",
    "T-L7-DEL-TEST-001":      "test_l7_del_test.py",
    "T-L7-OVERSIZED-DIFF-001":"test_l7_oversized_diff.py",
    "T-L7-WORKFLOW-MOD-001":  "test_l7_workflow_mod.py",
}


def _load_l7_v5_ids() -> set[str]:
    """Extract V5 L7 test IDs from the YAML catalog."""
    doc = yaml.safe_load(TEST_CASES_YAML.read_text(encoding="utf-8"))
    ids: set[str] = set()
    for entry in doc:
        if not isinstance(entry, dict):
            continue
        if entry.get("layer") == "L7" and entry.get("version") == "V5":
            ids.add(entry["id"])
    return ids


def test_v5_l7_catalog_matches_phase6_gate_map() -> None:
    """The map above must be in sync with the YAML catalog for V5 L7.
    If a new V5 L7 bypass class is added to the YAML, this test forces
    the corresponding test module to be authored AND listed here."""

    yaml_ids = _load_l7_v5_ids()
    map_ids = set(V5_L7_BYPASS_TO_TEST_MODULE)
    extra_in_map = map_ids - yaml_ids
    missing_in_map = yaml_ids - map_ids
    assert not extra_in_map, f"map lists bypass IDs not in YAML: {extra_in_map}"
    assert not missing_in_map, (
        f"YAML defines V5 L7 bypasses with no test module mapping: {missing_in_map}"
    )


@pytest.mark.parametrize("test_id,module", sorted(V5_L7_BYPASS_TO_TEST_MODULE.items()))
def test_v5_l7_test_module_exists(test_id: str, module: str) -> None:
    """Every V5 L7 bypass class must have its test module on disk and
    must reference its T-L7-* ID in the docstring or body so a reader
    can trace test → bypass class."""

    path = MUTATION_DIR / module
    assert path.exists(), f"missing L7 test module for {test_id}: {path}"
    text = path.read_text(encoding="utf-8")
    assert test_id in text, (
        f"{module} must reference its bypass ID {test_id} so traceability "
        f"matrix stays self-documenting"
    )


def test_v5_l7_full_suite_modules_importable() -> None:
    """Every V5 L7 test module must import without error. pytest's own
    collection of `tests/mutation/` then proves they run; recursing
    into a child pytest from inside this test would loop, so we settle
    for the importability + count contract."""

    import importlib.util

    for test_id, module in V5_L7_BYPASS_TO_TEST_MODULE.items():
        path = MUTATION_DIR / module
        spec = importlib.util.spec_from_file_location(
            f"_l7_gate_check_{path.stem}", path
        )
        assert spec and spec.loader, f"cannot build spec for {path}"
        m = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(m)
        except Exception as e:
            raise AssertionError(f"{module} ({test_id}) failed to import: {e}") from e
    # Sanity: the count locked here matches Phase 5's announced 9 + 0 deferred.
    assert len(V5_L7_BYPASS_TO_TEST_MODULE) == 9


def test_v5_l7_each_module_asserts_a_defense_layer() -> None:
    """Per tests/mutation/README.md the value of each L7 test is the
    DEFENSE LAYER it proves. Every module's docstring must name a layer
    (L2 schema / L6 CI / L8 governance) so the README claim is
    grep-verifiable."""

    layer_token = re.compile(r"\b(L2|L6|L7|L8)\b")
    for module in V5_L7_BYPASS_TO_TEST_MODULE.values():
        text = (MUTATION_DIR / module).read_text(encoding="utf-8")
        # First docstring (up to closing triple-quote)
        m = re.search(r'"""(.*?)"""', text, re.DOTALL)
        assert m, f"{module} must open with a module docstring"
        header = m.group(1)
        assert layer_token.search(header), (
            f"{module} docstring must name a defense layer (L2/L6/L7/L8); got:\n{header[:400]}"
        )
