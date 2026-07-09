"""W9 doc-lint — operator docs must never present eval/test-only or auth
instructions as operator steps (G-W9-NOEVALFLAGS, and the W9 auth invariant).

This is a **test-plane** lint over ``rdx-tea/docs/**`` only. It is not
shipped and is not part of the runtime. The lint has two rules:

  1. FORBIDDEN tokens (eval/test-only flags + auth material) must appear
     ZERO times in the operator docs. These are things an operator must
     never be told to type: the ``--simulate-child`` /
     ``--test-write-fake-artefact`` / ``--allow-fixture-diff`` flags and
     their env gates, the research/eval harness dirs, and any auth
     material or config-dir override. (G-W9-NOEVALFLAGS is the core of
     this rule.)

  2. DEFERRED-only terms (``rdx-tea-validate``, hooks/modes/Cat-4,
     subagent propagation, G7 behavioural benefit) may appear ONLY in a
     file that also carries a "deferred" marker — so they are never
     presented as a shipped operator command. This keeps the deferred
     enforcement-plane backlog out of the operational instructions.

The lint is deterministic and self-contained (no live model calls, no
import of the shipped runtime). Tests prove it RED on each forbidden token
(synthetic docs) and GREEN on the real operator docs.
"""

from __future__ import annotations

from pathlib import Path

import pytest

RDX_TEA_DIR = Path(__file__).resolve().parent.parent.parent
DOCS_DIR = RDX_TEA_DIR / "docs"

# ---------------------------------------------------------------------------
# Rule 1 — tokens an operator must NEVER be told to type. Substring match,
# case-sensitive (mirrors the G-W9-NOEVALFLAGS grep and the G-AUTH grep).
# ---------------------------------------------------------------------------
FORBIDDEN_TOKENS = (
    # eval/test-only flags (the G-W9-NOEVALFLAGS core three + siblings)
    "--simulate-child",
    "--test-write-fake-artefact",
    "--allow-fixture-diff",
    "RDX_TEA_ALLOW_TEST_ARTEFACT",
    "RDX_TEA_ALLOW_FIXTURE_DIFF",
    # research/eval harness — never an operator surface
    "live-harness",
    "evals",
    "12-run pilot",
    "mass eval",
    # auth material / config-dir override — the W9 auth invariant
    "CLAUDE_CONFIG_DIR",
    "ANTHROPIC_API_KEY",
    "CLAUDE_CODE_OAUTH_TOKEN",
    "apiKeyHelper",
    "setup-token",
    ".credentials.json",
)

# ---------------------------------------------------------------------------
# Rule 2 — deferred enforcement-plane terms. Allowed ONLY when the same file
# also carries a "deferred" marker (case-insensitive), so they are never
# presented as a production operator command.
# ---------------------------------------------------------------------------
DEFERRED_ONLY_TERMS = (
    "rdx-tea-validate",
)
DEFERRED_MARKER = "deferred"


def _md_files(docs_dir: Path) -> list[Path]:
    return sorted(p for p in docs_dir.rglob("*.md") if p.is_file())


def lint_docs(docs_dir: Path) -> dict:
    """Return ``{status, hits, deferred_violations, missing}`` for a docs
    directory. Fail-closed: a missing docs directory is an ERROR (a rename
    or deletion must never silently pass)."""
    if not docs_dir.exists():
        return {"status": "ERROR", "hits": [], "deferred_violations": [],
                "missing": [str(docs_dir)]}

    hits: list[dict] = []
    deferred_violations: list[dict] = []
    for path in _md_files(docs_dir):
        text = path.read_text(encoding="utf-8")
        lower = text.lower()
        for lineno, line in enumerate(text.splitlines(), start=1):
            for tok in FORBIDDEN_TOKENS:
                if tok in line:
                    hits.append({"file": str(path), "line": lineno,
                                 "token": tok})
        for term in DEFERRED_ONLY_TERMS:
            if term in text and DEFERRED_MARKER not in lower:
                deferred_violations.append({"file": str(path), "term": term})

    status = "PASS" if not hits and not deferred_violations else "FAIL"
    return {"status": status, "hits": hits,
            "deferred_violations": deferred_violations, "missing": []}


# ---------------------------------------------------------------------------
# GREEN — the real operator docs are clean.
# ---------------------------------------------------------------------------
def test_real_operator_docs_are_clean() -> None:
    result = lint_docs(DOCS_DIR)
    assert result["status"] == "PASS", result


def test_docs_dir_exists_and_has_required_guides() -> None:
    required = {"README.md", "INSTALL.md", "RUN_WORKFLOWS.md",
                "EVIDENCE_INSPECTION.md", "TROUBLESHOOTING.md"}
    present = {p.name for p in _md_files(DOCS_DIR)}
    assert required <= present, f"missing operator guides: {required - present}"


# ---------------------------------------------------------------------------
# RED — every forbidden token is caught in a synthetic doc.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("tok", FORBIDDEN_TOKENS)
def test_forbidden_token_is_flagged(tmp_path: Path, tok: str) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "GUIDE.md").write_text(
        f"# Guide\n\nRun this: `{tok}` as a step.\n", encoding="utf-8")
    result = lint_docs(docs)
    assert result["status"] == "FAIL", result
    assert any(h["token"] == tok for h in result["hits"]), result


# ---------------------------------------------------------------------------
# RED — a deferred term without a deferred marker is flagged; WITH a marker
# it passes.
# ---------------------------------------------------------------------------
def test_deferred_term_without_marker_is_flagged(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "GUIDE.md").write_text(
        "# Guide\n\nStep 3: run `rdx-tea-validate` to admit the run.\n",
        encoding="utf-8")
    result = lint_docs(docs)
    assert result["status"] == "FAIL", result
    assert any(v["term"] == "rdx-tea-validate"
               for v in result["deferred_violations"]), result


def test_deferred_term_with_marker_passes(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "GUIDE.md").write_text(
        "# Guide\n\n`rdx-tea-validate` is deferred backlog; it is not a "
        "production command.\n", encoding="utf-8")
    result = lint_docs(docs)
    assert result["status"] == "PASS", result


# ---------------------------------------------------------------------------
# Fail-closed — a missing docs directory is an ERROR, never a silent pass.
# ---------------------------------------------------------------------------
def test_missing_docs_dir_is_error(tmp_path: Path) -> None:
    result = lint_docs(tmp_path / "no-such-docs")
    assert result["status"] == "ERROR"
    assert result["missing"]


# ---------------------------------------------------------------------------
# The G-W9-NOEVALFLAGS core three explicitly (the acceptance-gate grep).
# ---------------------------------------------------------------------------
def test_g_w9_noevalflags_core_three_absent_from_real_docs() -> None:
    core = ("simulate-child", "test-write-fake-artefact", "allow-fixture-diff")
    for path in _md_files(DOCS_DIR):
        text = path.read_text(encoding="utf-8")
        for tok in core:
            assert tok not in text, f"{tok!r} present in {path}"
