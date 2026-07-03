#!/usr/bin/env python3
"""Create a disposable git worktree/project with the install-tree
adapter installed and the given fixture materialised.

Usage:
  prepare_workspace.py --dest DIR --fixture FIXTURE_DIR --scenario NAME

Output: JSON to stdout with `project`, `run_id`, `head_sha`, `base_sha`.
Fails closed if the fixture directory is missing or the workspace
already exists (never overwrite).
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

RDX_TEA_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = RDX_TEA_DIR.parent
WORKSPACE = REPO_ROOT.parent
INSTALL_TREE = RDX_TEA_DIR / "poc" / "install-tree"
UPSTREAM_TEA = WORKSPACE / "upstream" / "bmad-method-test-architecture-enterprise"


def _run(cmd, cwd=None):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=False)
    if r.returncode != 0:
        raise RuntimeError(f"{cmd!r} failed: {r.stderr}")
    return r.stdout.strip()


def prepare(dest: Path, fixture: Path, scenario: str, workflow: str) -> dict:
    if dest.exists():
        raise RuntimeError(f"refusing to overwrite existing {dest}")
    if not fixture.exists():
        raise RuntimeError(f"fixture missing: {fixture}")
    dest.mkdir(parents=True)
    shutil.copytree(INSTALL_TREE / "_bmad", dest / "_bmad")
    (dest / "_bmad-run").mkdir()
    (dest / "_bmad-output" / "test-artifacts").mkdir(parents=True)
    # D3.3 §4.5: TEA config is REQUIRED for the wrapper's sequential guard.
    (dest / "_bmad" / "tea").mkdir(exist_ok=True)
    (dest / "_bmad" / "tea" / "config.yaml").write_text(
        "tea_execution_mode: sequential\n"
        "test_artifacts: '{project-root}/_bmad-output/test-artifacts'\n"
        "output_folder: '{project-root}/_bmad-output'\n"
        f"project_name: {scenario}\n",
        encoding="utf-8",
    )
    # Install RDX-TEA wrapper skills.
    if (INSTALL_TREE / ".claude").exists():
        shutil.copytree(INSTALL_TREE / ".claude", dest / ".claude")
    # Install real BMAD TEA skill (workflow-specific).
    skill_slug = f"bmad-testarch-{workflow}"
    skill_src = UPSTREAM_TEA / "src" / "workflows" / "testarch" / skill_slug
    if skill_src.exists():
        skill_dst = dest / ".claude" / "skills" / skill_slug
        if not skill_dst.exists():
            shutil.copytree(skill_src, skill_dst)
    # 1) Copy metadata files.
    # story.md → _bmad-run/story.md (wrapper reads it there).
    # Cargo.toml and rust-toolchain[.toml] → project root.
    metadata_files = ("Cargo.toml", "rust-toolchain", "rust-toolchain.toml")
    fixture_story = fixture / "story.md"
    if fixture_story.exists():
        (dest / "_bmad-run").mkdir(parents=True, exist_ok=True)
        shutil.copy2(fixture_story, dest / "_bmad-run" / "story.md")
    _bmad_run = fixture / "_bmad-run"
    if _bmad_run.exists():
        for f in _bmad_run.rglob("*"):
            if f.is_file():
                rel = f.relative_to(fixture)
                target = dest / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, target)
    for name in metadata_files:
        src = fixture / name
        if src.exists():
            shutil.copy2(src, dest / name)
    # Init git and make the BASE commit (metadata only).
    _run(["git", "init", "-q"], cwd=dest)
    _run(["git", "add", "-A"], cwd=dest)
    _run(["git", "-c", "user.email=harness@rdx-tea", "-c", "user.name=harness",
          "commit", "-q", "--allow-empty", "-m", f"{scenario} base"], cwd=dest)
    base_sha = _run(["git", "rev-parse", "HEAD"], cwd=dest)

    # 2) Apply the diff and commit HEAD.
    diff_patch = fixture / "diff.patch"
    if diff_patch.exists():
        # Store the absolute patch path so `git apply` finds it after cwd change.
        abs_patch = diff_patch.resolve()
        shutil.copy2(diff_patch, dest / "_bmad-run" / "diff.patch")
        # `git apply` for new-file diffs — no --3way, no --index (we
        # `git add -A` right after).
        _run(["git", "apply", "--whitespace=nowarn", str(abs_patch)], cwd=dest)
        _run(["git", "add", "-A"], cwd=dest)
        # Amend allowed to keep single-commit? No — need two commits.
        _run(["git", "-c", "user.email=harness@rdx-tea", "-c", "user.name=harness",
              "commit", "-q", "-m", f"{scenario} head"], cwd=dest)
    head = _run(["git", "rev-parse", "HEAD"], cwd=dest)

    run_id = f"{scenario}-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
    return {
        "project": str(dest),
        "workflow": workflow,
        "scenario": scenario,
        "run_id": run_id,
        "head_sha": head,
        "base_sha": base_sha,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dest", required=True, type=Path)
    ap.add_argument("--fixture", required=True, type=Path)
    ap.add_argument("--scenario", required=True)
    ap.add_argument("--workflow", required=True,
                    choices=("test-design", "atdd", "framework", "ci",
                              "automate", "test-review", "nfr", "trace"))
    args = ap.parse_args()
    try:
        r = prepare(args.dest, args.fixture, args.scenario, args.workflow)
    except RuntimeError as err:
        print(f"prepare_workspace failed: {err}", file=sys.stderr)
        return 1
    print(json.dumps(r, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
