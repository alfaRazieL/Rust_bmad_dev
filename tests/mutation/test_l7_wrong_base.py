"""T-L7-WRONG-BASE-001 — Evidence claims base_sha=A but PR's actual
base is sha B. CI preflight rejects.
"""

from __future__ import annotations

import sys


def test_l7_wrong_base_sha_rejected(validator_pkg):
    sys.path.insert(0, str(validator_pkg))
    try:
        from rdx_validator.preflight import check_evidence_freshness
        from rdx_validator.diff import compute_diff_digest
    finally:
        sys.path.pop(0)

    diff_text = "diff --git a/x b/x\n--- a/x\n+++ b/x\n@@\n+changed\n"
    evidence = {
        "diff_digest": compute_diff_digest(diff_text),
        "base_sha": "a" * 40,  # WRONG
        "head_sha": "h" * 40,
    }
    r = check_evidence_freshness(
        evidence=evidence,
        current_diff=diff_text,
        current_base_sha="b" * 40,  # actual PR base
        current_head_sha="h" * 40,
    )
    assert r.wrong_base is True
    assert r.stale_evidence is False
    assert "base_sha" in (r.reason or "").lower()
