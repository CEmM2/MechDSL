"""Tests for mechdsl.lib.tensor_ops — Tier-1 tensor operations.

Deterministic tests using analytically known results and seeded random
matrices. Tolerance: atol=1e-12 per 07-CONVENTIONS.md.
"""

from __future__ import annotations

import numpy as np
from numpy.testing import assert_allclose

from mechdsl.lib.tensor_ops import (
    cauchy_from_pk1,
    deformation_gradient,
    det_33,
    green_lagrange,
    inv_33,
    mat_mul_33,
    mat_mul_T_33,
    pk1_from_pk2,
    right_cauchy_green,
)

TOL = 1e-12
I3 = np.eye(3, dtype=np.float64)


# ---------------------------------------------------------------------------
# 1. Identity matrix tests
# ---------------------------------------------------------------------------
class TestIdentity:
    """Verify all ops behave correctly with the identity matrix."""

    def test_mat_mul_identity(self) -> None:
        """A @ I = A for arbitrary A."""
        rng = np.random.default_rng(42)
        A = rng.standard_normal((3, 3))
        assert_allclose(mat_mul_33(A, I3), A, atol=TOL)
        assert_allclose(mat_mul_33(I3, A), A, atol=TOL)

    def test_det_identity(self) -> None:
        assert det_33(I3) == 1.0

    def test_inv_identity(self) -> None:
        assert_allclose(inv_33(I3), I3, atol=TOL)

    def test_right_cauchy_green_identity(self) -> None:
        """C(I) = I^T @ I = I."""
        assert_allclose(right_cauchy_green(I3), I3, atol=TOL)

    def test_green_lagrange_identity(self) -> None:
        """E(I) = (I - I)/2 = 0."""
        E = green_lagrange(I3)
        assert_allclose(E, np.zeros((3, 3)), atol=TOL)


# ---------------------------------------------------------------------------
# 2. Simple shear tests
# ---------------------------------------------------------------------------
class TestSimpleShear:
    """F = [[1, gamma, 0], [0, 1, 0], [0, 0, 1]] with gamma = 0.1."""

    gamma = 0.1

    @staticmethod
    def _F(gamma: float) -> np.ndarray:
        F = np.eye(3, dtype=np.float64)
        F[0, 1] = gamma
        return F

    def test_right_cauchy_green(self) -> None:
        F = self._F(self.gamma)
        C = right_cauchy_green(F)
        # Analytically: C = F^T F
        # C_00 = 1, C_01 = gamma, C_02 = 0
        # C_10 = gamma, C_11 = 1 + gamma^2, C_12 = 0
        # C_22 = 1
        expected = np.array(
            [
                [1.0, self.gamma, 0.0],
                [self.gamma, 1.0 + self.gamma**2, 0.0],
                [0.0, 0.0, 1.0],
            ],
            dtype=np.float64,
        )
        assert_allclose(C, expected, atol=TOL)

    def test_green_lagrange(self) -> None:
        F = self._F(self.gamma)
        E = green_lagrange(F)
        g = self.gamma
        expected = np.array(
            [
                [0.0, g / 2.0, 0.0],
                [g / 2.0, g**2 / 2.0, 0.0],
                [0.0, 0.0, 0.0],
            ],
            dtype=np.float64,
        )
        assert_allclose(E, expected, atol=TOL)

    def test_det_simple_shear(self) -> None:
        """Simple shear is volume-preserving: J = 1."""
        F = self._F(self.gamma)
        assert_allclose(det_33(F), 1.0, atol=TOL)


# ---------------------------------------------------------------------------
# 3. Random invertible matrices: inv(A) @ A ≈ I
# ---------------------------------------------------------------------------
class TestRandomInvertible:
    def test_inv_roundtrip(self) -> None:
        rng = np.random.default_rng(42)
        for _ in range(10):
            A = rng.standard_normal((3, 3))
            # Ensure invertible (random matrices are generically invertible)
            A_inv = inv_33(A)
            assert_allclose(mat_mul_33(A_inv, A), I3, atol=TOL)
            assert_allclose(mat_mul_33(A, A_inv), I3, atol=TOL)


# ---------------------------------------------------------------------------
# 4. PK transforms: round-trip consistency
# ---------------------------------------------------------------------------
class TestPKTransforms:
    """Verify P = F @ S and sigma = (1/J) P @ F^T are consistent."""

    def test_pk1_from_pk2_identity(self) -> None:
        """When F = I, P = S."""
        rng = np.random.default_rng(42)
        S = rng.standard_normal((3, 3))
        S = 0.5 * (S + S.T)  # symmetric PK2
        P = pk1_from_pk2(I3, S)
        assert_allclose(P, S, atol=TOL)

    def test_cauchy_from_pk1_identity(self) -> None:
        """When F = I (J=1), sigma = P @ I^T = P."""
        rng = np.random.default_rng(42)
        P = rng.standard_normal((3, 3))
        sigma = cauchy_from_pk1(P, I3, 1.0)
        assert_allclose(sigma, P, atol=TOL)

    def test_pk_roundtrip(self) -> None:
        """For known F and symmetric S, verify sigma = (1/J) F S F^T."""
        rng = np.random.default_rng(99)
        F = np.eye(3, dtype=np.float64) + 0.1 * rng.standard_normal((3, 3))
        S = rng.standard_normal((3, 3))
        S = 0.5 * (S + S.T)  # symmetric PK2

        J = det_33(F)
        P = pk1_from_pk2(F, S)
        sigma = cauchy_from_pk1(P, F, J)

        # Direct computation: sigma = (1/J) F S F^T
        sigma_direct = (1.0 / J) * (F @ S @ F.T)
        assert_allclose(sigma, sigma_direct, atol=TOL)

    def test_cauchy_symmetry(self) -> None:
        """Cauchy stress should be symmetric when PK2 is symmetric."""
        rng = np.random.default_rng(77)
        F = np.eye(3, dtype=np.float64) + 0.05 * rng.standard_normal((3, 3))
        S = rng.standard_normal((3, 3))
        S = 0.5 * (S + S.T)

        J = det_33(F)
        P = pk1_from_pk2(F, S)
        sigma = cauchy_from_pk1(P, F, J)
        assert_allclose(sigma, sigma.T, atol=TOL)


