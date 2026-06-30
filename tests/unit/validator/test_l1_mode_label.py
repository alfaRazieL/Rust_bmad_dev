"""Phase 4 — validator output explicitly labels the current mode.

From the Phase 4 plan:
    - Validator output explicitly labels current mode

The envelope already carries the raw `mode` code (MODE_0..MODE_4 — covered
by T-L1-POL-001 / aggregator tests). Phase 4 adds the human-facing
`mode_label` field so downstream consumers (the wrapper report, the CI
summary, the hook message) don't have to maintain their own mode→label
table — and don't risk drifting into calling Mode 1 "Enforced".

The labels are normative; they're what T-L5-MODE-001 (smoke half in
test_mode_naming.py) checks the docs against.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
VALIDATOR = REPO_ROOT / "rdx-validator" / "rdx_validator" / "cli.py"

EXPECTED_LABELS = {
    "MODE_0": "Advisory",
    "MODE_1": "Local Validated",
    "MODE_2": "Local Gated",
    "MODE_3": "CI Enforced",
    "MODE_4": "Specialist Approval",
}


def _run_validator(diff_file: Path, mode: str) -> dict:
    r = subprocess.run(
        [
            sys.executable,
            str(VALIDATOR),
            "--diff-file",
            str(diff_file),
            "--mode",
            mode,
            "--contracts-dir",
            str(REPO_ROOT / "tests" / "contracts"),
        ],
        capture_output=True,
        text=True,
        check=False,
        cwd=REPO_ROOT,
    )
    # The validator writes evidence JSON to stdout (unless --quiet).
    assert r.stdout.strip(), (
        f"validator produced no stdout for mode={mode}\nstderr:{r.stderr}"
    )
    return json.loads(r.stdout)


@pytest.fixture(scope="module")
def trivial_diff(tmp_path_factory) -> Path:
    """An intentionally-empty diff so the run completes cleanly regardless
    of mode (Phase 4 is about envelope formatting, not check semantics)."""
    p = tmp_path_factory.mktemp("mode-label-fixture") / "empty.diff"
    p.write_text("", encoding="utf-8")
    return p


@pytest.mark.parametrize("mode,label", list(EXPECTED_LABELS.items()))
def test_envelope_includes_mode_label(trivial_diff: Path, mode: str, label: str):
    env = _run_validator(trivial_diff, mode)
    assert env.get("mode") == mode, f"raw mode field must round-trip; got {env.get('mode')!r}"
    assert env.get("mode_label") == label, (
        f"mode_label for {mode} must be {label!r}; got {env.get('mode_label')!r}"
    )


def test_envelope_mode_label_is_distinct_field_not_overload(trivial_diff: Path):
    """`mode` and `mode_label` are separate fields — downstream parsers must
    not have to choose between machine code and human label."""
    env = _run_validator(trivial_diff, "MODE_1")
    assert "mode" in env and "mode_label" in env
    assert env["mode"] != env["mode_label"], (
        "mode (machine) and mode_label (human) must be different strings"
    )
