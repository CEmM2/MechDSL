"""Perzyna viscoplasticity with backward Euler return map — numerical (numpy) implementation.

Extends J2 plasticity with a Perzyna-type overstress viscosity term.  Instead
of the rate-independent consistency condition f = 0, the plastic strain rate is
proportional to a power of the overstress:

    dε_p/dt = (1/eta) * <f/sigma_y>^m  * n_flow

where n_flow is the outward normal to the yield surface, eta is the viscosity
parameter, and m is the rate-sensitivity exponent.

For the backward Euler return map the discrete scalar equation to solve for the
plastic multiplier increment dl is:

    R(dl) = sigma_eq_trial - 3*mu*dl - sigma_y(alpha + dl)
            - eta * (dl / dt)^(1/m)  = 0

When eta → 0 the viscous term vanishes and the equation reduces exactly to the
rate-independent J2 consistency condition.

References:
    Perzyna (1966), Fundamental Problems in Viscoplasticity, Adv. Appl. Mech.
    de Souza Neto, Peric & Owen (2008), Computational Methods for Plasticity,
        Ch. 8.
    Simo & Hughes (1998), Computational Inelasticity, Ch. 3.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from mechdsl.symbolic.constitutive import ConstitutiveModel

# Re-use pure helpers from j2_power_law — no duplication of deviatoric /
# von Mises / elastic tangent logic.
from mechdsl.symbolic.models.j2_power_law import (
    ReturnMappingResult,
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


@dataclass(frozen=True)
class PerzynaMaterial:
    """Perzyna viscoplastic material with power-law isotropic hardening.

    Parameters
    ----------
    E : float
        Young's modulus (> 0).
    nu : float
        Poisson's ratio (-1 < nu < 0.5).
    sigma_y0 : float
        Initial yield stress (> 0).
    K : float
        Hardening modulus (>= 0).
    n : float
        Hardening exponent (> 0).
    eta : float
        Perzyna viscosity parameter (> 0).  At eta → 0 the model reduces to
        rate-independent J2.
    m : float
        Rate-sensitivity exponent (> 0).  Higher m = more sensitive to rate.
    """

    E: float
    nu: float
    sigma_y0: float
    K: float
    n: float
    eta: float
    m: float

    def __post_init__(self) -> None:
        if self.E <= 0:
            raise ValueError(f"E must be > 0, got {self.E}")
        if not (-1 < self.nu < 0.5):
            raise ValueError(f"nu must be in (-1, 0.5), got {self.nu}")
        if self.sigma_y0 <= 0:
            raise ValueError(f"sigma_y0 must be > 0, got {self.sigma_y0}")
        if self.K < 0:
            raise ValueError(f"K must be >= 0, got {self.K}")
        if self.n <= 0:
            raise ValueError(f"n must be > 0, got {self.n}")
        if self.eta <= 0:
            raise ValueError(f"eta must be > 0, got {self.eta}")
        if self.m <= 0:
            raise ValueError(f"m must be > 0, got {self.m}")

    @property
    def lam(self) -> float:
        """First Lame parameter lambda."""
        return self.E * self.nu / ((1.0 + self.nu) * (1.0 - 2.0 * self.nu))

    @property
    def mu(self) -> float:
        """Second Lame parameter (shear modulus) mu."""
        return self.E / (2.0 * (1.0 + self.nu))


# ---------------------------------------------------------------------------
# Yield stress helpers  (identical contract to j2_power_law versions)
# ---------------------------------------------------------------------------


def yield_stress(mat: PerzynaMaterial, alpha: float) -> float:
    """Yield stress: sigma_y = sigma_y0 + K * alpha^n."""
    if alpha <= 0.0:
        return mat.sigma_y0
    return float(mat.sigma_y0 + mat.K * alpha**mat.n)


def yield_stress_derivative(mat: PerzynaMaterial, alpha: float) -> float:
    """Derivative of yield stress w.r.t. alpha: H' = K * n * alpha^(n-1).

    Returns 0 for alpha <= 1e-12 (regularisation, same as j2_power_law).
    """
    if alpha <= 1e-12:
        return 0.0
    return float(mat.K * mat.n * alpha ** (mat.n - 1.0))


# ---------------------------------------------------------------------------
# Radial return mapping (Perzyna, backward Euler)
# ---------------------------------------------------------------------------


def radial_return(
    mat: PerzynaMaterial,
    E_strain: NDArray,
    alpha_old: float,
    dt: float,
    tol: float = 1e-12,
    max_iter: int = 50,
) -> ReturnMappingResult:
    """Backward Euler radial return for Perzyna viscoplasticity.

    Algorithm
    ---------
    1. Elastic trial: S_trial = lambda * tr(E) * I + 2 * mu * E
    2. Compute deviatoric trial stress and von Mises equivalent
    3. Check yield: f_trial = sigma_eq_trial - sigma_y(alpha_old)
       (If f_trial <= 0 and the viscous overstress at dl=0 is also <= 0,
       the step is elastic.)
    4. Plastic: Newton iteration on the residual
          R(dl) = sigma_eq_trial - 3*mu*dl - sigma_y(alpha_old + dl)
                  - eta * (dl/dt)^(1/m)
       with line-search back-tracking when Newton would give dl <= 0, and a
       bisection fallback when Newton stalls.
    5. Update stress: S = S_vol + (1 - 3*mu*dl / sigma_eq_trial) * S_dev_trial
    6. Update alpha: alpha_new = alpha_old + delta_lambda

    Algorithmic tangent
    -------------------
    For P3-1 the tangent is **stubbed as the elastic tangent** when plastic.
    P3-3 will replace this stub with the proper consistent tangent.

    Parameters
    ----------
    mat : PerzynaMaterial
        Material parameters including eta and m.
    E_strain : NDArray
        Green-Lagrange strain tensor (3, 3).
    alpha_old : float
        Previous accumulated equivalent plastic strain.
    dt : float
        Time step size (> 0).
    tol : float
        Newton convergence tolerance on the normalised residual.
    max_iter : int
        Maximum Newton iterations.

    Returns
    -------
    ReturnMappingResult
        Updated stress, internal variables, and tangent (elastic stub for P3-1).
    """
    if dt <= 0.0:
        raise ValueError(f"dt must be > 0, got {dt}")

    lam = mat.lam
    mu = mat.mu

    # --- 1. Elastic trial stress (SVK-like, same as J2) ---
    tr_E = float(np.trace(E_strain))
    S_trial: NDArray = lam * tr_E * np.eye(3) + 2.0 * mu * E_strain

    # --- 2. Deviatoric trial and von Mises ---
    S_dev_trial = deviatoric(S_trial)
    S_vol_trial = S_trial - S_dev_trial
    sigma_eq_trial = von_mises(S_dev_trial)

    # --- Von Mises near-zero guard (07-CONVENTIONS.md) ---
    sigma_y_old = yield_stress(mat, alpha_old)
    C_el = elastic_tangent(lam, mu)

    if sigma_eq_trial < 1e-12 * sigma_y_old:
        return ReturnMappingResult(
            stress=S_trial,
            alpha_new=alpha_old,
            delta_lambda=0.0,
            is_plastic=False,
            tangent=C_el,
        )

    # --- 3. Check whether a plastic step is needed at all ---
    # The Perzyna viscous term is zero at dl=0, so the trial yield check is
    # identical to the rate-independent case.
    f_trial = sigma_eq_trial - sigma_y_old

    if f_trial <= 0.0:
        return ReturnMappingResult(
            stress=S_trial,
            alpha_new=alpha_old,
            delta_lambda=0.0,
            is_plastic=False,
            tangent=C_el,
        )

    # --- 4. Plastic: Newton iteration ---
    #
    # R(dl) = sigma_eq_trial - 3*mu*dl - sigma_y(alpha_old + dl)
    #         - eta * (dl/dt)^(1/m)  = 0
    #
    # dR/d(dl) = -3*mu - H' - (eta/m) * (1/dt)^(1/m) * dl^(1/m - 1)
    #
    # The viscous term is singular at dl=0 when 1/m > 1 (m < 1).
    # To avoid this we start Newton from a small positive dl.
    # We also add line-search back-tracking to keep dl > 0.

    stress_ref = max(abs(sigma_eq_trial), sigma_y_old, 1.0)
    effective_tol = max(tol, tol * stress_ref)

    # Initial guess: use J2 rate-independent estimate (ignore viscous term)
    # f_trial = sigma_eq_trial - sigma_y0 = 3*mu*dl + H'*dl approximately
    # => dl ~ f_trial / (3*mu)  (upper bound, viscosity only adds resistance)
    dl = max(f_trial / (3.0 * mu + 1.0), 1e-15)  # ensure strictly positive

    inv_m = 1.0 / mat.m
    eta = mat.eta

    def _residual(d: float) -> tuple[float, float]:
        """Return (R, dR/d(dl)) at a given dl > 0."""
        alpha_t = alpha_old + d
        sy = yield_stress(mat, alpha_t)
        H_prime = yield_stress_derivative(mat, alpha_t)

        # Viscous overstress term: eta * (dl/dt)^(1/m)
        visc = eta * (d / dt) ** inv_m
        # dVisc/d(dl) = eta * inv_m * (1/dt)^(inv_m) * d^(inv_m - 1)
        #             = visc * inv_m / d
        dvisc = visc * inv_m / d

        R = sigma_eq_trial - 3.0 * mu * d - sy - visc
        dR = -3.0 * mu - H_prime - dvisc
        return R, dR

    R = float("inf")
    for _it in range(max_iter):
        R, dR = _residual(dl)

        if abs(R) < effective_tol:
            break

        if abs(dR) < 1e-30:
            # Derivative vanished — can't do Newton, fall back to bisection
            break

        ddl = -R / dR

        # Line-search: keep dl strictly positive
        step = 1.0
        dl_new = dl + step * ddl
        for _ in range(10):
            if dl_new > 1e-15:
                break
            step *= 0.5
            dl_new = dl + step * ddl
        else:
            # Cannot step forward while keeping dl > 0; fall back to bisection
            dl_new = dl * 0.5  # shrink toward 0 — will be caught below

        dl = dl_new
    else:
        # Newton did not converge — try bisection fallback before giving up
        # Bracket: at dl=0 residual = f_trial > 0;
        # we need an upper bound where R < 0.
        pass

    # Bisection fallback if Newton residual is still too large
    if abs(R) >= effective_tol:
        # Find upper bracket: keep doubling dl until R < 0
        dl_lo = 1e-15
        dl_hi = dl
        R_hi, _ = _residual(dl_hi)
        for _ in range(60):
            if R_hi < 0.0:
                break
            dl_hi *= 2.0
            R_hi, _ = _residual(dl_hi)
        else:
            raise RuntimeError(
                f"Perzyna return mapping: could not bracket root after bisection "
                f"expansion. |R| = {abs(R_hi):.3e}"
            )

        # Bisect
        for _ in range(80):
            dl_mid = 0.5 * (dl_lo + dl_hi)
            R_mid, _ = _residual(dl_mid)
            if abs(R_mid) < effective_tol:
                dl = dl_mid
                R = R_mid
                break
            if R_mid > 0.0:
                dl_lo = dl_mid
            else:
                dl_hi = dl_mid
        else:
            dl = 0.5 * (dl_lo + dl_hi)
            R, _ = _residual(dl)
            if abs(R) >= effective_tol:
                raise RuntimeError(
                    f"Perzyna return mapping bisection did not converge. |R| = {abs(R):.3e}"
                )

    # Clamp tiny negative from Newton (07-CONVENTIONS.md: dl >= -1e-15)
    if dl < 0.0:
        if dl >= -1e-15:
            dl = 0.0
        else:
            raise ValueError(f"Negative plastic multiplier delta_lambda = {dl:.3e}")

    # --- 5. Update stress ---
    ratio = 3.0 * mu * dl / sigma_eq_trial
    S_updated: NDArray = S_vol_trial + (1.0 - ratio) * S_dev_trial

    # --- 6. Update alpha ---
    alpha_new = alpha_old + dl

    # --- Algorithmic consistent tangent ---
    #
    # Derived from linearisation of the Perzyna return-map residual at convergence
    # (Simo & Hughes 1998, §3.4, Box 3.5 extended for viscoplasticity).
    #
    # At convergence the residual is:
    #   R(dl) = sigma_eq_trial - 3*mu*dl - sigma_y(alpha_old+dl) - eta*(dl/dt)^(1/m) = 0
    #
    # Total differentiation gives d(dl)/d(sigma_eq_trial) = 1 / (3*mu + H' + eta_term)
    # where:
    #   H'        = d(sigma_y)/d(alpha)|_{alpha_new}   (isotropic hardening slope)
    #   eta_term  = (eta/m) * (1/dt)^(1/m) * dl^(1/m - 1)   (viscosity stiffening)
    #
    # The tangent takes the standard Simo-Hughes J2 box form with denominator
    #   (3*mu + H') replaced by (3*mu + H' + eta_term):
    #
    #   C_alg = kappa*(I⊗I) + 2*mu*theta*P_dev
    #           + (9*mu^2*dl/sigma_eq - 9*mu^2 / (3*mu + H' + eta_term)) * (n⊗n)
    #
    # At eta→0 (eta_term→0) this reduces byte-for-byte to the rate-independent J2 tangent.
    #
    # Elastic branch: elastic tangent (standard; already returned above).
    H_prime_new = yield_stress_derivative(mat, alpha_new)

    # Viscosity stiffening term: d(visc)/d(dl) at convergence
    # visc = eta * (dl/dt)^(1/m) => d(visc)/d(dl) = eta * (1/m) * (1/dt)^(1/m) * dl^(1/m - 1)
    #                                               = visc * (1/m) / dl
    inv_m = 1.0 / mat.m
    visc_at_conv = mat.eta * (dl / dt) ** inv_m
    eta_term = visc_at_conv * inv_m / dl  # d(visc)/d(dl) at convergence

    tangent = assemble_j2_like_tangent(
        lam=lam,
        mu=mu,
        S_dev_trial=S_dev_trial,
        sigma_eq_trial=sigma_eq_trial,
        dl=dl,
        denominator=3.0 * mu + H_prime_new + eta_term,
    )

    return ReturnMappingResult(
        stress=S_updated,
        alpha_new=alpha_new,
        delta_lambda=dl,
        is_plastic=True,
        tangent=tangent,
    )


# ---------------------------------------------------------------------------
# ConstitutiveModel wrapper
# ---------------------------------------------------------------------------


class PerzynaModel(ConstitutiveModel):
    """Perzyna viscoplasticity wrapper implementing the ConstitutiveModel interface.

    The wrapper requires ``dt`` (time step) and ``alpha`` (equivalent plastic
    strain) as state keyword arguments in every call.
    """

    def __init__(self, mat: PerzynaMaterial) -> None:
        self._mat = mat

    def pk2_stress(self, E_strain: NDArray, **state: float) -> NDArray:
        """Return PK2 stress from Perzyna radial return mapping."""
        alpha = state.get("alpha", 0.0)
        dt = state.get("dt", 1.0)
        return radial_return(self._mat, E_strain, alpha, dt).stress

    def material_tangent(self, E_strain: NDArray, **state: float) -> NDArray:
        """Return algorithmic tangent (3,3,3,3) — elastic stub for P3-1."""
        alpha = state.get("alpha", 0.0)
        dt = state.get("dt", 1.0)
        return radial_return(self._mat, E_strain, alpha, dt).tangent

    def voigt_tangent(self, E_strain: NDArray, **state: float) -> NDArray:
        """Return Voigt-form tangent (6,6) using tensorial Voigt ordering."""
        alpha = state.get("alpha", 0.0)
        dt = state.get("dt", 1.0)
        C4 = radial_return(self._mat, E_strain, alpha, dt).tangent
        return tangent_to_voigt_66(C4)

    @property
    def state_variables(self) -> tuple[str, ...]:
        return ("alpha",)

    @property
    def is_dissipative(self) -> bool:
        return True
