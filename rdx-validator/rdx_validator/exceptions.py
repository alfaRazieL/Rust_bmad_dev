"""Exception block parser.

Closes (Phase 2):
  T-L1-EXC-001 — accepts valid {rule, reason, scope, expires_at, authorized_by}
  T-L1-EXC-002 — rejects missing `reason`

Exception is a record that waives or downgrades a finding for a specific rule.
The evidence schema requires `rule_id`, `scope`, `expires_at`, `authorized_by`.
A `reason` field is required by RDX policy for any author-justified exception.
"""

from __future__ import annotations

from dataclasses import dataclass


class ValidationError(ValueError):
    """Raised when an exception block fails structural validation."""

    def __init__(self, message: str, field: str | None = None):
        super().__init__(message)
        self.field = field


@dataclass(frozen=True)
class Exception_:
    rule_id: str
    reason: str
    scope: str
    expires_at: str
    authorized_by: str
    story_ref: str | None = None


_REQUIRED_FIELDS = ("rule_id", "reason", "scope", "expires_at", "authorized_by")


def parse_exception(data: dict) -> Exception_:
    """Validate and convert a raw dict into an Exception_ object."""
    if not isinstance(data, dict):
        raise ValidationError("exception must be an object", field=None)
    for fld in _REQUIRED_FIELDS:
        if fld not in data or data[fld] in (None, ""):
            raise ValidationError(f"missing or empty field: {fld}", field=fld)
    return Exception_(
        rule_id=str(data["rule_id"]),
        reason=str(data["reason"]),
        scope=str(data["scope"]),
        expires_at=str(data["expires_at"]),
        authorized_by=str(data["authorized_by"]),
        story_ref=data.get("story_ref"),
    )
