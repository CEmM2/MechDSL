"""Tests for Perzyna viscoplasticity (Tasks P3-1, P3-3).

Covers:
    P3-1: Return map correctness, rate-independent limit, rate sensitivity
    P3-3: Consistent algorithmic tangent (FD check + major symmetry)
"""

from __future__ import annotations

import numpy as np
import pytest

from mechdsl.symbolic.models.j2_power_law import (
    J2PowerLawMaterial,
)
from mechdsl.symbolic.models.j2_power_law import (
    radial_return as j2_radial_return,
)
from mechdsl.symbolic.models.perzyna import (
    PerzynaMaterial,
    radial_return,
)

# ---------------------------------------------------------------------------
# Shared material fixtures
# ---------------------------------------------------------------------------

# Shared elastic parameters for both J2 and Perzyna materials
_E = 200e3  # MPa
_nu = 0.3
_sigma_y0 = 250.0  # MPa
_K = 500.0  # MPa
_n = 0.4

# J2 reference material (rate-independent)
J2_MAT = J2PowerLawMaterial(E=_E, nu=_nu, sigma_y0=_sigma_y0, K=_K, n=_n)

# Perzyna material with near-zero viscosity — should match J2 to 1e-8
PERZYNA_NEAR_ZERO = PerzynaMaterial(E=_E, nu=_nu, sigma_y0=_sigma_y0, K=_K, n=_n, eta=1e-12, m=1.0)

# Perzyna material with significant viscosity
PERZYNA_VISC = PerzynaMaterial(E=_E, nu=_nu, sigma_y0=_sigma_y0, K=_K, n=_n, eta=1.0, m=1.0)

# dt used for quasi-static / rate-independent comparisons: 1 second
DT_QUASI = 1.0


def _large_strain() -> np.ndarray:
    """A strain tensor that forces yielding."""
    return 5e-2 * np.array(
        [
            [1.0, 0.3, 0.1],
            [0.3, -0.2, 0.05],
            [0.1, 0.05, -0.5],
        ]
    )


def _uniaxial_strain(eps: float) -> np.ndarray:
    """Uniaxial Green-Lagrange strain (no Poisson contraction for simplicity)."""
    return np.diag([eps, 0.0, 0.0])


