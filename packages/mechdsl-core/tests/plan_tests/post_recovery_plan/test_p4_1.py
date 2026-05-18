"""Tests for Task P4-1: frontend/math_parser.py wrapping nrpylatex.

Acceptance criteria covered:
1. Parses an indexed expression without error (SVK-flavoured rank-2 copy).
2. Mixed F^{iI} two-point: spatial/material index distinction is
   classified post-parse by enforce_index_convention.
3. Unsupported node raises with explicit Phase-4 reference.
"""

from __future__ import annotations

import pytest

from mechdsl.frontend.math_parser import (
    MathParseError,
    MathParseResult,
    parse_math,
)

_RANK2_COPY = "% declare FUU --dim 3\n% declare AUU --dim 3\nA^{i j} = F^{i j}\n"

_TWO_POINT = "% declare FUU --dim 3\n% declare AUU --dim 3\nA^{i I} = F^{i I}\n"


class TestTaskP4_1:
    """Tests for Task P4-1: math_parser.py wrapping nrpylatex.

    Acceptance criteria covered: 1, 2, 3.
    """

    @pytest.mark.unit
    def test_rank2_indexed_expression_parses(self) -> None:
        """parse_math returns a populated MathParseResult for a balanced
        rank-2 tensor copy ``A^{ij} = F^{ij}``. Stand-in for the
        SVK-PK1 surface — full SVK requires bound-index + scalar mix
        that nrpylatex 1.4.0 grammar does not accept end-to-end (see
        module docstring).
        """
        result = parse_math(_RANK2_COPY)
        assert isinstance(result, MathParseResult)
        assert "FUU" in result.tensors
        assert "AUU" in result.tensors
        assert result.tensors["FUU"].rank == 2
        assert result.tensors["AUU"].rank == 2

    @pytest.mark.unit
    def test_two_point_tensor_index_distinction_preserved(self) -> None:
        """``F^{iI}`` post-parse classification reports axis 0 as
        spatial and axis 1 as material (per 07-CONVENTIONS.md letter
        case rule — nrpylatex itself does not enforce this).
        """
        result = parse_math(_TWO_POINT)
        f_class = result.classifications["FUU"]
        assert 0 in f_class.spatial_axes, f"axis 0 of FUU should be spatial (i), got {f_class}"
        assert 1 in f_class.material_axes, f"axis 1 of FUU should be material (I), got {f_class}"

    @pytest.mark.unit
    def test_unsupported_node_raises_with_phase_pointer(self) -> None:
        """A LaTeX block that exercises an nrpylatex grammar feature
        outside the supported subset (e.g. ``\\det``) raises
        MathParseError whose message names ``post_recovery_plan
        Phase 4``.
        """
        unsupported = "% declare FUU --dim 3\nJ = \\mathrm{det}(F)\n"
        with pytest.raises(MathParseError) as excinfo:
            parse_math(unsupported)
        assert "post_recovery_plan Phase 4" in str(excinfo.value), (
            f"missing Phase-4 pointer in error: {excinfo.value}"
        )

    @pytest.mark.unit
    def test_index_convention_violation_raises(self) -> None:
        """A tensor that appears with both spatial and material letters
        on the same axis raises MathParseError with the Phase-4 pointer.
        Forces correct convention usage at the front door.
        """
        # Two parses; nrpylatex namespace is reset between them, but our
        # convention check operates on a single parse — so synthesise a
        # block where F^{ij} (spatial) and F^{IJ} (material) coexist on
        # rank-2 F.
        bad = "% declare FUU --dim 3\n% declare AUU --dim 3\nA^{i j} = F^{i j} + F^{I J}\n"
        with pytest.raises(MathParseError) as excinfo:
            parse_math(bad)
        assert "post_recovery_plan Phase 4" in str(excinfo.value)
