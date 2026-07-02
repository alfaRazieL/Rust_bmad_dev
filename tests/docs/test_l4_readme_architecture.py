"""T-DOC-README-ARCHITECTURE-001 — Phase 10 implementation tasks: README
must cover every doc topic listed in `RDX_IMPLEMENTATION_PLAN_TESTED.md`
Phase 10 § Implementation tasks.

Public positioning (Phase 10 exit-gate, also enforced by T-V5-ACC-06):
- RDX does NOT prove correctness of all Rust decisions
- Cat-1 is deterministic
- Cat-2 verifies evidence
- Cat-3 is judgment review
- Cat-4 requires approval
- CI is the source of enforcement
- Wrapper is workflow UX (NOT hard enforcement)
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
README = REPO_ROOT / "README.md"


def _readme_text_lower() -> str:
    return README.read_text(encoding="utf-8").lower()


def test_readme_lists_all_five_modes():
    text = _readme_text_lower()
    for mode in ("mode 0", "mode 1", "mode 2", "mode 3", "mode 4"):
        assert mode in text, f"README must list {mode}."


def test_readme_uses_canonical_mode_labels():
    """The canonical labels come from .claude/skills/rdx-setup/assets/modes.md
    and from `rdx-validator/rdx_validator/cli.py::MODE_LABELS`."""
    text = _readme_text_lower()
    for label in ("advisory", "local validated", "local gated",
                  "ci enforced", "specialist approval"):
        assert label in text, (
            f"README must use the canonical mode label '{label}'."
        )


def test_readme_covers_validator():
    text = _readme_text_lower()
    assert "rdx-validator" in text or "rdx_validator" in text, (
        "README must describe the standalone validator package."
    )
    assert "deterministic" in text, (
        "README must explain the validator is deterministic (Cat-1/2)."
    )


def test_readme_covers_wrapper():
    text = _readme_text_lower()
    assert "rdx-dev-story" in text, (
        "README must describe the rdx-dev-story wrapper."
    )
    assert "soft" in text or "cooperative" in text, (
        "README must frame the wrapper as soft-gate / LLM-cooperative."
    )


def test_readme_covers_pre_push_hook():
    text = _readme_text_lower()
    assert "pre-push" in text or "pre push" in text, (
        "README must describe the pre-push git hook (Mode 2)."
    )
    assert "--no-verify" in text, (
        "README must document the --no-verify bypass."
    )


def test_readme_covers_ci_required_check():
    text = _readme_text_lower()
    assert "required check" in text, (
        "README must document the CI required-check (Mode 3) enforcement boundary."
    )
    assert "rdx-gate.yml" in text, (
        "README must reference the rdx-gate.yml workflow."
    )


def test_readme_covers_cat1_through_cat4():
    text = _readme_text_lower()
    for cat in ("cat-1", "cat-2", "cat-3", "cat-4"):
        assert cat in text, f"README must explain {cat}."


def test_readme_covers_specialist_approvals():
    text = _readme_text_lower()
    assert "codeowners" in text, (
        "README must mention the CODEOWNERS integration for Cat-4."
    )
    assert ("approvers.yaml" in text or "approval" in text), (
        "README must reference the approvers.yaml / in-repo approval JSON."
    )


def test_readme_covers_evidence_schema():
    text = _readme_text_lower()
    assert "evidence" in text, "README must explain the evidence model."
    assert ("schema" in text or "rdx-evidence" in text), (
        "README must reference the evidence schema."
    )


def test_readme_covers_status_semantics():
    text = _readme_text_lower()
    for verdict in ("pass", "fail", "review_required", "approval_required"):
        assert verdict in text, (
            f"README must mention the status verdict '{verdict}'."
        )
    assert "exit code" in text or "exit-code" in text, (
        "README must explain the exit-code taxonomy (0/1/2/3/4)."
    )


def test_readme_covers_exception_model():
    text = _readme_text_lower()
    assert "exception" in text, (
        "README must document the policy exception model."
    )


def test_readme_covers_update_and_uninstall():
    text = _readme_text_lower()
    assert "update" in text, "README must cover the update workflow."
    assert "uninstall" in text, "README must cover the uninstall workflow."


def test_readme_covers_review_integration():
    text = _readme_text_lower()
    assert "rdx-code-review" in text or "code review" in text, (
        "README must describe the rdx-code-review wrapper / Cat-3 layer."
    )
    assert "rdx-judgment" in text or "rule auditor" in text, (
        "README must mention the rdx-judgment Cat-3 evaluator."
    )


def test_readme_covers_troubleshooting_and_limitations():
    text = _readme_text_lower()
    assert "troubleshoot" in text, "README must include a troubleshooting section."
    assert "limitation" in text, "README must enumerate limitations."


def test_readme_links_compatibility_matrix():
    text = README.read_text(encoding="utf-8")
    assert ("tests/compatibility/matrix.md" in text
            or "compatibility matrix" in text.lower()), (
        "README must link or reference the compatibility matrix."
    )


def test_readme_public_positioning_statements_present():
    """The seven public positioning statements from Phase 10."""
    text = _readme_text_lower()
    assert "does not prove" in text or "does not guarantee" in text, (
        "README must say RDX does NOT prove correctness of all Rust decisions."
    )
    assert ("ci is the" in text and "enforcement" in text) or (
        "source of enforcement" in text), (
        "README must state that CI is the source of enforcement."
    )
    assert ("wrapper" in text and ("workflow ux" in text
                                   or "ux" in text or "soft" in text)), (
        "README must position the wrapper as workflow UX, not enforcement."
    )