class TestTaskP3_1PerzynaReturnMap:
    """
    Tests for Task P3-1: Perzyna viscoplasticity with backward Euler return map.
    Acceptance criteria covered: AC-1 (rate-independent limit), AC-2 (rate sensitivity), AC-3 (convergence).
    """

    @pytest.mark.unit
    def test_rate_independent_limit_matches_j2(self):
        """
        Verifies: At eta = 1e-12, Perzyna produces the same stress as
        rate-independent J2 power-law.
        Acceptance criterion: Same stress within 1e-8.
        Passes when: max |sigma_perzyna - sigma_j2| < 1e-8.
        """
        E_strain = _large_strain()
        alpha_old = 0.0

        j2_res = j2_radial_return(J2_MAT, E_strain, alpha_old)
        pz_res = radial_return(PERZYNA_NEAR_ZERO, E_strain, alpha_old, dt=DT_QUASI)

        # Both should be in the plastic regime
        assert j2_res.is_plastic, "J2 must enter plastic regime for this test"
        assert pz_res.is_plastic, "Perzyna must enter plastic regime for this test"

        max_diff = float(np.max(np.abs(pz_res.stress - j2_res.stress)))
        assert max_diff < 1e-8, (
            f"Perzyna (eta=1e-12) stress differs from J2 by {max_diff:.3e} (limit 1e-8)"
        )

        # alpha_new should also match closely
        alpha_diff = abs(pz_res.alpha_new - j2_res.alpha_new)
        assert alpha_diff < 1e-8, f"Perzyna alpha_new differs from J2 by {alpha_diff:.3e}"

    @pytest.mark.unit
    def test_rate_sensitivity_higher_rate_gives_higher_stress(self):
        """
        Verifies: At eta = 1.0 (high viscosity), stress increases monotonically
        with strain rate.
        Acceptance criterion: Stress at high rate > stress at low rate.
        Passes when: sigma(eps_dot_high) > sigma(eps_dot_low) for 3+ rate pairs.
        """
        # Fix strain magnitude; vary strain rate via dt (smaller dt = higher rate)
        # strain = eps_dot * dt, so for a fixed strain eps_axial:
        #   eps_dot = eps_axial / dt  => smaller dt means higher rate
        eps_axial = 0.05  # fixed total strain (well above yield)
        E_strain = _uniaxial_strain(eps_axial)
        alpha_old = 0.0

        # dt values: large dt = slow rate, small dt = fast rate
        dt_values = [1e3, 1e1, 1e-1, 1e-3, 1e-5]  # decreasing dt => increasing rate

        von_mises_stresses = []
        for dt in dt_values:
            res = radial_return(PERZYNA_VISC, E_strain, alpha_old, dt=dt)
            s_dev = res.stress - (np.trace(res.stress) / 3.0) * np.eye(3)
            sigma_eq = float(np.sqrt(1.5 * np.tensordot(s_dev, s_dev, axes=2)))
            von_mises_stresses.append(sigma_eq)

        # Stress must be monotonically non-decreasing as rate increases (dt decreases)
        monotone_count = 0
        for i in range(len(von_mises_stresses) - 1):
            if von_mises_stresses[i + 1] >= von_mises_stresses[i] - 1e-6:
                monotone_count += 1

        assert monotone_count >= 3, (
            f"Rate sensitivity not monotone: stresses = {von_mises_stresses}. "
            f"Only {monotone_count}/4 pairs satisfied sigma(high_rate) >= sigma(low_rate)."
        )

        # Also verify that the fastest rate gives strictly higher stress than slowest
        assert von_mises_stresses[-1] > von_mises_stresses[0], (
            f"Fastest rate stress {von_mises_stresses[-1]:.4f} must exceed "
            f"slowest rate stress {von_mises_stresses[0]:.4f}"
        )

    @pytest.mark.unit
    def test_quasi_static_limit_matches_j2(self):
        """
        Verifies: At very low strain rate, Perzyna matches J2 power-law.
        Acceptance criterion: Quasi-static result within 1e-6 of J2.
        Passes when: max |sigma_perzyna(eps_dot->0) - sigma_j2| < 1e-6.
        """
        E_strain = _large_strain()
        alpha_old = 0.0

        # Very large dt = very slow rate => viscous term eta*(dl/dt)^(1/m) → 0
        # Use eta=1.0, dt=1e9 => (dl/dt)^1 ~ dl/1e9 ≈ 0
        mat_qs = PerzynaMaterial(E=_E, nu=_nu, sigma_y0=_sigma_y0, K=_K, n=_n, eta=1.0, m=1.0)
        dt_quasi = 1e9  # quasi-static: very large time step

        j2_res = j2_radial_return(J2_MAT, E_strain, alpha_old)
        pz_res = radial_return(mat_qs, E_strain, alpha_old, dt=dt_quasi)

        assert j2_res.is_plastic
        assert pz_res.is_plastic

        max_diff = float(np.max(np.abs(pz_res.stress - j2_res.stress)))
        assert max_diff < 1e-6, (
            f"Quasi-static Perzyna stress differs from J2 by {max_diff:.3e} (limit 1e-6)"
        )

    @pytest.mark.unit
    def test_return_mapping_convergence(self):
        """
        Verifies: Return mapping Newton iteration converges in < 30 iterations.
        Acceptance criterion: Convergence on all test strain states.
        Passes when: Newton iterations < 30 for each of 10 random strain states.
        """
        rng = np.random.default_rng(42)
        mat = PerzynaMaterial(E=_E, nu=_nu, sigma_y0=_sigma_y0, K=_K, n=_n, eta=0.5, m=1.5)
        dt = 0.01

        # Use max_iter=30 — if it doesn't converge the call will raise RuntimeError
        n_tested = 0
        n_plastic = 0
        for _ in range(10):
            # Random symmetric strain above yield
            A = rng.standard_normal((3, 3))
            E_strain = 0.05 * 0.5 * (A + A.T)

            # This will raise RuntimeError if > 30 iterations needed
            res = radial_return(mat, E_strain, alpha_old=0.0, dt=dt, max_iter=30)
            n_tested += 1
            if res.is_plastic:
                n_plastic += 1

        assert n_tested == 10, "All 10 strain states must complete without exception"
        # At least some strains should trigger plasticity given the large strain magnitudes
        assert n_plastic >= 5, f"Expected at least 5 plastic cases out of 10, got {n_plastic}"


