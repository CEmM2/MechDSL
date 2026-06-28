"""Independent 1D mixed-hardening plasticity reference.

constitutive_latex Phase 6 (P6-3). Ground-truth oracle for the J2 MIXED
(isotropic power-law + linear kinematic) hardening return map. As with
the kinematic variant (``ref_j2_kinematic.py``) there is NO existing
mechdsl oracle for mixed hardening, so this reference is *self-authored*
ground truth — and the top risk is "a wrong reference silently passes a
wrong transpile."

Two defences make it trustworthy:

1. **Independent derivation (anti-tautology).** This is the classical
   scalar 1D mixed plasticity model in *physical* stress-strain space
   (``sigma``, total strain ``eps``, plastic strain ``ep``, scalar
   back-stress ``q``, accumulated plastic strain ``alpha``), NOT a
   scalarisation of the 3D tensor radial-return algebra. It extends the
   bilinear-kinematic 1D model (``ref_j2_kinematic.Bilinear1D``) with a
   power-law isotropic radius::

       sigma     = E*(eps - ep)                  (1D Hooke on elastic strain)
       q         = H_kin*ep                       (linear kinematic back-stress)
       sigma_y   = sigma_y0 + K*alpha^n           (power-law isotropic radius)
       f         = |sigma - q| - sigma_y(alpha)   (yield on relative stress)

   Because ``sigma_y(alpha)`` is a nonlinear power law in
   ``alpha = alpha_old + dl``, the 1D consistency condition is NONLINEAR
   in ``dl`` and is solved here by an INDEPENDENT scalar Newton loop
   (its own derivative, its own residual) — it does NOT call the
   algo2code-transpiled scalar function, nor any tensor helper. The 3D
   path (deviatoric tensor return + Prager tensor back-stress +
   power-law alpha + algo2code scalar multiplier solve) and this path
   share no code; they agree only because both encode the same *physics*
   integrated by different algebra.

2. **Reduction cross-checks (the strongest signal).** The companion test
   compares the 3D mixed law against the ALREADY-VALIDATED P6-1 isotropic
   and P6-2 kinematic implementations in the two degenerate limits
   (``H_kin = 0`` and ``K = 0``). Those reductions are independent of
   this reference entirely, so even a wrong reference cannot mask a
   mixed-law error: the reductions tie the mixed law back to two
   independently-validated models.

Mapping to the 3D model
-----------------------

The 3D mixed model works in deviatoric/von-Mises space. A uniaxial
*deviatoric* Green-Lagrange strain ``E = diag(e, -e/2, -e/2)`` (traceless,
so the elastic predictor is purely deviatoric, no volumetric coupling)
maps to this 1D model with the *effective deviatoric* parameters::

    E_1d    = 3*mu      (signed von-Mises trial-stress slope vs e)
    H_kin   = H_kin     (Prager modulus)
    K, n    = K, n      (power-law isotropic radius, unchanged)
    Y0      = sigma_y0  (initial yield radius)

and the comparable 1D "stress" is the signed von-Mises equivalent of the
deviatoric stress, recovered from the 3D tensor as ``1.5 * dev(S)[0,0]``.
The accumulated plastic strain ``alpha`` increments by ``|dl_1d|`` each
plastic step, matching the 3D ``alpha += dl`` convention (``dl >= 0`` and
the 1D plastic increment magnitude equals the von-Mises equivalent
increment ``dl``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from numpy.typing import NDArray


@dataclass(frozen=True)
class Mixed1D:
    """Parameters of the 1D mixed-hardening model.

    Parameters
    ----------
    E : float
        Elastic modulus (1D). For the deviatoric mapping this is ``3*mu``.
    H_kin : float
        Linear kinematic (Prager) hardening modulus.
    K : float
        Isotropic power-law hardening modulus.
    n : float
        Isotropic power-law hardening exponent.
    sigma_y0 : float
        Initial yield stress (radius at alpha = 0).
    """

    E: float
    H_kin: float
    K: float
    n: float
    sigma_y0: float

    def sigma_y(self, alpha: float) -> float:
        """Isotropic radius sigma_y(alpha) = sigma_y0 + K*alpha^n."""
        if alpha <= 0.0:
            return self.sigma_y0
        return float(self.sigma_y0 + self.K * alpha**self.n)

    def iso_slope(self, alpha: float) -> float:
        """Isotropic slope d(sigma_y)/d(alpha) = K*n*alpha^(n-1).

        Regularised to 0 below 1e-12 (the n<1 divergence guard), matching
        the 3D path's :func:`mechdsl.lib.plasticity_mixed._isotropic_slope`.
        """
        if alpha <= 1e-12:
            return 0.0
        return float(self.K * self.n * alpha ** (self.n - 1.0))


def _solve_dl_newton(
    model: Mixed1D,
    xi_trial_abs: float,
    alpha_old: float,
    tol: float = 1e-13,
    max_iter: int = 100,
) -> float:
    """Independent 1D scalar Newton solve for the plastic multiplier.

    Solves the 1D mixed consistency residual::

        r(dl) = xi_trial_abs - (E + H_kin)*dl - sigma_y(alpha_old + dl) = 0
        r'(dl) = -(E + H_kin) - K*n*(alpha_old + dl)^(n-1)

    Here ``E`` is the 1D elastic modulus (== 3*mu in the deviatoric
    mapping), so ``E + H_kin`` plays the role of the 3D ``3*mu + H_kin``.

    This is a SEPARATE implementation from the transpiled algo2code
    scalar solve — its own residual, its own derivative, its own loop —
    so an error in the transpiled solve cannot be masked by this oracle.
    """
    dl = 0.0
    for _ in range(max_iter):
        alpha = alpha_old + dl
        sy = model.sigma_y(alpha)
        slope = model.iso_slope(alpha)
        r = xi_trial_abs - (model.E + model.H_kin) * dl - sy
        if abs(r) < tol * max(model.sigma_y0, 1.0):
            break
        drdl = -(model.E + model.H_kin) - slope
        dl -= r / drdl
    return dl


def simulate_uniaxial_cyclic(
    model: Mixed1D,
    strain_path: NDArray,
) -> dict[str, NDArray]:
    """Integrate the 1D mixed-hardening model along a strain path.

    Strain-driven, fully implicit one-step return per increment. The
    isotropic power law makes the consistency residual nonlinear in the
    plastic-multiplier increment, so each plastic step runs the
    independent 1D scalar Newton solve :func:`_solve_dl_newton`::

        sigma_trial = E*(eps - ep_old)
        xi          = sigma_trial - q_old
        f           = |xi| - sigma_y(alpha_old)
        if f <= 0:  elastic, sigma = sigma_trial
        else:       dl = Newton(|xi|, alpha_old);  s = sign(xi)
                    ep    += dl*s
                    q     += H_kin*dl*s
                    alpha += dl
                    sigma  = E*(eps - ep)

    Parameters
    ----------
    model:
        Mixed-hardening material parameters.
    strain_path:
        1D array of total strains (loading / unloading / reverse).

    Returns
    -------
    dict with keys:
        ``strain``         total strain (echoed),
        ``stress``         signed stress,
        ``back_stress``    signed kinematic back-stress q,
        ``plastic_strain`` accumulated (signed) plastic strain ep,
        ``alpha``          accumulated (unsigned) equivalent plastic strain,
        ``is_plastic``     bool per step.
    """
    strain_path = np.asarray(strain_path, dtype=np.float64)
    n = strain_path.size

    stress = np.empty(n, dtype=np.float64)
    back = np.empty(n, dtype=np.float64)
    ep_arr = np.empty(n, dtype=np.float64)
    alpha_arr = np.empty(n, dtype=np.float64)
    plastic = np.empty(n, dtype=bool)

    ep = 0.0
    q = 0.0
    alpha = 0.0
    for i, eps in enumerate(strain_path):
        sigma_trial = model.E * (eps - ep)
        xi = sigma_trial - q
        f = abs(xi) - model.sigma_y(alpha)
        if f <= 0.0:
            sigma = sigma_trial
            plastic[i] = False
        else:
            dl = _solve_dl_newton(model, abs(xi), alpha)
            sgn = 1.0 if xi >= 0.0 else -1.0
            ep += dl * sgn
            q += model.H_kin * dl * sgn
            alpha += dl
            sigma = model.E * (eps - ep)
            plastic[i] = True
        stress[i] = sigma
        back[i] = q
        ep_arr[i] = ep
        alpha_arr[i] = alpha

    return {
        "strain": strain_path,
        "stress": stress,
        "back_stress": back,
        "plastic_strain": ep_arr,
        "alpha": alpha_arr,
        "is_plastic": plastic,
    }


def analytic_first_yield(model: Mixed1D) -> dict[str, float]:
    """Closed-form first-yield landmarks (hand-verifiable).

    Before any plastic flow ``alpha = 0`` and ``q = 0``, so the response
    is purely elastic until ``|sigma| = sigma_y0``:

    - ``eps_yield``   = sigma_y0 / E,
    - ``sigma_yield`` = sigma_y0.

    These are independent of K, n and H_kin (all hardening engages only
    after first yield), giving a clean reviewer check.
    """
    return {
        "eps_yield": model.sigma_y0 / model.E,
        "sigma_yield": model.sigma_y0,
    }


__all__ = [
    "Mixed1D",
    "analytic_first_yield",
    "simulate_uniaxial_cyclic",
]
