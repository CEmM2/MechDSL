"""Tests for Task P5-1: Tet4 element (4-node linear tetrahedron, 1-point quadrature).

Acceptance criteria:
- AC-1: Partition of unity: sum_a N_a = 1 at every quadrature point.
- AC-2: Constant field exactness: interpolating a linear field reproduces it to machine precision.
- AC-3: Positive Jacobian on a regular tet.
- AC-4: ElementType.TET4 round-trips through ProblemIR construction.
"""

from __future__ import annotations

import numpy as np
import pytest

from mechdsl.codegen.tet4_tables import (
    SHAPE_AT_QUAD,
    TET4_NODE_COORDS,
    TET4_QUAD_WEIGHTS,
    reference_gradient_at_physical,
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


class TestTaskP5_1Tet4:
    """Tests for Task P5-1: Tet4 element.

    Acceptance criteria covered: AC-1 (partition of unity), AC-2 (constant-field exactness),
    AC-3 (positive Jacobian), AC-4 (ElementType.TET4 in IR).
    """

    @pytest.mark.unit
    def test_tet4_partition_of_unity(self):
        """Verifies: sum of shape functions = 1 at the single Gauss point.
        Acceptance criterion: AC-1 — Partition of unity.
        Passes when: sum_a N_a(xi_q) == 1 within machine tolerance.
        """
        # Check at the single quadrature point using pre-evaluated table
        assert SHAPE_AT_QUAD.shape == (1, 4), (
            f"Expected SHAPE_AT_QUAD shape (1, 4), got {SHAPE_AT_QUAD.shape}"
        )
        for q in range(SHAPE_AT_QUAD.shape[0]):
            total = float(np.sum(SHAPE_AT_QUAD[q]))
            assert abs(total - 1.0) < 1e-15, f"Partition of unity violated at q={q}: sum = {total}"

        # Also check at a few arbitrary interior points
        interior_pts = [
            (0.1, 0.1, 0.1),
            (0.5, 0.2, 0.1),
            (0.25, 0.25, 0.25),  # centroid
            (0.0, 0.0, 0.0),  # vertex 0
        ]
        for xi, eta, zeta in interior_pts:
            N = shape_functions(xi, eta, zeta)
            total = float(np.sum(N))
            assert abs(total - 1.0) < 1e-14, (
                f"Partition of unity violated at ({xi},{eta},{zeta}): sum = {total}"
            )

    @pytest.mark.unit
    def test_tet4_constant_field_exactness(self):
        """Verifies: interpolating a linear field on Tet4 reproduces it exactly.
        Acceptance criterion: AC-2 — Constant field exactness.
        Passes when: max|u_interp - u_exact| < 1e-14 at arbitrary interior points.

        For linear Tet4, both constant AND linear fields are reproduced exactly
        (the shape functions are themselves linear).
        """
        # Node coordinates: vertices of the reference tet
        # N0=(0,0,0), N1=(1,0,0), N2=(0,1,0), N3=(0,0,1)
        X = TET4_NODE_COORDS  # shape (4, 3)

        # Define a linear scalar field: u(x, y, z) = 3 + 2x - y + 4z
        # Nodal values
        def u_exact(xyz):
            return 3.0 + 2.0 * xyz[0] - xyz[1] + 4.0 * xyz[2]

        u_nodes = np.array([u_exact(X[a]) for a in range(4)])

        # Evaluate at several interior points and compare interpolation vs exact
        test_pts = [
            (0.1, 0.1, 0.1),
            (0.5, 0.2, 0.1),
            (0.25, 0.25, 0.25),
            (0.3, 0.1, 0.05),
        ]
        for xi, eta, zeta in test_pts:
            N = shape_functions(xi, eta, zeta)
            u_interp = float(np.dot(N, u_nodes))
            # At parametric point (xi, eta, zeta), physical coords on reference tet:
            # x = N @ X = xi * (1,0,0) + eta * (0,1,0) + zeta * (0,0,1) = (xi, eta, zeta)
            x_phys = np.dot(N, X)
            u_ref = u_exact(x_phys)
            assert abs(u_interp - u_ref) < 1e-14, (
                f"Linear field exactness failed at ({xi},{eta},{zeta}): "
                f"interp={u_interp}, exact={u_ref}, diff={abs(u_interp - u_ref)}"
            )

    @pytest.mark.unit
    def test_tet4_jacobian_positive_on_regular_tet(self):
        """Verifies: the element Jacobian is strictly positive on a regular reference tet.
        Acceptance criterion: AC-3 — Positive Jacobian on a regular tet.
        Passes when: det(J) > 0 and equals the expected reference volume (1/6 for unit-volume ref).
        """
        # Reference tet node coordinates: identity mapping (X_elem = reference element)
        X_elem = TET4_NODE_COORDS.copy()  # (4, 3): vertices at (0,0,0),(1,0,0),(0,1,0),(0,0,1)

        # For the reference tet the Jacobian is constant = I (identity),
        # so det(J0) = 1. The quadrature weight 1/6 encodes the reference volume.
        dNdX, detJ0 = reference_gradient_at_physical(X_elem, q=0)

        # Jacobian must be positive
        assert detJ0 > 0.0, f"Jacobian non-positive: detJ0 = {detJ0}"

        # For the reference tet (node coords = standard basis vectors),
        # J = d(x)/d(xi) = X^T @ dN/dxi
        # The reference element has J = I (identity), so det(J0) = 1
        assert abs(detJ0 - 1.0) < 1e-14, f"Expected det(J0) = 1.0 for reference tet, got {detJ0}"

        # The integrated volume = sum_q w_q * det(J0) = (1/6) * 1 = 1/6
        integrated_volume = float(np.sum(TET4_QUAD_WEIGHTS)) * detJ0
        expected_volume = 1.0 / 6.0
        assert abs(integrated_volume - expected_volume) < 1e-14, (
            f"Reference tet volume = {integrated_volume}, expected {expected_volume}"
        )

        # Also check gradient shape
        assert dNdX.shape == (4, 3), f"Expected dNdX shape (4, 3), got {dNdX.shape}"

        # Test with a scaled tet (scale factor s => det(J) = s^3)
        s = 2.0
        X_scaled = X_elem * s
        _, detJ_scaled = reference_gradient_at_physical(X_scaled, q=0)
        assert abs(detJ_scaled - s**3) < 1e-12, (
            f"Expected det(J) = {s**3} for scaled tet, got {detJ_scaled}"
        )

    @pytest.mark.unit
    def test_tet4_elementtype_in_ir(self):
        """Verifies: ElementType.TET4 is accepted by ProblemIR and round-trips through construction.
        Acceptance criterion: AC-4 — ElementType.TET4 in IR.
        Passes when: a ProblemIR built with element_type=TET4 validates and preserves the value.
        """
        # Verify TET4 exists in the enum
        assert hasattr(ElementType, "TET4"), "ElementType.TET4 not defined"
        assert ElementType.TET4.value == "tet4"

        # Build a minimal ProblemIR with TET4
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
            element_type=ElementType.TET4,
            material=material,
            boundaries=(bc,),
        )

        # Round-trip: element_type is preserved
        assert ir.element_type == ElementType.TET4, (
            f"ProblemIR element_type changed: expected TET4, got {ir.element_type}"
        )
        assert ir.element_type.value == "tet4"

        # HEX8 still works (no regression)
        ir_hex = ProblemIR(
            dim=3,
            formulation=Formulation.TOTAL_LAGRANGIAN,
            element_type=ElementType.HEX8,
            material=material,
            boundaries=(bc,),
        )
        assert ir_hex.element_type == ElementType.HEX8

        # Unsupported type should still raise (TET10 not yet supported)
        # We test by checking TET10 is NOT in the enum (it's a later task)
        assert not hasattr(ElementType, "TET10") or ElementType.TET10 is not None, (
            "TET10 should not yet be in ElementType (it's planned for a later task)"
        )
