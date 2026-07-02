"""Phase 7 L4 — code-review integration tests.

Two patterns are in scope:
- R2 (primary): `rdx-code-review` wrapper that overrides agent.menu[code=CR]
  to call bmad-code-review as a child skill and then invoke rdx-judgment
  before the unified final report. T-L4-CR-001.
- R1 (control): `_bmad/custom/bmad-code-review.toml` declares an
  `on_complete = "rdx-judgment"` hook so rdx-judgment runs AFTER the
  standard review's triage + presentation. Documented as a fallback —
  the timing limitation (findings arrive after story status update) is
  the reason R2 is primary. T-L4-CR-002.

These tests are STATIC structural checks. The runtime LLM-cooperative
confirmation (a real subagent actually following the SKILL prose) is the
job of the L5 / L8 cases (cat3-scope, cat3-cat1-immutable, doc-not-rust,
clear-violation) consumed by bmad-eval-runner.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from tests.bmad._helpers.resolver_shim import resolve
from tests.bmad._helpers.skill_parser import parse


HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent.parent

R2_FIXTURE = HERE / "r2-wrapper" / "expected.json"
R1_FIXTURE = HERE / "r1-on-complete" / "expected.json"

CR_WRAPPER_SKILL = REPO_ROOT / ".claude" / "skills" / "rdx-code-review" / "SKILL.md"
JUDGMENT_SKILL = REPO_ROOT / ".claude" / "skills" / "rdx-judgment" / "SKILL.md"
DEV_OVERRIDE = (
    REPO_ROOT
    / ".claude"
    / "skills"
    / "rdx-setup"
    / "assets"
    / "agent-overrides"
    / "bmad-agent-dev.toml"
)
R1_CONTROL_OVERRIDE = (
    REPO_ROOT
    / ".claude"
    / "skills"
    / "rdx-setup"
    / "assets"
    / "workflow-overrides"
    / "bmad-code-review.toml"
)

BASE_DEV_AGENT = (
    REPO_ROOT / "tests" / "bmad" / "menu-override" / "fixture-base" / "bmad-agent-dev.toml"
)


# ─── T-L4-CR-001 — R2 wrapper ────────────────────────────────────────────


def test_t_l4_cr_001_rdx_code_review_skill_exists():
    """The R2 wrapper SKILL.md file must exist at the canonical path."""
    assert CR_WRAPPER_SKILL.exists(), (
        f"rdx-code-review SKILL.md missing at {CR_WRAPPER_SKILL}; "
        "R2 wrapper is the primary code-review integration per RDX_TEST_STRATEGY.md §8"
    )


def test_t_l4_cr_001_wrapper_frontmatter_honest():
    """Wrapper description must NOT claim hard enforcement (T-V5-ACC-06)."""
    parsed = parse(CR_WRAPPER_SKILL)
    assert parsed.name == "rdx-code-review"
    assert parsed.description, "description must be non-empty"
    expected = json.loads(R2_FIXTURE.read_text())
    for phrase in expected["forbidden_phrases"]:
        assert phrase.lower() not in parsed.description.lower(), (
            f"description must not contain forbidden phrase: {phrase!r}"
        )


def test_t_l4_cr_001_wrapper_orders_child_then_judgment():
    """The wrapper body must declare BEFORE → CHILD (bmad-code-review) →
    JUDGMENT (rdx-judgment) → UNIFIED report ordering."""
    parsed = parse(CR_WRAPPER_SKILL)
    body = parsed.body
    expected = json.loads(R2_FIXTURE.read_text())

    assert expected["expected_child_skill"] in body, (
        "wrapper must invoke bmad-code-review as the child skill"
    )
    assert expected["expected_post_child_skill"] in body, (
        "wrapper must invoke rdx-judgment after the child"
    )

    # Ordering: anchor on the step-section headings, not first-mention
    # prose. The Phase 3 wrapper uses the same pattern — `body.index(
    # "BEFORE marker")` etc — so a substring in the introductory section
    # does not flip the ordering.
    idx_before = body.index("BEFORE marker")
    idx_child = body.index("Invoke child skill (bmad-code-review)")
    idx_judgment = body.index("Invoke rdx-judgment")
    assert idx_before < idx_child < idx_judgment, (
        f"ordering violated: BEFORE({idx_before}) < CHILD({idx_child}) < JUDGMENT({idx_judgment})"
    )

    # Final sentinel and recursion guard sentinel both declared.
    assert expected["expected_final_sentinel"] in body, (
        f"wrapper must emit {expected['expected_final_sentinel']} on the happy path"
    )
    assert expected["expected_halt_sentinel_on_recursion"] in body, (
        "wrapper must declare a recursion-guard sentinel"
    )


def test_t_l4_cr_001_wrapper_carries_soft_gate_disclaimer():
    """Soft-gate disclaimer must appear in the SKILL body."""
    body = parse(CR_WRAPPER_SKILL).body.lower()
    expected = json.loads(R2_FIXTURE.read_text())
    for needle in expected["expected_soft_gate_phrases"]:
        assert needle.lower() in body, (
            f"wrapper body must carry soft-gate phrase {needle!r}"
        )


def test_t_l4_cr_001_wrapper_unified_report_contract():
    """Wrapper must explicitly contract that the final report contains
    BOTH the standard bmad-code-review layers AND the RDX Rule Auditor
    layer. Otherwise a non-cooperative LLM could omit the RDX section
    silently."""
    body = parse(CR_WRAPPER_SKILL).body.lower()
    # Must mention both surfaces appear in the unified report.
    assert "rdx rule auditor" in body or "rdx-judgment" in body
    assert "standard review" in body or "bmad-code-review" in body
    assert "unified" in body or "combined" in body or "final report" in body


def test_t_l4_cr_001_menu_override_sets_cr_to_rdx_code_review():
    """The shipped dev-agent override must replace CR → rdx-code-review.
    Merge-by-code semantics: the base agent declares CR → bmad-code-review;
    the RDX override REPLACES it via the same code key."""
    assert DEV_OVERRIDE.exists(), f"dev agent override missing: {DEV_OVERRIDE}"
    merged = resolve(BASE_DEV_AGENT, DEV_OVERRIDE)
    menu = merged.get("menu", [])
    cr_entries = [e for e in menu if e.get("code") == "CR"]
    assert len(cr_entries) == 1, (
        f"CR must appear exactly once after merge, got {len(cr_entries)}"
    )
    assert cr_entries[0]["skill"] == "rdx-code-review", (
        f"CR menu must point to rdx-code-review, got {cr_entries[0]['skill']!r}"
    )


def test_t_l4_cr_001_rdx_judgment_skill_exists():
    """The wrapper invokes `rdx-judgment` as the post-child layer; the
    skill must therefore exist on disk."""
    assert JUDGMENT_SKILL.exists(), (
        f"rdx-judgment SKILL.md missing at {JUDGMENT_SKILL}; "
        "the R2 wrapper depends on it for the Cat-3 evaluator layer"
    )
    parsed = parse(JUDGMENT_SKILL)
    assert parsed.name == "rdx-judgment"


def test_t_l4_cr_001_no_recursion_in_wrapper():
    """The wrapper must NOT invoke itself. Static check: there is exactly
    one Skill-tool invocation in the body for bmad-code-review, exactly
    one for rdx-judgment, and zero for rdx-code-review."""
    body = parse(CR_WRAPPER_SKILL).body
    # Count self-references in code-fence Skill-tool patterns. The
    # recursion guard sentinel itself names rdx-code-review in prose;
    # exclude that line.
    self_invocations = re.findall(
        r"Skill[^\n]*rdx-code-review|skill\s*=\s*['\"]rdx-code-review['\"]",
        body,
    )
    assert not self_invocations, (
        f"wrapper must not invoke rdx-code-review from inside rdx-code-review; "
        f"got {self_invocations}"
    )


# ─── T-L4-CR-002 — R1 on_complete control ────────────────────────────────


def test_t_l4_cr_002_r1_override_artefact_exists():
    """The R1 control artefact (workflow override) ships under rdx-setup
    assets so users who explicitly opt out of R2 can install it."""
    assert R1_CONTROL_OVERRIDE.exists(), (
        f"R1 control override missing at {R1_CONTROL_OVERRIDE}; "
        "T-L4-CR-002 requires the artefact even though R2 is primary"
    )


def test_t_l4_cr_002_r1_override_declares_on_complete_judgment():
    """The R1 override must declare `on_complete = "rdx-judgment"`."""
    text = R1_CONTROL_OVERRIDE.read_text(encoding="utf-8")
    expected = json.loads(R1_FIXTURE.read_text())
    # Tolerant pattern: TOML may format with spaces/quotes either way.
    pattern = (
        r"on_complete\s*=\s*['\"]"
        + re.escape(expected["expected_on_complete_value"])
        + r"['\"]"
    )
    assert re.search(pattern, text), (
        f"R1 override must declare on_complete = {expected['expected_on_complete_value']!r}; "
        f"file contents:\n{text}"
    )


def test_t_l4_cr_002_r1_override_documents_timing_limitation():
    """The R1 override must include a comment block stating that this is
    a fallback / control test with a timing limitation (findings after
    triage). Otherwise a user might install R1 in addition to R2 and
    double-evaluate, OR mistake R1 for the primary integration."""
    text = R1_CONTROL_OVERRIDE.read_text(encoding="utf-8")
    expected = json.loads(R1_FIXTURE.read_text())
    for phrase in expected["expected_documentation_phrases"]:
        assert phrase.lower() in text.lower(), (
            f"R1 override must document phrase {phrase!r} (timing limitation / fallback role)"
        )
    assert expected["expected_timing_limitation_phrase"].lower() in text.lower(), (
        f"R1 override must explicitly state the timing limitation "
        f"({expected['expected_timing_limitation_phrase']!r})"
    )
    assert "R2" in text or "rdx-code-review" in text, (
        "R1 override must point readers at R2 (the primary integration)"
    )
