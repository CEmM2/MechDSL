"""Shared fixtures for ti-runtime tests."""

from __future__ import annotations

import pytest
import taichi as ti


@pytest.fixture(autouse=True)
def _ti_cpu():
    """Re-init Taichi on CPU before each test so freshly-allocated fields are valid."""
    ti.init(arch=ti.cpu, default_fp=ti.f64)
    yield
