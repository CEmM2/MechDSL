"""Tests for Layer 4 — Element IR and FE localisation."""

import numpy as np
import pytest

from mechdsl.ir.element_ir import (
    _HEX8_NODES,
    ElementIR,
    create_hex8_element_ir,
    hex8_basis,
    hex8_quadrature,
)

# ------------------------------------------------------------------
# 1. Hex8 quadrature has 8 points (2x2x2)
# ------------------------------------------------------------------


class TestQuadrature:
    def test_n_points(self):
        """2x2x2 Gauss quadrature has 8 points."""
        quad = hex8_quadrature()
        assert quad.n_points == 8
        assert quad.points.shape == (8, 3)
        assert quad.weights.shape == (8,)

    # ------------------------------------------------------------------
    # 2. Quadrature weights sum to 8 (integral of 1 over [-1,1]^3)
    # ------------------------------------------------------------------

    def test_weights_sum(self):
        """Weights sum to 8 = volume of [-1,1]^3."""
        quad = hex8_quadrature()
        assert np.isclose(quad.weights.sum(), 8.0)

    def test_points_symmetric(self):
        """Quadrature points are symmetric about origin."""
        quad = hex8_quadrature()
        assert np.allclose(quad.points.mean(axis=0), 0.0)

    def test_points_at_gauss_locations(self):
        """All coordinates are +/- 1/sqrt(3)."""
        quad = hex8_quadrature()
        g = 1.0 / np.sqrt(3.0)
        assert np.allclose(np.abs(quad.points), g)


# ------------------------------------------------------------------
# 3. Partition of unity: sum(N_i) = 1 at random points
# ------------------------------------------------------------------


class TestPartitionOfUnity:
    def test_partition_of_unity_random(self):
        """Sum of shape functions = 1 at 10 random points in [-1,1]^3."""
        basis = hex8_basis()
        rng = np.random.default_rng(42)
        for _ in range(10):
            xi, eta, zeta = rng.uniform(-1, 1, size=3)
            vals = basis.evaluate(xi, eta, zeta)
            assert np.isclose(vals.sum(), 1.0), (
                f"Partition of unity failed at ({xi}, {eta}, {zeta}): sum = {vals.sum()}"
            )

    def test_partition_of_unity_at_origin(self):
        """All shape functions equal 1/8 at origin."""
        basis = hex8_basis()
        vals = basis.evaluate(0.0, 0.0, 0.0)
        assert np.allclose(vals, 0.125)

    def test_partition_of_unity_at_gauss_points(self):
        """Partition of unity holds at all Gauss points."""
        basis = hex8_basis()
        quad = hex8_quadrature()
        for pt in quad.points:
            vals = basis.evaluate(pt[0], pt[1], pt[2])
            assert np.isclose(vals.sum(), 1.0)


# ------------------------------------------------------------------
# 4. Kronecker delta at all 8 nodes
# ------------------------------------------------------------------


class TestKroneckerDelta:
    def test_kronecker_at_nodes(self):
        """N_i(node_j) = delta_{ij} for all i,j in 0..7."""
        basis = hex8_basis()
        for j in range(8):
            xi, eta, zeta = _HEX8_NODES[j]
            vals = basis.evaluate(float(xi), float(eta), float(zeta))
            for i in range(8):
                expected = 1.0 if i == j else 0.0
                assert np.isclose(vals[i], expected), (
                    f"N_{i}(node_{j}) = {vals[i]}, expected {expected}"
                )


# ------------------------------------------------------------------
# 5. Shape function gradient consistency with finite differences
# ------------------------------------------------------------------


class TestGradientConsistency:
    def test_gradient_finite_difference(self):
        """Analytic gradient matches central finite differences."""
        basis = hex8_basis()
        h = 1e-7
        rng = np.random.default_rng(123)

        for _ in range(5):
            xi, eta, zeta = rng.uniform(-0.9, 0.9, size=3)
            grad_analytic = basis.gradient(xi, eta, zeta)

            # Finite difference for each direction
            grad_fd = np.empty((8, 3), dtype=np.float64)

            vals_p = basis.evaluate(xi + h, eta, zeta)
            vals_m = basis.evaluate(xi - h, eta, zeta)
            grad_fd[:, 0] = (vals_p - vals_m) / (2.0 * h)

            vals_p = basis.evaluate(xi, eta + h, zeta)
            vals_m = basis.evaluate(xi, eta - h, zeta)
            grad_fd[:, 1] = (vals_p - vals_m) / (2.0 * h)

            vals_p = basis.evaluate(xi, eta, zeta + h)
            vals_m = basis.evaluate(xi, eta, zeta - h)
            grad_fd[:, 2] = (vals_p - vals_m) / (2.0 * h)

            np.testing.assert_allclose(
                grad_analytic,
                grad_fd,
                atol=1e-6,
                err_msg=f"Gradient mismatch at ({xi}, {eta}, {zeta})",
            )

    def test_gradient_sum_is_zero(self):
        """Sum of shape function gradients = 0 (partition of unity)."""
        basis = hex8_basis()
        rng = np.random.default_rng(456)
        for _ in range(5):
            xi, eta, zeta = rng.uniform(-1, 1, size=3)
            grad = basis.gradient(xi, eta, zeta)
            assert np.allclose(grad.sum(axis=0), 0.0, atol=1e-14), (
                f"Gradient sum != 0 at ({xi}, {eta}, {zeta})"
            )


