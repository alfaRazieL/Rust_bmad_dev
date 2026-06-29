"""L3 integration test — validator against a real Cargo project fixture.

Closes (Phase 2 exit gate minimum):
  T-L3-CRATE-001 — green Cargo crate, validator PASS (exit 0)
  T-L3-CRATE-003 — dual-run base/head with same error signature → BASELINE_FAILURE_OBSERVED
  T-L3-CRATE-004 — dual-run base PASS, head FAIL → REGRESSION_FAILURE

The validator does not invoke cargo itself — it consumes a diff and (optionally)
pre-recorded evidence. Cargo presence is therefore not required by these tests,
which keeps CI environment-independent.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path


def _validator_invocation() -> list[str]:
    return [sys.executable, "-m", "rdx_validator"]


def _run_validator(args: list[str], cwd: Path | None = None, env_extra: dict | None = None):
    import os

    env = os.environ.copy()
    env.update(env_extra or {})
    return subprocess.run(
        _validator_invocation() + args,
        cwd=cwd,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def test_l3_crate_001_green_crate_passes(repo_root: Path, fixtures_dir: Path, tmp_path: Path):
    """T-L3-CRATE-001 — running validator against a doc-only change in a
    green crate returns exit 0 with an aggregate PASS verdict.
    """
    crate_src = fixtures_dir / "cargo-projects" / "green-crate"
    diff_file = crate_src / "expected-diff.diff"
    story_file = crate_src / "story.json"

    evidence_in = crate_src / "evidence-in.json"
    out_path = tmp_path / "evidence.json"
    env = {"PYTHONPATH": str(repo_root / "rdx-validator")}
    res = _run_validator(
        [
            "--diff-file", str(diff_file),
            "--story", str(story_file),
            "--contracts-dir", str(repo_root / "tests" / "contracts"),
            "--mode", "MODE_2",
            "--evidence-in", str(evidence_in),
            "--evidence-out", str(out_path),
            "--quiet",
        ],
        env_extra=env,
    )
    assert res.returncode == 0, f"validator returned {res.returncode}; stderr={res.stderr}"
    assert out_path.exists(), "evidence file not written"
    evidence = json.loads(out_path.read_text(encoding="utf-8"))
    assert evidence["aggregate"]["verdict"] in ("PASS", "NOT_APPLICABLE"), evidence["aggregate"]


def test_l3_crate_003_dual_run_same_signature_not_blocking(
    repo_root: Path, fixtures_dir: Path, tmp_path: Path
):
    """T-L3-CRATE-003 — same error signature on base+head yields baseline observed (exit 0)."""
    crate_src = fixtures_dir / "cargo-projects" / "green-crate"
    baseline_file = fixtures_dir / "cargo-projects" / "baseline-red" / "baseline-data.json"

    env = {"PYTHONPATH": str(repo_root / "rdx-validator")}
    res = _run_validator(
        [
            "--diff-file", str(crate_src / "expected-diff.diff"),
            "--contracts-dir", str(repo_root / "tests" / "contracts"),
            "--mode", "MODE_2",
            "--dual-run",
            "--baseline-data", str(baseline_file),
            "--evidence-out", str(tmp_path / "ev.json"),
            "--quiet",
        ],
        env_extra=env,
    )
    assert res.returncode == 0, f"expected exit 0, got {res.returncode}; stderr={res.stderr}"
    ev = json.loads((tmp_path / "ev.json").read_text(encoding="utf-8"))
    rules = ev["rules"]
    assert "CORE-011" in rules
    assert rules["CORE-011"]["verdict"] == "BASELINE_FAILURE_OBSERVED"


def test_l3_crate_004_dual_run_green_to_red_blocks(
    repo_root: Path, fixtures_dir: Path, tmp_path: Path
):
    """T-L3-CRATE-004 — base green, head red → REGRESSION_FAILURE (exit 1)."""
    crate_src = fixtures_dir / "cargo-projects" / "green-crate"
    baseline_file = fixtures_dir / "cargo-projects" / "regression-introduced" / "baseline-data.json"

    env = {"PYTHONPATH": str(repo_root / "rdx-validator")}
    res = _run_validator(
        [
            "--diff-file", str(crate_src / "expected-diff.diff"),
            "--contracts-dir", str(repo_root / "tests" / "contracts"),
            "--mode", "MODE_2",
            "--dual-run",
            "--baseline-data", str(baseline_file),
            "--evidence-out", str(tmp_path / "ev.json"),
            "--quiet",
        ],
        env_extra=env,
    )
    assert res.returncode == 1, f"expected exit 1, got {res.returncode}; stderr={res.stderr}"
    ev = json.loads((tmp_path / "ev.json").read_text(encoding="utf-8"))
    assert ev["rules"]["CORE-011"]["verdict"] == "REGRESSION_FAILURE"


def test_l3_crate_005_unsafe_no_safety_blocks(
    repo_root: Path, fixtures_dir: Path, tmp_path: Path
):
    """T-L3-CRATE-005 (Phase 2 minimum slice) — unsafe surface w/o SAFETY
    yields APPROVAL_REQUIRED (exit 3) when activated. Exercised end-to-end
    via CLI on the unsafe positive fixture.
    """
    env = {"PYTHONPATH": str(repo_root / "rdx-validator")}
    res = _run_validator(
        [
            "--diff-file", str(fixtures_dir / "diffs" / "unsafe" / "negative-no-safety-comment.diff"),
            "--contracts-dir", str(repo_root / "tests" / "contracts"),
            "--mode", "MODE_2",
            "--evidence-out", str(tmp_path / "ev.json"),
            "--quiet",
        ],
        env_extra=env,
    )
    assert res.returncode == 3, f"expected exit 3, got {res.returncode}; stderr={res.stderr}"
    ev = json.loads((tmp_path / "ev.json").read_text(encoding="utf-8"))
    assert ev["rules"].get("RP-UNSAFE-001", {}).get("verdict") == "APPROVAL_REQUIRED"
