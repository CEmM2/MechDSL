"""Independent 1D bilinear kinematic-hardening plasticity reference.

constitutive_latex Phase 6 (P6-2). Ground-truth oracle for the J2 linear
kinematic (Prager) hardening return map. There is NO existing mechdsl
oracle for kinematic hardening (the j2_power_law oracle is isotropic), so
this reference is a *self-authored* ground truth — and the top risk for
P6-2 is "a wrong reference silently passes a wrong transpile."

Two defences make it trustworthy:

1. **Independent derivation.** This is the classical scalar 1D bilinear
   kinematic plasticity model in *physical* stress-strain space
   (``sigma``, total strain ``eps``, plastic strain ``ep``, scalar
   back-stress ``q``), NOT a scalarisation of the 3D tensor radial-return
   algebra. It is a textbook elementary model:

       sigma = E*(eps - ep)            (1D Hooke on the elastic strain)
       q     = H*ep                    (linear kinematic back-stress)
       f     = |sigma - q| - sigma_y0  (yield on the relative stress)

   The 3D path (deviatoric tensor return + Prager tensor back-stress +
   algo2code scalar multiplier solve) and this path share no code. They
   only agree because both are the same *physics*, integrated by
   different algebra — exactly the independent differential-test the plan
   (lines 200, 207) calls for.

2. **Analytic cross-validation.** :func:`analytic_bilinear_landmarks`
   returns the hand-computable closed-form landmarks of the bilinear
   cyclic response (first-yield strain/stress, post-yield tangent
   modulus, forward back-stress, reverse-yield stress). The companion
   test asserts the simulator reproduces these BEFORE the reference is
   trusted to validate the transpile.

Mapping to the 3D model
-----------------------

The 3D kinematic model works in deviatoric/von-Mises space. A uniaxial
*deviatoric* Green-Lagrange strain ``E = diag(e, -e/2, -e/2)`` (traceless,
so the elastic predictor is purely deviatoric, no volumetric coupling)
maps to this 1D model with the *effective deviatoric* parameters::

    E_1d  = 3*mu      (signed von-Mises trial-stress slope vs e)
    H_1d  = H_kin     (Prager modulus)
    Y     = sigma_y0  (constant yield radius)

and the comparable 1D "stress" is the signed von-Mises equivalent of the
deviatoric stress, recovered from the 3D tensor as ``1.5 * dev(S)[0,0]``.
See :func:`packages/mechdsl-core/tests/plan_tests/constitutive_latex/test_P6-2.py`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from numpy.typing import NDArray


@dataclass(frozen=True)
class Bilinear1D:
    """Parameters of the 1D bilinear kinematic-hardening model.

    Parameters
    ----------
    E : float
        Elastic modulus (1D). For the deviatoric mapping this is ``3*mu``.
    H : float
        Linear kinematic-hardening modulus.
    sigma_y0 : float
        Constant yield stress.
    """

    E: float
    H: float
    sigma_y0: float

    @property
    def E_tangent(self) -> float:
        """Post-yield (elastoplastic) tangent modulus E_t = E*H/(E+H)."""
        return self.E * self.H / (self.E + self.H)

    @property
    def eps_yield(self) -> float:
        """First-yield total strain, eps_y = sigma_y0 / E."""
        return self.sigma_y0 / self.E


def simulate_uniaxial_cyclic(
    model: Bilinear1D,
    strain_path: NDArray,
) -> dict[str, NDArray]:
    """Integrate the 1D bilinear kinematic model along a strain path.

    Strain-driven, fully implicit one-step return (the bilinear residual
    is linear, so the closed form is exact each step):

        sigma_trial = E*(eps - ep_old)
        f = |sigma_trial - q_old| - sigma_y0
        if f <= 0:  elastic, sigma = sigma_trial
        else:       dl = f/(E+H); s = sign(sigma_trial - q_old)
                    ep += dl*s;  q += H*dl*s;  sigma = E*(eps - ep)

    Parameters
    ----------
    model:
        Bilinear material parameters.
    strain_path:
        1D array of total strains (loading / unloading / reverse).

    Returns
    -------
    dict with keys:
        ``strain``      total strain (echoed),
        ``stress``      signed stress,
        ``back_stress`` signed kinematic back-stress q,
        ``plastic_strain`` accumulated (signed) plastic strain ep,
        ``is_plastic``  bool per step.
    """
    strain_path = np.asarray(strain_path, dtype=np.float64)
    n = strain_path.size

    stress = np.empty(n, dtype=np.float64)
    back = np.empty(n, dtype=np.float64)
    ep_arr = np.empty(n, dtype=np.float64)
    plastic = np.empty(n, dtype=bool)

    ep = 0.0
    q = 0.0
    for i, eps in enumerate(strain_path):
        sigma_trial = model.E * (eps - ep)
        xi = sigma_trial - q
        f = abs(xi) - model.sigma_y0
        if f <= 0.0:
            sigma = sigma_trial
            plastic[i] = False
        else:
            dl = f / (model.E + model.H)
            sgn = 1.0 if xi >= 0.0 else -1.0
            ep += dl * sgn
            q += model.H * dl * sgn
            sigma = model.E * (eps - ep)
            plastic[i] = True
        stress[i] = sigma
        back[i] = q
        ep_arr[i] = ep

    return {
        "strain": strain_path,
        "stress": stress,
        "back_stress": back,
        "plastic_strain": ep_arr,
        "is_plastic": plastic,
    }


def analytic_bilinear_landmarks(
    model: Bilinear1D,
    eps_peak: float,
) -> dict[str, float]:
    """Closed-form landmarks of a forward-load-then-reverse bilinear cycle.

    Hand-computable from elementary 1D bilinear kinematic plasticity.
    Loading monotonically from 0 to ``eps_peak`` (assumed > eps_yield),
    then reversing.

    Returns the quantities a reviewer can verify by hand:

    - ``eps_yield``        first-yield total strain = sigma_y0 / E.
    - ``sigma_yield``      first-yield stress = sigma_y0.
    - ``E_tangent``        post-yield tangent E_t = E*H/(E+H).
    - ``sigma_peak``       stress at eps_peak on the bilinear envelope:
                           sigma_y0 + E_t*(eps_peak - eps_yield).
    - ``back_stress_peak`` forward back-stress at the peak: q_f.
    - ``sigma_reverse``    stress at which the material re-yields on
                           reversal: q_f - sigma_y0 (Bauschinger).

    Back-stress at peak (closed form): the accumulated plastic strain at
    the peak is ``ep_peak = (eps_peak - eps_yield) * E/(E+H)`` (each
    plastic strain increment is ``f/(E+H)`` and the elastic strain at the
    surface stays sigma_y0/E), hence ``q_f = H * ep_peak``.
    """
    eps_y = model.eps_yield
    Et = model.E_tangent
    sigma_peak = model.sigma_y0 + Et * (eps_peak - eps_y)
    ep_peak = (eps_peak - eps_y) * model.E / (model.E + model.H)
    q_f = model.H * ep_peak
    return {
        "eps_yield": eps_y,
        "sigma_yield": model.sigma_y0,
        "E_tangent": Et,
        "sigma_peak": sigma_peak,
        "back_stress_peak": q_f,
        "sigma_reverse": q_f - model.sigma_y0,
    }


__all__ = [
    "Bilinear1D",
    "analytic_bilinear_landmarks",
    "simulate_uniaxial_cyclic",
]