# ---------------------------------------------------------------------------
# 5. det_33: known determinant values
# ---------------------------------------------------------------------------
class TestDet33:
    def test_identity_det(self) -> None:
        assert_allclose(det_33(I3), 1.0, atol=TOL)

    def test_scaled_identity(self) -> None:
        """det(2I) = 8."""
        assert_allclose(det_33(2.0 * I3), 8.0, atol=TOL)

    def test_known_matrix(self) -> None:
        """Hand-computed determinant."""
        A = np.array(
            [[1.0, 2.0, 3.0], [0.0, 1.0, 4.0], [5.0, 6.0, 0.0]],
            dtype=np.float64,
        )
        # det = 1*(0-24) - 2*(0-20) + 3*(0-5) = -24 + 40 - 15 = 1
        assert_allclose(det_33(A), 1.0, atol=TOL)

    def test_singular_matrix(self) -> None:
        """Singular matrix has det = 0."""
        A = np.array(
            [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0], [7.0, 8.0, 9.0]],
            dtype=np.float64,
        )
        assert_allclose(det_33(A), 0.0, atol=TOL)

    def test_det_product(self) -> None:
        """det(AB) = det(A) * det(B)."""
        rng = np.random.default_rng(42)
        A = rng.standard_normal((3, 3))
        B = rng.standard_normal((3, 3))
        assert_allclose(
            det_33(mat_mul_33(A, B)),
            det_33(A) * det_33(B),
            atol=TOL,
        )


# ---------------------------------------------------------------------------
# 6. deformation_gradient: F = I + grad_u
# ---------------------------------------------------------------------------
class TestDeformationGradient:
    def test_zero_displacement_gradient(self) -> None:
        """grad_u = 0 => F = I."""
        F = deformation_gradient(np.zeros((3, 3), dtype=np.float64))
        assert_allclose(F, I3, atol=TOL)

    def test_recovery(self) -> None:
        """F - I should give back grad_u."""
        rng = np.random.default_rng(42)
        grad_u = 0.1 * rng.standard_normal((3, 3))
        F = deformation_gradient(grad_u)
        assert_allclose(F - I3, grad_u, atol=TOL)

    def test_small_strain(self) -> None:
        """For small grad_u, F ≈ I + grad_u directly."""
        grad_u = np.array(
            [[0.001, 0.002, 0.0], [0.0, -0.001, 0.0], [0.0, 0.0, 0.003]],
            dtype=np.float64,
        )
        F = deformation_gradient(grad_u)
        expected = I3 + grad_u
        assert_allclose(F, expected, atol=TOL)


# ---------------------------------------------------------------------------
# 7. green_lagrange: symmetry and zero for F = I
# ---------------------------------------------------------------------------
class TestGreenLagrangeProperties:
    def test_zero_for_identity(self) -> None:
        """E = 0 when F = I (no deformation)."""
        assert_allclose(green_lagrange(I3), np.zeros((3, 3)), atol=TOL)

    def test_symmetric(self) -> None:
        """E should always be symmetric for any F."""
        rng = np.random.default_rng(42)
        for _ in range(10):
            F = np.eye(3) + 0.2 * rng.standard_normal((3, 3))
            E = green_lagrange(F)
            assert_allclose(E, E.T, atol=TOL)

    def test_pure_dilatation(self) -> None:
        """For F = lambda * I, E = (lambda^2 - 1)/2 * I."""
        lam = 1.05
        F = lam * I3
        E = green_lagrange(F)
        expected = 0.5 * (lam**2 - 1.0) * I3
        assert_allclose(E, expected, atol=TOL)


# ---------------------------------------------------------------------------
# 8. mat_mul_T_33: verify A^T @ B
# ---------------------------------------------------------------------------
class TestMatMulT:
    def test_basic(self) -> None:
        rng = np.random.default_rng(42)
        A = rng.standard_normal((3, 3))
        B = rng.standard_normal((3, 3))
        assert_allclose(mat_mul_T_33(A, B), A.T @ B, atol=TOL)

    def test_orthogonal(self) -> None:
        """For orthogonal Q: Q^T @ Q = I."""
        # Construct orthogonal matrix via QR decomposition
        rng = np.random.default_rng(42)
        Q, _ = np.linalg.qr(rng.standard_normal((3, 3)))
        assert_allclose(mat_mul_T_33(Q, Q), I3, atol=TOL)
