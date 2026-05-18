"""Tests for Task P3-4: Phase 3 acceptance suite — viscoplastic verification.

Covers rate sensitivity, quasi-static limit, and thermal softening as the
distinguishing features of viscoplasticity against closed-form or limiting-case
expectations. Uses ``radial_return`` directly on a single (E, alpha, T) triple —
no Newton solve or Taichi required.
"""

from __future__ import annotations

import numpy as np
import pytest

from mechdsl.symbolic.models.j2_power_law import (
    J2PowerLawMaterial,
    deviatoric,
    von_mises,
)
from mechdsl.symbolic.models.j2_power_law import (
    radial_return as j2_radial_return,
)
from mechdsl.symbolic.models.johnson_cook import JohnsonCookMaterial
from mechdsl.symbolic.models.johnson_cook import (
    radial_return as jc_radial_return,
)
from mechdsl.symbolic.models.perzyna import PerzynaMaterial
from mechdsl.symbolic.models.perzyna import (
    radial_return as perzyna_radial_return,
)

# ---------------------------------------------------------------------------
# Reference parameters (steel-like: MPa, mm, tonne, s)
# ---------------------------------------------------------------------------
_E = 200_000.0
_NU = 0.3
_SIGMA_Y0 = 250.0  # = JC.A
_K = 500.0  # = JC.B
_N = 0.5  # hardening exponent
_EPS_DOT_0 = 1.0  # JC reference rate (1/s)
_T_REF = 293.0  # K
_T_MELT = 1793.0  # K
_RHO_CP = 3.588e3  # MPa/K
_BETA_TQ = 0.9  # Taylor-Quinney

_ALPHA_OLD = 0.01  # pre-yielded so Perzyna/JC are firmly in plastic branch


def _uniaxial_strain(eps_11: float) -> np.ndarray:
    """Pure uniaxial Green-Lagrange strain E_11 = eps_11, rest zero."""
    E = np.zeros((3, 3))
    E[0, 0] = eps_11
    return E


def _perzyna_mat(eta: float, m: float = 1.0) -> PerzynaMaterial:
    return PerzynaMaterial(E=_E, nu=_NU, sigma_y0=_SIGMA_Y0, K=_K, n=_N, eta=eta, m=m)


def _jc_mat(**overrides: float) -> JohnsonCookMaterial:
    defaults = dict(
        E=_E,
        nu=_NU,
        A=_SIGMA_Y0,
        B=_K,
        n=_N,
        C=0.05,
        m=1.0,
        eps_dot_0=_EPS_DOT_0,
        T_melt=_T_MELT,
        T_ref=_T_REF,
        rho_c_p=_RHO_CP,
        beta=_BETA_TQ,
    )
    defaults.update(overrides)
    return JohnsonCookMaterial(**defaults)


def _j2_mat() -> J2PowerLawMaterial:
    return J2PowerLawMaterial(E=_E, nu=_NU, sigma_y0=_SIGMA_Y0, K=_K, n=_N)


