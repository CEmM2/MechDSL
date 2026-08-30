"""Tests for Task P5-3: Hex20 element (20-node serendipity, 3x3x3 = 27-point quadrature).

Acceptance criteria:
- AC-1: Partition of unity at all 27 quadrature points.
- AC-2: Quadratic field exactness (serendipity reproduces a complete trilinear + edge-quadratic space).
- AC-3: Jacobian positive on a regular hex.
- AC-4: ElementType.HEX20 round-trips through ProblemIR construction.
"""

from __future__ import annotations

import numpy as np
import pytest

from mechdsl.codegen.hex20_tables import (
    HEX20_NODE_COORDS,
    HEX20_QUAD_POINTS,
    HEX20_QUAD_WEIGHTS,
    SHAPE_AT_QUAD,
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


class TestTaskP5_3Hex20:
    """Tests for Task P5-3: Hex20 serendipity element.

    Acceptance criteria covered: AC-1 (partition of unity at 27 pts), AC-2 (quadratic exactness),
    AC-3 (positive Jacobian), AC-4 (ElementType.HEX20 in IR).
    """

    @pytest.mark.unit
    def test_hex20_partition_of_unity(self):
        """Verifies: sum of shape functions = 1 at all 27 Gauss points.
        Acceptance criterion: AC-1 — Partition of unity at all 27 quadrature points.
        Passes when: sum_a N_a(xi_q) == 1 within machine tolerance for every q in 1..27.
        """
        assert SHAPE_AT_QUAD.shape == (27, 20), (
            f"Expected SHAPE_AT_QUAD shape (27, 20), got {SHAPE_AT_QUAD.shape}"
        )

        # Check via pre-evaluated table at all 27 Gauss points
        errors = []
        for q in range(27):
            total = float(np.sum(SHAPE_AT_QUAD[q]))
            err = abs(total - 1.0)
            if err >= 1e-14:
                errors.append((q, total, err))
        assert not errors, (
            f"Partition of unity violated at {len(errors)} Gauss point(s): "
            + ", ".join(f"q={q}: sum={s:.15g} (err={e:.3e})" for q, s, e in errors)
        )

        # Also check at a variety of points including corners and edge midpoints
        extra_pts = [
            # 8 corners
            (-1.0, -1.0, -1.0),
            (+1.0, -1.0, -1.0),
            (+1.0, +1.0, -1.0),
            (-1.0, +1.0, -1.0),
            (-1.0, -1.0, +1.0),
            (+1.0, -1.0, +1.0),
            (+1.0, +1.0, +1.0),
            (-1.0, +1.0, +1.0),
            # 4 edge midpoints
            (0.0, -1.0, -1.0),
            (+1.0, 0.0, -1.0),
            (-1.0, -1.0, 0.0),
            (+1.0, +1.0, 0.0),
            # Interior points
            (0.0, 0.0, 0.0),
            (0.3, -0.5, 0.7),
            (-0.2, 0.8, -0.4),
        ]
        for xi, eta, zeta in extra_pts:
            N = shape_functions(xi, eta, zeta)
            total = float(np.sum(N))
            assert abs(total - 1.0) < 1e-14, (
                f"Partition of unity violated at ({xi},{eta},{zeta}): sum = {total:.15g}"
            )

        # Verify quadrature weights sum to 8 (volume of [-1,1]^3)
        w_sum = float(np.sum(HEX20_QUAD_WEIGHTS))
        assert abs(w_sum - 8.0) < 1e-14, f"Quadrature weight sum = {w_sum:.15g}, expected 8.0"

        # Report max partition-of-unity error across all 27 Gauss points
        max_err = float(np.max(np.abs(np.sum(SHAPE_AT_QUAD, axis=1) - 1.0)))
        assert max_err < 1e-14, f"Max partition-of-unity error = {max_err:.3e}"

    @pytest.mark.unit
    def test_hex20_quadratic_field_exactness(self):
        """Verifies: Hex20 serendipity reproduces a quadratic field (within the serendipity subspace).
        Acceptance criterion: AC-2 — Quadratic field exactness.
        Passes when: max|u_interp - u_exact| < 1e-13 for fields in the serendipity polynomial space.

        The serendipity Hex20 basis spans: 1, x, y, z, xy, xz, yz, x^2, y^2, z^2,
        x^2 y, x^2 z, y^2 x, y^2 z, z^2 x, z^2 y, xyz, x^2 yz, xy^2 z, xyz^2
        (20 terms). Any polynomial in this space is interpolated exactly.

        We test with a field from this subspace:
          f(xi, eta, zeta) = 1 + xi + eta + zeta + xi*eta + xi*zeta + eta*zeta
                           + xi^2 + eta^2 + zeta^2
        """
        # Use the reference element (parametric = physical)
        X = HEX20_NODE_COORDS

        def u_exact(xyz: np.ndarray) -> float:
            x, y, z = float(xyz[0]), float(xyz[1]), float(xyz[2])
            return 1.0 + x + y + z + x * y + x * z + y * z + x * x + y * y + z * z

        # Nodal values at all 20 reference nodes
        u_nodes = np.array([u_exact(X[a]) for a in range(20)])

        # Test at all 27 Gauss points and several extra interior points
        test_pts = [
            (
                float(HEX20_QUAD_POINTS[q, 0]),
                float(HEX20_QUAD_POINTS[q, 1]),
                float(HEX20_QUAD_POINTS[q, 2]),
            )
            for q in range(27)
        ] + [
            (0.0, 0.0, 0.0),
            (0.5, 0.3, -0.4),
            (-0.7, 0.2, 0.6),
            (0.1, -0.8, 0.3),
        ]

        max_err = 0.0
        for xi, eta, zeta in test_pts:
            N = shape_functions(xi, eta, zeta)
            # On the reference hex, parametric coords = physical coords
            xyz = np.dot(N, X)
            u_interp = float(np.dot(N, u_nodes))
            u_ref = u_exact(xyz)
            err = abs(u_interp - u_ref)
            max_err = max(max_err, err)
            assert err < 1e-13, (
                f"Quadratic exactness failed at ({xi:.4f},{eta:.4f},{zeta:.4f}): "
                f"interp={u_interp:.15g}, exact={u_ref:.15g}, diff={err:.3e}"
            )

    @pytest.mark.unit
    def test_hex20_jacobian_positive_on_regular_hex(self):
        """Verifies: element Jacobian is strictly positive on a regular reference hex.
        Acceptance criterion: AC-3 — Jacobian positive on a regular hex.
        Passes when: det(J) > 0 at every quadrature point on the unit cube.

        On the reference element (X_elem = HEX20_NODE_COORDS), the map is
        the identity, so J = I and det(J) = 1.0 at every point.
        """
        X_elem = HEX20_NODE_COORDS

        det_vals = []
        for q in range(27):
            _dNdX, detJ0 = reference_gradient_at_physical(X_elem, q)
            det_vals.append(detJ0)
            assert detJ0 > 0.0, f"Non-positive Jacobian det={detJ0:.6e} at quadrature point q={q}"
            # On the identity map, det(J) should be exactly 1.0
            assert abs(detJ0 - 1.0) < 1e-12, (
                f"Jacobian det={detJ0:.15g} != 1.0 at q={q} (diff={abs(detJ0 - 1.0):.3e})"
            )

        # Confirm dNdX shape is correct
        dNdX_q0, _ = reference_gradient_at_physical(X_elem, 0)
        assert dNdX_q0.shape == (20, 3), f"dNdX shape expected (20,3), got {dNdX_q0.shape}"

        min_det = min(det_vals)
        assert min_det > 0.0, f"Minimum Jacobian det = {min_det:.6e}"

    @pytest.mark.unit
    def test_hex20_elementtype_in_ir(self):
        """Verifies: ElementType.HEX20 is accepted by ProblemIR and round-trips through construction.
        Acceptance criterion: AC-4 — ElementType.HEX20 in IR.
        Passes when: a ProblemIR built with element_type=HEX20 validates and preserves the value.
        """
        # Verify HEX20 exists in the enum
        assert hasattr(ElementType, "HEX20"), "ElementType.HEX20 not defined"
        assert ElementType.HEX20.value == "hex20"

        # Build a minimal ProblemIR with HEX20
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
            element_type=ElementType.HEX20,
            material=material,
            boundaries=(bc,),
        )

        # Round-trip: element_type is preserved
        assert ir.element_type == ElementType.HEX20, (
            f"ProblemIR element_type changed: expected HEX20, got {ir.element_type}"
        )
        assert ir.element_type.value == "hex20"

        # to_dict / from_dict round-trip
        d = ir.to_dict()
        assert d["element_type"] == "hex20"
        ir2 = ProblemIR.from_dict(d)
        assert ir2.element_type == ElementType.HEX20

        # HEX8, TET4, TET10 still work (no regression)
        ir_hex8 = ProblemIR(
            dim=3,
            formulation=Formulation.TOTAL_LAGRANGIAN,
            element_type=ElementType.HEX8,
            material=material,
            boundaries=(bc,),
        )
        assert ir_hex8.element_type == ElementType.HEX8

        ir_tet4 = ProblemIR(
            dim=3,
            formulation=Formulation.TOTAL_LAGRANGIAN,
            element_type=ElementType.TET4,
            material=material,
            boundaries=(bc,),
        )
        assert ir_tet4.element_type == ElementType.TET4

        ir_tet10 = ProblemIR(
            dim=3,
            formulation=Formulation.TOTAL_LAGRANGIAN,
            element_type=ElementType.TET10,
            material=material,
            boundaries=(bc,),
        )
        assert ir_tet10.element_type == ElementType.TET10
