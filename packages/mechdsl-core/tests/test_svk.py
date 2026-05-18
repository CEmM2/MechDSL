"""Tests for the St. Venant-Kirchhoff (SVK) constitutive model.

Verifies stress, tangent symmetries, and consistency with Voigt utilities.
"""

import numpy as np
import pytest
from numpy.testing import assert_allclose

from mechdsl.symbolic.models.svk import (
    SVKMaterial,
    material_tangent_4th,
    material_tangent_voigt,
    pk2_stress,
)
from mechdsl.symbolic.voigt import tangent_to_voigt_66

# ---------------------------------------------------------------------------
# Material fixtures
# ---------------------------------------------------------------------------

LAM = 115384.615384615  # lambda for E=200e3, nu=0.3
MU = 76923.076923077  # mu for E=200e3, nu=0.3


@pytest.fixture
def steel() -> SVKMaterial:
    return SVKMaterial.from_E_nu(200e3, 0.3)


@pytest.fixture
def simple_mat() -> SVKMaterial:
    return SVKMaterial(lam=100.0, mu=50.0)


# ---------------------------------------------------------------------------
# from_E_nu
# ---------------------------------------------------------------------------


class TestFromENu:
    def test_lambda_value(self, steel: SVKMaterial):
        assert steel.lam == pytest.approx(LAM, rel=1e-10)

    def test_mu_value(self, steel: SVKMaterial):
        assert steel.mu == pytest.approx(MU, rel=1e-10)

    def test_known_values(self):
        """E=1, nu=0.25 -> lam=0.4, mu=0.4."""
        mat = SVKMaterial.from_E_nu(1.0, 0.25)
        assert mat.lam == pytest.approx(0.4, rel=1e-12)
        assert mat.mu == pytest.approx(0.4, rel=1e-12)


# ---------------------------------------------------------------------------
# PK2 stress
# ---------------------------------------------------------------------------


class TestPK2Stress:
    def test_zero_strain_gives_zero_stress(self, simple_mat: SVKMaterial):
        E = np.zeros((3, 3), dtype=np.float64)
        S = pk2_stress(simple_mat, E)
        assert_allclose(S, np.zeros((3, 3)), atol=1e-15)

    def test_uniaxial_strain(self, simple_mat: SVKMaterial):
        """Uniaxial E_11 only: S_11 = (lam + 2*mu) * E_11, S_22 = S_33 = lam * E_11."""
        E = np.zeros((3, 3), dtype=np.float64)
        E[0, 0] = 0.01
        S = pk2_stress(simple_mat, E)

        lam, mu = simple_mat.lam, simple_mat.mu
        assert S[0, 0] == pytest.approx((lam + 2 * mu) * 0.01, rel=1e-12)
        assert S[1, 1] == pytest.approx(lam * 0.01, rel=1e-12)
        assert S[2, 2] == pytest.approx(lam * 0.01, rel=1e-12)
        # off-diag zero
        assert S[0, 1] == pytest.approx(0.0, abs=1e-15)
        assert S[0, 2] == pytest.approx(0.0, abs=1e-15)
        assert S[1, 2] == pytest.approx(0.0, abs=1e-15)

    def test_pure_shear(self, simple_mat: SVKMaterial):
        """Pure shear E_12 = E_21 = gamma/2: S_12 = 2*mu*E_12."""
        E = np.zeros((3, 3), dtype=np.float64)
        gamma = 0.005
        E[0, 1] = gamma / 2
        E[1, 0] = gamma / 2
        S = pk2_stress(simple_mat, E)
        assert S[0, 1] == pytest.approx(2 * simple_mat.mu * gamma / 2, rel=1e-12)
        # trace(E) = 0, so diagonal of S should be zero
        assert S[0, 0] == pytest.approx(0.0, abs=1e-15)
        assert S[1, 1] == pytest.approx(0.0, abs=1e-15)
        assert S[2, 2] == pytest.approx(0.0, abs=1e-15)

    def test_hydrostatic_strain(self, simple_mat: SVKMaterial):
        """Hydrostatic E = e*I: S = (3*lam + 2*mu)*e*I."""
        e = 0.002
        E = e * np.eye(3, dtype=np.float64)
        S = pk2_stress(simple_mat, E)
        expected_diag = (3 * simple_mat.lam + 2 * simple_mat.mu) * e
        assert S[0, 0] == pytest.approx(expected_diag, rel=1e-12)
        assert S[1, 1] == pytest.approx(expected_diag, rel=1e-12)
        assert S[2, 2] == pytest.approx(expected_diag, rel=1e-12)


# ---------------------------------------------------------------------------
# Material tangent symmetries
# ---------------------------------------------------------------------------


class TestTangentSymmetries:
    def test_major_symmetry(self, simple_mat: SVKMaterial):
        """C_IJKL == C_KLIJ (major symmetry)."""
        C4 = material_tangent_4th(simple_mat)
        for i in range(3):
            for j in range(3):
                for k in range(3):
                    for el in range(3):
                        assert C4[i, j, k, el] == pytest.approx(C4[k, el, i, j], abs=1e-14), (
                            f"Major sym failed at ({i},{j},{k},{el})"
                        )

    def test_minor_symmetry_left(self, simple_mat: SVKMaterial):
        """C_IJKL == C_JIKL (minor symmetry, left pair)."""
        C4 = material_tangent_4th(simple_mat)
        for i in range(3):
            for j in range(3):
                for k in range(3):
                    for el in range(3):
                        assert C4[i, j, k, el] == pytest.approx(C4[j, i, k, el], abs=1e-14), (
                            f"Minor left sym failed at ({i},{j},{k},{el})"
                        )

    def test_minor_symmetry_right(self, simple_mat: SVKMaterial):
        """C_IJKL == C_IJLK (minor symmetry, right pair)."""
        C4 = material_tangent_4th(simple_mat)
        for i in range(3):
            for j in range(3):
                for k in range(3):
                    for el in range(3):
                        assert C4[i, j, k, el] == pytest.approx(C4[i, j, el, k], abs=1e-14), (
                            f"Minor right sym failed at ({i},{j},{k},{el})"
                        )


