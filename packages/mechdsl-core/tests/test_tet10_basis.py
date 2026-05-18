"""Tests for Task P5-2: Tet10 element (10-node quadratic tetrahedron, 4-point quadrature).

Acceptance criteria:
- AC-1: Partition of unity at all 4 quadrature points.
- AC-2: Quadratic field exactness (reproduces a + b x + c y + d z + quadratic terms to machine precision).
- AC-3: Polynomial-integration test against a known exact value.
- AC-4: ElementType.TET10 round-trips through ProblemIR construction.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from mechdsl.codegen.tet10_tables import (
    SHAPE_AT_QUAD,
    TET10_NODE_COORDS,
    TET10_QUAD_POINTS,
    TET10_QUAD_WEIGHTS,
    shape_functions,
)
from mechdsl.ir.mechanics_ir import (
    BCType,
    BoundaryCondition,
    ElementType,
    Formulation,
    MaterialSpec,
    ProblemIR,
)


class TestTaskP5_2Tet10:
    """Tests for Task P5-2: Tet10 element.

    Acceptance criteria covered: AC-1 (partition of unity), AC-2 (quadratic exactness),
    AC-3 (polynomial integration), AC-4 (ElementType.TET10 in IR).
    """

    @pytest.mark.unit
    def test_tet10_partition_of_unity(self):
        """Verifies: sum of shape functions = 1 at all 4 Gauss points.
        Acceptance criterion: AC-1 — Partition of unity at all 4 quadrature points.
        Passes when: sum_a N_a(xi_q) == 1 within machine tolerance for every q.
        """
        assert SHAPE_AT_QUAD.shape == (4, 10), (
            f"Expected SHAPE_AT_QUAD shape (4, 10), got {SHAPE_AT_QUAD.shape}"
        )

        # Check via pre-evaluated table
        for q in range(4):
            total = float(np.sum(SHAPE_AT_QUAD[q]))
            assert abs(total - 1.0) < 1e-14, (
                f"Partition of unity violated at Gauss point q={q}: sum = {total}"
            )

        # Also check at a variety of interior and boundary points
        extra_pts = [
            (0.1, 0.1, 0.1),
            (0.5, 0.25, 0.1),
            (1.0 / 3.0, 1.0 / 3.0, 1.0 / 6.0),
            (0.0, 0.0, 0.0),  # corner N0
            (1.0, 0.0, 0.0),  # corner N1
            (0.0, 1.0, 0.0),  # corner N2
            (0.0, 0.0, 1.0),  # corner N3
            (0.5, 0.0, 0.0),  # midpoint N4
            (0.5, 0.5, 0.0),  # midpoint N5
            (0.25, 0.25, 0.25),  # centroid
        ]
        for xi, eta, zeta in extra_pts:
            N = shape_functions(xi, eta, zeta)
            total = float(np.sum(N))
            assert abs(total - 1.0) < 1e-14, (
                f"Partition of unity violated at ({xi},{eta},{zeta}): sum = {total}"
            )

    @pytest.mark.unit
    def test_tet10_quadratic_field_exactness(self):
        """Verifies: interpolating an arbitrary quadratic field reproduces it exactly.
        Acceptance criterion: AC-2 — Quadratic field exactness.
        Passes when: max|u_interp - u_exact| < 1e-13 at several interior points.

        The Tet10 basis spans all quadratic polynomials in 3D, so it must
        interpolate any quadratic field exactly via its 10 nodal degrees of freedom.

        Field chosen: f(x, y, z) = 1 + 2x + 3y + 4z + x^2 + x*y + y*z
        """
        # Node coordinates of the reference tet (parametric = physical here)
        X = TET10_NODE_COORDS  # shape (10, 3)

        def u_exact(xyz: np.ndarray) -> float:
            x, y, z = xyz[0], xyz[1], xyz[2]
            return 1.0 + 2.0 * x + 3.0 * y + 4.0 * z + x**2 + x * y + y * z

        # Compute nodal values of the quadratic field at all 10 nodes
        u_nodes = np.array([u_exact(X[a]) for a in range(10)])

        # Test at several interior parametric points
        # On the reference tet, parametric coords = physical coords
        test_pts = [
            (0.1, 0.1, 0.1),
            (0.3, 0.2, 0.15),
            (0.5, 0.2, 0.1),
            (0.25, 0.25, 0.25),  # centroid
            (0.1, 0.05, 0.02),
            # All 4 Gauss points
            (TET10_QUAD_POINTS[0, 0], TET10_QUAD_POINTS[0, 1], TET10_QUAD_POINTS[0, 2]),
            (TET10_QUAD_POINTS[1, 0], TET10_QUAD_POINTS[1, 1], TET10_QUAD_POINTS[1, 2]),
            (TET10_QUAD_POINTS[2, 0], TET10_QUAD_POINTS[2, 1], TET10_QUAD_POINTS[2, 2]),
            (TET10_QUAD_POINTS[3, 0], TET10_QUAD_POINTS[3, 1], TET10_QUAD_POINTS[3, 2]),
        ]

        for xi, eta, zeta in test_pts:
            N = shape_functions(float(xi), float(eta), float(zeta))
            u_interp = float(np.dot(N, u_nodes))
            # On the reference tet, physical coords = parametric coords
            xyz = np.dot(N, X)
            u_ref = u_exact(xyz)
            err = abs(u_interp - u_ref)
            assert err < 1e-13, (
                f"Quadratic exactness failed at ({xi:.4f},{eta:.4f},{zeta:.4f}): "
                f"interp={u_interp:.15g}, exact={u_ref:.15g}, diff={err:.3e}"
            )

    @pytest.mark.unit
    def test_tet10_polynomial_integration(self):
        """Verifies: the 4-point Gauss rule integrates quadratic polynomials exactly.
        Acceptance criterion: AC-3 — Polynomial-integration test against a known exact value.

        Exact integrals over the unit reference tetrahedron (volume = 1/6):
          ∫ L_a * L_b dV = 1/120 for a ≠ b
          ∫ L_a^2     dV = 2/120 = 1/60

        These are all degree-2 polynomials; the 4-point symmetric rule
        integrates them to machine precision.

        We test:
          (1) ∫ L0*L1 dV = ∫ (1-xi-eta-zeta)*xi dV = 1/120
          (2) ∫ L1*L2 dV = ∫ xi*eta dV            = 1/120
          (3) ∫ L1^2  dV = ∫ xi^2 dV              = 1/60
        """
        # Quadrature points in (xi, eta, zeta) = (L1, L2, L3)
        pts = TET10_QUAD_POINTS  # (4, 3)
        wts = TET10_QUAD_WEIGHTS  # (4,)

        # Test 1: ∫ L0 * L1 dV  (off-diagonal, a≠b)
        exact_ab = 1.0 / 120.0
        result_L0L1 = 0.0
        for q in range(4):
            xi, eta, zeta = pts[q]
            L0 = 1.0 - xi - eta - zeta
            L1 = xi
            result_L0L1 += wts[q] * L0 * L1
        assert abs(result_L0L1 - exact_ab) < 1e-15, (
            f"∫ L0*L1 dV: got {result_L0L1:.15g}, expected {exact_ab:.15g}, "
            f"diff={abs(result_L0L1 - exact_ab):.3e}"
        )

        # Test 2: ∫ L1 * L2 dV  (another off-diagonal pair)
        result_L1L2 = 0.0
        for q in range(4):
            xi, eta, zeta = pts[q]
            L1 = xi
            L2 = eta
            result_L1L2 += wts[q] * L1 * L2
        assert abs(result_L1L2 - exact_ab) < 1e-15, (
            f"∫ L1*L2 dV: got {result_L1L2:.15g}, expected {exact_ab:.15g}, "
            f"diff={abs(result_L1L2 - exact_ab):.3e}"
        )

        # Test 3: ∫ L1^2 dV  (diagonal, a=b)
        exact_aa = 1.0 / 60.0
        result_L1sq = 0.0
        for q in range(4):
            xi, eta, zeta = pts[q]
            L1 = xi
            result_L1sq += wts[q] * L1 * L1
        assert abs(result_L1sq - exact_aa) < 1e-15, (
            f"∫ L1^2 dV: got {result_L1sq:.15g}, expected {exact_aa:.15g}, "
            f"diff={abs(result_L1sq - exact_aa):.3e}"
        )

        # Test 4: weights sum to 1/6 (reference-tet volume)
        w_sum = float(np.sum(wts))
        expected_vol = 1.0 / 6.0
        assert abs(w_sum - expected_vol) < 1e-15, (
            f"Sum of quadrature weights = {w_sum:.15g}, expected {expected_vol:.15g}"
        )

        # Test 5: constant function ∫ 1 dV = 1/6
        result_const = float(np.sum(wts))
        assert abs(result_const - expected_vol) < 1e-15, (
            f"∫ 1 dV: got {result_const:.15g}, expected {expected_vol:.15g}"
        )

        # Test 6: quadrature constants are correct
        sqrt5 = math.sqrt(5.0)
        a_expected = (5.0 - sqrt5) / 20.0
        b_expected = (5.0 + 3.0 * sqrt5) / 20.0
        assert abs(float(pts[0, 0]) - a_expected) < 1e-15, "Q0 xi != a"
        assert abs(float(pts[1, 0]) - b_expected) < 1e-15, "Q1 xi != b"
        assert abs(float(wts[0]) - 1.0 / 24.0) < 1e-16, "w0 != 1/24"

    @pytest.mark.unit
    def test_tet10_elementtype_in_ir(self):
        """Verifies: ElementType.TET10 is accepted by ProblemIR and round-trips through construction.
        Acceptance criterion: AC-4 — ElementType.TET10 in IR.
        Passes when: a ProblemIR built with element_type=TET10 validates and preserves the value.
        """
        # Verify TET10 exists in the enum
        assert hasattr(ElementType, "TET10"), "ElementType.TET10 not defined"
        assert ElementType.TET10.value == "tet10"

        # Build a minimal ProblemIR with TET10
        bc = BoundaryCondition(
            name="fixed",
            bc_type=BCType.DIRICHLET,
            field_name="u",
            components=(0, 1, 2),
            value=0.0,
        )
        material = MaterialSpec(
            model="svk",
            params={"E": 200e9, "nu": 0.3},
        )
        ir = ProblemIR(
            dim=3,
            formulation=Formulation.TOTAL_LAGRANGIAN,
            element_type=ElementType.TET10,
            material=material,
            boundaries=(bc,),
        )

        # Round-trip: element_type is preserved
        assert ir.element_type == ElementType.TET10, (
            f"ProblemIR element_type changed: expected TET10, got {ir.element_type}"
        )
        assert ir.element_type.value == "tet10"

        # to_dict / from_dict round-trip
        d = ir.to_dict()
        assert d["element_type"] == "tet10"
        ir2 = ProblemIR.from_dict(d)
        assert ir2.element_type == ElementType.TET10

        # HEX8 and TET4 still work (no regression)
        ir_hex = ProblemIR(
            dim=3,
            formulation=Formulation.TOTAL_LAGRANGIAN,
            element_type=ElementType.HEX8,
            material=material,
            boundaries=(bc,),
        )
        assert ir_hex.element_type == ElementType.HEX8

        ir_tet4 = ProblemIR(
            dim=3,
            formulation=Formulation.TOTAL_LAGRANGIAN,
            element_type=ElementType.TET4,
            material=material,
            boundaries=(bc,),
        )
        assert ir_tet4.element_type == ElementType.TET4
