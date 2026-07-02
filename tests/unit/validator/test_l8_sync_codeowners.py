"""L8 — sync-codeowners CLI.

Closes:
  T-L8-CAT4-004 — sync-codeowners generates a deterministic CODEOWNERS section
                  from approvers.yaml, preserves foreign manual entries via a
                  marker block, and is idempotent (re-running yields the same
                  file byte-for-byte).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / ".claude" / "skills" / "rdx-setup" / "scripts" / "sync_codeowners.py"
SAMPLE = REPO_ROOT / "tests" / "fixtures" / "approvers" / "sample-approvers"


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=cwd, capture_output=True, text=True, env=env, check=False,
    )


def _golden_text() -> str:
    return (SAMPLE / "CODEOWNERS.golden").read_text(encoding="utf-8")


def test_t_l8_cat4_004_generates_codeowners_from_sample(tmp_path: Path):
    """sync-codeowners with pre-existing foreign entries preserves them and appends
    the RDX-managed marker block in deterministic order."""
    project_root = tmp_path
    (project_root / "_bmad" / "rdx").mkdir(parents=True, exist_ok=True)
    (project_root / "_bmad" / "rdx" / "approvers.yaml").write_text(
        (SAMPLE / "approvers.yaml").read_text(encoding="utf-8"), encoding="utf-8"
    )
    (project_root / ".github").mkdir(parents=True, exist_ok=True)
    (project_root / ".github" / "CODEOWNERS").write_text(
        (SAMPLE / "CODEOWNERS.pre-existing").read_text(encoding="utf-8"), encoding="utf-8"
    )
    res = _run(["--project-root", str(project_root)], cwd=project_root)
    assert res.returncode == 0, f"unexpected exit {res.returncode}; stderr={res.stderr}"
    out = (project_root / ".github" / "CODEOWNERS").read_text(encoding="utf-8")
    assert out == _golden_text(), (
        "generated CODEOWNERS does not match golden\n"
        f"--- expected ---\n{_golden_text()}\n--- got ---\n{out}"
    )


def test_t_l8_cat4_004_idempotent(tmp_path: Path):
    """Re-running sync-codeowners must yield the same file (no marker drift)."""
    project_root = tmp_path
    (project_root / "_bmad" / "rdx").mkdir(parents=True, exist_ok=True)
    (project_root / "_bmad" / "rdx" / "approvers.yaml").write_text(
        (SAMPLE / "approvers.yaml").read_text(encoding="utf-8"), encoding="utf-8"
    )
    (project_root / ".github").mkdir(parents=True, exist_ok=True)
    (project_root / ".github" / "CODEOWNERS").write_text(
        (SAMPLE / "CODEOWNERS.pre-existing").read_text(encoding="utf-8"), encoding="utf-8"
    )
    for _ in range(3):
        res = _run(["--project-root", str(project_root)], cwd=project_root)
        assert res.returncode == 0, f"unexpected exit {res.returncode}; stderr={res.stderr}"
    out = (project_root / ".github" / "CODEOWNERS").read_text(encoding="utf-8")
    assert out == _golden_text(), "idempotency violated — output drifts across runs"
