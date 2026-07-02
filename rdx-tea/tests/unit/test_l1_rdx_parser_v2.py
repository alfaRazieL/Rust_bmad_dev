"""L1 unit tests for the semantic RDX rule parser (Phase B of D3 proof).

Failing-first tests that force the parser (`rdx-tea/poc/adapter/rdx_parser.py`)
to extract the FULL normative body of every canonical rule, not just IDs.

The parser is the answer to `D3_CORRECTION_AUDIT §3.2` and enables the
Variant D3 active-context bundle (§5.2 of the D3 prompt).

Every canonical RULE-ID discovered in the KB must have all mandatory
fields populated:
  rule_id, title, layer, importance, trigger, risk, rule,
  required_reasoning, validation, exceptions, sources, pack_id, source_line
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

RDX_TEA_DIR = Path(__file__).resolve().parent.parent.parent
REPO_ROOT = RDX_TEA_DIR.parent

PARSER_PATH = RDX_TEA_DIR / "poc" / "adapter" / "rdx_parser.py"


def _import_parser():
    if not PARSER_PATH.exists():
        pytest.skip("rdx_parser.py not yet written — expected RED state")
    spec = importlib.util.spec_from_file_location("rdx_parser_v2", PARSER_PATH)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)   # type: ignore[union-attr]
    return m


MANDATORY_FIELDS = {
    "rule_id", "title", "layer", "importance", "trigger", "risk",
    "rule", "required_reasoning", "validation", "exceptions", "sources",
    "pack_id", "source_line",
}


def test_l1_parser_v2_exists_and_parses_kb() -> None:
    p = _import_parser()
    rules = p.parse_all()
    assert isinstance(rules, list)
    assert len(rules) >= 60   # 18 CORE + ≥ 42 pack rules at minimum


def test_l1_parser_v2_every_rule_has_mandatory_fields() -> None:
    p = _import_parser()
    rules = p.parse_all()
    for rule in rules:
        missing = MANDATORY_FIELDS - set(rule.keys())
        assert not missing, f"rule {rule.get('rule_id','?')} missing {missing}"
        # No field may be empty except sources (which may be empty list).
        for k in MANDATORY_FIELDS - {"sources"}:
            v = rule[k]
            assert v not in (None, "", []), (
                f"rule {rule['rule_id']} field {k} is empty: {v!r}"
            )


def test_l1_parser_v2_rp_async_005_is_semantic() -> None:
    """The canonical content of RP-ASYNC-005 (from section-6-packs.md
    heading `### RP-ASYNC-005 — Cancellation safety and async cleanup are
    explicit`) must be preserved verbatim in the parsed IR.

    This is the specific example the D3 prompt §5.2 uses to distinguish
    metadata from semantic projection.
    """
    p = _import_parser()
    r = next(x for x in p.parse_all() if x["rule_id"] == "RP-ASYNC-005")
    assert r["title"] == "Cancellation safety and async cleanup are explicit"
    assert r["layer"] == "RISK_PACK"
    assert r["importance"] == "COMMON"
    assert r["pack_id"] == "async"
    # Rule must contain the trio the D3 prompt calls out.
    for keyword in ("cancel-safe", "not cancel-safe", "intentionally lossy"):
        assert keyword in r["rule"], f"missing keyword {keyword!r} in Rule body"
    for keyword in ("partial-progress state", "cleanup ownership"):
        assert keyword in r["rule"], f"missing keyword {keyword!r} in Rule body"
    # Validation must reference the cancellation/timeout/shutdown tests.
    for keyword in ("Cancellation", "timeout", "shutdown"):
        assert keyword in r["validation"], f"missing keyword {keyword!r} in Validation"
    assert r["exceptions"], "exceptions body must be preserved"
    assert r["sources"], "sources list must be non-empty for RP-ASYNC-005"


def test_l1_parser_v2_core_rules_parsed() -> None:
    """All 18 CORE-* rules from section-4-core.md must appear."""
    p = _import_parser()
    ids = {r["rule_id"] for r in p.parse_all()}
    for n in range(1, 19):
        rid = f"CORE-{n:03d}"
        assert rid in ids, f"missing {rid}"


def test_l1_parser_v2_pack_membership_correct() -> None:
    """RP-<PACK>-NNN rules must have pack_id equal to the RDX router pack
    key (lower-cased). Router canonical map:
      ASYNC→async, UNSAFE→unsafe, FFI→ffi, MACRO→macro, API→api,
      CARGO→cargo, TEST→testing, DATA/SEC/IO→data-security-io,
      DB→db, TIME→time-config-client, OPS→ops, PERF→perf.
    """
    p = _import_parser()
    router_packs = {
        "ASYNC": "async", "UNSAFE": "unsafe", "FFI": "ffi",
        "MACRO": "macro", "API": "api", "CARGO": "cargo",
        "TEST": "testing",
        "DATA": "data-security-io", "SEC": "data-security-io", "IO": "data-security-io",
        "DB": "db", "TIME": "time-config-client",
        "OPS": "ops", "PERF": "perf",
    }
    for r in p.parse_all():
        rid = r["rule_id"]
        if rid.startswith("RP-"):
            prefix = rid.split("-")[1]
            expected = router_packs.get(prefix)
            assert expected, f"unknown pack prefix {prefix} in {rid}"
            assert r["pack_id"] == expected, (
                f"{rid} has pack_id={r['pack_id']}, expected {expected}"
            )


def test_l1_parser_v2_fails_closed_on_malformed_input(tmp_path: Path) -> None:
    """Rule blocks that miss a mandatory field must raise, not silently
    swallow. Failing closed is a `D3` requirement (prompt §5.2)."""
    p = _import_parser()
    bad = tmp_path / "bad.md"
    bad.write_text("""### RP-BAD-001 — No fields

