"""Pre-flight evidence checks — Phase 5 L7 mutation guards.

Closes:
  T-L7-STALE-DIFF-001  evidence diff_digest must match current diff
  T-L7-WRONG-BASE-001  evidence base_sha must match current PR base
  T-L7-OVERSIZED-DIFF-001  diff size bounded; oversize → ENVIRONMENT_UNAVAILABLE

Pre-flight runs before any Cat-1/2 check so a tampered or stale
evidence block cannot smuggle a fake PASS past the validator.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

# Default maximum diff size: 10 MiB. Above this we refuse to load the
# whole diff and return ENVIRONMENT_UNAVAILABLE so neither validator
# nor hook OOM under adversarial / DoS-class inputs.
DEFAULT_MAX_DIFF_BYTES = 10 * 1024 * 1024


@dataclass(frozen=True)
class PreflightResult:
    stale_evidence: bool
    wrong_base: bool
    reason: str | None = None


def _digest_hex(diff_text: str) -> str:
    """Raw sha256 hex digest, matching the format used in the evidence envelope."""
    return hashlib.sha256(diff_text.encode("utf-8")).hexdigest()


def _normalise(digest: str) -> str:
    """Accept either raw hex or `sha256:HEX` form."""
    if digest.startswith("sha256:"):
        return digest[len("sha256:") :].lower()
    return digest.lower()


def check_evidence_freshness(
    *,
    evidence: dict,
    current_diff: str,
    current_base_sha: str | None,
    current_head_sha: str | None,
) -> PreflightResult:
    """Verify that the submitted evidence still describes the current PR.

    Stale-evidence path (T-L7-STALE-DIFF-001): the evidence's diff_digest
    must match a recomputed digest of the current diff bytes.

    Wrong-base path (T-L7-WRONG-BASE-001): the evidence's base_sha must
    match the actual PR base sha (passed by the CI runner). If the
    caller cannot determine a base sha (offline / local hook), the
    base-sha check is skipped — we never refuse a freshness check for
    lack of CI metadata.
    """
    if not evidence:
        # Nothing to check — no preflight violation.
        return PreflightResult(stale_evidence=False, wrong_base=False)

    claimed_digest = _normalise(str(evidence.get("diff_digest", "")))
    actual_digest = _digest_hex(current_diff)
    stale = bool(claimed_digest) and claimed_digest != actual_digest

    wrong_base = False
    base_reason = None
    if current_base_sha and evidence.get("base_sha"):
        claimed_base = str(evidence["base_sha"]).lower()
        if claimed_base != current_base_sha.lower():
            wrong_base = True
            base_reason = (
                f"evidence.base_sha={claimed_base[:12]} does not match "
                f"current PR base_sha={current_base_sha[:12]}"
            )

    if stale and wrong_base:
        reason = f"stale diff_digest AND {base_reason}"
    elif stale:
        reason = (
            f"diff_digest mismatch: evidence claims {claimed_digest[:12]} "
            f"but current diff hashes to {actual_digest[:12]}"
        )
    elif wrong_base:
        reason = base_reason
    else:
        reason = None
    return PreflightResult(stale_evidence=stale, wrong_base=wrong_base, reason=reason)


def diff_within_bounds(diff_bytes: int, max_bytes: int = DEFAULT_MAX_DIFF_BYTES) -> bool:
    return diff_bytes <= max_bytes
