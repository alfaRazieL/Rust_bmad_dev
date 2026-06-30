"""L8 — Cat-4 specialist approval driver tests.

Closes (Phase 8 exit gate):
  T-L8-CAT4-001 — unsafe diff, no approval → APPROVAL_REQUIRED + exit 3
  T-L8-CAT4-002 — unsafe diff, valid approval → PASS + exit 0
  T-L8-CAT4-003 — approval present but approver_identity unauthorized → APPROVAL_REQUIRED
  T-L8-CAT4-005 — approval schema enforcement (single end-to-end happy path through validator)
  T-L7-APPROVAL-REUSE-001 — approval pinned to diff_digest by file name; new diff → re-blocked
  T-L8-GOV-001 — protected governance path (here: _bmad/rust-kb/**) requires governance role

Each test prepares an isolated project tree under tmp_path:

  <tmp>/
    _bmad/rdx/approvers.yaml
    _bmad/rdx/approvals/<digest>.json   (only when an approval is being supplied)
    diff.patch                          (copied from tests/fixtures/diffs/...)
    story.json

and invokes the validator with --project-root pointing at it. The validator
must (Phase 8) read approvers.yaml + approvals/, match changed paths against
patterns, and resolve each Cat-4 verdict to PASS only when an authorised
approval JSON is present for the current diff_digest.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURES = REPO_ROOT / "tests" / "fixtures"
SAMPLE_APPROVERS = FIXTURES / "approvers" / "sample-approvers" / "approvers.yaml"


def _sha(diff_text: str) -> str:
    return hashlib.sha256(diff_text.encode("utf-8")).hexdigest()


def _run_validator(project_root: Path, diff_file: Path, story_file: Path | None = None,
                   evidence_out: Path | None = None) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT / "rdx-validator")
    cmd = [
        sys.executable, "-m", "rdx_validator",
        "--project-root", str(project_root),
        "--diff-file", str(diff_file),
        "--contracts-dir", str(REPO_ROOT / "tests" / "contracts"),
        "--mode", "MODE_4",
        "--quiet",
    ]
    if story_file is not None:
        cmd += ["--story", str(story_file)]
    if evidence_out is not None:
        cmd += ["--evidence-out", str(evidence_out)]
    return subprocess.run(cmd, capture_output=True, text=True, env=env, check=False)


def _scaffold_project(tmp_path: Path, diff_fixture: Path) -> tuple[Path, Path, str]:
    """Create the in-repo layout the validator expects and return key paths.

    Returns (project_root, diff_file_in_project, diff_digest).
    """
    (tmp_path / "_bmad" / "rdx" / "approvals").mkdir(parents=True, exist_ok=True)
    shutil.copy(SAMPLE_APPROVERS, tmp_path / "_bmad" / "rdx" / "approvers.yaml")
    diff_dst = tmp_path / "diff.patch"
    shutil.copy(diff_fixture, diff_dst)
    diff_digest = _sha(diff_dst.read_text(encoding="utf-8"))
    story = {"story_id": "STORY-PHASE8-CAT4", "protected_files": [], "risk_tags": [],
             "agent_activated_packs": [], "router_suppressions": []}
    (tmp_path / "story.json").write_text(json.dumps(story), encoding="utf-8")
    return tmp_path, diff_dst, diff_digest


def _write_approval(project_root: Path, diff_digest: str, *, rule_id: str,
                    approver_identity: str, approver_role: str,
                    decision: str = "approved", paths: list[str] | None = None) -> Path:
    approval = {
        "approval_schema_version": "v1",
        "rule_id": rule_id,
        "approver_identity": approver_identity,
        "approver_role": approver_role,
        "head_sha": "0123456789abcdef0123456789abcdef01234567",
        "diff_digest": diff_digest,
        "timestamp": "2026-06-30T12:00:00Z",
        "scope": {"paths": paths or []},
        "decision": decision,
    }
    out = project_root / "_bmad" / "rdx" / "approvals" / f"{diff_digest}.json"
    out.write_text(json.dumps(approval, indent=2), encoding="utf-8")
    return out


# ---------------------------------------------------------------------------
# T-L8-CAT4-001 — no approval → blocked
# ---------------------------------------------------------------------------
def test_t_l8_cat4_001_unsafe_no_approval_blocks(tmp_path: Path):
    project_root, diff_file, _digest = _scaffold_project(
        tmp_path, FIXTURES / "diffs" / "cat4-unsafe" / "positive.diff"
    )
    out = tmp_path / "evidence.json"
    res = _run_validator(project_root, diff_file,
                         story_file=project_root / "story.json", evidence_out=out)
    assert res.returncode == 3, f"expected exit 3, got {res.returncode}\nstderr: {res.stderr}"
    envelope = json.loads(out.read_text(encoding="utf-8"))
    assert envelope["aggregate"]["verdict"] == "BLOCKED"
    rule = envelope["rules"]["RP-UNSAFE-001"]
    assert rule["verdict"] == "APPROVAL_REQUIRED"


# ---------------------------------------------------------------------------
# T-L8-CAT4-002 — valid approval → PASS
# ---------------------------------------------------------------------------
def test_t_l8_cat4_002_valid_approval_passes(tmp_path: Path):
    project_root, diff_file, digest = _scaffold_project(
        tmp_path, FIXTURES / "diffs" / "cat4-unsafe" / "positive.diff"
    )
    _write_approval(
        project_root, digest,
        rule_id="RP-UNSAFE-001",
        approver_identity="alice@example.com",
        approver_role="unsafe-reviewers",
        paths=["src/unsafe/foo.rs"],
    )
    out = tmp_path / "evidence.json"
    res = _run_validator(project_root, diff_file,
                         story_file=project_root / "story.json", evidence_out=out)
    assert res.returncode == 0, f"expected exit 0, got {res.returncode}\nstderr: {res.stderr}"
    envelope = json.loads(out.read_text(encoding="utf-8"))
    rule = envelope["rules"]["RP-UNSAFE-001"]
    assert rule["verdict"] == "PASS", f"expected PASS after approval, got {rule}"
    assert envelope["aggregate"]["verdict"] in ("PASS", "NOT_APPLICABLE")


# ---------------------------------------------------------------------------
# T-L8-CAT4-003 — unauthorized approver → still blocked
# ---------------------------------------------------------------------------
def test_t_l8_cat4_003_unauthorized_approver_blocks(tmp_path: Path):
    project_root, diff_file, digest = _scaffold_project(
        tmp_path, FIXTURES / "diffs" / "cat4-unsafe" / "positive.diff"
    )
    _write_approval(
        project_root, digest,
        rule_id="RP-UNSAFE-001",
        approver_identity="mallory@example.com",
        approver_role="unsafe-reviewers",
        paths=["src/unsafe/foo.rs"],
    )
    out = tmp_path / "evidence.json"
    res = _run_validator(project_root, diff_file,
                         story_file=project_root / "story.json", evidence_out=out)
    assert res.returncode == 3, f"expected exit 3, got {res.returncode}\nstderr: {res.stderr}"
    envelope = json.loads(out.read_text(encoding="utf-8"))
    rule = envelope["rules"]["RP-UNSAFE-001"]
    assert rule["verdict"] == "APPROVAL_REQUIRED"
    msg = (rule.get("message") or "").lower()
    assert "identity" in msg or "unauthorised" in msg or "unauthorized" in msg, (
        f"verdict message must explain identity mismatch, got: {rule}"
    )


# ---------------------------------------------------------------------------
# T-L8-CAT4-005 — schema enforcement (one end-to-end happy path)
# A malformed approval file (missing required field) must NOT satisfy the rule
# even when the approver identity is otherwise valid — validator falls back to
# APPROVAL_REQUIRED with a schema-violation message.
# ---------------------------------------------------------------------------
def test_t_l8_cat4_005_malformed_approval_blocks(tmp_path: Path):
    project_root, diff_file, digest = _scaffold_project(
        tmp_path, FIXTURES / "diffs" / "cat4-unsafe" / "positive.diff"
    )
    bad = {
        "approval_schema_version": "v1",
        # missing rule_id on purpose
        "approver_identity": "alice@example.com",
        "approver_role": "unsafe-reviewers",
        "head_sha": "0123456789abcdef0123456789abcdef01234567",
        "diff_digest": digest,
        "timestamp": "2026-06-30T12:00:00Z",
        "scope": {"paths": ["src/unsafe/foo.rs"]},
        "decision": "approved",
    }
    (project_root / "_bmad" / "rdx" / "approvals" / f"{digest}.json").write_text(
        json.dumps(bad), encoding="utf-8"
    )
    out = tmp_path / "evidence.json"
    res = _run_validator(project_root, diff_file,
                         story_file=project_root / "story.json", evidence_out=out)
    assert res.returncode == 3
    envelope = json.loads(out.read_text(encoding="utf-8"))
    rule = envelope["rules"]["RP-UNSAFE-001"]
    assert rule["verdict"] == "APPROVAL_REQUIRED"
    assert "schema" in (rule.get("message") or "").lower(), (
        f"verdict message must explain schema failure, got: {rule}"
    )


# ---------------------------------------------------------------------------
# T-L7-APPROVAL-REUSE-001 — diff change invalidates approval (B1 binding)
# ---------------------------------------------------------------------------
def test_t_l7_approval_reuse_001_diff_change_invalidates(tmp_path: Path):
    project_root, original_diff, d1 = _scaffold_project(
        tmp_path, FIXTURES / "diffs" / "cat4-unsafe" / "positive.diff"
    )
    # Approve D1
    _write_approval(
        project_root, d1,
        rule_id="RP-UNSAFE-001",
        approver_identity="alice@example.com",
        approver_role="unsafe-reviewers",
        paths=["src/unsafe/foo.rs"],
    )
    # Sanity: with D1 approval, the original diff PASSes.
    out1 = tmp_path / "evidence-1.json"
    res1 = _run_validator(project_root, original_diff,
                          story_file=project_root / "story.json", evidence_out=out1)
    assert res1.returncode == 0, f"baseline PASS expected, got {res1.returncode}"

    # Now author replaces the diff with a revised one (D2 ≠ D1).
    revised = project_root / "diff.patch"
    shutil.copy(FIXTURES / "diffs" / "cat4-unsafe" / "positive-revised.diff", revised)
    d2 = _sha(revised.read_text(encoding="utf-8"))
    assert d1 != d2, "revised fixture must differ"

    # The D1 approval file still exists but no D2 approval file → re-blocked.
    out2 = tmp_path / "evidence-2.json"
    res2 = _run_validator(project_root, revised,
                          story_file=project_root / "story.json", evidence_out=out2)
    assert res2.returncode == 3, f"diff change must re-block, got {res2.returncode}"
    env2 = json.loads(out2.read_text(encoding="utf-8"))
    assert env2["rules"]["RP-UNSAFE-001"]["verdict"] == "APPROVAL_REQUIRED"


# ---------------------------------------------------------------------------
# T-L8-GOV-001 — KB / validator / schema / workflow modifications need governance
# ---------------------------------------------------------------------------
def test_t_l8_gov_001_kb_change_requires_governance(tmp_path: Path):
    project_root, diff_file, _digest = _scaffold_project(
        tmp_path, FIXTURES / "diffs" / "cat4-governance" / "kb-change.diff"
    )
    out = tmp_path / "evidence.json"
    res = _run_validator(project_root, diff_file,
                         story_file=project_root / "story.json", evidence_out=out)
    assert res.returncode == 3, f"governance path must block, got {res.returncode}\nstderr: {res.stderr}"
    envelope = json.loads(out.read_text(encoding="utf-8"))
    # The synthesised governance rule id is GOV-KB-001 (per sample approvers.yaml).
    assert "GOV-KB-001" in envelope["rules"], envelope["rules"]
    rule = envelope["rules"]["GOV-KB-001"]
    assert rule["verdict"] == "APPROVAL_REQUIRED"
    assert (rule.get("message") or "").lower().__contains__("governance")