# ------------------------------------------------------------------
# 6. ElementIR construction validates correctly
# ------------------------------------------------------------------


class TestElementIRConstruction:
    def test_create_hex8(self):
        """create_hex8_element_ir builds a valid ElementIR."""
        eir = create_hex8_element_ir()
        assert eir.element_type == "hex8"
        assert eir.n_nodes == 8
        assert eir.dim == 3
        assert eir.formulation == "total_lagrangian"
        assert eir.quadrature.n_points == 8
        assert eir.basis.n_nodes == 8

    def test_direct_construction(self):
        """Direct ElementIR construction with valid args."""
        eir = ElementIR(
            element_type="hex8",
            n_nodes=8,
            dim=3,
            basis=hex8_basis(),
            quadrature=hex8_quadrature(),
            formulation="total_lagrangian",
        )
        assert eir.element_type == "hex8"


# ------------------------------------------------------------------
# 7. Invalid element_type / n_nodes / dim rejected
# ------------------------------------------------------------------


class TestElementIRValidation:
    def test_invalid_element_type(self):
        """Unsupported element type raises ValueError referencing Plan B phase B5."""
        with pytest.raises(ValueError, match=r"not supported.*Plan B phase B5"):
            ElementIR(
                element_type="hex27",
                n_nodes=27,
                dim=3,
                basis=hex8_basis(),
                quadrature=hex8_quadrature(),
                formulation="total_lagrangian",
            )

    def test_invalid_n_nodes(self):
        """Wrong node count raises ValueError."""
        with pytest.raises(ValueError, match="HEX8 requires 8 nodes"):
            ElementIR(
                element_type="hex8",
                n_nodes=4,
                dim=3,
                basis=hex8_basis(),
                quadrature=hex8_quadrature(),
                formulation="total_lagrangian",
            )

    def test_invalid_dim(self):
        """Non-3D dim raises ValueError."""
        with pytest.raises(ValueError, match="Only 3D supported"):
            ElementIR(
                element_type="hex8",
                n_nodes=8,
                dim=2,
                basis=hex8_basis(),
                quadrature=hex8_quadrature(),
                formulation="total_lagrangian",
            )

    def test_invalid_element_type_mentions_plan_b(self):
        """Error message for invalid element type mentions Plan B."""
        with pytest.raises(ValueError, match="Plan B"):
            ElementIR(
                element_type="hex27",
                n_nodes=27,
                dim=3,
                basis=hex8_basis(),
                quadrature=hex8_quadrature(),
                formulation="total_lagrangian",
            )

    def test_invalid_dim_mentions_plan_b(self):
        """Error message for invalid dim mentions Plan B."""
        with pytest.raises(ValueError, match="Plan B"):
            ElementIR(
                element_type="hex8",
                n_nodes=8,
                dim=2,
                basis=hex8_basis(),
                quadrature=hex8_quadrature(),
                formulation="total_lagrangian",
            )

    def test_frozen(self):
        """ElementIR is immutable."""
        eir = create_hex8_element_ir()
        with pytest.raises(AttributeError):
            eir.dim = 2  # type: ignore[misc]


class TestProblemIRFrozen:
    """Verify ProblemIR is also immutable."""

    def test_frozen(self):
        from mechdsl.ir.mechanics_ir import (
            BCType,
            BoundaryCondition,
            ElementType,
            Formulation,
            MaterialSpec,
            ProblemIR,
        )

        p = ProblemIR(
            dim=3,
            formulation=Formulation.TOTAL_LAGRANGIAN,
            element_type=ElementType.HEX8,
            material=MaterialSpec(model="svk"),
            boundaries=(BoundaryCondition(name="fix", bc_type=BCType.DIRICHLET),),
        )
        with pytest.raises(AttributeError):
            p.dim = 2  # type: ignore[misc]


# ---------------------------------------------------------------------------
# __post_init__ validation tests for QuadratureRule
# ---------------------------------------------------------------------------


class TestQuadratureRuleValidation:
    """Tests for QuadratureRule __post_init__ validators."""

    def test_bad_points_shape(self) -> None:
        from mechdsl.ir.element_ir import QuadratureRule

        with pytest.raises(ValueError, match="points must be"):
            QuadratureRule(
                points=np.zeros((8,)),
                weights=np.zeros((8,)),
            )

    def test_bad_weights_shape(self) -> None:
        from mechdsl.ir.element_ir import QuadratureRule

        with pytest.raises(ValueError, match="weights must be 1D"):
            QuadratureRule(
                points=np.zeros((8, 3)),
                weights=np.zeros((8, 3)),
            )

    def test_points_weights_length_mismatch(self) -> None:
        from mechdsl.ir.element_ir import QuadratureRule

        with pytest.raises(ValueError, match=r"points rows.*weights length"):
            QuadratureRule(
                points=np.zeros((8, 3)),
                weights=np.zeros((4,)),
            )
