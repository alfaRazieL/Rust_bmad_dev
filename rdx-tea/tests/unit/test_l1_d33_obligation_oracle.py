"""D3.3 §4.7 — obligation oracle + CSV byte-equality."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import yaml

RDX_TEA_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(RDX_TEA_DIR / "poc" / "install-tree" / "_bmad" / "rdx-tea" / "scripts"))

if "rdx_parser" in sys.modules:
    del sys.modules["rdx_parser"]
if "obligation_matrix" in sys.modules:
    del sys.modules["obligation_matrix"]

rdx_parser = importlib.import_module("rdx_parser")
om = importlib.import_module("obligation_matrix")

ORACLE = yaml.safe_load(
    (RDX_TEA_DIR / "evals" / "oracles" / "workflow-obligation-oracle.yaml").read_text()
)


def test_l1_d33_oracle_covers_every_workflow():
    for w in om.all_workflows():
        assert w in ORACLE["workflows"], f"oracle missing workflow {w}"


def test_l1_d33_oracle_positive_packs_match_matrix():
    for w, spec in ORACLE["workflows"].items():
        m = om.matrix_for(w)
        assert set(spec["positive_packs"]) == set(m["packs"]), (
            f"workflow {w}: oracle positive={spec['positive_packs']} "
            f"vs matrix packs={m['packs']}"
        )


def test_l1_d33_oracle_negative_packs_disjoint_from_positive():
    for w, spec in ORACLE["workflows"].items():
        neg = set(spec["negative_packs"])
        pos = set(spec["positive_packs"])
        assert not (neg & pos), f"{w}: overlap between negative and positive packs"


def test_l1_d33_oracle_representative_rules_exist_in_kb():
    ids = {r["rule_id"] for r in rdx_parser.parse_all()}
    for w, spec in ORACLE["workflows"].items():
        for key in ("positive_rule_representative", "negative_rule_representative"):
            rid = spec[key]["rule_id"]
            assert rid in ids, f"{w} {key}: {rid!r} not in KB"


def test_l1_d33_oracle_decisions_match_coverage_for():
    for w, spec in ORACLE["workflows"].items():
        p = spec["positive_rule_representative"]
        c = om.coverage_for(w, p["rule_id"], p["pack"])
        assert c["decision"] == "INCLUDE", (
            f"{w}: positive rep {p['rule_id']} in pack {p['pack']} "
            f"expected INCLUDE, got {c}"
        )
        n = spec["negative_rule_representative"]
        c = om.coverage_for(w, n["rule_id"], n["pack"])
        assert c["decision"] == "EXCLUDE", (
            f"{w}: negative rep {n['rule_id']} in pack {n['pack']} "
            f"expected EXCLUDE, got {c}"
        )


def test_l1_d33_oracle_core_rules_match_matrix():
    for w, spec in ORACLE["workflows"].items():
        m = om.matrix_for(w)
        expected = spec["core_rules_included"]
        if expected == "*":
            assert m["core_rules"] is True, f"{w} expects all CORE-*, matrix says {m['core_rules']}"
        else:
            assert set(expected) == set(m["core_rules"]), (
                f"{w}: oracle CORE={expected} vs matrix CORE={m['core_rules']}"
            )


def test_l1_d33_csv_byte_equality():
    """`generate_csv()` output equals the committed CSV byte-for-byte."""
    generated = om.generate_csv()
    committed = (RDX_TEA_DIR / "architecture" / "WORKFLOW_OBLIGATION_MATRIX.csv").read_text()
    assert generated == committed, (
        "WORKFLOW_OBLIGATION_MATRIX.csv is out of sync with obligation_matrix.py; "
        "regenerate via `python3 -c 'import obligation_matrix as om; print(om.generate_csv())' "
        "> rdx-tea/architecture/WORKFLOW_OBLIGATION_MATRIX.csv"
    )
