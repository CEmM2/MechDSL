"""Tests for J2 plasticity with power-law hardening (P3.3).

Covers:
    1. Below-yield elastic branch
    2. Above-yield plastic branch
    3. Yield stress monotonicity
    4. Return mapping consistency (f ≈ 0 after return)
    5. Below-yield matches SVK elastic stress
    6. Consistent tangent major symmetry
    7. Consistent tangent finite-difference check
    8. Von Mises near-zero guard
    9. Deviatoric: trace == 0
"""

from __future__ import annotations

import numpy as np
import pytest

from mechdsl.symbolic.models.j2_power_law import (
    J2PowerLawMaterial,
    deviatoric,
    elastic_tangent,
    radial_return,
    von_mises,
    yield_stress,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

STEEL = J2PowerLawMaterial(
    E=200e3,  # MPa
    nu=0.3,
    sigma_y0=250.0,  # MPa
    K=500.0,  # MPa
    n=0.4,
)


def _small_strain() -> np.ndarray:
    """A strain well below yield for steel-like material."""
    return 1e-5 * np.eye(3)


def _large_strain() -> np.ndarray:
    """A strain that forces yielding."""
    return 5e-2 * np.array(
        [
            [1.0, 0.3, 0.1],
            [0.3, -0.2, 0.05],
            [0.1, 0.05, -0.5],
        ]
    )


# ---------------------------------------------------------------------------
# 1. Below yield — elastic branch
# ---------------------------------------------------------------------------


def test_below_yield_elastic() -> None:
    """Small strain should remain elastic: is_plastic == False, delta_lambda == 0."""
    E_strain = _small_strain()
    result = radial_return(STEEL, E_strain, alpha_old=0.0)

    assert not result.is_plastic
    assert result.delta_lambda == 0.0
    assert result.alpha_new == 0.0


# ---------------------------------------------------------------------------
# 2. Above yield — plastic branch
# ---------------------------------------------------------------------------


def test_above_yield_plastic() -> None:
    """Large strain should trigger yielding: is_plastic == True, delta_lambda > 0."""
    E_strain = _large_strain()
    result = radial_return(STEEL, E_strain, alpha_old=0.0)

    assert result.is_plastic
    assert result.delta_lambda > 0.0
    assert result.alpha_new > 0.0


# ---------------------------------------------------------------------------
# 3. Yield stress monotonicity
# ---------------------------------------------------------------------------


def test_yield_stress_monotonicity() -> None:
    """sigma_y(alpha) should be monotonically increasing for K > 0, n > 0."""
    alphas = np.linspace(0.0, 1.0, 50)
    sy_values = [yield_stress(STEEL, a) for a in alphas]

    for i in range(len(sy_values) - 1):
        assert sy_values[i + 1] >= sy_values[i], (
            f"Yield stress decreased: sigma_y({alphas[i + 1]:.4f}) = {sy_values[i + 1]:.6f} "
            f"< sigma_y({alphas[i]:.4f}) = {sy_values[i]:.6f}"
        )


def test_yield_stress_at_zero() -> None:
    """sigma_y(0) == sigma_y0."""
    assert yield_stress(STEEL, 0.0) == STEEL.sigma_y0


# ---------------------------------------------------------------------------
# 4. Return mapping consistency: f(S_updated, alpha_new) ≈ 0
# ---------------------------------------------------------------------------


def test_return_mapping_consistency() -> None:
    """After return, the yield function should be satisfied to within tolerance."""
    E_strain = _large_strain()
    result = radial_return(STEEL, E_strain, alpha_old=0.0)

    assert result.is_plastic

    # Recompute yield function at converged state
    S_dev = deviatoric(result.stress)
    sigma_eq = von_mises(S_dev)
    sy = yield_stress(STEEL, result.alpha_new)

    f = sigma_eq - sy
    assert abs(f) < 1e-10, f"Yield function residual |f| = {abs(f):.3e}"


# ---------------------------------------------------------------------------
# 5. Below-yield stress matches SVK elastic stress
# ---------------------------------------------------------------------------


def test_below_yield_matches_svk() -> None:
    """In the elastic regime, radial_return stress == lambda*tr(E)*I + 2*mu*E."""
    E_strain = _small_strain()
    result = radial_return(STEEL, E_strain, alpha_old=0.0)

    lam = STEEL.lam
    mu = STEEL.mu
    S_svk = lam * np.trace(E_strain) * np.eye(3) + 2.0 * mu * E_strain

    np.testing.assert_allclose(result.stress, S_svk, atol=1e-12)


# ---------------------------------------------------------------------------
# 6. Consistent tangent symmetry: C[I,J,K,L] == C[K,L,I,J]
# ---------------------------------------------------------------------------


def test_tangent_major_symmetry_elastic() -> None:
    """Elastic tangent has major symmetry."""
    E_strain = _small_strain()
    result = radial_return(STEEL, E_strain, alpha_old=0.0)
    C = result.tangent

    for ii in range(3):
        for jj in range(3):
            for kk in range(3):
                for ll in range(3):
                    assert abs(C[ii, jj, kk, ll] - C[kk, ll, ii, jj]) < 1e-12, (
                        f"Major symmetry violated at ({ii},{jj},{kk},{ll}): "
                        f"{C[ii, jj, kk, ll]:.6e} != {C[kk, ll, ii, jj]:.6e}"
                    )


def test_tangent_major_symmetry_plastic() -> None:
    """Algorithmic tangent has major symmetry in plastic regime."""
    E_strain = _large_strain()
    result = radial_return(STEEL, E_strain, alpha_old=0.0)
    C = result.tangent

    for ii in range(3):
        for jj in range(3):
            for kk in range(3):
                for ll in range(3):
                    assert abs(C[ii, jj, kk, ll] - C[kk, ll, ii, jj]) < 1e-10, (
                        f"Major symmetry violated at ({ii},{jj},{kk},{ll}): "
                        f"{C[ii, jj, kk, ll]:.6e} != {C[kk, ll, ii, jj]:.6e}"
                    )


# ---------------------------------------------------------------------------
# 7. Consistent tangent finite-difference check
# ---------------------------------------------------------------------------


def _fd_tangent(
    mat: J2PowerLawMaterial,
    E_strain: np.ndarray,
    alpha_old: float,
    eps: float = 1e-7,
) -> np.ndarray:
    """Compute the tangent C_IJKL via central finite differences.

    For each (K, L) component we construct a symmetric perturbation
    dE_sym = sym(e_K x e_L) and compute dS / dE_{KL} by central differencing.
    """
    C_fd = np.zeros((3, 3, 3, 3))
    for K in range(3):
        for L in range(3):
            # Symmetric perturbation in the (K, L) direction
            dE = np.zeros((3, 3))
            dE[K, L] = 1.0
            dE_sym = 0.5 * (dE + dE.T)

            E_plus = E_strain + eps * dE_sym
            E_minus = E_strain - eps * dE_sym

            S_plus = radial_return(mat, E_plus, alpha_old=alpha_old).stress
            S_minus = radial_return(mat, E_minus, alpha_old=alpha_old).stress

            C_fd[:, :, K, L] = (S_plus - S_minus) / (2.0 * eps)

    return C_fd


def test_tangent_fd_elastic() -> None:
    """Finite-difference check of elastic tangent."""
    E_strain = _small_strain()
    result = radial_return(STEEL, E_strain, alpha_old=0.0)
    C_alg = result.tangent
    C_fd = _fd_tangent(STEEL, E_strain, alpha_old=0.0)

    # Elastic regime: smooth tangent, central FD with h=1e-7 should match to 1e-8
    np.testing.assert_allclose(C_alg, C_fd, atol=1e-8, rtol=1e-8)


def test_tangent_fd_plastic() -> None:
    """Finite-difference check of algorithmic (consistent) tangent in plastic regime."""
    E_strain = _large_strain()
    alpha_old = 0.01  # some accumulated plastic strain
    result = radial_return(STEEL, E_strain, alpha_old=alpha_old)
    C_alg = result.tangent

    assert result.is_plastic, "Expected plastic regime for FD check"

    C_fd = _fd_tangent(STEEL, E_strain, alpha_old=alpha_old)

    np.testing.assert_allclose(C_alg, C_fd, atol=1e-4, rtol=1e-4)


# ---------------------------------------------------------------------------
# 8. Von Mises near-zero guard
# ---------------------------------------------------------------------------


def test_von_mises_near_zero_guard() -> None:
    """Near-zero deviatoric stress should not cause division by zero."""
    # Purely volumetric strain => deviatoric stress ~ 0
    E_strain = 1e-20 * np.eye(3)
    result = radial_return(STEEL, E_strain, alpha_old=0.0)

    assert not result.is_plastic
    assert np.all(np.isfinite(result.stress))
    assert np.all(np.isfinite(result.tangent))


def test_von_mises_zero_tensor() -> None:
    """Von Mises of zero tensor is zero."""
    assert von_mises(np.zeros((3, 3))) == 0.0


def test_von_mises_pure_shear() -> None:
    """Von Mises of pure shear matches analytical value."""
    # tau_xy = 100 => s = [[0, 100, 0], [100, 0, 0], [0, 0, 0]]
    # sigma_eq = sqrt(3/2 * 2 * 100^2) = sqrt(3) * 100
    s = np.array([[0.0, 100.0, 0.0], [100.0, 0.0, 0.0], [0.0, 0.0, 0.0]])
    expected = np.sqrt(3.0) * 100.0
    assert abs(von_mises(s) - expected) < 1e-10


# ---------------------------------------------------------------------------
# 9. Deviatoric: trace == 0
# ---------------------------------------------------------------------------


def test_deviatoric_trace_zero() -> None:
    """Trace of deviatoric part of any symmetric tensor is zero."""
    rng = np.random.default_rng(42)
    for _ in range(10):
        A = rng.standard_normal((3, 3))
        A_sym = 0.5 * (A + A.T)
        A_dev = deviatoric(A_sym)
        assert abs(np.trace(A_dev)) < 1e-14


def test_deviatoric_of_deviatoric() -> None:
    """Deviatoric of deviatoric is itself (projection is idempotent)."""
    rng = np.random.default_rng(123)
    A = rng.standard_normal((3, 3))
    A_sym = 0.5 * (A + A.T)
    A_dev = deviatoric(A_sym)
    A_dev_dev = deviatoric(A_dev)
    np.testing.assert_allclose(A_dev, A_dev_dev, atol=1e-14)


# ---------------------------------------------------------------------------
# Additional edge-case tests
# ---------------------------------------------------------------------------


def test_elastic_tangent_matches_result_tangent() -> None:
    """In elastic regime, the returned tangent matches the standalone elastic_tangent."""
    E_strain = _small_strain()
    result = radial_return(STEEL, E_strain, alpha_old=0.0)
    C_el = elastic_tangent(STEEL.lam, STEEL.mu)
    np.testing.assert_allclose(result.tangent, C_el, atol=1e-12)


def test_lame_parameters() -> None:
    """Verify Lame parameter formulas."""
    mat = J2PowerLawMaterial(E=200e3, nu=0.3, sigma_y0=250.0, K=500.0, n=0.4)
    # lambda = E*nu / ((1+nu)(1-2nu))
    expected_lam = 200e3 * 0.3 / (1.3 * 0.4)
    expected_mu = 200e3 / (2.0 * 1.3)
    assert abs(mat.lam - expected_lam) < 1e-10
    assert abs(mat.mu - expected_mu) < 1e-10


def test_plastic_with_prior_hardening() -> None:
    """Return mapping works correctly with non-zero alpha_old."""
    E_strain = _large_strain()
    alpha_old = 0.05

    result = radial_return(STEEL, E_strain, alpha_old=alpha_old)
    assert result.is_plastic
    assert result.alpha_new > alpha_old

    # Consistency: yield function satisfied
    S_dev = deviatoric(result.stress)
    sigma_eq = von_mises(S_dev)
    sy = yield_stress(STEEL, result.alpha_new)
    assert abs(sigma_eq - sy) < 1e-10


def test_uniaxial_tension_elastic() -> None:
    """Uniaxial small strain: S_11 = E * epsilon, S_22 = S_33 from Poisson."""
    eps_11 = 1e-6  # very small
    E_strain = np.diag([eps_11, -STEEL.nu * eps_11, -STEEL.nu * eps_11])
    result = radial_return(STEEL, E_strain, alpha_old=0.0)

    assert not result.is_plastic
    # S_11 should be close to E * eps_11 for uniaxial
    # Via Lame: S_11 = lam*(1 - 2*nu)*eps_11 + 2*mu*eps_11 = E*eps_11
    expected_S11 = STEEL.E * eps_11
    assert abs(result.stress[0, 0] - expected_S11) < 1e-6 * abs(expected_S11) + 1e-15


# ---------------------------------------------------------------------------
# R3.5.1 — Error path tests (T1, T2)
# ---------------------------------------------------------------------------


class TestRadialReturnErrorPaths:
    """Tests for radial_return error paths added in Phase 2 (H3) and Phase 3."""

    def test_radial_return_non_convergence(self) -> None:
        """T1: Return mapping must raise RuntimeError when max_iter is too small."""
        mat = J2PowerLawMaterial(E=200e3, nu=0.3, sigma_y0=250.0, K=1000.0, n=0.5)
        # Uniaxial tension well above yield to ensure plastic regime
        E_strain = np.diag([0.01, -0.003, -0.003])
        with pytest.raises(RuntimeError, match="did not converge"):
            radial_return(mat, E_strain, alpha_old=0.0, max_iter=0)

    def test_radial_return_stalled_newton(self) -> None:
        """T2: Stalled Newton either converges with dl>=0 or raises — never silently fails."""
        mat = J2PowerLawMaterial(E=200e3, nu=0.3, sigma_y0=250.0, K=1e8, n=0.1)
        # Uniaxial strain produces deviatoric stress that exceeds yield
        E_strain = np.diag([0.1, -0.03, -0.03])
        try:
            result = radial_return(mat, E_strain, alpha_old=0.0)
            assert result.delta_lambda >= 0.0
            assert result.is_plastic  # must have entered plastic regime
        except RuntimeError:
            pass  # Expected: stall or non-convergence

    def test_negative_delta_lambda_guard(self) -> None:
        """A valid plastic return always has delta_lambda >= 0."""
        mat = J2PowerLawMaterial(E=200e3, nu=0.3, sigma_y0=250.0, K=1000.0, n=0.5)
        # Uniaxial strain above yield — ensures plastic path is exercised
        E_strain = np.diag([0.005, -0.0015, -0.0015])
        result = radial_return(mat, E_strain, alpha_old=0.0)
        assert result.is_plastic, "Must enter plastic regime for this test"
        assert result.delta_lambda >= 0.0


# ---------------------------------------------------------------------------
# R3.5.3 — __post_init__ validation tests for J2PowerLawMaterial
# ---------------------------------------------------------------------------


class TestJ2MaterialValidation:
    """Tests for J2PowerLawMaterial __post_init__ validators."""

    def test_invalid_E_raises(self) -> None:
        with pytest.raises(ValueError, match="E must be > 0"):
            J2PowerLawMaterial(E=-1.0, nu=0.3, sigma_y0=250.0, K=1000.0, n=0.5)

    def test_invalid_nu_high_raises(self) -> None:
        with pytest.raises(ValueError, match="nu must be in"):
            J2PowerLawMaterial(E=200e3, nu=0.5, sigma_y0=250.0, K=1000.0, n=0.5)

    def test_invalid_nu_low_raises(self) -> None:
        with pytest.raises(ValueError, match="nu must be in"):
            J2PowerLawMaterial(E=200e3, nu=-1.0, sigma_y0=250.0, K=1000.0, n=0.5)

    def test_invalid_sigma_y0_raises(self) -> None:
        with pytest.raises(ValueError, match="sigma_y0 must be > 0"):
            J2PowerLawMaterial(E=200e3, nu=0.3, sigma_y0=0.0, K=1000.0, n=0.5)

    def test_invalid_K_raises(self) -> None:
        with pytest.raises(ValueError, match="K must be >= 0"):
            J2PowerLawMaterial(E=200e3, nu=0.3, sigma_y0=250.0, K=-1.0, n=0.5)

    def test_invalid_n_raises(self) -> None:
        with pytest.raises(ValueError, match="n must be > 0"):
            J2PowerLawMaterial(E=200e3, nu=0.3, sigma_y0=250.0, K=1000.0, n=0.0)
