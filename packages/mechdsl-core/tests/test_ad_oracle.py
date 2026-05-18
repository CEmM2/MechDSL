"""Tests for the AD oracle verification module (P3.5).

Verifies:
1. SVK stress: FD oracle matches pk2_stress over random deformation states
2. SVK tangent: FD oracle matches material_tangent_4th (constant for SVK)
3. J2 elastic branch: below-yield J2 stress matches SVK stress
4. Random deformation generator: all samples have J > 0
5. FD stress on known energy function: W = 0.5*tr(E^2) gives S = E
"""

from __future__ import annotations

import numpy as np
from numpy.testing import assert_allclose

from mechdsl.lib.tensor_ops import det_33, green_lagrange
from mechdsl.symbolic.models.svk import (
    SVKMaterial,
    material_tangent_4th,
    pk2_stress,
)
from mechdsl.verify.ad_oracle import (
    fd_stress_from_energy,
    fd_tangent_from_stress,
    generate_random_deformation,
    verify_j2_elastic_branch,
    verify_svk,
)

# ---------------------------------------------------------------------------
# Material parameters
# ---------------------------------------------------------------------------

SVK_PARAMS_LAME = {"lam": 100.0, "mu": 50.0}
SVK_PARAMS_E_NU = {"E": 200e3, "nu": 0.3}
J2_PARAMS = {
    "E": 200e3,
    "nu": 0.3,
    "sigma_y0": 250.0,
    "K": 500.0,
    "n": 0.4,
}


# ---------------------------------------------------------------------------
# 1. SVK stress: FD oracle vs pk2_stress
# ---------------------------------------------------------------------------


class TestSVKStress:
    def test_fd_stress_matches_pk2_stress(self) -> None:
        """FD oracle stress matches pk2_stress over 100 random deformation states."""
        result = verify_svk(SVK_PARAMS_LAME, n_samples=100, seed=42)
        assert result["max_stress_error"] < 1e-6, (
            f"SVK stress FD error too large: {result['max_stress_error']:.3e}"
        )

    def test_fd_stress_matches_pk2_stress_e_nu(self) -> None:
        """Same test with E/nu parameterisation."""
        result = verify_svk(SVK_PARAMS_E_NU, n_samples=50, seed=123)
        assert result["max_stress_error"] < 1e-6, (
            f"SVK stress FD error too large: {result['max_stress_error']:.3e}"
        )

    def test_zero_strain_gives_zero_stress(self) -> None:
        """FD stress of SVK energy at zero strain is zero."""
        mat = SVKMaterial(lam=100.0, mu=50.0)

        def energy(E: np.ndarray) -> float:
            tr_E = np.trace(E)
            tr_E2 = np.trace(E @ E)
            return 0.5 * mat.lam * tr_E**2 + mat.mu * tr_E2

        E_zero = np.zeros((3, 3), dtype=np.float64)
        S_fd = fd_stress_from_energy(energy, E_zero)
        assert_allclose(S_fd, np.zeros((3, 3)), atol=1e-12)


# ---------------------------------------------------------------------------
# 2. SVK tangent: FD oracle vs material_tangent_4th
# ---------------------------------------------------------------------------


class TestSVKTangent:
    def test_fd_tangent_matches_analytical(self) -> None:
        """FD oracle tangent matches material_tangent_4th over 100 random states.

        SVK tangent is constant, so this verifies FD correctness at many
        different strain states.
        """
        result = verify_svk(SVK_PARAMS_LAME, n_samples=100, seed=42)
        assert result["max_tangent_error"] < 1e-6, (
            f"SVK tangent FD error too large: {result['max_tangent_error']:.3e}"
        )

    def test_tangent_at_zero_strain(self) -> None:
        """FD tangent at zero strain matches analytical tangent."""
        mat = SVKMaterial(lam=100.0, mu=50.0)
        C4_analytical = material_tangent_4th(mat)

        E_zero = np.zeros((3, 3), dtype=np.float64)
        C4_fd = fd_tangent_from_stress(lambda e: pk2_stress(mat, e), E_zero)

        C_norm = np.linalg.norm(C4_analytical)
        rel_err = np.linalg.norm(C4_analytical - C4_fd) / C_norm
        assert rel_err < 1e-6, f"Tangent FD error at zero strain: {rel_err:.3e}"

    def test_all_passed_flag(self) -> None:
        """verify_svk returns all_passed=True for correct implementation."""
        result = verify_svk(SVK_PARAMS_LAME, n_samples=20, seed=99)
        assert result["all_passed"] is True


# ---------------------------------------------------------------------------
# 3. J2 elastic branch: stress matches SVK for below-yield strains
# ---------------------------------------------------------------------------


class TestJ2ElasticBranch:
    def test_j2_elastic_matches_svk(self) -> None:
        """Below-yield J2 stress matches SVK elastic stress over 100 samples."""
        result = verify_j2_elastic_branch(J2_PARAMS, n_samples=100, seed=42)
        assert result["max_stress_error"] < 1e-6, (
            f"J2 elastic branch error too large: {result['max_stress_error']:.3e}"
        )

    def test_all_passed_flag(self) -> None:
        """verify_j2_elastic_branch returns all_passed=True."""
        result = verify_j2_elastic_branch(J2_PARAMS, n_samples=50, seed=77)
        assert result["all_passed"] is True


