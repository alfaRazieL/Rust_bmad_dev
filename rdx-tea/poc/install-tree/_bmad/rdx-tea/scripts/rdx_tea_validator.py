"""RDX-TEA verifier (D3.2).

Integrity behavioural eval. Not the production enforcement verdict —
that will be the `rdx-tea-validate` subcommand in `rdx-validator/rdx_tea`
once G7 closes and Stage-03 of the D3 proof plan runs.

`verify()` returns a dict describing every check and its outcome. The
CLI wrapper (`--sidecar`) still exits non-zero on any FAIL — the
`verify()` return value carries per-check status so behavioural evals
can compare arms.

Checks performed:

  * schema:                sidecar validates against rdx-tea-run.v1
  * manifest_hash:         prepare_manifest_sha256 matches manifest on disk
  * bundle_hash:           projection_hash matches active-context.md on disk
  * artifact_hash:         artifact_sha256 matches artefact bytes
  * base_head_exist:       both SHAs resolve via git cat-file
  * diff_digest_recomputed: SHA-256(diff.patch) matches sidecar.diff_digest
  * canonical_snapshot:    manifest.rdx_canonical_snapshot_sha256 matches recompute
  * source_lock:           rdx_source_sha and tea_source_sha match sources.lock
  * artifact_boundary:     artefact is inside project-root, not a symlink,
                           and not writing outside the declared output dirs

Every check reports {name, status, detail}.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import yaml

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

import rdx_parser  # noqa: E402


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


def _git_cat_file_exists(project_root: Path, sha: str) -> bool:
    try:
        r = subprocess.run(
            ["git", "-C", str(project_root), "cat-file", "-e", sha],
            capture_output=True, text=True, check=False,
        )
        return r.returncode == 0
    except FileNotFoundError:
        return False


def _canonical_snapshot_hash() -> str:
    root = rdx_parser.CANONICAL_ROOT
    if isinstance(root, rdx_parser._DevRootView):
        contracts_dir = root._contracts
        kb_dir = root._kb
    else:
        contracts_dir = root
        kb_dir = root / "kb-sections"
    lines: list[str] = []
    for src in [
        contracts_dir / "router-rules.json",
        contracts_dir / "status-definitions.json",
        contracts_dir / "rule-check-map.json",
        contracts_dir / "authority-matrix.json",
        kb_dir / "section-4-core.md",
        kb_dir / "section-6-packs.md",
        kb_dir / "section-8-governance.md",
    ]:
        if src.exists():
            lines.append(f"{src.name} {_sha256_file(src)}")
    return hashlib.sha256("\n".join(sorted(lines)).encode("utf-8")).hexdigest()


def _record(checks: list[dict], name: str, ok: bool, detail: str = "") -> None:
    checks.append({"check": name, "status": "PASS" if ok else "FAIL", "detail": detail})


def verify(
    *,
    sidecar_path: Path,
    project_root: Path | None = None,
    workflow: str | None = None,
    run_id: str | None = None,
    source_lock_path: Path | None = None,
    artifact_path: Path | None = None,
) -> dict:
    checks: list[dict] = []
    if not sidecar_path.exists():
        raise ValidatorError(f"sidecar missing: {sidecar_path}")
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))

    # 1) schema — bundled with install-tree canonical/, with a dev-tree
    # fallback for tests running inside the RDX repo.
    import jsonschema
    schema_candidates = [
        _HERE.parent / "canonical" / "rdx-tea-run.v1.schema.json",
        _HERE.parent.parent.parent.parent / "rdx-tea" / "architecture" / "rdx-tea-run.v1.schema.json",
    ]
    schema_path = next((c for c in schema_candidates if c.exists()), schema_candidates[0])
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        jsonschema.validate(instance=sidecar, schema=schema)
        _record(checks, "schema", True)
    except FileNotFoundError:
        _record(checks, "schema", False, f"schema file missing at {schema_path}")
    except jsonschema.ValidationError as err:
        _record(checks, "schema", False, str(err.message))

    workflow = workflow or sidecar["workflow"]
    run_id = run_id or sidecar.get("run_id", "")
    if project_root is None:
        # Recover project_root from artifact_path assumption:
        # <project-root>/_bmad-output/... or from a caller-supplied
        # artifact_path.
        artifact = artifact_path or Path(sidecar["artifact_path"])
        # Walk up to find `_bmad/`.
        p = artifact.parent
        for _ in range(8):
            if (p / "_bmad" / "rdx-tea").exists():
                project_root = p
                break
            p = p.parent
    if project_root is None:
        project_root = Path.cwd()

    runtime_dir = project_root / "_bmad" / "rdx-tea" / "runtime" / workflow / run_id
    manifest_path = runtime_dir / "run-manifest.json"

    # 2) manifest_hash
    if manifest_path.exists():
        actual = _sha256_file(manifest_path)
        _record(checks, "manifest_hash",
                actual == sidecar["prepare_manifest_sha256"],
                f"disk={actual[:12]} sidecar={sidecar['prepare_manifest_sha256'][:12]}")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    else:
        _record(checks, "manifest_hash", False, f"manifest missing at {manifest_path}")
        manifest = {}

    # 3) bundle_hash
    bundle_path = runtime_dir / "active-context.md"
    if bundle_path.exists():
        actual = _sha256_file(bundle_path)
        _record(checks, "bundle_hash", actual == sidecar["projection_hash"],
                f"disk={actual[:12]} sidecar={sidecar['projection_hash'][:12]}")
    else:
        _record(checks, "bundle_hash", False, "active-context.md missing")

    # 4) artifact_hash
    artifact = artifact_path or Path(sidecar["artifact_path"])
    if artifact.exists():
        actual = _sha256_file(artifact)
        _record(checks, "artifact_hash", actual == sidecar["artifact_sha256"])
    else:
        _record(checks, "artifact_hash", False, f"artefact missing: {artifact}")

    # 5) base_head_exist (git)
    base_ok = _git_cat_file_exists(project_root, sidecar["base_sha"])
    head_ok = _git_cat_file_exists(project_root, sidecar["head_sha"])
    _record(checks, "base_head_exist", base_ok and head_ok,
            f"base_ok={base_ok} head_ok={head_ok}")

    # 6) diff_digest_recomputed
    diff_path = runtime_dir / "diff.patch"
    if diff_path.exists():
        recomputed = hashlib.sha256(diff_path.read_bytes()).hexdigest()
        _record(checks, "diff_digest_recomputed",
                recomputed == sidecar["diff_digest"],
                f"disk={recomputed[:12]} sidecar={sidecar['diff_digest'][:12]}")
    else:
        _record(checks, "diff_digest_recomputed", False, "diff.patch missing")

    # 7) canonical_snapshot
    cur_snap = _canonical_snapshot_hash()
    manifest_snap = manifest.get("rdx_canonical_snapshot_sha256", "")
    _record(checks, "canonical_snapshot",
            manifest_snap == cur_snap,
            f"manifest={manifest_snap[:12]} current={cur_snap[:12]}")

    # 8) source_lock
    lock_ok = True
    detail = ""
    if source_lock_path and source_lock_path.exists():
        lock = yaml.safe_load(source_lock_path.read_text(encoding="utf-8")) or {}
        for key in ("rdx_source_sha", "tea_source_sha"):
            if sidecar.get(key) != lock.get(key):
                lock_ok = False
                detail += f"{key}: sidecar={sidecar.get(key,'')[:12]} lock={lock.get(key,'')[:12]}; "
        _record(checks, "source_lock", lock_ok, detail)
    else:
        _record(checks, "source_lock", False, "sources.lock missing")

    # 9) artifact_boundary
    try:
        art_resolved = artifact.resolve()
        proj_resolved = project_root.resolve()
        art_resolved.relative_to(proj_resolved)
        boundary_ok = True
        detail = ""
    except ValueError:
        boundary_ok = False
        detail = "artefact outside project-root"
    if artifact.is_symlink():
        boundary_ok = False
        detail = "artefact is a symlink"
    _record(checks, "artifact_boundary", boundary_ok, detail)

    failed = [c["check"] for c in checks if c["status"] == "FAIL"]
    return {
        "sidecar": str(sidecar_path),
        "workflow": workflow,
        "run_id": run_id,
        "checks": checks,
        "verdict": "PASS" if not failed else "FAIL",
        "failed_checks": failed,
    }


# Backwards-compatible thin `validate()` for the D3.1 signature.
def validate(sidecar_path: Path, artifact_path: Path | None = None) -> dict:
    """Legacy D3.1 entry-point. Prefer `verify()` for D3.2."""
    r = verify(sidecar_path=sidecar_path, artifact_path=artifact_path)
    if r["verdict"] != "PASS":
        raise ValidatorError(
            f"sidecar failed checks: {r['failed_checks']}"
        )
    return r


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sidecar", required=True, type=Path)
    ap.add_argument("--artifact", type=Path, default=None)
    ap.add_argument("--project-root", type=Path, default=None)
    ap.add_argument("--workflow", default=None)
    ap.add_argument("--run-id", default=None)
    ap.add_argument("--source-lock", type=Path, default=None)
    args = ap.parse_args()
    try:
        r = verify(
            sidecar_path=args.sidecar, artifact_path=args.artifact,
            project_root=args.project_root, workflow=args.workflow,
            run_id=args.run_id, source_lock_path=args.source_lock,
        )
    except (ValidatorError, FileNotFoundError) as err:
        print(f"verify failed: {err}", file=sys.stderr)
        return 1
    print(json.dumps(r, indent=2, sort_keys=True))
    return 0 if r["verdict"] == "PASS" else 2


if __name__ == "__main__":
    sys.exit(main())
