#!/usr/bin/env python3
"""Uninstall the RDX pre-push hook.

If a pre-existing user hook was preserved at install time it is
restored byte-equal. Otherwise the RDX-managed hook is removed.

Closes T-L6-HOOK-004.
"""

from __future__ import annotations

import argparse
import shutil
import stat
import sys
from pathlib import Path

RDX_SENTINEL = "# RDX-HOOK-MANAGED"
BACKUP_SUFFIX = "user.rdx-backup"


def _git_hooks_dir(project_root: Path) -> Path:
    git_dir = project_root / ".git"
    if not git_dir.exists():
        sys.stderr.write(f"error: {project_root} is not a git repo (no .git)\n")
        sys.exit(1)
    if git_dir.is_file():
        content = git_dir.read_text(encoding="utf-8").strip()
        if content.startswith("gitdir:"):
            git_dir = Path(content.split(":", 1)[1].strip())
    return git_dir / "hooks"


def uninstall(project_root: Path) -> int:
    hooks = _git_hooks_dir(project_root)
    target = hooks / "pre-push"
    backup = hooks / f"pre-push.{BACKUP_SUFFIX}"

    if not target.exists():
        # Nothing to do — but if backup exists for some reason, restore it.
        if backup.exists():
            shutil.copy2(backup, target)
            _make_executable(target)
            backup.unlink()
            print(f"[rdx-hooks] restored pre-existing hook (no managed hook found)")
        else:
            print("[rdx-hooks] no managed hook to uninstall")
        return 0

    body = target.read_text(encoding="utf-8", errors="replace")
    if RDX_SENTINEL not in body:
        print(f"[rdx-hooks] pre-push hook at {target} is not RDX-managed; leaving alone")
        return 0

    if backup.exists():
        # Restore the user's previous hook byte-equal.
        target.write_bytes(backup.read_bytes())
        # Match original mode if possible (best effort).
        try:
            target.chmod(backup.stat().st_mode)
        except OSError:
            _make_executable(target)
        backup.unlink()
        print(f"[rdx-hooks] restored pre-existing hook to {target}")
    else:
        target.unlink()
        print(f"[rdx-hooks] removed RDX-managed hook at {target}")
    return 0


def _make_executable(p: Path) -> None:
    mode = p.stat().st_mode
    p.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="rdx-uninstall-hook")
    ap.add_argument("--project-root", required=True)
    args = ap.parse_args(argv)
    return uninstall(Path(args.project_root).resolve())


if __name__ == "__main__":
    sys.exit(main())
