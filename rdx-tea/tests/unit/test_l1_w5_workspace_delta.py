"""L1 W5 — production workspace-delta + artifact-consistency module.

Promotes D3.4.0 §7-§8 (reference: live-harness/rule_operation.py) into the
SHIPPED surface as `scripts/workspace_delta.py`. The production module must
NOT import live-harness/evals, must judge declared-file claims against the
REAL workspace delta + filesystem, and must:

  * fail-closed on a phantom file claim (declared-generated file that exists
    neither on disk nor in the delta);
  * fail-closed on a declared-but-missing generated file (unless the run
    marked it planned-but-not-generated);
  * treat duplicate frontmatter keys as a WARNING, never a failure by
    itself;
  * fail-closed on frontmatter contradicting reality and on declared paths
    that escape the project root.

Gates: G-W5-DELTA, G-W5-CONSISTENCY, G-SPLIT-IMPORT.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

RDX_TEA_DIR = Path(__file__).resolve().parent.parent.parent
SCRIPTS = RDX_TEA_DIR / "poc" / "install-tree" / "_bmad" / "rdx-tea" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import workspace_delta as wd  # noqa: E402


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


# --------------------------------------------------- collect_workspace_delta

def test_w5_collect_delta_reports_created_and_hashes(tmp_path):
    proj = tmp_path / "proj"
    out = proj / "_bmad-output" / "test-artifacts"
    out.mkdir(parents=True)
    art = out / "plan.md"
    art.write_text("# plan\n", encoding="utf-8")
    delta = wd.collect_workspace_delta(project_root=proj, new_artefacts=[art])
    rel = "_bmad-output/test-artifacts/plan.md"
    assert delta["created_files"] == [rel]
    assert delta["deleted_files"] == []
    assert delta["hashes"][rel] == _sha(art)


def test_w5_collect_delta_classifies_modified_via_pre_snapshot(tmp_path):
    proj = tmp_path / "proj"
    out = proj / "_bmad-output"
    out.mkdir(parents=True)
    created = out / "new.md"
    created.write_text("new\n", encoding="utf-8")
    modified = out / "old.md"
    modified.write_text("changed\n", encoding="utf-8")
    pre = {str(modified.resolve()): "deadbeef"}
    delta = wd.collect_workspace_delta(
        project_root=proj, new_artefacts=[created, modified], pre_snapshot=pre)
    assert delta["created_files"] == ["_bmad-output/new.md"]
    assert delta["modified_files"] == ["_bmad-output/old.md"]


def test_w5_collect_delta_declared_existing_and_missing(tmp_path):
    proj = tmp_path / "proj"
    out = proj / "_bmad-output"
    out.mkdir(parents=True)
    art = out / "story.md"
    art.write_text(
        "---\n"
        "generatedFiles:\n"
        "  - _bmad-output/story.md\n"
        "  - src/missing.rs\n"
        "---\n\n# body\n",
        encoding="utf-8",
    )
    delta = wd.collect_workspace_delta(project_root=proj, new_artefacts=[art])
    assert "_bmad-output/story.md" in delta["declared_generated_files"]
    assert "src/missing.rs" in delta["declared_generated_files"]
    assert delta["declared_existing_files"] == ["_bmad-output/story.md"]
    assert delta["declared_missing_files"] == ["src/missing.rs"]


# ----------------------------------------------- workspace_delta_consistency

def test_w5_delta_consistency_pass_when_all_declared_exist(tmp_path):
    proj = tmp_path / "proj"
    out = proj / "_bmad-output"
    out.mkdir(parents=True)
    art = out / "a.md"
    art.write_text(
        "---\ngeneratedFiles:\n  - _bmad-output/a.md\n---\n", encoding="utf-8")
    delta = wd.collect_workspace_delta(project_root=proj, new_artefacts=[art])
    status, reasons = wd.workspace_delta_consistency(delta)
    assert status == "PASS"
    assert reasons == []


def test_w5_delta_consistency_fails_on_declared_missing(tmp_path):
    proj = tmp_path / "proj"
    out = proj / "_bmad-output"
    out.mkdir(parents=True)
    art = out / "a.md"
    art.write_text(
        "---\ngeneratedFiles:\n  - src/never_written.rs\n---\n", encoding="utf-8")
    delta = wd.collect_workspace_delta(project_root=proj, new_artefacts=[art])
    status, reasons = wd.workspace_delta_consistency(delta)
    assert status == "FAIL"
    assert any("missing" in r for r in reasons)


def test_w5_delta_consistency_planned_escape_hatch(tmp_path):
    proj = tmp_path / "proj"
    out = proj / "_bmad-output"
    out.mkdir(parents=True)
    art = out / "a.md"
    art.write_text(
        "---\n"
        "generatedFiles:\n  - src/future.rs\n"
        "declarationPlannedNotGenerated: true\n"
        "---\n",
        encoding="utf-8",
    )
    delta = wd.collect_workspace_delta(project_root=proj, new_artefacts=[art])
    status, reasons = wd.workspace_delta_consistency(delta)
    assert status == "PASS", reasons


# ------------------------------------------------- check_artifact_consistency

def test_w5_artifact_consistency_phantom_claim_fails(tmp_path):
    proj = tmp_path / "proj"
    out = proj / "_bmad-output"
    out.mkdir(parents=True)
    art = out / "a.md"
    art.write_text(
        "---\ngeneratedFiles:\n  - src/phantom.rs\n---\n", encoding="utf-8")
    delta = wd.collect_workspace_delta(project_root=proj, new_artefacts=[art])
    findings = wd.check_artifact_consistency([art], proj, delta)
    assert findings["status"] == "FAIL"
    assert "src/phantom.rs" in findings["phantom_file_claims"]


def test_w5_artifact_consistency_real_artifact_passes(tmp_path):
    proj = tmp_path / "proj"
    out = proj / "_bmad-output"
    out.mkdir(parents=True)
    art = out / "a.md"
    art.write_text(
        "---\ngeneratedFiles:\n  - _bmad-output/a.md\n---\n# body\n",
        encoding="utf-8")
    delta = wd.collect_workspace_delta(project_root=proj, new_artefacts=[art])
    findings = wd.check_artifact_consistency([art], proj, delta)
    assert findings["status"] == "PASS", findings["reasons"]
    assert findings["phantom_file_claims"] == []


def test_w5_artifact_consistency_duplicate_frontmatter_is_warning(tmp_path):
    """Duplicate frontmatter keys across blocks are a WARNING, not a
    failure — the artifact still reconciles with reality."""
    proj = tmp_path / "proj"
    out = proj / "_bmad-output"
    out.mkdir(parents=True)
    art = out / "a.md"
    art.write_text(
        "---\nstoryId: A-1\n---\n\n"
        "some prose\n\n"
        "---\nstoryId: A-1\nlastStep: 3\n---\n",
        encoding="utf-8",
    )
    delta = wd.collect_workspace_delta(project_root=proj, new_artefacts=[art])
    findings = wd.check_artifact_consistency([art], proj, delta)
    assert findings["status"] == "PASS", findings["reasons"]
    assert any("storyId" in w for w in findings["warnings"])


def test_w5_artifact_consistency_escaping_path_fails(tmp_path):
    proj = tmp_path / "proj"
    out = proj / "_bmad-output"
    out.mkdir(parents=True)
    art = out / "a.md"
    art.write_text(
        "---\ngeneratedFiles:\n  - ../../etc/passwd\n---\n", encoding="utf-8")
    delta = wd.collect_workspace_delta(project_root=proj, new_artefacts=[art])
    findings = wd.check_artifact_consistency([art], proj, delta)
    assert findings["status"] == "FAIL"
    assert findings["nonexistent_project_paths"]


def test_w5_artifact_consistency_contradiction_fails(tmp_path):
    """A declared-file key that appears twice with values whose union has a
    file missing from reality is a contradiction (hard fail)."""
    proj = tmp_path / "proj"
    out = proj / "_bmad-output"
    out.mkdir(parents=True)
    art = out / "a.md"
    art.write_text(
        "---\ngeneratedFiles: [_bmad-output/a.md]\n---\n\n"
        "---\ngeneratedFiles: [src/ghost.rs]\n---\n",
        encoding="utf-8",
    )
    delta = wd.collect_workspace_delta(project_root=proj, new_artefacts=[art])
    findings = wd.check_artifact_consistency([art], proj, delta)
    assert findings["status"] == "FAIL"
    assert findings["contradictory_frontmatter"]


# --------------------------------------------------------- split / boundary

def test_w5_module_does_not_import_live_harness_or_evals():
    """The promoted module is on the shipped surface, so the authoritative
    G-SPLIT-IMPORT detector (contracts test) must find zero boundary hits in
    it — no eval-module import and no research-plane path literal."""
    sys.path.insert(0, str(RDX_TEA_DIR / "tests" / "contracts"))
    import test_l0_boundary_split_import as boundary  # noqa: E402

    src = (SCRIPTS / "workspace_delta.py").read_text(encoding="utf-8")
    assert boundary.find_violations(src) == [], (
        "production workspace_delta.py trips the G-SPLIT-IMPORT detector")
