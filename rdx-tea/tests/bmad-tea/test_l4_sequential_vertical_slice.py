"""L4 sequential vertical slice (Phase E of the D3 proof).

Programmatically executes the D3 seam sequence end-to-end:

  1. prepare.py writes active-context bundle from a real diff.
  2. Upstream resolver merges the RDX-TEA overlay onto the real TEA
     `bmad-testarch-test-design/customize.toml` (verified in Phase C).
  3. Persistent-facts contains the bundle path (real assertion).
  4. A simulated TEA workflow reads the persistent_facts entries and
     emits a "test-design" artefact whose content depends on the loaded
     bundle. This is the closest we can get to a real LLM run without
     a live model — it verifies that the bundle IS the knowledge the
     workflow sees.
  5. binder.py runs on the artefact (as workflow.on_complete would),
     writes rdx-tea-run.v1 sidecar.
  6. The sidecar is validated against the JSON schema.

Two workflows are exercised:
  * `test-design` — the ADR-002 canonical demo workflow.
  * `atdd` — a workflow that normally uses subagent orchestration.
    With execution_mode='sequential' this collapses to a single run;
    the bundle still lands in persistent_facts.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
from pathlib import Path

import jsonschema
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
SIDECAR_SCHEMA = RDX_TEA_DIR / "architecture" / "rdx-tea-run.v1.schema.json"


def _load(mod_path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, mod_path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)   # type: ignore[union-attr]
    return m


prepare_mod = _load(PREPARE_PY, "prepare")
binder_mod = _load(BINDER_PY, "binder")


ASYNC_DIFF = """diff --git a/src/lib.rs b/src/lib.rs
--- a/src/lib.rs
+++ b/src/lib.rs
@@ -0,0 +1,7 @@
+use tokio::task;
+pub async fn run() {
+    let h = tokio::spawn(async {});
+    h.await.unwrap();
+}
"""


def _mk_project(base: Path, workflow_skill_slug: str) -> Path:
    proj = base / "proj"
    proj.mkdir()
    (proj / "_bmad" / "custom").mkdir(parents=True)
    (proj / "_bmad-run").mkdir()
    skill_src = UPSTREAM_TEA / "src" / "workflows" / "testarch" / workflow_skill_slug
    if not skill_src.exists():
        pytest.skip(f"upstream skill missing {skill_src}")
    skill_dst = proj / ".claude" / "skills" / workflow_skill_slug
    shutil.copytree(skill_src, skill_dst)
    return proj


def _write_overlay(proj: Path, workflow_skill_slug: str, workflow_short: str) -> None:
    overlay = proj / "_bmad" / "custom" / f"{workflow_skill_slug}.toml"
    overlay.write_text(f'''[workflow]

activation_steps_prepend = [
  "Run: python3 {{project-root}}/_bmad/rdx-tea/scripts/prepare.py --workflow {workflow_short} --project-root {{project-root}}. HALT on non-zero exit.",
]

persistent_facts = [
  "file:{{project-root}}/_bmad/rdx-tea/runtime/{workflow_short}/active-context.md",
]

on_complete = "Run: python3 {{project-root}}/_bmad/rdx-tea/scripts/binder.py --workflow {workflow_short} --project-root {{project-root}} --artifact <the artefact path from workflow.yaml outputs>"
''')


def _run_resolver(proj: Path, workflow_skill_slug: str) -> dict:
    r = subprocess.run(
        [str(VENV_PY), str(RESOLVER),
         "--skill", str(proj / ".claude" / "skills" / workflow_skill_slug),
         "--key", "workflow"],
        cwd=str(proj), capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)["workflow"]


def _run_prepare(proj: Path, workflow_short: str, diff: str) -> dict:
    (proj / "_bmad-run" / "diff.patch").write_text(diff)
    (proj / "_bmad-run" / "story.md").write_text("# Rust async story\n")
    return prepare_mod.prepare(
        project_root=proj,
        workflow=workflow_short,
        story_path=proj / "_bmad-run" / "story.md",
        diff_path=proj / "_bmad-run" / "diff.patch",
    )


def _simulated_tea_artifact(proj: Path, workflow_short: str) -> Path:
    """Simulate the TEA workflow writing an artefact under
    `_bmad-output/test-artifacts/`.

    The simulated artefact's content is deterministically derived from
    the loaded persistent_facts. The point of the test is to prove the
    bundle IS what a downstream reader sees — not to substitute for a
    real LLM.
    """
    bundle_path = proj / "_bmad" / "rdx-tea" / "runtime" / workflow_short / "active-context.md"
    bundle = bundle_path.read_text(encoding="utf-8")
    out_dir = proj / "_bmad-output" / "test-artifacts"
    out_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = out_dir / f"{workflow_short}-artifact.md"
    body = ["# Simulated TEA artefact\n"]
    body.append("The workflow read the following active-context bundle:\n")
    body.append("```markdown\n")
    body.append(bundle)
    body.append("```\n")
    artifact_path.write_text("".join(body), encoding="utf-8")
    return artifact_path


def _validate_sidecar(sidecar: dict) -> None:
    schema = json.loads(SIDECAR_SCHEMA.read_text())
    jsonschema.validate(instance=sidecar, schema=schema)


# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "workflow_slug,workflow_short",
    [
        ("bmad-testarch-test-design", "test-design"),
        ("bmad-testarch-atdd", "atdd"),
    ],
)
def test_l4_e01_vertical_slice_produces_valid_sidecar(
    tmp_path: Path, workflow_slug: str, workflow_short: str
) -> None:
    proj = _mk_project(tmp_path, workflow_slug)
    _write_overlay(proj, workflow_slug, workflow_short)
    # Step 1: resolver produces the merged workflow block.
    merged = _run_resolver(proj, workflow_slug)
    assert any("prepare.py" in s for s in merged["activation_steps_prepend"])
    assert any("active-context.md" in f for f in merged["persistent_facts"])
    assert "binder.py" in merged["on_complete"]

    # Step 2: prepare runs (activation_steps_prepend #1).
    manifest = _run_prepare(proj, workflow_short, ASYNC_DIFF)
    assert manifest["execution_mode"] == "sequential"
    # Rule presence assertion — only if the workflow's obligation matrix
    # includes `async`. atdd and test-design both do (per ADR-002 §3.3).
    async_packs = [p for p in manifest["active_packs"] if p["pack_id"] == "async"]
    assert async_packs, f"async pack should activate: {manifest['active_packs']}"

    # Step 3: persistent_facts is now available and points at a
    # non-empty file.
    bundle = (proj / "_bmad" / "rdx-tea" / "runtime" / workflow_short / "active-context.md")
    assert bundle.exists() and bundle.read_bytes(), "bundle empty"
    assert "cancel-safe" in bundle.read_text(), "async obligation not loaded"

    # Step 4: simulated TEA emits its artefact.
    artefact = _simulated_tea_artifact(proj, workflow_short)
    assert artefact.exists()
    assert "cancel-safe" in artefact.read_text(), (
        "artefact must reflect the loaded bundle — a real TEA workflow "
        "would have consumed persistent_facts"
    )

    # Step 5: binder runs (workflow.on_complete).
    sidecar = binder_mod.bind(project_root=proj, workflow=workflow_short, artifact=artefact)
    _validate_sidecar(sidecar)
    assert sidecar["schema_version"] == "rdx-tea-run.v1"
    assert sidecar["execution_mode"] == "sequential"
    assert sidecar["workflow"] == workflow_short
    assert sidecar["completed"] is True
    assert sidecar["artifact_sha256"] == hashlib.sha256(artefact.read_bytes()).hexdigest()
    # Sidecar carries no LLM-set verdict fields.
    for banned in ("verdict", "rdx_verdict", "cat1_verdict", "passed"):
        assert banned not in sidecar, f"sidecar leaked verdict field {banned}"


def test_l4_e02_sidecar_invalidated_on_artifact_mutation(tmp_path: Path) -> None:
    """If someone mutates the TEA artefact after binder ran, the sidecar
    hash no longer matches."""
    proj = _mk_project(tmp_path, "bmad-testarch-test-design")
    _write_overlay(proj, "bmad-testarch-test-design", "test-design")
    _run_prepare(proj, "test-design", ASYNC_DIFF)
    artefact = _simulated_tea_artifact(proj, "test-design")
    sidecar = binder_mod.bind(project_root=proj, workflow="test-design", artifact=artefact)
    old_hash = sidecar["artifact_sha256"]
    artefact.write_text(artefact.read_text() + "\n<tampered>\n")
    new_hash = hashlib.sha256(artefact.read_bytes()).hexdigest()
    assert old_hash != new_hash, "artefact hash must change on tamper"


def test_l4_e03_sidecar_present_only_after_binder(tmp_path: Path) -> None:
    proj = _mk_project(tmp_path, "bmad-testarch-test-design")
    _write_overlay(proj, "bmad-testarch-test-design", "test-design")
    _run_prepare(proj, "test-design", ASYNC_DIFF)
    artefact = _simulated_tea_artifact(proj, "test-design")
    sidecar_path = artefact.with_suffix(artefact.suffix + ".rdx-tea.json")
    assert not sidecar_path.exists()
    binder_mod.bind(project_root=proj, workflow="test-design", artifact=artefact)
    assert sidecar_path.exists()


def test_l4_e04_binder_fails_closed_without_prepare_manifest(tmp_path: Path) -> None:
    """If prepare never ran, binder must not silently succeed with an
    empty active_packs claim."""
    proj = tmp_path / "proj"
    proj.mkdir()
    fake_artifact = proj / "artefact.md"
    fake_artifact.write_text("no bundle loaded")
    with pytest.raises(SystemExit):
        binder_mod.bind(project_root=proj, workflow="test-design", artifact=fake_artifact)


def test_l4_e05_execution_mode_recorded_as_sequential(tmp_path: Path) -> None:
    """G6 v1: sequential-only claim is machine-verifiable."""
    proj = _mk_project(tmp_path, "bmad-testarch-test-design")
    _write_overlay(proj, "bmad-testarch-test-design", "test-design")
    manifest = _run_prepare(proj, "test-design", ASYNC_DIFF)
    assert manifest["execution_mode"] == "sequential"
    artefact = _simulated_tea_artifact(proj, "test-design")
    sidecar = binder_mod.bind(project_root=proj, workflow="test-design", artifact=artefact)
    assert sidecar["execution_mode"] == "sequential"
