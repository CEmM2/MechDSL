"""J2 mixed hardening (isotropic power-law + linear kinematic) — algo2code path.

constitutive_latex Phase 6 (P6-3). The dissipative MIXED-hardening
return map: the yield surface BOTH *translates* (back-stress ``beta``,
Prager — from P6-2) AND *expands* (power-law radius
``sigma_y(alpha) = sigma_y0 + K*alpha^n`` — from P6-1), simultaneously.
Yield is measured on the RELATIVE (shifted) stress ``xi = dev(S) - beta``
against the EXPANDING radius ``sigma_y(alpha)``::

    f = ||xi||_eq - sigma_y(alpha),   sigma_y(alpha) = sigma_y0 + K*alpha^n

The scalar plastic-multiplier solve is the ``algo2code``-transpiled
function from ``dev/algorithms/radial_return_j2_mixed.tex`` (loaded via
:func:`algo2code.library.radial_return_j2_mixed.transpile_radial_return_j2_mixed`).
Because the isotropic part is a nonlinear power law in
``alpha = alpha_old + dl`` the discrete consistency condition is
NONLINEAR in ``dl``, so the scalar source runs the Newton loop of the
isotropic variant (P6-1) — with the kinematic ``(3*mu + H_kin)*dl``
linear term in the residual and the Prager modulus folded into the
Newton denominator alongside the isotropic slope. The surrounding tensor
algebra is orchestrated here in NumPy — the same division of labour as
:mod:`mechdsl.lib.plasticity` (isotropic) and
:mod:`mechdsl.lib.plasticity_kinematic` (kinematic).

State carried between steps
---------------------------

Both internal variables advance together (this is what makes it *mixed*):

- accumulated plastic strain ``alpha`` (drives isotropic radius growth);
- deviatoric back-stress tensor ``beta`` (Prager translation);
- plastic strain ``Ep`` (the elastic predictor uses ``E - Ep``).

Flow direction and tensor updates (identical convention to P6-2)
----------------------------------------------------------------

The flow normal is the von-Mises yield-function gradient
``nf = d||xi||_eq/dS = (3/2) * xi / ||xi||_eq``. With ``dEp = dl*nf`` the
deviatoric stress relaxes by ``||2*mu*dl*nf||_eq = 3*mu*dl``, the Prager
back-stress advances by ``||(2/3)*H_kin*dl*nf||_eq = H_kin*dl``, and the
radius grows by ``sigma_y(alpha+dl) - sigma_y(alpha)``. Setting
``||xi_new||_eq = sigma_y(alpha+dl)`` gives the consistency residual the
scalar solve inverts::

    r(dl) = ||xi_trial||_eq - (3*mu + H_kin)*dl - sigma_y(alpha_old + dl) = 0

with ``alpha_new = alpha_old + dl``,
``beta_new = beta_old + (2/3)*H_kin*dl*nf``.

Reductions
----------

- ``H_kin = 0`` -> ``beta`` stays 0, ``xi == dev(S)``: the law reduces to
  the isotropic power-law variant (P6-1).
- ``K = 0`` -> ``sigma_y(alpha) == sigma_y0`` (constant radius), the
  residual is linear: the law reduces to the linear kinematic variant
  (P6-2).
"""

from __future__ import annotations

from collections.abc import Callable  # noqa: TC003 — runtime use in cast() below
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

import numpy as np

from algo2code.library.radial_return_j2_mixed import (
    transpile_radial_return_j2_mixed,
)
from mechdsl.symbolic.models.j2_power_law import (
    deviatoric,
    elastic_tangent,
    von_mises,
)

if TYPE_CHECKING:
    from numpy.typing import NDArray


# ── Transpile the mixed algpseudocode once at import time ───────────────────
#
# `algo2code.transpile` returns a Python module string with a top-level
# `radial_return_j2_mixed(xi_eq, alpha, mu, K, n, H_kin, sigy0, tol, max_iter)`
# function. We exec it into a clean namespace and capture the callable —
# the same pattern as `mechdsl.lib.plasticity` and `plasticity_kinematic`.
_TRANSPILED_NAMESPACE: dict[str, object] = {}
_TRANSPILED_SOURCE = transpile_radial_return_j2_mixed(backend="taichi")
exec(
    compile(_TRANSPILED_SOURCE, "<algo2code:radial_return_j2_mixed>", "exec"),
    _TRANSPILED_NAMESPACE,
)
_radial_return_mixed_scalar = cast(
    "Callable[..., Any]", _TRANSPILED_NAMESPACE["radial_return_j2_mixed"]
)


