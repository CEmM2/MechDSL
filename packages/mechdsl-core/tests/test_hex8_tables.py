"""Tests for Hex8 static table provider (P6.1).

Verifies pre-computed tables for code generation are correct and consistent
with the callable shape function / gradient implementations.
"""

from __future__ import annotations

import numpy as np
import pytest

from mechdsl.codegen.hex8_tables import (
    GRAD_AT_QUAD,
    HEX8_NODE_COORDS,
    HEX8_QUAD_POINTS,
    HEX8_QUAD_WEIGHTS,
    SHAPE_AT_QUAD,
    reference_gradient_at_physical,
    shape_functions,
    shape_gradients,
)

# ------------------------------------------------------------------
# 1. Partition of unity: sum(N_a) = 1 at random points
# ------------------------------------------------------------------


class TestPartitionOfUnity:
    def test_partition_of_unity_random(self):
        """sum(N_a(xi,eta,zeta)) = 1 at 10 random points in [-1,1]^3."""
        rng = np.random.default_rng(42)
        for _ in range(10):
            xi, eta, zeta = rng.uniform(-1, 1, size=3)
            vals = shape_functions(xi, eta, zeta)
            assert np.isclose(vals.sum(), 1.0), (
                f"Partition of unity failed at ({xi}, {eta}, {zeta}): sum = {vals.sum()}"
            )


# ------------------------------------------------------------------
# 2. Kronecker delta: N_a(node_b) = delta_ab
# ------------------------------------------------------------------


class TestKroneckerDelta:
    def test_kronecker_at_nodes(self):
        """N_a(node_b) = delta_{ab} for all 8 nodes."""
        for b in range(8):
            xi, eta, zeta = HEX8_NODE_COORDS[b]
            vals = shape_functions(float(xi), float(eta), float(zeta))
            expected = np.zeros(8, dtype=np.float64)
            expected[b] = 1.0
            np.testing.assert_allclose(
                vals, expected, atol=1e-15, err_msg=f"Kronecker delta failed at node {b}"
            )


# ------------------------------------------------------------------
# 3. Quadrature weights sum to 8 (volume of [-1,1]^3)
# ------------------------------------------------------------------


class TestQuadratureWeightsSum:
    def test_weights_sum(self):
        """sum(w_q) = 8."""
        assert np.isclose(HEX8_QUAD_WEIGHTS.sum(), 8.0)


# ------------------------------------------------------------------
# 4. Quadrature exactness
# ------------------------------------------------------------------


class TestQuadratureExactness:
    def test_integral_x_squared(self):
        """integral of x^2 over [-1,1]^3 = 8/3."""
        # f(x,y,z) = x^2, integrated exactly by 2-pt Gauss in each direction
        result = 0.0
        for q in range(8):
            x = HEX8_QUAD_POINTS[q, 0]
            w = HEX8_QUAD_WEIGHTS[q]
            result += w * x**2
        np.testing.assert_allclose(result, 8.0 / 3.0, atol=1e-14)

    def test_integral_xy_is_zero(self):
        """integral of x*y over [-1,1]^3 = 0 (odd function in each variable)."""
        result = 0.0
        for q in range(8):
            x, y, _z = HEX8_QUAD_POINTS[q]
            w = HEX8_QUAD_WEIGHTS[q]
            result += w * x * y
        np.testing.assert_allclose(result, 0.0, atol=1e-15)


# ------------------------------------------------------------------
# 5. SHAPE_AT_QUAD consistency with shape_functions()
# ------------------------------------------------------------------


class TestShapeAtQuadConsistency:
    def test_shape_at_quad_matches_callable(self):
        """SHAPE_AT_QUAD[q, a] matches shape_functions() at quad points."""
        for q in range(8):
            xi, eta, zeta = HEX8_QUAD_POINTS[q]
            expected = shape_functions(float(xi), float(eta), float(zeta))
            np.testing.assert_allclose(
                SHAPE_AT_QUAD[q], expected, atol=1e-15, err_msg=f"Mismatch at quad point {q}"
            )


# ------------------------------------------------------------------
# 6. GRAD_AT_QUAD consistency with shape_gradients()
# ------------------------------------------------------------------


class TestGradAtQuadConsistency:
    def test_grad_at_quad_matches_callable(self):
        """GRAD_AT_QUAD[q, a, i] matches shape_gradients() at quad points."""
        for q in range(8):
            xi, eta, zeta = HEX8_QUAD_POINTS[q]
            expected = shape_gradients(float(xi), float(eta), float(zeta))
            np.testing.assert_allclose(
                GRAD_AT_QUAD[q], expected, atol=1e-15, err_msg=f"Mismatch at quad point {q}"
            )


# ------------------------------------------------------------------
# 7. Gradient finite difference
# ------------------------------------------------------------------


