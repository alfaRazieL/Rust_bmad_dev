"""Shared CI / hook test helpers — Phase 5.

Materialises real local git repositories in a tmp dir so the L6 hook
tests + L6 CI workflow tests + L7 mutation tests can run end-to-end
without needing a live GitHub repo.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
RDX_HOOKS_DIR = REPO_ROOT / ".claude" / "skills" / "rdx-hooks"
INSTALL_HOOK_SCRIPT = RDX_HOOKS_DIR / "scripts" / "install-hook.py"
UNINSTALL_HOOK_SCRIPT = RDX_HOOKS_DIR / "scripts" / "uninstall-hook.py"
CI_RUNNER_SCRIPT = REPO_ROOT / ".github" / "scripts" / "rdx-ci-runner.py"
RDX_GATE_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "rdx-gate.yml"
BRANCH_PROTECTION_DOC = REPO_ROOT / "docs" / "branch-protection.md"


def git(*args: str, cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    """Run git with deterministic identity to keep commits stable."""
    env = os.environ.copy()
    env.update(
        {
            "GIT_AUTHOR_NAME": "RDX Test",
            "GIT_AUTHOR_EMAIL": "rdx-test@example.com",
            "GIT_COMMITTER_NAME": "RDX Test",
            "GIT_COMMITTER_EMAIL": "rdx-test@example.com",
            # Hide local user config from sample repos.
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_CONFIG_SYSTEM": "/dev/null",
        }
    )
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=check,
    )


@dataclass
class SampleRepo:
    """A local git working tree paired with a bare 'origin'."""

    work: Path
    bare: Path

    def commit_file(self, relpath: str, content: str, message: str) -> str:
        p = self.work / relpath
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        git("add", relpath, cwd=self.work)
        git("commit", "-m", message, cwd=self.work)
        return git("rev-parse", "HEAD", cwd=self.work).stdout.strip()

    def write_story(self, story: dict) -> Path:
        path = self.work / "STORY.json"
        path.write_text(json.dumps(story, indent=2), encoding="utf-8")
        git("add", "STORY.json", cwd=self.work)
        git("commit", "-m", "story: contract", cwd=self.work)
        return path


@pytest.fixture
def sample_hook_repo(tmp_path: Path) -> SampleRepo:
    """Create a local repo + bare remote with one initial commit on main."""
    bare = tmp_path / "origin.git"
    work = tmp_path / "work"
    work.mkdir()
    git("init", "--bare", "--initial-branch=main", str(bare), cwd=tmp_path)
    git("init", "--initial-branch=main", cwd=work)
    git("remote", "add", "origin", str(bare), cwd=work)
    # baseline files matching sample-repo-spec.md
    (work / "Cargo.toml").write_text(
        '[package]\nname = "demo"\nversion = "0.0.0"\nedition = "2021"\n',
        encoding="utf-8",
    )
    (work / "src").mkdir()
    (work / "src" / "lib.rs").write_text("pub fn noop() {}\n", encoding="utf-8")
    (work / "src" / "auth").mkdir()
    (work / "src" / "auth" / "login.rs").write_text(
        "pub fn check_token(token: &str) -> bool { !token.is_empty() }\n",
        encoding="utf-8",
    )
    (work / "STORY.json").write_text(
        json.dumps(
            {
                "story_id": "STORY-DEMO-001",
                "protected_files": ["src/auth/**"],
                "risk_tags": [],
                "agent_activated_packs": [],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    git("add", ".", cwd=work)
    git("commit", "-m", "baseline", cwd=work)
    git("push", "-u", "origin", "main", cwd=work)
    return SampleRepo(work=work, bare=bare)


@pytest.fixture
def sample_ci_repo(tmp_path: Path) -> SampleRepo:
    """Create a local repo with main + a `pr-head` branch ready to diff.

    No bare remote — the L6 CI tests do not need a push surface, they
    only need two refs and the rdx-ci-runner script.
    """
    work = tmp_path / "work"
    work.mkdir()
    git("init", "--initial-branch=main", cwd=work)
    (work / "Cargo.toml").write_text(
        '[package]\nname = "demo"\nversion = "0.0.0"\nedition = "2021"\n',
        encoding="utf-8",
    )
    (work / "src").mkdir()
    (work / "src" / "lib.rs").write_text("pub fn noop() {}\n", encoding="utf-8")
    (work / "src" / "auth").mkdir()
    (work / "src" / "auth" / "login.rs").write_text(
        "pub fn check_token(token: &str) -> bool { !token.is_empty() }\n",
        encoding="utf-8",
    )
    (work / "STORY.json").write_text(
        json.dumps(
            {
                "story_id": "STORY-CI-001",
                "protected_files": ["src/auth/**"],
                "risk_tags": [],
                "agent_activated_packs": [],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    git("add", ".", cwd=work)
    git("commit", "-m", "baseline", cwd=work)
    git("checkout", "-b", "pr-head", cwd=work)
    return SampleRepo(work=work, bare=Path("/dev/null"))


@pytest.fixture(scope="session")
def hook_install_script() -> Path:
    return INSTALL_HOOK_SCRIPT


@pytest.fixture(scope="session")
def hook_uninstall_script() -> Path:
    return UNINSTALL_HOOK_SCRIPT


@pytest.fixture(scope="session")
def ci_runner_script() -> Path:
    return CI_RUNNER_SCRIPT


@pytest.fixture(scope="session")
def rdx_gate_workflow() -> Path:
    return RDX_GATE_WORKFLOW


@pytest.fixture(scope="session")
def branch_protection_doc() -> Path:
    return BRANCH_PROTECTION_DOC


def run_script(script: Path, *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(script), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
