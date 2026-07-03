"""L4 D3.3 deterministic gap closure tests.

Covers §4 of the D3.3 prompt:

  §4.1 Run-specific overlay proved via real upstream `resolve_customization.py`
  §4.2 Workspace isolation via active-run.lock + two-worktree adversarial
  §4.3 Pre-bind boundary (symlink, outside project, outside declared outputs)
  §4.4 Rust relevance split (docs-only in Rust repo → empty bundle)
  §4.5 observed_mode surrogate populated from transcript (or INFERRED_ABSENT)
  §4.6 ATDD wrapper self-contained (no external read directive)
"""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

RDX_TEA_DIR = Path(__file__).resolve().parent.parent.parent
REPO_ROOT = RDX_TEA_DIR.parent
WORKSPACE = REPO_ROOT.parent
UPSTREAM_TEA = WORKSPACE / "upstream" / "bmad-method-test-architecture-enterprise"
UPSTREAM_BMAD = WORKSPACE / "upstream" / "BMAD-METHOD"
VENV_PY = RDX_TEA_DIR / ".venv-baseline" / "bin" / "python"
INSTALL_TREE = RDX_TEA_DIR / "poc" / "install-tree"
RESOLVER = UPSTREAM_BMAD / "src" / "scripts" / "resolve_customization.py"


ASYNC_DIFF = """diff --git a/src/lib.rs b/src/lib.rs
--- a/src/lib.rs
+++ b/src/lib.rs
@@ -0,0 +1,4 @@
+pub async fn f() {
+    let h = tokio::spawn(async {});
+    h.await.unwrap();
+}
"""

DOCS_ONLY_DIFF = """diff --git a/README.md b/README.md
--- a/README.md
+++ b/README.md
@@ -0,0 +1,1 @@
+# Docs update inside a Rust project.
"""


def _run(cmd: list[str], cwd: Path, env: dict | None = None):
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True,
                          env=env, check=False)


@pytest.fixture
def rust_project(tmp_path: Path) -> Path:
    """Fresh rust-flavoured git project with install-tree adapter."""
    proj = tmp_path / "proj"
    proj.mkdir()
    shutil.copytree(INSTALL_TREE / "_bmad", proj / "_bmad")
    (proj / "_bmad-run").mkdir()
    (proj / "_bmad-output" / "test-artifacts").mkdir(parents=True)
    slug = "bmad-testarch-test-design"
    if not (UPSTREAM_TEA / "src" / "workflows" / "testarch" / slug).exists():
        pytest.skip("upstream TEA missing")
    shutil.copytree(UPSTREAM_TEA / "src" / "workflows" / "testarch" / slug,
                    proj / ".claude" / "skills" / slug)
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
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "init"],
    ):
        r = _run(c, cwd=proj)
        assert r.returncode == 0, r.stderr
    return proj


def _venv() -> Path:
    return VENV_PY


def _env() -> dict:
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env["RDX_TEA_ALLOW_FIXTURE_DIFF"] = "1"
    env["RDX_TEA_ALLOW_TEST_ARTEFACT"] = "1"
    return env


def _prepare(project: Path, run_id: str, diff: str = ASYNC_DIFF):
    (project / "_bmad-run" / "diff.patch").write_text(diff, encoding="utf-8")
    head = _run(["git", "-C", str(project), "rev-parse", "HEAD"], cwd=project).stdout.strip()
    wrap = project / "_bmad" / "rdx-tea" / "scripts" / "rdx_tea_wrapper.py"
    skill = project / ".claude" / "skills" / "bmad-testarch-test-design"
    return _run([str(_venv()), str(wrap), "prepare-run",
                 "--workflow", "test-design",
                 "--project-root", str(project),
                 "--run-id", run_id,
                 "--skill-dir", str(skill),
                 "--base-sha", head, "--head-sha", head,
                 "--allow-fixture-diff", str(project / "_bmad-run" / "diff.patch")],
                cwd=project, env=_env())


def _finalize(project: Path, run_id: str):
    wrap = project / "_bmad" / "rdx-tea" / "scripts" / "rdx_tea_wrapper.py"
    return _run([str(_venv()), str(wrap), "finalize-run",
                 "--workflow", "test-design",
                 "--project-root", str(project),
                 "--run-id", run_id,
                 "--test-write-fake-artefact"],
                cwd=project, env=_env())


# ============================================================ §4.1 overlay


