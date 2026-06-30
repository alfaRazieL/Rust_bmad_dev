"""T-V6-ACC-04 — End-to-end Cat-4 acceptance.

Steps (from RDX_TEST_CASES.yaml):
  unsafe change → blocked → approval committed → unblocked → diff changes → re-blocked

This test exercises the full Phase 8 stack as a black box. It is the
acceptance gate for the V6 Cat-4 deliverable.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURES = REPO_ROOT / "tests" / "fixtures"
SAMPLE_APPROVERS = FIXTURES / "approvers" / "sample-approvers" / "approvers.yaml"


def _sha(diff_text: str) -> str:
    return hashlib.sha256(diff_text.encode("utf-8")).hexdigest()


def _run_validator(project_root: Path, diff_file: Path, evidence_out: Path) -> subprocess.CompletedProcess:
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
            "--evidence-out", str(evidence_out),
            "--quiet",
        ],
        capture_output=True, text=True, env=env, check=False,
    )


def _write_cargo_evidence(project_root: Path, diff_digest: str) -> None:
    """Write a CORE-011 PASS stub pinned to the given digest so the Cat-4 path
    is the only blocking concern."""
    evidence = {
        "rdx_schema_version": "v1",
        "story_id": "STORY-V6-ACC-04",
        "head_sha": "0123456789abcdef0123456789abcdef01234567",
        "base_sha": "fedcba9876543210fedcba9876543210fedcba98",
        "diff_digest": diff_digest,
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
                        "output_digest": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
                    }
                ],
            }
        },
        "exceptions": [],
        "approvals": [],
        "aggregate": {"verdict": "PASS", "exit_code": 0},
    }
    (project_root / "evidence-in.json").write_text(json.dumps(evidence), encoding="utf-8")


def test_t_v6_acc_04_cat4_full_cycle(tmp_path: Path):
    project_root = tmp_path
    (project_root / "_bmad" / "rdx" / "approvals").mkdir(parents=True, exist_ok=True)
    shutil.copy(SAMPLE_APPROVERS, project_root / "_bmad" / "rdx" / "approvers.yaml")
    (project_root / "story.json").write_text(
        json.dumps({"story_id": "STORY-V6-ACC-04"}), encoding="utf-8"
    )

    # Step 1 — unsafe diff with no approval → BLOCKED.
    diff_v1 = project_root / "diff.patch"
    shutil.copy(FIXTURES / "diffs" / "cat4-unsafe" / "positive.diff", diff_v1)
    digest_v1 = _sha(diff_v1.read_text(encoding="utf-8"))
    _write_cargo_evidence(project_root, digest_v1)
    ev1 = project_root / "ev1.json"
    r1 = _run_validator(project_root, diff_v1, ev1)
    assert r1.returncode == 3, f"step 1: expected exit 3, got {r1.returncode}\nstderr={r1.stderr}"
    env1 = json.loads(ev1.read_text(encoding="utf-8"))
    assert env1["rules"]["RP-UNSAFE-001"]["verdict"] == "APPROVAL_REQUIRED"

    # Step 2 — specialist commits approval JSON pinned to digest_v1 → PASS.
    approval = {
        "approval_schema_version": "v1",
        "rule_id": "RP-UNSAFE-001",
        "approver_identity": "alice@example.com",
        "approver_role": "unsafe-reviewers",
        "head_sha": "0123456789abcdef0123456789abcdef01234567",
        "diff_digest": digest_v1,
        "timestamp": "2026-06-30T12:00:00Z",
        "scope": {"paths": ["src/unsafe/foo.rs"]},
        "decision": "approved",
    }
    (project_root / "_bmad" / "rdx" / "approvals" / f"{digest_v1}.json").write_text(
        json.dumps(approval, indent=2), encoding="utf-8"
    )
    ev2 = project_root / "ev2.json"
    r2 = _run_validator(project_root, diff_v1, ev2)
    assert r2.returncode == 0, f"step 2: expected exit 0, got {r2.returncode}\nstderr={r2.stderr}"
    env2 = json.loads(ev2.read_text(encoding="utf-8"))
    assert env2["rules"]["RP-UNSAFE-001"]["verdict"] == "PASS"

    # Step 3 — author revises the diff (digest changes) → re-blocked.
    diff_v2 = project_root / "diff.patch"
    shutil.copy(FIXTURES / "diffs" / "cat4-unsafe" / "positive-revised.diff", diff_v2)
    digest_v2 = _sha(diff_v2.read_text(encoding="utf-8"))
    assert digest_v1 != digest_v2
    _write_cargo_evidence(project_root, digest_v2)
    ev3 = project_root / "ev3.json"
    r3 = _run_validator(project_root, diff_v2, ev3)
    assert r3.returncode == 3, f"step 3: expected exit 3, got {r3.returncode}\nstderr={r3.stderr}"
    env3 = json.loads(ev3.read_text(encoding="utf-8"))
    assert env3["rules"]["RP-UNSAFE-001"]["verdict"] == "APPROVAL_REQUIRED"