class TestGradientFiniteDifference:
    def test_gradient_fd(self):
        """shape_gradients matches finite differences of shape_functions."""
        h = 1e-7
        rng = np.random.default_rng(123)

        for _ in range(5):
            xi, eta, zeta = rng.uniform(-0.9, 0.9, size=3)
            grad_analytic = shape_gradients(xi, eta, zeta)
            grad_fd = np.empty((8, 3), dtype=np.float64)

            # d/dxi
            grad_fd[:, 0] = (
                shape_functions(xi + h, eta, zeta) - shape_functions(xi - h, eta, zeta)
            ) / (2.0 * h)
            # d/deta
            grad_fd[:, 1] = (
                shape_functions(xi, eta + h, zeta) - shape_functions(xi, eta - h, zeta)
            ) / (2.0 * h)
            # d/dzeta
            grad_fd[:, 2] = (
                shape_functions(xi, eta, zeta + h) - shape_functions(xi, eta, zeta - h)
            ) / (2.0 * h)

            np.testing.assert_allclose(
                grad_analytic,
                grad_fd,
                atol=1e-6,
                err_msg=f"Gradient FD mismatch at ({xi}, {eta}, {zeta})",
            )


# ------------------------------------------------------------------
# 8. reference_gradient_at_physical: unit cube element
# ------------------------------------------------------------------


class TestReferenceGradientUnitCube:
    """For a unit cube [0,1]^3 the mapping from [-1,1]^3 is x = (xi+1)/2.

    Therefore J0 = diag(0.5, 0.5, 0.5) and:
      - detJ0 = 1/8
      - dN/dX = dN/dxi @ J0^{-1} = dN/dxi * 2
    """

    @pytest.fixture
    def unit_cube_coords(self) -> np.ndarray:
        """Node coordinates of a unit cube [0,1]^3 in MFEM/VTK order."""
        return (HEX8_NODE_COORDS + 1.0) / 2.0

    def test_detJ0(self, unit_cube_coords: np.ndarray):
        """detJ0 = 1/8 for unit cube."""
        for q in range(8):
            _dNdX, detJ0 = reference_gradient_at_physical(unit_cube_coords, q)
            np.testing.assert_allclose(detJ0, 0.125, atol=1e-14, err_msg=f"q={q}")

    def test_dNdX_scaling(self, unit_cube_coords: np.ndarray):
        """dN/dX = dN/dxi * 2 for unit cube."""
        for q in range(8):
            dNdX, _detJ0 = reference_gradient_at_physical(unit_cube_coords, q)
            expected = GRAD_AT_QUAD[q] * 2.0
            np.testing.assert_allclose(
                dNdX, expected, atol=1e-14, err_msg=f"dN/dX scaling wrong at q={q}"
            )


# ------------------------------------------------------------------
# 9. Patch test: linear displacement field exactly reproduced
# ------------------------------------------------------------------


class TestPatchTest:
    """A linear displacement field u(X) = A @ X + b must be exactly
    reproduced by the FE interpolation at every quadrature point.

    This verifies that reference_gradient_at_physical produces gradients
    that exactly recover constant strain fields.
    """

    def test_constant_strain_recovery(self):
        """Linear displacement u = A @ X gives constant gradient A at all quad points."""
        rng = np.random.default_rng(99)

        # Arbitrary linear map coefficients
        A = rng.uniform(-0.05, 0.05, size=(3, 3))

        # Unit cube element
        X_elem = (HEX8_NODE_COORDS + 1.0) / 2.0  # (8, 3)

        # Nodal displacements from linear field: u_a = A @ X_a
        u_elem = X_elem @ A.T  # (8, 3)

        for q in range(8):
            dNdX, _detJ0 = reference_gradient_at_physical(X_elem, q)

            # Displacement gradient at quad point: du/dX = u^T @ dN/dX
            grad_u = u_elem.T @ dNdX  # (3, 3)

            np.testing.assert_allclose(
                grad_u,
                A,
                atol=1e-13,
                err_msg=f"Patch test failed at quadrature point {q}",
            )


# ------------------------------------------------------------------
# 10. Table shapes
# ------------------------------------------------------------------


class TestTableShapes:
    def test_node_coords_shape(self):
        assert HEX8_NODE_COORDS.shape == (8, 3)
        assert HEX8_NODE_COORDS.dtype == np.float64

    def test_quad_points_shape(self):
        assert HEX8_QUAD_POINTS.shape == (8, 3)
        assert HEX8_QUAD_POINTS.dtype == np.float64

    def test_quad_weights_shape(self):
        assert HEX8_QUAD_WEIGHTS.shape == (8,)
        assert HEX8_QUAD_WEIGHTS.dtype == np.float64

    def test_shape_at_quad_shape(self):
        assert SHAPE_AT_QUAD.shape == (8, 8)
        assert SHAPE_AT_QUAD.dtype == np.float64

    def test_grad_at_quad_shape(self):
        assert GRAD_AT_QUAD.shape == (8, 8, 3)
        assert GRAD_AT_QUAD.dtype == np.float64


# ---------------------------------------------------------------------------
# R3.5.2 — T3: Degenerate element error path
# ---------------------------------------------------------------------------


class TestDegenerateElement:
    """T3: Inverted element must raise ValueError."""

    def test_inverted_element_raises(self) -> None:
        """Swapping two nodes inverts the element, producing detJ0 <= 0."""
        X_bad = HEX8_NODE_COORDS.copy()
        X_bad[[0, 1]] = X_bad[[1, 0]]  # invert by swapping nodes 0 and 1
        with pytest.raises(ValueError, match=r"[Nn]on-positive Jacobian"):
            reference_gradient_at_physical(X_bad, 0)  # q=0 (quadrature point index)