def test_l4_d33_overlay_written_and_resolver_returns_run_scoped_path(rust_project: Path):
    r = _prepare(rust_project, "ovl-01")
    assert r.returncode == 0, r.stderr
    overlay = rust_project / "_bmad" / "custom" / "bmad-testarch-test-design.toml"
    assert overlay.exists()
    assert "ovl-01/active-context.md" in overlay.read_text(encoding="utf-8")

    # Run the REAL upstream resolver.
    skill = rust_project / ".claude" / "skills" / "bmad-testarch-test-design"
    r2 = _run([str(_venv()), str(RESOLVER),
               "--skill", str(skill), "--key", "workflow"],
              cwd=rust_project, env=_env())
    assert r2.returncode == 0, r2.stderr
    merged = json.loads(r2.stdout)["workflow"]
    facts = merged["persistent_facts"]
    assert any("runtime/test-design/ovl-01/active-context.md" in f for f in facts), (
        f"resolver did not merge the run-scoped bundle path: {facts}"
    )
    # No stale static path.
    for f in facts:
        assert "runtime/test-design/active-context.md" not in f, (
            f"stale static path still present: {f}"
        )


def test_l4_d33_finalize_restores_overlay(rust_project: Path):
    # Pre-existing user overlay.
    pre = rust_project / "_bmad" / "custom" / "bmad-testarch-test-design.toml"
    pre.parent.mkdir(parents=True, exist_ok=True)
    pre.write_text("[workflow]\npersistent_facts = [\"file:PRE-EXISTING\"]\n",
                   encoding="utf-8")
    r1 = _prepare(rust_project, "ovl-02")
    assert r1.returncode == 0
    # Overlay was replaced.
    assert "ovl-02" in pre.read_text()
    # Backup exists.
    backup = rust_project / "_bmad" / "rdx-tea" / "runtime" / "test-design" / "ovl-02" / "overlay-backup.toml"
    assert backup.exists()
    assert "PRE-EXISTING" in backup.read_text()
    r2 = _finalize(rust_project, "ovl-02")
    assert r2.returncode == 0, r2.stderr
    # Restored to the pre-existing content.
    assert "PRE-EXISTING" in pre.read_text()


# ============================================================ §4.2 lock


def test_l4_d33_active_run_lock_refuses_second_run(rust_project: Path):
    r1 = _prepare(rust_project, "lock-01")
    assert r1.returncode == 0
    # Second run without finalize must fail.
    r2 = _prepare(rust_project, "lock-02")
    assert r2.returncode != 0
    assert "active" in (r1.stderr + r2.stderr + r2.stdout).lower()
    _finalize(rust_project, "lock-01")
    # Now a second run is accepted.
    r3 = _prepare(rust_project, "lock-03")
    assert r3.returncode == 0


def test_l4_d33_two_worktrees_isolated(tmp_path: Path, rust_project: Path):
    """Second, independent worktree with different install-tree copy
    must not see the first worktree's overlay or bundle."""
    proj_b = tmp_path / "proj_b"
    shutil.copytree(rust_project, proj_b, symlinks=True,
                    ignore=shutil.ignore_patterns(".git"))
    for c in (
        ["git", "init", "-q"], ["git", "add", "-A"],
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "init-b"],
    ):
        _run(c, cwd=proj_b)
    r_a = _prepare(rust_project, "iso-A")
    assert r_a.returncode == 0
    _finalize(rust_project, "iso-A")
    r_b = _prepare(proj_b, "iso-B")
    assert r_b.returncode == 0
    _finalize(proj_b, "iso-B")
    # A's bundle path not visible in B.
    b_dir = proj_b / "_bmad" / "rdx-tea" / "runtime" / "test-design"
    assert (b_dir / "iso-B" / "active-context.md").exists()
    assert not (b_dir / "iso-A" / "active-context.md").exists(), (
        "B's runtime tree leaked A's run"
    )


# ============================================================ §4.3 pre-bind


def test_l4_d33_prebind_rejects_symlink(rust_project: Path):
    r = _prepare(rust_project, "pb-sym-01")
    assert r.returncode == 0
    real = rust_project / "_bmad-output" / "test-artifacts" / "real.md"
    real.write_text("real", encoding="utf-8")
    link = rust_project / "_bmad-output" / "test-artifacts" / "linked.md"
    link.symlink_to(real)
    binder_mod = _import_binder()
    with pytest.raises(binder_mod.BinderError, match="symlink"):
        binder_mod.bind(project_root=rust_project, workflow="test-design",
                        artifact=link, run_id="pb-sym-01")


