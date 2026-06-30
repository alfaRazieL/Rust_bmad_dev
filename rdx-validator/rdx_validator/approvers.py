"""Cat-4 specialist approval evaluation (Phase 8).

Reads two artifacts from the user's project root:

  _bmad/rdx/approvers.yaml          — A3 hybrid canonical (rule-pattern → role → identities)
  _bmad/rdx/approvals/<digest>.json — B1 per-diff approval, validated against approval.v1.schema.json

Public surface:

  load_approvers(project_root)       → ApproversSpec | None
  pattern_verdicts(spec, paths)      → list[PendingApproval]
  resolve(verdicts, spec, project_root, diff_digest)
                                     → list[RuleVerdict] with PASS/APPROVAL_REQUIRED

The validator integrates by:
  1. Calling pattern_verdicts() to synthesise APPROVAL_REQUIRED rules for
     governance / approval-required paths the router doesn't already cover.
  2. Calling resolve() after pack translations to either downgrade
     APPROVAL_REQUIRED → PASS (when a well-formed authorised approval exists
     for the current diff_digest) or keep the rule blocking.

Soft-gate: missing approvers.yaml or missing schema files leaves the existing
verdicts untouched (cat-4 simply has no extra constraint to apply). This keeps
RDX usable on projects that don't yet opt into Cat-4 governance.
"""

from __future__ import annotations

import fnmatch
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

try:
    import yaml  # PyYAML (already an RDX test/runtime dep)
except ImportError:  # pragma: no cover
    yaml = None

try:
    from jsonschema import Draft202012Validator
except ImportError:  # pragma: no cover
    Draft202012Validator = None  # type: ignore[assignment]

from .status import RuleVerdict, Severity, Verdict


@dataclass(frozen=True)
class ApproverPattern:
    path: str
    rule_id: str
    role: str


@dataclass
class ApproversSpec:
    """Loaded approvers.yaml."""

    roles: dict[str, list[str]]
    patterns: list[ApproverPattern]

    def identities_for(self, role: str) -> list[str]:
        return list(self.roles.get(role, []))

    def matching_patterns(self, paths: Iterable[str]) -> list[tuple[ApproverPattern, str]]:
        """Return (pattern, matched_path) pairs in spec order, one per unique rule_id.

        We only need to fire each Cat-4 rule once even if many paths match.
        """
        out: list[tuple[ApproverPattern, str]] = []
        seen_rules: set[str] = set()
        for p in self.patterns:
            for path in paths:
                if _glob_match(p.path, path):
                    if p.rule_id in seen_rules:
                        break
                    seen_rules.add(p.rule_id)
                    out.append((p, path))
                    break
        return out


def _glob_match(pattern: str, path: str) -> bool:
    """fnmatch-with-globstar matching. `**` matches any number of path segments.

    Examples:
        src/unsafe/**       matches src/unsafe/foo.rs and src/unsafe/sub/bar.rs
        _bmad/rust-kb/**    matches _bmad/rust-kb/section-4-core.md
        tests/contracts/router-rules.json — exact match
    """
    # Fast path: no globstar — defer to fnmatch on the whole string.
    if "**" not in pattern:
        return fnmatch.fnmatchcase(path, pattern)
    # Build a regex from the pattern character-by-character so we control how
    # `**` interacts with `/`.
    out: list[str] = []
    i = 0
    while i < len(pattern):
        ch = pattern[i]
        if ch == "*" and i + 1 < len(pattern) and pattern[i + 1] == "*":
            # `**/` matches zero or more directory segments (including empty);
            # bare `**` matches anything (incl. /).
            if i + 2 < len(pattern) and pattern[i + 2] == "/":
                out.append("(?:.*/)?")
                i += 3
            else:
                out.append(".*")
                i += 2
            continue
        if ch == "*":
            out.append("[^/]*")
            i += 1
            continue
        if ch == "?":
            out.append("[^/]")
            i += 1
            continue
        out.append(re.escape(ch))
        i += 1
    regex = "(?s:" + "".join(out) + r")\Z"
    return re.match(regex, path) is not None


def load_approvers(project_root: Path) -> ApproversSpec | None:
    """Load approvers.yaml; return None if absent (tolerated)."""
    path = project_root / "_bmad" / "rdx" / "approvers.yaml"
    if not path.exists():
        return None
    if yaml is None:  # pragma: no cover - PyYAML is a required test dep
        return None
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        return None
    roles_raw = data.get("roles") or {}
    roles: dict[str, list[str]] = {}
    for name, body in roles_raw.items():
        if isinstance(body, dict):
            ids = body.get("identities") or []
        else:
            ids = []
        roles[name] = [str(i) for i in ids]
    patterns_raw = data.get("patterns") or []
    patterns = [
        ApproverPattern(path=str(p["path"]), rule_id=str(p["rule_id"]), role=str(p["role"]))
        for p in patterns_raw
        if isinstance(p, dict) and "path" in p and "rule_id" in p and "role" in p
    ]
    return ApproversSpec(roles=roles, patterns=patterns)


