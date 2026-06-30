"""Shared mutation-test helpers — Phase 5.

These point at the rdx-validator + the schema living in this repo so
the mutation tests can directly assert validator + schema behavior on
hand-crafted evidence fixtures.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO_ROOT / "tests" / "contracts" / "schemas" / "rdx-evidence.v1.schema.json"
CONTRACTS_DIR = REPO_ROOT / "tests" / "contracts"
VALIDATOR_PKG = REPO_ROOT / "rdx-validator"


@pytest.fixture(scope="session")
def schema_path() -> Path:
    return SCHEMA_PATH


@pytest.fixture(scope="session")
def contracts_dir() -> Path:
    return CONTRACTS_DIR


@pytest.fixture(scope="session")
def validator_pkg() -> Path:
    return VALIDATOR_PKG
