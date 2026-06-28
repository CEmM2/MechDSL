"""NRPyLaTeX -> mechdsl symbolic round-trip tests for equation semantics."""

from __future__ import annotations

import pytest

from mechdsl.frontend import parse_with_math
from mechdsl.frontend.math_parser import MathParseError, parse_math
from mechdsl.symbolic.bridge import (
    SymbolicEquation,
    SymbolicNode,
    convert_equations,
    convert_namespace,
)

_FINITE_DEFORMATION = r"""
% declare FDD --dim 3
% declare GDD --dim 3
% declare CDD --dim 3
% declare SDD --dim 3
% declare PDD --dim 3
% declare \mu \lambda --const
F_{i I} = G_{i I}
C_{I J} = F_{i I} F_{i J}
J = \det{F}
\Psi = \frac{\lambda}{2} (\log{J})^2 - \mu \log{J} + \frac{\mu}{2}(C_{I I} - 3)
S_{I J} = \lambda \log{J} C_{I J}^{-1} + \mu C_{I J}
P_{i I} = F_{i J} S_{J I}
"""

_J2_YIELD = r"""
% declare sUU --dim 3
% declare sDD --dim 3
% declare sigmaY --const
f = \sqrt{\frac{3}{2} s^{i j} s_{i j}} - sigmaY
"""

_TWO_POINT = "% declare FUU --dim 3\n% declare AUU --dim 3\nA^{i I} = F^{i I}\n"


def _equation_by_lhs(equations: tuple[SymbolicEquation, ...], lhs: str) -> SymbolicEquation:
    for equation in equations:
        if equation.lhs == lhs:
            return equation
    raise AssertionError(f"missing equation with LHS {lhs!r}")


@pytest.mark.docs
@pytest.mark.integration
def test_round_trip_finite_deformation_equations_are_preserved() -> None:
    """Finite-deformation MVP equations preserve source-level semantics."""
    result = parse_math(_FINITE_DEFORMATION)
    nodes = convert_namespace(result.tensors, result.classifications)
    equations = convert_equations(result.equations)

    assert nodes["FDD"].kind == "tensor2"
    assert nodes["CDD"].kind == "tensor2"

    c_eq = _equation_by_lhs(equations, "C_{I J}")
    assert c_eq.free_indices == ("I", "J")
    assert c_eq.contracted_indices == ("i",)
    assert c_eq.role == "auxiliary_definition"

    j_eq = _equation_by_lhs(equations, "J")
    assert j_eq.rhs == r"\det{F}"
    assert j_eq.free_indices == ()

    psi_eq = _equation_by_lhs(equations, r"\Psi")
    assert r"\log{J}" in psi_eq.rhs
    assert psi_eq.role == "strain_energy"

    s_eq = _equation_by_lhs(equations, "S_{I J}")
    assert s_eq.free_indices == ("I", "J")
    assert s_eq.role == "stress_measure"

    p_eq = _equation_by_lhs(equations, "P_{i I}")
    assert p_eq.free_indices == ("I", "i")
    assert p_eq.contracted_indices == ("J",)
    assert p_eq.role == "stress_measure"


@pytest.mark.docs
@pytest.mark.integration
def test_round_trip_j2_yield_scalar_expression_is_preserved() -> None:
    """J2 scalar yield expression keeps sqrt/contraction semantics."""
    result = parse_math(_J2_YIELD)
    nodes = convert_namespace(result.tensors, result.classifications)
    equations = convert_equations(result.equations)

    assert nodes["sUU"].kind == "tensor2"
    assert nodes["sDD"].kind == "tensor2"
    assert nodes["sigmaY"].kind == "constant"

    f_eq = _equation_by_lhs(equations, "f")
    assert f_eq.role == "yield_function"
    assert f_eq.free_indices == ()
    assert f_eq.contracted_indices == ("i", "j")
    assert r"\sqrt" in f_eq.rhs


@pytest.mark.docs
@pytest.mark.integration
def test_round_trip_two_point_F_iI_preserves_indices() -> None:
    """``A^{iI} = F^{iI}`` round-trips with spatial/material axes."""
    result = parse_math(_TWO_POINT)
    nodes = convert_namespace(result.tensors, result.classifications)
    equations = convert_equations(result.equations)

    f = nodes["FUU"]
    a = nodes["AUU"]
    assert f.classification is not None
    assert 0 in f.classification.spatial_axes
    assert 1 in f.classification.material_axes
    assert a.classification is not None
    assert 0 in a.classification.spatial_axes
    assert 1 in a.classification.material_axes

    equation = _equation_by_lhs(equations, "A^{i I}")
    assert equation.free_indices == ("I", "i")
    assert equation.contracted_indices == ()


@pytest.mark.docs
@pytest.mark.integration
def test_invalid_spatial_material_tensor_fails_before_lowering() -> None:
    """Known spatial tensors may not carry material indices."""
    bad = "% declare sigmaDD --dim 3\n% declare FDD --dim 3\n\\sigma_{i I} = F_{i I}\n"
    with pytest.raises(MathParseError, match="spatial tensor"):
        parse_math(bad)


@pytest.mark.docs
@pytest.mark.integration
def test_unsupported_full_grammar_node_fails_with_phase_pointer() -> None:
    """Non-MVP functions are explicit full-grammar deferrals."""
    unsupported = "% declare a --const\nb = \\sin{a}\n"
    with pytest.raises(MathParseError) as excinfo:
        parse_math(unsupported)
    assert "full-grammar phase" in str(excinfo.value)
    assert "post_recovery_plan Phase 4" in str(excinfo.value)


@pytest.mark.docs
@pytest.mark.integration
def test_round_trip_through_frontend_pipeline() -> None:
    """Existing frontend integration remains backward compatible."""
    src = (
        "% mechanics dim 3\n"
        "% mechanics cell hex8\n"
        "% mechanics formulation total_lagrangian\n"
        "% mechanics material svk --E 200e3 --nu 0.3\n"
        "% mechanics boundary Gamma_u --type dirichlet --value 0\n"
        "% declare FUU --dim 3\n"
        "% declare AUU --dim 3\n"
        "$A^{i I} = F^{i I}$\n"
    )
    ctx = parse_with_math(src)
    assert "math" in ctx
    tensors = ctx["math"]["tensors"]
    assert "FUU" in tensors
    assert isinstance(tensors["FUU"], SymbolicNode)
    assert tensors["FUU"].rank == 2
