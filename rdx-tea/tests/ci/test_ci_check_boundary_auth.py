"""W8 CI check tooling — production/eval boundary + auth-preservation greps.

Unit tests for the new ``ci_check.py`` subcommands that Wave 8 wires into
``.github/workflows/rdx-tea-integration-check.yml``:

  * ``boundary-check <surface> ...`` — G-SPLIT-IMPORT. Fails on any hit of
    ``import live_harness`` / ``import evals`` / ``live-harness/`` /
    ``evals/`` / ``evidence/`` / ``research/`` in a shipped/distribution
    surface.
  * ``auth-check <surface> ...`` — G-AUTH. Fails on any auth material or
    ``CLAUDE_CONFIG_DIR`` override in a shipped/distribution surface.

Both checks are fail-closed: a missing surface is an ERROR (a rename must
not silently pass), ``__pycache__`` is ignored, and the real shipped
surfaces (``poc/install-tree`` and ``installer``) must be clean.

ci_check.py lives in ``live-harness`` (CI tooling, test/CI plane — NOT the
shipped runtime), so importing it here does not touch G-SPLIT-IMPORT, which
governs only ``poc/install-tree`` and ``installer``.

Deterministic only. No live model calls.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

RDX_TEA_DIR = Path(__file__).resolve().parent.parent.parent
CI_CHECK_PY = RDX_TEA_DIR / "live-harness" / "ci_check.py"
SHIPPED_SURFACES = (
    RDX_TEA_DIR / "poc" / "install-tree",
    RDX_TEA_DIR / "installer",
)


def _load_ci_check():
    spec = importlib.util.spec_from_file_location("rdx_tea_ci_check", CI_CHECK_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


cc = _load_ci_check()


# --------------------------------------------------------------------------- #
# Real shipped surfaces are clean (the production invariant W8 must guard).
# --------------------------------------------------------------------------- #
def test_boundary_check_real_shipped_surfaces_pass(capsys) -> None:
    rc = cc.boundary_check(list(SHIPPED_SURFACES))
    out = json.loads(capsys.readouterr().out)
    assert rc == 0, out
    assert out["status"] == "PASS"
    assert out["hits"] == []


def test_auth_check_real_shipped_surfaces_pass(capsys) -> None:
    rc = cc.auth_check(list(SHIPPED_SURFACES))
    out = json.loads(capsys.readouterr().out)
    assert rc == 0, out
    assert out["status"] == "PASS"
    assert out["hits"] == []


# --------------------------------------------------------------------------- #
# Every boundary token fails closed.
# --------------------------------------------------------------------------- #
BOUNDARY_HITS = (
    "import live_harness",
    "import evals",
    "from live-harness/foo import bar",   # contains live-harness/
    "path = 'evals/fixtures'",            # contains evals/
    "open('evidence/hashes')",            # contains evidence/
    "see research/notes",                 # contains research/
)


@pytest.mark.parametrize("line", BOUNDARY_HITS)
def test_boundary_check_fails_on_forbidden_token(tmp_path: Path, capsys, line: str) -> None:
    surface = tmp_path / "ship"
    surface.mkdir()
    (surface / "leak.py").write_text(f"x = 1\n{line}\n", encoding="utf-8")
    rc = cc.boundary_check([surface])
    out = json.loads(capsys.readouterr().out)
    assert rc != 0, out
    assert out["status"] == "FAIL"
    assert len(out["hits"]) >= 1
    assert out["hits"][0]["file"].endswith("leak.py")


@pytest.mark.parametrize("tok", [
    "ANTHROPIC_API_KEY",
    "CLAUDE_CODE_OAUTH_TOKEN",
    "apiKeyHelper",
    "setup-token",
    ".credentials.json",
    "CLAUDE_CONFIG_DIR",
])
def test_auth_check_fails_on_auth_token(tmp_path: Path, capsys, tok: str) -> None:
    surface = tmp_path / "ship"
    surface.mkdir()
    (surface / "cfg.json").write_text(f'{{"x": "{tok}"}}\n', encoding="utf-8")
    rc = cc.auth_check([surface])
    out = json.loads(capsys.readouterr().out)
    assert rc != 0, out
    assert out["status"] == "FAIL"
    assert any(h["token"] == tok for h in out["hits"])


# --------------------------------------------------------------------------- #
# Fail-closed on a missing surface (a rename must never silently pass).
# --------------------------------------------------------------------------- #
def test_boundary_check_missing_surface_is_error(tmp_path: Path, capsys) -> None:
    rc = cc.boundary_check([tmp_path / "does-not-exist"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 9
    assert out["status"] == "ERROR"
    assert out["missing_surfaces"]


def test_auth_check_missing_surface_is_error(tmp_path: Path, capsys) -> None:
    rc = cc.auth_check([tmp_path / "does-not-exist"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 9
    assert out["status"] == "ERROR"


# --------------------------------------------------------------------------- #
# __pycache__ is ignored (compiled artefacts are not the shipped source).
# --------------------------------------------------------------------------- #
def test_boundary_check_ignores_pycache(tmp_path: Path, capsys) -> None:
    surface = tmp_path / "ship"
    (surface / "__pycache__").mkdir(parents=True)
    (surface / "__pycache__" / "x.txt").write_text("import evals\n", encoding="utf-8")
    (surface / "clean.py").write_text("x = 1\n", encoding="utf-8")
    rc = cc.boundary_check([surface])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0, out
    assert out["status"] == "PASS"


def test_boundary_check_skips_binary_files(tmp_path: Path, capsys) -> None:
    surface = tmp_path / "ship"
    surface.mkdir()
    (surface / "blob.bin").write_bytes(b"\xff\xfe\x00import evals\x00")
    (surface / "clean.py").write_text("x = 1\n", encoding="utf-8")
    rc = cc.boundary_check([surface])
    out = json.loads(capsys.readouterr().out)
    # Undecodable bytes are skipped rather than crashing the check.
    assert rc == 0, out
    assert out["status"] == "PASS"


# --------------------------------------------------------------------------- #
# CLI surface (what the workflow actually invokes).
# --------------------------------------------------------------------------- #
def _run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(CI_CHECK_PY), *args],
        capture_output=True, text=True,
    )


def test_cli_boundary_check_clean_surface_exit_zero() -> None:
    proc = _run_cli("boundary-check", *[str(s) for s in SHIPPED_SURFACES])
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert json.loads(proc.stdout)["status"] == "PASS"


def test_cli_auth_check_clean_surface_exit_zero() -> None:
    proc = _run_cli("auth-check", *[str(s) for s in SHIPPED_SURFACES])
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert json.loads(proc.stdout)["status"] == "PASS"


def test_cli_boundary_check_dirty_surface_exit_nonzero(tmp_path: Path) -> None:
    surface = tmp_path / "ship"
    surface.mkdir()
    (surface / "leak.py").write_text("import live_harness\n", encoding="utf-8")
    proc = _run_cli("boundary-check", str(surface))
    assert proc.returncode != 0
    assert json.loads(proc.stdout)["status"] == "FAIL"
