"""Shared pytest fixtures for MechDSL tests."""

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
GOLDEN_DIR = Path(__file__).resolve().parent / "golden"
REF_DIR = Path(__file__).resolve().parent / "ref"


@pytest.fixture
def golden_dir() -> Path:
    """Path to golden artifact files for regression testing."""
    return GOLDEN_DIR


@pytest.fixture
def ref_dir() -> Path:
    """Path to handwritten reference kernels."""
    return REF_DIR
