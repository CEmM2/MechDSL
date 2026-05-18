"""Tests for Lemaitre damage variable + evolution equation (Task P6-1).

Covers scalar damage D in [0,1), evolution dD/dp = (Y/S_d)^s_d with
Y = sigma_eq^2 R_v / (2 E (1-D)^2). State (alpha, D) per QP. Effective stress
sigma_eff = sigma/(1-D). Damage threshold eps_D — no damage until alpha > eps_D.
Couples to J2 power-law (not Perzyna/JC).

Four required acceptance-test cases plus failure-route coverage:
1. D monotonic under monotonic load
2. Damage threshold respected (D=0 until alpha > eps_D)
3. D=0 matches J2 power law (regression guard)
4. D approaches D_crit and stays below 1
5. Pure hydrostatic load: no plastic flow => no damage
6. Elastic load (below yield): alpha = D = 0
7. D -> 1 clamp triggers (D_new < 1 - 1e-6)
8. triaxiality_factor matches analytic uniaxial value
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
from mechdsl.symbolic.models.lemaitre import (
    LemaitreMaterial,
    energy_release_rate,
    lemaitre_return,
    triaxiality_factor,
)
from mechdsl.symbolic.voigt import sym_tensor_to_voigt

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_E = 200e3  # MPa
_NU = 0.3
_SIGMA_Y0 = 250.0  # MPa
_K = 500.0
_N = 0.4
_S_D = 1.0  # MPa (damage denominator)
_SD_EXP = 1.0  # damage exponent s_d
_EPS_D = 0.0  # damage threshold (zero => damage always active once plastic)


def _j2_mat() -> J2PowerLawMaterial:
    return J2PowerLawMaterial(E=_E, nu=_NU, sigma_y0=_SIGMA_Y0, K=_K, n=_N)


def _lemaitre_mat(
    S_d: float = _S_D,
    s_d: float = _SD_EXP,
    eps_D: float = _EPS_D,
) -> LemaitreMaterial:
    return LemaitreMaterial(
        E=_E,
        nu=_NU,
        sigma_y0=_SIGMA_Y0,
        K=_K,
        n=_N,
        S_d=S_d,
        s_d=s_d,
        eps_D=eps_D,
    )


def _uniaxial_strain(eps: float) -> np.ndarray:
    """Uniaxial Green-Lagrange strain (no Poisson contraction)."""
    return np.diag([eps, 0.0, 0.0])


def _hydrostatic_strain(eps: float) -> np.ndarray:
    return eps * np.eye(3)


class TestTaskP6_1:
    """Unit tests for Lemaitre CDM implementation (Task P6-1)."""

    @pytest.mark.unit
    def test_d_monotonic_under_monotonic_load(self) -> None:
        """Verify D is non-decreasing under monotonic plastic loading.

        Uses uniaxial tension where sigma_H/sigma_eq = 1/3, so R_v > 2/3(1+nu)
        (the triaxiality factor is genuinely exercised, not 1 or 0).
        """
        mat = _lemaitre_mat(S_d=1.0, s_d=1.0, eps_D=0.0)

        alpha = 0.0
        D = 0.0
        prev_D = 0.0
        saw_plastic = False

        eps_values = np.linspace(0.001, 0.05, 20)  # monotonically increasing
        for eps in eps_values:
            E_strain = _uniaxial_strain(eps)
            res = lemaitre_return(mat, E_strain, alpha_n=alpha, D_n=D, dt=1.0)
            # D must be non-decreasing
            assert res.D_new >= prev_D - 1e-15, (
                f"D decreased from {prev_D} to {res.D_new} at eps={eps}"
            )
            if res.delta_lambda > 0.0:
                saw_plastic = True
            alpha = res.alpha_new
            D = res.D_new
            prev_D = D

        assert saw_plastic, "Test must enter plastic regime to exercise damage"
        assert D > 0.0, "Damage must grow under monotonic plastic loading"

    @pytest.mark.unit
    def test_damage_threshold_respected(self) -> None:
        """Verify D stays at 0 until accumulated plastic strain alpha exceeds eps_D.

        Uses uniaxial tension with a non-trivial threshold.
        """
        eps_D_threshold = 0.005
        mat = _lemaitre_mat(S_d=1.0, s_d=1.0, eps_D=eps_D_threshold)

        alpha = 0.0
        D = 0.0
        saw_below_threshold_plastic = False
        saw_above_threshold = False

        # Ramp through yield
        for eps in np.linspace(0.0015, 0.03, 40):
            E_strain = _uniaxial_strain(eps)
            res = lemaitre_return(mat, E_strain, alpha_n=alpha, D_n=D, dt=1.0)

            if res.alpha_new <= eps_D_threshold:
                if res.is_plastic:
                    saw_below_threshold_plastic = True
                # Below threshold: D must be exactly unchanged
                assert res.D_new == D, (
                    f"D changed below threshold: alpha_new={res.alpha_new}, "
                    f"eps_D={eps_D_threshold}, D_old={D}, D_new={res.D_new}"
                )
            else:
                saw_above_threshold = True

            alpha = res.alpha_new
            D = res.D_new

        assert saw_below_threshold_plastic, (
            "Test must have at least one plastic step below the threshold to be meaningful"
        )
        assert saw_above_threshold, "Test must cross the threshold to exercise it"
        assert D > 0.0, "Damage must accumulate past the threshold"

    @pytest.mark.unit
    def test_d_zero_matches_j2_power_law(self) -> None:
        """Regression guard: at D_n=0 AND eps_D so high that D stays 0, Lemaitre stress
        must byte-match J2 power-law (single step)."""
        # Use an enormous eps_D so damage never activates on a single step
        mat = _lemaitre_mat(S_d=1.0, s_d=1.0, eps_D=1e9)
        j2_mat = _j2_mat()

        # Try multiple strain states to avoid coincidental match
        strains = [
            _uniaxial_strain(0.03),
            np.diag([0.02, -0.01, -0.005]),
            np.array([[0.03, 0.01, 0.0], [0.01, -0.01, 0.005], [0.0, 0.005, -0.005]]),
        ]
        for E_strain in strains:
            lem = lemaitre_return(mat, E_strain, alpha_n=0.0, D_n=0.0, dt=1.0)
            j2 = j2_radial_return(j2_mat, E_strain, alpha_old=0.0)

            assert lem.D_new == 0.0, f"D must remain 0 when eps_D large, got {lem.D_new}"
            assert lem.alpha_new == pytest.approx(j2.alpha_new, abs=1e-14)
            assert lem.delta_lambda == pytest.approx(j2.delta_lambda, abs=1e-14)
            max_diff = float(np.max(np.abs(lem.stress - j2.stress)))
            assert max_diff < 1e-12, (
                f"Lemaitre (D=0) stress differs from J2 by {max_diff:.3e}, expected < 1e-12"
            )

    @pytest.mark.unit
    def test_d_approaches_dcrit_stays_below_one(self) -> None:
        """Verify D remains bounded below 1 even under very large plastic strain
        (the 1-D divisor must not blow up; clamp must trigger)."""
        # Use small S_d and large s_d so damage grows fast
        mat = _lemaitre_mat(S_d=0.01, s_d=1.0, eps_D=0.0)

        alpha = 0.0
        D = 0.0
        # Drive to very large plastic strain
        for eps in np.linspace(0.01, 1.0, 200):
            E_strain = _uniaxial_strain(eps)
            res = lemaitre_return(mat, E_strain, alpha_n=alpha, D_n=D, dt=1.0)
            alpha = res.alpha_new
            D = res.D_new
            # Strict invariant: clamp ensures D < 1 - 1e-6
            assert D < 1.0 - 1e-6 + 1e-15, f"D={D} violated clamp at eps={eps}"

        # By end of loading, D should have hit or approached the clamp
        assert D > 0.5, f"Sanity: with aggressive params, D should be high by the end, got {D}"
        assert D <= 1.0 - 1e-6, f"D={D} must respect the (1-1e-6) ceiling"


class TestTaskP6_1FailureRoutes:
    """Extra coverage for code paths not hit by the four acceptance tests."""

    @pytest.mark.unit
    def test_pure_hydrostatic_no_plastic_no_damage(self) -> None:
        """Hydrostatic load produces no deviatoric stress (sigma_eq=0),
        no plastic flow, so D must stay at D_n."""
        mat = _lemaitre_mat()
        E_strain = _hydrostatic_strain(1e-3)
        res = lemaitre_return(mat, E_strain, alpha_n=0.0, D_n=0.0, dt=1.0)
        assert not res.is_plastic
        assert res.alpha_new == 0.0
        assert res.D_new == 0.0
        assert res.delta_lambda == 0.0

    @pytest.mark.unit
    def test_elastic_below_yield_no_damage(self) -> None:
        """Purely elastic loading (below yield): alpha and D must remain 0."""
        mat = _lemaitre_mat()
        # very small strain, no yield
        E_strain = _uniaxial_strain(1e-5)
        res = lemaitre_return(mat, E_strain, alpha_n=0.0, D_n=0.0, dt=1.0)
        assert not res.is_plastic
        assert res.alpha_new == 0.0
        assert res.D_new == 0.0

    @pytest.mark.unit
    def test_triaxiality_factor_uniaxial(self) -> None:
        """For uniaxial stress state (sigma_H/sigma_eq = 1/3), R_v must equal
        2/3(1+nu) + 3(1-2*nu)(1/3)^2 = 2/3(1+nu) + (1-2*nu)/3."""
        # Build a pure uniaxial stress state: sigma_xx = 100, others = 0
        sigma = np.diag([100.0, 0.0, 0.0])
        nu = 0.3
        R_v = triaxiality_factor(sym_tensor_to_voigt(sigma), nu)
        expected = 2.0 / 3.0 * (1.0 + nu) + (1.0 - 2.0 * nu) / 3.0
        assert R_v == pytest.approx(expected, rel=1e-12)

    @pytest.mark.unit
    def test_triaxiality_factor_pure_shear(self) -> None:
        """Pure shear: sigma_H = 0 => R_v = 2/3(1+nu)."""
        sigma = np.array([[0.0, 50.0, 0.0], [50.0, 0.0, 0.0], [0.0, 0.0, 0.0]])
        nu = 0.3
        R_v = triaxiality_factor(sym_tensor_to_voigt(sigma), nu)
        assert R_v == pytest.approx(2.0 / 3.0 * (1.0 + nu), rel=1e-12)

    @pytest.mark.unit
    def test_energy_release_rate_zero_when_sigma_eq_zero(self) -> None:
        """Y = 0 when sigma_eq = 0 (no distortional energy)."""
        Y = energy_release_rate(sigma_eq=0.0, R_v=1.0, E=_E, D=0.0)
        assert Y == 0.0

    @pytest.mark.unit
    def test_material_validation_rejects_bad_params(self) -> None:
        """LemaitreMaterial must validate S_d > 0, s_d > 0, eps_D >= 0."""
        with pytest.raises(ValueError, match="S_d"):
            LemaitreMaterial(
                E=_E,
                nu=_NU,
                sigma_y0=_SIGMA_Y0,
                K=_K,
                n=_N,
                S_d=0.0,
                s_d=1.0,
                eps_D=0.0,
            )
        with pytest.raises(ValueError, match="s_d"):
            LemaitreMaterial(
                E=_E,
                nu=_NU,
                sigma_y0=_SIGMA_Y0,
                K=_K,
                n=_N,
                S_d=1.0,
                s_d=0.0,
                eps_D=0.0,
            )
        with pytest.raises(ValueError, match="eps_D"):
            LemaitreMaterial(
                E=_E,
                nu=_NU,
                sigma_y0=_SIGMA_Y0,
                K=_K,
                n=_N,
                S_d=1.0,
                s_d=1.0,
                eps_D=-0.1,
            )

    @pytest.mark.unit
    def test_nominal_stress_scales_with_one_minus_d(self) -> None:
        """Sanity: sigma_nominal = (1-D_new) * sigma_effective.

        Verified by computing the effective-stress J2 solution and checking that
        the Lemaitre nominal stress equals (1-D_new)*sigma_eff.
        """
        mat = _lemaitre_mat(S_d=0.5, s_d=1.0, eps_D=0.0)
        j2_mat = _j2_mat()
        E_strain = _uniaxial_strain(0.03)

        lem = lemaitre_return(mat, E_strain, alpha_n=0.0, D_n=0.0, dt=1.0)
        j2 = j2_radial_return(j2_mat, E_strain, alpha_old=0.0)

        # J2 stress is the undamaged (effective) stress
        expected_nominal = (1.0 - lem.D_new) * j2.stress
        max_diff = float(np.max(np.abs(lem.stress - expected_nominal)))
        assert max_diff < 1e-10, f"Nominal stress != (1-D)*sigma_eff: diff={max_diff:.3e}"
