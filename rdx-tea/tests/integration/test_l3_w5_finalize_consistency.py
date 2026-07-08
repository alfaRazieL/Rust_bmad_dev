"""L3 W5 — finalize-run judges artifact consistency against reality.

End-to-end through the real wrapper CLI (prepare-run → the test writes a
REAL artefact with declared-file frontmatter → finalize-run). Proves:

  * a phantom file claim (declared-generated file that exists neither on
    disk nor in the delta) fails the run CLOSED — non-zero exit — while the
    run-report is still preserved honestly with consistency_status=FAIL,
    the overlay is restored, and the active-run lock is released (W4
    invariants hold on the failure path);
  * an honest artefact whose declared files all exist finalizes PASS and
    carries `workspace_delta` + `artifact_consistency` in the report;
  * duplicate frontmatter is a WARNING, not a failure.

Gates: G-W5-DELTA, G-W5-CONSISTENCY (fail-closed), plus the W4
lock/overlay lifecycle invariant on the failure path.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

RDX_TEA_DIR = Path(__file__).resolve().parent.parent.parent
REPO_ROOT = RDX_TEA_DIR.parent
UPSTREAM_ROOT = Path(os.environ.get("RDX_TEA_UPSTREAM_ROOT",
                                    str(REPO_ROOT.parent / "upstream")))
UPSTREAM_TEA = UPSTREAM_ROOT / "bmad-method-test-architecture-enterprise"
INSTALL_TREE = RDX_TEA_DIR / "poc" / "install-tree"
VENV_PY = Path(sys.executable)
SLUG = "bmad-testarch-test-design"
WORKFLOW = "test-design"

ASYNC_DIFF = """diff --git a/src/lib.rs b/src/lib.rs
--- a/src/lib.rs
+++ b/src/lib.rs
@@ -0,0 +1,4 @@
+pub async fn f() {
+    let h = tokio::spawn(async {});
+    h.await.unwrap();
+}
"""


def _run(cmd, cwd, env=None):
    return subprocess.run([str(c) for c in cmd], cwd=str(cwd),
                          capture_output=True, text=True, env=env, check=False)


def _env():
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env["RDX_TEA_ALLOW_FIXTURE_DIFF"] = "1"
    return env


@pytest.fixture
def project(tmp_path):
    proj = tmp_path / "proj"
    proj.mkdir()
    shutil.copytree(INSTALL_TREE / "_bmad", proj / "_bmad")
    (proj / "_bmad-run").mkdir()
    (proj / "_bmad-output" / "test-artifacts").mkdir(parents=True)
    if not (UPSTREAM_TEA / "src" / "workflows" / "testarch" / SLUG).exists():
        pytest.skip("upstream TEA missing")
    shutil.copytree(UPSTREAM_TEA / "src" / "workflows" / "testarch" / SLUG,
                    proj / ".claude" / "skills" / SLUG)
    (proj / "_bmad" / "tea").mkdir(exist_ok=True)
    (proj / "_bmad" / "tea" / "config.yaml").write_text(
        "tea_execution_mode: sequential\n"
        "test_artifacts: '{project-root}/_bmad-output/test-artifacts'\n"
        "output_folder: '{project-root}/_bmad-output'\n",
        encoding="utf-8",
    )
    (proj / "Cargo.toml").write_text("[package]\nname='p'\nversion='0'\n",
                                     encoding="utf-8")
    (proj / "_bmad-run" / "story.md").write_text("# story\n", encoding="utf-8")
    for c in (
        ["git", "init", "-q"],
        ["git", "add", "-A"],
        ["git", "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "-q", "-m", "init"],
    ):
        r = _run(c, cwd=proj)
        assert r.returncode == 0, r.stderr
    return proj


def _prepare(proj, run_id):
    (proj / "_bmad-run" / "diff.patch").write_text(ASYNC_DIFF, encoding="utf-8")
    head = _run(["git", "-C", str(proj), "rev-parse", "HEAD"],
                cwd=proj).stdout.strip()
    wrap = proj / "_bmad" / "rdx-tea" / "scripts" / "rdx_tea_wrapper.py"
    skill = proj / ".claude" / "skills" / SLUG
    return _run([VENV_PY, wrap, "prepare-run",
                 "--workflow", WORKFLOW, "--project-root", proj,
                 "--run-id", run_id, "--skill-dir", skill,
                 "--base-sha", head, "--head-sha", head,
                 "--allow-fixture-diff", proj / "_bmad-run" / "diff.patch"],
                cwd=proj, env=_env())


def _finalize(proj, run_id):
    wrap = proj / "_bmad" / "rdx-tea" / "scripts" / "rdx_tea_wrapper.py"
    return _run([VENV_PY, wrap, "finalize-run",
                 "--workflow", WORKFLOW, "--project-root", proj,
                 "--run-id", run_id],
                cwd=proj, env=_env())


def _write_artefact(proj, name, frontmatter):
    art = proj / "_bmad-output" / "test-artifacts" / name
    art.write_text(frontmatter + "\n# body\n", encoding="utf-8")
    return art


def _report(proj, run_id):
    p = (proj / "_bmad" / "rdx-tea" / "runtime" / WORKFLOW / run_id
         / "run-report.json")
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def _overlay(proj):
    return proj / "_bmad" / "custom" / f"bmad-testarch-{WORKFLOW}.toml"


def _lock(proj):
    return proj / "_bmad" / "rdx-tea" / "runtime" / "active-run.lock"


# ------------------------------------------------------------- phantom fail

def test_w5_finalize_fails_closed_on_phantom_claim(project):
    r = _prepare(project, "phantom-01")
    assert r.returncode == 0, r.stderr
    _write_artefact(project, "plan.md",
                    "---\ngeneratedFiles:\n  - src/phantom_never_written.rs\n---")
    r2 = _finalize(project, "phantom-01")
    # Fail-closed: non-zero exit.
    assert r2.returncode != 0, r2.stdout
    assert "consistency" in (r2.stderr + r2.stdout).lower()
    # Honest report preserved with consistency_status=FAIL.
    rep = _report(project, "phantom-01")
    assert rep is not None, "run-report must be preserved on failure"
    assert rep["consistency_status"] == "FAIL"
    assert "src/phantom_never_written.rs" in \
        rep["artifact_consistency"]["phantom_file_claims"]
    # W4 invariants hold on the failure path: overlay restored (removed,
    # no pre-existing) and lock released.
    assert not _overlay(project).exists(), "overlay not restored on failure"
    assert not _lock(project).exists(), "active-run lock not released on failure"


def test_w5_finalize_fails_closed_on_declared_missing(project):
    r = _prepare(project, "missing-01")
    assert r.returncode == 0, r.stderr
    # Declared file absent, not marked planned-not-generated.
    _write_artefact(project, "plan.md",
                    "---\ngeneratedFiles:\n  - src/absent.rs\n---")
    r2 = _finalize(project, "missing-01")
    assert r2.returncode != 0, r2.stdout
    rep = _report(project, "missing-01")
    assert rep["workspace_delta_consistency"]["status"] == "FAIL"
    assert not _lock(project).exists()


# ------------------------------------------------------------- honest pass

def test_w5_finalize_passes_when_declared_files_exist(project):
    r = _prepare(project, "honest-01")
    assert r.returncode == 0, r.stderr
    # Declare the artefact's own (existing) path — reconciles with reality.
    _write_artefact(
        project, "plan.md",
        "---\ngeneratedFiles:\n  - _bmad-output/test-artifacts/plan.md\n---")
    r2 = _finalize(project, "honest-01")
    assert r2.returncode == 0, r2.stderr
    rep = json.loads(r2.stdout)
    assert rep["consistency_status"] == "PASS"
    assert rep["artifact_consistency"]["status"] == "PASS"
    assert rep["workspace_delta"]["created_files"] == \
        ["_bmad-output/test-artifacts/plan.md"]
    # sidecar present exactly once for the one real artefact.
    assert len(rep["sidecars"]) == 1


def test_w5_finalize_duplicate_frontmatter_is_warning_not_failure(project):
    r = _prepare(project, "dup-01")
    assert r.returncode == 0, r.stderr
    _write_artefact(
        project, "plan.md",
        "---\nstoryId: S-1\n---\n\nprose\n\n---\nstoryId: S-1\nlastStep: 2\n---")
    r2 = _finalize(project, "dup-01")
    assert r2.returncode == 0, r2.stderr
    rep = json.loads(r2.stdout)
    assert rep["consistency_status"] == "PASS"
    assert any("storyId" in w for w in rep["artifact_consistency"]["warnings"])
