"""Phase 6 — L5 eval harness fixtures.

L5 measures LLM behavior under wrapped invocation. These tests verify
the *harness contract* (case files exist and parse; aggregator computes
thresholds correctly). The statistical runs themselves are driven by
`bmad-eval-runner` against a real LLM session — that path is NOT
exercised in CI per RDX_TEST_STRATEGY.md §4 ("L5 = scheduled, not
per-PR blocker").
"""

from __future__ import annotations

from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
EVALS_DIR = REPO_ROOT / "tests" / "evals"

# Canonical list per RDX_IMPLEMENTATION_PLAN_TESTED.md §6.2 + tests/evals/README.md
L5_PHASE6_SLUGS = [
    "router-not-skipped",
    "no-self-attested-pass",
    "not-run-honesty",
    "mode-naming",
    "no-irrelevant-pack",
    "context-pressure",
    "fail-honesty",
]


@pytest.fixture(scope="session")
def evals_dir() -> Path:
    return EVALS_DIR


@pytest.fixture(scope="session")
def l5_phase6_slugs() -> list[str]:
    return list(L5_PHASE6_SLUGS)