@dataclass(frozen=True)
class J2MixedMaterial:
    """J2 plasticity material with mixed (isotropic + kinematic) hardening.

    Parameters
    ----------
    E : float
        Young's modulus (> 0).
    nu : float
        Poisson's ratio (-1 < nu < 0.5).
    sigma_y0 : float
        Initial yield stress (> 0).
    K : float
        Isotropic power-law hardening modulus (>= 0). ``K = 0`` collapses
        to pure kinematic hardening (P6-2).
    n : float
        Isotropic power-law hardening exponent (> 0).
    H_kin : float
        Linear kinematic (Prager) hardening modulus (>= 0). ``H_kin = 0``
        collapses to pure isotropic hardening (P6-1).
    """

    E: float
    nu: float
    sigma_y0: float
    K: float
    n: float
    H_kin: float

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
        if self.H_kin < 0:
            raise ValueError(f"H_kin must be >= 0, got {self.H_kin}")

    @property
    def lam(self) -> float:
        """First Lame parameter lambda."""
        return self.E * self.nu / ((1.0 + self.nu) * (1.0 - 2.0 * self.nu))

    @property
    def mu(self) -> float:
        """Second Lame parameter (shear modulus) mu."""
        return self.E / (2.0 * (1.0 + self.nu))


@dataclass(frozen=True)
class MixedReturnResult:
    """Result of one mixed-hardening return-mapping step."""

    stress: NDArray  # Updated PK2 stress (3, 3)
    alpha_new: float  # Updated accumulated equivalent plastic strain
    plastic_strain: NDArray  # Updated plastic strain Ep (3, 3)
    back_stress: NDArray  # Updated deviatoric back-stress beta (3, 3)
    delta_lambda: float  # Plastic multiplier increment
    is_plastic: bool  # Whether yielding occurred
    tangent: NDArray  # Algorithmic tangent (3, 3, 3, 3)


def radial_return_mixed(
    mat: J2MixedMaterial,
    E_strain: NDArray,
    alpha_old: float,
    plastic_strain_old: NDArray,
    back_stress_old: NDArray,
    tol: float = 1e-12,
    max_iter: int = 50,
) -> MixedReturnResult:
    """Mixed-hardening radial return for one strain state.

    The elastic predictor uses the *elastic* strain ``E - Ep_old``; the
    plastic-multiplier solve is the algo2code-transpiled scalar Newton
    function; the back-stress, plastic strain and accumulated plastic
    strain advance in tensor space.

    Parameters
    ----------
    mat:
        Mixed-hardening material parameters.
    E_strain:
        Total Green-Lagrange strain tensor (3, 3) at the current step.
    alpha_old:
        Committed accumulated equivalent plastic strain from the previous
        step (drives the isotropic radius growth).
    plastic_strain_old:
        Committed plastic strain ``Ep`` (3, 3) from the previous step.
    back_stress_old:
        Committed deviatoric back-stress ``beta`` (3, 3) from the
        previous step.
    tol, max_iter:
        Passed through to the scalar Newton solve.

    Returns
    -------
    MixedReturnResult
    """
    lam = mat.lam
    mu = mat.mu

    # --- 1. Elastic predictor on the elastic strain E - Ep. ---
    E_elastic = E_strain - plastic_strain_old
    tr_Ee = float(np.trace(E_elastic))
    S_trial = lam * tr_Ee * np.eye(3) + 2.0 * mu * E_elastic

    # --- 2. Deviatoric / volumetric split and RELATIVE stress xi. ---
    S_dev_trial = deviatoric(S_trial)
    S_vol_trial = S_trial - S_dev_trial
    xi_trial = S_dev_trial - back_stress_old
    xi_eq_trial = von_mises(xi_trial)

    # --- 3. Near-zero relative-stress guard (07-CONVENTIONS analogue). ---
    if xi_eq_trial < 1e-12 * mat.sigma_y0:
        C_el = elastic_tangent(lam, mu)
        return MixedReturnResult(
            stress=S_trial,
            alpha_new=alpha_old,
            plastic_strain=plastic_strain_old,
            back_stress=back_stress_old,
            delta_lambda=0.0,
            is_plastic=False,
            tangent=C_el,
        )

    # --- 4. Scalar plastic-multiplier Newton solve — algo2code-transpiled. ---
    # The wrapper recomputes alpha_new = alpha_old + dl itself (the orchestration
    # is authoritative for state), so the scalar's alpha_new is intentionally
    # unused — same division of labour as mechdsl.lib.plasticity.
    plastic_flag, _alpha_new_from_algo, dl_from_algo = _radial_return_mixed_scalar(
        xi_eq=xi_eq_trial,
        alpha=alpha_old,
        mu=mu,
        K=mat.K,
        n=mat.n,
        H_kin=mat.H_kin,
        sigy0=mat.sigma_y0,
        tol=tol,
        max_iter=max_iter,
    )

    if plastic_flag == 0:
        C_el = elastic_tangent(lam, mu)
        return MixedReturnResult(
            stress=S_trial,
            alpha_new=alpha_old,
            plastic_strain=plastic_strain_old,
            back_stress=back_stress_old,
            delta_lambda=0.0,
            is_plastic=False,
            tangent=C_el,
        )

    dl = float(dl_from_algo)
    if dl < 0.0:
        if dl >= -1e-15:
            dl = 0.0
        else:
            msg = f"Negative plastic multiplier delta_lambda = {dl:.3e}"
            raise ValueError(msg)

    # --- 5. Flow direction and tensor updates (Prager + isotropic alpha). ---
    #
    # Flow normal nf = (3/2) * xi / ||xi||_eq, the gradient of the von Mises
    # yield function df/dS. With dEp = dl*nf the deviatoric stress relaxes by
    # ||2*mu*dl*nf||_eq = 3*mu*dl, the Prager back-stress advances by
    # ||(2/3)*H_kin*dl*nf||_eq = H_kin*dl, and the radius grows by
    # sigma_y(alpha+dl) - sigma_y(alpha) — so ||xi||_eq returns exactly to the
    # (expanded) yield surface. Same flow-normal convention as P6-2; using
    # xi/||xi||_eq directly would mis-scale both the return and the back-stress.
    nf = 1.5 * xi_trial / xi_eq_trial

    S_dev_updated = S_dev_trial - 2.0 * mu * dl * nf
    S_updated = S_vol_trial + S_dev_updated

    plastic_strain_new = plastic_strain_old + dl * nf
    back_stress_new = back_stress_old + (2.0 / 3.0) * mat.H_kin * dl * nf
    alpha_new = alpha_old + dl

    # --- 6. Algorithmic consistent tangent (Simo-Hughes form, mixed). ---
    #
    # The linearised return map has the canonical factored form with the flow
    # normal taken from the RELATIVE stress xi and the hardening denominator
    # 3*mu + H_kin + H_iso', where H_iso' = K*n*alpha_new^(n-1) is the isotropic
    # power-law slope at the converged state. Reduces to the isotropic tangent
    # when H_kin = 0 and to the kinematic tangent when K = 0.
    H_iso_prime = _isotropic_slope(mat, alpha_new)
    C_ep = _assemble_mixed_tangent(
        lam=lam,
        mu=mu,
        xi_trial=xi_trial,
        xi_eq_trial=xi_eq_trial,
        dl=dl,
        denominator=3.0 * mu + mat.H_kin + H_iso_prime,
    )

    return MixedReturnResult(
        stress=S_updated,
        alpha_new=alpha_new,
        plastic_strain=plastic_strain_new,
        back_stress=back_stress_new,
        delta_lambda=dl,
        is_plastic=True,
        tangent=C_ep,
    )


