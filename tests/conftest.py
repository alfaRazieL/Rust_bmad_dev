"""Shared pytest fixtures for RDX test suite.

Exposes the repository root to all test modules so contract tests can locate
schemas, KB sections, and other artifacts deterministically regardless of the
working directory from which pytest is invoked.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
CONTRACTS_DIR = REPO_ROOT / "tests" / "contracts"
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures"
KB_DIR = REPO_ROOT / ".claude" / "skills" / "rdx-setup" / "assets" / "kb-sections"
VALIDATOR_DIR = REPO_ROOT / "rdx-validator"

# Make `rdx_validator` importable from tests without an editable install.
if str(VALIDATOR_DIR) not in sys.path:
    sys.path.insert(0, str(VALIDATOR_DIR))


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


@pytest.fixture(scope="session")
def validator_dir() -> Path:
    return VALIDATOR_DIR
