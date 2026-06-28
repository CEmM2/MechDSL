"""Focused fgram Phase 4 P4-1 coverage."""

from __future__ import annotations

import pytest

from mechdsl.frontend.math_parser import (
    MathParseError,
    extract_equations,
    parse_math,
)
from mechdsl.symbolic.bridge import convert_equations


@pytest.mark.integration
def test_p4_1_equation_bridge_preserves_line_role_and_indices() -> None:
    source = r"""
% declare FDD --dim 3
% declare SDD --dim 3
% declare PDD --dim 3
P_{i I} = F_{i J} S_{J I}
"""
    result = parse_math(source)
    equations = convert_equations(result.equations)

    assert len(equations) == 1
    equation = equations[0]
    assert equation.lhs == "P_{i I}"
    assert equation.rhs == "F_{i J} S_{J I}"
    assert equation.free_indices == ("I", "i")
    assert equation.contracted_indices == ("J",)
    assert equation.role == "stress_measure"
    assert equation.source_line == 5


@pytest.mark.integration
def test_p4_1_invalid_material_index_on_spatial_stress_is_actionable() -> None:
    source = "% declare sigmaDD --dim 3\n% declare FDD --dim 3\n\\sigma_{i I} = F_{i I}\n"

    with pytest.raises(MathParseError) as excinfo:
        parse_math(source)

    message = str(excinfo.value)
    assert "spatial tensor" in message
    assert "post_recovery_plan Phase 4" in message


@pytest.mark.integration
def test_p4_1_non_letter_lhs_classifies_without_error() -> None:
    """A LHS that does not begin with a letter must not crash role inference."""
    (equation,) = extract_equations("2 a = b + c\n")

    assert equation.role == "auxiliary_definition"


@pytest.mark.integration
def test_p4_1_directive_keyword_overrides_symbol_heuristic() -> None:
    """A role directive in the block is authoritative over LHS-symbol heuristics."""
    # LHS ``S`` would heuristically be a stress measure, but the block carries a
    # strain_energy directive, which must win.
    (equation,) = extract_equations("% mechanics strain_energy\nS = a + b\n")

    assert equation.role == "strain_energy"
