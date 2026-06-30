"""T-L7-DISABLED-PACK-001 — Author omits a real pack from the claimed
activated_packs. CI re-runs the router and CORE-015 raises FAIL.

This is an integration-level reaffirmation of T-L2-CORE015-001 (which
already covers the unit-level case). The L7 test calls the validator
CLI to ensure end-to-end behaviour matches.
"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest


def test_l7_disabled_pack_caught(validator_pkg, contracts_dir, tmp_path):
    """Diff introduces unsafe code; story claims unsafe pack is NOT active."""
    diff_file = tmp_path / "unsafe.diff"
    diff_file.write_text(
        "diff --git a/src/lib.rs b/src/lib.rs\n"
        "index 1..2 100644\n"
        "--- a/src/lib.rs\n"
        "+++ b/src/lib.rs\n"
        "@@ -1,1 +1,4 @@\n"
        " pub fn x() {}\n"
        "+pub unsafe fn raw() {\n"
        "+    *(0 as *const u8);\n"
        "+}\n",
        encoding="utf-8",
    )
    story = tmp_path / "STORY.json"
    story.write_text(
        json.dumps(
            {
                "story_id": "STORY-DISABLED-001",
                "protected_files": [],
                "risk_tags": [],
                "agent_activated_packs": [],  # author lied: omitted unsafe
            }
        ),
        encoding="utf-8",
    )
    out = tmp_path / "evidence.json"

    r = subprocess.run(
        [
            sys.executable,
            "-m",
            "rdx_validator",
            "--project-root",
            str(tmp_path),
            "--diff-file",
            str(diff_file),
            "--story",
            str(story),
            "--mode",
            "MODE_3",
            "--contracts-dir",
            str(contracts_dir),
            "--evidence-out",
            str(out),
        ],
        cwd=str(validator_pkg),
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode != 0, f"runner should refuse; stdout={r.stdout}"
    env = json.loads(out.read_text(encoding="utf-8"))
    core_015 = env["rules"].get("CORE-015")
    assert core_015 is not None
    assert core_015["verdict"] == "FAIL", core_015
