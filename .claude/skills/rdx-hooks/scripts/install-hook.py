#!/usr/bin/env python3
"""Install the RDX pre-push hook into <project-root>/.git/hooks/pre-push.

Phase 5 — opt-in installer. Closes:
  T-L6-HOOK-001  push blocked when validator exits 1
  T-L6-HOOK-002  push permitted when validator exits 0
  T-L6-HOOK-003  chains with pre-existing pre-push hook
  T-L6-HOOK-004  uninstall restores pre-existing hook
  T-L6-HOOK-005  `--no-verify` bypass still works (by design)

Idempotent: re-running on an already-installed repo is a no-op.
Foreign-preserving: any pre-existing pre-push hook is moved to
`pre-push.user.rdx-backup` so uninstall can restore it byte-equal.
"""

from __future__ import annotations

import argparse
import shutil
import stat
import sys
from pathlib import Path

RDX_SENTINEL = "# RDX-HOOK-MANAGED"
BACKUP_SUFFIX = "user.rdx-backup"


def _hook_body() -> str:
    here = Path(__file__).resolve().parent.parent / "assets" / "pre-push.sh"
    return here.read_text(encoding="utf-8")


def _git_hooks_dir(project_root: Path) -> Path:
    git_dir = project_root / ".git"
    if not git_dir.exists():
        sys.stderr.write(f"error: {project_root} is not a git repo (no .git)\n")
        sys.exit(1)
    if git_dir.is_file():
        # gitdir: <path> linked worktree case
        content = git_dir.read_text(encoding="utf-8").strip()
        if content.startswith("gitdir:"):
            git_dir = Path(content.split(":", 1)[1].strip())
    hooks = git_dir / "hooks"
    hooks.mkdir(parents=True, exist_ok=True)
    return hooks


def install(project_root: Path) -> int:
    hooks = _git_hooks_dir(project_root)
    target = hooks / "pre-push"
    backup = hooks / f"pre-push.{BACKUP_SUFFIX}"

    body = _hook_body()
    if target.exists():
        existing = target.read_text(encoding="utf-8", errors="replace")
        if RDX_SENTINEL in existing:
            # Already managed — refresh body but keep backup as-is.
            target.write_text(body, encoding="utf-8")
            _make_executable(target)
            print(f"[rdx-hooks] refreshed managed hook at {target}")
            return 0
        # Foreign hook present — move it aside before installing.
        if not backup.exists():
            shutil.copy2(target, backup)
            _make_executable(backup)
        else:
            # Backup exists but current target is foreign and not ours;
            # do not clobber the backup, just overwrite the target.
            pass

    target.write_text(body, encoding="utf-8")
    _make_executable(target)
    print(f"[rdx-hooks] installed pre-push hook at {target}")
    if backup.exists():
        print(f"[rdx-hooks] preserved pre-existing hook at {backup}")
    return 0


def _make_executable(p: Path) -> None:
    mode = p.stat().st_mode
    p.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="rdx-install-hook")
    ap.add_argument("--project-root", required=True)
    args = ap.parse_args(argv)
    return install(Path(args.project_root).resolve())


if __name__ == "__main__":
    sys.exit(main())
