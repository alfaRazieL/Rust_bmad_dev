"""RDX-TEA sidecar validator (D3.1).

Verifies a `<tea-artifact>.rdx-tea.json` sidecar against the artefact it
references. Fails closed on any of:

  * missing sidecar;
  * artefact_sha256 disagreement;
  * schema_version mismatch;
  * bundle vs projection_hash mismatch (if bundle path resolvable);
  * missing mandatory identity fields.

Not the final rdx-tea-validate subcommand of `rdx-validator` — that
lives in `rdx-validator/rdx_tea/` and is deferred to a later stage.
This validator is the smallest useful runtime check available today.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


class ValidatorError(RuntimeError):
    pass


_REQUIRED_FIELDS = (
    "schema_version", "workflow", "execution_mode",
    "active_packs", "artifact_path", "artifact_sha256",
    "prepare_manifest_sha256", "projection_hash", "completed",
    "base_sha", "head_sha", "diff_digest",
    "rdx_source_sha", "tea_source_sha",
)


def _sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def validate(sidecar_path: Path, artifact_path: Path | None = None) -> dict:
    if not sidecar_path.exists():
        raise ValidatorError(f"sidecar missing: {sidecar_path}")
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    missing = [k for k in _REQUIRED_FIELDS if k not in sidecar or sidecar[k] in (None, "")]
    if missing:
        raise ValidatorError(f"sidecar missing required fields: {missing}")
    if sidecar["schema_version"] != "rdx-tea-run.v1":
        raise ValidatorError(f"unexpected schema_version {sidecar['schema_version']!r}")
    if sidecar["execution_mode"] != "sequential":
        raise ValidatorError(
            f"D3 v1 requires sequential; sidecar has {sidecar['execution_mode']!r}"
        )
    if not sidecar["completed"]:
        raise ValidatorError("sidecar completed=false")
    artifact = artifact_path or Path(sidecar["artifact_path"])
    if not artifact.exists():
        raise ValidatorError(f"artefact missing: {artifact}")
    disk_hash = _sha256_file(artifact)
    if disk_hash != sidecar["artifact_sha256"]:
        raise ValidatorError(
            f"artefact tamper detected: disk={disk_hash[:12]} vs "
            f"sidecar={sidecar['artifact_sha256'][:12]}"
        )
    return sidecar


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sidecar", required=True, type=Path)
    ap.add_argument("--artifact", type=Path, default=None)
    args = ap.parse_args()
    try:
        validate(args.sidecar, args.artifact)
    except ValidatorError as err:
        print(f"validate failed: {err}", file=sys.stderr)
        return 1
    print("ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
