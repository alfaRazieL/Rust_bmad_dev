"""RDX-TEA active-context bundle preparer (Phase D of the D3 proof).

Invoked as `activation_steps_prepend` step from
`_bmad/custom/bmad-testarch-<workflow>.toml` per ADR-002 §5.6.

Reads:
  * `<project-root>/_bmad-run/story.md` (story text; ok if absent)
  * `<project-root>/_bmad-run/diff.patch` (unified diff of story change)
  * `<project-root>/_bmad-run/tags.txt` (one story tag per line; ok if absent)
  * canonical RDX contracts at `<rdx-repo>/tests/contracts/router-rules.json`
  * canonical RDX KB sections (via `rdx_parser.parse_all`)

Emits atomically:
  * `<project-root>/_bmad/rdx-tea/runtime/<workflow>/active-context.md`
  * `<project-root>/_bmad/rdx-tea/runtime/<workflow>/run-manifest.json`

Exit codes:
  0  ok (bundle written; may be a no-op if no packs activate)
  1  malformed input
  2  RDX Router import failure
  3  atomic write failure

Determinism:
  * inputs → identical bytes (no wallclock)
  * atomic replace via os.replace after write to sibling tmp
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
RDX_TEA_DIR = _HERE.parent.parent
REPO_ROOT = RDX_TEA_DIR.parent

# Wire RDX validator + rdx_parser onto sys.path.
sys.path.insert(0, str(REPO_ROOT / "rdx-validator"))
sys.path.insert(0, str(_HERE))

from rdx_validator.router import RouterRules, activated_pack_names, replay  # noqa: E402

import rdx_parser  # noqa: E402


CANONICAL_ROUTER_JSON = REPO_ROOT / "tests" / "contracts" / "router-rules.json"

WORKFLOW_OBLIGATION_MATRIX = {
    # per BUILDER_TEA_RECONCILIATION §3.3 + D3 prompt §5.4
    "test-design": {"async", "unsafe", "ffi", "macro", "api", "testing", "data-security-io", "db", "time-config-client"},
    "atdd":        {"async", "api", "testing"},
    "automate":    {"async", "api", "testing"},
    "test-review": {"api", "testing"},
    "nfr":         {"unsafe", "data-security-io", "perf", "db", "time-config-client", "ops"},
    "trace":       {"testing"},
    "framework":   {"cargo", "testing"},
    "ci":          {"testing", "cargo"},
}

# Rules within a pack always emit these fields into the fragment.
_FRAGMENT_FIELDS = (
    "rule", "required_reasoning", "validation", "exceptions",
    "trigger", "risk",
)


def _load_router() -> RouterRules:
    if not CANONICAL_ROUTER_JSON.exists():
        raise SystemExit(f"canonical router rules missing: {CANONICAL_ROUTER_JSON}")
    return RouterRules.load(CANONICAL_ROUTER_JSON)


def _read_optional(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _load_tags(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _select_active_rules(
    active_pack_ids: list[str],
    workflow: str,
    parsed_rules: list[dict],
) -> list[dict]:
    """Return the subset of parsed_rules whose pack_id is both active
    (per Router) AND allowed for this workflow (per obligation matrix)."""
    allowed = WORKFLOW_OBLIGATION_MATRIX.get(workflow, set())
    active_set = set(active_pack_ids) & allowed
    return [r for r in parsed_rules if r["pack_id"] in active_set]


def _render_bundle(
    workflow: str,
    story: str,
    active_rules: list[dict],
    active_pack_ids: list[str],
) -> str:
    """Render the active-context.md markdown fragment.

    The fragment contains ONLY the workflow-scoped obligations. It never
    contains an RDX verdict enum value or a Cat-1 PASS claim (prompt
    §5.5).
    """
    lines: list[str] = []
    lines.append("---")
    lines.append(f"rdx_tea_bundle_version: 1")
    lines.append(f"workflow: {workflow}")
    lines.append(f"active_packs:")
    for pid in sorted(active_pack_ids):
        rules = [r["rule_id"] for r in active_rules if r["pack_id"] == pid]
        lines.append(f"  - pack_id: {pid}")
        lines.append(f"    rule_ids:")
        for rid in rules:
            lines.append(f"      - {rid}")
    lines.append("source_of_truth: tests/contracts/router-rules.json + .claude/skills/rdx-setup/assets/kb-sections/")
    lines.append("---")
    lines.append("")
    lines.append(f"# RDX active-context bundle for `{workflow}`")
    lines.append("")
    if not active_rules:
        lines.append("_No RDX pack activated for this story/diff. No Rust rules apply._")
        lines.append("")
        return "\n".join(lines) + "\n"

    for pid in sorted(active_pack_ids):
        pack_rules = [r for r in active_rules if r["pack_id"] == pid]
        if not pack_rules:
            continue
        lines.append(f"## Pack `{pid}`")
        lines.append("")
        for r in pack_rules:
            lines.append(f"### `{r['rule_id']}` — {r['title']}")
            lines.append("")
            for field in _FRAGMENT_FIELDS:
                label = field.replace("_", " ").capitalize()
                lines.append(f"**{label}:** {r[field]}")
                lines.append("")
    return "\n".join(lines) + "\n"


def _stable_now() -> str:
    """Reproducible timestamp: from env `RDX_TEA_FAKE_NOW`, else UTC now
    truncated to whole seconds. Callers set the env in tests for
    determinism."""
    fake = os.environ.get("RDX_TEA_FAKE_NOW")
    if fake:
        return fake
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _atomic_write(target: Path, content: bytes) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_bytes(content)
    os.replace(tmp, target)


def _hash_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def prepare(
    project_root: Path,
    workflow: str,
    story_path: Path | None = None,
    diff_path: Path | None = None,
    tags_path: Path | None = None,
    output_root: Path | None = None,
) -> dict:
    """Prepare and atomically write the active-context bundle. Returns
    the machine manifest dict."""
    router = _load_router()
    story = _read_optional(story_path) if story_path else ""
    diff = _read_optional(diff_path) if diff_path else ""
    tags = _load_tags(tags_path) if tags_path else []

    activations = replay(diff, router, tags)
    router_active_pack_ids = activated_pack_names(activations)
    allowed = WORKFLOW_OBLIGATION_MATRIX.get(workflow, set())
    # Only packs that BOTH activated AND are in the workflow's obligation
    # matrix propagate into the bundle. This is what makes the bundle
    # workflow-specific (ADR-002 §5.4 obligation matrix).
    active_pack_ids = sorted(set(router_active_pack_ids) & set(allowed))

    parsed_rules = rdx_parser.parse_all()
    active_rules = _select_active_rules(active_pack_ids, workflow, parsed_rules)

    bundle = _render_bundle(workflow, story, active_rules, active_pack_ids)
    bundle_bytes = bundle.encode("utf-8")

    output_root = output_root or (project_root / "_bmad" / "rdx-tea" / "runtime" / workflow)
    bundle_path = output_root / "active-context.md"
    manifest_path = output_root / "run-manifest.json"

    manifest = {
        "schema_version": "rdx-tea-run.v1",
        "workflow": workflow,
        "execution_mode": "sequential",
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
        "workflow_obligation_matrix": sorted(WORKFLOW_OBLIGATION_MATRIX.get(workflow, [])),
        "bundle_sha256": _hash_bytes(bundle_bytes),
        "bundle_bytes": len(bundle_bytes),
        "rdx_kb_source_hashes": rdx_parser.source_hashes(),
        "rdx_router_sha256": _hash_bytes(CANONICAL_ROUTER_JSON.read_bytes()),
        "prepared_at": _stable_now(),
    }

    _atomic_write(bundle_path, bundle_bytes)
    manifest_bytes = json.dumps(manifest, indent=2, sort_keys=True).encode("utf-8")
    _atomic_write(manifest_path, manifest_bytes)
    return manifest


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workflow", required=True)
    ap.add_argument("--project-root", required=True, type=Path)
    ap.add_argument("--story", type=Path, default=None)
    ap.add_argument("--diff", type=Path, default=None)
    ap.add_argument("--tags", type=Path, default=None)
    ap.add_argument("--output-root", type=Path, default=None)
    args = ap.parse_args()
    try:
        m = prepare(
            project_root=args.project_root,
            workflow=args.workflow,
            story_path=args.story,
            diff_path=args.diff,
            tags_path=args.tags,
            output_root=args.output_root,
        )
    except Exception as err:  # noqa: BLE001
        print(f"prepare failed: {err}", file=sys.stderr)
        return 1
    print(json.dumps(m, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
