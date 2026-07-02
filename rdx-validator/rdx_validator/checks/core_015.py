"""CORE-015 — Router parity.

T-L2-CORE015-001 — agent-claimed activated_packs missing real signal → FAIL
T-L2-CORE015-002 — agent claim with documented suppression → PASS
"""

from __future__ import annotations

from typing import Iterable

from ..router import PackActivation
from ..status import RuleVerdict, Severity, Verdict


def check_core_015(
    validator_activations: Iterable[PackActivation],
    agent_claimed: Iterable[str],
    documented_suppressions: Iterable[str] = (),
) -> RuleVerdict:
    validator_active = {a.pack for a in validator_activations if a.active}
    agent = set(agent_claimed)
    suppress = set(documented_suppressions)

    missing_in_agent = validator_active - agent - suppress
    extra_in_agent = agent - validator_active

    if not missing_in_agent and not extra_in_agent:
        return RuleVerdict(
            rule_id="CORE-015",
            category=1,
            verdict=Verdict.PASS,
            severity=Severity.INFO,
        )
    parts: list[str] = []
    if missing_in_agent:
        parts.append(f"agent missed packs: {sorted(missing_in_agent)}")
    if extra_in_agent:
        parts.append(f"agent invented packs: {sorted(extra_in_agent)}")
    return RuleVerdict(
        rule_id="CORE-015",
        category=1,
        verdict=Verdict.FAIL,
        severity=Severity.BLOCKING,
        reason="; ".join(parts),
    )
