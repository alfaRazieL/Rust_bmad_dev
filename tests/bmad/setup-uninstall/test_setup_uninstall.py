"""L4 setup / uninstall tests — T-L4-SETUP-001/002/003.

These tests run the deterministic install + uninstall scripts shipped by
the rdx-setup skill against a sandboxed temp project. They verify:

- T-L4-SETUP-001: fresh install writes KB sections + agent override TOMLs
  + `[modules.rdx]` config block.
- T-L4-SETUP-002: re-running the install is idempotent — no duplicate
  entries, no destruction of foreign customizations.
- T-L4-SETUP-003: uninstall returns the project to its pre-install state
  (RDX KB sections removed, RDX-tagged overrides removed, foreign user
  overrides preserved, `[modules.rdx]` removed).

The scripts live under `.claude/skills/rdx-setup/scripts/install.py` and
`.../uninstall.py` so they can be invoked deterministically here AND
followed step-by-step by Claude when executing the SKILL.md prose.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
RDX_SETUP_DIR = REPO_ROOT / ".claude" / "skills" / "rdx-setup"
INSTALL_SCRIPT = RDX_SETUP_DIR / "scripts" / "install.py"
UNINSTALL_SCRIPT = RDX_SETUP_DIR / "scripts" / "uninstall.py"
FOREIGN_FIXTURE = (
    Path(__file__).resolve().parent
    / "existing-custom-fixture"
    / "bmad-agent-dev.toml"
)

EXPECTED_KB_FILES = [
    "section-4-core.md",
    "section-5-router.md",
    "section-6-packs.md",
    "section-8-governance.md",
]
EXPECTED_OVERRIDE_FILES = [
    "bmad-agent-dev.toml",
    "bmad-agent-architect.toml",
    "bmad-agent-pm.toml",
]


def _run(script: Path, project_root: Path) -> subprocess.CompletedProcess:
    """Run install/uninstall script with --project-root.

    These scripts have no third-party deps so a plain subprocess call works.
    """
    return subprocess.run(
        [sys.executable, str(script), "--project-root", str(project_root)],
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.fixture
def clean_project(tmp_path: Path) -> Path:
    """Sandbox project: empty `_bmad/` with a minimal config.yaml."""
    proj = tmp_path / "clean-project"
    (proj / "_bmad").mkdir(parents=True)
    (proj / "_bmad" / "config.yaml").write_text(
        "modules:\n  bmad_core:\n    version: \"1.0.0\"\n",
        encoding="utf-8",
    )
    return proj


@pytest.fixture
def project_with_foreign(tmp_path: Path) -> Path:
    """Sandbox project with a pre-existing foreign user customization."""
    proj = tmp_path / "project-with-foreign"
    (proj / "_bmad" / "custom").mkdir(parents=True)
    (proj / "_bmad" / "config.yaml").write_text(
        "modules:\n  bmad_core:\n    version: \"1.0.0\"\n",
        encoding="utf-8",
    )
    shutil.copy(FOREIGN_FIXTURE, proj / "_bmad" / "custom" / "bmad-agent-dev.toml")
    return proj


def test_install_script_exists():
    assert INSTALL_SCRIPT.exists(), f"install script missing: {INSTALL_SCRIPT}"
    assert UNINSTALL_SCRIPT.exists(), f"uninstall script missing: {UNINSTALL_SCRIPT}"


def test_t_l4_setup_001_fresh_install(clean_project: Path):
    """T-L4-SETUP-001 — fresh install writes KB sections, overrides, config."""
    result = _run(INSTALL_SCRIPT, clean_project)
    assert result.returncode == 0, f"install failed: {result.stderr}\n{result.stdout}"

    # KB sections present.
    kb_dir = clean_project / "_bmad" / "rust-kb"
    for fname in EXPECTED_KB_FILES:
        assert (kb_dir / fname).exists(), f"missing KB file: {fname}"

    # Agent override TOMLs present.
    custom_dir = clean_project / "_bmad" / "custom"
    for fname in EXPECTED_OVERRIDE_FILES:
        assert (custom_dir / fname).exists(), f"missing override: {fname}"

    # config.yaml updated with [modules.rdx].
    config_text = (clean_project / "_bmad" / "config.yaml").read_text()
    assert "rdx:" in config_text, "config.yaml missing modules.rdx section"


def test_t_l4_setup_002_install_is_idempotent(project_with_foreign: Path):
    """T-L4-SETUP-002 — second install run does not duplicate entries
    and does not destroy foreign customizations."""
    r1 = _run(INSTALL_SCRIPT, project_with_foreign)
    assert r1.returncode == 0, f"first install failed: {r1.stderr}"
    dev_after_first = (
        project_with_foreign / "_bmad" / "custom" / "bmad-agent-dev.toml"
    ).read_text()

    r2 = _run(INSTALL_SCRIPT, project_with_foreign)
    assert r2.returncode == 0, f"second install failed: {r2.stderr}"
    dev_after_second = (
        project_with_foreign / "_bmad" / "custom" / "bmad-agent-dev.toml"
    ).read_text()

    # Bytewise idempotent.
    assert dev_after_first == dev_after_second, "install not idempotent"

    # Foreign user's XX entry and principle still present.
    assert "user-custom-skill" in dev_after_second
    assert "User-added principle preserved" in dev_after_second

    # Single RDX-DS entry (no duplicate).
    rdx_ds_count = dev_after_second.count('skill = "rdx-dev-story"')
    assert rdx_ds_count == 1, f"DS→rdx-dev-story must appear once, got {rdx_ds_count}"


def test_t_l4_setup_003_uninstall_round_trip(project_with_foreign: Path):
    """T-L4-SETUP-003 — uninstall removes RDX artifacts, preserves foreign."""
    # Install first.
    r1 = _run(INSTALL_SCRIPT, project_with_foreign)
    assert r1.returncode == 0, f"install failed: {r1.stderr}"

    # Uninstall.
    r2 = _run(UNINSTALL_SCRIPT, project_with_foreign)
    assert r2.returncode == 0, f"uninstall failed: {r2.stderr}\n{r2.stdout}"

    # KB sections removed.
    kb_dir = project_with_foreign / "_bmad" / "rust-kb"
    assert not kb_dir.exists() or not any(kb_dir.iterdir()), (
        "rust-kb dir should be empty or removed after uninstall"
    )

    # RDX-tagged content removed from dev override; foreign content preserved.
    dev = (
        project_with_foreign / "_bmad" / "custom" / "bmad-agent-dev.toml"
    ).read_text()
    assert "rdx-dev-story" not in dev, "RDX DS override must be removed"
    assert "rust-kb/section-4-core.md" not in dev, "RDX persistent_facts must be removed"
    assert "user-custom-skill" in dev, "foreign user XX entry must be preserved"
    assert "User-added principle preserved" in dev, (
        "foreign user principle must be preserved"
    )

    # [modules.rdx] removed from config.yaml.
    config = (project_with_foreign / "_bmad" / "config.yaml").read_text()
    assert "rdx:" not in config, "[modules.rdx] must be removed after uninstall"
