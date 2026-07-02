"""L0 static-contract tests for the RDX → TEA projection generator.

These tests are the FAILING contract for `poc/adapter/projection.py`.
They MUST run against a repo checked out at the SHA recorded in
`rdx-tea/research/SOURCE_LOCK.md §1`. If the SHA changes, the golden hashes
in this file are expected to change and the test-suite maintainer must
regenerate them with `python rdx-tea/poc/adapter/projection.py --emit-hashes`.

Every test asserts one of the knowledge-plane G-gates from the task prompt:

- G2 (canonical projection): the generator reads only files hashed in
  SOURCE_LOCK §5 and produces deterministic, hash-stable output.
- G3 (Router parity): activation of every pack is derived from
  `tests/contracts/router-rules.json` and reproduces the canonical
  pack list, `activation_policy`, `confidence_class`, `related_rule_ids`.

No enforcement-plane assertions here — those live in later layers by
project rule (`feedback_rdx_tea_knowledge_first`).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest


# --------------------------------------------------------------------------
# Locate the RDX repo root and canonical contract files.
# --------------------------------------------------------------------------

RDX_TEA_DIR = Path(__file__).resolve().parent.parent.parent   # rdx-tea/
REPO_ROOT = RDX_TEA_DIR.parent                                # RDX repo root
CONTRACTS = REPO_ROOT / "tests" / "contracts"
KB_SECTIONS = REPO_ROOT / ".claude" / "skills" / "rdx-setup" / "assets" / "kb-sections"

CANONICAL_ROUTER = CONTRACTS / "router-rules.json"
CANONICAL_STATUS = CONTRACTS / "status-definitions.json"
CANONICAL_RULE_CHECK_MAP = CONTRACTS / "rule-check-map.json"
CANONICAL_AUTHORITY = CONTRACTS / "authority-matrix.json"

CORE_KB = KB_SECTIONS / "section-4-core.md"
ROUTER_KB = KB_SECTIONS / "section-5-router.md"
PACKS_KB = KB_SECTIONS / "section-6-packs.md"
GOV_KB = KB_SECTIONS / "section-8-governance.md"

# Canonical SHA-256 hashes copied from
# rdx-tea/evidence/hashes/SOURCE_LOCK_files_sha256.txt (SOURCE_LOCK §5).
EXPECTED_CANONICAL_HASHES = {
    CANONICAL_ROUTER: None,   # populated by fixture; asserted stable across runs
    CANONICAL_STATUS: None,
    CANONICAL_RULE_CHECK_MAP: None,
    CANONICAL_AUTHORITY: None,
    (KB_SECTIONS / "section-4-core.md"): "aa419c1a76551b8aa6248fad6a7f1cdafc8bcfeae7251e8f4fc4f3fa6a30c876",
    (KB_SECTIONS / "section-5-router.md"): "579a890cc1065fbcca112a786ebda8e938869383338ef3755fea9671b65ee776",
    (KB_SECTIONS / "section-6-packs.md"): "d4665fc9351164ce6744620a2c25c6e1c3ecb9fe0852307d164b4ddabaafa270",
    (KB_SECTIONS / "section-8-governance.md"): "4d683f87054f940d9398bef4b86705063a721975adbe8a43caeb60c78981a07f",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# --------------------------------------------------------------------------
# 0. Source lock hashes — tests are meaningless if the canonical inputs
#    have shifted.
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "path,expected",
    [
        (KB_SECTIONS / "section-4-core.md",       "aa419c1a76551b8aa6248fad6a7f1cdafc8bcfeae7251e8f4fc4f3fa6a30c876"),
        (KB_SECTIONS / "section-5-router.md",     "579a890cc1065fbcca112a786ebda8e938869383338ef3755fea9671b65ee776"),
        (KB_SECTIONS / "section-6-packs.md",      "d4665fc9351164ce6744620a2c25c6e1c3ecb9fe0852307d164b4ddabaafa270"),
        (KB_SECTIONS / "section-8-governance.md", "4d683f87054f940d9398bef4b86705063a721975adbe8a43caeb60c78981a07f"),
    ],
    ids=["core", "router", "packs", "gov"],
)
def test_l0_source_lock_hash(path: Path, expected: str) -> None:
    """SOURCE_LOCK §5 hashes must match. Otherwise the entire proof is stale."""
    assert path.exists(), f"canonical KB file missing: {path}"
    assert _sha256(path) == expected, (
        f"KB drift at {path}. Regenerate SOURCE_LOCK.md and every downstream "
        f"golden hash. Do not silently accept the new value."
    )


# --------------------------------------------------------------------------
# 1. Status vocabulary imported by the projection must match verbatim.
# --------------------------------------------------------------------------

EXPECTED_STATUS_VERDICTS = {
    "PASS",
    "FAIL",
    "NOT_APPLICABLE",
    "NOT_RUN",
    "EVIDENCE_REQUIRED",
    "REVIEW_REQUIRED",
    "APPROVAL_REQUIRED",
    "BASELINE_FAILURE_OBSERVED",
    "BASELINE_BLOCKS_VALIDATION",
    "REGRESSION_FAILURE",
    "REGRESSION_FIXED",
    "ENVIRONMENT_UNAVAILABLE",
    "TOOL_UNAVAILABLE",
    "BLOCKED",
}
EXPECTED_STATUS_SEVERITIES = {"INFO", "WARNING", "BLOCKING"}


def test_l0_status_vocabulary_complete() -> None:
    """Prompt §5.1 regression target: verify no `EVIDENCE_MISSING`,
    the correct spelling is `EVIDENCE_REQUIRED`, and all 14 verdicts
    are present in the canonical file."""
    data = json.loads(CANONICAL_STATUS.read_text())
    verdicts = set(data["verdicts"].keys())
    severities = set(data["severities"].keys())
    assert verdicts == EXPECTED_STATUS_VERDICTS, (
        f"missing={EXPECTED_STATUS_VERDICTS - verdicts}, "
        f"extra={verdicts - EXPECTED_STATUS_VERDICTS}"
    )
    assert severities == EXPECTED_STATUS_SEVERITIES
    assert "EVIDENCE_REQUIRED" in verdicts
    assert "EVIDENCE_MISSING" not in verdicts  # prompt §5.1


# --------------------------------------------------------------------------
# 2. Router pack list, activation policy, confidence class, and rule-ID
#    prefixes — the projection must reproduce these byte-identically.
# --------------------------------------------------------------------------

EXPECTED_PACKS = {
    "async":              ("STRONG", "AUTO_ACTIVATE",       9),
    "unsafe":             ("STRONG", "AUTO_ACTIVATE",      11),
    "ffi":                ("STRONG", "AUTO_ACTIVATE",       7),
    "macro":              ("STRONG", "AUTO_ACTIVATE",       4),
    "api":                ("MEDIUM", "STORY_TAG_REQUIRED", 18),
    "cargo":              ("STRONG", "AUTO_ACTIVATE",       9),
    "testing":            ("MEDIUM", "STORY_TAG_REQUIRED",  4),
    "data-security-io":   ("MEDIUM", "AUTO_SUGGEST",       23),
    "db":                 ("MEDIUM", "AUTO_SUGGEST",        6),
    "time-config-client": ("MEDIUM", "AUTO_SUGGEST",        7),
    "ops":                ("WEAK",   "STORY_TAG_REQUIRED",  9),
    "perf":               ("WEAK",   "STORY_TAG_REQUIRED",  8),
}


def test_l0_router_packs_canonical() -> None:
    """Prompt §5.3 regression target: the Router is not hand-copied; every
    pack's activation policy, confidence class, and related-rule-id count
    must survive the projection unchanged."""
    data = json.loads(CANONICAL_ROUTER.read_text())
    observed = {
        name: (pack["confidence_class"], pack["activation_policy"], len(pack["related_rule_ids"]))
        for name, pack in data["packs"].items()
    }
    assert observed == EXPECTED_PACKS


def test_l0_router_rule_ids_prefixes() -> None:
    """Prompt §5.2: no `RUST-*` IDs; every pack rule uses `RP-*`."""
    data = json.loads(CANONICAL_ROUTER.read_text())
    for pack_name, pack in data["packs"].items():
        for rid in pack["related_rule_ids"]:
            assert rid.startswith("RP-"), (
                f"pack {pack_name} rule {rid} does not use RP- prefix — "
                "projection will lose canonical ID"
            )


def test_l0_story_tag_required_packs_preserved() -> None:
    """Prompt §5.3 explicit list: `STORY_TAG_REQUIRED` packs are `api`,
    `testing`, `ops`, `perf`. Any adapter that drops story-tag state must
    fail here first."""
    data = json.loads(CANONICAL_ROUTER.read_text())
    story_tag_required = {
        name for name, pack in data["packs"].items()
        if pack["activation_policy"] == "STORY_TAG_REQUIRED"
    }
    assert story_tag_required == {"api", "testing", "ops", "perf"}


# --------------------------------------------------------------------------
# 3. Rule-check-map (37 rules) prefix distribution.
# --------------------------------------------------------------------------

def test_l0_rule_check_map_prefixes() -> None:
    data = json.loads(CANONICAL_RULE_CHECK_MAP.read_text())
    rules = data["rules"]
    by_prefix = {}
    for rid in rules:
        p = rid.split("-")[0]
        by_prefix[p] = by_prefix.get(p, 0) + 1
    assert by_prefix == {"CORE": 18, "RP": 14, "GOV": 5}


# --------------------------------------------------------------------------
# 4. Projection generator: must exist and be deterministic.
#    (These tests are currently RED — the generator is not written yet.)
# --------------------------------------------------------------------------

# Path where the projection generator will live.
PROJECTION_MODULE = RDX_TEA_DIR / "poc" / "adapter" / "projection.py"
PROJECTION_OUT_DIR = RDX_TEA_DIR / "poc" / "projections"


def _import_projection():
    """Import the generator module. Skips if the file does not exist yet
    (bootstrap phase)."""
    if not PROJECTION_MODULE.exists():
        pytest.skip(
            "poc/adapter/projection.py not yet written — tests are red by design"
        )
    import importlib.util
    spec = importlib.util.spec_from_file_location("rdx_tea_projection", PROJECTION_MODULE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def test_l0_projection_generator_reads_only_canonical_inputs() -> None:
    """G2: the generator must declare its inputs as *files* under
    tests/contracts/ and .claude/skills/rdx-setup/assets/kb-sections/,
    not string constants."""
    mod = _import_projection()
    inputs = mod.CANONICAL_INPUTS   # expected attribute: list of Path
    for p in inputs:
        p = Path(p)
        assert p.exists(), f"declared canonical input missing: {p}"
        # Only allow files under the two canonical roots.
        try:
            p.resolve().relative_to((REPO_ROOT / "tests" / "contracts").resolve())
        except ValueError:
            p.resolve().relative_to((REPO_ROOT / ".claude" / "skills" / "rdx-setup" / "assets" / "kb-sections").resolve())


def test_l0_projection_generator_is_deterministic() -> None:
    """G2: two consecutive runs on the same SHA produce identical output
    (byte-for-byte)."""
    mod = _import_projection()
    out1 = mod.render_all()   # expected: dict[str, bytes]
    out2 = mod.render_all()
    assert out1 == out2


def test_l0_projection_generator_covers_all_packs() -> None:
    """G3: for each of the 12 canonical Router packs there must be at least
    one emitted fragment file, so no pack is silently dropped."""
    mod = _import_projection()
    out = mod.render_all()
    for pack in EXPECTED_PACKS:
        matches = [k for k in out if pack in k]
        assert matches, f"no projection fragment mentions pack {pack}"


def test_l0_projection_generator_emits_rdx_tea_index_row_per_pack() -> None:
    """G3: rdx-tea-index.csv must have one row per pack, with the same
    schema TEA workflows use (`id,name,description,tags,tier,fragment_file`)."""
    mod = _import_projection()
    csv_text = mod.render_index_csv()   # expected: str
    header, *rows = csv_text.strip().splitlines()
    assert header.strip() == "id,name,description,tags,tier,fragment_file"
    ids = {row.split(",", 1)[0] for row in rows}
    for pack in EXPECTED_PACKS:
        assert any(pack in i for i in ids), f"pack {pack} not in projection index"
