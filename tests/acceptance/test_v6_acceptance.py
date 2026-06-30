"""Phase 7 V6 acceptance — T-V6-ACC-01/02/03.

Three acceptance assertions that lock the Phase 7 release boundary:

- T-V6-ACC-01 — Phase 7's additions (rdx-judgment + rdx-code-review)
  must NOT break any V5 acceptance test. Runs the V5 acceptance pack as
  a subprocess and asserts exit code 0.
- T-V6-ACC-02 — Cat-3 routing works AND Cat-1 immutability holds. The
  two underlying claims are proved by separate structural / harness
  tests; this acceptance assertion verifies both surfaces are in place.
- T-V6-ACC-03 — The R2 code-review wrapper is structurally complete
  (CR menu override, child→judgment ordering, soft-gate disclaimer).
  Runtime LLM behavior is covered by the L5 evals; this is the
  release-boundary structural acceptance.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from tests.bmad._helpers.resolver_shim import resolve


REPO_ROOT = Path(__file__).resolve().parents[2]

CR_WRAPPER_SKILL = REPO_ROOT / ".claude" / "skills" / "rdx-code-review" / "SKILL.md"
JUDGMENT_SKILL = REPO_ROOT / ".claude" / "skills" / "rdx-judgment" / "SKILL.md"
FINDING_SCHEMA = (
    REPO_ROOT / "tests" / "contracts" / "schemas" / "rdx-judgment-finding.v1.schema.json"
)
DEV_OVERRIDE = (
    REPO_ROOT
    / ".claude"
    / "skills"
    / "rdx-setup"
    / "assets"
    / "agent-overrides"
    / "bmad-agent-dev.toml"
)
BASE_DEV_AGENT = (
    REPO_ROOT / "tests" / "bmad" / "menu-override" / "fixture-base" / "bmad-agent-dev.toml"
)


# ─── T-V6-ACC-01 ─────────────────────────────────────────────────────────


def test_t_v6_acc_01_v5_regression_pack_passes():
    """Run the V5 regression pack (contracts + unit + doc-honesty + CI
    workflow tests) and require exit code 0. The catalogue of which
    tests cover which V5 ACC ID is in `v5-regression-pack/spec.md`."""

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "--no-header",
            "tests/contracts",
            "tests/unit",
            "tests/acceptance/test_doc_honesty.py",
            "tests/ci",
            "tests/bmad",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert proc.returncode == 0, (
        f"V5 regression pack failed under Phase 7 additions.\n"
        f"stdout (last 2000):\n{proc.stdout[-2000:]}\n"
        f"stderr (last 2000):\n{proc.stderr[-2000:]}"
    )


# ─── T-V6-ACC-02 ─────────────────────────────────────────────────────────


def test_t_v6_acc_02_cat3_routing_and_cat1_immutability():
    """Both surfaces in place: (1) Cat-3 routing via rdx-judgment + the
    scope filter, (2) Cat-1 immutability via the finding schema."""

    # (1) rdx-judgment skill exists and declares its verdict set + scope.
    assert JUDGMENT_SKILL.exists()
    body = JUDGMENT_SKILL.read_text(encoding="utf-8")
    for verdict in (
        "PASS",
        "FAIL",
        "DECISION_REQUIRED",
        "SPECIALIST_REQUIRED",
        "INSUFFICIENT_EVIDENCE",
    ):
        assert verdict in body, f"rdx-judgment must declare verdict {verdict}"

    # (2) Finding schema rejects evaluator-set Cat-1 PASS.
    import jsonschema

    schema = json.loads(FINDING_SCHEMA.read_text(encoding="utf-8"))
    cat1_pass = {
        "rule_id": "CORE-007",
        "category": 1,
        "location": {"file": "_bmad/scripts/resolve_customization.py"},
        "contract_ref": "CORE-007 protected files",
        "reasoning": "I think this should pass.",
        "verdict": "PASS",
        "confidence": 0.99,
        "suggested_routing": "PASS",
        "set_by": "evaluator",
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(cat1_pass, schema)


# ─── T-V6-ACC-03 ─────────────────────────────────────────────────────────


def test_t_v6_acc_03_r2_wrapper_structurally_complete():
    """The R2 wrapper passes the same structural checks as the Phase 3
    rdx-dev-story wrapper — frontmatter clean, soft-gate disclaimer,
    child→judgment ordering, CR menu override in place."""

    # Frontmatter + body checks.
    assert CR_WRAPPER_SKILL.exists()
    text = CR_WRAPPER_SKILL.read_text(encoding="utf-8")
    # Forbidden phrases — same set as Phase 3 wrapper.
    lower = text.lower()
    for phrase in ("hard enforcement", "guarantees compliance"):
        assert phrase not in lower, (
            f"R2 wrapper carries forbidden phrase {phrase!r}"
        )
    # Soft-gate disclaimer.
    assert "soft gate" in lower
    # Child → judgment ordering.
    idx_child = text.find("bmad-code-review")
    idx_judgment = text.find("rdx-judgment")
    assert -1 < idx_child < idx_judgment, (
        f"R2 wrapper must invoke bmad-code-review BEFORE rdx-judgment "
        f"(idx_child={idx_child}, idx_judgment={idx_judgment})"
    )

    # CR menu override wired.
    merged = resolve(BASE_DEV_AGENT, DEV_OVERRIDE)
    cr = [e for e in merged["menu"] if e["code"] == "CR"]
    assert len(cr) == 1 and cr[0]["skill"] == "rdx-code-review"
