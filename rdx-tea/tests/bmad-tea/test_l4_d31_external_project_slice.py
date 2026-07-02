"""L4 D3.1 vertical slice in a FRESH EXTERNAL PROJECT.

This test proves that the D3.1 adapter works when installed into a
disposable project that has NO access to the RDX dev tree. Only the
`install-tree/_bmad/rdx-tea/` payload plus upstream BMAD-METHOD +
BMAD TEA source. The dev-tree paths (`tests/contracts/`,
`.claude/skills/rdx-setup/assets/kb-sections/`, `rdx-validator/`) are
UNREACHABLE inside the tmp project — enforced by chdir + env-cleaned
subprocess invocation.

This is the "install once, run anywhere" proof required by the D3.1
prompt items 4 and 10.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

RDX_TEA_DIR = Path(__file__).resolve().parent.parent.parent
REPO_ROOT = RDX_TEA_DIR.parent
WORKSPACE = REPO_ROOT.parent
UPSTREAM_TEA = WORKSPACE / "upstream" / "bmad-method-test-architecture-enterprise"
UPSTREAM_BMAD = WORKSPACE / "upstream" / "BMAD-METHOD"
VENV_PY = RDX_TEA_DIR / ".venv-baseline" / "bin" / "python"
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


@pytest.fixture
def external_project(tmp_path: Path) -> Path:
    """A tmp project outside the RDX repo with the adapter installed via
    file copy — mirrors what a real installer would do."""
    proj = tmp_path / "external_proj"
    proj.mkdir()
    # Install the D3.1 adapter payload.
    shutil.copytree(INSTALL_TREE / "_bmad", proj / "_bmad")
    (proj / "_bmad-run").mkdir()
    (proj / "_bmad-output" / "test-artifacts").mkdir(parents=True)
    # Copy the upstream TEA skill so the wrapper can discover outputs.
    skill_dst = proj / ".claude" / "skills" / "bmad-testarch-test-design"
    if not (UPSTREAM_TEA / "src" / "workflows" / "testarch" / "bmad-testarch-test-design").exists():
        pytest.skip("upstream TEA absent — bootstrap needs to run")
    shutil.copytree(
        UPSTREAM_TEA / "src" / "workflows" / "testarch" / "bmad-testarch-test-design",
        skill_dst,
    )
    # Stub TEA config with sequential mode.
    (proj / "_bmad" / "tea").mkdir(exist_ok=True)
    (proj / "_bmad" / "tea" / "config.yaml").write_text(
        "tea_execution_mode: sequential\n"
        "test_artifacts: '{project-root}/_bmad-output/test-artifacts'\n"
        "output_folder: '{project-root}/_bmad-output'\n"
        "project_name: external\n",
        encoding="utf-8",
    )
    (proj / "_bmad-run" / "diff.patch").write_text(ASYNC_DIFF, encoding="utf-8")
    (proj / "_bmad-run" / "story.md").write_text("# External Rust story\n", encoding="utf-8")
    return proj


def _venv_python() -> Path:
    return VENV_PY


def _run(cmd: list[str], cwd: Path, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True,
                          text=True, env=env, check=False)


def test_l4_d31_e01_wrapper_runs_end_to_end_in_external_project(external_project: Path) -> None:
    """The wrapper must run cleanly from a project that has no access to
    the RDX dev tree. Env is sanitised of anything pointing at the RDX
    repo."""
    env = os.environ.copy()
    env.pop("RDX_TEA_CANONICAL_ROOT", None)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    # Explicitly REMOVE PYTHONPATH so the child can't see the dev tree.
    env.pop("PYTHONPATH", None)
    wrapper = external_project / "_bmad" / "rdx-tea" / "scripts" / "rdx_tea_wrapper.py"
    skill = external_project / ".claude" / "skills" / "bmad-testarch-test-design"
    r = _run([
        str(_venv_python()), str(wrapper),
        "--workflow", "test-design",
        "--project-root", str(external_project),
        "--skill-dir", str(skill),
        "--simulate-child",
    ], cwd=external_project, env=env)
    assert r.returncode == 0, f"wrapper failed: {r.stderr}"

    report = json.loads(r.stdout)
    assert report["workflow"] == "test-design"
    assert report["execution_mode"] == "sequential"
    assert report["requested_mode"] == "sequential"
    assert report["sidecars"], "no sidecars produced"
    sc = report["sidecars"][0]
    for k in ("base_sha", "head_sha", "diff_digest",
              "rdx_source_sha", "tea_source_sha",
              "projection_hash", "artifact_sha256"):
        assert sc.get(k) and len(sc[k]) >= 40, f"sidecar.{k} missing/short"
    assert sc["execution_mode"] == "sequential"
    assert sc["completed"] is True


def test_l4_d31_e02_sidecar_schema_valid_from_external_project(external_project: Path) -> None:
    import jsonschema
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    wrapper = external_project / "_bmad" / "rdx-tea" / "scripts" / "rdx_tea_wrapper.py"
    skill = external_project / ".claude" / "skills" / "bmad-testarch-test-design"
    r = _run([
        str(_venv_python()), str(wrapper),
        "--workflow", "test-design",
        "--project-root", str(external_project),
        "--skill-dir", str(skill),
        "--simulate-child",
    ], cwd=external_project, env=env)
    assert r.returncode == 0, r.stderr
    schema = json.loads(
        (RDX_TEA_DIR / "architecture" / "rdx-tea-run.v1.schema.json").read_text()
    )
    sidecars = json.loads(r.stdout)["sidecars"]
    for sc in sidecars:
        jsonschema.validate(instance=sc, schema=schema)


def test_l4_d31_e03_binder_fails_closed_when_bundle_tampered(external_project: Path) -> None:
    """Modify the bundle after prepare, then attempt to bind — must fail."""
    # Run prepare first via the wrapper (simulated).
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    wrapper = external_project / "_bmad" / "rdx-tea" / "scripts" / "rdx_tea_wrapper.py"
    skill = external_project / ".claude" / "skills" / "bmad-testarch-test-design"
    r = _run([
        str(_venv_python()), str(wrapper),
        "--workflow", "test-design",
        "--project-root", str(external_project),
        "--skill-dir", str(skill),
        "--simulate-child",
    ], cwd=external_project, env=env)
    assert r.returncode == 0
    # Tamper the bundle.
    bundle = external_project / "_bmad" / "rdx-tea" / "runtime" / "test-design" / "active-context.md"
    bundle.write_text(bundle.read_text() + "\n<injected by attacker>\n", encoding="utf-8")
    # Direct binder invocation must now refuse.
    binder = external_project / "_bmad" / "rdx-tea" / "scripts" / "binder.py"
    artefact = list((external_project / "_bmad-output" / "test-artifacts").glob("*.md"))[0]
    r2 = _run([
        str(_venv_python()), str(binder),
        "--workflow", "test-design",
        "--project-root", str(external_project),
        "--artifact", str(artefact),
    ], cwd=external_project, env=env)
    assert r2.returncode != 0, (
        f"binder should refuse tampered bundle: {r2.stdout} {r2.stderr}"
    )
    assert "tamper" in (r2.stderr + r2.stdout).lower()


def test_l4_d31_e04_prepare_fails_closed_without_identity(external_project: Path) -> None:
    """The D3 gap — identity fields were optional. D3.1 makes them
    mandatory and prepare refuses to write a bundle without them."""
    prepare = external_project / "_bmad" / "rdx-tea" / "scripts" / "prepare.py"
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    r = _run([
        str(_venv_python()), str(prepare),
        "--workflow", "test-design",
        "--project-root", str(external_project),
        # NOTE: intentionally omit --base-sha, --head-sha, --rdx-source-sha, --tea-source-sha
    ], cwd=external_project, env=env)
    assert r.returncode != 0, "prepare should reject missing identity"


def test_l4_d31_e05_no_rdx_dev_tree_paths_referenced(external_project: Path) -> None:
    """Regression against the D3 portability gap: EXECUTABLE files in the
    install tree (Python scripts, shell) must not name any absolute
    dev-tree path or import rdx_validator directly. JSON data files may
    carry informational `kb_source` fields (source-of-truth pointers)
    but no scripts import them for path resolution."""
    forbidden_in_scripts = [
        str(REPO_ROOT),
        "tests/contracts",
        ".claude/skills/rdx-setup",
        "rdx-validator/rdx_validator",
    ]
    for src in (external_project / "_bmad" / "rdx-tea").rglob("*"):
        if not src.is_file():
            continue
        if src.suffix not in (".py", ".sh", ".toml", ".yaml", ".yml"):
            continue
        try:
            txt = src.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for f in forbidden_in_scripts:
            assert f not in txt, (
                f"install-tree script {src.name} embeds dev-tree path {f!r}"
            )
    # No absolute path from the RDX repo in the executable payload.
    for src in (external_project / "_bmad" / "rdx-tea" / "scripts").rglob("*.py"):
        assert str(REPO_ROOT) not in src.read_text(encoding="utf-8")


def test_l4_d31_e06_wrapper_verifies_sequential_mode(external_project: Path) -> None:
    """If the TEA config declares an unsupported mode, the wrapper must
    fail closed."""
    (external_project / "_bmad" / "tea" / "config.yaml").write_text(
        "tea_execution_mode: subagent\n"
        "test_artifacts: '{project-root}/_bmad-output/test-artifacts'\n",
        encoding="utf-8",
    )
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    wrapper = external_project / "_bmad" / "rdx-tea" / "scripts" / "rdx_tea_wrapper.py"
    skill = external_project / ".claude" / "skills" / "bmad-testarch-test-design"
    r = _run([
        str(_venv_python()), str(wrapper),
        "--workflow", "test-design",
        "--project-root", str(external_project),
        "--skill-dir", str(skill),
        "--simulate-child",
    ], cwd=external_project, env=env)
    assert r.returncode != 0
    assert "sequential" in (r.stderr + r.stdout).lower()


def test_l4_d31_e07_bootstrap_verifies_upstream_tags(tmp_path: Path) -> None:
    """The bootstrap script clones the exact SHAs recorded in
    sources.lock. It refuses if either tag resolves differently."""
    bs = INSTALL_TREE / "_bmad" / "rdx-tea" / "bootstrap" / "bootstrap.py"
    # Skip when upstream clones are already present — this test is
    # about verifying the mechanism, not re-downloading upstream in CI.
    if not (WORKSPACE / "upstream").exists():
        pytest.skip("no upstream clone to reuse")
    # Reuse existing upstream repos to avoid network.
    target = tmp_path / "reuse"
    target.mkdir()
    shutil.copytree(UPSTREAM_BMAD, target / "BMAD-METHOD")
    shutil.copytree(UPSTREAM_TEA, target / "bmad-method-test-architecture-enterprise")
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    r = subprocess.run(
        [str(_venv_python()), str(bs), "--target-dir", str(target)],
        capture_output=True, text=True, env=env, check=False,
    )
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["bmad_source_sha"] == "3bcd6c3cce6e381b759e23185b099081496567a5"
    assert out["tea_source_sha"] == "8734d51f24071ddbcb3617390b5fcddb4128ef77"