# ---------------------------------------------------------------------------
# Tangent = dS/dE (finite difference verification)
# ---------------------------------------------------------------------------


class TestTangentFiniteDifference:
    def test_tangent_matches_numerical_dSdE(self, simple_mat: SVKMaterial):
        """Verify C_IJKL = dS_IJ/dE_KL by finite difference perturbation.

        Computes dS_ij/dE_kl for all 81 components individually, then
        symmetrises the result in the (k,l) pair to recover minor symmetry:
            C_ijkl = (dS_ij/dE_kl + dS_ij/dE_lk) / 2
        This is necessary because pk2_stress treats E as a general matrix,
        so perturbing E[k,l] alone misses the E[l,k] coupling.
        """
        rng = np.random.default_rng(42)
        E0 = 0.01 * rng.standard_normal((3, 3))
        E0 = 0.5 * (E0 + E0.T)  # symmetrise

        C4_analytical = material_tangent_4th(simple_mat)

        eps = 1e-7
        # Raw partial derivatives dS_ij / dE_kl (no symmetry assumed)
        dSdE_raw = np.zeros((3, 3, 3, 3), dtype=np.float64)
        for k in range(3):
            for el in range(3):
                E_plus = E0.copy()
                E_minus = E0.copy()
                E_plus[k, el] += eps
                E_minus[k, el] -= eps

                S_plus = pk2_stress(simple_mat, E_plus)
                S_minus = pk2_stress(simple_mat, E_minus)
                dSdE_raw[:, :, k, el] = (S_plus - S_minus) / (2.0 * eps)

        # Symmetrise in (k,l) to get the tangent on the symmetric manifold
        C4_numerical = 0.5 * (dSdE_raw + dSdE_raw.transpose(0, 1, 3, 2))

        # SVK tangent is constant, so analytical should match regardless of E0
        assert_allclose(C4_numerical, C4_analytical, atol=1e-5)


# ---------------------------------------------------------------------------
# Voigt tangent consistency
# ---------------------------------------------------------------------------


class TestVoigtTangentConsistency:
    def test_voigt_tangent_matches_tangent_to_voigt_66(self, simple_mat: SVKMaterial):
        """material_tangent_voigt == tangent_to_voigt_66(material_tangent_4th)."""
        C6_direct = material_tangent_voigt(simple_mat)
        C4 = material_tangent_4th(simple_mat)
        C6_via_util = tangent_to_voigt_66(C4)
        assert_allclose(C6_direct, C6_via_util, atol=1e-14)

    def test_voigt_tangent_symmetric(self, steel: SVKMaterial):
        """6x6 Voigt tangent must be symmetric for SVK."""
        C6 = material_tangent_voigt(steel)
        assert_allclose(C6, C6.T, atol=1e-14)

    def test_voigt_tangent_known_values(self, simple_mat: SVKMaterial):
        """Spot-check known entries of isotropic tangent in Voigt form."""
        C6 = material_tangent_voigt(simple_mat)
        lam, mu = simple_mat.lam, simple_mat.mu
        # C6[0,0] = lam + 2*mu
        assert C6[0, 0] == pytest.approx(lam + 2 * mu)
        # C6[0,1] = lam
        assert C6[0, 1] == pytest.approx(lam)
        # C6[3,3] = mu (shear modulus, unscaled)
        assert C6[3, 3] == pytest.approx(mu)
        # C6[4,4] = mu
        assert C6[4, 4] == pytest.approx(mu)
        # C6[5,5] = mu
        assert C6[5, 5] == pytest.approx(mu)
        # Off-diagonal shear-normal coupling = 0
        assert C6[0, 3] == pytest.approx(0.0, abs=1e-15)
        assert C6[3, 0] == pytest.approx(0.0, abs=1e-15)


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


class TestSVKInputValidation:
    def test_wrong_strain_shape(self, simple_mat: SVKMaterial):
        with pytest.raises(ValueError, match=r"Expected.*3.*3"):
            pk2_stress(simple_mat, np.zeros((2, 2)))


# ---------------------------------------------------------------------------
# R3.5.3 — __post_init__ validation tests for SVKMaterial
# ---------------------------------------------------------------------------


class TestSVKMaterialValidation:
    """Tests for SVKMaterial __post_init__ and from_E_nu validators."""

    def test_invalid_mu_raises(self) -> None:
        with pytest.raises(ValueError, match=r"mu.*must be > 0"):
            SVKMaterial(lam=100.0, mu=-1.0)

    def test_from_E_nu_invalid_E_raises(self) -> None:
        with pytest.raises(ValueError, match="E must be > 0"):
            SVKMaterial.from_E_nu(E=-1.0, nu=0.3)

    def test_from_E_nu_invalid_nu_raises(self) -> None:
        with pytest.raises(ValueError, match="nu must be in"):
            SVKMaterial.from_E_nu(E=200e3, nu=0.5)
