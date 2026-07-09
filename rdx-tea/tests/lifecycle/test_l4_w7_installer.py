"""L4 lifecycle tests — Wave 7 project installer.

Gates exercised (ACCEPTANCE_GATES.md §Wave 7 + cross-cutting):
  * G-W7-INSTALL     — fresh install / update / uninstall on a temp dir.
  * G-W7-NOAUTH      — no auth material written or read; no config-dir override.
  * G-W7-IDEMPOTENT  — second install is a no-op; ``*.user.toml`` preserved.
  * G-AUTH           — auth-env grep over installer + installed surface is zero.
  * G-SPLIT-IMPORT   — installed surface imports no eval/harness, references no
                        eval/evidence path.

Test selectors map to the gate commands:
  ``-k install`` / ``-k noauth`` / ``-k idempot``.

No live model calls. Deterministic only.
"""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

RDX_TEA_DIR = Path(__file__).resolve().parent.parent.parent
INSTALLER_PY = RDX_TEA_DIR / "installer" / "project_installer.py"
INSTALLER_DIR = RDX_TEA_DIR / "installer"


def _load_installer():
    spec = importlib.util.spec_from_file_location("rdx_tea_project_installer", INSTALLER_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


pi = _load_installer()


# Files that MUST exist in an installed project (prompt §"installed-surface checks").
REQUIRED_INSTALLED = (
    "_bmad/rdx-tea/scripts/admission.py",
    "_bmad/rdx-tea/scripts/workspace_delta.py",
    "_bmad/rdx-tea/scripts/binder.py",
    "_bmad/rdx-tea/scripts/prepare.py",
    "_bmad/rdx-tea/scripts/rdx_tea_wrapper.py",
    "_bmad/rdx-tea/scripts/rdx_tea_validator.py",
    "_bmad/rdx-tea/scripts/router.py",
    "_bmad/rdx-tea/scripts/diff.py",
    "_bmad/rdx-tea/scripts/obligation_matrix.py",
    "_bmad/rdx-tea/scripts/rdx_parser.py",
    "_bmad/rdx-tea/bootstrap/sources.lock",
    "_bmad/rdx-tea/VERSION",
    "_bmad/rdx-tea/canonical/router-rules.json",
    "_bmad/rdx-tea/canonical/authority-matrix.json",
    ".claude/skills/rdx-tea-test-design/SKILL.md",
    ".claude/skills/rdx-tea-atdd/SKILL.md",
    ".claude/settings.json",
)

# Directory prefixes that must NEVER appear in an installed project.
FORBIDDEN_INSTALLED_DIRS = (
    "live-harness",
    "evals",
    "evidence",
    "research",
    "tests",
    "implementation",
    "implementation-plan",
)

# Auth material the installer/installed surface must never write or read.
AUTH_TOKENS = (
    "ANTHROPIC_API_KEY",
    "CLAUDE_CODE_OAUTH_TOKEN",
    "setup-token",
    "apiKeyHelper",
    ".credentials.json",
)
CONFIG_DIR_TOKEN = "CLAUDE_CONFIG_DIR"

# G-SPLIT-IMPORT grep pattern (same as the acceptance gate).
BOUNDARY_RE = re.compile(r"import live_harness|import evals|live-harness/|evals/|evidence/")


def _all_files(root: Path) -> list[Path]:
    return [p for p in root.rglob("*") if p.is_file()]


# --------------------------------------------------------------------------- #
# G-W7-INSTALL — fresh install places the full shipped surface.
# --------------------------------------------------------------------------- #
def test_w7_fresh_install_places_full_surface(tmp_path: Path) -> None:
    result = pi.install(tmp_path)
    assert result["mode"] == "install"
    for rel in REQUIRED_INSTALLED:
        assert (tmp_path / rel).is_file(), f"missing installed file: {rel}"
    # canonical/** installed (not just the two spot-checked files).
    assert (tmp_path / "_bmad/rdx-tea/canonical/kb-sections/section-4-core.md").is_file()
    # overlay dir created (overlays are generated per run).
    assert (tmp_path / "_bmad/custom").is_dir()


def test_w7_install_settings_is_isolation_only(tmp_path: Path) -> None:
    pi.install(tmp_path)
    settings = json.loads((tmp_path / ".claude/settings.json").read_text())
    assert settings == {
        "autoMemoryEnabled": False,
        "disableBundledSkills": True,
        "disableClaudeAiConnectors": True,
    }
    # No auth fields of any kind in the project settings.
    blob = json.dumps(settings)
    for tok in AUTH_TOKENS + (CONFIG_DIR_TOKEN,):
        assert tok not in blob


def test_w7_installed_surface_excludes_eval_and_repo_only_dirs(tmp_path: Path) -> None:
    pi.install(tmp_path)
    for rel in _all_files(tmp_path):
        parts = rel.relative_to(tmp_path).parts
        for forbidden in FORBIDDEN_INSTALLED_DIRS:
            assert forbidden not in parts, f"installed surface leaked {forbidden}: {rel}"


def test_w7_installed_surface_has_no_boundary_refs(tmp_path: Path) -> None:
    """G-SPLIT-IMPORT: the installed surface imports no eval/harness module
    and references no eval/evidence path."""
    pi.install(tmp_path)
    hits = []
    for p in _all_files(tmp_path):
        if p.suffix in (".py", ".json", ".md", ".lock", ".toml", ".yaml"):
            text = p.read_text(encoding="utf-8", errors="ignore")
            for line in text.splitlines():
                if BOUNDARY_RE.search(line):
                    hits.append(f"{p.relative_to(tmp_path)}: {line.strip()}")
    assert hits == [], f"boundary refs in installed surface: {hits}"


def test_w7_install_deterministic_manifest_across_projects(tmp_path: Path) -> None:
    a = tmp_path / "a"
    b = tmp_path / "b"
    pi.install(a)
    pi.install(b)
    ma = (a / "_bmad/rdx-tea/.rdx-tea-install-manifest.json").read_bytes()
    mb = (b / "_bmad/rdx-tea/.rdx-tea-install-manifest.json").read_bytes()
    assert ma == mb, "install manifest is not deterministic across projects"


def test_w7_source_inventory_contains_every_required_script() -> None:
    rels = {rel for rel, _ in pi.source_inventory()}
    for script in pi.REQUIRED_SCRIPTS:
        assert f"_bmad/rdx-tea/scripts/{script}" in rels


def test_w7_install_missing_production_script_fails_closed(tmp_path: Path, monkeypatch) -> None:
    """A deterministic file inventory catches a broken distribution: if a
    required production script is absent from source, install refuses."""
    import shutil

    fake_tree = tmp_path / "fake-install-tree"
    shutil.copytree(pi.INSTALL_TREE, fake_tree)
    (fake_tree / "_bmad/rdx-tea/scripts/admission.py").unlink()
    monkeypatch.setattr(pi, "INSTALL_TREE", fake_tree)
    monkeypatch.setattr(pi, "SRC_ADAPTER", fake_tree / "_bmad" / "rdx-tea")
    with pytest.raises(pi.MissingProductionFileError):
        pi.source_inventory()


# --------------------------------------------------------------------------- #
# G-W7-INSTALL — installed admission CLI recompute smoke.
# --------------------------------------------------------------------------- #
def test_w7_installed_admission_cli_recompute_smoke(tmp_path: Path) -> None:
    """The installed admission gate recomputes from primitives and never
    trusts a self-reported ``admissible`` flag (W6 invariant preserved)."""
    pi.install(tmp_path)
    admission = tmp_path / "_bmad/rdx-tea/scripts/admission.py"
    assert admission.is_file()
    dishonest = tmp_path / "dishonest-report.json"
    dishonest.write_text(json.dumps({"admissible": True, "admission": "SUCCESS"}))
    proc = subprocess.run(
        [sys.executable, str(admission), "admit", "--report", str(dishonest)],
        cwd=str(tmp_path), capture_output=True, text=True,
    )
    assert proc.returncode == 2, proc.stdout + proc.stderr
    out = json.loads(proc.stdout)
    assert out["admissible"] is False
    assert out["run_outcome"] != "SUCCESS"


# --------------------------------------------------------------------------- #
# G-W7-IDEMPOTENT — second install no-op; user content preserved.
# --------------------------------------------------------------------------- #
def test_w7_second_install_is_idempotent_noop(tmp_path: Path) -> None:
    pi.install(tmp_path)
    second = pi.install(tmp_path)
    assert second["changed"] == [], f"second install changed: {second['changed']}"
    assert len(second["unchanged"]) == second["file_count"]


def test_w7_update_is_idempotent_and_preserves_user_toml(tmp_path: Path) -> None:
    pi.install(tmp_path)
    user = tmp_path / "_bmad/custom/bmad-testarch-test-design.user.toml"
    user.parent.mkdir(parents=True, exist_ok=True)
    user.write_text("# personal overlay\n[workflow]\npersistent_facts = ['keep me']\n")
    before = user.read_bytes()
    result = pi.update(tmp_path)
    assert result["mode"] == "update"
    assert result["changed"] == []
    assert user.read_bytes() == before, "update clobbered a *.user.toml"


def test_w7_install_refuses_to_overwrite_user_toml(tmp_path: Path) -> None:
    """No adapter-owned inventory path is a ``*.user.toml``; the write guard
    fails closed if one ever slipped in."""
    for rel, _ in pi.source_inventory():
        assert not rel.endswith(".user.toml")
    with pytest.raises(pi.UserFileProtectedError):
        pi.write_overlay(tmp_path, "test-design.user")  # ends up *.user.toml


def test_w7_install_preserves_user_settings_keys(tmp_path: Path) -> None:
    settings = tmp_path / ".claude/settings.json"
    settings.parent.mkdir(parents=True, exist_ok=True)
    settings.write_text(json.dumps({"theme": "dark"}))
    pi.install(tmp_path)
    merged = json.loads(settings.read_text())
    assert merged["theme"] == "dark"           # user key preserved
    assert merged["disableBundledSkills"] is True
    pi.uninstall(tmp_path)
    survived = json.loads(settings.read_text())
    assert survived == {"theme": "dark"}, "uninstall did not restore user settings"


# --------------------------------------------------------------------------- #
# G-W7-INSTALL / rollback — uninstall removes adapter, keeps user content.
# --------------------------------------------------------------------------- #
def test_w7_uninstall_removes_adapter_keeps_user_content(tmp_path: Path) -> None:
    pi.install(tmp_path)
    user = tmp_path / "_bmad/custom/bmad-testarch-atdd.user.toml"
    user.parent.mkdir(parents=True, exist_ok=True)
    user.write_text("# mine\n")
    user_doc = tmp_path / "_bmad-output/my-notes.md"
    user_doc.parent.mkdir(parents=True, exist_ok=True)
    user_doc.write_text("user artifact\n")

    report = pi.uninstall(tmp_path)

    # Adapter files gone.
    assert not (tmp_path / "_bmad/rdx-tea/scripts/admission.py").exists()
    assert not (tmp_path / "_bmad/rdx-tea/VERSION").exists()
    assert not (tmp_path / ".claude/settings.json").exists()
    assert not (tmp_path / "_bmad/rdx-tea/.rdx-tea-install-manifest.json").exists()
    # User content kept.
    assert user.exists(), "uninstall removed a *.user.toml"
    assert user_doc.exists(), "uninstall removed a user artifact"
    assert any(k.endswith(".user.toml") for k in report["kept"])


# --------------------------------------------------------------------------- #
# G-W7-NOAUTH / G-AUTH — no auth material; no config-dir override.
# --------------------------------------------------------------------------- #
def test_w7_noauth_installer_source_has_no_auth_material() -> None:
    for p in _all_files(INSTALLER_DIR):
        if "__pycache__" in p.parts:
            continue
        text = p.read_text(encoding="utf-8", errors="ignore")
        for tok in AUTH_TOKENS:
            assert tok not in text, f"auth token {tok!r} in installer source {p}"
        assert CONFIG_DIR_TOKEN not in text, f"config-dir override in installer {p}"


def test_w7_noauth_installed_surface_has_no_auth_material(tmp_path: Path) -> None:
    pi.install(tmp_path)
    for p in _all_files(tmp_path):
        text = p.read_text(encoding="utf-8", errors="ignore")
        for tok in AUTH_TOKENS:
            assert tok not in text, f"auth token {tok!r} in installed file {p}"
        assert CONFIG_DIR_TOKEN not in text, f"config-dir override in installed {p}"


def test_w7_noauth_no_config_dir_env_referenced() -> None:
    """The installer never sets/overrides the CLI config-dir env variable."""
    src = INSTALLER_PY.read_text(encoding="utf-8")
    assert CONFIG_DIR_TOKEN not in src


# --------------------------------------------------------------------------- #
# Version-range refusal — fail closed.
# --------------------------------------------------------------------------- #
def _write_tea_config(project_root: Path, body: str) -> None:
    cfg = project_root / "_bmad/tea/config.yaml"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(body)


def test_w7_install_refuses_unsupported_tea_version(tmp_path: Path) -> None:
    _write_tea_config(tmp_path, "tea_execution_mode: sequential\ntea_version: \"2.5.0\"\n")
    with pytest.raises(pi.VersionRangeError):
        pi.install(tmp_path)
    # Fail closed: nothing installed.
    assert not (tmp_path / "_bmad/rdx-tea").exists()


def test_w7_install_refuses_too_old_tea_version(tmp_path: Path) -> None:
    _write_tea_config(tmp_path, "tea_version: 1.18.9\n")
    with pytest.raises(pi.VersionRangeError):
        pi.install(tmp_path)
    assert not (tmp_path / "_bmad/rdx-tea").exists()


def test_w7_install_refuses_unparseable_tea_version(tmp_path: Path) -> None:
    _write_tea_config(tmp_path, "tea_version: not-a-version\n")
    with pytest.raises(pi.VersionRangeError):
        pi.install(tmp_path)
    assert not (tmp_path / "_bmad/rdx-tea").exists()


def test_w7_install_accepts_supported_tea_version(tmp_path: Path) -> None:
    _write_tea_config(tmp_path, "tea_execution_mode: sequential\ntea_version: \"1.19.0\"\n")
    result = pi.install(tmp_path)
    assert result["tea_version"] == "1.19.0"
    assert (tmp_path / "_bmad/rdx-tea/scripts/admission.py").is_file()


def test_w7_install_accepts_when_no_tea_version_declared(tmp_path: Path) -> None:
    _write_tea_config(tmp_path, "tea_execution_mode: sequential\n")
    result = pi.install(tmp_path)
    assert result["tea_version"] is None
    assert (tmp_path / "_bmad/rdx-tea/VERSION").is_file()


def test_w7_supported_bounds_derived_from_sources_lock() -> None:
    low, high = pi.supported_tea_bounds()
    assert low == (1, 19, 0)
    assert high == (2, 0, 0)
