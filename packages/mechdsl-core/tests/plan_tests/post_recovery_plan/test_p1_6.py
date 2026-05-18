"""Tests for Task P1-6: test_p7_2 directive-only Neumann path."""

from __future__ import annotations

from pathlib import Path

import pytest

_TARGET = (
    Path(__file__).resolve().parents[2]
    / "plan_tests"
    / "recovery_plan_latex_contract"
    / "test_p7_2.py"
)


class TestTaskP1_6:
    """Tests for Task P1-6: test_p7_2 directive-only Neumann path.

    The acceptance work for this task is the rewrite of test_p7_2 itself
    (verified by `uv run pytest .../test_p7_2.py -v`). The cases below
    audit the rewrite's structural shape so a future regression that
    re-introduces the manual-injection pattern surfaces here.
    """

    @pytest.mark.unit
    def test_target_file_exists(self):
        assert _TARGET.is_file(), f"missing {_TARGET}"

    @pytest.mark.unit
    def test_target_no_longer_constructs_f_ext_directly(self):
        """Acceptance criterion #1: the manual `mod.f_ext.from_numpy(...)`
        injection is gone; the kernel emitted by P1-5 drives the load."""
        text = _TARGET.read_text(encoding="utf-8")
        assert "mod.f_ext.from_numpy" not in text, (
            "test_p7_2 must drive f_ext via the emitted "
            "init_f_ext_from_neumann_load kernel, not via direct injection"
        )
        assert "mod.init_f_ext_from_neumann_load" in text, (
            "test_p7_2 must call the directive-driven f_ext kernel"
        )

    @pytest.mark.unit
    def test_traction_string_gap_comment_removed(self):
        """Acceptance criterion #3: the placeholder traction-string-gap
        comment that flagged the missing directive flow (closes follow-up
        item 9) is no longer present."""
        text = _TARGET.read_text(encoding="utf-8")
        assert "placeholder for symbolic binding" not in text, (
            "the obsolete traction-string-gap placeholder comment must be "
            "removed once P1-1..P1-5 land the directive flow"
        )
        assert "the numeric f_ext is provided here as the contract" not in text

    @pytest.mark.unit
    def test_latex_directive_carries_numeric_traction_and_surface(self):
        """The Neumann directive in CANONICAL_LATEX_SOURCE uses the new
        numeric 3-vector traction form and an explicit `--surface` tag,
        exercising P1-2's directive parser extension."""
        text = _TARGET.read_text(encoding="utf-8")
        assert '--traction "1 0 0"' in text or '--traction "0 0 -1000"' in text, (
            "expected a numeric 3-vector traction in CANONICAL_LATEX_SOURCE"
        )
        assert "--surface x1" in text or "--surface " in text, (
            "expected an explicit --surface tag on the Neumann directive"
        )

    @pytest.mark.unit
    def test_test_p7_2_asserts_f_ext_kernel_present(self):
        """The rewrite asserts compile_latex returns a non-None
        f_ext_kernel — that's the contract P1-5 introduced and the
        directive-only path depends on."""
        text = _TARGET.read_text(encoding="utf-8")
        assert "bundle.f_ext_kernel is not None" in text
        assert "init_f_ext_from_neumann_load" in text
