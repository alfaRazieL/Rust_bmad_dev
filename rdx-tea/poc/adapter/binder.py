"""RDX-TEA sidecar binder (Phase E of the D3 proof).

Invoked as `workflow.on_complete` after the TEA workflow writes its
artefact. Reads:
  * `<project-root>/_bmad/rdx-tea/runtime/<workflow>/run-manifest.json`
    (written by prepare.py)
  * the TEA artefact path (from `workflow.yaml:outputs[].path` — for the
    PoC we accept it via CLI --artifact)

Writes:
  * `<tea-artifact>.rdx-tea.json` — schema `rdx-tea-run.v1` (see
    `rdx-tea/architecture/rdx-tea-run.v1.schema.json`).

The sidecar contains no trusted RDX PASS verdict from the LLM. It only
records what the prepare script already knows plus the artefact hash so
a later RDX validator can derive its verdict independently (ADR-002
§5.5).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _stable_now() -> str:
    fake = os.environ.get("RDX_TEA_FAKE_NOW")
    if fake:
        return fake
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def bind(
    project_root: Path,
    workflow: str,
    artifact: Path,
) -> dict:
    """Bind a completed TEA artefact to the prepare manifest and write
    the sidecar."""
    runtime_dir = project_root / "_bmad" / "rdx-tea" / "runtime" / workflow
    manifest_path = runtime_dir / "run-manifest.json"
    if not manifest_path.exists():
        raise SystemExit(
            f"no prepare manifest at {manifest_path} — prepare step never ran"
        )
    if not artifact.exists():
        raise SystemExit(f"artefact missing: {artifact}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_bytes = manifest_path.read_bytes()

    sidecar = {
        "schema_version": "rdx-tea-run.v1",
        "workflow": workflow,
        "execution_mode": manifest.get("execution_mode", "sequential"),
        "active_packs": manifest.get("active_packs", []),
        "artifact_path": str(artifact.resolve()),
        "artifact_sha256": _sha256(artifact),
        "prepare_manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "prepared_at": manifest.get("prepared_at", ""),
        "bound_at": _stable_now(),
        "completed": True,
    }
    # Optional identity fields — pass through from environment if
    # available.
    for env_key, field in (
        ("RDX_TEA_BASE_SHA", "base_sha"),
        ("RDX_TEA_HEAD_SHA", "head_sha"),
        ("RDX_TEA_DIFF_DIGEST", "diff_digest"),
        ("RDX_TEA_RDX_SOURCE_SHA", "rdx_source_sha"),
        ("RDX_TEA_TEA_SOURCE_SHA", "tea_source_sha"),
    ):
        v = os.environ.get(env_key)
        if v:
            sidecar[field] = v
    # projection_hash = sha256 of the bundle we wrote in prepare
    bundle_path = runtime_dir / "active-context.md"
    if bundle_path.exists():
        sidecar["projection_hash"] = _sha256(bundle_path)

    sidecar_path = artifact.with_suffix(artifact.suffix + ".rdx-tea.json")
    sidecar_bytes = json.dumps(sidecar, indent=2, sort_keys=True).encode("utf-8")
    tmp = sidecar_path.with_suffix(sidecar_path.suffix + ".tmp")
    tmp.write_bytes(sidecar_bytes)
    os.replace(tmp, sidecar_path)
    return sidecar


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workflow", required=True)
    ap.add_argument("--project-root", required=True, type=Path)
    ap.add_argument("--artifact", required=True, type=Path)
    args = ap.parse_args()
    try:
        s = bind(args.project_root, args.workflow, args.artifact)
    except SystemExit as err:
        print(str(err), file=sys.stderr)
        return 1
    print(json.dumps(s, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
