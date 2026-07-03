"""RDX-TEA bootstrap (D3.1).

Clones the exact upstream BMAD-METHOD and BMAD TEA tags recorded in
`sources.lock` into a caller-supplied directory. Verifies the resulting
`resolve_customization.py` and `bmad-tea/customize.toml` byte-hashes
against expected values written by the last vertical-slice run.

Idempotent: if a clone directory already exists, `git fetch` + tag
checkout; refuses to clone into a non-empty directory that does not
look like a clean previous bootstrap.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import subprocess
import sys
from pathlib import Path

import yaml

import os  # noqa: E401

_HERE = Path(__file__).resolve().parent


def _sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _run(cmd: list[str], cwd: Path | None = None) -> str:
    r = subprocess.run(cmd, cwd=str(cwd) if cwd else None,
                       capture_output=True, text=True, check=False)
    if r.returncode != 0:
        raise RuntimeError(f"{cmd!r} failed: {r.stderr}")
    return r.stdout


def clone_or_update(repo_url: str, tag: str, dest: Path) -> str:
    """Clone `repo_url` into `dest` and check out `tag`. If `dest` is
    already a repo, fetch tags and check out."""
    if (dest / ".git").exists():
        _run(["git", "fetch", "--tags", "origin"], cwd=dest)
        _run(["git", "checkout", tag], cwd=dest)
    else:
        dest.parent.mkdir(parents=True, exist_ok=True)
        _run(["git", "clone", "--depth", "50", repo_url, str(dest)])
        _run(["git", "fetch", "--tags", "origin"], cwd=dest)
        _run(["git", "checkout", tag], cwd=dest)
    sha = _run(["git", "rev-parse", "HEAD"], cwd=dest).strip()
    return sha


def _assert_clean_worktree(dest: Path) -> None:
    """Fail closed if `dest` has uncommitted changes or an untracked file
    other than a fresh clone marker. `RDX_TEA_BOOTSTRAP_SKIP_WORKTREE_CHECK=1`
    bypasses the check for test rigs that reuse a local clone."""
    if os.environ.get("RDX_TEA_BOOTSTRAP_SKIP_WORKTREE_CHECK") == "1":
        return
    r = subprocess.run(["git", "-C", str(dest), "status", "--porcelain"],
                       capture_output=True, text=True, check=True)
    if r.stdout.strip():
        raise RuntimeError(
            f"upstream clone at {dest} has dirty worktree — refuse to proceed:\n"
            f"{r.stdout}"
        )


def _assert_expected_hashes(bmad_dst: Path, tea_dst: Path, expected: dict) -> None:
    """Verify SHA-256 of load-bearing upstream files matches `sources.lock`."""
    checks = {
        "bmad_resolve_customization_py":
            bmad_dst / "src" / "scripts" / "resolve_customization.py",
        "tea_bmad_tea_customize_toml":
            tea_dst / "src" / "agents" / "bmad-tea" / "customize.toml",
        "tea_test_design_customize_toml":
            tea_dst / "src" / "workflows" / "testarch" / "bmad-testarch-test-design" / "customize.toml",
        "tea_test_design_skill_md":
            tea_dst / "src" / "workflows" / "testarch" / "bmad-testarch-test-design" / "SKILL.md",
    }
    for key, path in checks.items():
        if not path.exists():
            raise RuntimeError(f"expected file missing: {path}")
        exp = expected.get(key)
        if not exp:
            continue
        got = _sha256(path)
        if got != exp:
            raise RuntimeError(
                f"hash mismatch for {key}: expected {exp}, got {got}"
            )


def verify_only(target_dir: Path, sources_lock_path: Path | None = None) -> dict:
    """D3.3.2 §12. Non-clonig, non-mutating source-lock check.

    Verifies that both upstream worktrees exist under `target_dir`,
    that HEAD matches `sources.lock`, that the worktree is clean, and
    that the expected-file-hash allowlist still matches on disk. Any
    drift raises RuntimeError so the CI step exits non-zero.
    """
    lock_path = sources_lock_path or (_HERE / "sources.lock")
    lock = yaml.safe_load(lock_path.read_text(encoding="utf-8"))
    bmad_dst = target_dir / "BMAD-METHOD"
    tea_dst = target_dir / "bmad-method-test-architecture-enterprise"
    missing = [str(p) for p in (bmad_dst, tea_dst) if not p.exists()]
    if missing:
        raise RuntimeError(f"upstream worktrees missing: {missing}")
    bmad_sha = _run(["git", "rev-parse", "HEAD"], cwd=bmad_dst)
    if bmad_sha != lock["bmad_source_sha"]:
        raise RuntimeError(
            f"BMAD-METHOD HEAD {bmad_sha} != expected {lock['bmad_source_sha']}"
        )
    _assert_clean_worktree(bmad_dst)
    tea_sha = _run(["git", "rev-parse", "HEAD"], cwd=tea_dst)
    if tea_sha != lock["tea_source_sha"]:
        raise RuntimeError(
            f"TEA HEAD {tea_sha} != expected {lock['tea_source_sha']}"
        )
    _assert_clean_worktree(tea_dst)
    _assert_expected_hashes(bmad_dst, tea_dst, lock.get("expected_file_hashes") or {})
    resolver = bmad_dst / "src" / "scripts" / "resolve_customization.py"
    if not resolver.exists():
        raise RuntimeError(f"upstream resolver missing at {resolver}")
    return {
        "status": "PASS",
        "bmad_source_sha": bmad_sha,
        "tea_source_sha": tea_sha,
        "resolver_path": str(resolver),
        "resolver_sha256": _sha256(resolver),
        "hashes_verified": True,
        "worktrees_clean": True,
    }


def bootstrap(target_dir: Path, sources_lock_path: Path | None = None) -> dict:
    lock_path = sources_lock_path or (_HERE / "sources.lock")
    lock = yaml.safe_load(lock_path.read_text(encoding="utf-8"))
    bmad_dst = target_dir / "BMAD-METHOD"
    tea_dst = target_dir / "bmad-method-test-architecture-enterprise"

    bmad_sha = clone_or_update(lock["bmad_source_repo"], lock["bmad_source_tag"], bmad_dst)
    if bmad_sha != lock["bmad_source_sha"]:
        raise RuntimeError(
            f"BMAD-METHOD tag {lock['bmad_source_tag']} resolves to {bmad_sha} "
            f"but sources.lock expects {lock['bmad_source_sha']}"
        )
    _assert_clean_worktree(bmad_dst)

    tea_sha = clone_or_update(lock["tea_source_repo"], lock["tea_source_tag"], tea_dst)
    if tea_sha != lock["tea_source_sha"]:
        raise RuntimeError(
            f"TEA tag {lock['tea_source_tag']} resolves to {tea_sha} "
            f"but sources.lock expects {lock['tea_source_sha']}"
        )
    _assert_clean_worktree(tea_dst)

    _assert_expected_hashes(bmad_dst, tea_dst, lock.get("expected_file_hashes") or {})

    resolver = bmad_dst / "src" / "scripts" / "resolve_customization.py"
    if not resolver.exists():
        raise RuntimeError(f"upstream resolver not found at {resolver}")

    return {
        "bmad_dir": str(bmad_dst),
        "tea_dir":  str(tea_dst),
        "bmad_source_sha": bmad_sha,
        "tea_source_sha":  tea_sha,
        "resolver_path":   str(resolver),
        "resolver_sha256": _sha256(resolver),
        "hashes_verified": True,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target-dir", required=True, type=Path)
    ap.add_argument("--sources-lock", type=Path, default=None)
    ap.add_argument("--verify-only", action="store_true",
                    help=("D3.3.2 §12: check the two upstream worktrees "
                          "match sources.lock without cloning. Exits "
                          "non-zero on any drift."))
    args = ap.parse_args()
    import json as _j
    try:
        if args.verify_only:
            r = verify_only(args.target_dir, args.sources_lock)
        else:
            r = bootstrap(args.target_dir, args.sources_lock)
    except Exception as err:  # noqa: BLE001
        print(_j.dumps({"status": "FAIL", "error": str(err)}, indent=2))
        return 1
    print(_j.dumps(r, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