class TestTaskP3_4ViscoplasticAcceptance:
    """
    Tests for Task P3-4: Rate sensitivity + quasi-static limit + thermal softening.
    Acceptance criteria covered: AC-1 (rate sensitivity), AC-2 (quasi-static limit),
    AC-3 (thermal softening).
    """

    @pytest.mark.unit
    def test_perzyna_rate_sensitivity(self):
        """Perzyna equivalent stress increases monotonically with strain rate.

        Strategy: fix the strain increment and drive the return map with
        progressively smaller ``dt`` (higher equivalent rate dl/dt). The
        overstress term ``eta * (dl/dt)^(1/m)`` must produce a monotone
        increase in equivalent stress across 4 orders of magnitude in rate.
        """
        mat = _perzyna_mat(eta=100.0, m=1.0)
        E_strain = _uniaxial_strain(0.01)

        # Larger dt => lower rate => lower stress.
        dts = [1.0e0, 1.0e-1, 1.0e-2, 1.0e-3, 1.0e-4]

        sigmas = []
        for dt in dts:
            res = perzyna_radial_return(mat, E_strain, _ALPHA_OLD, dt)
            assert res.is_plastic, f"Expected plastic regime at dt={dt}"
            sigmas.append(von_mises(deviatoric(res.stress)))

        for i in range(len(sigmas) - 1):
            assert sigmas[i + 1] > sigmas[i] + 1e-3, (
                f"Perzyna stress not monotone in rate: "
                f"sigma(dt={dts[i]})={sigmas[i]:.3f} >= "
                f"sigma(dt={dts[i + 1]})={sigmas[i + 1]:.3f}"
            )

        assert sigmas[-1] > sigmas[0] * 1.05, (
            "Perzyna rate sensitivity signal too weak - "
            f"sigma(high rate)={sigmas[-1]:.3f}, sigma(low rate)={sigmas[0]:.3f}"
        )

    @pytest.mark.unit
    def test_jc_rate_sensitivity(self):
        """Johnson-Cook stress increases monotonically with strain rate.

        JC clamps the rate factor to ``1`` below ``eps_dot_0``, so ``dt`` must
        be small enough that ``dl/dt`` exceeds ``eps_dot_0`` for the rate
        dependence to be active.  With ``dl ~ 5e-3`` and ``eps_dot_0 = 1 /s``,
        ``dt`` below ``5e-3`` keeps us in the rate-active regime.
        """
        mat = _jc_mat(C=0.05, beta=0.0)
        E_strain = _uniaxial_strain(0.01)

        # dt values keeping dl/dt >> eps_dot_0 across 4 orders of magnitude
        dts = [1.0e-3, 1.0e-4, 1.0e-5, 1.0e-6, 1.0e-7]

        sigmas = []
        for dt in dts:
            res = jc_radial_return(mat, E_strain, _ALPHA_OLD, _T_REF, dt)
            assert res.is_plastic, f"Expected plastic regime at dt={dt}"
            sigmas.append(von_mises(deviatoric(res.stress)))

        for i in range(len(sigmas) - 1):
            assert sigmas[i + 1] > sigmas[i] + 1e-3, (
                f"JC stress not monotone in rate: "
                f"sigma(dt={dts[i]})={sigmas[i]:.3f} >= "
                f"sigma(dt={dts[i + 1]})={sigmas[i + 1]:.3f}"
            )

        assert sigmas[-1] > sigmas[0] * 1.05, (
            "JC rate sensitivity signal too weak - "
            f"sigma(high rate)={sigmas[-1]:.3f}, sigma(low rate)={sigmas[0]:.3f}"
        )

    @pytest.mark.unit
    def test_perzyna_quasi_static_limit(self):
        """At eta -> 0, Perzyna matches rate-independent J2 power-law within 1e-6."""
        mat_pz = _perzyna_mat(eta=1.0e-12, m=1.0)
        mat_j2 = _j2_mat()
        E_strain = _uniaxial_strain(0.01)

        res_pz = perzyna_radial_return(mat_pz, E_strain, _ALPHA_OLD, dt=1.0)
        res_j2 = j2_radial_return(mat_j2, E_strain, _ALPHA_OLD)

        assert res_pz.is_plastic and res_j2.is_plastic

        stress_err = float(np.max(np.abs(res_pz.stress - res_j2.stress)))
        assert stress_err < 1e-6, (
            f"Perzyna quasi-static stress deviates from J2 by {stress_err:.3e}"
        )

        alpha_err = abs(res_pz.alpha_new - res_j2.alpha_new)
        assert alpha_err < 1e-6, f"Perzyna quasi-static alpha deviates from J2 by {alpha_err:.3e}"

    @pytest.mark.unit
    def test_jc_quasi_static_limit(self):
        """At eps_dot <= eps_dot_0 with C=0 and beta=0 at T=T_ref,
        JC matches rate-independent J2 power-law within 1e-6."""
        # Isolate rate and thermal contributions to zero
        mat_jc = _jc_mat(C=0.0, beta=0.0)
        mat_j2 = _j2_mat()
        E_strain = _uniaxial_strain(0.01)

        # dt=1 so dl/dt = dl/1 <= eps_dot_0=1 (rate factor = 1 exactly)
        res_jc = jc_radial_return(mat_jc, E_strain, _ALPHA_OLD, _T_REF, dt=1.0)
        res_j2 = j2_radial_return(mat_j2, E_strain, _ALPHA_OLD)

        assert res_jc.is_plastic and res_j2.is_plastic

        stress_err = float(np.max(np.abs(res_jc.stress - res_j2.stress)))
        assert stress_err < 1e-6, f"JC quasi-static stress deviates from J2 by {stress_err:.3e}"

        alpha_err = abs(res_jc.alpha_new - res_j2.alpha_new)
        assert alpha_err < 1e-6, f"JC quasi-static alpha deviates from J2 by {alpha_err:.3e}"

    @pytest.mark.unit
    def test_jc_thermal_softening(self):
        """At increasing T, JC equivalent stress decreases monotonically.

        Strategy: drive the return map at identical strain increment but
        increasing initial temperature, with ``beta=0`` so no adiabatic
        heating confounds the comparison. The stress sequence must be
        strictly decreasing.
        """
        # C=0 isolates thermal effect; beta=0 prevents adiabatic heating
        mat = _jc_mat(C=0.0, beta=0.0)
        E_strain = _uniaxial_strain(0.01)

        # Temperatures spanning [T_ref, near T_melt] — strong softening expected
        T_list = [
            _T_REF,
            _T_REF + 300.0,
            _T_REF + 600.0,
            _T_REF + 900.0,
            _T_REF + 1200.0,
        ]

        sigmas = []
        for T in T_list:
            res = jc_radial_return(mat, E_strain, _ALPHA_OLD, T, dt=1.0)
            assert res.is_plastic, f"Expected plastic regime at T={T}"
            sigmas.append(von_mises(deviatoric(res.stress)))

        for i in range(len(sigmas) - 1):
            assert sigmas[i + 1] < sigmas[i] - 1e-3, (
                f"JC thermal softening not monotone: "
                f"sigma(T={T_list[i]})={sigmas[i]:.3f} <= "
                f"sigma(T={T_list[i + 1]})={sigmas[i + 1]:.3f}"
            )

        # Sanity: strong softening at high T (sigma should drop by at least 10%)
        assert sigmas[-1] < sigmas[0] * 0.9, (
            "JC thermal softening signal too weak - "
            f"sigma(T_ref)={sigmas[0]:.3f}, sigma(high T)={sigmas[-1]:.3f}"
        )
