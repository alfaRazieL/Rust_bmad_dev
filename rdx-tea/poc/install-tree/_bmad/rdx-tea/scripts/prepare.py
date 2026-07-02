"""RDX-TEA active-context bundle preparer (D3.1 production layout).

Installed at `<project-root>/_bmad/rdx-tea/scripts/prepare.py`. Reads the
canonical adapter payload from `<install-root>/canonical/` — no dev-tree
dependency. Invoked by the wrapper (`rdx_tea_wrapper.py`) which supplies
the story / diff / tags paths, project-root, base/head SHAs and the
run identity.

Semantics:
  * Router replay uses the VENDORED `router.py` byte-copied from
    RDX v6.8.0 `rdx_validator/router.py`.
  * WORKFLOW_OBLIGATION_MATRIX applied at pack AND rule-field level:
    - pack filtering removes irrelevant packs;
    - CORE-* rules included per `core_rules` policy per workflow;
    - only allowed IR fields emitted per rule.
  * `run-manifest.json` records the identity fields the wrapper passed
    in (base_sha, head_sha, diff_digest, rdx_source_sha, tea_source_sha)
    as MANDATORY. Missing identity → prepare fails closed.
  * Bundle bytes are deterministic (sorted iteration; no wall-clock).

Emits atomically:
  * `<project-root>/_bmad/rdx-tea/runtime/<workflow>/active-context.md`
  * `<project-root>/_bmad/rdx-tea/runtime/<workflow>/run-manifest.json`
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

import rdx_parser  # noqa: E402
from obligation_matrix import (  # noqa: E402
    WORKFLOW_OBLIGATION_MATRIX,
    core_rules_allowed,
    fields_allowed,
    matrix_for,
    pack_allowed,
)
# Vendored router — see D3_1_PRODUCTION_LAYOUT_AUDIT.md.
from router import RouterRules, activated_pack_names, replay  # noqa: E402


CANONICAL_ROOT = rdx_parser.CANONICAL_ROOT


def _canonical_file(name: str) -> Path:
    """Absolute path to a canonical JSON contract."""
    if isinstance(CANONICAL_ROOT, rdx_parser._DevRootView):
        return CANONICAL_ROOT._contracts / name
    return CANONICAL_ROOT / name


class PrepareError(RuntimeError):
    pass


def _load_router() -> RouterRules:
    p = _canonical_file("router-rules.json")
    if not p.exists():
        raise PrepareError(f"canonical router-rules.json missing at {p}")
    return RouterRules.load(p)


def _read_optional(path: Path | None) -> str:
    if path is None:
        return ""
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _load_tags(path: Path | None) -> list[str]:
    if path is None or not path.exists():
        return []
    return [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]


def _select_active_rules(
    active_pack_ids: list[str],
    workflow: str,
    parsed_rules: list[dict],
) -> list[dict]:
    """Return rules that (a) match an activated pack for this workflow OR
    (b) satisfy the workflow's CORE inclusion policy — but ONLY when at
    least one pack is active. A non-Rust / non-activating diff yields
    an empty bundle to avoid injecting Rust CORE rules into unrelated
    stories."""
    if not active_pack_ids:
        return []
    out: list[dict] = []
    for r in parsed_rules:
        rid = r["rule_id"]
        if rid.startswith("CORE-"):
            if core_rules_allowed(workflow, rid):
                out.append(r)
        else:
            if r["pack_id"] in active_pack_ids and pack_allowed(workflow, r["pack_id"]):
                out.append(r)
    return out


def _rule_pretty_field(field: str) -> str:
    return field.replace("_", " ").capitalize()


def _render_bundle(
    workflow: str,
    active_rules: list[dict],
    active_pack_ids: list[str],
) -> str:
    """Render active-context.md with workflow-scoped field filtering.

    The bundle carries no RDX verdict vocabulary and no LLM-side PASS
    field (ADR-002 §5.5, D3.1 audit item 7).
    """
    allowed_fields = fields_allowed(workflow)
    lines: list[str] = []
    lines.append("---")
    lines.append(f"rdx_tea_bundle_version: 1")
    lines.append(f"workflow: {workflow}")
    lines.append("active_packs:")
    for pid in sorted(active_pack_ids):
        rules = [r["rule_id"] for r in active_rules
                 if r["pack_id"] == pid or (r["pack_id"] == "core" and pid == "core")]
        lines.append(f"  - pack_id: {pid}")
        lines.append("    rule_ids:")
        for rid in rules:
            lines.append(f"      - {rid}")
    core_rules_in_bundle = [r["rule_id"] for r in active_rules if r["rule_id"].startswith("CORE-")]
    if core_rules_in_bundle:
        lines.append("core_rules:")
        for rid in core_rules_in_bundle:
            lines.append(f"  - {rid}")
    lines.append("source_of_truth: canonical/router-rules.json + canonical/kb-sections/")
    lines.append("---")
    lines.append("")
    lines.append(f"# RDX active-context bundle for `{workflow}`")
    lines.append("")

    if not active_rules:
        lines.append("_No RDX pack activated for this story/diff and no CORE-* rule allowed. No Rust rules apply._")
        lines.append("")
        return "\n".join(lines) + "\n"

    # CORE section (only what the obligation matrix allows for this workflow).
    core_only = [r for r in active_rules if r["rule_id"].startswith("CORE-")]
    if core_only:
        lines.append("## Always-on Core rules")
        lines.append("")
        for r in core_only:
            lines.append(f"### `{r['rule_id']}` — {r['title']}")
            lines.append("")
            for f in sorted(allowed_fields):
                if f in r and r[f]:
                    lines.append(f"**{_rule_pretty_field(f)}:** {r[f]}")
                    lines.append("")

    # Pack sections.
    for pid in sorted(active_pack_ids):
        pack_rules = [r for r in active_rules if r["pack_id"] == pid]
        if not pack_rules:
            continue
        lines.append(f"## Pack `{pid}`")
        lines.append("")
        for r in pack_rules:
            lines.append(f"### `{r['rule_id']}` — {r['title']}")
            lines.append("")
            for f in sorted(allowed_fields):
                if f in r and r[f]:
                    lines.append(f"**{_rule_pretty_field(f)}:** {r[f]}")
                    lines.append("")
    return "\n".join(lines) + "\n"


def _stable_now() -> str:
    fake = os.environ.get("RDX_TEA_FAKE_NOW")
    if fake:
        return fake
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _atomic_write(target: Path, content: bytes) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_bytes(content)
    os.replace(tmp, target)


def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _canonical_snapshot_hash() -> str:
    """SHA-256 of a deterministic manifest of every canonical file."""
    if isinstance(CANONICAL_ROOT, rdx_parser._DevRootView):
        contracts_dir = CANONICAL_ROOT._contracts
        kb_dir = CANONICAL_ROOT._kb
    else:
        contracts_dir = CANONICAL_ROOT
        kb_dir = CANONICAL_ROOT / "kb-sections"
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
    return _sha256_bytes("\n".join(sorted(lines)).encode("utf-8"))


def prepare(
    project_root: Path,
    workflow: str,
    identity: dict,
    story_path: Path | None = None,
    diff_path: Path | None = None,
    tags_path: Path | None = None,
    output_root: Path | None = None,
) -> dict:
    """Prepare and atomically write the active-context bundle.

    `identity` MUST include mandatory keys — see `_MANDATORY_IDENTITY`.
    Missing key → PrepareError. This is the D3.1 fix for the D3 gap
    "identity fields optional / env-only".
    """
    missing = [k for k in _MANDATORY_IDENTITY if k not in identity or not identity[k]]
    if missing:
        raise PrepareError(f"identity missing mandatory fields: {missing}")

    router = _load_router()
    diff = _read_optional(diff_path)
    tags = _load_tags(tags_path)
    story = _read_optional(story_path)

    activations = replay(diff, router, tags)
    router_active_pack_ids = activated_pack_names(activations)
    active_pack_ids = sorted(set(router_active_pack_ids) & set(matrix_for(workflow)["packs"]))

    parsed_rules = rdx_parser.parse_all()
    active_rules = _select_active_rules(active_pack_ids, workflow, parsed_rules)

    bundle = _render_bundle(workflow, active_rules, active_pack_ids)
    bundle_bytes = bundle.encode("utf-8")
    bundle_sha256 = _sha256_bytes(bundle_bytes)

    diff_digest = hashlib.sha256(diff.encode("utf-8")).hexdigest()
    if identity.get("diff_digest") not in (diff_digest, ""):
        raise PrepareError(
            f"identity.diff_digest={identity['diff_digest'][:12]} disagrees "
            f"with computed {diff_digest[:12]} — refusing to write bundle"
        )

    output_root = output_root or (project_root / "_bmad" / "rdx-tea" / "runtime" / workflow)
    bundle_path = output_root / "active-context.md"
    manifest_path = output_root / "run-manifest.json"

    manifest = {
        "schema_version": "rdx-tea-run.v1",
        "workflow": workflow,
        "execution_mode": "sequential",
        "requested_mode": "sequential",
        "story_present": bool(story.strip()),
        "diff_present": bool(diff.strip()),
        "story_tags": tags,
        "active_packs": [
            {
                "pack_id": pid,
                "rule_ids": [r["rule_id"] for r in active_rules if r["pack_id"] == pid],
            }
            for pid in sorted(active_pack_ids)
        ],
        "core_rules": [r["rule_id"] for r in active_rules if r["rule_id"].startswith("CORE-")],
        "workflow_obligation_matrix": {
            "packs": sorted(matrix_for(workflow)["packs"]),
            "fields": sorted(fields_allowed(workflow)),
            "core_rules_policy": (
                "all" if matrix_for(workflow)["core_rules"] is True
                else (sorted(matrix_for(workflow)["core_rules"])
                      if isinstance(matrix_for(workflow)["core_rules"], (set, frozenset)) else "none")
            ),
        },
        "bundle_sha256": bundle_sha256,
        "bundle_bytes": len(bundle_bytes),
        "rdx_kb_source_hashes": rdx_parser.source_hashes(),
        "rdx_canonical_snapshot_sha256": _canonical_snapshot_hash(),
        "identity": {
            "base_sha":  identity["base_sha"],
            "head_sha":  identity["head_sha"],
            "diff_digest": diff_digest,
            "rdx_source_sha": identity["rdx_source_sha"],
            "tea_source_sha": identity["tea_source_sha"],
        },
        "prepared_at": _stable_now(),
    }

    _atomic_write(bundle_path, bundle_bytes)
    manifest_bytes = json.dumps(manifest, indent=2, sort_keys=True).encode("utf-8")
    _atomic_write(manifest_path, manifest_bytes)
    return manifest


_MANDATORY_IDENTITY = ("base_sha", "head_sha", "rdx_source_sha", "tea_source_sha")


def _identity_from_cli(args: argparse.Namespace) -> dict:
    """Build identity dict from CLI args. All four mandatory items must
    be supplied by the wrapper. `diff_digest` may be empty (prepare
    computes it and stamps it back)."""
    return {
        "base_sha":  args.base_sha or "",
        "head_sha":  args.head_sha or "",
        "diff_digest": args.diff_digest or "",
        "rdx_source_sha": args.rdx_source_sha or "",
        "tea_source_sha": args.tea_source_sha or "",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workflow", required=True)
    ap.add_argument("--project-root", required=True, type=Path)
    ap.add_argument("--story", type=Path, default=None)
    ap.add_argument("--diff", type=Path, default=None)
    ap.add_argument("--tags", type=Path, default=None)
    ap.add_argument("--output-root", type=Path, default=None)
    ap.add_argument("--base-sha", required=True)
    ap.add_argument("--head-sha", required=True)
    ap.add_argument("--diff-digest", default="")
    ap.add_argument("--rdx-source-sha", required=True)
    ap.add_argument("--tea-source-sha", required=True)
    args = ap.parse_args()
    try:
        m = prepare(
            project_root=args.project_root,
            workflow=args.workflow,
            identity=_identity_from_cli(args),
            story_path=args.story,
            diff_path=args.diff,
            tags_path=args.tags,
            output_root=args.output_root,
        )
    except PrepareError as err:
        print(f"prepare failed: {err}", file=sys.stderr)
        return 1
    except Exception as err:  # noqa: BLE001
        print(f"prepare failed: {err}", file=sys.stderr)
        return 2
    print(json.dumps(m, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
