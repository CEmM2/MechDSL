"""J2 linear kinematic (Prager) hardening — algo2code-orchestrated path.

constitutive_latex Phase 6 (P6-2). The dissipative kinematic-hardening
return map: the yield surface *translates* (back-stress ``beta``) rather
than *expands*. Yield is measured on the RELATIVE (shifted) stress
``xi = dev(S) - beta`` with a CONSTANT yield radius ``sigma_y0`` (no
isotropic hardening — all hardening lives in ``beta``).

The scalar plastic-multiplier solve is the ``algo2code``-transpiled
function from ``dev/algorithms/radial_return_j2_kinematic.tex`` (loaded
via :func:`algo2code.library.radial_return_j2_kinematic.transpile_radial_return_j2_kinematic`).
The surrounding tensor algebra (deviatoric split, relative stress, von
Mises of ``xi``, stress reconstruction, plastic-strain and back-stress
update, algorithmic tangent) is orchestrated here in NumPy — exactly the
division of labour used by the isotropic variant in
:mod:`mechdsl.lib.plasticity`.

Back-stress update algebra (Prager, discrete)
---------------------------------------------

The flow normal is the von-Mises yield-function gradient
``nf = d||xi||_eq/dS = (3/2) * xi / ||xi||_eq``, which has Frobenius
norm ``||nf||_F = sqrt(3/2)`` and equivalent norm ``||nf||_eq =
sqrt(3/2 * nf:nf) = 3/2``. The associative-flow tensor updates are:

- plastic strain:       ``Ep_new = Ep + dl*nf``
- radial return:        ``dev(S)_new = dev(S)_tr - 2*mu*dl*nf``
- back-stress (Prager): ``beta_new = beta + (2/3)*H_kin*dl*nf``

On a radial step ``xi_new = dev(S)_new - beta_new`` stays parallel to
``nf``, so its equivalent norm drops by ``(3*mu + H_kin)*dl``: the
deviatoric stress relaxes toward the surface by ``||2*mu*dl*nf||_eq =
2*mu*dl*(3/2) = 3*mu*dl`` and the Prager back-stress advances by
``||(2/3)*H_kin*dl*nf||_eq = (2/3)*H_kin*dl*(3/2) = H_kin*dl``. Setting
``||xi_new||_eq = sigma_y0`` gives the linear consistency condition the
scalar return map inverts:

    ``dl = (||xi_trial||_eq - sigma_y0) / (3*mu + H_kin)``.

(Using ``xi/||xi||_eq`` directly — equivalent norm 1 — instead of the
factor-3/2 gradient ``nf`` would mis-scale both the return and the
back-stress: ``||xi||_eq would then contract by only (2*mu + 2/3*H_kin)*dl``
and the step would NOT return to the yield surface.)

State carried between steps: the deviatoric back-stress tensor ``beta``
and the plastic strain ``Ep`` (the elastic predictor uses ``E - Ep``).
"""

from __future__ import annotations

from collections.abc import Callable  # noqa: TC003 — runtime use in cast() below
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

import numpy as np

from algo2code.library.radial_return_j2_kinematic import (
    transpile_radial_return_j2_kinematic,
)
from mechdsl.symbolic.models.j2_power_law import (
    deviatoric,
    elastic_tangent,
    von_mises,
)

if TYPE_CHECKING:
    from numpy.typing import NDArray


# ── Transpile the kinematic algpseudocode once at import time ───────────────
#
# `algo2code.transpile` returns a Python module string with a top-level
# `radial_return_j2_kinematic(xi_eq, mu, H_kin, sigy0, tol, max_iter)`
# function. We exec it into a clean namespace and capture the callable —
# the same pattern as `mechdsl.lib.plasticity`.
_TRANSPILED_NAMESPACE: dict[str, object] = {}
_TRANSPILED_SOURCE = transpile_radial_return_j2_kinematic(backend="taichi")
exec(
    compile(_TRANSPILED_SOURCE, "<algo2code:radial_return_j2_kinematic>", "exec"),
    _TRANSPILED_NAMESPACE,
)
_radial_return_kinematic_scalar = cast(
    "Callable[..., Any]", _TRANSPILED_NAMESPACE["radial_return_j2_kinematic"]
)


@dataclass(frozen=True)
class J2KinematicMaterial:
    """J2 plasticity material with linear kinematic (Prager) hardening.

    Parameters
    ----------
    E : float
        Young's modulus (> 0).
    nu : float
        Poisson's ratio (-1 < nu < 0.5).
    sigma_y0 : float
        (Constant) yield stress (> 0). No isotropic hardening.
    H_kin : float
        Linear kinematic (Prager) hardening modulus (>= 0).
    """

    E: float
    nu: float
    sigma_y0: float
    H_kin: float

    def __post_init__(self) -> None:
        if self.E <= 0:
            raise ValueError(f"E must be > 0, got {self.E}")
        if not (-1 < self.nu < 0.5):
            raise ValueError(f"nu must be in (-1, 0.5), got {self.nu}")
        if self.sigma_y0 <= 0:
            raise ValueError(f"sigma_y0 must be > 0, got {self.sigma_y0}")
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
class KinematicReturnResult:
    """Result of one kinematic return-mapping step."""

    stress: NDArray  # Updated PK2 stress (3, 3)
    plastic_strain: NDArray  # Updated plastic strain Ep (3, 3)
    back_stress: NDArray  # Updated deviatoric back-stress beta (3, 3)
    delta_lambda: float  # Plastic multiplier increment
    is_plastic: bool  # Whether yielding occurred
    tangent: NDArray  # Algorithmic tangent (3, 3, 3, 3)


