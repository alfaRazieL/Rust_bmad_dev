"""L6 — pre-push hook end-to-end tests.

Closes (Phase 5 entry-gate):
  T-L6-HOOK-001  pre-push blocks push when validator returns exit 1
  T-L6-HOOK-002  pre-push permits push when validator returns exit 0
  T-L6-HOOK-003  pre-push chains with pre-existing hook
  T-L6-HOOK-004  uninstall restores pre-existing hook
  T-L6-HOOK-005  `git push --no-verify` bypass is possible but observable

These tests materialise a real local git repo + bare remote in tmp_path
and invoke the pre-push hook through actual `git push`. No
GitHub-Actions runtime required.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from .conftest import git, run_script


def _install_hook(repo_work: Path, install_script: Path, extra: list[str] | None = None) -> None:
    extra = extra or []
    r = run_script(install_script, "--project-root", str(repo_work), *extra)
    assert r.returncode == 0, f"install-hook failed: {r.stderr or r.stdout}"


def _uninstall_hook(repo_work: Path, uninstall_script: Path) -> subprocess.CompletedProcess:
    return run_script(uninstall_script, "--project-root", str(repo_work))


def _push(repo_work: Path, branch: str = "main", *, extra: list[str] | None = None) -> subprocess.CompletedProcess:
    extra = extra or []
    env = os.environ.copy()
    env.update(
        {
            "GIT_AUTHOR_NAME": "RDX Test",
            "GIT_AUTHOR_EMAIL": "rdx-test@example.com",
            "GIT_COMMITTER_NAME": "RDX Test",
            "GIT_COMMITTER_EMAIL": "rdx-test@example.com",
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_CONFIG_SYSTEM": "/dev/null",
        }
    )
    return subprocess.run(
        ["git", "push", *extra, "origin", branch],
        cwd=repo_work,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


# ---------------------------------------------------------------------------
# T-L6-HOOK-001 — push blocked when validator exits 1
# ---------------------------------------------------------------------------


def test_l6_hook_001_blocks_push_on_validator_fail(sample_hook_repo, hook_install_script):
    _install_hook(sample_hook_repo.work, hook_install_script)

    # Author a diff that violates CORE-007 (protected file touched, no exception).
    auth_login = sample_hook_repo.work / "src" / "auth" / "login.rs"
    auth_login.write_text(
        auth_login.read_text(encoding="utf-8") + "\npub fn backdoor() {}\n",
        encoding="utf-8",
    )
    git("add", "src/auth/login.rs", cwd=sample_hook_repo.work)
    git("commit", "-m", "CORE-007 violation", cwd=sample_hook_repo.work)

    pre_push_sha = git(
        "rev-parse", "refs/remotes/origin/main", cwd=sample_hook_repo.work
    ).stdout.strip()
    r = _push(sample_hook_repo.work)
    post_push_sha = git(
        "rev-parse", "refs/remotes/origin/main", cwd=sample_hook_repo.work
    ).stdout.strip()

    assert r.returncode != 0, f"push should have been blocked; stderr=\n{r.stderr}"
    assert pre_push_sha == post_push_sha, "remote ref must not have advanced"
    combined = (r.stderr or "") + (r.stdout or "")
    assert "RDX" in combined or "rdx-validator" in combined, (
        "hook output should announce RDX gate fail"
    )


# ---------------------------------------------------------------------------
# T-L6-HOOK-002 — push permitted when validator exits 0
# ---------------------------------------------------------------------------


def test_l6_hook_002_permits_clean_push(sample_hook_repo, hook_install_script):
    _install_hook(sample_hook_repo.work, hook_install_script)

    # Author a clean diff (non-protected file, no router triggers).
    lib_rs = sample_hook_repo.work / "src" / "lib.rs"
    lib_rs.write_text(
        lib_rs.read_text(encoding="utf-8") + "\npub fn added_noop() {}\n",
        encoding="utf-8",
    )
    git("add", "src/lib.rs", cwd=sample_hook_repo.work)
    git("commit", "-m", "harmless addition", cwd=sample_hook_repo.work)

    r = _push(sample_hook_repo.work)
    assert r.returncode == 0, f"clean push should succeed; stderr=\n{r.stderr}"


# ---------------------------------------------------------------------------
# T-L6-HOOK-003 — chaining preserves pre-existing hook
# ---------------------------------------------------------------------------


def test_l6_hook_003_chains_existing_hook(sample_hook_repo, hook_install_script):
    hooks_dir = sample_hook_repo.work / ".git" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    pre_existing = hooks_dir / "pre-push"
    sentinel = sample_hook_repo.work / "EXISTING_HOOK_RAN.txt"
    pre_existing.write_text(
        "#!/usr/bin/env sh\n"
        f'echo "existing pre-push fired" > "{sentinel}"\n'
        "exit 0\n",
        encoding="utf-8",
    )
    pre_existing.chmod(0o755)

    _install_hook(sample_hook_repo.work, hook_install_script)

    # Clean diff so both hooks return 0 and push succeeds.
    lib_rs = sample_hook_repo.work / "src" / "lib.rs"
    lib_rs.write_text(
        lib_rs.read_text(encoding="utf-8") + "\npub fn another_noop() {}\n",
        encoding="utf-8",
    )
    git("add", "src/lib.rs", cwd=sample_hook_repo.work)
    git("commit", "-m", "noop", cwd=sample_hook_repo.work)

    r = _push(sample_hook_repo.work)
    assert r.returncode == 0, f"push should succeed; stderr=\n{r.stderr}"
    assert sentinel.exists(), "pre-existing hook should have fired alongside RDX hook"


# ---------------------------------------------------------------------------
# T-L6-HOOK-004 — uninstall restores pre-existing hook
# ---------------------------------------------------------------------------


def test_l6_hook_004_uninstall_restores_existing(sample_hook_repo, hook_install_script, hook_uninstall_script):
    hooks_dir = sample_hook_repo.work / ".git" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    pre_existing = hooks_dir / "pre-push"
    original_body = (
        "#!/usr/bin/env sh\n"
        '# user-pre-existing hook\n'
        "exit 0\n"
    )
    pre_existing.write_text(original_body, encoding="utf-8")
    pre_existing.chmod(0o755)
    original_sha = pre_existing.read_bytes()

    _install_hook(sample_hook_repo.work, hook_install_script)

    # Hook should now be the RDX hook (different bytes).
    assert pre_existing.read_bytes() != original_sha

    r = _uninstall_hook(sample_hook_repo.work, hook_uninstall_script)
    assert r.returncode == 0, f"uninstall failed: {r.stderr or r.stdout}"

    assert pre_existing.exists(), "pre-existing hook should have been restored"
    assert pre_existing.read_bytes() == original_sha, (
        "pre-existing hook content was not restored byte-equal"
    )


# ---------------------------------------------------------------------------
# T-L6-HOOK-005 — --no-verify bypass documented behavior
# ---------------------------------------------------------------------------


def test_l6_hook_005_no_verify_bypass(sample_hook_repo, hook_install_script):
    _install_hook(sample_hook_repo.work, hook_install_script)

    auth_login = sample_hook_repo.work / "src" / "auth" / "login.rs"
    auth_login.write_text(
        auth_login.read_text(encoding="utf-8") + "\npub fn backdoor() {}\n",
        encoding="utf-8",
    )
    git("add", "src/auth/login.rs", cwd=sample_hook_repo.work)
    git("commit", "-m", "CORE-007 violation", cwd=sample_hook_repo.work)

    blocked = _push(sample_hook_repo.work)
    assert blocked.returncode != 0, "hook must block first"

    bypassed = _push(sample_hook_repo.work, extra=["--no-verify"])
    assert bypassed.returncode == 0, f"--no-verify must succeed; stderr={bypassed.stderr}"
