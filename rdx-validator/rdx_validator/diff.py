"""Diff parser.

Closes (Phase 2):
  T-L1-DIFF-001 — parse_added_lines extracts only `+` lines
  T-L1-DIFF-002 — parse_diff_paths strips b/ prefix and ignores /dev/null
  T-L1-DIFF-003 — handles renames (a/old.rs -> b/new.rs)
  T-L1-DIGEST-001/002 — diff_digest stability + sensitivity
  T-L1-COMMENT-001 — is_likely_comment_or_doc heuristic

Input is unified diff text (as `git diff a...b` would emit).
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Iterable


_DIGEST_PREFIX = "sha256:"


@dataclass(frozen=True)
class FileChange:
    """One file's worth of changes in a unified diff."""

    old_path: str | None
    new_path: str | None
    is_rename: bool
    is_deletion: bool
    is_addition: bool
    added_lines: tuple[str, ...] = field(default_factory=tuple)
    removed_lines: tuple[str, ...] = field(default_factory=tuple)

    @property
    def post_path(self) -> str | None:
        """Path after the change. None for pure deletions."""
        return self.new_path if not self.is_deletion else None


def compute_diff_digest(diff_text: str) -> str:
    """Stable SHA-256 digest of the diff content."""
    return _DIGEST_PREFIX + hashlib.sha256(diff_text.encode("utf-8")).hexdigest()


def parse_added_lines(diff_text: str) -> list[str]:
    """Return only the added content lines (excludes `+++` header lines).

    The result is the literal line content with the leading `+` stripped.
    Empty additions are preserved.
    """
    added: list[str] = []
    for line in diff_text.splitlines():
        if line.startswith("+++"):
            continue
        if line.startswith("+"):
            added.append(line[1:])
    return added


def parse_removed_lines(diff_text: str) -> list[str]:
    """Return only the removed content lines (excludes `---` headers)."""
    removed: list[str] = []
    for line in diff_text.splitlines():
        if line.startswith("---"):
            continue
        if line.startswith("-"):
            removed.append(line[1:])
    return removed


def parse_diff_paths(diff_text: str) -> list[str]:
    """Return the changed file paths (post-image).

    Behaviour:
      - `b/` prefix is stripped
      - `/dev/null` (pure deletion) is omitted
      - renames return the new path only (the diff header carries both)
      - duplicates are preserved in input order (callers may de-dup)
    """
    paths: list[str] = []
    for line in diff_text.splitlines():
        if not line.startswith("+++ "):
            continue
        spec = line[4:].strip()
        if spec == "/dev/null":
            continue
        if spec.startswith("b/"):
            spec = spec[2:]
        paths.append(spec)
    return paths


def parse_file_changes(diff_text: str) -> list[FileChange]:
    """Parse the diff into one FileChange per file block.

    Recognises `diff --git`, `rename from/to`, `--- a/path | /dev/null`,
    `+++ b/path | /dev/null`, hunks and +/- content lines.
    """
    changes: list[FileChange] = []

    current_old: str | None = None
    current_new: str | None = None
    rename_old: str | None = None
    rename_new: str | None = None
    is_rename = False
    added: list[str] = []
    removed: list[str] = []
    in_hunk = False
    saw_header = False

    def flush() -> None:
        nonlocal current_old, current_new, rename_old, rename_new
        nonlocal is_rename, added, removed, in_hunk, saw_header
        if not saw_header and not added and not removed:
            return
        old_path = current_old
        new_path = current_new
        if is_rename:
            old_path = rename_old
            new_path = rename_new
        is_deletion = new_path is None and old_path is not None
        is_addition = old_path is None and new_path is not None
        changes.append(
            FileChange(
                old_path=old_path,
                new_path=new_path,
                is_rename=is_rename,
                is_deletion=is_deletion,
                is_addition=is_addition,
                added_lines=tuple(added),
                removed_lines=tuple(removed),
            )
        )
        current_old = None
        current_new = None
        rename_old = None
        rename_new = None
        is_rename = False
        added = []
        removed = []
        in_hunk = False
        saw_header = False

    for line in diff_text.splitlines():
        if line.startswith("diff --git "):
            flush()
            saw_header = True
            continue
        if line.startswith("rename from "):
            is_rename = True
            rename_old = line[len("rename from "):].strip()
            continue
        if line.startswith("rename to "):
            is_rename = True
            rename_new = line[len("rename to "):].strip()
            continue
        if line.startswith("--- "):
            spec = line[4:].strip()
            if spec == "/dev/null":
                current_old = None
            elif spec.startswith("a/"):
                current_old = spec[2:]
            else:
                current_old = spec
            in_hunk = False
            continue
        if line.startswith("+++ "):
            spec = line[4:].strip()
            if spec == "/dev/null":
                current_new = None
            elif spec.startswith("b/"):
                current_new = spec[2:]
            else:
                current_new = spec
            in_hunk = False
            continue
        if line.startswith("@@"):
            in_hunk = True
            continue
        if not in_hunk:
            continue
        if line.startswith("+"):
            added.append(line[1:])
        elif line.startswith("-"):
            removed.append(line[1:])

    flush()
    return changes


_COMMENT_PREFIXES = ("//", "/*", "*/", "#")


def is_likely_comment_or_doc(line: str) -> bool:
    """Quick heuristic: True if the line is a comment / doc / TOML-style key-stripper.

    True for leading `//`, `///`, `//!`, `/*`, `*` continuation, and `#`
    (shell or Cargo.toml comment).  False for trailing `// foo` after code on
    the same line (we err on the side of "this line has real code").
    """
    stripped = line.lstrip()
    if not stripped:
        return True
    if stripped.startswith("//"):
        return True
    if stripped.startswith("/*"):
        return True
    if stripped.startswith("*"):
        return True
    if stripped.startswith("#") and not stripped.startswith("#[") and not stripped.startswith("#!"):
        return True
    return False


def added_code_lines(diff_text: str) -> list[str]:
    """Added lines minus comment-only lines."""
    return [ln for ln in parse_added_lines(diff_text) if not is_likely_comment_or_doc(ln)]


def added_lines_per_file(changes: Iterable[FileChange]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for c in changes:
        if c.post_path is None:
            continue
        out.setdefault(c.post_path, []).extend(c.added_lines)
    return out