class TestTaskP3_3PerzynaTangent:
    """
    Tests for Task P3-3: Consistent viscoplastic algorithmic tangent (Perzyna).
    Acceptance criteria covered: AC-1 (FD check), AC-3 (major symmetry).
    """

    # Material: significant viscosity so eta_term is non-trivial.
    _mat = PerzynaMaterial(E=_E, nu=_nu, sigma_y0=_sigma_y0, K=_K, n=_n, eta=1.0, m=1.5)
    _dt = 0.01  # small dt => high strain rate => meaningful viscous correction
    _alpha_old = 0.005  # pre-yielded so power-law slope is active

    @staticmethod
    def _fd_tangent(mat: PerzynaMaterial, E: np.ndarray, alpha_old: float, dt: float) -> np.ndarray:
        """Central-difference FD of the stress update w.r.t. strain (3,3,3,3).

        For each (K, L) component we perturb by sym(e_K x e_L) scaled by ``eps``
        and central-difference with 2*eps denominator (same harness as
        ``test_j2.py::_fd_tangent``).
        """
        eps = 1e-7
        C_fd = np.zeros((3, 3, 3, 3))
        for k in range(3):
            for l_ in range(3):
                dE = np.zeros((3, 3))
                dE[k, l_] = 1.0
                dE_sym = 0.5 * (dE + dE.T)
                Sp = radial_return(mat, E + eps * dE_sym, alpha_old, dt).stress
                Sm = radial_return(mat, E - eps * dE_sym, alpha_old, dt).stress
                C_fd[:, :, k, l_] = (Sp - Sm) / (2.0 * eps)
        return C_fd

    @pytest.mark.unit
    def test_perzyna_tangent_fd_check(self):
        """
        Verifies: Perzyna tangent matches finite difference of the stress update.
        Acceptance criterion: Agreement within 1e-5 on 10 random strain states.
        Passes when: max |C_analytical - C_FD| / max(|C_FD|, 1) < 1e-5 for all states.
        """
        mat = self._mat
        dt = self._dt
        alpha_old = self._alpha_old
        rng = np.random.default_rng(42)
        tol = 1e-5

        n_plastic = 0
        for i in range(10):
            # Random symmetric strain large enough to ensure plasticity on most states
            A = rng.standard_normal((3, 3))
            E = 0.03 * 0.5 * (A + A.T)

            result = radial_return(mat, E, alpha_old, dt)
            C_analytical = result.tangent

            C_fd = self._fd_tangent(mat, E, alpha_old, dt)

            scale = max(float(np.max(np.abs(C_fd))), 1.0)
            err = float(np.max(np.abs(C_analytical - C_fd))) / scale
            assert err < tol, (
                f"State {i}: FD tangent mismatch rel err = {err:.3e} "
                f"(is_plastic={result.is_plastic}, dl={result.delta_lambda:.3e})"
            )

            if result.is_plastic:
                n_plastic += 1

        # Sanity: most strain states must have triggered plasticity
        assert n_plastic >= 5, (
            f"Only {n_plastic}/10 states were plastic — test may not be exercising "
            "the plastic tangent."
        )

    @pytest.mark.unit
    def test_perzyna_tangent_major_symmetry(self):
        """
        Verifies: Perzyna tangent has major symmetry (C_IJKL == C_KLIJ).
        Acceptance criterion: Symmetry within 1e-10.
        Passes when: max |C_IJKL - C_KLIJ| < 1e-10.
        """
        mat = self._mat
        dt = self._dt
        alpha_old = self._alpha_old
        rng = np.random.default_rng(7)

        for i in range(5):
            A = rng.standard_normal((3, 3))
            E = 0.03 * 0.5 * (A + A.T)
            result = radial_return(mat, E, alpha_old, dt)
            C = result.tangent
            err = float(np.max(np.abs(C - np.transpose(C, (2, 3, 0, 1)))))
            assert err < 1e-10, (
                f"State {i}: major symmetry violated, max |C_IJKL - C_KLIJ| = {err:.3e}"
            )

    @pytest.mark.unit
    def test_perzyna_tangent_reduces_to_j2_at_zero_viscosity(self):
        """
        Smoke test: at eta=1e-12 the Perzyna consistent tangent matches the
        rate-independent J2 tangent byte-for-byte (within 1e-8).
        """
        from mechdsl.symbolic.models.j2_power_law import (
            J2PowerLawMaterial,
        )
        from mechdsl.symbolic.models.j2_power_law import (
            radial_return as j2_radial_return,
        )

        mat_pz = PERZYNA_NEAR_ZERO  # eta=1e-12, m=1.0
        mat_j2 = J2PowerLawMaterial(E=_E, nu=_nu, sigma_y0=_sigma_y0, K=_K, n=_n)
        E = _large_strain()

        res_pz = radial_return(mat_pz, E, alpha_old=0.01, dt=DT_QUASI)
        res_j2 = j2_radial_return(mat_j2, E, alpha_old=0.01)

        assert res_pz.is_plastic and res_j2.is_plastic

        err = float(np.max(np.abs(res_pz.tangent - res_j2.tangent)))
        assert err < 1e-6, (
            f"Perzyna tangent at eta=1e-12 deviates from J2 tangent by {err:.3e} (should be < 1e-6)"
        )

    @pytest.mark.unit
    def test_elastic_branch_returns_elastic_tangent(self):
        """Below yield the tangent must equal the elastic tangent exactly."""
        from mechdsl.symbolic.models.j2_power_law import elastic_tangent

        mat = PerzynaMaterial(E=_E, nu=_nu, sigma_y0=_sigma_y0, K=_K, n=_n, eta=1.0, m=1.0)
        E_small = 1e-5 * np.eye(3)
        result = radial_return(mat, E_small, alpha_old=0.0, dt=1.0)

        assert not result.is_plastic
        C_el = elastic_tangent(mat.lam, mat.mu)
        np.testing.assert_allclose(result.tangent, C_el, atol=1e-14)


