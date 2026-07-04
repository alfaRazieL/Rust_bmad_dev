#!/usr/bin/env python3
"""D3.4.0 §7-§8 — deterministic workspace-delta and artifact-consistency.

No LLM. Two responsibilities:

  collect_workspace_delta(workspace, base_sha)
      Full post-run delta of the disposable git workspace: created /
      modified / deleted files (vs the base commit + untracked), with
      sha256 hashes, plus the files the TEA artifact DECLARES it
      generated, and which of those actually exist.

  check_artifact_consistency(artifact_paths, workspace, delta)
      Deterministic detectors: duplicate frontmatter keys, contradictory
      frontmatter values, declared paths that do not exist, project
      paths that do not exist, artifact file-claims not backed by the
      workspace delta, duplicate story metadata. Judges
      artifact_consistency against REALITY (the delta), so a genuine
      admissible candidate is possible while phantom file claims fail.

Both feed the v4 evidence fields `workspace_delta`,
`workspace_delta_consistency`, `artifact_consistency`, and
`admission_reasons`.
"""

from __future__ import annotations

import hashlib
import re
import subprocess
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

_IGNORE_PREFIXES = (
    "_bmad/",          # adapter runtime + scripts (installed, not generated)
    ".claude/",        # skills + project settings
    ".git/",
)


def _sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() and p.is_file() else ""


def _git(args: list[str], cwd: Path) -> str:
    r = subprocess.run(["git", "-C", str(cwd), *args],
                       capture_output=True, text=True, check=False)
    return r.stdout


# ------------------------------------------------------- frontmatter parse

def _extract_frontmatter_blocks(text: str) -> list[str]:
    """Return every YAML frontmatter block delimited by `---` lines. TEA
    checklists can carry more than one (a real defect we want to detect),
    so we return ALL blocks, not just the first."""
    blocks: list[str] = []
    lines = text.splitlines()
    i = 0
    # Leading frontmatter block only starts at the top; but child skills
    # sometimes emit a second `---`-delimited block. We scan for paired
    # `---` fences from the top of the file.
    fence_idx = [n for n, ln in enumerate(lines) if ln.strip() == "---"]
    for a, b in zip(fence_idx[0::2], fence_idx[1::2]):
        blocks.append("\n".join(lines[a + 1:b]))
    return blocks


