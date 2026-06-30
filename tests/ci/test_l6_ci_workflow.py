"""L6 — CI workflow end-to-end tests.

Closes (Phase 5 entry-gate):
  T-L6-CI-001  GitHub Actions blocks PR with invalid evidence
  T-L6-CI-002  CI loads validator from trusted source (target branch, not PR head)
  T-L6-CI-003  Fork PR safe — workflow runs without secrets
  T-L6-CI-004  CI dual-run distinguishes baseline from regression
  T-L6-CI-005  CI rejects stale evidence (diff_digest mismatch)
  T-V5-ACC-05  CI independently recomputes deterministic verdicts

These tests use the local `rdx-ci-runner.py` (which is what the
.github/workflows/rdx-gate.yml workflow invokes). The runner implements
Option B trust by checking out validator code from the base ref via
`git show <base>:<path>` — so the same script that runs in CI runs
here, no GitHub-Actions runtime required.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from .conftest import REPO_ROOT, git


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _run_runner(
    ci_runner_script: Path,
    repo: Path,
    *,
    base_ref: str = "main",
    head_ref: str = "HEAD",
    extra: list[str] | None = None,
) -> subprocess.CompletedProcess:
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
        [
            sys.executable,
            str(ci_runner_script),
            "--project-root",
            str(repo),
            "--base-ref",
            base_ref,
            "--head-ref",
            head_ref,
            "--validator-repo",
            str(REPO_ROOT),
            "--validator-ref",
            "HEAD",
            *extra,
        ],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


# ---------------------------------------------------------------------------
# T-L6-CI-001 — required check fails on CORE-007 violation
# ---------------------------------------------------------------------------


def test_l6_ci_001_blocks_pr_with_invalid_evidence(sample_ci_repo, ci_runner_script):
    auth_login = sample_ci_repo.work / "src" / "auth" / "login.rs"
    auth_login.write_text(
        auth_login.read_text(encoding="utf-8") + "\npub fn backdoor() {}\n",
        encoding="utf-8",
    )
    git("add", "src/auth/login.rs", cwd=sample_ci_repo.work)
    git("commit", "-m", "violate CORE-007", cwd=sample_ci_repo.work)

    r = _run_runner(ci_runner_script, sample_ci_repo.work, base_ref="main", head_ref="pr-head")
    assert r.returncode == 1, f"runner should exit 1; stdout={r.stdout}\nstderr={r.stderr}"
    envelope = json.loads(r.stdout)
    assert envelope["aggregate"]["verdict"] in {"FAIL", "BLOCKED"}
    assert envelope["rules"]["CORE-007"]["verdict"] == "FAIL"


# ---------------------------------------------------------------------------
# T-L6-CI-002 — Option B: validator loaded from base, not PR head
# ---------------------------------------------------------------------------


def test_l6_ci_002_validator_loaded_from_base(sample_ci_repo, ci_runner_script):
    """PR replaces validator with a stub that always PASSes.

    The runner is told to use the *real* validator (from this repo's
    HEAD), not the tampered copy in the sample repo's pr-head. This
    simulates Option B where CI checks out the validator from the
    target branch, not the PR head.
    """
    # Bring the validator package into the sample repo on main first.
    rdx_dir = sample_ci_repo.work / "rdx-validator"
    if not rdx_dir.exists():
        # copy a token marker so PR can "tamper" with it
        (rdx_dir).mkdir()
        (rdx_dir / "MARKER.txt").write_text("real validator\n", encoding="utf-8")
        git("add", ".", cwd=sample_ci_repo.work)
        git("commit", "-m", "seed validator marker", cwd=sample_ci_repo.work)
        git("checkout", "pr-head", cwd=sample_ci_repo.work)
        git("merge", "--ff-only", "main", cwd=sample_ci_repo.work)

    # PR tampers with validator marker AND violates CORE-007.
    (rdx_dir / "MARKER.txt").write_text("PR-TAMPERED\n", encoding="utf-8")
    auth_login = sample_ci_repo.work / "src" / "auth" / "login.rs"
    auth_login.write_text(
        auth_login.read_text(encoding="utf-8") + "\npub fn backdoor() {}\n",
        encoding="utf-8",
    )
    git("add", ".", cwd=sample_ci_repo.work)
    git("commit", "-m", "tamper validator + violate CORE-007", cwd=sample_ci_repo.work)

    r = _run_runner(ci_runner_script, sample_ci_repo.work, base_ref="main", head_ref="pr-head")
    # PR's tampered validator must NOT influence the verdict.
    assert r.returncode == 1, f"violation must still be caught; stdout={r.stdout}"
    envelope = json.loads(r.stdout)
    assert envelope["rules"]["CORE-007"]["verdict"] == "FAIL"
    # Runner records that validator was sourced from main / base, not PR head.
    assert envelope["validator"]["source"] in {"TARGET_BRANCH", "PINNED_RELEASE"}


# ---------------------------------------------------------------------------
# T-L6-CI-003 — Fork PR safe — workflow runs without secrets
# ---------------------------------------------------------------------------


def test_l6_ci_003_fork_pr_no_secrets(rdx_gate_workflow):
    """Structural: the workflow declares minimal `permissions:` and
    does not reference any secrets for Cat-1/2 verification."""
    assert rdx_gate_workflow.exists(), "rdx-gate.yml must exist"
    data = yaml.safe_load(rdx_gate_workflow.read_text(encoding="utf-8"))
    perms = data.get("permissions") or {}
    # Either dict with read-only contents, or string 'read-all'.
    if isinstance(perms, dict):
        assert perms.get("contents") in {"read", None}, perms
        assert "id-token" not in perms, "fork PRs must not get id-token"
        assert "packages" not in perms, "fork PRs must not get packages write"
    else:
        assert perms in {"read-all", "contents: read"}, perms

    # Workflow body must not reference secrets for Cat-1/2 steps.
    body = rdx_gate_workflow.read_text(encoding="utf-8")
    # The Cat-1/2 path may reference secrets only in a comment block.
    # We assert no active `${{ secrets.* }}` substitutions appear in
    # blocking steps.
    blocking_section = body.split("# Cat-3")[0] if "# Cat-3" in body else body
    assert "${{ secrets." not in blocking_section, (
        "Cat-1/2 blocking steps must not depend on secrets (fork-PR safety)"
    )


# ---------------------------------------------------------------------------
# T-L6-CI-004 — dual-run distinguishes baseline from regression
# ---------------------------------------------------------------------------


def test_l6_ci_004_dual_run_baseline_vs_regression(sample_ci_repo, ci_runner_script):
    """Pre-seed main with a baseline FAIL (CORE-007 already violated on
    main). PR makes an unrelated change. Runner reports
    BASELINE_FAILURE_OBSERVED, not blames the PR.
    """
    git("checkout", "main", cwd=sample_ci_repo.work)
    auth_login = sample_ci_repo.work / "src" / "auth" / "login.rs"
    auth_login.write_text(
        auth_login.read_text(encoding="utf-8") + "\npub fn baseline_violation() {}\n",
        encoding="utf-8",
    )
    git("add", ".", cwd=sample_ci_repo.work)
    git("commit", "-m", "baseline violation on main", cwd=sample_ci_repo.work)
    git("checkout", "pr-head", cwd=sample_ci_repo.work)
    git("merge", "main", "-m", "merge main", cwd=sample_ci_repo.work)

    # PR adds an unrelated, harmless change.
    lib = sample_ci_repo.work / "src" / "lib.rs"
    lib.write_text(lib.read_text(encoding="utf-8") + "\npub fn unrelated() {}\n", encoding="utf-8")
    git("add", "src/lib.rs", cwd=sample_ci_repo.work)
    git("commit", "-m", "unrelated change", cwd=sample_ci_repo.work)

    r = _run_runner(
        ci_runner_script,
        sample_ci_repo.work,
        base_ref="main",
        head_ref="pr-head",
        extra=["--dual-run"],
    )
    envelope = json.loads(r.stdout)
    # Either an explicit BASELINE_FAILURE_OBSERVED rule, or PR-introduced
    # rules are all NOT_APPLICABLE / PASS — never blame the PR.
    pr_rules = envelope["rules"]
    blame_pr = any(
        pr_rules.get(rid, {}).get("verdict") == "FAIL"
        and pr_rules[rid].get("blame") == "PR_HEAD"
        for rid in pr_rules
    )
    assert not blame_pr, (
        "PR must not be blamed for baseline failure; envelope=\n" + json.dumps(envelope, indent=2)
    )
    assert r.returncode == 0, "exit 0 for baseline-only failure (informational)"


# ---------------------------------------------------------------------------
# T-L6-CI-005 — CI rejects stale evidence (diff_digest mismatch)
# ---------------------------------------------------------------------------


def test_l6_ci_005_rejects_stale_evidence(sample_ci_repo, ci_runner_script, tmp_path):
    # PR's evidence.json carries diff_digest from an earlier commit.
    auth_login = sample_ci_repo.work / "src" / "auth" / "login.rs"
    auth_login.write_text(
        auth_login.read_text(encoding="utf-8") + "\npub fn first() {}\n",
        encoding="utf-8",
    )
    git("add", "src/auth/login.rs", cwd=sample_ci_repo.work)
    git("commit", "-m", "first PR commit", cwd=sample_ci_repo.work)
    # Author then adds another commit, but submits stale evidence.
    auth_login.write_text(
        auth_login.read_text(encoding="utf-8") + "\npub fn second() {}\n",
        encoding="utf-8",
    )
    git("add", "src/auth/login.rs", cwd=sample_ci_repo.work)
    git("commit", "-m", "second PR commit", cwd=sample_ci_repo.work)

    stale_evidence = tmp_path / "stale-evidence.json"
    stale_evidence.write_text(
        json.dumps(
            {
                "rdx_schema_version": "v1",
                "story_id": "STORY-CI-001",
                "head_sha": "0" * 40,
                "base_sha": "f" * 40,
                "diff_digest": "sha256:" + "1" * 64,  # fabricated, won't match
                "mode": "MODE_3",
                "rules": {
                    "CORE-007": {
                        "category": 1,
                        "verdict": "PASS",  # fake PASS
                        "severity": "INFO",
                        "author": "VALIDATOR",
                    }
                },
                "aggregate": {
                    "verdict": "PASS",
                    "exit_code": 0,
                    "blocking_count": 0,
                    "warning_count": 0,
                    "info_count": 1,
                },
            }
        ),
        encoding="utf-8",
    )

    r = _run_runner(
        ci_runner_script,
        sample_ci_repo.work,
        base_ref="main",
        head_ref="pr-head",
        extra=["--evidence-in", str(stale_evidence)],
    )
    envelope = json.loads(r.stdout)
    # CI must recompute and not let stale PASS through; CORE-007 should
    # be FAIL since the diff touches the protected path.
    assert envelope["rules"]["CORE-007"]["verdict"] == "FAIL"
    assert envelope.get("preflight", {}).get("stale_evidence") is True, (
        "CI runner should record that the submitted evidence was stale; envelope=\n"
        + json.dumps(envelope, indent=2)
    )
    assert r.returncode == 1


# ---------------------------------------------------------------------------
# T-V5-ACC-05 — CI independently recomputes deterministic verdicts
# ---------------------------------------------------------------------------


def test_v5_acc_05_ci_matches_local(sample_ci_repo, ci_runner_script):
    """Local validator + CI runner over the same PR produce identical
    rule verdicts (the JSON envelope rules block must match)."""
    # Make a clean, deterministic PR diff.
    lib = sample_ci_repo.work / "src" / "lib.rs"
    lib.write_text(lib.read_text(encoding="utf-8") + "\npub fn another() {}\n", encoding="utf-8")
    git("add", "src/lib.rs", cwd=sample_ci_repo.work)
    git("commit", "-m", "harmless", cwd=sample_ci_repo.work)

    # Local run (using the in-repo validator directly).
    sys_path_env = os.environ.copy()
    sys_path_env["PYTHONPATH"] = str(REPO_ROOT / "rdx-validator")
    local = subprocess.run(
        [
            sys.executable,
            "-m",
            "rdx_validator",
            "--project-root",
            str(sample_ci_repo.work),
            "--story",
            str(sample_ci_repo.work / "STORY.json"),
            "--base",
            "main",
            "--head",
            "pr-head",
            "--mode",
            "MODE_3",
            "--contracts-dir",
            str(REPO_ROOT / "tests" / "contracts"),
        ],
        capture_output=True,
        text=True,
        check=False,
        env=sys_path_env,
    )
    assert local.returncode in (0, 1, 3, 4), local.stderr
    local_env = json.loads(local.stdout)

    ci = _run_runner(ci_runner_script, sample_ci_repo.work, base_ref="main", head_ref="pr-head")
    assert ci.returncode in (0, 1, 3, 4), ci.stderr
    ci_env = json.loads(ci.stdout)

    local_rules = {
        k: (v["verdict"], v["severity"]) for k, v in local_env["rules"].items()
    }
    ci_rules = {k: (v["verdict"], v["severity"]) for k, v in ci_env["rules"].items()}
    assert local_rules == ci_rules, (
        "CI verdicts must match local for deterministic rules; local="
        f"{local_rules} ci={ci_rules}"
    )
    assert local_env["aggregate"]["exit_code"] == ci_env["aggregate"]["exit_code"]
