"""RDX-TEA workspace delta + artifact consistency (D3.4.0 section 7-8).

Shipped-surface re-implementation of the D3.4.0 rule-operation reference
(the eval-plane `rule_operation.py`, which is NOT installed into a user
project). This module is a clean, self-contained re-implementation: the
production runtime imports no eval-plane module and references no research-
plane path, per the production/eval split (G-SPLIT-IMPORT). Determinism
only — no LLM, no wall-clock, no random, sorted iteration.

Two responsibilities, both judged against REALITY (the real workspace delta
and the real files on disk), so an honest candidate can pass while a
dishonest one fails closed:

  collect_workspace_delta(project_root, new_artefacts, ...)
      The post-run delta computed by the wrapper (`_delta_outputs`): the
      created / modified files under the canonical output roots, with
      sha256 hashes, plus the files the TEA artefact frontmatter DECLARES
      it generated and which of those actually exist.

  workspace_delta_consistency(delta)
      FAIL if a declared generated file is missing AND the run did not mark
      it planned-but-not-generated (§7.2). Otherwise PASS.

  check_artifact_consistency(artifact_paths, project_root, delta)
      Deterministic detectors. Hard failures (fail-closed): frontmatter that
      contradicts reality, declared paths that escape the project root, and
      phantom file claims (declared-generated files that exist neither on
      disk nor in the delta). Duplicate frontmatter keys and duplicate story
      metadata are recorded as WARNINGS, never failures by themselves.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path


# Frontmatter keys that name files the workflow claims to have generated.
_DECLARED_FILE_KEYS = (
    "generatedTestFiles",
    "generatedFiles",
    "modifiedFiles",
    "createdFiles",
)
# Frontmatter key that, when present and true, marks a declaration as
# planned-but-not-generated (the precommitted escape hatch, §7.2).
_PLANNED_FLAG_KEY = "declarationPlannedNotGenerated"

# Story-metadata keys whose distinct duplication is a warning-level smell.
_STORY_META_KEYS = ("storyId", "storyKey", "lastStep")


def _sha256_file(p: Path) -> str:
    return (hashlib.sha256(p.read_bytes()).hexdigest()
            if p.exists() and p.is_file() else "")


# ------------------------------------------------------- frontmatter parse

def _extract_frontmatter_blocks(text: str) -> list[str]:
    """Return every YAML frontmatter block delimited by `---` lines. TEA
    checklists can carry more than one (a real defect we want to detect),
    so we return ALL paired `---` fences, not just the leading block."""
    lines = text.splitlines()
    fence_idx = [n for n, ln in enumerate(lines) if ln.strip() == "---"]
    blocks: list[str] = []
    for a, b in zip(fence_idx[0::2], fence_idx[1::2]):
        blocks.append("\n".join(lines[a + 1:b]))
    return blocks


def _parse_frontmatter_keys(block: str) -> list[tuple[str, str]]:
    """Return (key, raw_value) pairs in order, WITHOUT collapsing
    duplicates (so duplicates are detectable). Block list values that span
    indented `-` lines are captured as a joined `[a, b]` raw string."""
    pairs: list[tuple[str, str]] = []
    lines = block.splitlines()
    key_re = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*):(.*)$")
    i = 0
    while i < len(lines):
        m = key_re.match(lines[i])
        if not m:
            i += 1
            continue
        key, inline = m.group(1), m.group(2).strip()
        if inline:
            pairs.append((key, inline))
            i += 1
            continue
        # Possibly a block list on following indented `-` lines.
        j = i + 1
        collected: list[str] = []
        while j < len(lines) and (lines[j].startswith((" ", "\t"))
                                  and lines[j].strip().startswith("-")):
            collected.append(lines[j].strip().lstrip("-").strip().strip("'\""))
            j += 1
        pairs.append((key, "[" + ", ".join(collected) + "]"))
        i = j if j > i + 1 else i + 1
    return pairs


def _values_for_key(pairs: list[tuple[str, str]], key: str) -> list[str]:
    return [v for k, v in pairs if k == key]


def _parse_list_value(raw: str) -> list[str]:
    """Parse an inline `[a, b]` or empty `[]` value into a list of file
    paths. A bare scalar becomes a single-element list."""
    raw = raw.strip()
    if raw in ("[]", "[ ]", ""):
        return []
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1].strip()
        if not inner:
            return []
        return [x.strip().strip("'\"") for x in inner.split(",") if x.strip()]
    return [raw.strip().strip("'\"")]


def parse_declared_files(artifact_paths: list[Path]) -> tuple[set[str], bool]:
    """Union of declared generated files across every artefact's
    frontmatter, and whether any block set the planned-not-generated flag."""
    declared: set[str] = set()
    planned = False
    for ap in artifact_paths or []:
        if not ap.exists():
            continue
        text = ap.read_text(encoding="utf-8", errors="replace")
        for block in _extract_frontmatter_blocks(text):
            pairs = _parse_frontmatter_keys(block)
            for key in _DECLARED_FILE_KEYS:
                for raw in _values_for_key(pairs, key):
                    for f in _parse_list_value(raw):
                        if f:
                            declared.add(f)
            for raw in _values_for_key(pairs, _PLANNED_FLAG_KEY):
                if raw.strip().lower() in ("true", "yes", "1"):
                    planned = True
    return declared, planned


# ------------------------------------------------------- workspace delta

def _rel(project_root: Path, p: Path) -> str:
    """Project-relative POSIX path for a delta artefact. Falls back to the
    resolved absolute path if the artefact is not under the project root
    (the binder boundary already rejects that case before finalize)."""
    try:
        return p.resolve().relative_to(project_root.resolve()).as_posix()
    except ValueError:
        return p.resolve().as_posix()


def collect_workspace_delta(
    project_root: Path,
    new_artefacts: list[Path],
    artifact_paths: list[Path] | None = None,
    pre_snapshot: dict | None = None,
) -> dict:
    """D3.4.0 §7. Post-run delta of the real workspace.

    `new_artefacts` is the wrapper's `_delta_outputs` result (new-or-changed
    files under the canonical output roots, deduped by resolved real path).
    `pre_snapshot` (optional, `{resolved_abs_path: sha256}`) classifies each
    delta artefact as created (absent before) or modified (present before).
    `artifact_paths` supplies the frontmatter to parse (defaults to
    `new_artefacts`)."""
    pre = pre_snapshot or {}
    created: list[str] = []
    modified: list[str] = []
    hashes: dict[str, str] = {}
    for p in new_artefacts:
        rel = _rel(project_root, p)
        key = str(p.resolve())
        if key in pre:
            modified.append(rel)
        else:
            created.append(rel)
        h = _sha256_file(p)
        if h:
            hashes[rel] = h
    created = sorted(set(created))
    modified = sorted(set(modified))

    declared, planned = parse_declared_files(
        artifact_paths if artifact_paths is not None else new_artefacts)

    declared_existing = sorted(
        f for f in declared if (project_root / f).exists())
    declared_missing = sorted(
        f for f in declared if not (project_root / f).exists())
    for f in declared_existing:
        p = project_root / f
        if p.is_file():
            hashes[f] = _sha256_file(p)

    return {
        "created_files": created,
        "modified_files": modified,
        "deleted_files": [],
        "declared_generated_files": sorted(declared),
        "declared_existing_files": declared_existing,
        "declared_missing_files": declared_missing,
        "planned_not_generated": planned,
        "hashes": hashes,
    }


def workspace_delta_consistency(delta: dict) -> tuple[str, list[str]]:
    """PASS unless a declared generated file is missing and the run did not
    mark it planned-but-not-generated (§7.2)."""
    reasons: list[str] = []
    missing = delta.get("declared_missing_files", [])
    if missing and not delta.get("planned_not_generated"):
        reasons.append(f"declared generated files missing: {missing}")
    return ("PASS" if not reasons else "FAIL", reasons)


# --------------------------------------------------- artifact consistency

def check_artifact_consistency(
    artifact_paths: list[Path],
    project_root: Path,
    delta: dict,
) -> dict:
    """Deterministic artifact-consistency detectors (§8), judged against the
    real delta + filesystem."""
    duplicate_keys: list[str] = []
    contradictory: list[str] = []
    nonexistent_project_paths: list[str] = []
    phantom_claims: list[str] = []
    duplicate_story_metadata: list[str] = []

    proj_resolved = project_root.resolve()
    delta_files = (set(delta.get("created_files", []))
                   | set(delta.get("modified_files", [])))

    for ap in artifact_paths:
        if not ap.exists():
            continue
        text = ap.read_text(encoding="utf-8", errors="replace")
        blocks = _extract_frontmatter_blocks(text)
        all_pairs: list[tuple[str, str]] = []
        for block in blocks:
            all_pairs.extend(_parse_frontmatter_keys(block))

        # Duplicate keys across the artefact's frontmatter.
        seen: dict[str, list[str]] = {}
        for k, v in all_pairs:
            seen.setdefault(k, []).append(v)
        for k, vals in seen.items():
            if len(vals) <= 1:
                continue
            duplicate_keys.append(f"{ap.name}:{k}")
            if k in _DECLARED_FILE_KEYS:
                parsed = [set(_parse_list_value(v)) for v in vals]
                union = set().union(*parsed) if parsed else set()
                missing = sorted(
                    f for f in union if not (project_root / f).exists())
                if missing:
                    contradictory.append(
                        f"{ap.name}:{k} declares {sorted(union)} "
                        f"but missing {missing}")
            elif len(set(vals)) > 1 and k in _STORY_META_KEYS:
                duplicate_story_metadata.append(f"{ap.name}:{k}={vals}")

    # Declared paths must not escape the project root.
    for f in delta.get("declared_generated_files", []):
        resolved = (project_root / f).resolve()
        try:
            resolved.relative_to(proj_resolved)
        except ValueError:
            nonexistent_project_paths.append(f)

    # Phantom claims: a declared generated file that exists neither on disk
    # NOR in the delta's created/modified sets.
    for f in delta.get("declared_generated_files", []):
        if not (project_root / f).exists() and f not in delta_files:
            phantom_claims.append(f)

    findings = {
        "duplicate_frontmatter_keys": sorted(set(duplicate_keys)),
        "contradictory_frontmatter": sorted(set(contradictory)),
        "nonexistent_project_paths": sorted(set(nonexistent_project_paths)),
        "phantom_file_claims": sorted(set(phantom_claims)),
        "duplicate_story_metadata": sorted(set(duplicate_story_metadata)),
    }
    # artifact_consistency FAILS only on reality-contradicting findings:
    # contradictions the delta cannot reconcile, escaping paths, or phantom
    # claims. Pure duplicate keys whose values reconcile with the workspace
    # are recorded as warnings, not failures.
    hard = (findings["contradictory_frontmatter"]
            + findings["nonexistent_project_paths"]
            + findings["phantom_file_claims"])
    findings["status"] = "PASS" if not hard else "FAIL"
    findings["reasons"] = hard[:6] if hard else []
    findings["warnings"] = (findings["duplicate_frontmatter_keys"]
                            + findings["duplicate_story_metadata"])
    return findings
