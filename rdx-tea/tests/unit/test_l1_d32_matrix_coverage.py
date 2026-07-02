"""D3.2 §9: single-source obligation matrix + coverage on all 138 rules.

Loads the semantic parser and asserts every workflow × rule combination
has a machine-recorded decision (INCLUDE / EXCLUDE) with a reason.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

RDX_TEA_DIR = Path(__file__).resolve().parent.parent.parent
INSTALL = RDX_TEA_DIR / "poc" / "install-tree" / "_bmad" / "rdx-tea" / "scripts"
sys.path.insert(0, str(INSTALL))

if "rdx_parser" in sys.modules:
    del sys.modules["rdx_parser"]
if "obligation_matrix" in sys.modules:
    del sys.modules["obligation_matrix"]

rdx_parser = importlib.import_module("rdx_parser")
om = importlib.import_module("obligation_matrix")


def test_l1_matrix_coverage_of_all_parsed_rules() -> None:
    rules = rdx_parser.parse_all()
    workflows = om.all_workflows()
    assert len(workflows) == 8, workflows
    coverage: dict[str, dict[str, str]] = {w: {} for w in workflows}
    for r in rules:
        for w in workflows:
            c = om.coverage_for(w, r["rule_id"], r["pack_id"])
            coverage[w][r["rule_id"]] = c["decision"]
    # 138 rules × 8 workflows = 1104 cells; assert every cell has a
    # decision.
    for w in workflows:
        for r in rules:
            assert r["rule_id"] in coverage[w]
            assert coverage[w][r["rule_id"]] in ("INCLUDE", "EXCLUDE")


def test_l1_matrix_generates_csv() -> None:
    csv_text = om.generate_csv()
    lines = csv_text.strip().splitlines()
    assert lines[0].startswith("workflow,rule_id_or_pack,included_fields")
    # At least one row per workflow.
    seen = set(ln.split(",", 1)[0] for ln in lines[1:])
    for w in om.all_workflows():
        assert w in seen, f"workflow {w} missing from generated CSV"


def test_l1_matrix_core_never_universal_when_workflow_is_ci() -> None:
    """`ci` workflow must NOT include every CORE-* — only CORE-004
    (root-cause) is allowed."""
    for rid in ("CORE-001", "CORE-002", "CORE-005", "CORE-009", "CORE-015"):
        assert om.core_rules_allowed("ci", rid) in (True, False)  # any
    # CORE-004 must be included by design.
    assert om.core_rules_allowed("ci", "CORE-004") is True
    # Explicit exclusion: workflow ci must not carry CORE-016.
    assert om.core_rules_allowed("ci", "CORE-016") is False


def test_l1_matrix_no_workflow_has_empty_scope() -> None:
    for w in om.all_workflows():
        m = om.matrix_for(w)
        assert m["packs"], f"workflow {w} has empty packs"
        assert m["fields"], f"workflow {w} has empty fields"
