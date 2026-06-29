"""L1 unit tests for the diff parser.

Closes:
  T-L1-DIFF-001 — parse_added_lines extracts only `+` content lines
  T-L1-DIFF-002 — parse_diff_paths strips b/ prefix and ignores /dev/null
  T-L1-DIFF-003 — handles file renames (a/old.rs → b/new.rs)
  T-L1-DIGEST-001 — compute_diff_digest is stable across N invocations
  T-L1-DIGEST-002 — digest changes when whitespace changes
  T-L1-COMMENT-001 — is_likely_comment_or_doc per-step matches
"""

from __future__ import annotations

from pathlib import Path

import pytest

from rdx_validator.diff import (
    compute_diff_digest,
    is_likely_comment_or_doc,
    parse_added_lines,
    parse_diff_paths,
    parse_file_changes,
)


def _read(fixtures_dir: Path, name: str) -> str:
    return (fixtures_dir / "diffs" / name).read_text(encoding="utf-8")


# ---------- T-L1-DIFF-001 ----------
def test_l1_diff_001_added_lines_excludes_header(fixtures_dir: Path):
    diff = _read(fixtures_dir, "single-file-add.diff")
    added = parse_added_lines(diff)
    assert added, "must have at least one added line"
    for line in added:
        assert not line.startswith("++ "), "added lines must not start with `++`"
    # We added 5 lines: 3 code lines, 1 blank, 1 comment.
    assert len(added) == 5, f"expected 5 added lines, got {len(added)}: {added!r}"
    assert any("greet" in ln for ln in added)


# ---------- T-L1-DIFF-002 ----------
def test_l1_diff_002_paths_strip_b_prefix_and_skip_dev_null(fixtures_dir: Path):
    diff = _read(fixtures_dir, "file-deletion.diff")
    paths = parse_diff_paths(diff)
    assert "src/new.rs" in paths, "post-image of created file must be reported"
    assert all(not p.startswith("b/") for p in paths)
    assert "/dev/null" not in paths
    # the deleted file path src/old.rs has +++ /dev/null so must NOT appear
    assert "src/old.rs" not in paths


# ---------- T-L1-DIFF-003 ----------
def test_l1_diff_003_rename_returns_new_path(fixtures_dir: Path):
    diff = _read(fixtures_dir, "file-rename.diff")
    paths = parse_diff_paths(diff)
    assert "src/new.rs" in paths
    # Old name must not appear in the post-image path list
    assert "src/old.rs" not in paths
    # The parser should also flag the rename in structured form
    changes = parse_file_changes(diff)
    assert any(c.is_rename and c.new_path == "src/new.rs" for c in changes)


# ---------- T-L1-DIGEST-001 ----------
def test_l1_digest_001_stable_across_invocations(fixtures_dir: Path):
    diff = _read(fixtures_dir, "fixture-1-real-async.diff")
    digests = {compute_diff_digest(diff) for _ in range(100)}
    assert len(digests) == 1, f"digest must be deterministic: {digests}"


# ---------- T-L1-DIGEST-002 ----------
def test_l1_digest_002_whitespace_change_changes_digest(fixtures_dir: Path):
    a = (fixtures_dir / "diffs" / "digest-whitespace-pair" / "a.diff").read_text(encoding="utf-8")
    # b.diff is byte-identical on disk, but we add one trailing space and recompute.
    b = a + " \n"
    da = compute_diff_digest(a)
    db = compute_diff_digest(b)
    assert da != db, "trailing whitespace must change the digest"


# ---------- T-L1-COMMENT-001 ----------
@pytest.mark.parametrize(
    "line,expected",
    [
        ("// foo", True),
        ("/// doc comment", True),
        ("//! inner doc", True),
        ("/* block */", True),
        (" * continuation", True),
        ("# Cargo.toml comment", True),
        ("    ", True),  # blank/whitespace
        ("let x = 1; // trailing", False),  # real code with trailing comment
        ("pub fn foo() {}", False),
        ("#[derive(Debug)]", False),  # attribute, not comment
    ],
)
def test_l1_comment_001_heuristic(line: str, expected: bool):
    assert is_likely_comment_or_doc(line) is expected, line
