"""T-L7-DEL-TEST-001 — PR removes #[test] without authorized exception.
Validator's CORE-014 check (already proven at L2) catches it.

This L7 test is an integration-level reaffirmation: invoke the
validator CLI on a synthetic deletion diff and assert CORE-014 FAIL.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_l7_deleted_test_caught(validator_pkg, contracts_dir, tmp_path):
    diff_file = tmp_path / "deleted-tests.diff"
    diff_file.write_text(
        "diff --git a/src/lib.rs b/src/lib.rs\n"
        "index 1..2 100644\n"
        "--- a/src/lib.rs\n"
        "+++ b/src/lib.rs\n"
        "@@ -1,8 +1,3 @@\n"
        " pub fn x() {}\n"
        "-#[test]\n"
        "-fn first_test() { assert!(true); }\n"
        "-\n"
        "-#[test]\n"
        "-fn second_test() { assert_eq!(1, 1); }\n",
        encoding="utf-8",
    )
    story = tmp_path / "STORY.json"
    story.write_text(
        json.dumps(
            {
                "story_id": "STORY-DEL-001",
                "protected_files": [],
                "risk_tags": [],
                "agent_activated_packs": [],
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
    assert r.returncode != 0, f"runner must flag; stderr={r.stderr}"
    env = json.loads(out.read_text(encoding="utf-8"))
    assert env["rules"]["CORE-014"]["verdict"] == "FAIL"
