"""Phase 7 — rdx-judgment harness helpers.

This module is the local-side counterpart to the rdx-judgment skill.
The skill itself runs in an LLM session; this module ships the
deterministic helpers bmad-eval-runner uses to score transcripts:

- `count_verdict_variance` — T-L8-EVAL-CONSISTENT-001 statistical
  guard. Given N run records and the canonical expected verdict, count
  how many runs differed.
- `filter_active_scope` — T-L8-ACTIVE-RULES-001 scope-discipline
  enforcer. Given a transcript's findings and the active-pack envelope,
  separate in-scope from out-of-scope findings.
- `classify_doc_kind` — T-L8-DOC-CLASS-001 deterministic doc
  classifier. Distinguishes governance docs (architecture, ADRs,
  unsafe SAFETY docs, FFI/ABI, persistence schemas, security
  boundaries, RDX KB) from ordinary docs (README, marketing).
- `validate_finding` — JSON Schema validator for
  rdx-judgment-finding.v1, including the Cat-1 immutability guard.

Nothing here calls an LLM; that boundary belongs to bmad-eval-runner
plus the actual skill prose. The helpers exist so the *gate* —
"the evaluator did not load inactive packs, did not overturn Cat-1,
did not finds Rust noise in README" — is deterministic and re-runnable
in CI long after the LLM session finished.
"""

from __future__ import annotations

import dataclasses as _dc
import json
from pathlib import Path
from typing import Iterable

import jsonschema


__all__ = [
    "ScopeFilterResult",
    "count_verdict_variance",
    "filter_active_scope",
    "classify_doc_kind",
    "load_finding_schema",
    "validate_finding",
]


# ─── Variance harness (T-L8-EVAL-CONSISTENT-001) ─────────────────────────


def count_verdict_variance(runs: Iterable[dict], canonical_verdict: str) -> int:
    """Count how many run records produced a verdict that differs from
    `canonical_verdict`. Used by bmad-eval-runner to compare against
    the per-case `variance_threshold` documented in
    tests/fixtures/cat3-cases/<id>/case.json.

    A run record is expected to be a dict with at least `verdict`. Runs
    without `verdict` are treated as differing (silent omission = bad
    evidence).
    """
    canonical = str(canonical_verdict).strip()
    differing = 0
    for r in runs:
        v = (r or {}).get("verdict")
        if v is None or str(v).strip() != canonical:
            differing += 1
    return differing


# ─── Scope filter (T-L8-ACTIVE-RULES-001 / T-L5-CAT3-SCOPE-001) ─────────


@_dc.dataclass(frozen=True)
class ScopeFilterResult:
    in_scope: list[dict]
    out_of_scope: list[dict]
    scope_violation: bool


def filter_active_scope(
    findings: Iterable[dict],
    allowed_prefixes: Iterable[str],
    forbidden_prefixes: Iterable[str],
) -> ScopeFilterResult:
    """Partition `findings` into in-scope vs out-of-scope using rule-ID
    prefix matching. A finding is out-of-scope if its rule_id starts
    with any `forbidden_prefixes` entry, OR if no `allowed_prefixes`
    entry matches.

    `scope_violation` is True iff at least one finding is out-of-scope.
    A non-violating result means rdx-judgment respected the active-packs
    envelope.
    """
    allowed = tuple(allowed_prefixes)
    forbidden = tuple(forbidden_prefixes)
    in_scope: list[dict] = []
    out_of_scope: list[dict] = []
    for f in findings:
        rid = (f or {}).get("rule_id", "")
        if any(rid.startswith(p) for p in forbidden):
            out_of_scope.append(dict(f))
            continue
        if allowed and not any(rid.startswith(p) for p in allowed):
            out_of_scope.append(dict(f))
            continue
        in_scope.append(dict(f))
    return ScopeFilterResult(
        in_scope=in_scope,
        out_of_scope=out_of_scope,
        scope_violation=bool(out_of_scope),
    )


# ─── Doc classifier (T-L8-DOC-CLASS-001 / T-L5-DOC-001) ─────────────────


_GOVERNANCE_DIR_PREFIXES = (
    "docs/architecture",
    "docs/adr",
    "docs/api",
    "docs/security",
    "docs/persistence",
    "docs/threat",
)
_GOVERNANCE_PATH_KEYWORDS = (
    "/safety/",
    "/ffi/",
    "/abi/",
    "/governance/",
)
_GOVERNANCE_FILE_NAMES = (
    "threat-model.md",
    "architecture.md",
    "abi.md",
    "ffi.md",
    "safety.md",
)
_RDX_GOVERNANCE_ROOTS = (
    ".claude/skills/rdx-setup/assets/kb-sections/",
    "tests/contracts/",
)
_ORDINARY_NAMES = (
    "README.md",
    "README.rst",
    "CHANGELOG.md",
    "CHANGES.md",
    "CONTRIBUTING.md",
    "AUTHORS.md",
)
_ORDINARY_DIR_PREFIXES = (
    "docs/marketing",
    "docs/blog",
    "docs/announcements",
)


def classify_doc_kind(path: str) -> str:
    """Classify a documentation file path as either 'governance' (in
    rdx-judgment scope per Phase 7 §7.5) or 'ordinary' (out of scope).

    Files that are not docs at all (.rs, .toml, .json under code paths)
    are returned as 'code' so callers can short-circuit; rdx-judgment
    only consults this classifier for paths it already identified as
    documentation.
    """
    p = path.strip()
    while p.startswith("./"):
        p = p[2:]
    if not p:
        return "ordinary"

    # Ordinary docs are matched first (most specific).
    base = p.rsplit("/", 1)[-1]
    for prefix in _ORDINARY_DIR_PREFIXES:
        if p.startswith(prefix):
            return "ordinary"
    if base in _ORDINARY_NAMES:
        return "ordinary"

    # Governance docs.
    for prefix in _GOVERNANCE_DIR_PREFIXES:
        if p.startswith(prefix):
            return "governance"
    for kw in _GOVERNANCE_PATH_KEYWORDS:
        if kw in "/" + p:
            return "governance"
    if base in _GOVERNANCE_FILE_NAMES:
        return "governance"
    for root in _RDX_GOVERNANCE_ROOTS:
        if p.startswith(root):
            return "governance"

    # Code paths short-circuit.
    if p.endswith((".rs", ".toml", ".lock")):
        return "code"

    return "ordinary"


# ─── Finding schema validator (Cat-1 immutability guard) ─────────────────


def _schema_path() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "tests"
        / "contracts"
        / "schemas"
        / "rdx-judgment-finding.v1.schema.json"
    )


def load_finding_schema() -> dict:
    return json.loads(_schema_path().read_text(encoding="utf-8"))


def validate_finding(finding: dict) -> None:
    """Raise jsonschema.ValidationError if `finding` violates the
    rdx-judgment-finding v1 schema (including the Cat-1 immutability
    invariant)."""
    jsonschema.validate(finding, load_finding_schema())
