"""Johnson-Cook viscoplasticity with adiabatic temperature evolution — numpy implementation.

Implements the Johnson-Cook flow stress model with backward-Euler coupled return
mapping for the plastic multiplier (dl) and temperature increment (dT).

The yield stress is:

    sigma_y(alpha, dot_eps, T) = (A + B * alpha^n) * (1 + C * ln(eps_dot_star))
                                 * (1 - T_star^m)

where:
    eps_dot_star = max(dot_eps / eps_dot_0, 1.0)   (no log below reference rate)
    T_star       = clamp((T - T_ref) / (T_melt - T_ref), 0, 1)

Adiabatic temperature evolution (per step):

    dT = beta * sigma_y(alpha_new, dot_eps, T_new) * dl / rho_c_p

Backward-Euler coupled residuals solved simultaneously:

    R1(dl, dT) = sigma_eq_trial - 3*mu*dl
                 - sigma_y(alpha_old + dl, dot_eps, T_old + dT)
    R2(dl, dT) = rho_c_p * dT
                 - beta * sigma_y(alpha_old + dl, dot_eps, T_old + dT) * dl

At T = T_ref and dot_eps = eps_dot_0 the model reduces exactly to rate-independent
J2 plasticity with power-law hardening: sigma_y = A + B * alpha^n.

References:
    Johnson & Cook (1983), A constitutive model and data for metals subjected to
        large strains, high strain rates, and high temperatures. Proc. 7th Int.
        Symp. Ballistics, pp. 541-547.
    Simo & Hughes (1998), Computational Inelasticity, Ch. 3.4.
    de Souza Neto, Peric & Owen (2008), Computational Methods for Plasticity, Ch. 8.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from mechdsl.symbolic.constitutive import ConstitutiveModel

# Re-use pure helpers from j2_power_law — no duplication of deviatoric /
# von Mises / elastic tangent logic.
from mechdsl.symbolic.models.j2_power_law import (
    assemble_j2_like_tangent,
    deviatoric,
    elastic_tangent,
    von_mises,
)
from mechdsl.symbolic.voigt import tangent_to_voigt_66

if TYPE_CHECKING:
    from numpy.typing import NDArray

# ---------------------------------------------------------------------------
# Material dataclass
# ---------------------------------------------------------------------------

# Small margin kept below T_melt to avoid singularity (T_star -> 1 => sy -> 0).
_T_MELT_MARGIN = 1e-6


@dataclass(frozen=True)
class JohnsonCookMaterial:
    """Johnson-Cook viscoplastic material with adiabatic temperature evolution.

    Parameters
    ----------
    E : float
        Young's modulus (> 0), Pa or consistent units.
    nu : float
        Poisson's ratio (-1 < nu < 0.5).
    A : float
        Static yield stress, i.e. sigma_y at alpha=0, reference rate and
        temperature (> 0).
    B : float
        Strain-hardening coefficient (>= 0).
    n : float
        Strain-hardening exponent (> 0).
    C : float
        Strain-rate sensitivity coefficient (>= 0).
    m : float
        Thermal-softening exponent (> 0).
    eps_dot_0 : float
        Reference strain rate (> 0).
    T_melt : float
        Melting temperature in the same units as T_ref and the runtime T.
        Must satisfy T_melt > T_ref.
    T_ref : float
        Reference temperature at which A was measured.
    rho_c_p : float
        Volumetric heat capacity rho * c_p (> 0).
    beta : float
        Taylor-Quinney inelastic heat fraction (0 <= beta <= 1, default 0.9).
    """

    E: float
    nu: float
    A: float
    B: float
    n: float
    C: float
    m: float
    eps_dot_0: float
    T_melt: float
    T_ref: float
    rho_c_p: float
    beta: float = 0.9

    def __post_init__(self) -> None:
        if self.E <= 0:
            raise ValueError(f"E must be > 0, got {self.E}")
        if not (-1 < self.nu < 0.5):
            raise ValueError(f"nu must be in (-1, 0.5), got {self.nu}")
        if self.A <= 0:
            raise ValueError(f"A must be > 0, got {self.A}")
        if self.B < 0:
            raise ValueError(f"B must be >= 0, got {self.B}")
        if self.n <= 0:
            raise ValueError(f"n must be > 0, got {self.n}")
        if self.C < 0:
            raise ValueError(f"C must be >= 0, got {self.C}")
        if self.m <= 0:
            raise ValueError(f"m must be > 0, got {self.m}")
        if self.eps_dot_0 <= 0:
            raise ValueError(f"eps_dot_0 must be > 0, got {self.eps_dot_0}")
        if self.T_melt <= self.T_ref:
            raise ValueError(
                f"T_melt must be > T_ref, got T_melt={self.T_melt}, T_ref={self.T_ref}"
            )
        if self.rho_c_p <= 0:
            raise ValueError(f"rho_c_p must be > 0, got {self.rho_c_p}")
        if not (0.0 <= self.beta <= 1.0):
            raise ValueError(f"beta must be in [0, 1], got {self.beta}")

    @property
    def lam(self) -> float:
        """First Lame parameter lambda."""
        return self.E * self.nu / ((1.0 + self.nu) * (1.0 - 2.0 * self.nu))

    @property
    def mu(self) -> float:
        """Second Lame parameter (shear modulus) mu."""
        return self.E / (2.0 * (1.0 + self.nu))


# ---------------------------------------------------------------------------
# Yield stress helpers
# ---------------------------------------------------------------------------


def _T_star(mat: JohnsonCookMaterial, T: float) -> float:
    """Normalised temperature T_star = (T - T_ref) / (T_melt - T_ref), clamped [0, 1]."""
    raw = (T - mat.T_ref) / (mat.T_melt - mat.T_ref)
    return float(np.clip(raw, 0.0, 1.0))


def _eps_dot_star(mat: JohnsonCookMaterial, dot_eps: float) -> float:
    """Normalised strain rate, floored at 1.0 (no extrapolation below reference rate)."""
    return max(dot_eps / mat.eps_dot_0, 1.0)


def yield_stress(mat: JohnsonCookMaterial, alpha: float, dot_eps: float, T: float) -> float:
    """Johnson-Cook yield stress.

    sigma_y = (A + B * alpha^n) * (1 + C * ln(eps_dot_star)) * (1 - T_star^m)

    Parameters
    ----------
    mat : JohnsonCookMaterial
    alpha : float  — equivalent plastic strain (>= 0)
    dot_eps : float — current equivalent plastic strain rate
    T : float      — current temperature
    """
    # Strain-hardening factor
    strain_factor = mat.A if alpha <= 0.0 else mat.A + mat.B * alpha**mat.n

    # Rate-sensitivity factor (floored at 1 — no softening below reference rate)
    eds = _eps_dot_star(mat, dot_eps)
    rate_factor = 1.0 + mat.C * float(np.log(eds))

    # Thermal-softening factor
    Ts = _T_star(mat, T)
    thermal_factor = 1.0 - Ts**mat.m

    return float(strain_factor * rate_factor * thermal_factor)


def d_sy_d_alpha(mat: JohnsonCookMaterial, alpha: float, dot_eps: float, T: float) -> float:
    """Closed-form partial derivative of yield_stress w.r.t. alpha.

    d sigma_y / d alpha = B * n * alpha^(n-1) * rate_factor * thermal_factor
    Returns 0 for alpha <= 1e-12 (regularisation, same as j2_power_law).
    """
    if alpha <= 1e-12:
        return 0.0
    eds = _eps_dot_star(mat, dot_eps)
    rate_factor = 1.0 + mat.C * float(np.log(eds))
    Ts = _T_star(mat, T)
    thermal_factor = 1.0 - Ts**mat.m
    return float(mat.B * mat.n * alpha ** (mat.n - 1.0) * rate_factor * thermal_factor)


def d_sy_d_T(mat: JohnsonCookMaterial, alpha: float, dot_eps: float, T: float) -> float:
    """Closed-form partial derivative of yield_stress w.r.t. T.

    d sigma_y / d T = (A + B * alpha^n) * rate_factor
                     * (-m * T_star^(m-1)) / (T_melt - T_ref)

    Returns 0 when T <= T_ref (T_star = 0, derivative of (1 - T_star^m) = 0 at T_star=0
    for m > 1; for m <= 1 the derivative diverges, but since T_star <= 0 => clamped to 0
    => thermal factor = 1 = constant there).
    Also returns 0 when T >= T_melt (clamped at T_star = 1).
    """
    Ts_raw = (T - mat.T_ref) / (mat.T_melt - mat.T_ref)
    # Outside [0, 1] the clamped T_star is constant so derivative is 0.
    if Ts_raw <= 0.0 or Ts_raw >= 1.0:
        return 0.0
    Ts = Ts_raw  # in (0, 1)

    strain_factor = mat.A if alpha <= 0.0 else mat.A + mat.B * alpha**mat.n

    eds = _eps_dot_star(mat, dot_eps)
    rate_factor = 1.0 + mat.C * float(np.log(eds))

    dT_star_dT = 1.0 / (mat.T_melt - mat.T_ref)
    d_thermal_dT = -mat.m * Ts ** (mat.m - 1.0) * dT_star_dT

    return float(strain_factor * rate_factor * d_thermal_dT)


# ---------------------------------------------------------------------------
# Johnson-Cook radial return result (extends ReturnMappingResult with T_new)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class JCReturnMappingResult:
    """Result of the Johnson-Cook return mapping algorithm."""

    stress: NDArray  # Updated PK2 stress (3, 3)
    alpha_new: float  # Updated equivalent plastic strain
    T_new: float  # Updated temperature
    delta_lambda: float  # Plastic multiplier increment dl
    is_plastic: bool  # Whether yielding occurred
    tangent: NDArray  # Algorithmic tangent (3, 3, 3, 3) — elastic stub for P3-2


# ---------------------------------------------------------------------------
# Coupled (dl, dT) Newton solver for Johnson-Cook
# ---------------------------------------------------------------------------


def radial_return(
    mat: JohnsonCookMaterial,
    E_strain: NDArray,
    alpha_old: float,
    T_old: float,
    dt: float,
    tol: float = 1e-12,
    max_iter: int = 50,
) -> JCReturnMappingResult:
    """Backward-Euler radial return for Johnson-Cook viscoplasticity.

    Solves the coupled system R(dl, dT) = 0:

        R1(dl, dT) = sigma_eq_trial - 3*mu*dl
                     - sigma_y(alpha_old + dl, dl/dt, T_old + dT)
        R2(dl, dT) = rho_c_p * dT
                     - beta * sigma_y(alpha_old + dl, dl/dt, T_old + dT) * dl

    using a 2x2 Newton iteration with analytical Jacobian.  A line-search
    keeps dl > 0 and T_new < T_melt - margin.

    Algorithm
    ---------
    1. Elastic trial: S_trial = lambda * tr(E) * I + 2 * mu * E
    2. Deviatoric trial stress and von Mises equivalent
    3. Yield check at T_old: if f_trial <= 0, return elastic result
    4. Coupled (dl, dT) Newton iteration
    5. Update stress and state

    Parameters
    ----------
    mat : JohnsonCookMaterial
    E_strain : NDArray (3, 3)  — Green-Lagrange strain tensor
    alpha_old : float          — previous equivalent plastic strain
    T_old : float              — temperature at start of increment
    dt : float                 — time step size (> 0)
    tol : float                — Newton convergence tolerance
    max_iter : int             — maximum Newton iterations

    Returns
    -------
    JCReturnMappingResult
    """
    if dt <= 0.0:
        raise ValueError(f"dt must be > 0, got {dt}")

    T_melt_guard = mat.T_melt - _T_MELT_MARGIN * (mat.T_melt - mat.T_ref)
    if T_old >= mat.T_melt:
        raise ValueError(
            f"T_old={T_old} >= T_melt={mat.T_melt}: temperature at or above melting point. "
            "The Johnson-Cook model predicts complete loss of strength; "
            "clamp T < T_melt before calling radial_return."
        )

    lam = mat.lam
    mu = mat.mu

    # --- 1. Elastic trial stress ---
    tr_E = float(np.trace(E_strain))
    S_trial: NDArray = lam * tr_E * np.eye(3) + 2.0 * mu * E_strain

    # --- 2. Deviatoric trial and von Mises ---
    S_dev_trial = deviatoric(S_trial)
    S_vol_trial = S_trial - S_dev_trial
    sigma_eq_trial = von_mises(S_dev_trial)

    # --- Von Mises near-zero guard ---
    sigma_y_old = yield_stress(mat, alpha_old, 0.0, T_old)
    C_el = elastic_tangent(lam, mu)

    if sigma_eq_trial < 1e-12 * sigma_y_old:
        return JCReturnMappingResult(
            stress=S_trial,
            alpha_new=alpha_old,
            T_new=T_old,
            delta_lambda=0.0,
            is_plastic=False,
            tangent=C_el,
        )

    # --- 3. Yield check ---
    f_trial = sigma_eq_trial - sigma_y_old

    if f_trial <= 0.0:
        return JCReturnMappingResult(
            stress=S_trial,
            alpha_new=alpha_old,
            T_new=T_old,
            delta_lambda=0.0,
            is_plastic=False,
            tangent=C_el,
        )

    # --- 4. Coupled (dl, dT) Newton iteration ---
    #
    # State: x = [dl, dT]
    #
    # R1 = sigma_eq_trial - 3*mu*dl - sy(alpha_old+dl, dl/dt, T_old+dT) = 0
    # R2 = rho_c_p * dT - beta * sy(alpha_old+dl, dl/dt, T_old+dT) * dl = 0
    #
    # Jacobian (analytical):
    #   dR1/d(dl) = -3*mu - d_sy_d_alpha - (C/dl)*sy*(1 if edot_star>1 else 0)
    #               (rate term via chain rule on eps_dot = dl/dt)
    #   dR1/d(dT) = -d_sy_d_T
    #   dR2/d(dl) = -beta*(d_sy_d_alpha + rate_correction)*dl - beta*sy
    #   dR2/d(dT) = rho_c_p - beta*d_sy_d_T*dl
    #
    # where the rate_correction term accounts for d(sy)/d(eps_dot) * d(eps_dot)/d(dl).
    # d(sy)/d(eps_dot) * d(eps_dot)/d(dl) = sy * C / (eps_dot * eps_dot_0 / eps_dot_0) * 1/dt
    #   when eps_dot_star > 1 (rate-sensitive regime).

    stress_ref = max(abs(sigma_eq_trial), sigma_y_old, 1.0)
    effective_tol = max(tol, tol * stress_ref)

    # Initial guess: dl from rate-independent J2 estimate, dT = 0
    # H'_nom uses finite difference at alpha_old (or 0 if at zero)
    H_nom = d_sy_d_alpha(mat, max(alpha_old, 1e-12), 0.0, T_old)
    dl = max(f_trial / (3.0 * mu + H_nom + 1.0), 1e-15)
    dT = 0.0

    def _residuals_and_jac(dl_: float, dT_: float) -> tuple[float, float, NDArray]:
        """Return (R1, R2, J_2x2) for given (dl, dT)."""
        alpha_t = alpha_old + dl_
        T_t = T_old + dT_
        dot_eps_t = dl_ / dt  # equivalent plastic strain rate

        sy = yield_stress(mat, alpha_t, dot_eps_t, T_t)

        # Partial derivatives of sigma_y
        dsy_da = d_sy_d_alpha(mat, alpha_t, dot_eps_t, T_t)
        dsy_dT = d_sy_d_T(mat, alpha_t, dot_eps_t, T_t)

        # Rate sensitivity contribution: d(sy)/d(dot_eps) * d(dot_eps)/d(dl)
        # Only active when eps_dot_star > 1 (i.e., dot_eps_t > eps_dot_0).
        if dot_eps_t > mat.eps_dot_0 and dl_ > 1e-20:
            # sy = ... * (1 + C * ln(dot_eps_t / eps_dot_0))
            # d(sy)/d(dot_eps_t) = strain_factor * thermal_factor * C / dot_eps_t
            # d(dot_eps_t)/d(dl) = 1/dt
            # Combined: sy * C / (ln_term * dot_eps_t * dt) ... but simpler:
            # d(sy)/d(dl) via rate = (C / (1 + C*ln(edstar))) * sy / (dl_)
            # because d(ln(edstar))/d(dl) = 1/dl_ (since edstar = dl_/(dt*eps_dot_0))
            dsy_d_dl_rate = mat.C * sy / ((1.0 + mat.C * np.log(dot_eps_t / mat.eps_dot_0)) * dl_)
        else:
            dsy_d_dl_rate = 0.0

        R1 = sigma_eq_trial - 3.0 * mu * dl_ - sy
        R2 = mat.rho_c_p * dT_ - mat.beta * sy * dl_

        # Jacobian rows [dR1/ddl, dR1/ddT; dR2/ddl, dR2/ddT]
        J = np.array(
            [
                [
                    -3.0 * mu - dsy_da - dsy_d_dl_rate,  # dR1/ddl
                    -dsy_dT,  # dR1/ddT
                ],
                [
                    -mat.beta * (dsy_da + dsy_d_dl_rate) * dl_ - mat.beta * sy,  # dR2/ddl
                    mat.rho_c_p - mat.beta * dsy_dT * dl_,  # dR2/ddT
                ],
            ]
        )

        return R1, R2, J

    R1 = float("inf")
    R2 = float("inf")
    # J_conv is the 2x2 Newton Jacobian at convergence — retained for the
    # consistent tangent assembly (P3-3).  Initialised to a dummy value;
    # always overwritten before the tangent is computed.
    J_conv: NDArray = np.zeros((2, 2))
    J = J_conv  # alias so the name is defined before the loop body runs

    for _it in range(max_iter):
        R1, R2, J = _residuals_and_jac(dl, dT)

        res_norm = max(abs(R1), abs(R2 / max(abs(mat.rho_c_p), 1.0)))
        if res_norm < effective_tol:
            J_conv = J  # capture converged Jacobian
            break

        # Solve 2x2 system: J * [ddl; ddT] = -[R1; R2]
        det_J = J[0, 0] * J[1, 1] - J[0, 1] * J[1, 0]
        if abs(det_J) < 1e-30 * max(abs(J[0, 0]), abs(J[1, 1]), 1.0):
            # Near-singular Jacobian — fall back to updating dl only
            if abs(J[0, 0]) > 1e-30:
                ddl = -R1 / J[0, 0]
                ddT = 0.0
            else:
                break
        else:
            # Cramer's rule for 2x2
            ddl = (-R1 * J[1, 1] + R2 * J[0, 1]) / det_J
            ddT = (-J[0, 0] * R2 + J[1, 0] * R1) / det_J

        # Line-search: maintain dl > 0 and T_new < T_melt_guard
        step = 1.0
        dl_new = dl + step * ddl
        dT_new = dT + step * ddT
        for _ in range(15):
            T_new_candidate = T_old + dT_new
            if dl_new > 1e-20 and T_new_candidate < T_melt_guard:
                break
            step *= 0.5
            dl_new = dl + step * ddl
            dT_new = dT + step * ddT
        else:
            # Cannot satisfy constraints — keep current (dl, dT) and give up
            break

        dl = dl_new
        dT = dT_new
    else:
        # Final residual check after exhausting iterations
        R1, R2, J = _residuals_and_jac(dl, dT)
        J_conv = J  # capture converged Jacobian
        res_norm = max(abs(R1), abs(R2 / max(abs(mat.rho_c_p), 1.0)))
        if res_norm >= effective_tol:
            raise RuntimeError(
                f"Johnson-Cook return mapping did not converge in {max_iter} iterations. "
                f"|R1| = {abs(R1):.3e}, |R2| = {abs(R2):.3e}"
            )

    # Guard against temperature overshoot from line-search edge cases
    T_new = T_old + dT
    if T_new >= mat.T_melt:
        raise ValueError(
            f"Coupled Newton produced T_new={T_new} >= T_melt={mat.T_melt}. "
            "Reduce the time step or check material parameters."
        )

    # Clamp tiny negative dl (07-CONVENTIONS.md: dl >= -1e-15)
    if dl < 0.0:
        if dl >= -1e-15:
            dl = 0.0
        else:
            raise ValueError(f"Negative plastic multiplier delta_lambda = {dl:.3e}")

    # --- 5. Update stress ---
    ratio = 3.0 * mu * dl / sigma_eq_trial
    S_updated: NDArray = S_vol_trial + (1.0 - ratio) * S_dev_trial

    # --- Algorithmic consistent tangent (P3-3) ---
    #
    # Derived from implicit differentiation of the coupled (dl, dT) Newton system
    # at convergence (Simo & Hughes 1998, §3.4 extended for thermal coupling;
    # Schur-complement elimination of dT).
    #
    # At convergence the 2x2 Newton residual satisfies:
    #   J_conv * [d(dl)/d(E_IJ); d(dT)/d(E_IJ)] = [∂sigma_eq_trial/∂E_IJ; 0]
    #
    # where J_conv = [[J00, J01], [J10, J11]] is the converged Jacobian.
    # Solving by Cramer's rule:
    #   d(dl)/d(sigma_eq_trial) = J_conv[1,1] / det(J_conv)
    #
    # For the J2-like box form (Simo & Hughes §3.4, Box 3.5), the effective
    # "denominator" that replaces (3*mu + H') is:
    #
    #   D_eff = det(J_conv) / J_conv[1,1]
    #         = (J00*J11 - J01*J10) / J11
    #
    # Note: J00 = -(3*mu + H' + rate_terms) < 0, J11 > 0, so D_eff < 0.
    # The assemble_j2_like_tangent helper uses the positive denominator convention
    # (matching (3*mu + H') > 0 for J2), so we pass -D_eff:
    #
    #   denominator = -D_eff = -det(J_conv) / J_conv[1,1]   (> 0 for stable return)
    #
    # At beta=0, C=0, T=T_ref (no coupling): J01=J10=0, J11=rho_c_p,
    #   D_eff = J00 = -(3*mu + H'), so -D_eff = 3*mu + H' — identical to J2. ✓
    det_J_conv = J_conv[0, 0] * J_conv[1, 1] - J_conv[0, 1] * J_conv[1, 0]
    J11 = J_conv[1, 1]
    if abs(J11) > 1e-30 and abs(det_J_conv) > 1e-30:
        denominator = -det_J_conv / J11
    else:
        # Degenerate: fall back to uncoupled Perzyna-like denominator
        # (handles pathological edge cases; should not occur in practice)
        denominator = -J_conv[0, 0]  # = 3*mu + H' + rate_terms

    tangent = assemble_j2_like_tangent(
        lam=lam,
        mu=mu,
        S_dev_trial=S_dev_trial,
        sigma_eq_trial=sigma_eq_trial,
        dl=dl,
        denominator=denominator,
    )

    return JCReturnMappingResult(
        stress=S_updated,
        alpha_new=alpha_old + dl,
        T_new=T_new,
        delta_lambda=dl,
        is_plastic=True,
        tangent=tangent,
    )


# ---------------------------------------------------------------------------
# ConstitutiveModel wrapper
# ---------------------------------------------------------------------------


class JohnsonCookModel(ConstitutiveModel):
    """Johnson-Cook viscoplasticity wrapper implementing the ConstitutiveModel interface.

    Requires ``alpha``, ``T``, and ``dt`` as state keyword arguments in every call.
    """

    def __init__(self, mat: JohnsonCookMaterial) -> None:
        self._mat = mat

    def pk2_stress(self, E_strain: NDArray, **state: float) -> NDArray:
        """Return PK2 stress from Johnson-Cook radial return mapping."""
        alpha = state.get("alpha", 0.0)
        T = state.get("T", self._mat.T_ref)
        dt = state.get("dt", 1.0)
        return radial_return(self._mat, E_strain, alpha, T, dt).stress

    def material_tangent(self, E_strain: NDArray, **state: float) -> NDArray:
        """Return algorithmic tangent (3,3,3,3) — elastic stub for P3-2."""
        alpha = state.get("alpha", 0.0)
        T = state.get("T", self._mat.T_ref)
        dt = state.get("dt", 1.0)
        return radial_return(self._mat, E_strain, alpha, T, dt).tangent

    def voigt_tangent(self, E_strain: NDArray, **state: float) -> NDArray:
        """Return Voigt-form tangent (6,6) using tensorial Voigt ordering."""
        alpha = state.get("alpha", 0.0)
        T = state.get("T", self._mat.T_ref)
        dt = state.get("dt", 1.0)
        C4 = radial_return(self._mat, E_strain, alpha, T, dt).tangent
        return tangent_to_voigt_66(C4)

    @property
    def state_variables(self) -> tuple[str, ...]:
        return ("alpha", "T")

    @property
    def is_dissipative(self) -> bool:
        return True
