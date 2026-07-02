"""Policy resolution.

Loads a `--policy-config <FILE>` into a `Policy` object.

Closes (Phase 2):
  T-L1-POL-001 — `mode: advisory` disables all blocking; exit code stays 0.
"""

from __future__ import annotations

import json
from pathlib import Path

from .status import Mode, Policy


def load(path: Path) -> Policy:
    data = json.loads(path.read_text(encoding="utf-8"))
    mode_raw = (data.get("mode") or "MODE_2").upper()
    advisory = bool(data.get("advisory", False))
    if mode_raw == "ADVISORY":
        advisory = True
        mode = Mode.MODE_0
    else:
        try:
            mode = Mode(mode_raw)
        except ValueError as e:
            raise ValueError(f"unknown mode: {mode_raw}") from e
    return Policy(
        mode=mode,
        advisory=advisory,
        accepted_not_run_reasons=tuple(data.get("accepted_not_run_reasons", []) or ()),
        approval_for_baseline_block=bool(data.get("approval_for_baseline_block", False)),
    )