def test_l4_d33_prebind_rejects_outside_project(tmp_path: Path, rust_project: Path):
    r = _prepare(rust_project, "pb-out-01")
    assert r.returncode == 0
    outside = tmp_path / "outside.md"
    outside.write_text("outside", encoding="utf-8")
    binder_mod = _import_binder()
    with pytest.raises(binder_mod.BinderError, match="outside project-root"):
        binder_mod.bind(project_root=rust_project, workflow="test-design",
                        artifact=outside, run_id="pb-out-01")


def test_l4_d33_prebind_rejects_outside_declared_output(rust_project: Path):
    r = _prepare(rust_project, "pb-out2-01")
    assert r.returncode == 0
    # Artefact inside project but outside declared output roots.
    stray = rust_project / "src" / "stray.md"
    stray.parent.mkdir(parents=True, exist_ok=True)
    stray.write_text("s", encoding="utf-8")
    binder_mod = _import_binder()
    declared = [rust_project / "_bmad-output" / "test-artifacts"]
    with pytest.raises(binder_mod.BinderError, match="outside declared output roots"):
        binder_mod.bind(project_root=rust_project, workflow="test-design",
                        artifact=stray, run_id="pb-out2-01",
                        declared_output_roots=declared)


def _import_binder():
    sys.path.insert(0, str(INSTALL_TREE / "_bmad" / "rdx-tea" / "scripts"))
    if "binder" in sys.modules:
        del sys.modules["binder"]
    return importlib.import_module("binder")


# ============================================================ §4.4 relevance


def test_l4_d33_docs_only_inside_rust_repo_yields_empty_bundle(rust_project: Path):
    r = _prepare(rust_project, "docs-01", diff=DOCS_ONLY_DIFF)
    assert r.returncode == 0, r.stderr
    manifest_path = (rust_project / "_bmad" / "rdx-tea" / "runtime"
                     / "test-design" / "docs-01" / "run-manifest.json")
    manifest = json.loads(manifest_path.read_text())
    assert manifest["rust_scope"] is False, (
        f"docs-only diff in Rust repo should yield rust_scope=false, got {manifest}"
    )
    assert not manifest["active_packs"]
    assert not manifest["core_rules"]


def test_l4_d33_rust_diff_still_carries_core(rust_project: Path):
    r = _prepare(rust_project, "rs-01", diff=ASYNC_DIFF)
    assert r.returncode == 0
    manifest_path = (rust_project / "_bmad" / "rdx-tea" / "runtime"
                     / "test-design" / "rs-01" / "run-manifest.json")
    manifest = json.loads(manifest_path.read_text())
    assert manifest["rust_scope"] is True
    assert manifest["core_rules"], "Rust diff should include CORE-* rules"


# ============================================================ §4.5 observed


def test_l4_d33_observed_mode_recorded(rust_project: Path):
    _prepare(rust_project, "obs-01")
    r = _finalize(rust_project, "obs-01")
    assert r.returncode == 0
    rep = json.loads(r.stdout)
    assert "observed_mode" in rep
    # Without a transcript, the wrapper reports INFERRED_ABSENT.
    assert rep["observed_mode"] in (
        "OBSERVED_SEQUENTIAL", "OBSERVED_SUBAGENT", "INFERRED_ABSENT"
    )


def test_l4_d33_observed_mode_detects_subagent_transcript(rust_project: Path):
    _prepare(rust_project, "obs-sub-01")
    # Simulate a transcript with a subagent dispatch token — this
    # exercises the parser, not a live run.
    run_dir = rust_project / "_bmad" / "rdx-tea" / "runtime" / "test-design" / "obs-sub-01"
    (run_dir / "transcript.stream.jsonl").write_text(
        '{"event":"subagent_dispatch","name":"worker-a"}\n',
        encoding="utf-8",
    )
    r = _finalize(rust_project, "obs-sub-01")
    assert r.returncode == 0
    rep = json.loads(r.stdout)
    assert rep["observed_mode"] == "OBSERVED_SUBAGENT"


# ============================================================ §4.6 atdd


def test_l4_d33_atdd_wrapper_self_contained():
    p = INSTALL_TREE / ".claude" / "skills" / "rdx-tea-atdd" / "SKILL.md"
    text = p.read_text(encoding="utf-8")
    # Must NOT direct the reader to a sibling.
    assert "Follow the seven steps in" not in text
    assert "sibling SKILL.md" not in text
    # Every mandatory phase must be present.
    for phase in ("Step 1", "Step 2", "Step 3", "Step 4",
                  "Step 5", "Step 6", "Step 7"):
        assert phase in text, f"ATDD wrapper missing {phase}"
    # Correct workflow name.
    assert "bmad-testarch-atdd" in text
    assert "atdd" in text
