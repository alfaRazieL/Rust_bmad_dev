#!/usr/bin/env python3
"""W10 acceptance-ladder driver (evidence plane — NOT shipped surface).

Runs the full acceptance ladder (MASTER_IMPLEMENTATION_PLAN §6.9) rung by
rung against the current working tree and records an honest, structured
evidence log to ``ACCEPTANCE_LADDER.json`` beside this file.

This driver lives under ``evidence/`` (the HISTORICAL/evidence plane) and is
never part of the shipped surface; it may invoke pytest / ci_check / the
golden-hash generators. It writes only under this W10 evidence directory.

Usage (from repo root, with the baseline venv python)::

    rdx-tea/.venv-baseline/bin/python \
        rdx-tea/evidence/logs/W10/run_acceptance_ladder.py

Determinism note: pytest pass-counts and golden-hash lines are
deterministic; the recorded ``git_head`` reflects the tree the ladder ran
against. No wall-clock is embedded (the JSON is an audit record, not a
golden generator).
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[3]  # rdx-tea/evidence/logs/W10 -> repo root
PY = sys.executable

# Each rung: (id, gate-ids, description, argv). argv runs from REPO_ROOT.
LADDER: list[tuple[str, str, str, list[str]]] = [
    ("W2-canonical-pin", "G-W2-CANON/G-DET",
     "canonical snapshot hash matches pin",
     [PY, "rdx-tea/evidence/hashes/w2_canonical_snapshot.py"]),
    ("W3-bundle-golden", "G-W3-DETERMINISM/G-DET",
     "golden bundle signature matches pin",
     [PY, "rdx-tea/evidence/hashes/w3_bundle_golden.py"]),
    ("W2-router", "G-W2-PARITY/G-W2-FORBIDDEN",
     "router parity + forbidden/docs-only pack activation",
     [PY, "-m", "pytest", "rdx-tea/tests",
      "-k", "router_parity or forbidden or docs_only", "-q"]),
    ("W3-schema-identity", "G-W3-IDENTITY/G-W3-SCHEMA",
     "bundle identity fail-closed + schema validation",
     [PY, "-m", "pytest", "rdx-tea/tests", "-k", "identity or schema", "-q"]),
    ("W4-lifecycle", "G-W4-LIFECYCLE/G-W4-SEQUENTIAL/G-W4-NOTASK",
     "wrapper prepare->child->finalize slice + sequential + no-Task",
     [PY, "-m", "pytest", "rdx-tea/tests/bmad-tea", "rdx-tea/tests/lifecycle", "-q"]),
    ("W5-sidecar-delta-consistency", "G-W5-SIDECAR/G-W5-DELTA/G-W5-CONSISTENCY",
     "one sidecar/artefact, workspace delta, artifact consistency",
     [PY, "-m", "pytest", "rdx-tea/tests",
      "-k", "sidecar or dedupe or delta or consistency", "-q"]),
    ("W6-verifier-admission-failclosed", "G-W6-VERIFIER/G-W6-ADMISSION/G-W6-FAILCLOSED",
     "verifier per-check mutation, admission recompute, fail-closed",
     [PY, "-m", "pytest", "rdx-tea/tests",
      "-k", "verifier or admission or failclosed", "-q"]),
    ("W7-installer", "G-W7-INSTALL/G-W7-NOAUTH/G-W7-IDEMPOTENT",
     "installer install/update/uninstall + no-auth + idempotent",
     [PY, "-m", "pytest", "rdx-tea/tests/lifecycle/test_l4_w7_installer.py", "-q"]),
    ("W8-ci-boundary-auth", "G-W8-CI/G-SPLIT-IMPORT/G-AUTH",
     "ci_check boundary/auth unit tests",
     [PY, "-m", "pytest", "rdx-tea/tests/ci", "-q"]),
    ("W8-boundary-check", "G-SPLIT-IMPORT",
     "ci_check boundary-check over shipped surface",
     [PY, "rdx-tea/live-harness/ci_check.py", "boundary-check",
      "rdx-tea/poc/install-tree", "rdx-tea/installer"]),
    ("W8-auth-check", "G-AUTH",
     "ci_check auth-check over shipped surface",
     [PY, "rdx-tea/live-harness/ci_check.py", "auth-check",
      "rdx-tea/poc/install-tree", "rdx-tea/installer"]),
    ("W9-docs", "G-W9-DOCS/G-W9-NOEVALFLAGS",
     "operator docs copy-run + doc-lint",
     [PY, "-m", "pytest", "rdx-tea/tests/docs", "-q"]),
    ("W10-acceptance", "G-W10-E2E/G-W10-ROLLBACK",
     "clean-install E2E, lifecycle smoke admissible, rollback",
     [PY, "-m", "pytest", "rdx-tea/tests/acceptance", "-q"]),
    ("full-suite", "ALL",
     "entire rdx-tea/tests suite (single canonical collection)",
     [PY, "-m", "pytest", "rdx-tea/tests", "-q"]),
]

_PYTEST_TAIL = re.compile(r"(\d+) passed(?:, (\d+) skipped)?(?:, (\d+) failed)?")


def _tail(text: str, n: int = 6) -> str:
    lines = [ln for ln in text.strip().splitlines() if ln.strip()]
    return "\n".join(lines[-n:])


def _pytest_counts(text: str) -> dict | None:
    m = None
    for m in _PYTEST_TAIL.finditer(text):
        pass
    if not m:
        return None
    return {
        "passed": int(m.group(1)),
        "skipped": int(m.group(2) or 0),
        "failed": int(m.group(3) or 0),
    }


def main() -> int:
    env = {"PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin"}
    import os
    run_env = os.environ.copy()
    run_env.pop("RDX_TEA_FAKE_NOW", None)

    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT,
                          capture_output=True, text=True).stdout.strip()

    rungs = []
    all_green = True
    for rung_id, gates, desc, argv in LADDER:
        proc = subprocess.run(argv, cwd=REPO_ROOT, capture_output=True,
                              text=True, env=run_env)
        combined = proc.stdout + proc.stderr
        counts = _pytest_counts(combined)
        ok = proc.returncode == 0 and (counts is None or counts["failed"] == 0)
        all_green = all_green and ok
        rungs.append({
            "rung": rung_id,
            "gates": gates,
            "description": desc,
            "command": " ".join(
                "python" if a == PY else a for a in argv),
            "cwd": "<repo-root>",
            "exit_code": proc.returncode,
            "pytest_counts": counts,
            "result": "PASS" if ok else "FAIL",
            "stdout_tail": _tail(combined),
        })
        print(f"[{'PASS' if ok else 'FAIL'}] {rung_id}: exit={proc.returncode} "
              f"{counts or ''}")

    out = {
        "schema": "rdx-tea-acceptance-ladder.v1",
        "stage": "W10 acceptance ladder (MASTER_IMPLEMENTATION_PLAN §6.9)",
        "git_head": head,
        "python": PY,
        "all_rungs_green": all_green,
        "rung_count": len(rungs),
        "rungs": rungs,
        "notes": [
            "Rungs 1-5 (deterministic) green before any live smoke; rung 6 "
            "live-model child is separately owner-authorized and NOT run here.",
            "source-lock verify (bootstrap --verify-only) requires the upstream "
            "clone and runs in GitHub Actions on push; last verified PASS at W8 CI.",
            "This is a local surrogate for the offline-capable CI gates; the "
            "authoritative GitHub Actions run executes on push.",
        ],
    }
    (HERE / "ACCEPTANCE_LADDER.json").write_text(
        json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"\nall_rungs_green={all_green}  ({len(rungs)} rungs)")
    return 0 if all_green else 1


if __name__ == "__main__":
    sys.exit(main())
