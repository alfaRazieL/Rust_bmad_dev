"""W9 doc-command copy-run check (G-W9-DOCS).

The operator docs tell an operator to run three command surfaces:

  * the installer            (``rdx-tea/installer/project_installer.py``)
  * the wrapper lifecycle    (``.../scripts/rdx_tea_wrapper.py``)
  * the admission recompute  (``.../scripts/admission.py``)

This test asserts those surfaces are real and copy-runnable: each script
exists at the path the docs reference, each responds to ``--help`` with
exit 0, and each doc actually mentions the script it documents (a drift
guard so a renamed script cannot silently orphan the docs).

Deterministic; ``--help`` runs argparse only — no run is executed, no live
model call is made.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

RDX_TEA_DIR = Path(__file__).resolve().parent.parent.parent
DOCS_DIR = RDX_TEA_DIR / "docs"
SCRIPTS = RDX_TEA_DIR / "poc" / "install-tree" / "_bmad" / "rdx-tea" / "scripts"

INSTALLER = RDX_TEA_DIR / "installer" / "project_installer.py"
WRAPPER = SCRIPTS / "rdx_tea_wrapper.py"
ADMISSION = SCRIPTS / "admission.py"


def _all_docs_text() -> str:
    return "\n".join(
        p.read_text(encoding="utf-8") for p in sorted(DOCS_DIR.rglob("*.md")))


# ---------------------------------------------------------------------------
# The documented scripts exist at the documented paths.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("script", [INSTALLER, WRAPPER, ADMISSION])
def test_documented_script_exists(script: Path) -> None:
    assert script.is_file(), f"documented script missing: {script}"


# ---------------------------------------------------------------------------
# The docs actually reference each script by basename (drift guard).
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("script", [INSTALLER, WRAPPER, ADMISSION])
def test_docs_reference_script(script: Path) -> None:
    assert script.name in _all_docs_text(), \
        f"no operator doc references {script.name}"


# ---------------------------------------------------------------------------
# Each documented command surface is copy-runnable (--help exits 0).
# ---------------------------------------------------------------------------
def _help(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, *args, "--help"],
                          capture_output=True, text=True)


def test_installer_help_runs() -> None:
    proc = _help(str(INSTALLER))
    assert proc.returncode == 0, proc.stderr
    assert "rdx-tea-setup" in proc.stdout


def test_installer_install_help_runs() -> None:
    proc = subprocess.run(
        [sys.executable, str(INSTALLER), "install", "--help"],
        capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    assert "--project" in proc.stdout


def test_wrapper_help_runs() -> None:
    proc = _help(str(WRAPPER))
    assert proc.returncode == 0, proc.stderr
    assert "prepare-run" in proc.stdout and "finalize-run" in proc.stdout


def test_admission_admit_help_runs() -> None:
    proc = subprocess.run(
        [sys.executable, str(ADMISSION), "admit", "--help"],
        capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    assert "--report" in proc.stdout
