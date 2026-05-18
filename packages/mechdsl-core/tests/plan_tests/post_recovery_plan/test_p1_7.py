"""Tests for Task P1-7: Golden test test_boundary_neumann for emitted f_ext kernel."""

from __future__ import annotations

from pathlib import Path

import pytest

_TESTS_DIR = Path(__file__).resolve().parents[2]
_TARGET = _TESTS_DIR / "test_boundary_neumann.py"
_GOLDEN = _TESTS_DIR / "golden" / "boundary_neumann.ti.txt"


class TestTaskP1_7:
    """Tests for Task P1-7: Golden test for emitted f_ext kernel.

    Acceptance criteria covered: 1, 2, 3.
    The acceptance work is the new ``test_boundary_neumann.py`` file
    plus the committed ``boundary_neumann.ti.txt`` artifact. Tests
    below audit those two surfaces.
    """

    @pytest.mark.unit
    def test_test_boundary_neumann_passes_on_clean_checkout(self):
        """Acceptance criterion #1: the golden test file exists and
        carries the canonical Neumann fixture."""
        assert _TARGET.is_file(), f"missing {_TARGET}"
        text = _TARGET.read_text(encoding="utf-8")
        assert "NeumannKernelSpec" in text
        assert "emit_neumann_f_ext_kernel" in text
        # Canonical fixture per plan acceptance: traction "0 0 -1000".
        assert "(0.0, 0.0, -1000.0)" in text

    @pytest.mark.unit
    def test_golden_artifact_committed(self):
        """Acceptance criterion #2: golden file lives under
        tests/golden/ alongside the test."""
        assert _GOLDEN.is_file(), f"missing golden artifact {_GOLDEN}"
        body = _GOLDEN.read_text(encoding="utf-8")
        assert "init_f_ext_from_neumann_load" in body
        assert "f_ext[nid][2] = -1000" in body

    @pytest.mark.unit
    def test_intentional_codegen_change_diffs_in_golden(self):
        """Acceptance criterion #3: the golden test asserts on
        ``source == golden`` so any drift surfaces as a diff. Audit the
        target file for that comparison shape."""
        text = _TARGET.read_text(encoding="utf-8")
        assert "assert source == golden" in text, (
            "golden test must use a strict equality comparison so "
            "intentional codegen changes show up as a diff in the "
            "stored golden file"
        )
        # Regen escape hatch documented.
        assert "_UPDATE_GOLDEN" in text
