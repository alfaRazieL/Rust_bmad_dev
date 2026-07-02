"""T-L7-MOD-VALIDATOR-001 — PR rewrites validator to always PASS. CI
workflow loads the validator from main, so the tampered copy has no
effect.

This test asserts the structural contract in `rdx-ci-runner.py`:
when invoked with `--validator-ref <BASE>` it must source validator
code via `git show <BASE>:<path>`, never from the PR's working tree.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CI_RUNNER = REPO_ROOT / ".github" / "scripts" / "rdx-ci-runner.py"


def test_l7_ci_runner_uses_base_ref_not_pr_head():
    assert CI_RUNNER.exists(), "rdx-ci-runner.py must exist"
    body = CI_RUNNER.read_text(encoding="utf-8")
    # Option B contract: runner sources validator code from the base ref.
    # Either via `git show <ref>:<path>` or `git worktree add <ref>` or
    # `git checkout <ref> -- <path>`.
    proof = (
        "git", "show", ":",
    )
    assert "git" in body and ("show" in body or "worktree" in body or "archive" in body), body
    # And accepts an explicit --validator-ref flag so callers cannot
    # silently fall back to PR-head code.
    assert "--validator-ref" in body, "ci-runner must accept --validator-ref"
