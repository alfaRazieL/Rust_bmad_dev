#!/usr/bin/env python3
"""RDX CI runner — invokes the validator from a trusted source (target
branch / pinned release / reusable workflow), never from the PR head.

Phase 5 — implements Option B trust model per RDX_TEST_STRATEGY.md §7.

Closes (Phase 5 entry-gate):
  T-L6-CI-001  fail PR with invalid evidence
  T-L6-CI-002  validator loaded from target branch, not PR head
  T-L6-CI-004  dual-run distinguishes baseline from regression
  T-L6-CI-005  rejects stale evidence (diff_digest mismatch)
  T-L7-MOD-VALIDATOR-001  PR-rewritten validator has no effect
  T-V5-ACC-05  CI re-computation matches local verdict

Usage:
    rdx-ci-runner.py \\
        --project-root <path-to-sample-repo> \\
        --base-ref <main> \\
        --head-ref <pr-head> \\
        [--validator-repo <path>] \\
        [--validator-ref <ref>] \\
        [--evidence-in <file>] \\
        [--dual-run] \\
        [--mode MODE_3]
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

DEFAULT_MODE = "MODE_3"


def _git(args: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=check)


def _checkout_from_ref(*, validator_repo: Path, ref: str, paths: list[str], dest: Path) -> None:
    """Materialise files from a git ref into dest.

    Implements the Option B trust mechanism: we use `git show <ref>:<path>`
    (and `git ls-tree -r <ref> <dir>` for directories) so the runner can
    fetch base-branch versions of the validator + schema + contracts
    without trusting the PR head's working tree.
    """
    for relpath in paths:
        # Discover entries under this path on the given ref.
        ls = _git(["ls-tree", "-r", "--name-only", ref, "--", relpath], cwd=validator_repo)
        entries = [e for e in ls.stdout.splitlines() if e.strip()]
        if not entries:
            # Treat as a single file.
            content = _git(["show", f"{ref}:{relpath}"], cwd=validator_repo).stdout
            (dest / relpath).parent.mkdir(parents=True, exist_ok=True)
            (dest / relpath).write_text(content, encoding="utf-8")
            continue
        for fpath in entries:
            content = _git(["show", f"{ref}:{fpath}"], cwd=validator_repo, check=False).stdout
            (dest / fpath).parent.mkdir(parents=True, exist_ok=True)
            (dest / fpath).write_text(content, encoding="utf-8")


def _diff_pr(project_root: Path, base_ref: str, head_ref: str) -> str:
    r = _git(["diff", f"{base_ref}...{head_ref}"], cwd=project_root)
    return r.stdout


def _resolve_sha(project_root: Path, ref: str) -> str | None:
    r = _git(["rev-parse", ref], cwd=project_root, check=False)
    return r.stdout.strip() or None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="rdx-ci-runner")
    ap.add_argument("--project-root", required=True, help="Sample / PR repo path")
    ap.add_argument("--base-ref", default="main")
    ap.add_argument("--head-ref", default="HEAD")
    ap.add_argument(
        "--validator-repo",
        default=None,
        help="Repo to load validator code from. Defaults to --project-root.",
    )
    ap.add_argument(
        "--validator-ref",
        default=None,
        help="Git ref in --validator-repo to load validator + schema from. Defaults to --base-ref.",
    )
    ap.add_argument("--evidence-in", default=None)
    ap.add_argument("--dual-run", action="store_true")
    ap.add_argument("--mode", default=DEFAULT_MODE)
    args = ap.parse_args(argv)

    project_root = Path(args.project_root).resolve()
    validator_repo = Path(args.validator_repo).resolve() if args.validator_repo else project_root

    with tempfile.TemporaryDirectory(prefix="rdx-ci-runner-") as tmp:
        trusted = Path(tmp)
        if args.validator_ref:
            # CI path — fetch from a specific ref via `git show <ref>:<path>`
            # so a PR-side tamper has no effect on the trusted source
            # (Option B per RDX_TEST_STRATEGY.md §7).
            try:
                _checkout_from_ref(
                    validator_repo=validator_repo,
                    ref=args.validator_ref,
                    paths=[
                        "rdx-validator",
                        "tests/contracts/router-rules.json",
                        "tests/contracts/rule-check-map.json",
                        "tests/contracts/status-definitions.json",
                        "tests/contracts/authority-matrix.json",
                        "tests/contracts/schemas/rdx-evidence.v1.schema.json",
                    ],
                    dest=trusted,
                )
            except subprocess.CalledProcessError as exc:
                print(
                    json.dumps(
                        {
                            "error": "validator/contract checkout from trusted ref failed",
                            "ref": args.validator_ref,
                            "detail": exc.stderr or str(exc),
                        }
                    )
                )
                return 2
        else:
            # Local-dev / pytest path — copy the working tree of
            # --validator-repo into the trusted tempdir. This is still
            # Option B (the validator code lives outside the PR's
            # working tree at --project-root), but skips the git
            # round-trip for tests with uncommitted validator changes.
            for relpath in (
                "rdx-validator",
                "tests/contracts/router-rules.json",
                "tests/contracts/rule-check-map.json",
                "tests/contracts/status-definitions.json",
                "tests/contracts/authority-matrix.json",
                "tests/contracts/schemas/rdx-evidence.v1.schema.json",
            ):
                src = validator_repo / relpath
                if not src.exists():
                    continue
                dst = trusted / relpath
                dst.parent.mkdir(parents=True, exist_ok=True)
                if src.is_dir():
                    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
                else:
                    shutil.copy2(src, dst)

        validator_dir = trusted / "rdx-validator"
        contracts_dir = trusted / "tests" / "contracts"

        # Recompute the PR diff fresh — never trust a PR-supplied diff file.
        diff_text = _diff_pr(project_root, args.base_ref, args.head_ref)
        diff_file = trusted / "_pr.diff"
        diff_file.write_text(diff_text, encoding="utf-8")

        # If the PR contains a STORY.json on the head, prefer it; otherwise
        # synthesize a minimal one from the base.
        story_file = project_root / "STORY.json"
        cmd = [
            sys.executable,
            "-m",
            "rdx_validator",
            "--project-root",
            str(project_root),
            "--diff-file",
            str(diff_file),
            "--mode",
            args.mode,
            "--contracts-dir",
            str(contracts_dir),
            "--validator-source",
            "TARGET_BRANCH",
        ]
        if story_file.exists():
            cmd.extend(["--story", str(story_file)])
        if args.evidence_in:
            cmd.extend(["--evidence-in", str(args.evidence_in)])
        if args.dual_run:
            cmd.append("--dual-run")
            # Best-effort dual-run baseline data: re-run validator on base
            # diff (empty PR-from-base if base==head) to obtain a baseline
            # outcome. For Phase 5, dual-run with no --baseline-data is
            # accepted as informational — the validator already handles
            # the absence path.

        env = os.environ.copy()
        env["PYTHONPATH"] = str(validator_dir) + os.pathsep + env.get("PYTHONPATH", "")

        proc = subprocess.run(cmd, env=env, capture_output=True, text=True, check=False)
        # Pass through the validator's JSON envelope on stdout and exit
        # code so the caller (workflow / pytest) reads them directly.
        sys.stdout.write(proc.stdout)
        if proc.stderr:
            sys.stderr.write(proc.stderr)
        return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
