"""Tests for Task P6-2: swap test_p7_2 + test_e2e_taichi to use _e2e_helpers.

Acceptance criteria:
1. Neither file contains a local copy of `_import_generated_module`.
2. Both files import the helper from `_e2e_helpers`.
3. Existing tests still pass (verified by running the affected files).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").is_file() and (parent / "packages").is_dir():
            return parent
    raise RuntimeError("repo root not found")


_TARGETS = (
    "packages/mechdsl-core/tests/test_e2e_taichi.py",
    "packages/mechdsl-core/tests/plan_tests/recovery_plan_latex_contract/test_p7_2.py",
)


class TestTaskP6_2:
    """Tests for Task P6-2: e2e helper swap deliverable."""

    @pytest.mark.unit
    @pytest.mark.parametrize("relpath", _TARGETS)
    def test_no_local_copy_remains(self, relpath: str) -> None:
        path = _repo_root() / relpath
        assert path.is_file(), f"target file missing: {path}"
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"^def\s+_import_generated_module\b", text, re.MULTILINE), (
            f"{relpath} still defines _import_generated_module locally; "
            "must import from _e2e_helpers"
        )

    @pytest.mark.unit
    @pytest.mark.parametrize("relpath", _TARGETS)
    def test_imports_helper_module(self, relpath: str) -> None:
        path = _repo_root() / relpath
        text = path.read_text(encoding="utf-8")
        assert "_e2e_helpers" in text, f"{relpath} must import from _e2e_helpers (none found)"
