"""Tests for Task P3-1 (PlanJune14 Phase 3).

Route the ``local_tangent`` einsum through the Layer-4b optimizer:
``lowering/einsum_extract.py`` -> ``codegen/einsum_optimizer.py`` ->
a :class:`~mechdsl.codegen.artifact.ContractionPlan` for the matrix-free
tangent matvec ``K(u)·v``, passing the JIT-budget counter. The contraction is
optimiser-produced, not hand-rolled.

Design note (P3-1): the matvec is exposed as a *dedicated builder*
(:func:`build_tangent_matvec_plan`) rather than a fourth key in
``extract_einsum_specs``. The three-key contract of ``extract_einsum_specs``
is pinned by existing tests/goldens; adding a key there would break them.
The builder derives the matvec einsum ``qaI,qiIjJ,qbJ,bj->qai`` from the same
ElementIR geometry and routes it through ``optimize_contraction``.
"""

from __future__ import annotations

import numpy as np
import opt_einsum
import pytest

from mechdsl.codegen.artifact import ContractionPlan
from mechdsl.codegen.einsum_optimizer import MAX_LINES_TI_FUNC, Tier, estimate_unrolled_lines
from mechdsl.ir.element_ir import create_hex8_element_ir
from mechdsl.lowering.einsum_extract import (
    TANGENT_MATVEC_APPLY_EINSUM,
    build_tangent_matvec_plan,
    extract_einsum_specs,
    tangent_matvec_apply_spec,
)

# ---------------------------------------------------------------------------
# Helpers — concrete SVK Hex8 arrays for the numeric AC-3 test
# ---------------------------------------------------------------------------


def _svk_material_tangent(lam: float, mu: float) -> np.ndarray:
    """St. Venant–Kirchhoff reference material tangent A_{iIjJ}.

    For SVK the constant fourth-order elasticity tensor in index form is
    ``C_{IJKL} = lam delta_{IJ} delta_{KL} + mu (delta_{IK} delta_{JL}
    + delta_{IL} delta_{JK})``. We use it directly as the consistent tangent
    block ``A(i=I, I, j=K, J=L)`` so the matvec test exercises a physically
    meaningful, symmetric tangent rather than noise.
    """
    d = np.eye(3)
    # C_{IJKL}
    c = (
        lam * np.einsum("ij,kl->ijkl", d, d)
        + mu * np.einsum("ik,jl->ijkl", d, d)
        + mu * np.einsum("il,jk->ijkl", d, d)
    )
    return c


def _svk_hex8_arrays(seed: int = 0) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Concrete ``(dN, A, v)`` arrays for an SVK Hex8 element.

    Returns
    -------
    dN : (n_qp, n_nodes, dim)
        Reference shape-function gradients at each quadrature point.
    A : (n_qp, dim, dim, dim, dim)
        The (constant, per-qp broadcast) SVK material tangent.
    v : (n_nodes, dim)
        A random direction field.
    """
    element_ir = create_hex8_element_ir()
    n_qp = element_ir.quadrature.n_points
    n_nodes = element_ir.n_nodes
    dim = element_ir.dim

    # Real Hex8 reference-gradient table dN(q,a,I).
    dN = np.empty((n_qp, n_nodes, dim), dtype=np.float64)
    for q, (xi, eta, zeta) in enumerate(element_ir.quadrature.points):
        dN[q] = element_ir.basis.gradient(xi, eta, zeta)

    lam, mu = 1.15, 0.77  # arbitrary Lamé constants (kPa-scale)
    a_single = _svk_material_tangent(lam, mu)
    A = np.broadcast_to(a_single, (n_qp, dim, dim, dim, dim)).copy()

    rng = np.random.default_rng(seed)
    v = rng.standard_normal((n_nodes, dim))
    return dN, A, v


class TestTaskP3_1:
    """Tests for Task P3-1: tangent contraction through the einsum optimizer. AC 1-3."""

    @pytest.mark.unit
    def test_einsum_extract_returns_local_tangent_string(self):
        """AC-1: einsum_extract yields the expected local_tangent subscripts for SVK Hex8."""
        element_ir = create_hex8_element_ir()

        # The full element tangent K(q,a,i,b,j) — the local_tangent contraction.
        specs = extract_einsum_specs(element_ir)
        assert specs["tangent_matvec"].einsum_string == "qaI,qiIjJ,qbJ->qaibj"

        # The matrix-free matvec view folds v(b,j) into that contraction.
        matvec_spec = tangent_matvec_apply_spec(element_ir)
        assert matvec_spec.einsum_string == "qaI,qiIjJ,qbJ,bj->qai"
        assert matvec_spec.einsum_string == TANGENT_MATVEC_APPLY_EINSUM
        # Operand order is (dN, A, dN, v); result is the per-qp Kv(q,a,i).
        assert matvec_spec.operand_shapes == (
            (8, 8, 3),
            (8, 3, 3, 3, 3),
            (8, 8, 3),
            (8, 3),
        )
        assert matvec_spec.result_shape == (8, 8, 3)

    @pytest.mark.unit
    def test_optimizer_yields_contraction_plan_within_budget(self):
        """AC-2: the optimizer produces a ContractionPlan that passes the JIT-budget counter."""
        element_ir = create_hex8_element_ir()
        plan = build_tangent_matvec_plan(element_ir)

        # It is an actual ContractionPlan carrying the opt_einsum path.
        assert isinstance(plan, ContractionPlan)
        assert plan.einsum_string == TANGENT_MATVEC_APPLY_EINSUM
        assert len(plan.contraction_path) >= 1  # path recorded, not hand-rolled

        # Re-run the budget counter over the recorded path: must be within the
        # 512-line @ti.func budget and Tier <= 2 (no Tier-3 restructuring).
        matvec_spec = tangent_matvec_apply_spec(element_ir)
        lines = estimate_unrolled_lines(
            matvec_spec.einsum_string,
            list(matvec_spec.operand_shapes),
            plan.contraction_path,
        )
        assert lines <= MAX_LINES_TI_FUNC
        assert plan.tier <= int(Tier.TIER_2)

    @pytest.mark.unit
    def test_matvec_contraction_equals_dense_tangent_applied_to_v(self):
        """AC-3: the matvec contraction numerically equals the dense local_tangent applied to v."""
        element_ir = create_hex8_element_ir()
        dN, A, v = _svk_hex8_arrays(seed=0)

        # Ground truth: form the full element tangent K(q,a,i,b,j) then apply v.
        k_full = np.einsum("qaI,qiIjJ,qbJ->qaibj", dN, A, dN)
        kv_dense = np.einsum("qaibj,bj->qai", k_full, v)

        # Optimiser path: contract directly via the recorded opt_einsum path.
        plan = build_tangent_matvec_plan(element_ir)
        kv_opt = opt_einsum.contract(
            TANGENT_MATVEC_APPLY_EINSUM,
            dN,
            A,
            dN,
            v,
            optimize=plan.contraction_path,
        )

        assert kv_opt.shape == (8, 8, 3)
        assert np.max(np.abs(kv_opt - kv_dense)) < 1e-12
