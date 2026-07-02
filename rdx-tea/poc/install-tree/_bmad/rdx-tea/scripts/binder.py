"""RDX-TEA sidecar binder (D3.1 production layout).

Called by the wrapper after every real TEA artefact is discovered. Reads
the prepare manifest, cross-checks the bundle-on-disk against
`manifest.bundle_sha256`, hashes the artefact, and writes
`<tea-artifact>.rdx-tea.json` following `rdx-tea-run.v1`.

Fails closed if:
  * prepare manifest is absent (no bundle was ever prepared → the run is
    not RDX-TEA-validated);
  * disk-bundle hash disagrees with manifest (someone tampered with the
    bundle between prepare and bind);
  * any mandatory identity field is missing from the manifest.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


class BinderError(RuntimeError):
    pass


def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _stable_now() -> str:
    fake = os.environ.get("RDX_TEA_FAKE_NOW")
    return fake or datetime.now(timezone.utc).replace(microsecond=0).isoformat()


_MANDATORY_IDENTITY = ("base_sha", "head_sha", "diff_digest",
                       "rdx_source_sha", "tea_source_sha")


def bind(
    project_root: Path,
    workflow: str,
    artifact: Path,
) -> dict:
    runtime_dir = project_root / "_bmad" / "rdx-tea" / "runtime" / workflow
    manifest_path = runtime_dir / "run-manifest.json"
    if not manifest_path.exists():
        raise BinderError(
            f"no prepare manifest at {manifest_path} — prepare step never ran"
        )
    if not artifact.exists():
        raise BinderError(f"artefact missing: {artifact}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    # Verify bundle-on-disk matches what prepare recorded.
    bundle_path = runtime_dir / "active-context.md"
    if not bundle_path.exists():
        raise BinderError(f"bundle missing at {bundle_path}")
    disk_hash = _sha256_file(bundle_path)
    expected = manifest.get("bundle_sha256")
    if not expected:
        raise BinderError("manifest missing bundle_sha256")
    if disk_hash != expected:
        raise BinderError(
            f"bundle tamper detected: disk sha256={disk_hash[:12]} vs "
            f"manifest.bundle_sha256={expected[:12]}"
        )

    identity = manifest.get("identity") or {}
    missing = [k for k in _MANDATORY_IDENTITY if not identity.get(k)]
    if missing:
        raise BinderError(f"manifest.identity missing mandatory fields: {missing}")

    sidecar = {
        "schema_version": "rdx-tea-run.v1",
        "workflow": workflow,
        "execution_mode": manifest.get("execution_mode", "sequential"),
        "active_packs": manifest.get("active_packs", []),
        "core_rules": manifest.get("core_rules", []),
        "artifact_path": str(artifact.resolve()),
        "artifact_sha256": _sha256_file(artifact),
        "prepare_manifest_sha256": _sha256_bytes(manifest_path.read_bytes()),
        "prepared_at": manifest.get("prepared_at", ""),
        "bound_at": _stable_now(),
        "completed": True,
        "base_sha": identity["base_sha"],
        "head_sha": identity["head_sha"],
        "diff_digest": identity["diff_digest"],
        "rdx_source_sha": identity["rdx_source_sha"],
        "tea_source_sha": identity["tea_source_sha"],
        "projection_hash": disk_hash,
    }
    sidecar_path = artifact.with_suffix(artifact.suffix + ".rdx-tea.json")
    tmp = sidecar_path.with_suffix(sidecar_path.suffix + ".tmp")
    tmp.write_bytes(json.dumps(sidecar, indent=2, sort_keys=True).encode("utf-8"))
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
    except BinderError as err:
        print(f"bind failed: {err}", file=sys.stderr)
        return 1
    print(json.dumps(s, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
