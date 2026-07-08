"""L1 W5 — binder sidecar: one-per-artefact, bundle-tamper, boundary.

Focused unit coverage for the W5 binder invariants (G-W5-SIDECAR):

  * exactly one sidecar per real artefact, next to the artefact, even when
    the child wrote under nested output roots (dedupe by resolved real path);
  * bundle-tamper fails closed — the binder recomputes
    sha256(active-context.md) and refuses if it disagrees with
    manifest.bundle_sha256;
  * artefact boundary fails closed on path-traversal / outside-project.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

RDX_TEA_DIR = Path(__file__).resolve().parent.parent.parent
SCRIPTS = RDX_TEA_DIR / "poc" / "install-tree" / "_bmad" / "rdx-tea" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import binder  # noqa: E402
import rdx_tea_wrapper as w  # noqa: E402

_IDENTITY = {
    "base_sha": "a" * 40,
    "head_sha": "b" * 40,
    "diff_digest": "c" * 64,
    "rdx_source_sha": "d" * 40,
    "tea_source_sha": "e" * 40,
}


def _prepare_runtime(project_root: Path, run_id: str, bundle_text: str) -> Path:
    """Write a minimal prepared runtime dir (bundle + manifest) the way
    prepare.py would, so binder.bind has an honest manifest to verify."""
    runtime = project_root / "_bmad" / "rdx-tea" / "runtime" / "test-design" / run_id
    runtime.mkdir(parents=True, exist_ok=True)
    bundle = runtime / "active-context.md"
    bundle.write_text(bundle_text, encoding="utf-8")
    bundle_sha = hashlib.sha256(bundle.read_bytes()).hexdigest()
    manifest = {
        "schema_version": "rdx-tea-run.v1",
        "workflow": "test-design",
        "run_id": run_id,
        "bundle_sha256": bundle_sha,
        "identity": dict(_IDENTITY),
        "rust_scope": True,
        "execution_mode": "sequential",
        "active_packs": [],
        "core_rules": [],
        "prepared_at": "2026-01-01T00:00:00+00:00",
    }
    (runtime / "run-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return runtime


def test_w5_one_sidecar_per_artefact_across_nested_roots(tmp_path):
    """A single artefact under a nested output root is discovered once and
    binds exactly one sidecar next to it — never a duplicate under the
    parent root."""
    proj = tmp_path / "proj"
    of = proj / "_bmad-output"
    ta = of / "test-artifacts"
    ta.mkdir(parents=True)
    art = ta / "plan.md"
    art.write_text("# plan\n", encoding="utf-8")
    _prepare_runtime(proj, "sc-01", "bundle body\n")

    # Nested roots collapse; the artefact is deduped to a single Path.
    delta = w._delta_outputs({}, [ta, of])
    assert len(delta) == 1

    binder.bind(project_root=proj, workflow="test-design", artifact=delta[0],
                run_id="sc-01", declared_output_roots=[ta, of])

    sidecars = list(of.rglob("*.rdx-tea.json"))
    assert len(sidecars) == 1, f"expected one sidecar, got {sidecars}"
    assert sidecars[0] == art.with_suffix(art.suffix + ".rdx-tea.json")


def test_w5_binder_bundle_tamper_fails_closed(tmp_path):
    """Mutating active-context.md after prepare makes the disk hash disagree
    with manifest.bundle_sha256 → the binder refuses (fail-closed)."""
    proj = tmp_path / "proj"
    ta = proj / "_bmad-output" / "test-artifacts"
    ta.mkdir(parents=True)
    art = ta / "plan.md"
    art.write_text("# plan\n", encoding="utf-8")
    runtime = _prepare_runtime(proj, "tamper-01", "original bundle\n")

    # Tamper: rewrite the bundle after the manifest recorded its hash.
    (runtime / "active-context.md").write_text("TAMPERED\n", encoding="utf-8")

    with pytest.raises(binder.BinderError, match="tamper"):
        binder.bind(project_root=proj, workflow="test-design", artifact=art,
                    run_id="tamper-01")
    # No sidecar written on a tampered bundle.
    assert not (art.with_suffix(art.suffix + ".rdx-tea.json")).exists()


def test_w5_binder_rejects_path_traversal_outside_project(tmp_path):
    """A `..`-traversal artefact path that resolves outside the project root
    fails closed before any sidecar write."""
    proj = tmp_path / "proj"
    ta = proj / "_bmad-output" / "test-artifacts"
    ta.mkdir(parents=True)
    _prepare_runtime(proj, "trav-01", "bundle\n")
    outside = tmp_path / "outside.md"
    outside.write_text("x", encoding="utf-8")
    traversal = ta / ".." / ".." / ".." / "outside.md"

    with pytest.raises(binder.BinderError, match="outside project-root"):
        binder.bind(project_root=proj, workflow="test-design",
                    artifact=traversal, run_id="trav-01")
