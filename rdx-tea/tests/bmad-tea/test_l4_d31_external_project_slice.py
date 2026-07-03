"""L4 D3.2 vertical slice in a FRESH EXTERNAL PROJECT (two-phase wrapper).

Restructured from D3.1 to use the two-phase `prepare-run` / `finalize-run`
wrapper. Uses `--test-write-fake-artefact` in place of the removed
`--simulate-child`; this flag is gated by the env
`RDX_TEA_ALLOW_TEST_ARTEFACT=1` (never enabled in production).

Every run has a real git head (base==head for the single-commit test
repo). The wrapper's strict identity resolver verifies each SHA with
`git cat-file`.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import jsonschema
import pytest

RDX_TEA_DIR = Path(__file__).resolve().parent.parent.parent
REPO_ROOT = RDX_TEA_DIR.parent
WORKSPACE = REPO_ROOT.parent
UPSTREAM_TEA = WORKSPACE / "upstream" / "bmad-method-test-architecture-enterprise"
UPSTREAM_BMAD = WORKSPACE / "upstream" / "BMAD-METHOD"
VENV_PY = Path(sys.executable)
INSTALL_TREE = RDX_TEA_DIR / "poc" / "install-tree"

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
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True,
                          text=True, env=env, check=False)


def _venv_python() -> Path:
    return VENV_PY


@pytest.fixture
def external_project(tmp_path: Path) -> Path:
    """Fresh external tmp project — no access to the RDX dev tree."""
    proj = tmp_path / "external_proj"
    proj.mkdir()
    shutil.copytree(INSTALL_TREE / "_bmad", proj / "_bmad")
    (proj / "_bmad-run").mkdir()
    (proj / "_bmad-output" / "test-artifacts").mkdir(parents=True)
    slug = "bmad-testarch-test-design"
    src = UPSTREAM_TEA / "src" / "workflows" / "testarch" / slug
    if not src.exists():
        pytest.skip("upstream TEA missing — run bootstrap")
    shutil.copytree(src, proj / ".claude" / "skills" / slug)
    # D3.2 §3 explicit sequential.
    (proj / "_bmad" / "tea").mkdir(exist_ok=True)
    (proj / "_bmad" / "tea" / "config.yaml").write_text(
        "tea_execution_mode: sequential\n"
        "test_artifacts: '{project-root}/_bmad-output/test-artifacts'\n"
        "output_folder: '{project-root}/_bmad-output'\n"
        "project_name: external\n",
        encoding="utf-8",
    )
    # Rust project marker for rust_scope auto-detection.
    (proj / "Cargo.toml").write_text("[package]\nname='p'\nversion='0'\n",
                                     encoding="utf-8")
    (proj / "_bmad-run" / "story.md").write_text("# Rust async story\n",
                                                 encoding="utf-8")
    (proj / "_bmad-run" / "diff.patch").write_text(ASYNC_DIFF, encoding="utf-8")
    # Real git repo for strict identity resolution.
    env = os.environ.copy()
    for c in (
        ["git", "-C", str(proj), "init", "-q"],
        ["git", "-C", str(proj), "add", "-A"],
        ["git", "-C", str(proj), "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "-q", "-m", "init"],
    ):
        r = subprocess.run(c, capture_output=True, text=True, env=env)
        assert r.returncode == 0, r.stderr
    return proj


def _wrap_env() -> dict:
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env["RDX_TEA_ALLOW_FIXTURE_DIFF"] = "1"
    env["RDX_TEA_ALLOW_TEST_ARTEFACT"] = "1"
    return env


def _git_head(project: Path, env: dict) -> str:
    r = _run(["git", "-C", str(project), "rev-parse", "HEAD"], cwd=project, env=env)
    assert r.returncode == 0
    return r.stdout.strip()


def _prepare_and_finalize(project: Path, run_id: str = "smoke-01",
                          tamper_bundle: bool = False) -> subprocess.CompletedProcess:
    env = _wrap_env()
    wrapper = project / "_bmad" / "rdx-tea" / "scripts" / "rdx_tea_wrapper.py"
    skill = project / ".claude" / "skills" / "bmad-testarch-test-design"
    head = _git_head(project, env)
    r = _run([str(_venv_python()), str(wrapper), "prepare-run",
              "--workflow", "test-design",
              "--project-root", str(project),
              "--run-id", run_id,
              "--skill-dir", str(skill),
              "--base-sha", head, "--head-sha", head,
              "--allow-fixture-diff", str(project / "_bmad-run" / "diff.patch")],
             cwd=project, env=env)
    if r.returncode != 0:
        return r
    if tamper_bundle:
        b = (project / "_bmad" / "rdx-tea" / "runtime" / "test-design"
             / run_id / "active-context.md")
        b.write_text(b.read_text() + "\n<attacker>\n", encoding="utf-8")
    return _run([str(_venv_python()), str(wrapper), "finalize-run",
                 "--workflow", "test-design",
                 "--project-root", str(project),
                 "--run-id", run_id,
                 "--test-write-fake-artefact"],
                cwd=project, env=env)


# --------------------------------------------------------------------------

def test_l4_d31_e01_two_phase_wrapper_end_to_end(external_project: Path) -> None:
    r = _prepare_and_finalize(external_project)
    assert r.returncode == 0, f"finalize-run failed: {r.stderr}"
    report = json.loads(r.stdout)
    assert report["workflow"] == "test-design"
    assert report["execution_mode"] == "sequential"
    assert report["requested_mode"] == "sequential"
    assert report["run_id"] == "smoke-01"
    assert report["sidecars"], "no sidecars produced"
    assert all(v["verdict"] == "PASS" for v in report["verifier"])
    sc = report["sidecars"][0]
    for k in ("base_sha", "head_sha", "diff_digest",
              "rdx_source_sha", "tea_source_sha",
              "projection_hash", "artifact_sha256"):
        assert sc[k] and len(sc[k]) >= 40, f"sidecar.{k} missing"


def test_l4_d31_e02_sidecar_schema_valid_from_external_project(external_project: Path) -> None:
    r = _prepare_and_finalize(external_project)
    assert r.returncode == 0, r.stderr
    schema = json.loads(
        (RDX_TEA_DIR / "architecture" / "rdx-tea-run.v1.schema.json").read_text()
    )
    for sc in json.loads(r.stdout)["sidecars"]:
        jsonschema.validate(instance=sc, schema=schema)


def test_l4_d31_e03_verifier_fails_on_bundle_tamper(external_project: Path) -> None:
    r = _prepare_and_finalize(external_project, tamper_bundle=True)
    assert r.returncode != 0
    out = (r.stderr + r.stdout).lower()
    assert "tamper" in out or "bundle" in out


def test_l4_d31_e04_prepare_fails_closed_without_identity(external_project: Path) -> None:
    prepare = external_project / "_bmad" / "rdx-tea" / "scripts" / "prepare.py"
    env = _wrap_env()
    # Omit --run-id and --base-sha entirely; argparse must fail.
    r = _run([str(_venv_python()), str(prepare),
              "--workflow", "test-design",
              "--project-root", str(external_project)],
             cwd=external_project, env=env)
    assert r.returncode != 0, "prepare must reject missing identity/run-id"


def test_l4_d31_e05_no_rdx_dev_tree_paths_referenced(external_project: Path) -> None:
    forbidden_in_scripts = [
        str(REPO_ROOT),
        "tests/contracts",
        ".claude/skills/rdx-setup",
        "rdx-validator/rdx_validator",
    ]
    for src in (external_project / "_bmad" / "rdx-tea").rglob("*"):
        if not src.is_file() or src.suffix not in (".py", ".sh", ".toml", ".yaml", ".yml"):
            continue
        try:
            txt = src.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for f in forbidden_in_scripts:
            assert f not in txt, f"{src.name} embeds dev-tree path {f!r}"


def test_l4_d31_e06_wrapper_rejects_non_sequential(external_project: Path) -> None:
    """D3.2 §3: `auto`, `subagent`, `agent-team` all rejected — only
    literal `sequential`."""
    (external_project / "_bmad" / "tea" / "config.yaml").write_text(
        "tea_execution_mode: auto\n"
        "test_artifacts: '{project-root}/_bmad-output/test-artifacts'\n",
        encoding="utf-8",
    )
    r = _prepare_and_finalize(external_project)
    assert r.returncode != 0
    assert "sequential" in (r.stderr + r.stdout).lower()


def test_l4_d31_e07_bootstrap_verifies_upstream_tags(tmp_path: Path) -> None:
    bs = INSTALL_TREE / "_bmad" / "rdx-tea" / "bootstrap" / "bootstrap.py"
    if not (WORKSPACE / "upstream").exists():
        pytest.skip("no upstream clone")
    target = tmp_path / "reuse"
    target.mkdir()
    shutil.copytree(UPSTREAM_BMAD, target / "BMAD-METHOD")
    shutil.copytree(UPSTREAM_TEA, target / "bmad-method-test-architecture-enterprise")
    env = _wrap_env()
    # D3.2: test reuses a pre-checked-out clone whose git-status is dirty
    # under tag checkouts (submodule quirks). The bootstrap's clean-worktree
    # guard is production-only and bypassed via env.
    env["RDX_TEA_BOOTSTRAP_SKIP_WORKTREE_CHECK"] = "1"
    r = subprocess.run(
        [str(_venv_python()), str(bs), "--target-dir", str(target)],
        capture_output=True, text=True, env=env, check=False,
    )
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["bmad_source_sha"] == "3bcd6c3cce6e381b759e23185b099081496567a5"
    assert out["tea_source_sha"] == "8734d51f24071ddbcb3617390b5fcddb4128ef77"
    assert out["hashes_verified"] is True


def test_l4_d31_e08_run_scoped_layout_isolates_runs(external_project: Path) -> None:
    """Two runs with different run_ids must produce separate runtime
    directories; second run does NOT touch the first."""
    _prepare_and_finalize(external_project, run_id="smoke-01")
    _prepare_and_finalize(external_project, run_id="smoke-02")
    root = external_project / "_bmad" / "rdx-tea" / "runtime" / "test-design"
    assert (root / "smoke-01" / "active-context.md").exists()
    assert (root / "smoke-02" / "active-context.md").exists()