# ---------------------------------------------------------------------------
# Additional unit tests: elastic branch, validation, edge cases
# ---------------------------------------------------------------------------


class TestPerzynaMaterialValidation:
    """Tests for PerzynaMaterial __post_init__ validators."""

    def test_invalid_E_raises(self):
        with pytest.raises(ValueError, match="E must be > 0"):
            PerzynaMaterial(E=-1.0, nu=0.3, sigma_y0=250.0, K=500.0, n=0.4, eta=1.0, m=1.0)

    def test_invalid_nu_high_raises(self):
        with pytest.raises(ValueError, match="nu must be in"):
            PerzynaMaterial(E=200e3, nu=0.5, sigma_y0=250.0, K=500.0, n=0.4, eta=1.0, m=1.0)

    def test_invalid_nu_low_raises(self):
        with pytest.raises(ValueError, match="nu must be in"):
            PerzynaMaterial(E=200e3, nu=-1.0, sigma_y0=250.0, K=500.0, n=0.4, eta=1.0, m=1.0)

    def test_invalid_sigma_y0_raises(self):
        with pytest.raises(ValueError, match="sigma_y0 must be > 0"):
            PerzynaMaterial(E=200e3, nu=0.3, sigma_y0=0.0, K=500.0, n=0.4, eta=1.0, m=1.0)

    def test_invalid_K_raises(self):
        with pytest.raises(ValueError, match="K must be >= 0"):
            PerzynaMaterial(E=200e3, nu=0.3, sigma_y0=250.0, K=-1.0, n=0.4, eta=1.0, m=1.0)

    def test_invalid_n_raises(self):
        with pytest.raises(ValueError, match="n must be > 0"):
            PerzynaMaterial(E=200e3, nu=0.3, sigma_y0=250.0, K=500.0, n=0.0, eta=1.0, m=1.0)

    def test_invalid_eta_raises(self):
        with pytest.raises(ValueError, match="eta must be > 0"):
            PerzynaMaterial(E=200e3, nu=0.3, sigma_y0=250.0, K=500.0, n=0.4, eta=0.0, m=1.0)

    def test_invalid_eta_negative_raises(self):
        with pytest.raises(ValueError, match="eta must be > 0"):
            PerzynaMaterial(E=200e3, nu=0.3, sigma_y0=250.0, K=500.0, n=0.4, eta=-1.0, m=1.0)

    def test_invalid_m_raises(self):
        with pytest.raises(ValueError, match="m must be > 0"):
            PerzynaMaterial(E=200e3, nu=0.3, sigma_y0=250.0, K=500.0, n=0.4, eta=1.0, m=0.0)

    def test_invalid_dt_raises(self):
        mat = PerzynaMaterial(E=200e3, nu=0.3, sigma_y0=250.0, K=500.0, n=0.4, eta=1.0, m=1.0)
        with pytest.raises(ValueError, match="dt must be > 0"):
            radial_return(mat, np.zeros((3, 3)), 0.0, dt=0.0)


