"""Lemaitre continuum damage mechanics coupled to J2 power-law plasticity.

Implements the classic Lemaitre scalar isotropic damage model with the
effective-stress principle and strain equivalence:

    sigma_effective = sigma_nominal / (1 - D)

The plastic law is applied to the effective stress; damage evolves from the
elastic energy release rate ``Y`` released per unit increment of accumulated
plastic strain ``p``:

    dD/dp = (Y / S_d)^{s_d},    with  Y = sigma_eq^2 * R_v / (2 E (1-D)^2)

where ``R_v`` is the de Souza Neto triaxiality factor

    R_v = 2/3 (1 + nu) + 3 (1 - 2 nu) (sigma_H / sigma_eq)^2 .

Damage is only active once the accumulated plastic strain exceeds the
threshold ``eps_D`` (the damage-nucleation strain).  ``D`` is clamped below
``1 - 1e-6`` to keep the ``1 - D`` divisor away from singularity — final
element deletion at ``D >= D_crit`` is handled in Task P6-2.

References
----------
Lemaitre (1985), A continuous damage mechanics model for ductile fracture,
    J. Eng. Mater. Technol. 107, 83-89.
de Souza Neto, Peric & Owen (2008), Computational Methods for Plasticity,
    Ch. 12 (Lemaitre's ductile damage model).
Simo & Hughes (1998), Computational Inelasticity, Ch. 3.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from mechdsl.symbolic.models.j2_power_law import (
    J2PowerLawMaterial,
)
from mechdsl.symbolic.models.j2_power_law import (
    radial_return as j2_radial_return,
)
from mechdsl.symbolic.voigt import sym_tensor_to_voigt

if TYPE_CHECKING:
    from numpy.typing import NDArray


# ---------------------------------------------------------------------------
# Numerical constants
# ---------------------------------------------------------------------------

# Upper bound on damage imposed during the return map.  Keeps the (1 - D)
# divisor numerically safe; element deletion at ``D_crit`` happens well
# below this ceiling.
D_MAX = 1.0 - 1e-6


# ---------------------------------------------------------------------------
# Material dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LemaitreMaterial:
    """Lemaitre damage material built on top of J2 power-law plasticity.

    Parameters
    ----------
    E : float
        Young's modulus (> 0).
    nu : float
        Poisson's ratio (-1 < nu < 0.5).
    sigma_y0 : float
        Initial yield stress (> 0).
    K : float
        Isotropic hardening modulus (>= 0).
    n : float
        Hardening exponent (> 0).
    S_d : float
        Damage denominator parameter in the evolution law (> 0, units of stress).
    s_d : float
        Damage evolution exponent (> 0).
    eps_D : float
        Damage nucleation threshold on the accumulated plastic strain
        (>= 0).  No damage accumulates while ``alpha <= eps_D``.
    """

    E: float
    nu: float
    sigma_y0: float
    K: float
    n: float
    S_d: float
    s_d: float
    eps_D: float

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
        if self.S_d <= 0:
            raise ValueError(f"S_d must be > 0, got {self.S_d}")
        if self.s_d <= 0:
            raise ValueError(f"s_d must be > 0, got {self.s_d}")
        if self.eps_D < 0:
            raise ValueError(f"eps_D must be >= 0, got {self.eps_D}")

    @property
    def lam(self) -> float:
        """First Lame parameter lambda."""
        return self.E * self.nu / ((1.0 + self.nu) * (1.0 - 2.0 * self.nu))

    @property
    def mu(self) -> float:
        """Second Lame parameter (shear modulus) mu."""
        return self.E / (2.0 * (1.0 + self.nu))

    def as_j2(self) -> J2PowerLawMaterial:
        """Project to the underlying J2 power-law material (damage-free)."""
        return J2PowerLawMaterial(
            E=self.E,
            nu=self.nu,
            sigma_y0=self.sigma_y0,
            K=self.K,
            n=self.n,
        )


# ---------------------------------------------------------------------------
# Helpers: triaxiality factor and energy release rate
# ---------------------------------------------------------------------------


def triaxiality_factor(sigma_voigt: NDArray, nu: float) -> float:
    """de Souza Neto triaxiality factor ``R_v``.

    ``R_v = 2/3 (1 + nu) + 3 (1 - 2 nu) (sigma_H / sigma_eq)^2``

    where ``sigma_H = tr(sigma)/3`` is the hydrostatic stress and
    ``sigma_eq = sqrt(3/2 s:s)`` is the von Mises equivalent.  When the
    deviatoric stress is (near-)zero the ratio ``sigma_H/sigma_eq`` is
    ill-defined; in that case ``R_v`` is returned as the purely deviatoric
    lower bound ``2/3 (1 + nu)`` — this matches the behaviour of the return
    map (no deviatoric stress implies no plastic flow, so R_v is never
    actually consumed by the damage evolution).

    Parameters
    ----------
    sigma_voigt : NDArray, shape (6,)
        Stress in tensorial Voigt ordering [xx, yy, zz, xy, xz, yz] with
        unscaled shears (07-CONVENTIONS §2).
    nu : float
        Poisson's ratio.

    Returns
    -------
    float
        The triaxiality factor ``R_v``.
    """
    if sigma_voigt.shape != (6,):
        raise ValueError(f"Expected (6,) Voigt vector, got {sigma_voigt.shape}")

    # Hydrostatic stress: sigma_H = (sxx + syy + szz) / 3
    sigma_H = float((sigma_voigt[0] + sigma_voigt[1] + sigma_voigt[2]) / 3.0)

    # Deviatoric components (indices 0..2 for normal, 3..5 for shear)
    s_xx = sigma_voigt[0] - sigma_H
    s_yy = sigma_voigt[1] - sigma_H
    s_zz = sigma_voigt[2] - sigma_H
    s_xy = sigma_voigt[3]
    s_xz = sigma_voigt[4]
    s_yz = sigma_voigt[5]

    # s:s = s_ij s_ij (symmetric, shears counted twice)
    s_dot_s = (
        s_xx * s_xx + s_yy * s_yy + s_zz * s_zz + 2.0 * (s_xy * s_xy + s_xz * s_xz + s_yz * s_yz)
    )
    sigma_eq = float(np.sqrt(1.5 * s_dot_s))

    base = 2.0 / 3.0 * (1.0 + nu)

    # Guard against sigma_eq == 0 (pure hydrostatic or pure zero stress).
    # In that regime damage never accumulates, so the value below is unused,
    # but returning a finite number keeps callers safe.
    if sigma_eq <= 1e-30:
        return base

    triax_ratio = sigma_H / sigma_eq
    return float(base + 3.0 * (1.0 - 2.0 * nu) * triax_ratio * triax_ratio)


def energy_release_rate(sigma_eq: float, R_v: float, E: float, D: float) -> float:
    """Elastic energy release rate ``Y``.

    ``Y = sigma_eq^2 * R_v / (2 * E * (1 - D)^2)``

    Parameters
    ----------
    sigma_eq : float
        Von Mises equivalent stress (effective stress in Lemaitre context).
    R_v : float
        Triaxiality factor (:func:`triaxiality_factor`).
    E : float
        Young's modulus.
    D : float
        Current damage value in ``[0, 1 - 1e-6]``.

    Returns
    -------
    float
        Non-negative energy release rate.
    """
    if sigma_eq <= 0.0:
        return 0.0
    one_minus_D = 1.0 - D
    # ``D`` is always clamped below D_MAX by the return map, but be defensive.
    if one_minus_D <= 0.0:
        one_minus_D = 1.0 - D_MAX
    return float(sigma_eq * sigma_eq * R_v / (2.0 * E * one_minus_D * one_minus_D))


# ---------------------------------------------------------------------------
# Result struct
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LemaitreReturnResult:
    """Result of the Lemaitre effective-stress return map.

    ``stress`` is the **nominal** PK2 stress, i.e. ``(1 - D_new) * sigma_eff``.
    ``tangent`` is the undamaged J2 algorithmic tangent — a damage-aware
    tangent is a P6-2 concern and is deliberately left unscaled here so that
    at ``D = 0`` this model reproduces J2 power-law byte-for-byte.
    """

    stress: NDArray  # Nominal PK2 stress (3, 3)
    alpha_new: float  # Updated equivalent plastic strain
    D_new: float  # Updated damage (clamped below D_MAX)
    delta_lambda: float  # Plastic multiplier increment
    is_plastic: bool  # Whether yielding occurred
    tangent: NDArray  # Algorithmic tangent (3, 3, 3, 3) — J2 effective-space


# ---------------------------------------------------------------------------
# Core return map
# ---------------------------------------------------------------------------


def lemaitre_return(
    mat: LemaitreMaterial,
    E_strain: NDArray,
    alpha_n: float,
    D_n: float,
    dt: float = 1.0,
    tol: float = 1e-12,
    max_iter: int = 50,
) -> LemaitreReturnResult:
    """Lemaitre effective-stress return mapping coupled to J2 power-law.

    Algorithm (strain-equivalence, per task P6-1)
    ---------------------------------------------
    1. Run the J2 power-law radial return on the (total) elastic predictor.
       Because the elastic predictor ``lambda tr(E) I + 2 mu E`` is built from
       the undamaged stiffness, the J2 result IS the effective stress field
       ``sigma_eff`` — this is the Lemaitre strain-equivalence assumption.
    2. Evaluate the triaxiality factor ``R_v`` and equivalent effective
       stress ``sigma_eq`` on that effective stress.
    3. Compute the energy release rate ``Y`` from ``sigma_eq, R_v, E, D_n``.
    4. If the new plastic strain exceeds the damage threshold ``eps_D``,
       increment damage:  ``D_new = D_n + (Y / S_d)^{s_d} * delta_lambda``.
       Otherwise leave ``D_new = D_n`` (guards ``D`` from accidentally
       crossing the threshold mid-step is overkill for P6-1; in practice the
       step sizes in the solver stay below the yield-threshold gap).
    5. Clamp ``D_new <= 1 - 1e-6`` (element deletion is P6-2's job).
    6. Nominal stress:  ``sigma_nominal = (1 - D_new) * sigma_eff``.

    Parameters
    ----------
    mat : LemaitreMaterial
        Material parameters.
    E_strain : NDArray, shape (3, 3)
        Total Green-Lagrange strain at the step end (Total Lagrangian).
    alpha_n : float
        Equivalent plastic strain at step start.
    D_n : float
        Damage at step start, must be in ``[0, D_MAX]``.
    dt : float
        Time-step size; retained in the signature so that future rate-
        dependent extensions (Perzyna + damage) are drop-in compatible.
        Ignored here (rate-independent J2 driver).
    tol : float
        Newton tolerance forwarded to the J2 return map.
    max_iter : int
        Maximum iterations forwarded to the J2 return map.

    Returns
    -------
    LemaitreReturnResult
        Nominal stress, updated (alpha, D), plastic multiplier, tangent.
    """
    if not (0.0 <= D_n <= D_MAX):
        # Allow exactly D_MAX (the clamp ceiling) but reject values outside [0, D_MAX].
        if D_n > D_MAX + 1e-15 or D_n < -1e-15:
            raise ValueError(
                f"D_n must be in [0, {D_MAX}], got {D_n}. "
                f"Element should have been marked for deletion in Plan B phase B6."
            )
        # Tiny numerical overshoot — snap to the clamp ceiling/floor.
        D_n = min(max(D_n, 0.0), D_MAX)

    # --- 1. Effective-stress J2 return map ----------------------------------
    j2_mat = mat.as_j2()
    j2_res = j2_radial_return(j2_mat, E_strain, alpha_old=alpha_n, tol=tol, max_iter=max_iter)

    sigma_eff: NDArray = j2_res.stress
    alpha_new = j2_res.alpha_new
    delta_lambda = j2_res.delta_lambda

    # --- 2. Compute effective von Mises and triaxiality factor --------------
    sigma_eff_voigt = sym_tensor_to_voigt(sigma_eff)
    sigma_H = float((sigma_eff_voigt[0] + sigma_eff_voigt[1] + sigma_eff_voigt[2]) / 3.0)
    s_xx = sigma_eff_voigt[0] - sigma_H
    s_yy = sigma_eff_voigt[1] - sigma_H
    s_zz = sigma_eff_voigt[2] - sigma_H
    s_xy = sigma_eff_voigt[3]
    s_xz = sigma_eff_voigt[4]
    s_yz = sigma_eff_voigt[5]
    s_dot_s = (
        s_xx * s_xx + s_yy * s_yy + s_zz * s_zz + 2.0 * (s_xy * s_xy + s_xz * s_xz + s_yz * s_yz)
    )
    sigma_eq = float(np.sqrt(1.5 * s_dot_s))

    R_v = triaxiality_factor(sigma_eff_voigt, mat.nu)

    # --- 3. Energy release rate Y -------------------------------------------
    Y = energy_release_rate(sigma_eq=sigma_eq, R_v=R_v, E=mat.E, D=D_n)

    # --- 4. Damage evolution -------------------------------------------------
    # Only increment damage if (a) a plastic step actually occurred, and
    # (b) the accumulated plastic strain at step end exceeds the threshold.
    if j2_res.is_plastic and alpha_new > mat.eps_D and Y > 0.0:
        dD = (Y / mat.S_d) ** mat.s_d * delta_lambda
        D_new = D_n + dD
    else:
        D_new = D_n

    # --- 5. Clamp ------------------------------------------------------------
    if D_new > D_MAX:
        D_new = D_MAX
    if D_new < 0.0:
        # Theoretically impossible (all ingredients non-negative) but guard anyway.
        D_new = 0.0

    # --- 6. Nominal stress ---------------------------------------------------
    nominal_stress: NDArray = (1.0 - D_new) * sigma_eff

    return LemaitreReturnResult(
        stress=nominal_stress,
        alpha_new=alpha_new,
        D_new=D_new,
        delta_lambda=delta_lambda,
        is_plastic=j2_res.is_plastic,
        tangent=j2_res.tangent,
    )
