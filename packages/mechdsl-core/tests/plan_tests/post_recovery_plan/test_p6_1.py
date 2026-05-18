"""Tests for Task P6-1: extract _e2e_helpers.py shared helper module.

Acceptance criteria:
1. Module packages/mechdsl-core/tests/_e2e_helpers.py exists, exposes
   _import_generated_module.
2. Imported helper has the same signature as the duplicated copies it
   replaces.
"""

from __future__ import annotations

import importlib.util
import inspect
from pathlib import Path

import pytest


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").is_file() and (parent / "packages").is_dir():
            return parent
    raise RuntimeError("repo root not found")


def _helpers_path() -> Path:
    return _repo_root() / "packages" / "mechdsl-core" / "tests" / "_e2e_helpers.py"


class TestTaskP6_1:
    """Tests for Task P6-1: shared helper module deliverable."""

    @pytest.mark.unit
    def test_helpers_module_exists(self) -> None:
        path = _helpers_path()
        assert path.is_file(), f"P6-1 deliverable missing: {path}"
        assert path.stat().st_size > 0

    @pytest.mark.unit
    def test_helpers_exposes_import_generated_module(self) -> None:
        path = _helpers_path()
        spec = importlib.util.spec_from_file_location("_e2e_helpers_p6_1", path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)  # type: ignore[union-attr]
        assert hasattr(module, "_import_generated_module"), (
            "_e2e_helpers must expose _import_generated_module"
        )
        fn = module._import_generated_module
        sig = inspect.signature(fn)
        params = list(sig.parameters)
        assert params[0] == "source"
        assert params[1] == "tmp_path"
        assert "name" in params
