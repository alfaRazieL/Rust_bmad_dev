"""T-L7-OVERSIZED-DIFF-001 — Oversized diff (>10MB) handled gracefully.

Validator must report `ENVIRONMENT_UNAVAILABLE` with exit code 2
rather than OOM, crash, or silently truncate. The threshold is
configurable via --max-diff-bytes (default 10 MiB).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_l7_oversized_diff_bounded(validator_pkg, contracts_dir, tmp_path):
    # Generate a 12 MiB synthetic diff (above 10 MiB default cap).
    diff_file = tmp_path / "huge.diff"
    chunk = "+padding line content that costs about 64 bytes per emitted line\n"
    big = "diff --git a/big.rs b/big.rs\n--- a/big.rs\n+++ b/big.rs\n@@ -0,0 +1,1 @@\n"
    target_bytes = 12 * 1024 * 1024
    with diff_file.open("w", encoding="utf-8") as fh:
        fh.write(big)
        written = len(big)
        while written < target_bytes:
            fh.write(chunk)
            written += len(chunk)

    story = tmp_path / "STORY.json"
    story.write_text(json.dumps({"story_id": "STORY-OVER-001"}), encoding="utf-8")
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
    assert r.returncode == 2, f"oversized diff must exit 2; got {r.returncode}; stderr={r.stderr}"
    if out.exists():
        env = json.loads(out.read_text(encoding="utf-8"))
        assert env["aggregate"]["verdict"] == "ENVIRONMENT_UNAVAILABLE"
