"""Shared pytest fixtures for RDX test suite.

Exposes the repository root to all test modules so contract tests can locate
schemas, KB sections, and other artifacts deterministically regardless of the
working directory from which pytest is invoked.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
CONTRACTS_DIR = REPO_ROOT / "tests" / "contracts"
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures"
KB_DIR = REPO_ROOT / ".claude" / "skills" / "rdx-setup" / "assets" / "kb-sections"


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(scope="session")
def contracts_dir() -> Path:
    return CONTRACTS_DIR


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    return FIXTURES_DIR


@pytest.fixture(scope="session")
def kb_dir() -> Path:
    return KB_DIR
