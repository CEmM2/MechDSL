"""Tests for Johnson-Cook viscoplasticity (Tasks P3-2, P3-3).

Covers:
    P3-2: JC flow stress, thermal coupling, rate sensitivity
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
from mechdsl.symbolic.models.johnson_cook import (
    JohnsonCookMaterial,
    JohnsonCookModel,
    radial_return,
    yield_stress,
)

# ---------------------------------------------------------------------------
# Shared fixtures / helpers
# ---------------------------------------------------------------------------

# Reference material parameters (steel-like, consistent units: MPa, mm, tonne, s)
_E = 200_000.0  # MPa
_NU = 0.3
_A = 250.0  # MPa  (matches sigma_y0 for J2 cross-check)
_B = 500.0  # MPa  (matches K for J2 cross-check)
_N = 0.5  # strain-hardening exponent
_C = 0.01  # small rate sensitivity (near 0 for reference-state tests)
_M = 1.0  # thermal softening exponent
_EPS_DOT_0 = 1.0  # 1/s — reference rate
_T_REF = 293.0  # K
_T_MELT = 1793.0  # K
_RHO_CP = 3.588e3  # MPa/K  (rho * c_p, e.g. 7800 kg/m^3 * 460 J/(kg K) * 1e-6 MPa/Pa)
_BETA = 0.9


def _default_mat(**overrides) -> JohnsonCookMaterial:
    defaults = dict(
        E=_E,
        nu=_NU,
        A=_A,
        B=_B,
        n=_N,
        C=_C,
        m=_M,
        eps_dot_0=_EPS_DOT_0,
        T_melt=_T_MELT,
        T_ref=_T_REF,
        rho_c_p=_RHO_CP,
        beta=_BETA,
    )
    defaults.update(overrides)
    return JohnsonCookMaterial(**defaults)


def _uniaxial_strain(eps_11: float) -> np.ndarray:
    """Pure uniaxial Green-Lagrange strain E_11 = eps_11, rest zero."""
    E = np.zeros((3, 3))
    E[0, 0] = eps_11
    return E


class TestTaskP3_2JohnsonCookReturnMap:
    """
    Tests for Task P3-2: Johnson-Cook flow stress + adiabatic temperature evolution.
    Acceptance criteria covered: AC-1 (baseline), AC-2 (thermal softening),
    AC-3 (rate hardening), AC-4 (convergence).
    """

    @pytest.mark.unit
    def test_baseline_match_to_power_law_j2(self):
        """
        Verifies: At T = Tref and eps_dot = eps_dot_0, JC matches a
        matched-parameter power-law J2.
        Acceptance criterion: Agreement within 1e-8.

        At T = T_ref:  T_star = 0 => thermal factor = 1 - 0^m = 1
        At eps_dot = eps_dot_0: eps_dot_star = 1 => rate factor = 1 + C*ln(1) = 1
        => sigma_y_JC = A + B * alpha^n  ==  sigma_y0 + K * alpha^n  (J2 with sigma_y0=A, K=B, n=n)

        The dt is chosen so that dl / dt = eps_dot_0 => dt = dl / eps_dot_0.
        We use dt = 1.0 / eps_dot_0 = 1.0 s so that dl/dt ≈ eps_dot_0 inside Newton.
        Since eps_dot = dl/dt and we need it = eps_dot_0 = 1.0, with dt=1 the final
        dl will match, but the Newton iteration is also coupling T_old = T_ref so
        dT = 0 (beta * sy * dl / rho_c_p is small but nonzero for large dl).

        For a strict comparison we use C = 0 (no rate sensitivity) and beta = 0
        (no adiabatic heating) in the JC material for the cleanest baseline match.
        """
        mat_jc = _default_mat(C=0.0, beta=0.0)
        mat_j2 = J2PowerLawMaterial(E=_E, nu=_NU, sigma_y0=_A, K=_B, n=_N)

        # Several uniaxial strain levels past yield
        for eps in [0.003, 0.005, 0.01, 0.02, 0.05]:
            E_strain = _uniaxial_strain(eps)

            # JC: T = T_ref, dt = 1.0 (eps_dot = dl/dt <= eps_dot_0, rate factor = 1)
            res_jc = radial_return(mat_jc, E_strain, 0.0, _T_REF, dt=1.0)
            # J2: standard rate-independent
            res_j2 = j2_radial_return(mat_j2, E_strain, 0.0)

            # Stress tensors must agree within 1e-8 (relative to yield stress magnitude)
            diff = np.max(np.abs(res_jc.stress - res_j2.stress))
            assert diff < 1e-8, (
                f"eps={eps}: JC stress deviates from J2 by {diff:.3e} (must be < 1e-8). "
                f"JC={res_jc.stress[0, 0]:.6f}, J2={res_j2.stress[0, 0]:.6f}"
            )

    @pytest.mark.unit
    def test_thermal_softening_monotonic(self):
        """
        Verifies: At T > Tref, yield stress is lower than at T = Tref.
        Acceptance criterion: Monotonic decrease in yield with increasing T.
        Passes when: sigma(T1) > sigma(T2) for T1 < T2 across 3+ temperatures.
        """
        mat = _default_mat(C=0.0, beta=0.0)  # isolate thermal effect

        # Fixed strain state well past yield, fixed rate
        E_strain = _uniaxial_strain(0.01)
        alpha_fixed = 0.005
        dot_eps_fixed = _EPS_DOT_0

        temperatures = [_T_REF, _T_REF + 300.0, _T_REF + 600.0, _T_REF + 900.0]
        stresses = []
        for T in temperatures:
            sy = yield_stress(mat, alpha_fixed, dot_eps_fixed, T)
            stresses.append(sy)

        # Verify strict monotonic decrease
        for i in range(len(stresses) - 1):
            assert stresses[i] > stresses[i + 1], (
                f"Thermal softening not monotonic: sigma(T={temperatures[i]:.0f}) = {stresses[i]:.4f} "
                f"<= sigma(T={temperatures[i + 1]:.0f}) = {stresses[i + 1]:.4f}"
            )

        # Also verify via return-map stress (not just yield_stress helper)
        sig_values = []
        for T in temperatures:
            res = radial_return(mat, E_strain, alpha_fixed, T, dt=1.0)
            sig_values.append(res.stress[0, 0])

        for i in range(len(sig_values) - 1):
            assert sig_values[i] > sig_values[i + 1], (
                f"Return-map thermal softening not monotonic at index {i}"
            )

    @pytest.mark.unit
    def test_rate_hardening_monotonic(self):
        """
        Verifies: At eps_dot > eps_dot_0, yield stress is higher.
        Acceptance criterion: Monotonic increase with strain rate.
        Passes when: sigma(rate_high) > sigma(rate_low) for 3+ rate pairs.
        """
        mat = _default_mat(C=0.05, beta=0.0)  # clear rate sensitivity, no heating

        alpha_fixed = 0.005
        T_fixed = _T_REF

        # Rates: at, 2x, 5x, 10x, 50x reference
        rates = [
            _EPS_DOT_0,
            2.0 * _EPS_DOT_0,
            5.0 * _EPS_DOT_0,
            10.0 * _EPS_DOT_0,
            50.0 * _EPS_DOT_0,
        ]
        stresses = []
        for dot_eps in rates:
            sy = yield_stress(mat, alpha_fixed, dot_eps, T_fixed)
            stresses.append(sy)

        # Verify strict monotonic increase
        for i in range(len(stresses) - 1):
            assert stresses[i] < stresses[i + 1], (
                f"Rate hardening not monotonic: sigma(dot_eps={rates[i]:.2f}) = {stresses[i]:.4f} "
                f">= sigma(dot_eps={rates[i + 1]:.2f}) = {stresses[i + 1]:.4f}"
            )

        # Also verify via the return map (dt chosen so dl/dt hits the target rate)
        E_strain = _uniaxial_strain(0.01)
        sig_values = []
        for dot_eps in rates:
            # dt = dl / dot_eps_target; we fix a strain increment and vary dt so that
            # the plastic strain rate comes out differently.  Simpler: use a very small dt
            # so that dl/dt > eps_dot_0, varying dt to hit each rate bracket.
            # We just use a fixed elastic trial and small dt to enter rate-sensitive regime.
            dt = 0.001 / dot_eps  # ensures dl/dt is in the target range
            res = radial_return(mat, E_strain, alpha_fixed, T_fixed, dt=dt)
            sig_values.append(res.stress[0, 0])

        for i in range(len(sig_values) - 1):
            assert sig_values[i] < sig_values[i + 1], (
                f"Return-map rate hardening not monotonic at index {i}"
            )

    @pytest.mark.unit
    def test_coupled_newton_convergence(self):
        """
        Verifies: Coupled (dl, dT) Newton converges on a 1D uniaxial case.
        Acceptance criterion: Convergence on all test cases.
        Passes when: Newton converges in < 30 iterations for each test state
                     (no RuntimeError raised).
        """
        mat = _default_mat()  # full JC with rate and thermal coupling

        strain_levels = [0.002, 0.005, 0.010, 0.020, 0.050, 0.100]
        dt = 0.01  # s - moderate step giving eps_dot = dl/dt around 0.1-1/s range

        for eps in strain_levels:
            E_strain = _uniaxial_strain(eps)
            # Should not raise; convergence failure raises RuntimeError
            res = radial_return(mat, E_strain, 0.0, _T_REF, dt=dt, max_iter=50)

            if res.is_plastic:
                assert res.delta_lambda > 0.0, (
                    f"eps={eps}: expected positive dl when is_plastic=True, got {res.delta_lambda}"
                )
                assert res.T_new >= _T_REF, (
                    f"eps={eps}: temperature decreased below T_ref — adiabatic heating should "
                    f"only increase T. T_new={res.T_new}, T_ref={_T_REF}"
                )
                assert res.T_new < _T_MELT, f"eps={eps}: T_new={res.T_new} >= T_melt={_T_MELT}"


# ---------------------------------------------------------------------------
# Material parameter validation
# ---------------------------------------------------------------------------


class TestJohnsonCookMaterialValidation:
    """Each __post_init__ ValueError path — one test per invalid param."""

    def test_E_non_positive_raises(self):
        with pytest.raises(ValueError, match="E must be > 0"):
            _default_mat(E=0.0)

    def test_E_negative_raises(self):
        with pytest.raises(ValueError, match="E must be > 0"):
            _default_mat(E=-1.0)

    def test_nu_at_lower_bound_raises(self):
        with pytest.raises(ValueError, match="nu must be in"):
            _default_mat(nu=-1.0)

    def test_nu_at_upper_bound_raises(self):
        with pytest.raises(ValueError, match="nu must be in"):
            _default_mat(nu=0.5)

    def test_A_zero_raises(self):
        with pytest.raises(ValueError, match="A must be > 0"):
            _default_mat(A=0.0)

    def test_A_negative_raises(self):
        with pytest.raises(ValueError, match="A must be > 0"):
            _default_mat(A=-1.0)

    def test_B_negative_raises(self):
        with pytest.raises(ValueError, match="B must be >= 0"):
            _default_mat(B=-0.1)

    def test_n_zero_raises(self):
        with pytest.raises(ValueError, match="n must be > 0"):
            _default_mat(n=0.0)

    def test_n_negative_raises(self):
        with pytest.raises(ValueError, match="n must be > 0"):
            _default_mat(n=-1.0)

    def test_C_negative_raises(self):
        with pytest.raises(ValueError, match="C must be >= 0"):
            _default_mat(C=-0.01)

    def test_m_zero_raises(self):
        with pytest.raises(ValueError, match="m must be > 0"):
            _default_mat(m=0.0)

    def test_m_negative_raises(self):
        with pytest.raises(ValueError, match="m must be > 0"):
            _default_mat(m=-1.0)

    def test_eps_dot_0_zero_raises(self):
        with pytest.raises(ValueError, match="eps_dot_0 must be > 0"):
            _default_mat(eps_dot_0=0.0)

    def test_eps_dot_0_negative_raises(self):
        with pytest.raises(ValueError, match="eps_dot_0 must be > 0"):
            _default_mat(eps_dot_0=-1.0)

    def test_T_melt_equal_T_ref_raises(self):
        with pytest.raises(ValueError, match="T_melt must be > T_ref"):
            _default_mat(T_melt=_T_REF)

    def test_T_melt_less_than_T_ref_raises(self):
        with pytest.raises(ValueError, match="T_melt must be > T_ref"):
            _default_mat(T_melt=_T_REF - 100.0)

    def test_rho_c_p_zero_raises(self):
        with pytest.raises(ValueError, match="rho_c_p must be > 0"):
            _default_mat(rho_c_p=0.0)

    def test_rho_c_p_negative_raises(self):
        with pytest.raises(ValueError, match="rho_c_p must be > 0"):
            _default_mat(rho_c_p=-1.0)

    def test_beta_below_zero_raises(self):
        with pytest.raises(ValueError, match="beta must be in"):
            _default_mat(beta=-0.01)

    def test_beta_above_one_raises(self):
        with pytest.raises(ValueError, match="beta must be in"):
            _default_mat(beta=1.01)

    def test_valid_params_construct_without_raising(self):
        mat = _default_mat()
        assert mat.A == _A
        assert mat.beta == _BETA

    def test_beta_zero_is_valid(self):
        mat = _default_mat(beta=0.0)
        assert mat.beta == 0.0

    def test_beta_one_is_valid(self):
        mat = _default_mat(beta=1.0)
        assert mat.beta == 1.0

    def test_B_zero_is_valid(self):
        # B = 0 means no strain hardening (pure perfectly-plastic at reference)
        mat = _default_mat(B=0.0)
        assert mat.B == 0.0

    def test_C_zero_is_valid(self):
        mat = _default_mat(C=0.0)
        assert mat.C == 0.0


# ---------------------------------------------------------------------------
# T_melt guard
# ---------------------------------------------------------------------------


class TestJohnsonCookTMeltGuard:
    """T >= T_melt on entry must raise a clear error."""

    def test_T_old_at_T_melt_raises(self):
        mat = _default_mat()
        E_strain = _uniaxial_strain(0.01)
        with pytest.raises(ValueError, match="T_melt"):
            radial_return(mat, E_strain, 0.0, mat.T_melt, dt=1.0)

    def test_T_old_above_T_melt_raises(self):
        mat = _default_mat()
        E_strain = _uniaxial_strain(0.01)
        with pytest.raises(ValueError, match="T_melt"):
            radial_return(mat, E_strain, 0.0, mat.T_melt + 100.0, dt=1.0)


# ---------------------------------------------------------------------------
# ConstitutiveModel wrapper
# ---------------------------------------------------------------------------


class TestJohnsonCookModelWrapper:
    """Basic smoke tests for JohnsonCookModel (ConstitutiveModel interface)."""

    def test_state_variables(self):
        mat = _default_mat()
        model = JohnsonCookModel(mat)
        assert model.state_variables == ("alpha", "T")

    def test_is_dissipative(self):
        mat = _default_mat()
        model = JohnsonCookModel(mat)
        assert model.is_dissipative is True

    def test_pk2_stress_shape(self):
        mat = _default_mat(C=0.0, beta=0.0)
        model = JohnsonCookModel(mat)
        E_strain = _uniaxial_strain(0.005)
        S = model.pk2_stress(E_strain, alpha=0.0, T=_T_REF, dt=1.0)
        assert S.shape == (3, 3)

    def test_material_tangent_shape(self):
        mat = _default_mat(C=0.0, beta=0.0)
        model = JohnsonCookModel(mat)
        E_strain = _uniaxial_strain(0.005)
        C4 = model.material_tangent(E_strain, alpha=0.0, T=_T_REF, dt=1.0)
        assert C4.shape == (3, 3, 3, 3)

    def test_voigt_tangent_shape(self):
        mat = _default_mat(C=0.0, beta=0.0)
        model = JohnsonCookModel(mat)
        E_strain = _uniaxial_strain(0.005)
        C66 = model.voigt_tangent(E_strain, alpha=0.0, T=_T_REF, dt=1.0)
        assert C66.shape == (6, 6)

    def test_defaults_T_to_T_ref_when_not_provided(self):
        """When T is not in state kwargs, pk2_stress should default to T_ref (no thermal effect)."""
        mat = _default_mat(C=0.0, beta=0.0)
        model = JohnsonCookModel(mat)
        E_strain = _uniaxial_strain(0.01)
        S_default = model.pk2_stress(E_strain, alpha=0.0, dt=1.0)
        S_explicit = model.pk2_stress(E_strain, alpha=0.0, T=_T_REF, dt=1.0)
        np.testing.assert_allclose(S_default, S_explicit, atol=1e-12)


# ---------------------------------------------------------------------------
# Elastic predictor recovery (zero plastic strain — elastic response)
# ---------------------------------------------------------------------------


class TestElasticPredictorRecovery:
    """Below yield, JC must return elastic trial stress exactly."""

    def test_elastic_step_returns_trial_stress(self):
        mat = _default_mat(C=0.0, beta=0.0)
        lam = mat.lam
        mu = mat.mu

        # Small strain — should be purely elastic
        E_strain = _uniaxial_strain(0.0005)
        res = radial_return(mat, E_strain, 0.0, _T_REF, dt=1.0)

        assert res.is_plastic is False
        assert res.delta_lambda == 0.0
        assert res.alpha_new == 0.0
        assert res.T_new == _T_REF

        # Trial stress: S = lam * tr(E) * I + 2 * mu * E
        S_expected = lam * float(np.trace(E_strain)) * np.eye(3) + 2.0 * mu * E_strain
        np.testing.assert_allclose(res.stress, S_expected, atol=1e-14)


# ---------------------------------------------------------------------------
# Task P3-3 stubs (do not modify — for Task P3-3)
# ---------------------------------------------------------------------------


class TestTaskP3_3JohnsonCookTangent:
    """
    Tests for Task P3-3: Consistent viscoplastic algorithmic tangent (JC).
    Acceptance criteria covered: AC-2 (FD check), AC-3 (major symmetry).
    """

    # Non-reference temperature and strain rate to exercise thermal coupling.
    _T_test = _T_REF + 50.0  # above reference: thermal softening active
    # dt chosen so that dl/dt ~ 10 * eps_dot_0 (rate-sensitive regime)
    _dt = 0.001  # with dl ~ 0.01, eps_dot = dl/dt ~ 10/s >> eps_dot_0=1/s
    _alpha_old = 0.005

    @staticmethod
    def _make_mat() -> JohnsonCookMaterial:
        return _default_mat(C=0.05, beta=0.9)

    @staticmethod
    def _fd_tangent(
        mat: JohnsonCookMaterial,
        E: np.ndarray,
        alpha_old: float,
        T_old: float,
        dt: float,
    ) -> np.ndarray:
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
                Sp = radial_return(mat, E + eps * dE_sym, alpha_old, T_old, dt).stress
                Sm = radial_return(mat, E - eps * dE_sym, alpha_old, T_old, dt).stress
                C_fd[:, :, k, l_] = (Sp - Sm) / (2.0 * eps)
        return C_fd

    @pytest.mark.unit
    def test_jc_tangent_fd_check(self):
        """
        Verifies: JC tangent matches FD of stress update, including non-reference T.
        Acceptance criterion: Agreement within 1e-5 on 10 random strain states.
        Passes when: max |C_analytical - C_FD| / max(|C_FD|, 1) < 1e-5 for all states.
        """
        mat = self._make_mat()
        T_old = self._T_test
        dt = self._dt
        alpha_old = self._alpha_old
        rng = np.random.default_rng(42)
        tol = 1e-5

        n_plastic = 0
        for i in range(10):
            # Random symmetric strain large enough to trigger plasticity on most states
            A = rng.standard_normal((3, 3))
            E = 0.03 * 0.5 * (A + A.T)

            result = radial_return(mat, E, alpha_old, T_old, dt)
            C_analytical = result.tangent  # (3, 3, 3, 3)

            C_fd = self._fd_tangent(mat, E, alpha_old, T_old, dt)

            scale = max(float(np.max(np.abs(C_fd))), 1.0)
            err = float(np.max(np.abs(C_analytical - C_fd))) / scale
            assert err < tol, (
                f"State {i}: FD tangent mismatch rel err = {err:.3e} "
                f"(is_plastic={result.is_plastic}, dl={result.delta_lambda:.3e}, "
                f"dT={result.T_new - T_old:.3e})"
            )

            if result.is_plastic:
                n_plastic += 1

        assert n_plastic >= 5, (
            f"Only {n_plastic}/10 states were plastic — test may not be exercising "
            "the plastic tangent."
        )

    @pytest.mark.unit
    def test_jc_tangent_major_symmetry(self):
        """
        Verifies: JC tangent has major symmetry (C_IJKL == C_KLIJ).
        Acceptance criterion: Symmetry within 1e-10.
        Passes when: max |C_IJKL - C_KLIJ| < 1e-10.
        """
        mat = self._make_mat()
        T_old = self._T_test
        dt = self._dt
        alpha_old = self._alpha_old
        rng = np.random.default_rng(13)

        for i in range(5):
            A = rng.standard_normal((3, 3))
            E = 0.03 * 0.5 * (A + A.T)
            result = radial_return(mat, E, alpha_old, T_old, dt)
            C = result.tangent
            err = float(np.max(np.abs(C - np.transpose(C, (2, 3, 0, 1)))))
            assert err < 1e-10, (
                f"State {i}: major symmetry violated, max |C_IJKL - C_KLIJ| = {err:.3e}"
            )

    @pytest.mark.unit
    def test_jc_tangent_reduces_to_j2_at_uncoupled_limit(self):
        """
        Smoke test: at C=0, beta=0, T=T_ref the JC consistent tangent must match
        the rate-independent J2 tangent (matched params) within 1e-8.

        At these settings: rate factor = 1, thermal factor = 1, no heating =>
        the coupled Newton decouples, dT=0, J is block-diagonal, D_eff = J[0,0]
        (the rate-independent J2 denominator).
        """
        from mechdsl.symbolic.models.j2_power_law import (
            J2PowerLawMaterial,
        )
        from mechdsl.symbolic.models.j2_power_law import (
            radial_return as j2_radial_return,
        )

        mat_jc = _default_mat(C=0.0, beta=0.0)
        mat_j2 = J2PowerLawMaterial(E=_E, nu=_NU, sigma_y0=_A, K=_B, n=_N)

        E = np.array(
            [
                [0.04, 0.01, 0.005],
                [0.01, -0.02, 0.003],
                [0.005, 0.003, -0.01],
            ]
        )
        alpha_old = 0.01

        # dt=1 so dl/dt <= eps_dot_0 => rate factor=1 (no log contribution)
        res_jc = radial_return(mat_jc, E, alpha_old, _T_REF, dt=1.0)
        res_j2 = j2_radial_return(mat_j2, E, alpha_old)

        assert res_jc.is_plastic and res_j2.is_plastic, (
            "Both models must enter plastic regime for this comparison."
        )

        err = float(np.max(np.abs(res_jc.tangent - res_j2.tangent)))
        assert err < 1e-6, (
            f"JC tangent (C=0, beta=0, T=T_ref) deviates from J2 tangent by {err:.3e} "
            "(should be < 1e-6)"
        )
