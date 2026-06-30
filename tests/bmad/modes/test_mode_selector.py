"""Phase 4 — mode selector + enforcement_level persistence (deterministic L4).

These tests cover the Phase 4 Implementation tasks:
  - `rdx-setup` interactive mode selector
  - Config records `enforcement_level` matching selected mode

The interactive prompting itself is an LLM-cooperative concern (the SKILL.md
prose walks the user through it). What we lock here is the *deterministic
artifact*: when the install script runs with `--enforcement-level MODE_X`,
the `[modules.rdx].enforcement_level` field in `config.yaml` records the
selected mode verbatim.

The mode set covered by Phase 4:
  - MODE_0 — Advisory       (informational only, exit 0 regardless)
  - MODE_1 — Local Validated (wrapper soft-gate; default)
  - MODE_2 — Local Gated     (pre-push hook; opt-in, --no-verify bypass)
  - MODE_3 — CI Enforced     (CI required check; tamper-resistant)
  - MODE_4 — Specialist Approval (Cat-4; deferred to Phase 8 for full wiring,
                                  Phase 4 only accepts the value)
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
INSTALL_SCRIPT = REPO_ROOT / ".claude" / "skills" / "rdx-setup" / "scripts" / "install.py"


def _install(project_root: Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(INSTALL_SCRIPT), "--project-root", str(project_root), *extra],
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.fixture
def empty_project(tmp_path: Path) -> Path:
    proj = tmp_path / "empty"
    (proj / "_bmad").mkdir(parents=True)
    (proj / "_bmad" / "config.yaml").write_text(
        "modules:\n  bmad_core:\n    version: \"1.0.0\"\n",
        encoding="utf-8",
    )
    return proj


def _read_rdx_block(project_root: Path) -> dict:
    cfg = yaml.safe_load(
        (project_root / "_bmad" / "config.yaml").read_text(encoding="utf-8")
    )
    return (cfg.get("modules") or {}).get("rdx", {}) or {}


@pytest.mark.parametrize(
    "mode_value",
    ["MODE_0", "MODE_1", "MODE_2", "MODE_3", "MODE_4"],
)
def test_install_records_enforcement_level_in_config(empty_project: Path, mode_value: str):
    """Install script must persist the selected mode into [modules.rdx]."""
    r = _install(empty_project, "--enforcement-level", mode_value)
    assert r.returncode == 0, f"install failed for {mode_value}: {r.stderr}\n{r.stdout}"
    block = _read_rdx_block(empty_project)
    assert block.get("enforcement_level") == mode_value, (
        f"enforcement_level must be {mode_value}; got {block.get('enforcement_level')!r}"
    )


def test_install_default_is_mode_1_local_validated(empty_project: Path):
    """Omitting --enforcement-level defaults to MODE_1 (Local Validated).

    MODE_1 matches the rdx-dev-story wrapper's soft-gate contract — anything
    looser (MODE_0) would silently disable the wrapper's failure halt, and
    anything stricter (MODE_2+) requires the user to opt into the hook /
    CI required check.
    """
    r = _install(empty_project)
    assert r.returncode == 0, f"install failed: {r.stderr}\n{r.stdout}"
    block = _read_rdx_block(empty_project)
    assert block.get("enforcement_level") == "MODE_1", (
        f"default enforcement_level must be MODE_1; got {block.get('enforcement_level')!r}"
    )


def test_install_rejects_unknown_mode(empty_project: Path):
    """An unknown mode token must fail loudly, never silently accept."""
    r = _install(empty_project, "--enforcement-level", "MODE_99")
    assert r.returncode != 0, "install must reject MODE_99"
    assert "MODE_99" in (r.stderr + r.stdout)


def test_install_is_idempotent_for_enforcement_level(empty_project: Path):
    """Re-running install with the same --enforcement-level must not change
    the config (anti-zombie + idempotent)."""
    r1 = _install(empty_project, "--enforcement-level", "MODE_2")
    assert r1.returncode == 0
    cfg_a = (empty_project / "_bmad" / "config.yaml").read_text(encoding="utf-8")
    r2 = _install(empty_project, "--enforcement-level", "MODE_2")
    assert r2.returncode == 0
    cfg_b = (empty_project / "_bmad" / "config.yaml").read_text(encoding="utf-8")
    assert cfg_a == cfg_b, "idempotent install must produce identical config.yaml"


def test_install_preserves_user_explicit_level_on_rerun_without_flag(empty_project: Path):
    """Once the user picked a mode (MODE_2), re-running install WITHOUT the
    flag must NOT silently downgrade them back to MODE_1.

    This protects against accidental reconfiguration during routine updates.
    """
    r1 = _install(empty_project, "--enforcement-level", "MODE_2")
    assert r1.returncode == 0
    r2 = _install(empty_project)
    assert r2.returncode == 0
    block = _read_rdx_block(empty_project)
    assert block.get("enforcement_level") == "MODE_2", (
        "re-running install without flag must preserve existing enforcement_level, "
        f"not reset to default; got {block.get('enforcement_level')!r}"
    )