def _isotropic_slope(mat: J2MixedMaterial, alpha: float) -> float:
    """Isotropic power-law hardening slope H' = K*n*alpha^(n-1).

    Mirrors :func:`mechdsl.symbolic.models.j2_power_law.yield_stress_derivative`:
    for hardening exponents n < 1 the slope diverges as alpha -> 0+, so a
    regularisation threshold returns 0 below it.
    """
    if alpha <= 1e-12:
        return 0.0
    return float(mat.K * mat.n * alpha ** (mat.n - 1.0))


def _assemble_mixed_tangent(
    lam: float,
    mu: float,
    xi_trial: NDArray,
    xi_eq_trial: float,
    dl: float,
    denominator: float,
) -> NDArray:
    """Algorithmic consistent tangent for mixed hardening.

    Identical factored form to
    :func:`mechdsl.symbolic.models.j2_power_law.assemble_j2_like_tangent`
    and :func:`mechdsl.lib.plasticity_kinematic._assemble_kinematic_tangent`,
    with the flow normal taken from the RELATIVE stress ``xi`` and the
    hardening denominator ``3*mu + H_kin + H_iso'``::

        C_alg = kappa * (I⊗I)
              + 2*mu*theta * P_dev
              + (9*mu^2*dl/||xi|| - 9*mu^2/denominator) * (n⊗n)

    with ``theta = 1 - 3*mu*dl/||xi||`` and ``n = xi/||xi||``.
    """
    kappa = lam + 2.0 * mu / 3.0
    theta = 1.0 - 3.0 * mu * dl / xi_eq_trial

    I2 = np.eye(3)
    I_sym = 0.5 * (np.einsum("ik,jl->ijkl", I2, I2) + np.einsum("il,jk->ijkl", I2, I2))
    P_dev = I_sym - (1.0 / 3.0) * np.einsum("ij,kl->ijkl", I2, I2)

    n_flow = xi_trial / xi_eq_trial
    n_outer_n = np.einsum("ij,kl->ijkl", n_flow, n_flow)

    C_alg: NDArray = (
        kappa * np.einsum("ij,kl->ijkl", I2, I2)
        + 2.0 * mu * theta * P_dev
        + (9.0 * mu**2 * dl / xi_eq_trial - 9.0 * mu**2 / denominator) * n_outer_n
    )
    return C_alg


__all__ = [
    "J2MixedMaterial",
    "MixedReturnResult",
    "radial_return_mixed",
]
