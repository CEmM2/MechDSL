"""Tests for Task P3-2: docstring-presence regression test.

P3-2's deliverable IS a new test file
(packages/mechdsl-core/tests/test_compile_latex_docstring.py). This file
is the meta-spec for that deliverable: it asserts the deliverable file
exists, lives at the canonical path, and exercises compile_latex.__doc__
with substring assertions on BoundaryCondition and the f_ext
caller-provisioning phrase.
"""

from __future__ import annotations

from pathlib import Path

import pytest


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").is_file() and (parent / "packages").is_dir():
            return parent
    raise RuntimeError("repo root not found")


def _deliverable_path() -> Path:
    return _repo_root() / "packages" / "mechdsl-core" / "tests" / "test_compile_latex_docstring.py"


class TestTaskP3_2:
    """Tests for Task P3-2: docstring-presence test deliverable."""

    @pytest.mark.docs
    def test_deliverable_test_file_exists(self) -> None:
        path = _deliverable_path()
        assert path.is_file(), f"Phase 3 P3-2 deliverable missing: expected file at {path}"
        assert path.stat().st_size > 0, f"{path} is empty"

    @pytest.mark.docs
    def test_deliverable_file_asserts_boundary_condition_substring(self) -> None:
        text = _deliverable_path().read_text(encoding="utf-8")
        # The deliverable must reference BoundaryCondition AND exercise
        # compile_latex.__doc__ (so a docstring removal would actually fail
        # the test rather than passing because the source file mentions BC).
        assert "BoundaryCondition" in text, (
            "deliverable test must assert BoundaryCondition substring presence"
        )
        assert "compile_latex" in text, "deliverable test must reference compile_latex"
        assert "__doc__" in text or "inspect.getdoc" in text, (
            "deliverable test must read compile_latex.__doc__ "
            "(via attribute access or inspect.getdoc)"
        )

    @pytest.mark.docs
    def test_deliverable_file_asserts_f_ext_caller_provisioning(self) -> None:
        text = _deliverable_path().read_text(encoding="utf-8")
        assert "f_ext" in text, "deliverable test must assert f_ext substring presence"
        # Caller-provisioning synonym set — any one suffices.
        synonyms = ("caller", "supplied", "supplies", "provisioning")
        assert any(token in text for token in synonyms), (
            f"deliverable test must assert at least one caller-provisioning synonym ({synonyms})"
        )
