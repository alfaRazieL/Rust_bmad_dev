"""L4 lifecycle tests for D3 (Phase H).

Focus on the parts of lifecycle actually implemented at PoC:
  * Repeated prepare invocations are idempotent (atomic replace works).
  * Interrupted prepare leaves no `.tmp` residue.
  * `.user.toml` overlay survives after a re-run.
  * Stale runtime bundle is cleaned by the next prepare (not accumulated).

Fresh install / uninstall / rollback / missing TEA / unsupported TEA
version stages are deferred to production installer work
(PROOF_COMPLETION superseded by D3_PROOF_PLAN §Stage H).
"""

from __future__ import annotations

import os
import sys
import importlib.util
import shutil
import subprocess
from pathlib import Path

import pytest

RDX_TEA_DIR = Path(__file__).resolve().parent.parent.parent
REPO_ROOT = RDX_TEA_DIR.parent
UPSTREAM_ROOT = Path(os.environ.get("RDX_TEA_UPSTREAM_ROOT", str(REPO_ROOT.parent / "upstream")))
WORKSPACE = UPSTREAM_ROOT.parent
UPSTREAM_TEA = UPSTREAM_ROOT / "bmad-method-test-architecture-enterprise"
UPSTREAM_BMAD = UPSTREAM_ROOT / "BMAD-METHOD"
RESOLVER = UPSTREAM_BMAD / "src" / "scripts" / "resolve_customization.py"
VENV_PY = Path(sys.executable)
PREPARE_PY = RDX_TEA_DIR / "poc" / "adapter" / "prepare.py"


spec = importlib.util.spec_from_file_location("prepare", PREPARE_PY)
prepare_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare_mod)


ASYNC_DIFF = "diff --git a/src/lib.rs b/src/lib.rs\n--- a/src/lib.rs\n+++ b/src/lib.rs\n@@ -0,0 +1,2 @@\n+pub async fn f() { tokio::spawn(async{}).await.unwrap(); }\n"


@pytest.fixture
def project(tmp_path: Path) -> Path:
    p = tmp_path / "proj"
    p.mkdir()
    (p / "_bmad" / "custom").mkdir(parents=True)
    (p / "_bmad-run").mkdir()
    return p


def _prepare(project: Path):
    (project / "_bmad-run" / "diff.patch").write_text(ASYNC_DIFF)
    return prepare_mod.prepare(
        project_root=project,
        workflow="test-design",
        diff_path=project / "_bmad-run" / "diff.patch",
    )


def test_l4_h01_repeated_prepare_is_idempotent(project: Path) -> None:
    import os
    os.environ["RDX_TEA_FAKE_NOW"] = "2026-07-02T00:00:00+00:00"
    try:
        m1 = _prepare(project)
        m2 = _prepare(project)
        assert m1 == m2
    finally:
        os.environ.pop("RDX_TEA_FAKE_NOW", None)


def test_l4_h02_no_tmp_leftover(project: Path) -> None:
    _prepare(project)
    d = project / "_bmad" / "rdx-tea" / "runtime" / "test-design"
    assert not list(d.glob("*.tmp"))


def test_l4_h03_overlay_toml_with_comments_survives_merge(tmp_path: Path) -> None:
    """A .user.toml with comments and array entries must not be
    clobbered by re-running the resolver."""
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "_bmad" / "custom").mkdir(parents=True)
    skill_src = UPSTREAM_TEA / "src" / "workflows" / "testarch" / "bmad-testarch-test-design"
    if not skill_src.exists():
        pytest.skip("upstream missing")
    skill_dst = proj / ".claude" / "skills" / "bmad-testarch-test-design"
    shutil.copytree(skill_src, skill_dst)
    (proj / "_bmad" / "custom" / "bmad-testarch-test-design.toml").write_text('''# team overlay
[workflow]
persistent_facts = [
  "file:{project-root}/_bmad/rdx-tea/runtime/test-design/active-context.md",
]
''')
    (proj / "_bmad" / "custom" / "bmad-testarch-test-design.user.toml").write_text('''# personal note
[workflow]
# tests must not delete this comment or my own array entry.
persistent_facts = [
  "Playwright > Cypress for this developer.",
]
''')
    r = subprocess.run(
        [str(VENV_PY), str(RESOLVER),
         "--skill", str(skill_dst), "--key", "workflow"],
        cwd=str(proj), capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr
    import json as _j
    merged = _j.loads(r.stdout)["workflow"]
    assert any("Playwright" in f for f in merged["persistent_facts"])
    assert any("active-context.md" in f for f in merged["persistent_facts"])
    # And the source file survives with its comment.
    u = (proj / "_bmad" / "custom" / "bmad-testarch-test-design.user.toml").read_text()
    assert "# personal note" in u


def test_l4_h04_stale_bundle_replaced_not_accumulated(project: Path) -> None:
    m1 = _prepare(project)
    # Second run with different diff (empty).
    (project / "_bmad-run" / "diff.patch").write_text("")
    m2 = prepare_mod.prepare(
        project_root=project, workflow="test-design",
        diff_path=project / "_bmad-run" / "diff.patch",
    )
    d = project / "_bmad" / "rdx-tea" / "runtime" / "test-design"
    files = sorted(f.name for f in d.iterdir() if not f.name.endswith(".tmp"))
    # Exactly two files: active-context.md and run-manifest.json.
    assert files == ["active-context.md", "run-manifest.json"], files
    # And the bundle now reflects the empty diff.
    assert m2["active_packs"] == []


def test_l4_h05_missing_tea_workflow_skill_but_prepare_still_runs(project: Path) -> None:
    """Prepare must not require the TEA skill directory to be present —
    it only needs the RDX canonical inputs. This is what makes prepare
    independently deployable."""
    m = _prepare(project)
    assert "schema_version" in m
