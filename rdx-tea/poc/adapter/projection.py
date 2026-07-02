"""RDX → TEA projection generator (PoC).

Reads the canonical RDX contract files hashed in
`rdx-tea/research/SOURCE_LOCK.md §5` and emits:

  * a per-pack knowledge fragment file under `rdx-tea/poc/projections/knowledge/`
  * an index CSV `rdx-tea/poc/projections/rdx-tea-index.csv`
    mirroring the BMAD `tea-index.csv` schema
    (`id,name,description,tags,tier,fragment_file`).

Deterministic: same inputs → identical bytes. No wall-clock or randomness.

This is the PoC generator that turns the RED L0 projection tests green.
It is deliberately minimal (~120 lines of logic). A production generator
would add per-workflow filtering, tier classification, and richer front-matter.
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path

# Locate the RDX repo root using rdx-tea/'s known position.
_HERE = Path(__file__).resolve().parent                # rdx-tea/poc/adapter
RDX_TEA_DIR = _HERE.parent.parent                      # rdx-tea/
REPO_ROOT = RDX_TEA_DIR.parent                         # RDX repo root
CONTRACTS = REPO_ROOT / "tests" / "contracts"
KB_SECTIONS = REPO_ROOT / ".claude" / "skills" / "rdx-setup" / "assets" / "kb-sections"

CANONICAL_INPUTS: list[Path] = [
    CONTRACTS / "router-rules.json",
    CONTRACTS / "status-definitions.json",
    CONTRACTS / "rule-check-map.json",
    CONTRACTS / "authority-matrix.json",
    KB_SECTIONS / "section-4-core.md",
    KB_SECTIONS / "section-5-router.md",
    KB_SECTIONS / "section-6-packs.md",
    KB_SECTIONS / "section-8-governance.md",
]


def _load_router() -> dict:
    return json.loads((CONTRACTS / "router-rules.json").read_text(encoding="utf-8"))


def _load_status() -> dict:
    return json.loads((CONTRACTS / "status-definitions.json").read_text(encoding="utf-8"))


def _tier_for(pack_meta: dict) -> str:
    """Deterministic tier classification.

    Rules (source: prompt §8, plus TEA convention in `tea-index.csv`):
      * STRONG + AUTO_ACTIVATE  → 'core'        (unconditional, high confidence)
      * MEDIUM                  → 'extended'    (opt-in or auto-suggest)
      * WEAK                    → 'specialized' (STORY_TAG_REQUIRED, weak signal)
    """
    conf = pack_meta.get("confidence_class", "MEDIUM")
    if conf == "STRONG":
        return "core"
    if conf == "MEDIUM":
        return "extended"
    return "specialized"


def _render_pack_fragment(pack_name: str, pack: dict, status_verdicts: list[str]) -> str:
    """Render one Rust-testing knowledge fragment for a single Router pack.

    The fragment is deterministic — no timestamp, no author, no run counter.
    The content is what a TEA workflow needs to know to design tests for the
    pack: activation signals, related RDX rule IDs, validation family, and
    escalation triggers.
    """
    lines = [
        "---",
        f"pack_id: {pack_name}",
        f"kb_section: {pack.get('kb_section', '')}",
        f"confidence_class: {pack.get('confidence_class', '')}",
        f"activation_policy: {pack.get('activation_policy', '')}",
        "source_of_truth: tests/contracts/router-rules.json",
        "---",
        "",
        f"# Rust risk pack: {pack.get('label', pack_name)}",
        "",
        "## When this pack activates",
        "",
        f"* Confidence: `{pack.get('confidence_class', '')}`",
        f"* Policy: `{pack.get('activation_policy', '')}`",
        "",
        "### Positive signals (in diff/file):",
    ]
    for s in pack.get("positive_signals", []):
        lines.append(f"* `{s}`")
    lines.append("")
    lines.append("### Negative signals (suppress activation):")
    for s in pack.get("negative_signals", []):
        lines.append(f"* {s}")
    lines.append("")
    lines.append("### Path signals:")
    for s in pack.get("path_signals", []):
        lines.append(f"* `{s}`")
    lines.append("")

    lines.append("## Escalation triggers (require specialist review)")
    for s in pack.get("escalation_triggers", []):
        lines.append(f"* {s}")
    lines.append("")

    lines.append("## Related canonical rule IDs")
    lines.append("")
    lines.append("Every rule ID below is defined by the RDX KB and MUST NOT be renamed by any downstream consumer:")
    lines.append("")
    for rid in pack.get("related_rule_ids", []):
        lines.append(f"* `{rid}`")
    lines.append("")

    lines.append("## Validation families the pack recommends")
    lines.append("")
    for s in pack.get("validation_family", []):
        lines.append(f"* {s}")
    lines.append("")

    lines.append("## Verdict vocabulary (from RDX canonical status)")
    lines.append("")
    lines.append(
        "The following verdicts are the ONLY strings allowed in an rdx-evidence.v1 envelope "
        "and MUST also be used by any TEA-side artefact that participates in the same verdict trail:"
    )
    lines.append("")
    for v in sorted(status_verdicts):
        lines.append(f"* `{v}`")
    lines.append("")

    lines.append("## Contract for TEA workflows using this fragment")
    lines.append("")
    lines.append(
        "1. If the story description or diff matches the positive signals above and no "
        "negative signal or `story_tag` suppression applies, add this pack's `related_rule_ids` "
        "to the `active_packs[].rule_ids` field of the test-design artefact."
    )
    lines.append(
        "2. Do NOT paraphrase a rule ID. IDs are strings, not descriptions."
    )
    lines.append(
        "3. Emit the resulting artefact using verdict strings from the vocabulary above."
    )
    lines.append("")

    return "\n".join(lines)


def render_all() -> dict[str, bytes]:
    """Deterministic bulk rendering.

    Returns a dict mapping *relative* fragment paths (POSIX, str) to their
    raw UTF-8 bytes. The index CSV is included under the key
    `rdx-tea-index.csv`.
    """
    router = _load_router()
    status = _load_status()
    verdicts = sorted(status["verdicts"].keys())

    out: dict[str, bytes] = {}

    for pack_name in sorted(router["packs"].keys()):
        pack = router["packs"][pack_name]
        fragment = _render_pack_fragment(pack_name, pack, verdicts)
        rel_path = f"knowledge/rdx-tea-{pack_name}.md"
        out[rel_path] = fragment.encode("utf-8")

    out["rdx-tea-index.csv"] = render_index_csv().encode("utf-8")
    return out


def render_index_csv() -> str:
    """Render an `rdx-tea-index.csv` mirroring the TEA `tea-index.csv` schema.

    Header: `id,name,description,tags,tier,fragment_file`
    Deterministic ordering: packs sorted alphabetically.
    """
    router = _load_router()
    buf = io.StringIO(newline="")
    writer = csv.writer(buf, quoting=csv.QUOTE_MINIMAL)
    writer.writerow(["id", "name", "description", "tags", "tier", "fragment_file"])
    for pack_name in sorted(router["packs"].keys()):
        pack = router["packs"][pack_name]
        rid = f"rdx-tea-{pack_name}"
        name = pack.get("label", pack_name)
        description = (
            f"RDX projection for Rust risk pack '{pack_name}' — "
            f"activation={pack.get('activation_policy','')}, "
            f"confidence={pack.get('confidence_class','')}"
        )
        # Tags include the pack name, canonical prefix, and confidence class
        # so TEA workflows can select fragments by tag matching.
        tags = ";".join([pack_name, "rdx", "rust", pack.get("confidence_class", "MEDIUM").lower()])
        tier = _tier_for(pack)
        fragment_file = f"knowledge/rdx-tea-{pack_name}.md"
        writer.writerow([rid, name, description, tags, tier, fragment_file])
    return buf.getvalue()


def emit_to_disk(dest: Path | None = None) -> Path:
    """Write render_all() output to `dest` (default: rdx-tea/poc/projections/).

    Overwrites existing files atomically enough for PoC purposes.
    """
    dest = dest or (RDX_TEA_DIR / "poc" / "projections")
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "knowledge").mkdir(parents=True, exist_ok=True)
    for rel, blob in render_all().items():
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(blob)
    return dest


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="RDX → TEA projection generator (PoC)")
    parser.add_argument("--emit", action="store_true", help="write projections to disk")
    parser.add_argument("--dest", type=Path, default=None)
    args = parser.parse_args()
    if args.emit:
        dest = emit_to_disk(args.dest)
        print(f"emitted → {dest}")
    else:
        out = render_all()
        for k, v in out.items():
            print(f"{k}: {len(v)} bytes")


if __name__ == "__main__":
    main()
