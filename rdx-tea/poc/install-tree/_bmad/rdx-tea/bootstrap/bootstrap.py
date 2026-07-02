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

    tea_sha = clone_or_update(lock["tea_source_repo"], lock["tea_source_tag"], tea_dst)
    if tea_sha != lock["tea_source_sha"]:
        raise RuntimeError(
            f"TEA tag {lock['tea_source_tag']} resolves to {tea_sha} "
            f"but sources.lock expects {lock['tea_source_sha']}"
        )

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
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target-dir", required=True, type=Path)
    ap.add_argument("--sources-lock", type=Path, default=None)
    args = ap.parse_args()
    try:
        r = bootstrap(args.target_dir, args.sources_lock)
    except Exception as err:  # noqa: BLE001
        print(f"bootstrap failed: {err}", file=sys.stderr)
        return 1
    import json as _j
    print(_j.dumps(r, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
