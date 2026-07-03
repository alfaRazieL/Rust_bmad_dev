#!/usr/bin/env python3
"""Invoke the real Claude Code CLI in headless mode against a prepared
workspace. Saves the full transcript to
`<workspace>/_bmad/rdx-tea/runtime/<workflow>/<run_id>/transcript.stream.jsonl`.

Live-only: NO simulator fallback. If the CLI is missing, fails closed.

Args:
  --workspace   the prepared workspace (from prepare_workspace.py)
  --workflow    e.g. test-design
  --run-id      the run identifier
  --model       cheap model to use (defaults to haiku)
  --max-budget-usd     hard budget cap
  --timeout-seconds    hard wall-clock cap
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_MODEL = "haiku"
FORBIDDEN_MODELS = ("opus", "claude-opus-4-7")
# D3.3.3 §8: model aliases are refused. A live pilot run must pin the
# exact schedule model ID (e.g. claude-haiku-4-5-20251001).
MODEL_ALIASES = ("haiku", "sonnet", "opus")
import re as _re
_EXACT_MODEL_RE = _re.compile(r"^claude-[a-z]+-\d+-\d+-\d{8}$")


def _stream_transcript(workspace: Path, workflow: str, run_id: str) -> Path:
    p = workspace / "_bmad" / "rdx-tea" / "runtime" / workflow / run_id / "transcript.stream.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def build_prompt(workflow: str) -> str:
    """The prompt handed to `claude -p`. Instructs the session to run
    the RDX-TEA wrapper skill, which itself invokes the underlying
    bmad-testarch-* child skill."""
    return (
        f"Invoke the /rdx-tea-{workflow} skill on the current project. "
        f"Follow every activation step in the wrapper's SKILL.md. "
        f"Do NOT skip the prepare-run or finalize-run subcommands. "
        f"Use the actual bmad-testarch-{workflow} child skill — do not "
        f"substitute output. Halt on any non-zero exit. When done, "
        f"summarise the run-report.json path."
    )


def _assert_exact_model(model: str, *, require_exact: bool) -> None:
    if model.lower() in FORBIDDEN_MODELS:
        raise RuntimeError(f"model {model!r} is forbidden by cost policy")
    if require_exact:
        if model in MODEL_ALIASES:
            raise RuntimeError(
                f"model alias {model!r} refused — D3.3.3 §8 requires the "
                f"exact pinned schedule model ID (e.g. claude-haiku-4-5-20251001)"
            )
        if not _EXACT_MODEL_RE.match(model):
            raise RuntimeError(
                f"model {model!r} is not an exact dated model ID "
                f"(expected pattern claude-<name>-<n>-<n>-YYYYMMDD)"
            )


def invoke(*,
           workspace: Path,
           workflow: str,
           run_id: str,
           model: str = DEFAULT_MODEL,
           max_budget_usd: float = 5.00,
           timeout_seconds: int = 900,
           prompt_override: str | None = None,
           settings_path: Path | None = None,
           mcp_config_path: Path | None = None,
           setting_sources: str | None = None,
           disallowed_tools: list[str] | None = None,
           permission_mode: str = "bypassPermissions",
           require_exact_model: bool = False) -> dict:
    """Invoke the real Claude Code CLI headlessly.

    D3.3.3 §1/§6: this function NEVER sets CLAUDE_CONFIG_DIR. It relies
    on the caller's inherited auth environment (existing CLI OAuth) and
    isolates only the PROJECT surface via --setting-sources /
    --strict-mcp-config / --mcp-config / --disallowedTools. No API key,
    no token helper, no --bare.
    """
    _assert_exact_model(model, require_exact=require_exact_model)
    cli = "claude"
    prompt = prompt_override if prompt_override is not None else build_prompt(workflow)
    transcript_path = _stream_transcript(workspace, workflow, run_id)
    cmd = [
        cli, "-p", prompt,
        "--model", model,
        "--output-format", "stream-json",
        "--verbose",
        "--max-budget-usd", str(max_budget_usd),
        "--permission-mode", permission_mode,
        "--add-dir", str(workspace),
        "--no-session-persistence",
    ]
    # D3.3.3 §6.4 project-only settings.
    if setting_sources:
        cmd += ["--setting-sources", setting_sources]
    if settings_path is not None:
        cmd += ["--settings", str(settings_path)]
    # D3.3.3 §6.3 strict empty MCP.
    if mcp_config_path is not None:
        cmd += ["--strict-mcp-config", "--mcp-config", str(mcp_config_path)]
    # D3.3.3 §9.2 deny subagent dispatch tools.
    if disallowed_tools:
        cmd += ["--disallowedTools", *disallowed_tools]
    start = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    try:
        result = subprocess.run(
            cmd, cwd=str(workspace),
            capture_output=True, text=True, check=False,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        # D3.3.3 §11: a timeout produces failure evidence — the
        # transcript (partial) is still written where available.
        return {
            "started_at": start,
            "finished_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "exit_code": -1,
            "reason": "timeout",
            "transcript_path": str(transcript_path),
            "command": cmd,
            "model": model,
        }
    transcript_path.write_text(result.stdout, encoding="utf-8")
    return {
        "started_at": start,
        "finished_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "exit_code": result.returncode,
        "transcript_path": str(transcript_path),
        "stderr_tail": result.stderr[-2000:],
        "command": cmd,
        "model": model,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", required=True, type=Path)
    ap.add_argument("--workflow", required=True)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--max-budget-usd", type=float, default=5.00)
    ap.add_argument("--timeout-seconds", type=int, default=900)
    args = ap.parse_args()
    try:
        r = invoke(
            workspace=args.workspace, workflow=args.workflow, run_id=args.run_id,
            model=args.model, max_budget_usd=args.max_budget_usd,
            timeout_seconds=args.timeout_seconds,
        )
    except RuntimeError as err:
        print(f"invoke_runtime failed: {err}", file=sys.stderr)
        return 1
    print(json.dumps(r, indent=2, sort_keys=True))
    return 0 if r["exit_code"] == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