- **Layer:** RISK_PACK

### RP-NEXT — filler
""")
    with pytest.raises(p.RdxParseError):
        p.parse_file(bad)


def test_l1_parser_v2_deterministic_order() -> None:
    """Two calls must return the same rule order (source line ascending)."""
    p = _import_parser()
    a = [r["rule_id"] for r in p.parse_all()]
    b = [r["rule_id"] for r in p.parse_all()]
    assert a == b


def test_l1_parser_v2_source_line_ascending_within_file() -> None:
    p = _import_parser()
    rules = p.parse_all()
    # Group by source_file, assert source_line monotonic.
    by_file: dict[str, list[int]] = {}
    for r in rules:
        by_file.setdefault(r["source_file"], []).append(r["source_line"])
    for f, lines in by_file.items():
        assert lines == sorted(lines), f"non-monotonic line order in {f}"


def test_l1_parser_v2_no_rust_prefix_ids() -> None:
    """Parser must not accidentally emit legacy `RUST-*` IDs. The KB
    references them only inside `Sources:`."""
    p = _import_parser()
    for r in p.parse_all():
        assert not r["rule_id"].startswith("RUST-")


def test_l1_parser_v2_source_hash_stable() -> None:
    """Parser records SHA-256 of the source file it read. Must be stable
    across calls."""
    p = _import_parser()
    h1 = p.source_hashes()
    h2 = p.source_hashes()
    assert h1 == h2
    assert h1  # non-empty


def test_l1_parser_v2_rule_ids_match_rule_check_map() -> None:
    """Every rule ID in rule-check-map.json must be discoverable by the
    parser. Extra rules in the KB are allowed."""
    import json
    p = _import_parser()
    parsed_ids = {r["rule_id"] for r in p.parse_all()}
    rcm = json.loads((REPO_ROOT / "tests" / "contracts" / "rule-check-map.json").read_text())
    for rid in rcm["rules"]:
        assert rid in parsed_ids, f"rule-check-map.json references {rid}, KB parser missed it"
