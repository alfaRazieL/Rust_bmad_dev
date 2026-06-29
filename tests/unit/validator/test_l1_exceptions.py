"""L1 unit tests for the exception parser.

Closes:
  T-L1-EXC-001 — parser accepts valid {rule_id, reason, scope, expires_at, authorized_by}
  T-L1-EXC-002 — parser rejects missing `reason`
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rdx_validator.exceptions import ValidationError, parse_exception


def _read(fixtures_dir: Path, name: str) -> dict:
    return json.loads((fixtures_dir / "evidence" / name).read_text(encoding="utf-8"))


def test_l1_exc_001_valid_exception_parsed(fixtures_dir: Path):
    data = _read(fixtures_dir, "exception-valid.json")
    exc = parse_exception(data)
    assert exc.rule_id == "CORE-007"
    assert exc.reason.startswith("explicit boundary expansion")
    assert exc.scope == "src/auth/login.rs"
    assert exc.authorized_by == "tech-lead@example.com"
    assert exc.story_ref == "STORY-AUTH-042"


def test_l1_exc_002_missing_reason_rejected(fixtures_dir: Path):
    data = _read(fixtures_dir, "exception-missing-reason.json")
    with pytest.raises(ValidationError) as exc_info:
        parse_exception(data)
    assert exc_info.value.field == "reason"