def synthesise_pattern_verdicts(
    spec: ApproversSpec, paths_changed: Iterable[str], already_emitted: Iterable[str]
) -> list[RuleVerdict]:
    """For each pattern that matches a changed path, emit a Cat-4 APPROVAL_REQUIRED
    rule — unless the router (or pack translator) already emitted the same rule_id.

    These rules cover governance / project-defined paths the router doesn't
    natively know about (e.g. _bmad/rust-kb/**).
    """
    emitted = set(already_emitted)
    out: list[RuleVerdict] = []
    for pattern, matched in spec.matching_patterns(paths_changed):
        if pattern.rule_id in emitted:
            continue
        emitted.add(pattern.rule_id)
        reason = (
            f"governance-protected path matched ({matched}); "
            f"requires role={pattern.role}"
        )
        out.append(
            RuleVerdict(
                rule_id=pattern.rule_id,
                category=4,
                verdict=Verdict.APPROVAL_REQUIRED,
                severity=Severity.BLOCKING,
                reason=reason,
            )
        )
    return out


def load_approval_schema(schema_path: Path) -> dict | None:
    if not schema_path.exists():
        return None
    return json.loads(schema_path.read_text(encoding="utf-8"))


def resolve_approvals(
    verdicts: list[RuleVerdict],
    spec: ApproversSpec | None,
    project_root: Path,
    diff_digest: str,
    approval_schema: dict | None,
) -> list[RuleVerdict]:
    """Downgrade APPROVAL_REQUIRED → PASS when an authorised approval JSON exists
    for the current diff_digest.

    Single-approval-per-diff (B1): _bmad/rdx/approvals/<digest>.json. The file's
    rule_id field names which rule it satisfies; other Cat-4 rules in the same
    diff stay blocked.
    """
    if spec is None:
        return verdicts
    approval_path = project_root / "_bmad" / "rdx" / "approvals" / f"{diff_digest}.json"
    if not approval_path.exists():
        return verdicts

    raw = approval_path.read_text(encoding="utf-8")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        return [
            _annotate_blocked(v, f"approval JSON parse error: {exc.msg}")
            if v.verdict == Verdict.APPROVAL_REQUIRED
            else v
            for v in verdicts
        ]

    if approval_schema is not None and Draft202012Validator is not None:
        errors = list(Draft202012Validator(approval_schema).iter_errors(data))
        if errors:
            msg = "approval JSON failed schema validation: " + "; ".join(
                f"{list(e.path)}: {e.message}" for e in errors
            )
            return [
                _annotate_blocked(v, msg) if v.verdict == Verdict.APPROVAL_REQUIRED else v
                for v in verdicts
            ]

    # Decisions other than 'approved' do not unblock the rule.
    if data.get("decision") != "approved":
        return [
            _annotate_blocked(v, f"approval recorded but decision={data.get('decision')}")
            if v.verdict == Verdict.APPROVAL_REQUIRED
            else v
            for v in verdicts
        ]

    if data.get("diff_digest") != diff_digest:
        # File name vs body mismatch — refuse silently.
        return [
            _annotate_blocked(
                v,
                "approval body diff_digest does not match file name (binding broken)",
            )
            if v.verdict == Verdict.APPROVAL_REQUIRED
            else v
            for v in verdicts
        ]

    rule_id = data.get("rule_id")
    identity = data.get("approver_identity")
    role = data.get("approver_role")
    role_identities = spec.identities_for(role) if role else []
    identity_ok = identity in role_identities

    out: list[RuleVerdict] = []
    for v in verdicts:
        if v.verdict != Verdict.APPROVAL_REQUIRED:
            out.append(v)
            continue
        if v.rule_id != rule_id:
            out.append(v)
            continue
        if not identity_ok:
            out.append(
                _annotate_blocked(
                    v,
                    f"approver identity '{identity}' is not authorised for role '{role}'",
                )
            )
            continue
        out.append(
            RuleVerdict(
                rule_id=v.rule_id,
                category=v.category,
                verdict=Verdict.PASS,
                severity=Severity.INFO,
                reason=(
                    f"approval honoured: rule_id={rule_id} approver={identity} "
                    f"role={role} diff_digest={diff_digest[:12]}"
                ),
            )
        )
    return out


def _annotate_blocked(verdict: RuleVerdict, message: str) -> RuleVerdict:
    base = verdict.reason or ""
    sep = "; " if base else ""
    return RuleVerdict(
        rule_id=verdict.rule_id,
        category=verdict.category,
        verdict=Verdict.APPROVAL_REQUIRED,
        severity=Severity.BLOCKING,
        reason=f"{base}{sep}{message}",
    )