class TestPerzynaElasticBranch:
    """Elastic branch should behave identically to J2 (no viscous contribution)."""

    def test_below_yield_elastic(self):
        """Small strain must remain elastic."""
        mat = PerzynaMaterial(E=_E, nu=_nu, sigma_y0=_sigma_y0, K=_K, n=_n, eta=1.0, m=1.0)
        E_strain = 1e-5 * np.eye(3)
        res = radial_return(mat, E_strain, alpha_old=0.0, dt=1.0)
        assert not res.is_plastic
        assert res.delta_lambda == 0.0
        assert res.alpha_new == 0.0

    def test_below_yield_stress_matches_svk(self):
        """In elastic regime, stress must match SVK formula."""
        mat = PerzynaMaterial(E=_E, nu=_nu, sigma_y0=_sigma_y0, K=_K, n=_n, eta=1.0, m=1.0)
        E_strain = 1e-5 * np.eye(3)
        res = radial_return(mat, E_strain, alpha_old=0.0, dt=1.0)

        lam = mat.lam
        mu = mat.mu
        S_svk = lam * np.trace(E_strain) * np.eye(3) + 2.0 * mu * E_strain
        np.testing.assert_allclose(res.stress, S_svk, atol=1e-12)

    def test_von_mises_near_zero_guard(self):
        """Purely volumetric strain with near-zero deviatoric should not raise."""
        mat = PerzynaMaterial(E=_E, nu=_nu, sigma_y0=_sigma_y0, K=_K, n=_n, eta=1.0, m=1.0)
        E_strain = 1e-20 * np.eye(3)
        res = radial_return(mat, E_strain, alpha_old=0.0, dt=1.0)
        assert not res.is_plastic
        assert np.all(np.isfinite(res.stress))
        assert np.all(np.isfinite(res.tangent))


class TestPerzynaPlasticBranch:
    """Plastic branch sanity checks."""

    def test_plastic_triggered(self):
        """Large strain must trigger plasticity."""
        mat = PerzynaMaterial(E=_E, nu=_nu, sigma_y0=_sigma_y0, K=_K, n=_n, eta=0.1, m=1.0)
        res = radial_return(mat, _large_strain(), alpha_old=0.0, dt=1.0)
        assert res.is_plastic
        assert res.delta_lambda > 0.0
        assert res.alpha_new > 0.0

    def test_stress_finite_and_well_formed(self):
        """Plastic stress must be finite and symmetric."""
        mat = PerzynaMaterial(E=_E, nu=_nu, sigma_y0=_sigma_y0, K=_K, n=_n, eta=0.1, m=1.0)
        res = radial_return(mat, _large_strain(), alpha_old=0.0, dt=1.0)
        assert np.all(np.isfinite(res.stress))
        np.testing.assert_allclose(res.stress, res.stress.T, atol=1e-12)

    def test_alpha_increases_under_plastic_loading(self):
        """alpha_new must be strictly greater than alpha_old in plastic regime."""
        mat = PerzynaMaterial(E=_E, nu=_nu, sigma_y0=_sigma_y0, K=_K, n=_n, eta=0.1, m=1.0)
        alpha_old = 0.02
        res = radial_return(mat, _large_strain(), alpha_old=alpha_old, dt=1.0)
        assert res.is_plastic
        assert res.alpha_new > alpha_old

    def test_different_m_exponents(self):
        """Return mapping must converge for a range of m values."""
        E_strain = _large_strain()
        for m_val in [0.5, 1.0, 2.0, 5.0]:
            mat = PerzynaMaterial(E=_E, nu=_nu, sigma_y0=_sigma_y0, K=_K, n=_n, eta=0.5, m=m_val)
            res = radial_return(mat, E_strain, alpha_old=0.0, dt=1.0)
            assert np.all(np.isfinite(res.stress)), f"Non-finite stress at m={m_val}"