def radial_return_kinematic(
    mat: J2KinematicMaterial,
    E_strain: NDArray,
    plastic_strain_old: NDArray,
    back_stress_old: NDArray,
    tol: float = 1e-12,
    max_iter: int = 50,
) -> KinematicReturnResult:
    """Linear-kinematic-hardening radial return for one strain state.

    The elastic predictor uses the *elastic* strain ``E - Ep_old``; the
    plastic-multiplier solve is the algo2code-transpiled scalar function;
    the back-stress and plastic strain advance in tensor space (Prager).

    Parameters
    ----------
    mat:
        Kinematic-hardening material parameters.
    E_strain:
        Total Green-Lagrange strain tensor (3, 3) at the current step.
    plastic_strain_old:
        Committed plastic strain ``Ep`` (3, 3) from the previous step.
    back_stress_old:
        Committed deviatoric back-stress ``beta`` (3, 3) from the
        previous step.
    tol, max_iter:
        Passed through to the scalar solve (the linear residual is exact;
        these exist for pattern symmetry with the isotropic variant).

    Returns
    -------
    KinematicReturnResult
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
        return KinematicReturnResult(
            stress=S_trial,
            plastic_strain=plastic_strain_old,
            back_stress=back_stress_old,
            delta_lambda=0.0,
            is_plastic=False,
            tangent=C_el,
        )

    # --- 4. Scalar plastic-multiplier solve — algo2code-transpiled. ---
    plastic_flag, dl_from_algo = _radial_return_kinematic_scalar(
        xi_eq=xi_eq_trial,
        mu=mu,
        H_kin=mat.H_kin,
        sigy0=mat.sigma_y0,
        tol=tol,
        max_iter=max_iter,
    )

    if plastic_flag == 0:
        C_el = elastic_tangent(lam, mu)
        return KinematicReturnResult(
            stress=S_trial,
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

    # --- 5. Flow direction and tensor updates (Prager). ---
    #
    # Flow normal nf = (3/2) * xi / ||xi||_eq, the gradient of the von Mises
    # yield function df/dS (||xi||_eq = sqrt(3/2 xi:xi) => d||xi||/dS = (3/2)
    # xi/||xi||). With dEp = dl*nf the deviatoric stress relaxes by
    # ||2*mu*dl*nf||_eq = 3*mu*dl and the Prager back-stress advances by
    # ||(2/3)*H_kin*dl*nf||_eq = H_kin*dl, so ||xi||_eq contracts by exactly
    # (3*mu + H_kin)*dl — the linear consistency condition the scalar solve
    # inverts. (Using xi/||xi||_eq directly, eq-norm 1, would mis-scale both
    # the return and the back-stress and break consistency.)
    nf = 1.5 * xi_trial / xi_eq_trial

    S_dev_updated = S_dev_trial - 2.0 * mu * dl * nf
    S_updated = S_vol_trial + S_dev_updated

    plastic_strain_new = plastic_strain_old + dl * nf
    back_stress_new = back_stress_old + (2.0 / 3.0) * mat.H_kin * dl * nf

    # --- 6. Algorithmic consistent tangent (Simo-Hughes form, kinematic). ---
    #
    # The linearised return map for linear kinematic hardening has the same
    # structure as the isotropic case with the effective hardening modulus
    # H' replaced by the constant Prager modulus H_kin and the flow normal
    # defined from the RELATIVE stress xi (not dev(S)). Reuse the canonical
    # factored form with denominator (3*mu + H_kin).
    C_ep = _assemble_kinematic_tangent(
        lam=lam,
        mu=mu,
        xi_trial=xi_trial,
        xi_eq_trial=xi_eq_trial,
        dl=dl,
        H_kin=mat.H_kin,
    )

    return KinematicReturnResult(
        stress=S_updated,
        plastic_strain=plastic_strain_new,
        back_stress=back_stress_new,
        delta_lambda=dl,
        is_plastic=True,
        tangent=C_ep,
    )


def _assemble_kinematic_tangent(
    lam: float,
    mu: float,
    xi_trial: NDArray,
    xi_eq_trial: float,
    dl: float,
    H_kin: float,
) -> NDArray:
    """Algorithmic consistent tangent for linear kinematic hardening.

    Identical factored form to :func:`assemble_j2_like_tangent` (Simo &
    Hughes Box 3.5) but with the flow normal taken from the RELATIVE
    stress ``xi`` and the hardening denominator ``3*mu + H_kin``::

        C_alg = kappa * (I⊗I)
              + 2*mu*theta * P_dev
              + (9*mu^2*dl/||xi|| - 9*mu^2/(3*mu+H_kin)) * (n⊗n)

    with ``theta = 1 - 3*mu*dl/||xi||`` and ``n = xi/||xi||``.
    """
    kappa = lam + 2.0 * mu / 3.0
    theta = 1.0 - 3.0 * mu * dl / xi_eq_trial

    I2 = np.eye(3)
    I_sym = 0.5 * (np.einsum("ik,jl->ijkl", I2, I2) + np.einsum("il,jk->ijkl", I2, I2))
    P_dev = I_sym - (1.0 / 3.0) * np.einsum("ij,kl->ijkl", I2, I2)

    n_flow = xi_trial / xi_eq_trial
    n_outer_n = np.einsum("ij,kl->ijkl", n_flow, n_flow)

    denom = 3.0 * mu + H_kin
    C_alg: NDArray = (
        kappa * np.einsum("ij,kl->ijkl", I2, I2)
        + 2.0 * mu * theta * P_dev
        + (9.0 * mu**2 * dl / xi_eq_trial - 9.0 * mu**2 / denom) * n_outer_n
    )
    return C_alg


__all__ = [
    "J2KinematicMaterial",
    "KinematicReturnResult",
    "radial_return_kinematic",
]
