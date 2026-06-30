"""T-L7-HA-MODE-DOWNGRADE-001 — Phase 9 HA-specific bypass path.

Scenario: a PR rewrites `_bmad/rdx/config.toml` to lower the project's
enforcement mode (e.g. MODE_4 → MODE_3) so that subsequent diffs would be
gated less strictly.

Defense layer: L7 governance — the file lives under `_bmad/rdx/**`, which
the HA-baseline `approvers.yaml` (see docs/threat-model.md §6) routes to
the `governance` role. The validator synthesises an APPROVAL_REQUIRED rule
(rule_id GOV-RDX-001) and exits 3 unless an authorised governance approval
is committed for the current diff_digest.

This is the L7 structural assertion. The end-to-end recheck (validator
reads diff → matches pattern → blocks) is exercised by the Phase 9
acceptance test T-V6-ACC-05 in
tests/acceptance/ha-adversarial-suite/test_v6_acc_05.py.

Catalogued in RDX_TEST_CASES.yaml as T-L7-HA-MODE-DOWNGRADE-001.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = REPO_ROOT / "tests" / "fixtures"
HA_APPROVERS = FIXTURES / "approvers" / "ha-baseline" / "approvers.yaml"
DIFF_FIXTURE = FIXTURES / "diffs" / "ha-mode-downgrade" / "positive.diff"


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _scaffold(tmp_path: Path) -> tuple[Path, Path, str]:
    (tmp_path / "_bmad" / "rdx" / "approvals").mkdir(parents=True, exist_ok=True)
    shutil.copy(HA_APPROVERS, tmp_path / "_bmad" / "rdx" / "approvers.yaml")
    diff_dst = tmp_path / "diff.patch"
    shutil.copy(DIFF_FIXTURE, diff_dst)
    diff_text = diff_dst.read_text(encoding="utf-8")
    diff_digest = _sha(diff_text)
    (tmp_path / "story.json").write_text(
        json.dumps(
            {
                "story_id": "STORY-HA-MODE-DOWNGRADE",
                "protected_files": [],
                "risk_tags": [],
                "router_suppressions": [],
            }
        ),
        encoding="utf-8",
    )
    evidence = {
        "rdx_schema_version": "v1",
        "story_id": "STORY-HA-MODE-DOWNGRADE",
        "head_sha": "0" * 40,
        "base_sha": "f" * 40,
        "diff_digest": diff_digest,
        "mode": "MODE_4",
        "rules": {
            "CORE-011": {
                "category": 1,
                "verdict": "PASS",
                "severity": "INFO",
                "author": "VALIDATOR",
                "evidence": [
                    {
                        "command": "cargo check --workspace --all-targets",
                        "exit_code": 0,
                        "output_digest": "a" * 64,
                    }
                ],
            }
        },
        "exceptions": [],
        "approvals": [],
        "aggregate": {"verdict": "PASS", "exit_code": 0},
    }
    (tmp_path / "evidence-in.json").write_text(json.dumps(evidence), encoding="utf-8")
    return tmp_path, diff_dst, diff_digest


def _run_validator(project_root: Path, diff_file: Path, out: Path) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT / "rdx-validator")
    return subprocess.run(
        [
            sys.executable, "-m", "rdx_validator",
            "--project-root", str(project_root),
            "--diff-file", str(diff_file),
            "--contracts-dir", str(REPO_ROOT / "tests" / "contracts"),
            "--story", str(project_root / "story.json"),
            "--mode", "MODE_4",
            "--evidence-in", str(project_root / "evidence-in.json"),
            "--evidence-out", str(out),
            "--quiet",
        ],
        capture_output=True, text=True, env=env, check=False,
    )


# -- L0/structural: HA baseline includes the governance pattern -----------------


def test_l7_ha_mode_downgrade_baseline_has_governance_pattern():
    """The HA-baseline approvers.yaml must route `_bmad/rdx/**` to the
    governance role; that's the structural precondition that makes the
    runtime check below meaningful."""

    import yaml

    spec = yaml.safe_load(HA_APPROVERS.read_text(encoding="utf-8"))
    patterns = spec.get("patterns") or []
    rdx_patterns = [p for p in patterns if p.get("path") == "_bmad/rdx/**"]
    assert len(rdx_patterns) == 1, (
        f"HA-baseline approvers.yaml must declare exactly one `_bmad/rdx/**` "
        f"pattern; got {rdx_patterns}"
    )
    assert rdx_patterns[0]["role"] == "governance"
    assert rdx_patterns[0]["rule_id"] == "GOV-RDX-001"


def test_l7_ha_mode_downgrade_fixture_targets_config_toml():
    """The bypass fixture diff must actually modify `_bmad/rdx/config.toml`
    so the governance pattern is exercised on the right path."""

    text = DIFF_FIXTURE.read_text(encoding="utf-8")
    assert "_bmad/rdx/config.toml" in text
    # The mode is being lowered, not raised — otherwise this would not be
    # a downgrade scenario.
    assert "-mode = \"MODE_4\"" in text and "+mode = \"MODE_3\"" in text


# -- runtime: validator blocks the unapproved downgrade -------------------------


def test_l7_ha_mode_downgrade_blocks_without_governance_approval(tmp_path: Path):
    project, diff, _digest = _scaffold(tmp_path)
    out = tmp_path / "evidence.json"
    r = _run_validator(project, diff, out)
    assert r.returncode == 3, (
        f"mode-downgrade PR must be blocked (exit 3), got {r.returncode}\n"
        f"stderr={r.stderr[-2000:]}"
    )
    env = json.loads(out.read_text(encoding="utf-8"))
    assert "GOV-RDX-001" in env["rules"], (
        f"expected GOV-RDX-001 in envelope rules; got {list(env['rules'])}"
    )
    rule = env["rules"]["GOV-RDX-001"]
    assert rule["verdict"] == "APPROVAL_REQUIRED"
    assert rule["category"] == 4


def test_l7_ha_mode_downgrade_unblocks_with_governance_approval(tmp_path: Path):
    project, diff, digest = _scaffold(tmp_path)
    approval = {
        "approval_schema_version": "v1",
        "rule_id": "GOV-RDX-001",
        "approver_identity": "alice@example.com",
        "approver_role": "governance",
        "head_sha": "0" * 40,
        "diff_digest": digest,
        "timestamp": "2026-06-30T12:00:00Z",
        "scope": {"paths": ["_bmad/rdx/config.toml"]},
        "decision": "approved",
    }
    (project / "_bmad" / "rdx" / "approvals" / f"{digest}.json").write_text(
        json.dumps(approval, indent=2), encoding="utf-8"
    )
    out = tmp_path / "evidence.json"
    r = _run_validator(project, diff, out)
    assert r.returncode == 0, (
        f"governance-approved downgrade must pass (exit 0), got {r.returncode}\n"
        f"stderr={r.stderr[-2000:]}"
    )
    env = json.loads(out.read_text(encoding="utf-8"))
    assert env["rules"]["GOV-RDX-001"]["verdict"] == "PASS"
