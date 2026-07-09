"""L5 W10 — end-to-end acceptance over a CLEAN INSTALL (release readiness).

These are the release-gate acceptance tests for Wave 10. Unlike the W4/W6
lifecycle slices (which drive a ``copytree`` of the install-tree), every
test here starts from a real ``project_installer.install()`` into a
disposable project — i.e. it exercises the *installed* surface exactly as
an operator would receive it (ACCEPTANCE_GATES.md §Wave 10).

Gates exercised:

  * G-W10-E2E       — clean install places the full shipped surface AND a
                      single bounded non-interactive lifecycle smoke on the
                      INSTALLED scripts is FINALIZED-admissible.
  * G-W10-ROLLBACK  — uninstall removes adapter-owned files and restores
                      user content (``*.user.toml``, user artifacts, user
                      settings keys).
  * G-AUTH          — no auth material / no ``CLAUDE_CONFIG_DIR`` in the
                      installed surface (re-asserted at the E2E level).
  * G-SPLIT-IMPORT  — installed surface imports no eval/harness module and
                      references no eval/evidence path (re-asserted here).

The smoke's "child" is the env-gated deterministic fake-artefact path
(``RDX_TEA_ALLOW_TEST_ARTEFACT=1``): NO live model, NO subagent/Task
dispatch. A live-model child run is a *separately* owner-authorized rung
(§6.9 rung 6) and is NOT exercised by this deterministic suite.

Test selectors map to the gate commands: ``-k rollback`` selects the
rollback gate; the whole module is the ``pytest rdx-tea/tests/acceptance``
E2E gate.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

RDX_TEA_DIR = Path(__file__).resolve().parent.parent.parent
INSTALLER_PY = RDX_TEA_DIR / "installer" / "project_installer.py"
VENV_PY = Path(sys.executable)
WORKFLOW = "test-design"
WRAPPER_REL = Path("_bmad") / "rdx-tea" / "scripts" / "rdx_tea_wrapper.py"
ADMISSION_REL = Path("_bmad") / "rdx-tea" / "scripts" / "admission.py"


def _load_installer():
    spec = importlib.util.spec_from_file_location(
        "rdx_tea_project_installer_w10", INSTALLER_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


pi = _load_installer()


# The ten production scripts + the anchor surface that MUST be installed.
REQUIRED_INSTALLED = tuple(
    f"_bmad/rdx-tea/scripts/{s}" for s in pi.REQUIRED_SCRIPTS
) + (
    "_bmad/rdx-tea/bootstrap/sources.lock",
    "_bmad/rdx-tea/VERSION",
    "_bmad/rdx-tea/canonical/router-rules.json",
    "_bmad/rdx-tea/canonical/authority-matrix.json",
    "_bmad/rdx-tea/canonical/rdx-tea-run.v1.schema.json",
    ".claude/skills/rdx-tea-test-design/SKILL.md",
    ".claude/skills/rdx-tea-atdd/SKILL.md",
    ".claude/settings.json",
)

# Directory prefixes that must NEVER ship into an installed project.
FORBIDDEN_INSTALLED_DIRS = (
    "live-harness", "evals", "evidence", "research",
    "tests", "implementation", "implementation-plan",
)

AUTH_TOKENS = (
    "ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN", "setup-token",
    "apiKeyHelper", ".credentials.json",
)
CONFIG_DIR_TOKEN = "CLAUDE_CONFIG_DIR"
BOUNDARY_RE = re.compile(
    r"import live_harness|import evals|live-harness/|evals/|evidence/")

ASYNC_DIFF = """diff --git a/src/lib.rs b/src/lib.rs
--- a/src/lib.rs
+++ b/src/lib.rs
@@ -0,0 +1,4 @@
+pub async fn f() {
+    let h = tokio::spawn(async {});
+    h.await.unwrap();
+}
"""


def _all_files(root: Path) -> list[Path]:
    return [p for p in root.rglob("*") if p.is_file()]


def _run(cmd, cwd, env=None) -> subprocess.CompletedProcess:
    return subprocess.run([str(c) for c in cmd], cwd=str(cwd),
                          capture_output=True, text=True, env=env, check=False)


def _lifecycle_env() -> dict:
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env.pop("RDX_TEA_FAKE_NOW", None)
    env["RDX_TEA_ALLOW_FIXTURE_DIFF"] = "1"
    env["RDX_TEA_ALLOW_TEST_ARTEFACT"] = "1"
    return env


def _prepare_project_for_lifecycle(project: Path) -> None:
    """Add the user-owned files a real run needs (config, story, diff,
    child-skill placeholder, git repo). These are NOT adapter-owned and are
    never written by the installer."""
    (project / "_bmad-run").mkdir(parents=True, exist_ok=True)
    (project / "_bmad-output" / "test-artifacts").mkdir(parents=True, exist_ok=True)
    (project / ".claude" / "skills" / "bmad-testarch-test-design").mkdir(
        parents=True, exist_ok=True)
    (project / "_bmad" / "tea").mkdir(parents=True, exist_ok=True)
    (project / "_bmad" / "tea" / "config.yaml").write_text(
        "tea_execution_mode: sequential\n"
        "test_artifacts: '{project-root}/_bmad-output/test-artifacts'\n"
        "output_folder: '{project-root}/_bmad-output'\n"
        "project_name: w10\n",
        encoding="utf-8",
    )
    (project / "Cargo.toml").write_text("[package]\nname='p'\nversion='0'\n",
                                        encoding="utf-8")
    (project / "_bmad-run" / "story.md").write_text("# Rust async story\n",
                                                    encoding="utf-8")
    (project / "_bmad-run" / "diff.patch").write_text(ASYNC_DIFF, encoding="utf-8")
    for c in (
        ["git", "init", "-q"], ["git", "add", "-A"],
        ["git", "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "-q", "-m", "init"],
    ):
        assert _run(c, cwd=project).returncode == 0


def _head(project: Path) -> str:
    return _run(["git", "-C", str(project), "rev-parse", "HEAD"],
                cwd=project).stdout.strip()


def _prepare(project: Path, run_id: str):
    head = _head(project)
    return _run(
        [VENV_PY, project / WRAPPER_REL, "prepare-run",
         "--workflow", WORKFLOW, "--project-root", project, "--run-id", run_id,
         "--skill-dir", project / ".claude" / "skills" / "bmad-testarch-test-design",
         "--base-sha", head, "--head-sha", head,
         "--allow-fixture-diff", project / "_bmad-run" / "diff.patch"],
        cwd=project, env=_lifecycle_env())


def _finalize(project: Path, run_id: str):
    return _run(
        [VENV_PY, project / WRAPPER_REL, "finalize-run",
         "--workflow", WORKFLOW, "--project-root", project, "--run-id", run_id,
         "--test-write-fake-artefact"],
        cwd=project, env=_lifecycle_env())


def _run_dir(project: Path, run_id: str) -> Path:
    return project / "_bmad" / "rdx-tea" / "runtime" / WORKFLOW / run_id


def _admit(project: Path, run_id: str):
    run_dir = _run_dir(project, run_id)
    return _run(
        [VENV_PY, project / ADMISSION_REL, "admit",
         "--report", run_dir / "run-report.json",
         "--state", run_dir / "run-state.json"],
        cwd=project, env=_lifecycle_env())


# --------------------------------------------------------------------------- #
# G-W10-E2E — clean install places the full shipped surface.
# --------------------------------------------------------------------------- #
def test_w10_clean_install_places_full_surface(tmp_path: Path) -> None:
    project = tmp_path / "disposable"
    result = pi.install(project)
    assert result["mode"] == "install"
    for rel in REQUIRED_INSTALLED:
        assert (project / rel).is_file(), f"clean install missing: {rel}"
    # All ten production scripts individually.
    for script in pi.REQUIRED_SCRIPTS:
        assert (project / "_bmad/rdx-tea/scripts" / script).is_file()
    # Overlay dir present for per-run overlays.
    assert (project / "_bmad/custom").is_dir()
    # Install manifest written (enables clean uninstall).
    assert (project / "_bmad/rdx-tea/.rdx-tea-install-manifest.json").is_file()


def test_w10_clean_install_settings_is_isolation_only_no_auth(tmp_path: Path) -> None:
    project = tmp_path / "disposable"
    pi.install(project)
    settings = json.loads((project / ".claude/settings.json").read_text())
    assert settings == {
        "autoMemoryEnabled": False,
        "disableBundledSkills": True,
        "disableClaudeAiConnectors": True,
    }
    blob = json.dumps(settings)
    for tok in AUTH_TOKENS + (CONFIG_DIR_TOKEN,):
        assert tok not in blob, f"auth/config token leaked into settings: {tok}"


def test_w10_clean_install_excludes_eval_research_and_test_dirs(tmp_path: Path) -> None:
    project = tmp_path / "disposable"
    pi.install(project)
    for p in _all_files(project):
        parts = p.relative_to(project).parts
        for forbidden in FORBIDDEN_INSTALLED_DIRS:
            assert forbidden not in parts, \
                f"installed surface leaked '{forbidden}': {p.relative_to(project)}"


def test_w10_clean_install_has_no_auth_material_anywhere(tmp_path: Path) -> None:
    project = tmp_path / "disposable"
    pi.install(project)
    for p in _all_files(project):
        text = p.read_text(encoding="utf-8", errors="ignore")
        for tok in AUTH_TOKENS:
            assert tok not in text, f"auth token {tok!r} in installed file {p}"
        assert CONFIG_DIR_TOKEN not in text, f"config-dir token in installed file {p}"


def test_w10_clean_install_has_no_boundary_refs(tmp_path: Path) -> None:
    """G-SPLIT-IMPORT re-asserted over the installed surface."""
    project = tmp_path / "disposable"
    pi.install(project)
    hits = []
    for p in _all_files(project):
        if p.suffix in (".py", ".json", ".md", ".lock", ".toml", ".yaml"):
            for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
                if BOUNDARY_RE.search(line):
                    hits.append(f"{p.relative_to(project)}: {line.strip()}")
    assert hits == [], f"boundary refs in installed surface: {hits}"


# --------------------------------------------------------------------------- #
# G-W10-E2E — bounded non-interactive lifecycle smoke on the INSTALLED scripts.
# --------------------------------------------------------------------------- #
def test_w10_e2e_installed_lifecycle_smoke_is_admissible(tmp_path: Path) -> None:
    """The single bounded non-interactive smoke: a clean install, then
    prepare -> (env-gated fake child) -> finalize on the INSTALLED wrapper,
    yields a FINALIZED-admissible run-report; the INSTALLED admission CLI
    recomputes admissibility from primitives (exit 0)."""
    project = tmp_path / "disposable"
    pi.install(project)
    _prepare_project_for_lifecycle(project)

    r1 = _prepare(project, "w10-smoke-01")
    assert r1.returncode == 0, r1.stderr
    r2 = _finalize(project, "w10-smoke-01")
    assert r2.returncode == 0, r2.stderr

    report = json.loads(r2.stdout)
    assert report["workflow"] == WORKFLOW
    assert report["execution_mode"] == "sequential"
    assert report["requested_mode"] == "sequential"
    assert report["run_id"] == "w10-smoke-01"
    assert report["sidecars"], "no sidecar bound in the smoke"
    assert all(v["verdict"] == "PASS" for v in report["verifier"])
    assert report["admission"]["admissible"] is True
    assert report["admission"]["run_outcome"] == "SUCCESS"
    # No Task/subagent dispatch was observed.
    assert report["observed_mode"] != "OBSERVED_SUBAGENT"

    # The INSTALLED admission CLI recomputes and admits (exit 0).
    a = _admit(project, "w10-smoke-01")
    assert a.returncode == 0, a.stdout + a.stderr
    admit_out = json.loads(a.stdout)
    assert admit_out["admissible"] is True
    assert admit_out["run_outcome"] == "SUCCESS"

    # A run-report file was persisted honestly under the run dir.
    assert (_run_dir(project, "w10-smoke-01") / "run-report.json").exists()


def test_w10_e2e_dishonest_selfadmit_is_recomputed_away(tmp_path: Path) -> None:
    """A run-report that self-declares ``admissible: true`` over failing
    primitives is NOT admitted by the installed admission CLI (recompute,
    never trust the recorded flag) — the fail-closed invariant survives
    into the installed surface."""
    project = tmp_path / "disposable"
    pi.install(project)
    dishonest = project / "dishonest-report.json"
    dishonest.write_text(json.dumps(
        {"admissible": True, "admission": {"admissible": True,
         "run_outcome": "SUCCESS"}}))
    proc = _run(
        [VENV_PY, project / ADMISSION_REL, "admit", "--report", dishonest],
        cwd=project, env=_lifecycle_env())
    assert proc.returncode == 2, proc.stdout + proc.stderr
    out = json.loads(proc.stdout)
    assert out["admissible"] is False
    assert out["run_outcome"] != "SUCCESS"


# --------------------------------------------------------------------------- #
# G-W10-ROLLBACK — uninstall removes adapter files, restores user content.
# --------------------------------------------------------------------------- #
def test_w10_rollback_uninstall_removes_adapter_keeps_user_content(tmp_path: Path) -> None:
    project = tmp_path / "disposable"
    pi.install(project)

    # User-owned content of three kinds.
    user_toml = project / "_bmad/custom/bmad-testarch-atdd.user.toml"
    user_toml.parent.mkdir(parents=True, exist_ok=True)
    user_toml.write_text("# personal overlay — keep me\n[workflow]\n")
    user_doc = project / "_bmad-output/my-notes.md"
    user_doc.parent.mkdir(parents=True, exist_ok=True)
    user_doc.write_text("user artifact\n")

    report = pi.uninstall(project)

    # Adapter-owned files gone.
    assert not (project / "_bmad/rdx-tea/scripts/admission.py").exists()
    assert not (project / "_bmad/rdx-tea/VERSION").exists()
    assert not (project / "_bmad/rdx-tea/.rdx-tea-install-manifest.json").exists()
    assert not (project / ".claude/settings.json").exists()
    # User content preserved.
    assert user_toml.exists(), "rollback removed a *.user.toml"
    assert user_doc.exists(), "rollback removed a user artifact"
    assert any(k.endswith(".user.toml") for k in report["kept"])


def test_w10_rollback_restores_user_toml_verbatim(tmp_path: Path) -> None:
    """The *.user.toml survives an install -> uninstall cycle byte-for-byte."""
    project = tmp_path / "disposable"
    pi.install(project)
    user_toml = project / "_bmad/custom/bmad-testarch-test-design.user.toml"
    user_toml.parent.mkdir(parents=True, exist_ok=True)
    original = ("# personal overlay\n[workflow]\n"
                "persistent_facts = ['file:my/own/context.md']\n")
    user_toml.write_text(original, encoding="utf-8")
    pi.uninstall(project)
    assert user_toml.exists(), "rollback deleted the user overlay"
    assert user_toml.read_text(encoding="utf-8") == original, \
        "rollback mutated the user overlay"


def test_w10_rollback_restores_user_settings_keys(tmp_path: Path) -> None:
    """Uninstall reverses the isolation merge and preserves user settings."""
    project = tmp_path / "disposable"
    settings = project / ".claude/settings.json"
    settings.parent.mkdir(parents=True, exist_ok=True)
    settings.write_text(json.dumps({"theme": "dark"}))
    pi.install(project)
    merged = json.loads(settings.read_text())
    assert merged["theme"] == "dark"
    assert merged["disableBundledSkills"] is True
    pi.uninstall(project)
    survived = json.loads(settings.read_text())
    assert survived == {"theme": "dark"}, "rollback did not restore user settings"


def test_w10_rollback_removes_every_manifest_adapter_file(tmp_path: Path) -> None:
    """Every non-user file recorded in the install manifest is removed on
    uninstall; nothing adapter-owned is left behind."""
    project = tmp_path / "disposable"
    pi.install(project)
    manifest = json.loads(
        (project / "_bmad/rdx-tea/.rdx-tea-install-manifest.json").read_text())
    adapter_files = [e["path"] for e in manifest["files"]
                     if not e["path"].endswith(".user.toml")]
    assert adapter_files, "manifest recorded no adapter files"
    pi.uninstall(project)
    leftover = [rel for rel in adapter_files if (project / rel).exists()]
    assert leftover == [], f"rollback left adapter files behind: {leftover}"


def test_w10_rollback_after_lifecycle_run_keeps_run_evidence(tmp_path: Path) -> None:
    """Uninstall removes adapter-owned *installed* files but never touches
    the user's run evidence written under the runtime dir during a run.

    ``_bmad/rdx-tea/runtime/**`` is run output (user content), not part of
    the install manifest, so rollback must leave it intact for the operator
    to inspect after the adapter is removed."""
    project = tmp_path / "disposable"
    pi.install(project)
    _prepare_project_for_lifecycle(project)
    assert _prepare(project, "w10-keep-01").returncode == 0
    assert _finalize(project, "w10-keep-01").returncode == 0
    run_report = _run_dir(project, "w10-keep-01") / "run-report.json"
    assert run_report.exists()

    pi.uninstall(project)

    # Adapter script gone, but the run evidence the operator produced stays.
    assert not (project / "_bmad/rdx-tea/scripts/admission.py").exists()
    assert run_report.exists(), "rollback destroyed user run evidence"
