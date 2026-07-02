"""T-L7-HA-APPROVERS-FORGERY-001 — Phase 9 HA-specific bypass path.

Scenario: a PR appends an attacker identity to
`roles.unsafe-reviewers.identities` in `_bmad/rdx/approvers.yaml`. If
accepted, the attacker could then commit Cat-4 approval JSONs on their
own unsafe code in subsequent PRs.

Defense layer: L7 governance — `_bmad/rdx/**` is on the HA-baseline
governance pattern (see docs/threat-model.md §6) which requires the
`governance` role to approve.  The validator synthesises an
APPROVAL_REQUIRED rule (rule_id GOV-RDX-001) and exits 3 until a
governance-role approval pinned to the current diff_digest is committed.

Catalogued in RDX_TEST_CASES.yaml as T-L7-HA-APPROVERS-FORGERY-001.
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

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = REPO_ROOT / "tests" / "fixtures"
HA_APPROVERS = FIXTURES / "approvers" / "ha-baseline" / "approvers.yaml"
DIFF_FIXTURE = FIXTURES / "diffs" / "ha-approvers-forgery" / "positive.diff"


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _scaffold(tmp_path: Path) -> tuple[Path, Path, str]:
    (tmp_path / "_bmad" / "rdx" / "approvals").mkdir(parents=True, exist_ok=True)
    shutil.copy(HA_APPROVERS, tmp_path / "_bmad" / "rdx" / "approvers.yaml")
    diff_dst = tmp_path / "diff.patch"
    shutil.copy(DIFF_FIXTURE, diff_dst)
    diff_text = diff_dst.read_text(encoding="utf-8")
    digest = _sha(diff_text)
    (tmp_path / "story.json").write_text(
        json.dumps(
            {
                "story_id": "STORY-HA-APPROVERS-FORGERY",
                "protected_files": [],
                "risk_tags": [],
                "router_suppressions": [],
            }
        ),
        encoding="utf-8",
    )
    evidence = {
        "rdx_schema_version": "v1",
        "story_id": "STORY-HA-APPROVERS-FORGERY",
        "head_sha": "0" * 40,
        "base_sha": "f" * 40,
        "diff_digest": digest,
        "mode": "MODE_4",
        "rules": {
            "CORE-011": {
                "category": 1,
                "verdict": "PASS",
                "severity": "INFO",
                "author": "VALIDATOR",
                "evidence": [
                    {
                        "command": "cargo check --workspace --all-targets",
                        "exit_code": 0,
                        "output_digest": "a" * 64,
                    }
                ],
            }
        },
        "exceptions": [],
        "approvals": [],
        "aggregate": {"verdict": "PASS", "exit_code": 0},
    }
    (tmp_path / "evidence-in.json").write_text(json.dumps(evidence), encoding="utf-8")
    return tmp_path, diff_dst, digest


def _run_validator(project_root: Path, diff_file: Path, out: Path) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT / "rdx-validator")
    return subprocess.run(
        [
            sys.executable, "-m", "rdx_validator",
            "--project-root", str(project_root),
            "--diff-file", str(diff_file),
            "--contracts-dir", str(REPO_ROOT / "tests" / "contracts"),
            "--story", str(project_root / "story.json"),
            "--mode", "MODE_4",
            "--evidence-in", str(project_root / "evidence-in.json"),
            "--evidence-out", str(out),
            "--quiet",
        ],
        capture_output=True, text=True, env=env, check=False,
    )


# -- structural: fixture targets approvers.yaml ---------------------------------


def test_l7_ha_approvers_forgery_fixture_targets_approvers_yaml():
    text = DIFF_FIXTURE.read_text(encoding="utf-8")
    assert "_bmad/rdx/approvers.yaml" in text
    # The diff must add a new identity line, not just whitespace.
    assert "mallory@attacker.example" in text


def test_l7_ha_approvers_forgery_attacker_not_in_baseline():
    """Sanity: the attacker identity is NOT in the baseline approvers.yaml
    that ships with the fixture — i.e., the forgery is a real addition,
    not a no-op."""

    baseline = HA_APPROVERS.read_text(encoding="utf-8")
    assert "mallory@attacker.example" not in baseline


# -- runtime: validator blocks the unapproved approvers.yaml mutation -----------


def test_l7_ha_approvers_forgery_blocks_without_governance_approval(tmp_path: Path):
    project, diff, _digest = _scaffold(tmp_path)
    out = tmp_path / "evidence.json"
    r = _run_validator(project, diff, out)
    assert r.returncode == 3, (
        f"approvers.yaml forgery PR must be blocked (exit 3), got {r.returncode}\n"
        f"stderr={r.stderr[-2000:]}"
    )
    env = json.loads(out.read_text(encoding="utf-8"))
    assert "GOV-RDX-001" in env["rules"], (
        f"expected GOV-RDX-001 in envelope rules; got {list(env['rules'])}"
    )
    rule = env["rules"]["GOV-RDX-001"]
    assert rule["verdict"] == "APPROVAL_REQUIRED"
    assert rule["category"] == 4


def test_l7_ha_approvers_forgery_unauthorized_approver_still_blocks(tmp_path: Path):
    """Even if the attacker also commits an approval JSON, an identity not
    in the governance role's identity list cannot self-approve."""

    project, diff, digest = _scaffold(tmp_path)
    approval = {
        "approval_schema_version": "v1",
        "rule_id": "GOV-RDX-001",
        "approver_identity": "mallory@attacker.example",
        "approver_role": "governance",
        "head_sha": "0" * 40,
        "diff_digest": digest,
        "timestamp": "2026-06-30T12:00:00Z",
        "scope": {"paths": ["_bmad/rdx/approvers.yaml"]},
        "decision": "approved",
    }
    (project / "_bmad" / "rdx" / "approvals" / f"{digest}.json").write_text(
        json.dumps(approval, indent=2), encoding="utf-8"
    )
    out = tmp_path / "evidence.json"
    r = _run_validator(project, diff, out)
    assert r.returncode == 3, (
        f"unauthorised approver must not unblock (exit 3 expected), got {r.returncode}\n"
        f"stderr={r.stderr[-2000:]}"
    )
    env = json.loads(out.read_text(encoding="utf-8"))
    assert env["rules"]["GOV-RDX-001"]["verdict"] == "APPROVAL_REQUIRED"
