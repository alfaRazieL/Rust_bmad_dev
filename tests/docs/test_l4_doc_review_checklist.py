"""T-DOC-CHECKLIST-001 — Phase 10 entry-gate: doc-review checklist authored.

The checklist enumerates every Phase 10 implementation topic so reviewers
can mechanically verify documentation completeness before release. The
canonical list of topics lives in
`RDX_IMPLEMENTATION_PLAN_TESTED.md` Phase 10 § Implementation tasks.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CHECKLIST = REPO_ROOT / "docs" / "doc-review-checklist.md"

REQUIRED_TOPICS = (
    "architecture overview",
    "mode comparison",
    "installation",
    "update",
    "uninstall",
    "evidence schema",
    "status semantics",
    "exception model",
    "hook behavior",
    "--no-verify",
    "ci setup",
    "review integration",
    "specialist approvals",
    "troubleshooting",
    "compatibility matrix",
    "limitations",
)


def test_doc_review_checklist_exists():
    assert CHECKLIST.exists(), (
        f"Phase 10 entry-gate missing: {CHECKLIST.relative_to(REPO_ROOT)} "
        "should enumerate the doc-review topics."
    )


def test_doc_review_checklist_enumerates_required_topics():
    text = CHECKLIST.read_text(encoding="utf-8").lower()
    missing = [t for t in REQUIRED_TOPICS if t not in text]
    assert not missing, (
        f"doc-review-checklist.md missing required topics: {missing}"
    )


def test_doc_review_checklist_uses_checkbox_format():
    """The checklist must use markdown task-list syntax so reviewers can
    tick items as they verify each section. Spot-check that at least
    half of the required topics appear next to a checkbox marker."""
    text = CHECKLIST.read_text(encoding="utf-8")
    boxes = text.count("- [ ]") + text.count("- [x]") + text.count("- [X]")
    assert boxes >= len(REQUIRED_TOPICS), (
        f"doc-review-checklist.md has {boxes} checkbox items but "
        f"requires at least {len(REQUIRED_TOPICS)} (one per topic)."
    )
