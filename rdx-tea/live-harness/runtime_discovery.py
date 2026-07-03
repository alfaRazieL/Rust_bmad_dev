#!/usr/bin/env python3
"""Detect the local Claude Code CLI and its headless capabilities.

Writes a JSON report to `--out` (or stdout). Fails closed if:
  - `claude` is not on PATH;
  - `--version` returns an unsupported major version (< 2);
  - `--print` and `--output-format stream-json` are not in the help
    output (indicates a fork or downgrade that cannot drive the
    harness).

Exit codes:
  0 = discovery succeeded
  1 = CLI missing
  2 = version unsupported
  3 = headless surface missing
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path


def _which(name: str) -> str | None:
    p = shutil.which(name)
    return str(Path(p)) if p else None


def _version(cli: str) -> str | None:
    r = subprocess.run([cli, "--version"], capture_output=True, text=True, check=False)
    if r.returncode != 0:
        return None
    m = re.search(r"(\d+\.\d+\.\d+)", r.stdout)
    return m.group(1) if m else None


def _help_text(cli: str) -> str:
    r = subprocess.run([cli, "--help"], capture_output=True, text=True, check=False)
    return r.stdout + r.stderr


def discover(cli_name: str = "claude") -> dict:
    cli = _which(cli_name)
    if not cli:
        return {"status": "MISSING", "reason": f"{cli_name} not on PATH"}
    ver = _version(cli)
    if not ver:
        return {"status": "UNKNOWN_VERSION", "cli": cli}
    major = int(ver.split(".")[0])
    if major < 2:
        return {"status": "UNSUPPORTED_VERSION", "cli": cli, "version": ver}
    help_txt = _help_text(cli)
    needed = ("--print", "--output-format", "stream-json")
    missing = [f for f in needed if f not in help_txt]
    if missing:
        return {
            "status": "HEADLESS_SURFACE_MISSING",
            "cli": cli, "version": ver, "missing": missing,
        }
    return {
        "status": "READY",
        "cli": cli,
        "version": ver,
        "surface": {
            "print": "--print",
            "output_format": "stream-json",
            "verbose": "--verbose",
            "max_budget_usd": "--max-budget-usd",
            "session_id": "--session-id",
        },
        "default_model_policy": {
            "allowed": ["claude-haiku-4-5-20251001", "claude-sonnet-4-6"],
            "forbidden": ["claude-opus-4-7", "opus"],
            "note": "D3.3 cost policy: live evals never use Opus.",
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--cli", default="claude")
    args = ap.parse_args()
    r = discover(args.cli)
    text = json.dumps(r, indent=2, sort_keys=True)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    print(text)
    return {"MISSING": 1, "UNKNOWN_VERSION": 2, "UNSUPPORTED_VERSION": 2,
            "HEADLESS_SURFACE_MISSING": 3, "READY": 0}.get(r["status"], 2)


if __name__ == "__main__":
    sys.exit(main())
