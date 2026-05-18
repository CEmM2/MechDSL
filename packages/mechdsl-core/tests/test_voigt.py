"""Tests for Voigt/Mandel conversion utilities.

Tests per 07-CONVENTIONS.md §2-3:
- Voigt ordering: [xx, yy, zz, xy, xz, yz], unscaled shears
- Mandel: P = diag(1, 1, 1, sqrt(2), sqrt(2), sqrt(2))
"""

import numpy as np
import pytest
from numpy.testing import assert_allclose

from mechdsl.symbolic.voigt import (
    VOIGT_MAP_3D,
    mandel_to_voigt,
    sym_tensor_to_voigt,
    tangent_to_voigt_66,
    tangent_voigt_to_mandel,
    voigt_66_to_tangent,
    voigt_to_mandel,
    voigt_to_sym_tensor,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _random_symmetric_33(rng: np.random.Generator) -> np.ndarray:
    """Generate a random symmetric 3x3 matrix."""
    A = rng.standard_normal((3, 3))
    return 0.5 * (A + A.T)


def _random_major_minor_symmetric_tangent(rng: np.random.Generator) -> np.ndarray:
    """Generate a random 4th-order tensor with major and minor symmetries.

    Build from the outer product of random symmetric 2nd-order tensors
    to guarantee all symmetries.
    """
    C4 = np.zeros((3, 3, 3, 3), dtype=np.float64)
    for _ in range(10):
        A = _random_symmetric_33(rng)
        # C_ijkl += A_ij * A_kl  gives major sym
        C4 += np.einsum("ij,kl->ijkl", A, A)
    # Already has minor sym from A being symmetric, and major sym from outer product.
    return C4


# ---------------------------------------------------------------------------
# 2nd-order tensor <-> Voigt round-trips
# ---------------------------------------------------------------------------


class TestTensorVoigtRoundTrip:
    """Round-trip conversions between 3x3 symmetric tensors and Voigt 6-vectors."""

    def test_identity_tensor(self):
        eye3 = np.eye(3, dtype=np.float64)
        v = sym_tensor_to_voigt(eye3)
        assert_allclose(v, [1, 1, 1, 0, 0, 0])
        T_back = voigt_to_sym_tensor(v)
        assert_allclose(T_back, eye3)

    def test_random_symmetric_roundtrip(self):
        rng = np.random.default_rng(42)
        T = _random_symmetric_33(rng)
        v = sym_tensor_to_voigt(T)
        T_back = voigt_to_sym_tensor(v)
        assert_allclose(T_back, T, atol=1e-15)

    def test_voigt_to_tensor_to_voigt(self):
        v = np.array([1.0, 2.0, 3.0, 0.5, -0.3, 0.7])
        T = voigt_to_sym_tensor(v)
        v_back = sym_tensor_to_voigt(T)
        assert_allclose(v_back, v, atol=1e-15)


# ---------------------------------------------------------------------------
# Voigt ordering convention
# ---------------------------------------------------------------------------


class TestVoigtOrdering:
    """Verify Voigt ordering matches 07-CONVENTIONS.md §2.1."""

    def test_voigt_map_length(self):
        assert len(VOIGT_MAP_3D) == 6

    def test_xy_at_index_3(self):
        """v[3] = T[0,1] (xy component)."""
        T = np.zeros((3, 3), dtype=np.float64)
        T[0, 1] = 7.0
        T[1, 0] = 7.0  # symmetric
        v = sym_tensor_to_voigt(T)
        assert v[3] == pytest.approx(7.0)
        # all others zero
        assert v[0] == pytest.approx(0.0)
        assert v[1] == pytest.approx(0.0)
        assert v[2] == pytest.approx(0.0)
        assert v[4] == pytest.approx(0.0)
        assert v[5] == pytest.approx(0.0)

    def test_xz_at_index_4(self):
        """v[4] = T[0,2] (xz component)."""
        T = np.zeros((3, 3), dtype=np.float64)
        T[0, 2] = 3.0
        T[2, 0] = 3.0
        v = sym_tensor_to_voigt(T)
        assert v[4] == pytest.approx(3.0)

    def test_yz_at_index_5(self):
        """v[5] = T[1,2] (yz component)."""
        T = np.zeros((3, 3), dtype=np.float64)
        T[1, 2] = -2.0
        T[2, 1] = -2.0
        v = sym_tensor_to_voigt(T)
        assert v[5] == pytest.approx(-2.0)

    def test_unscaled_shears(self):
        """Shears are unscaled: v[3] = T[0,1], NOT 2*T[0,1]."""
        T = np.zeros((3, 3), dtype=np.float64)
        T[0, 1] = 0.5
        T[1, 0] = 0.5
        v = sym_tensor_to_voigt(T)
        assert v[3] == pytest.approx(0.5)  # NOT 1.0


# ---------------------------------------------------------------------------
# 4th-order tangent <-> Voigt 6x6 round-trip
# ---------------------------------------------------------------------------


class TestTangentVoigtRoundTrip:
    """Round-trip conversions between (3,3,3,3) tangents and 6x6 Voigt matrices."""

    def test_tangent_roundtrip(self):
        rng = np.random.default_rng(123)
        C4 = _random_major_minor_symmetric_tangent(rng)
        C6 = tangent_to_voigt_66(C4)
        C4_back = voigt_66_to_tangent(C6)
        assert_allclose(C4_back, C4, atol=1e-14)

    def test_isotropic_tangent_symmetry(self):
        """Isotropic tangent 6x6 must be symmetric: C6[i,j] == C6[j,i]."""
        lam, mu = 100.0, 50.0
        d = np.eye(3)  # Kronecker delta
        C4 = np.zeros((3, 3, 3, 3), dtype=np.float64)
        for i in range(3):
            for j in range(3):
                for k in range(3):
                    for el in range(3):
                        C4[i, j, k, el] = lam * d[i, j] * d[k, el] + mu * (
                            d[i, k] * d[j, el] + d[i, el] * d[j, k]
                        )
        C6 = tangent_to_voigt_66(C4)
        assert_allclose(C6, C6.T, atol=1e-15)

    def test_voigt_66_to_tangent_minor_symmetries(self):
        """Reconstructed tangent must have minor symmetries."""
        rng = np.random.default_rng(99)
        C4 = _random_major_minor_symmetric_tangent(rng)
        C6 = tangent_to_voigt_66(C4)
        C4_back = voigt_66_to_tangent(C6)
        # minor left: C_ijkl == C_jikl
        for i in range(3):
            for j in range(3):
                for k in range(3):
                    for el in range(3):
                        assert C4_back[i, j, k, el] == pytest.approx(
                            C4_back[j, i, k, el], abs=1e-15
                        )


# ---------------------------------------------------------------------------
# Mandel conversions
# ---------------------------------------------------------------------------


class TestMandel:
    """Mandel scaling per 07-CONVENTIONS.md §3."""

    def test_voigt_mandel_roundtrip_vector(self):
        v = np.array([1.0, 2.0, 3.0, 0.5, -0.3, 0.7])
        m = voigt_to_mandel(v)
        v_back = mandel_to_voigt(m)
        assert_allclose(v_back, v, atol=1e-15)

    def test_mandel_scaling_values(self):
        v = np.array([1.0, 1.0, 1.0, 1.0, 1.0, 1.0])
        m = voigt_to_mandel(v)
        sqrt2 = np.sqrt(2)
        assert_allclose(m, [1, 1, 1, sqrt2, sqrt2, sqrt2])

    def test_tangent_mandel_equals_P_C_Pinv(self):
        """C_mandel = P @ C_voigt @ P^{-1} (§3.2)."""
        lam, mu = 100.0, 50.0
        d = np.eye(3)  # Kronecker delta
        C4 = np.zeros((3, 3, 3, 3), dtype=np.float64)
        for i in range(3):
            for j in range(3):
                for k in range(3):
                    for el in range(3):
                        C4[i, j, k, el] = lam * d[i, j] * d[k, el] + mu * (
                            d[i, k] * d[j, el] + d[i, el] * d[j, k]
                        )
        C6 = tangent_to_voigt_66(C4)
        C_mandel = tangent_voigt_to_mandel(C6)

        # Manual computation
        sqrt2 = np.sqrt(2)
        P = np.diag([1, 1, 1, sqrt2, sqrt2, sqrt2])
        P_inv = np.diag([1, 1, 1, 1 / sqrt2, 1 / sqrt2, 1 / sqrt2])
        C_mandel_manual = P @ C6 @ P_inv
        assert_allclose(C_mandel, C_mandel_manual, atol=1e-14)

    def test_mandel_tangent_symmetric_for_isotropic(self):
        """Mandel tangent of an isotropic material is symmetric."""
        lam, mu = 100.0, 50.0
        d = np.eye(3)  # Kronecker delta
        C4 = np.zeros((3, 3, 3, 3), dtype=np.float64)
        for i in range(3):
            for j in range(3):
                for k in range(3):
                    for el in range(3):
                        C4[i, j, k, el] = lam * d[i, j] * d[k, el] + mu * (
                            d[i, k] * d[j, el] + d[i, el] * d[j, k]
                        )
        C6 = tangent_to_voigt_66(C4)
        C_mandel = tangent_voigt_to_mandel(C6)
        assert_allclose(C_mandel, C_mandel.T, atol=1e-14)


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


class TestInputValidation:
    def test_tensor_wrong_shape(self):
        with pytest.raises(ValueError, match=r"Expected.*3.*3"):
            sym_tensor_to_voigt(np.zeros((2, 2)))

    def test_voigt_wrong_shape(self):
        with pytest.raises(ValueError, match=r"Expected.*6"):
            voigt_to_sym_tensor(np.zeros(3))

    def test_tangent_wrong_shape(self):
        with pytest.raises(ValueError, match=r"Expected.*3.*3.*3.*3"):
            tangent_to_voigt_66(np.zeros((3, 3)))

    def test_voigt_66_wrong_shape(self):
        with pytest.raises(ValueError, match=r"Expected.*6.*6"):
            voigt_66_to_tangent(np.zeros((3, 3)))
