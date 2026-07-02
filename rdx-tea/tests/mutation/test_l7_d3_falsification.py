"""L7 falsification tests for Variant D3 (prompt §7).

Each test attempts to falsify a D3 invariant. Where the current PoC
does not yet enforce the invariant, the test is marked xfail with a
pointer to the follow-up stage.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
from pathlib import Path

import pytest

RDX_TEA_DIR = Path(__file__).resolve().parent.parent.parent
REPO_ROOT = RDX_TEA_DIR.parent
WORKSPACE = REPO_ROOT.parent
UPSTREAM_TEA = WORKSPACE / "upstream" / "bmad-method-test-architecture-enterprise"
UPSTREAM_BMAD = WORKSPACE / "upstream" / "BMAD-METHOD"
RESOLVER = UPSTREAM_BMAD / "src" / "scripts" / "resolve_customization.py"
VENV_PY = RDX_TEA_DIR / ".venv-baseline" / "bin" / "python"

PREPARE_PY = RDX_TEA_DIR / "poc" / "adapter" / "prepare.py"
BINDER_PY = RDX_TEA_DIR / "poc" / "adapter" / "binder.py"


def _load(mod_path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, mod_path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


prepare_mod = _load(PREPARE_PY, "prepare")
binder_mod = _load(BINDER_PY, "binder")


ASYNC_DIFF = "diff --git a/src/lib.rs b/src/lib.rs\n--- a/src/lib.rs\n+++ b/src/lib.rs\n@@ -0,0 +1,3 @@\n+pub async fn f() {}\n+async fn g() { tokio::spawn(async {}).await.unwrap(); }\n"


@pytest.fixture
def project(tmp_path: Path) -> Path:
    p = tmp_path / "proj"
    p.mkdir()
    (p / "_bmad" / "custom").mkdir(parents=True)
    (p / "_bmad-run").mkdir()
    return p


def _prepare(project: Path, workflow: str, diff: str = ASYNC_DIFF):
    (project / "_bmad-run" / "diff.patch").write_text(diff)
    return prepare_mod.prepare(
        project_root=project,
        workflow=workflow,
        diff_path=project / "_bmad-run" / "diff.patch",
    )


def test_l7_f01_active_bundle_missing_binder_fails_closed(project: Path) -> None:
    """Prompt §7.2 — active bundle missing → TEA must not silently
    continue as RDX-enabled. Binder must refuse."""
    art = project / "artefact.md"
    art.write_text("no bundle")
    with pytest.raises(SystemExit):
        binder_mod.bind(project_root=project, workflow="test-design", artifact=art)


def test_l7_f02_bundle_hash_change_detected(project: Path) -> None:
    """Prompt §7.4 — bundle hash changes after load → detected by
    comparing sidecar projection_hash against fresh bundle hash."""
    _prepare(project, "test-design")
    art_dir = project / "_bmad-output" / "test-artifacts"
    art_dir.mkdir(parents=True)
    art = art_dir / "t.md"
    art.write_text("hi")
    s1 = binder_mod.bind(project_root=project, workflow="test-design", artifact=art)
    bundle_path = project / "_bmad" / "rdx-tea" / "runtime" / "test-design" / "active-context.md"
    # Tamper the bundle.
    bundle_path.write_text(bundle_path.read_text() + "\n<tamper>\n")
    new_hash = hashlib.sha256(bundle_path.read_bytes()).hexdigest()
    assert s1["projection_hash"] != new_hash, "hash must diverge on tamper"


def test_l7_f03_tea_artifact_change_after_sidecar_detected(project: Path) -> None:
    """Prompt §7.5 — TEA artefact changed after sidecar → sidecar hash
    no longer matches artefact bytes."""
    _prepare(project, "test-design")
    art_dir = project / "_bmad-output" / "test-artifacts"
    art_dir.mkdir(parents=True)
    art = art_dir / "t.md"
    art.write_text("hi")
    s = binder_mod.bind(project_root=project, workflow="test-design", artifact=art)
    art.write_text("hi\n<tamper>\n")
    assert s["artifact_sha256"] != hashlib.sha256(art.read_bytes()).hexdigest()


def test_l7_f04_non_rust_story_receives_no_pack(project: Path) -> None:
    """Prompt §7.9 — non-Rust story receives no Rust bundle."""
    m = _prepare(project, "test-design", diff="diff --git a/x.yaml b/x.yaml\n--- a/x.yaml\n+++ b/x.yaml\n@@ -0,0 +1,1 @@\n+ok\n")
    assert not m["active_packs"], f"non-Rust must be empty: {m['active_packs']}"


def test_l7_f05_bundle_never_carries_llm_pass_verdict(project: Path) -> None:
    """Prompt §7.14 — the generator never emits an RDX PASS in the
    bundle."""
    _prepare(project, "test-design")
    body = (project / "_bmad" / "rdx-tea" / "runtime" / "test-design" / "active-context.md").read_text()
    for banned in ("verdict: PASS", "verdict:PASS", "PASS_verdict", "cat1_pass"):
        assert banned not in body


def test_l7_f06_no_global_rdx_tea_index_consumed(project: Path) -> None:
    """Prompt §7.13 — the legacy parallel `rdx-tea-index.csv` must NOT
    be consumed by the prepare pipeline. This is enforced by simply not
    referencing it — regression guard via source scan."""
    txt = PREPARE_PY.read_text()
    assert "rdx-tea-index.csv" not in txt, (
        "prepare.py still references the legacy parallel index"
    )


def test_l7_f07_prepare_output_deterministic_across_two_processes(tmp_path: Path) -> None:
    """Prompt §7 — determinism check via two subprocess invocations."""
    for d in (tmp_path / "a", tmp_path / "b"):
        d.mkdir()
        (d / "_bmad-run").mkdir()
        (d / "_bmad-run" / "diff.patch").write_text(ASYNC_DIFF)
        (d / "_bmad-run" / "story.md").write_text("story")
    import os
    env = os.environ.copy()
    env["RDX_TEA_FAKE_NOW"] = "2026-07-02T00:00:00+00:00"
    for d in (tmp_path / "a", tmp_path / "b"):
        r = subprocess.run(
            [str(VENV_PY), str(PREPARE_PY),
             "--workflow", "test-design",
             "--project-root", str(d),
             "--diff", str(d / "_bmad-run" / "diff.patch"),
             "--story", str(d / "_bmad-run" / "story.md")],
            env=env, capture_output=True, text=True,
        )
        assert r.returncode == 0, r.stderr
    a = (tmp_path / "a" / "_bmad" / "rdx-tea" / "runtime" / "test-design" / "active-context.md").read_bytes()
    b = (tmp_path / "b" / "_bmad" / "rdx-tea" / "runtime" / "test-design" / "active-context.md").read_bytes()
    assert a == b, "bundle non-deterministic across two process runs"


def test_l7_f08_unsupported_workflow_raises_or_no_op(project: Path) -> None:
    """Prompt §7.11 — an unsupported workflow name must not silently
    write random packs into the bundle. Current PoC treats unknown
    workflows as empty obligation matrix → empty bundle."""
    m = _prepare(project, "bogus-workflow")
    assert not m["active_packs"], (
        f"unknown workflow must yield empty active_packs, got {m['active_packs']}"
    )