# ---------------------------------------------------------------------------
# 4. Random deformation generator: all samples have J > 0
# ---------------------------------------------------------------------------


class TestRandomDeformation:
    def test_all_positive_jacobian(self) -> None:
        """All generated deformation gradients have positive Jacobian."""
        rng = np.random.default_rng(42)
        n_samples = 200
        for i in range(n_samples):
            F = generate_random_deformation(rng)
            J = det_33(F)
            assert J > 0.0, f"Sample {i}: J = {J:.6e} <= 0"

    def test_shape(self) -> None:
        """Generated F is (3,3)."""
        rng = np.random.default_rng(0)
        F = generate_random_deformation(rng)
        assert F.shape == (3, 3)

    def test_not_identity(self) -> None:
        """Generated F is not exactly the identity (has a perturbation)."""
        rng = np.random.default_rng(42)
        F = generate_random_deformation(rng)
        assert np.linalg.norm(F - np.eye(3)) > 1e-10

    def test_produces_valid_green_lagrange(self) -> None:
        """Green-Lagrange strain from generated F is symmetric."""
        rng = np.random.default_rng(42)
        for _ in range(50):
            F = generate_random_deformation(rng)
            E = green_lagrange(F)
            assert_allclose(E, E.T, atol=1e-14)


# ---------------------------------------------------------------------------
# 5. FD stress on known energy function
# ---------------------------------------------------------------------------


class TestFDStressKnownEnergy:
    def test_half_trace_E_squared_gives_S_equals_E(self) -> None:
        """For W = 0.5 * tr(E^2), we have S = dW/dE = E.

        This verifies the FD stress routine on a simple known case.
        """
        rng = np.random.default_rng(42)
        for _ in range(20):
            R = rng.standard_normal((3, 3))
            E_strain = 0.01 * 0.5 * (R + R.T)  # small symmetric strain

            def energy_half_trace_sq(E: np.ndarray) -> float:
                return 0.5 * np.trace(E @ E)

            S_fd = fd_stress_from_energy(energy_half_trace_sq, E_strain)

            S_norm = np.linalg.norm(E_strain)
            if S_norm > 1e-15:
                rel_err = np.linalg.norm(S_fd - E_strain) / S_norm
                assert rel_err < 1e-6, f"W=0.5*tr(E^2) FD error: {rel_err:.3e}"
            else:
                assert_allclose(S_fd, E_strain, atol=1e-12)

    def test_trace_E_squared_gives_S_equals_2E(self) -> None:
        """For W = tr(E^2), we have S = dW/dE = 2*E."""
        rng = np.random.default_rng(99)
        for _ in range(10):
            R = rng.standard_normal((3, 3))
            E_strain = 0.01 * 0.5 * (R + R.T)

            def energy_trace_sq(E: np.ndarray) -> float:
                return float(np.trace(E @ E))

            S_fd = fd_stress_from_energy(energy_trace_sq, E_strain)
            S_exact = 2.0 * E_strain

            S_norm = np.linalg.norm(S_exact)
            if S_norm > 1e-15:
                rel_err = np.linalg.norm(S_fd - S_exact) / S_norm
                assert rel_err < 1e-6, f"W=tr(E^2) FD error: {rel_err:.3e}"

    def test_volumetric_energy_gives_volumetric_stress(self) -> None:
        """For W = 0.5 * tr(E)^2, we have S = tr(E) * I."""
        rng = np.random.default_rng(55)
        for _ in range(10):
            R = rng.standard_normal((3, 3))
            E_strain = 0.01 * 0.5 * (R + R.T)

            def energy_vol(E: np.ndarray) -> float:
                tr = np.trace(E)
                return 0.5 * tr**2

            S_fd = fd_stress_from_energy(energy_vol, E_strain)
            S_exact = np.trace(E_strain) * np.eye(3)

            S_norm = np.linalg.norm(S_exact)
            if S_norm > 1e-15:
                rel_err = np.linalg.norm(S_fd - S_exact) / S_norm
                assert rel_err < 1e-6


# ---------------------------------------------------------------------------
# FD tangent on known stress function
# ---------------------------------------------------------------------------


class TestFDTangentKnownStress:
    def test_identity_tangent(self) -> None:
        """For S(E) = E, the tangent is the 4th-order symmetric identity.

        C_IJKL = dE_IJ/dE_KL = 0.5*(delta_IK*delta_JL + delta_IL*delta_JK)
        """
        E_strain = 0.01 * np.eye(3, dtype=np.float64)

        def stress_is_E(E: np.ndarray) -> np.ndarray:
            return E.copy()

        C4_fd = fd_tangent_from_stress(stress_is_E, E_strain)

        # Expected: I_sym_{IJKL} = 0.5*(d_IK*d_JL + d_IL*d_JK)
        d = np.eye(3, dtype=np.float64)
        I_sym = np.zeros((3, 3, 3, 3), dtype=np.float64)
        for ii in range(3):
            for jj in range(3):
                for kk in range(3):
                    for ll in range(3):
                        I_sym[ii, jj, kk, ll] = 0.5 * (
                            d[ii, kk] * d[jj, ll] + d[ii, ll] * d[jj, kk]
                        )

        rel_err = np.linalg.norm(C4_fd - I_sym) / np.linalg.norm(I_sym)
        assert rel_err < 1e-6, f"Identity tangent FD error: {rel_err:.3e}"
