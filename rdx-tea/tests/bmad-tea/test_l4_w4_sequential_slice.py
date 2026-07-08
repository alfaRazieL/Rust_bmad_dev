"""L4 W4 — self-contained sequential prepare->child->finalize slice.

G-W4-LIFECYCLE requires a deterministic end-to-end slice
(prepare-run -> child -> finalize-run) that writes a run-report. The
existing D3.x slices depend on an upstream TEA clone and SKIP when it is
absent. This slice is self-contained (shipped install-tree + a real git
repo only), so the lifecycle gate has at least one always-executing proof.

The child is the env-gated deterministic fake-artefact path
(RDX_TEA_ALLOW_TEST_ARTEFACT=1) — NO live model, NO subagent/Task
dispatch. Named with `sequential` so `pytest -k sequential`
(G-W4-SEQUENTIAL) also picks it up.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import jsonschema
import pytest

RDX_TEA_DIR = Path(__file__).resolve().parent.parent.parent
INSTALL_TREE = RDX_TEA_DIR / "poc" / "install-tree"
VENV_PY = Path(sys.executable)
WRAPPER_REL = Path("_bmad") / "rdx-tea" / "scripts" / "rdx_tea_wrapper.py"
# Canonical schema is authoritative (architecture/ is a byte-identical mirror).
CANON_SCHEMA = (INSTALL_TREE / "_bmad" / "rdx-tea" / "canonical"
                / "rdx-tea-run.v1.schema.json")

ASYNC_DIFF = """diff --git a/src/lib.rs b/src/lib.rs
--- a/src/lib.rs
+++ b/src/lib.rs
@@ -0,0 +1,4 @@
+pub async fn f() {
+    let h = tokio::spawn(async {});
+    h.await.unwrap();
+}
"""


def _run(cmd: list[str], cwd: Path, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True,
                          env=env, check=False)


def _env() -> dict:
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
        "output_folder: '{project-root}/_bmad-output'\n",
        encoding="utf-8",
    )
    (proj / "Cargo.toml").write_text("[package]\nname='p'\nversion='0'\n",
                                     encoding="utf-8")
    (proj / "_bmad-run" / "story.md").write_text("# Rust async story\n", encoding="utf-8")
    (proj / "_bmad-run" / "diff.patch").write_text(ASYNC_DIFF, encoding="utf-8")
    for c in (
        ["git", "init", "-q"], ["git", "add", "-A"],
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "init"],
    ):
        r = _run(c, cwd=proj)
        assert r.returncode == 0, r.stderr
    return proj


def _head(project: Path) -> str:
    return _run(["git", "-C", str(project), "rev-parse", "HEAD"], cwd=project).stdout.strip()


def _prepare(project: Path, run_id: str) -> subprocess.CompletedProcess:
    head = _head(project)
    return _run([str(VENV_PY), str(project / WRAPPER_REL), "prepare-run",
                 "--workflow", "test-design", "--project-root", str(project),
                 "--run-id", run_id,
                 "--skill-dir", str(project / ".claude" / "skills" / "bmad-testarch-test-design"),
                 "--base-sha", head, "--head-sha", head,
                 "--allow-fixture-diff", str(project / "_bmad-run" / "diff.patch")],
                cwd=project, env=_env())


def _finalize(project: Path, run_id: str) -> subprocess.CompletedProcess:
    return _run([str(VENV_PY), str(project / WRAPPER_REL), "finalize-run",
                 "--workflow", "test-design", "--project-root", str(project),
                 "--run-id", run_id, "--test-write-fake-artefact"],
                cwd=project, env=_env())


def test_l4_w4_sequential_slice_end_to_end(project: Path) -> None:
    r1 = _prepare(project, "w4-slice-01")
    assert r1.returncode == 0, r1.stderr
    r2 = _finalize(project, "w4-slice-01")
    assert r2.returncode == 0, r2.stderr
    report = json.loads(r2.stdout)
    # Lifecycle contract.
    assert report["workflow"] == "test-design"
    assert report["execution_mode"] == "sequential"
    assert report["requested_mode"] == "sequential"
    assert report["run_id"] == "w4-slice-01"
    assert report["sidecars"], "no sidecar bound"
    assert all(v["verdict"] == "PASS" for v in report["verifier"])
    # Honest wall-clock audit stamp present in the (non-hashed) run-report.
    assert report.get("created_at"), "run-report missing created_at audit stamp"
    # A run-report file was persisted under the run dir.
    report_file = (project / "_bmad" / "rdx-tea" / "runtime" / "test-design"
                   / "w4-slice-01" / "run-report.json")
    assert report_file.exists()


def test_l4_w4_sequential_slice_sidecar_schema_valid(project: Path) -> None:
    r1 = _prepare(project, "w4-slice-02")
    assert r1.returncode == 0, r1.stderr
    r2 = _finalize(project, "w4-slice-02")
    assert r2.returncode == 0, r2.stderr
    schema = json.loads(CANON_SCHEMA.read_text())
    for sc in json.loads(r2.stdout)["sidecars"]:
        jsonschema.validate(instance=sc, schema=schema)
        assert sc["execution_mode"] == "sequential"


def test_l4_w4_sequential_mode_fail_closed_in_slice(project: Path) -> None:
    """The slice refuses to run when the resolved mode is not sequential."""
    (project / "_bmad" / "tea" / "config.yaml").write_text(
        "tea_execution_mode: agent-team\n"
        "test_artifacts: '{project-root}/_bmad-output/test-artifacts'\n"
        "output_folder: '{project-root}/_bmad-output'\n",
        encoding="utf-8",
    )
    r = _prepare(project, "w4-slice-03")
    assert r.returncode != 0
    assert "sequential" in (r.stderr + r.stdout).lower()
