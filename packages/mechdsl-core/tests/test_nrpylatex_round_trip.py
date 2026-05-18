"""nrpylatex → mechdsl symbolic round-trip tests.

post_recovery_plan Phase 4 (P4-4). The round trip exercised here is
the **import chain**:

    LaTeX-math source
        → mechdsl.frontend.math_parser.parse_math (nrpylatex AST)
        → mechdsl.symbolic.bridge.convert_namespace (SymbolicNode)
        → mechdsl.frontend.parse_with_math (frontend integration)

Three case families are pinned: a SVK-flavoured rank-2 contraction
surrogate, a J2 yield-style scalar contraction, and a two-point
``F^{iI}`` index-distinction case.

The plan's stronger acceptance criterion ("Round-trip test verifies
emitted Taichi residual matches handwritten reference within
tolerance") is **deferred** at this layer: nrpylatex 1.4.0's grammar
does not register ``\\det`` or ``\\log{}`` as known intrinsic functions,
so SVK PK1 / J2 yield in their full closed form do not parse without
a surrogate. Each test below documents the surrogate it uses and
points at the deferral.
"""

from __future__ import annotations

import pytest

from mechdsl.frontend import parse_with_math
from mechdsl.frontend.math_parser import parse_math
from mechdsl.symbolic.bridge import SymbolicNode, convert_namespace

_SVK_LIKE = "% declare FUU --dim 3\n% declare AUU --dim 3\nA^{i j} = F^{i j}\n"
"""SVK-PK1 surrogate: rank-2 tensor copy. Stands in for
``P^{ij} = 2μ ε^{ij} + λ ε^{kk} δ^{ij}`` until \\det / \\log
intrinsics are registered (deferred to a later post-recovery phase)."""

_J2_YIELD_LIKE = (
    "% declare sigmaUU --dim 3\n% declare sigmaDD --dim 3\nf = \\sigma^{i j} \\sigma_{i j}\n"
)
"""J2 yield surrogate: scalar contraction
``f = σ^{ij} σ_{ij}`` (norm-squared). Stands in for the closed-form
``f = sqrt(3/2 s:s) - σ_y`` until \\sqrt over a full deviator is
parseable."""

_TWO_POINT = "% declare FUU --dim 3\n% declare AUU --dim 3\nA^{i I} = F^{i I}\n"
"""Two-point F^{iI} index distinction case."""


@pytest.mark.docs
@pytest.mark.integration
def test_round_trip_svk_pk1_rank2_copy() -> None:
    """SVK-PK1 surrogate parses + bridges. Rank-2 tensors land as
    SymbolicNode kind='tensor2' on both sides of the assignment."""
    result = parse_math(_SVK_LIKE)
    nodes = convert_namespace(result.tensors, result.classifications)
    assert nodes["FUU"].kind == "tensor2"
    assert nodes["AUU"].kind == "tensor2"
    assert nodes["FUU"].rank == 2
    assert nodes["AUU"].rank == 2


@pytest.mark.docs
@pytest.mark.integration
def test_round_trip_j2_yield_norm_contraction() -> None:
    """J2-yield surrogate: σ^{ij} σ_{ij} is a scalar (rank 0) result.
    Both σUU and σDD round-trip to tensor2 nodes; ``f`` is the
    contracted scalar.
    """
    result = parse_math(_J2_YIELD_LIKE)
    nodes = convert_namespace(result.tensors, result.classifications)
    assert nodes["sigmaUU"].kind == "tensor2"
    assert nodes["sigmaDD"].kind == "tensor2"
    assert nodes["f"].kind == "scalar"
    assert nodes["f"].rank == 0


@pytest.mark.docs
@pytest.mark.integration
def test_round_trip_two_point_F_iI_preserves_indices() -> None:
    """``A^{iI} = F^{iI}`` round-trips with axis 0 spatial,
    axis 1 material on both tensors.
    """
    result = parse_math(_TWO_POINT)
    nodes = convert_namespace(result.tensors, result.classifications)
    f = nodes["FUU"]
    a = nodes["AUU"]
    assert f.classification is not None
    assert 0 in f.classification.spatial_axes
    assert 1 in f.classification.material_axes
    assert a.classification is not None
    assert 0 in a.classification.spatial_axes
    assert 1 in a.classification.material_axes


@pytest.mark.docs
@pytest.mark.integration
def test_round_trip_through_frontend_pipeline() -> None:
    """End-to-end: a directive-bearing source with a ``$...$`` math
    block flows through ``parse_with_math`` and produces a
    ``context['math']['tensors']`` map with SymbolicNode entries.
    """
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
