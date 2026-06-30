"""T-DOC-README-CI-COST-001 — Phase 10 exit-gate: README contains both
"Using RDX with GitHub Actions Free plan" and "switching to paid"
subsections with the concrete content required by
`RDX_IMPLEMENTATION_PLAN_TESTED.md` Phase 10 § README sections
(locked 2026-06-30)."""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
README = REPO_ROOT / "README.md"


def _section_body(text: str, heading_pattern: str) -> str:
    """Return the text from the first heading matching ``heading_pattern``
    (case-insensitive substring on the heading line) up to the next
    heading of equal-or-shallower level. Empty string if not found."""
    lines = text.splitlines()
    start = None
    start_level = 0
    for i, raw in enumerate(lines):
        if not raw.startswith("#"):
            continue
        m = re.match(r"^(#+)\s+(.*)$", raw)
        if not m:
            continue
        level = len(m.group(1))
        title = m.group(2).strip().lower()
        if heading_pattern.lower() in title:
            start = i
            start_level = level
            break
    if start is None:
        return ""
    body: list[str] = []
    for raw in lines[start + 1 :]:
        if raw.startswith("#"):
            m = re.match(r"^(#+)\s+", raw)
            if m and len(m.group(1)) <= start_level:
                break
        body.append(raw)
    return "\n".join(body)


def test_readme_exists():
    assert README.exists(), f"README missing at {README}"


def test_readme_has_gh_actions_free_subsection():
    body = _section_body(README.read_text(encoding="utf-8"),
                         "github actions free")
    assert body, ("README missing subsection containing "
                  "'GitHub Actions Free' in the heading.")


def test_readme_gh_free_mentions_2000_minute_budget():
    body = _section_body(README.read_text(encoding="utf-8"),
                         "github actions free").lower()
    assert ("2,000" in body or "2000" in body), (
        "GH Actions Free subsection must mention the 2,000-minute budget."
    )
    assert "minute" in body, "must mention 'minute' (the unit)."
    assert "month" in body, "must specify the per-month period."


def test_readme_gh_free_mentions_owner_aggregation():
    body = _section_body(README.read_text(encoding="utf-8"),
                         "github actions free").lower()
    assert ("per account" in body or "per organization" in body
            or "owner" in body), (
        "GH Actions Free subsection must explain that the 2,000-minute "
        "budget aggregates per account/organization owner across all "
        "private repos."
    )


def test_readme_gh_free_mentions_typical_pr_consumption():
    body = _section_body(README.read_text(encoding="utf-8"),
                         "github actions free").lower()
    assert "5" in body and "15" in body and "minute" in body, (
        "GH Actions Free subsection must mention typical 5–15 CI-min "
        "per Rust+RDX PR."
    )


def test_readme_gh_free_mentions_mode2_as_no_ci_alternative():
    body = _section_body(README.read_text(encoding="utf-8"),
                         "github actions free").lower()
    assert "mode 2" in body, "must reference Mode 2 by name."
    assert "no-ci" in body or "no ci" in body or "without ci" in body, (
        "must explicitly frame Mode 2 as the no-CI alternative."
    )


def test_readme_gh_free_has_step_by_step_rdx_gate_setup():
    body = _section_body(README.read_text(encoding="utf-8"),
                         "github actions free")
    assert "rdx-gate.yml" in body, (
        "GH Actions Free subsection must reference rdx-gate.yml."
    )
    assert re.search(r"required check", body, re.IGNORECASE), (
        "must mention setting rdx-gate.yml as a required check."
    )
    numbered = re.findall(r"(?m)^\s*\d+\.\s+\S", body)
    assert len(numbered) >= 3, (
        "must include numbered step-by-step setup (≥3 steps)."
    )


def test_readme_has_switching_to_paid_subsection():
    body = _section_body(README.read_text(encoding="utf-8"),
                         "switching to paid")
    assert body, ("README missing subsection containing "
                  "'switching to paid' in the heading.")


def test_readme_paid_subsection_compares_pro_team_enterprise():
    body = _section_body(README.read_text(encoding="utf-8"),
                         "switching to paid").lower()
    for tier in ("pro", "team", "enterprise"):
        assert tier in body, (
            f"paid subsection must compare the '{tier}' GitHub tier."
        )


def test_readme_paid_subsection_mentions_self_hosted_runners():
    body = _section_body(README.read_text(encoding="utf-8"),
                         "switching to paid").lower()
    assert "self-hosted" in body or "self hosted" in body, (
        "paid subsection must mention self-hosted runners as zero-cost option."
    )


def test_readme_paid_subsection_has_cost_calculator_hint():
    body = _section_body(README.read_text(encoding="utf-8"),
                         "switching to paid").lower()
    assert "calculator" in body or "calculation" in body or "×" in body or "*" in body, (
        "paid subsection must include a cost calculator hint "
        "(PR minutes × monthly PRs)."
    )


def test_readme_paid_subsection_explains_organization_move():
    body = _section_body(README.read_text(encoding="utf-8"),
                         "switching to paid").lower()
    assert "organization" in body, (
        "paid subsection must walk through moving the repo into an "
        "organization."
    )
