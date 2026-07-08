"""L3 W6 — fail-closed admission end-to-end (G-W6-FAILCLOSED, G-W6-ADMISSION).

Drives the SHIPPED wrapper + the SHIPPED admission CLI through a self-contained
run (install-tree + a real git repo; the child is the env-gated deterministic
fake-artefact path — NO live model, NO subagent/Task dispatch). Proves that a
failed or partial run is NEVER FINALIZED-admissible and that admission is
recomputed from primitives (a dishonest self-admit flag is ignored).

Named `failclosed` so `pytest -k failclosed` (G-W6-FAILCLOSED) selects them.
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
INSTALL_TREE = RDX_TEA_DIR / "poc" / "install-tree"
VENV_PY = Path(sys.executable)
WORKFLOW = "test-design"
WRAPPER_REL = Path("_bmad") / "rdx-tea" / "scripts" / "rdx_tea_wrapper.py"
ADMISSION_REL = Path("_bmad") / "rdx-tea" / "scripts" / "admission.py"

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
    env.pop("RDX_TEA_FAKE_NOW", None)
    env["RDX_TEA_ALLOW_FIXTURE_DIFF"] = "1"
    env["RDX_TEA_ALLOW_TEST_ARTEFACT"] = "1"
    return env


@pytest.fixture
def project(tmp_path: Path) -> Path:
    proj = tmp_path / "proj"
    proj.mkdir()
    shutil.copytree(INSTALL_TREE / "_bmad", proj / "_bmad")
    (proj / "_bmad-run").mkdir()
    (proj / "_bmad-output" / "test-artifacts").mkdir(parents=True)
    (proj / ".claude" / "skills" / "bmad-testarch-test-design").mkdir(parents=True)
    (proj / "_bmad" / "tea").mkdir(exist_ok=True)
    (proj / "_bmad" / "tea" / "config.yaml").write_text(
        "tea_execution_mode: sequential\n"
        "test_artifacts: '{project-root}/_bmad-output/test-artifacts'\n"
        "output_folder: '{project-root}/_bmad-output'\n", encoding="utf-8")
    (proj / "Cargo.toml").write_text("[package]\nname='p'\nversion='0'\n",
                                     encoding="utf-8")
    (proj / "_bmad-run" / "story.md").write_text("# Rust async story\n",
                                                 encoding="utf-8")
    (proj / "_bmad-run" / "diff.patch").write_text(ASYNC_DIFF, encoding="utf-8")
    for c in (
        ["git", "init", "-q"], ["git", "add", "-A"],
        ["git", "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "-q", "-m", "init"],
    ):
        assert _run(c, cwd=proj).returncode == 0
    return proj


def _head(project: Path) -> str:
    return _run(["git", "-C", str(project), "rev-parse", "HEAD"],
                cwd=project).stdout.strip()


def _prepare(project: Path, run_id: str):
    head = _head(project)
    return _run([VENV_PY, project / WRAPPER_REL, "prepare-run",
                 "--workflow", WORKFLOW, "--project-root", project,
                 "--run-id", run_id,
                 "--skill-dir", project / ".claude" / "skills" / "bmad-testarch-test-design",
                 "--base-sha", head, "--head-sha", head,
                 "--allow-fixture-diff", project / "_bmad-run" / "diff.patch"],
                cwd=project, env=_env())


def _finalize(project: Path, run_id: str, *, fake: bool = True):
    cmd = [VENV_PY, project / WRAPPER_REL, "finalize-run",
           "--workflow", WORKFLOW, "--project-root", project, "--run-id", run_id]
    if fake:
        cmd.append("--test-write-fake-artefact")
    return _run(cmd, cwd=project, env=_env())


def _admit(project: Path, run_id: str, *, with_state: bool = False):
    run_dir = project / "_bmad" / "rdx-tea" / "runtime" / WORKFLOW / run_id
    cmd = [VENV_PY, project / ADMISSION_REL, "admit",
           "--report", run_dir / "run-report.json"]
    if with_state:
        cmd += ["--state", run_dir / "run-state.json"]
    return _run(cmd, cwd=project, env=_env())


def _run_dir(project: Path, run_id: str) -> Path:
    return project / "_bmad" / "rdx-tea" / "runtime" / WORKFLOW / run_id


def _report(project: Path, run_id: str) -> dict | None:
    p = _run_dir(project, run_id) / "run-report.json"
    return json.loads(p.read_text()) if p.exists() else None


def _lock(project: Path) -> Path:
    return project / "_bmad" / "rdx-tea" / "runtime" / "active-run.lock"


def _overlay(project: Path) -> Path:
    return project / "_bmad" / "custom" / f"bmad-testarch-{WORKFLOW}.toml"


# ------------------------------------------------------------- honest pass

def test_w6_failclosed_honest_run_is_admissible(project: Path) -> None:
    assert _prepare(project, "fc-honest").returncode == 0
    r = _finalize(project, "fc-honest")
    assert r.returncode == 0, r.stderr
    rep = _report(project, "fc-honest")
    assert rep["admission"]["admissible"] is True
    assert rep["admission"]["run_outcome"] == "SUCCESS"
    # The shipped admission CLI recomputes and admits (exit 0).
    a = _admit(project, "fc-honest", with_state=True)
    assert a.returncode == 0, a.stdout + a.stderr
    assert json.loads(a.stdout)["admissible"] is True


# ------------------------------- verifier failure (finalize exits 0, gate closes)

def test_w6_failclosed_verifier_failure_never_admissible(project: Path) -> None:
    """A run whose verifier contains a failing check is never
    FINALIZED-admissible, even though finalize itself completes."""
    assert _prepare(project, "fc-verif").returncode == 0
    # Tamper the diff.patch AFTER prepare — the binder does not read it, so the
    # run finalizes, but the verifier's diff_digest_recomputed check FAILS.
    diff_path = _run_dir(project, "fc-verif") / "diff.patch"
    diff_path.write_text(diff_path.read_text() + "\n<tamper>\n")
    r = _finalize(project, "fc-verif")
    assert r.returncode == 0, r.stderr  # lifecycle completes...
    rep = _report(project, "fc-verif")
    assert any(v["verdict"] == "FAIL" for v in rep["verifier"])
    assert rep["admission"]["admissible"] is False           # ...but not admissible
    assert rep["admission"]["run_outcome"] == "VERIFIER_FAILURE"
    assert _admit(project, "fc-verif").returncode == 2


# --------------------------------------------- Task/subagent observed run

def test_w6_failclosed_subagent_observed_never_admissible(project: Path) -> None:
    assert _prepare(project, "fc-sub").returncode == 0
    (_run_dir(project, "fc-sub") / "transcript.stream.jsonl").write_text(
        '{"event":"subagent_dispatch","name":"worker-a"}\n', encoding="utf-8")
    r = _finalize(project, "fc-sub")
    assert r.returncode == 0, r.stderr
    rep = _report(project, "fc-sub")
    assert rep["observed_mode"] == "OBSERVED_SUBAGENT"
    assert rep["admission"]["admissible"] is False
    assert rep["admission"]["run_outcome"] == "WORKFLOW_FAILURE"
    assert _admit(project, "fc-sub").returncode == 2


# ----------------------------------- consistency failure (fail-closed + cleanup)

def test_w6_failclosed_consistency_failure_never_admissible(project: Path) -> None:
    assert _prepare(project, "fc-phantom").returncode == 0
    # A real artefact with a phantom generated-file claim.
    art = project / "_bmad-output" / "test-artifacts" / "plan.md"
    art.write_text("---\ngeneratedFiles:\n  - src/phantom_never_written.rs\n---\n# body\n",
                   encoding="utf-8")
    r = _finalize(project, "fc-phantom", fake=False)
    assert r.returncode != 0, r.stdout           # fail-closed exit
    rep = _report(project, "fc-phantom")          # report preserved honestly
    assert rep is not None
    assert rep["consistency_status"] == "FAIL"
    assert rep["admission"]["admissible"] is False
    assert rep["admission"]["run_outcome"] == "CONSISTENCY_FAILURE"
    # Cleanup still happened on the failure path (W4/W5 invariant preserved).
    assert not _lock(project).exists(), "active-run lock not released"
    assert not _overlay(project).exists(), "overlay not restored"
    # The preserved failed report is inadmissible via the CLI too.
    assert _admit(project, "fc-phantom", with_state=True).returncode == 2


# ------------------------------------------- partial (prepared, not finalized)

def test_w6_failclosed_partial_prepared_run_never_admissible(project: Path) -> None:
    assert _prepare(project, "fc-partial").returncode == 0
    # No finalize → no run-report → nothing to admit.
    assert not (_run_dir(project, "fc-partial") / "run-report.json").exists()
    a = _admit(project, "fc-partial")
    assert a.returncode == 2
    assert json.loads(a.stdout)["run_outcome"] == "RUNTIME_FAILURE"


# ---------------------------------- dishonest self-admit is recomputed away

def test_w6_failclosed_dishonest_selfadmit_is_recomputed(project: Path) -> None:
    """Tampering the recorded admission flag to true does not admit a run
    whose primitives fail — admission is recomputed, never trusted."""
    assert _prepare(project, "fc-liar").returncode == 0
    assert _finalize(project, "fc-liar").returncode == 0
    report_path = _run_dir(project, "fc-liar") / "run-report.json"
    rep = json.loads(report_path.read_text())
    # Forge a self-admitting bundle while corrupting a real primitive.
    rep["admissible"] = True
    rep["admission"] = {"admissible": True, "run_outcome": "SUCCESS", "reasons": []}
    rep["verifier"][0]["verdict"] = "FAIL"
    rep["verifier"][0]["failed_checks"] = ["bundle_hash"]
    report_path.write_text(json.dumps(rep, sort_keys=True))
    a = _admit(project, "fc-liar")
    assert a.returncode == 2, a.stdout
    out = json.loads(a.stdout)
    assert out["admissible"] is False
    assert out["run_outcome"] == "VERIFIER_FAILURE"