def _parse_frontmatter_keys(block: str) -> list[tuple[str, str]]:
    """Return (key, raw_value) pairs in order, WITHOUT collapsing
    duplicates (so duplicates are detectable). List values that span
    lines are captured as a joined raw string."""
    pairs: list[tuple[str, str]] = []
    lines = block.splitlines()
    i = 0
    key_re = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*):(.*)$")
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
        # Possibly a block list on following indented lines.
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
    paths."""
    raw = raw.strip()
    if raw in ("[]", "[ ]", ""):
        return []
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1].strip()
        if not inner:
            return []
        return [x.strip().strip("'\"") for x in inner.split(",") if x.strip()]
    return [raw.strip().strip("'\"")]


# ------------------------------------------------------- workspace delta

def collect_workspace_delta(workspace: Path, base_sha: str | None = None,
                            artifact_paths: list[Path] | None = None) -> dict:
    """D3.4.0 §7. Full post-run delta of the disposable git workspace."""
    created: list[str] = []
    modified: list[str] = []
    deleted: list[str] = []
    # `git status --porcelain` covers tracked-modified/deleted + untracked.
    porcelain = _git(["status", "--porcelain", "--untracked-files=all"], workspace)
    for line in porcelain.splitlines():
        if not line.strip():
            continue
        status = line[:2]
        path = line[3:].strip().strip('"')
        if any(path.startswith(pfx) for pfx in _IGNORE_PREFIXES):
            continue
        if status in ("??", "A ", "AM"):
            created.append(path)
        elif "D" in status:
            deleted.append(path)
        else:
            modified.append(path)
    created = sorted(set(created))
    modified = sorted(set(modified))
    deleted = sorted(set(deleted))

    hashes: dict[str, str] = {}
    for rel in created + modified:
        p = workspace / rel
        if p.exists() and p.is_file():
            hashes[rel] = _sha256_file(p)

    # Declared files from artifact frontmatter (union across all blocks).
    declared_generated: set[str] = set()
    planned_not_generated = False
    for ap in (artifact_paths or []):
        if not ap.exists():
            continue
        text = ap.read_text(encoding="utf-8", errors="replace")
        for block in _extract_frontmatter_blocks(text):
            pairs = _parse_frontmatter_keys(block)
            for key in _DECLARED_FILE_KEYS:
                for raw in _values_for_key(pairs, key):
                    for f in _parse_list_value(raw):
                        if f:
                            declared_generated.add(f)
            for raw in _values_for_key(pairs, _PLANNED_FLAG_KEY):
                if raw.strip().lower() in ("true", "yes", "1"):
                    planned_not_generated = True

    declared_existing = sorted(
        f for f in declared_generated if (workspace / f).exists()
    )
    declared_missing = sorted(
        f for f in declared_generated if not (workspace / f).exists()
    )
    # hash declared existing files too
    for f in declared_existing:
        p = workspace / f
        if p.is_file():
            hashes[f] = _sha256_file(p)

    return {
        "created_files": created,
        "modified_files": modified,
        "deleted_files": deleted,
        "declared_generated_files": sorted(declared_generated),
        "declared_existing_files": declared_existing,
        "declared_missing_files": declared_missing,
        "planned_not_generated": planned_not_generated,
        "hashes": hashes,
    }


def workspace_delta_consistency(delta: dict) -> tuple[str, list[str]]:
    """PASS unless a declared generated file is missing and the run did
    not mark it planned-but-not-generated (§7.2)."""
    reasons: list[str] = []
    missing = delta.get("declared_missing_files", [])
    if missing and not delta.get("planned_not_generated"):
        reasons.append(f"declared generated files missing: {missing}")
    status = "PASS" if not reasons else "FAIL"
    return status, reasons


# --------------------------------------------------- artifact consistency

def check_artifact_consistency(artifact_paths: list[Path], workspace: Path,
                               delta: dict) -> dict:
    """Deterministic artifact-consistency detectors (§8)."""
    duplicate_keys: list[str] = []
    contradictory: list[str] = []
    nonexistent_project_paths: list[str] = []
    phantom_claims: list[str] = []
    duplicate_story_metadata: list[str] = []

    for ap in artifact_paths:
        if not ap.exists():
            continue
        text = ap.read_text(encoding="utf-8", errors="replace")
        blocks = _extract_frontmatter_blocks(text)
        # Merge all blocks' pairs to detect cross-block duplicates.
        all_pairs: list[tuple[str, str]] = []
        for block in blocks:
            all_pairs.extend(_parse_frontmatter_keys(block))
        # Duplicate keys across the artifact's frontmatter.
        seen: dict[str, list[str]] = {}
        for k, v in all_pairs:
            seen.setdefault(k, []).append(v)
        for k, vals in seen.items():
            if len(vals) > 1:
                duplicate_keys.append(f"{ap.name}:{k}")
                # Contradiction = distinct non-empty values that are not
                # subset-compatible for file-list keys.
                if k in _DECLARED_FILE_KEYS:
                    parsed = [set(_parse_list_value(v)) for v in vals]
                    union = set().union(*parsed)
                    # Contradictory only if the union files do NOT all
                    # exist (i.e., the artifact cannot be reconciled with
                    # reality).
                    missing = sorted(f for f in union
                                     if not (workspace / f).exists())
                    if missing:
                        contradictory.append(
                            f"{ap.name}:{k} declares {sorted(union)} "
                            f"but missing {missing}")
                elif len(set(vals)) > 1 and k in ("storyId", "storyKey",
                                                   "lastStep"):
                    duplicate_story_metadata.append(f"{ap.name}:{k}={vals}")

        # Project-path claims: any declared file path must not escape the
        # workspace root.
        for f in delta.get("declared_generated_files", []):
            resolved = (workspace / f).resolve()
            try:
                resolved.relative_to(workspace.resolve())
            except ValueError:
                nonexistent_project_paths.append(f)

        # Phantom claims: a declared generated file that exists neither in
        # the workspace NOR in the delta's created/modified sets.
        delta_files = set(delta.get("created_files", [])) | set(
            delta.get("modified_files", []))
        for f in delta.get("declared_generated_files", []):
            if not (workspace / f).exists() and f not in delta_files:
                phantom_claims.append(f)

    findings = {
        "duplicate_frontmatter_keys": sorted(set(duplicate_keys)),
        "contradictory_frontmatter": sorted(set(contradictory)),
        "nonexistent_project_paths": sorted(set(nonexistent_project_paths)),
        "phantom_file_claims": sorted(set(phantom_claims)),
        "duplicate_story_metadata": sorted(set(duplicate_story_metadata)),
    }
    # artifact_consistency FAILS only on reality-contradicting findings:
    # contradictions the delta cannot reconcile, escaping paths, or
    # phantom claims. Pure duplicate keys whose values reconcile with the
    # workspace are recorded as warnings, not failures.
    hard = (findings["contradictory_frontmatter"]
            + findings["nonexistent_project_paths"]
            + findings["phantom_file_claims"])
    status = "PASS" if not hard else "FAIL"
    reasons = []
    if hard:
        reasons = hard[:6]
    findings["status"] = status
    findings["reasons"] = reasons
    findings["warnings"] = (findings["duplicate_frontmatter_keys"]
                            + findings["duplicate_story_metadata"])
    return findings
