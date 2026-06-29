"""L0 drift-prevention tests.

Covers test IDs:
  T-L0-DRIFT-001 — every pack in KB §5 has an entry in router-rules.json (bijective)
  T-L0-DRIFT-002 — every rule-check-map.json ID exists in the KB
  T-L0-RULE-IDS-001 — no duplicate rule IDs in KB

The tests invoke the drift-check scripts as black-box subprocesses so that the
same code path runs locally and in CI.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _run_script(script_path: Path, extra_args: list[str] | None = None) -> subprocess.CompletedProcess:
    cmd = [sys.executable, str(script_path)]
    if extra_args:
        cmd.extend(extra_args)
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def test_l0_drift_001_router_kb_bijective(contracts_dir: Path, repo_root: Path):
    """T-L0-DRIFT-001 — KB §5 pack set equals router-rules.json pack set."""
    script = contracts_dir / "drift-check.py"
    assert script.exists(), f"drift-check.py missing at {script}"
    result = _run_script(script, ["--mode", "router"])
    assert result.returncode == 0, (
        f"drift-check (router) failed: stdout={result.stdout!r} stderr={result.stderr!r}"
    )


def test_l0_drift_002_rule_check_map_ids_in_kb(contracts_dir: Path):
    """T-L0-DRIFT-002 — every rule ID in rule-check-map.json exists in KB."""
    script = contracts_dir / "drift-check.py"
    result = _run_script(script, ["--mode", "rules"])
    assert result.returncode == 0, (
        f"drift-check (rules) failed: stdout={result.stdout!r} stderr={result.stderr!r}"
    )


def test_l0_rule_ids_001_no_duplicates_in_kb(contracts_dir: Path):
    """T-L0-RULE-IDS-001 — no duplicate rule ID appears across KB sections."""
    script = contracts_dir / "duplicate-id-check.py"
    assert script.exists(), f"duplicate-id-check.py missing at {script}"
    result = _run_script(script)
    assert result.returncode == 0, (
        f"duplicate ID check failed: stdout={result.stdout!r} stderr={result.stderr!r}"
    )


def test_l0_drift_router_golden_snapshot_matches(contracts_dir: Path):
    """Snapshot test — router-rules.json must match the golden snapshot byte-for-byte
    after canonical re-serialisation. Any intentional change updates the golden file.
    """
    rules_path = contracts_dir / "router-rules.json"
    golden_path = contracts_dir / "golden" / "router-rules.golden.json"
    assert golden_path.exists(), f"golden snapshot missing: {golden_path}"

    rules = json.loads(rules_path.read_text(encoding="utf-8"))
    golden = json.loads(golden_path.read_text(encoding="utf-8"))
    assert rules == golden, "router-rules.json drifted from golden snapshot"
