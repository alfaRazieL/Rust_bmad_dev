"""T-L7-STALE-DIFF-001 — Evidence carries a stale diff_digest that does
not match the current diff. Pre-flight check must reject and re-run.

Defense layer: validator preflight + L6 CI runner.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


def test_l7_stale_diff_digest_rejected(validator_pkg, tmp_path):
    sys.path.insert(0, str(validator_pkg))
    try:
        from rdx_validator.preflight import check_evidence_freshness, PreflightResult
    finally:
        sys.path.pop(0)

    diff_text = "diff --git a/x b/x\n--- a/x\n+++ b/x\n@@\n+changed\n"
    stale_evidence = {
        "diff_digest": "sha256:" + "0" * 64,  # bogus
        "base_sha": "b" * 40,
        "head_sha": "h" * 40,
    }
    result: PreflightResult = check_evidence_freshness(
        evidence=stale_evidence,
        current_diff=diff_text,
        current_base_sha="b" * 40,
        current_head_sha="h" * 40,
    )
    assert result.stale_evidence is True
    assert result.wrong_base is False
    assert "diff_digest" in (result.reason or "").lower()


def test_l7_fresh_diff_digest_accepted(validator_pkg):
    sys.path.insert(0, str(validator_pkg))
    try:
        from rdx_validator.preflight import check_evidence_freshness
        from rdx_validator.diff import compute_diff_digest
    finally:
        sys.path.pop(0)

    diff_text = "diff --git a/x b/x\n--- a/x\n+++ b/x\n@@\n+changed\n"
    fresh = {
        "diff_digest": compute_diff_digest(diff_text),
        "base_sha": "b" * 40,
        "head_sha": "h" * 40,
    }
    r = check_evidence_freshness(
        evidence=fresh,
        current_diff=diff_text,
        current_base_sha="b" * 40,
        current_head_sha="h" * 40,
    )
    assert r.stale_evidence is False
    assert r.wrong_base is False
