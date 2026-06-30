"""T-L7-WORKFLOW-MOD-001 — PR modifies .github/workflows/rdx-gate.yml.
Branch protection (configured at GitHub UI level) must prevent merge
without CODEOWNERS approval.

Structural assertion: the rdx-gate workflow ships with a
`docs/branch-protection.md` describing the required rule set, and the
workflow YAML itself carries a self-documenting comment naming the
expected protection.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "rdx-gate.yml"
BP_DOC = REPO_ROOT / "docs" / "branch-protection.md"


def test_l7_branch_protection_documented():
    assert BP_DOC.exists(), "docs/branch-protection.md must exist"
    text = BP_DOC.read_text(encoding="utf-8")
    # Must explicitly name the workflow under protection AND require
    # CODEOWNERS / human review for modifications to it.
    assert "rdx-gate.yml" in text or ".github/workflows/" in text
    assert "CODEOWNERS" in text or "review" in text.lower()


def test_l7_workflow_self_documents_branch_protection():
    assert WORKFLOW.exists(), "rdx-gate.yml must exist"
    text = WORKFLOW.read_text(encoding="utf-8")
    # A docstring/comment in the workflow file must point to the
    # protection doc so future editors do not silently weaken it.
    assert "branch-protection" in text.lower() or "codeowners" in text.lower(), text
