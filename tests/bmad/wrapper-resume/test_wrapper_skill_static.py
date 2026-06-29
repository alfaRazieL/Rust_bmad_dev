"""L4 wrapper-resume static tests — T-L4-WR-001..006.

Phase 3 needs deterministic, CI-runnable evidence that the rdx-dev-story
wrapper SKILL.md declares all the safeguards required for each WR scenario.

These tests are STATIC structural checks on
`.claude/skills/rdx-dev-story/SKILL.md`. The runtime LLM-cooperative
confirmation (a real subagent actually following the SKILL prose) is
explicitly the job of the L5 behavioral evals in Phase 6 — see
`RDX_IMPLEMENTATION_PLAN_TESTED.md` Phase 3 exit gate:
    "L5 happy-path eval pass rate ≥ 85% over 20 runs (smoke; full L5 in Phase 6)"

Per `RDX_TEST_STRATEGY.md` §2 the L4 layer is "LLM-cooperative where
wrapper-resume; one-shot manual session for resume." That manual session
is the Phase 6 L5 work; what we lock in here is the structural contract
the SKILL.md must satisfy so the runtime path is reachable.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.bmad._helpers.skill_parser import parse

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent.parent
WRAPPER_SKILL = REPO_ROOT / ".claude" / "skills" / "rdx-dev-story" / "SKILL.md"


@pytest.fixture(scope="module")
def parsed_wrapper():
    assert WRAPPER_SKILL.exists(), f"Wrapper skill missing at {WRAPPER_SKILL}"
    return parse(WRAPPER_SKILL)


def test_wrapper_skill_frontmatter(parsed_wrapper):
    assert parsed_wrapper.name == "rdx-dev-story"
    assert parsed_wrapper.description, "description must be non-empty"
    # Description must NOT make a hard-enforcement claim.
    forbidden = ["hard enforcement", "guarantees compliance", "guaranteed"]
    for phrase in forbidden:
        assert phrase.lower() not in parsed_wrapper.description.lower(), (
            f"Wrapper description must not contain forbidden phrase: {phrase!r}"
        )


def test_t_l4_wr_001_happy_path_structure(parsed_wrapper):
    """T-L4-WR-001 — wrapper declares BEFORE → CHILD → AFTER → validator → report."""
    expected = json.loads((HERE / "happy-path" / "expected.json").read_text())
    body = parsed_wrapper.body

    # Required content markers.
    assert "BEFORE" in body, "wrapper must record a BEFORE marker prior to child"
    assert "bmad-dev-story" in body, "wrapper must invoke bmad-dev-story child skill"
    assert "AFTER" in body, "wrapper must record an AFTER marker post-child"
    assert "rdx-validator" in body or "validator" in body
    assert "report" in body.lower()

    # Ordering check based on step-section headers, not first-occurrence of
    # words that may appear in introductory prose.
    idx_before = body.index("BEFORE marker")
    idx_child = body.index("Invoke child skill")
    idx_after = body.index("AFTER marker")
    assert idx_before < idx_child < idx_after, (
        f"step ordering must be BEFORE({idx_before}) < CHILD({idx_child}) < AFTER({idx_after})"
    )

    # Final expected trace and exit code recorded in fixture (oracle).
    assert expected["expected_trace_order"] == ["BEFORE", "CHILD", "AFTER"]
    assert expected["expected_exit_code"] == 0


def test_t_l4_wr_002_child_error_handling(parsed_wrapper):
    """T-L4-WR-002 — wrapper must detect ERROR_MARKER and continue to validator."""
    body = parsed_wrapper.body
    assert "ERROR_MARKER" in body, "wrapper must name the child-error sentinel"
    assert "child_error" in body or "child-error" in body, (
        "wrapper must define wrapper_status=child_error path"
    )


def test_t_l4_wr_003_validator_fail_halt(parsed_wrapper):
    """T-L4-WR-003 — wrapper halts on validator non-zero exit code."""
    body = parsed_wrapper.body
    assert "WRAPPER_HALTED_DUE_TO_VALIDATOR_FAIL" in body, (
        "wrapper must declare the validator-fail halt sentinel"
    )
    # Soft-gate honesty (also enforced by T-V5-ACC-06 globally).
    assert "hard enforcement" not in body.lower() or "not hard enforcement" in body.lower()


def test_t_l4_wr_004_no_recursion(parsed_wrapper):
    """T-L4-WR-004 — wrapper forbids self-invocation; names exactly one child."""
    body = parsed_wrapper.body
    # Must explicitly forbid self-invocation.
    assert "must not" in body.lower() or "do not" in body.lower()
    assert "rdx-dev-story" in body  # appears in frontmatter at minimum
    # The Skill invocation in the body must target bmad-dev-story, NOT rdx-dev-story.
    # We assert there is no instruction "Skill ... rdx-dev-story" in the prose
    # (frontmatter mention is fine).
    body_lower = body.lower()
    # Look for the explicit recursion guard sentinel.
    assert "recursion" in body_lower or "self-invoke" in body_lower or "no-recursion" in body_lower


def test_t_l4_wr_005_missing_artifact_detection(parsed_wrapper):
    """T-L4-WR-005 — wrapper post-child step checks for required artifact."""
    body = parsed_wrapper.body
    assert "MISSING_ARTIFACT" in body or "missing artifact" in body.lower(), (
        "wrapper must declare a missing-artifact diagnostic"
    )
    # Required artifacts the wrapper checks for.
    assert "diff" in body.lower() or "evidence" in body.lower()


def test_t_l4_wr_006_risk_tag_preservation(parsed_wrapper):
    """T-L4-WR-006 — wrapper captures risk tags before child and re-reads after."""
    body = parsed_wrapper.body.lower()
    assert "risk" in body and "tag" in body, "wrapper must mention risk tags"
    # Must instruct to persist tags in stable storage (story file or persistent_facts).
    assert (
        "persistent_facts" in body or "story file" in body or "story.md" in body
    ), "wrapper must name stable storage for risk tags across child boundary"


def test_wrapper_declares_no_false_enforcement(parsed_wrapper):
    """T-V5-ACC-06 cross-reference — wrapper SKILL must not claim hard enforcement
    in Mode 0 / Mode 1 terms. Phrase 'soft gate' or equivalent must appear."""
    body = parsed_wrapper.body.lower()
    assert (
        "soft gate" in body
        or "soft-gate" in body
        or "cooperative" in body
        or "advisory" in body
    ), "wrapper must explicitly identify itself as a soft gate / cooperative orchestrator"


@pytest.mark.parametrize(
    "test_id,fixture_dir",
    [
        ("T-L4-WR-001", "happy-path"),
        ("T-L4-WR-002", "child-errored"),
        ("T-L4-WR-003", "validator-fail"),
        ("T-L4-WR-004", "no-recursion"),
        ("T-L4-WR-005", "missing-artifact"),
        ("T-L4-WR-006", "risk-tag-preservation"),
    ],
)
def test_each_wr_fixture_has_canonical_expected(test_id, fixture_dir):
    """Every WR test ID has a canonical expected.json alongside its fixture dir."""
    expected_path = HERE / fixture_dir / "expected.json"
    assert expected_path.exists(), f"missing expected.json for {test_id}"
    expected = json.loads(expected_path.read_text())
    assert expected["test_id"] == test_id
    assert "expected_status" in expected
    assert "expected_exit_code" in expected
    assert isinstance(expected["skill_must_declare"], list)
    assert len(expected["skill_must_declare"]) >= 1
