"""J2 plasticity with power-law isotropic hardening — numerical (numpy) implementation.

Implements the radial return mapping algorithm for small-strain J2 plasticity
in the Total Lagrangian setting (PK2 stress, Green-Lagrange strain).

The yield surface is:  f = sigma_eq - sigma_y(alpha)
where sigma_y(alpha) = sigma_y0 + K * alpha^n  (power-law hardening).

References:
    Simo & Hughes (1998), Computational Inelasticity, Ch. 3-4.
    de Souza Neto, Peric & Owen (2008), Computational Methods for Plasticity, Ch. 7.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from mechdsl.symbolic.constitutive import ConstitutiveModel
from mechdsl.symbolic.voigt import tangent_to_voigt_66

if TYPE_CHECKING:
    from numpy.typing import NDArray

# ---------------------------------------------------------------------------
# Material dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class J2PowerLawMaterial:
    """J2 plasticity material with power-law isotropic hardening.

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
    """

    E: float
    nu: float
    sigma_y0: float
    K: float
    n: float

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

    @property
    def lam(self) -> float:
        """First Lame parameter lambda."""
        return self.E * self.nu / ((1.0 + self.nu) * (1.0 - 2.0 * self.nu))

    @property
    def mu(self) -> float:
        """Second Lame parameter (shear modulus) mu."""
        return self.E / (2.0 * (1.0 + self.nu))


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def yield_stress(mat: J2PowerLawMaterial, alpha: float) -> float:
    """Yield stress: sigma_y = sigma_y0 + K * alpha^n."""
    if alpha <= 0.0:
        return mat.sigma_y0
    return float(mat.sigma_y0 + mat.K * alpha**mat.n)


def yield_stress_derivative(mat: J2PowerLawMaterial, alpha: float) -> float:
    """Derivative of yield stress w.r.t. alpha: H' = d(sigma_y)/d(alpha).

    H' = K * n * alpha^(n-1)  for alpha > 0, else 0.

    Warning: For hardening exponents n < 1, the derivative diverges as
    alpha -> 0+.  A regularisation threshold of 1e-12 is used to prevent
    floating-point overflow; this returns H' = 0 for alpha below the
    threshold.  Tests with n < 1 should start from a pre-yielded state
    (alpha > 0) to avoid this boundary.
    """
    if alpha <= 1e-12:
        return 0.0
    return float(mat.K * mat.n * alpha ** (mat.n - 1.0))


def von_mises(stress_dev: NDArray) -> float:
    """Von Mises equivalent stress from deviatoric stress tensor (3x3).

    sigma_eq = sqrt(3/2 * s_ij * s_ij)
    """
    return float(np.sqrt(1.5 * np.tensordot(stress_dev, stress_dev, axes=2)))


def deviatoric(S: NDArray) -> NDArray:
    """Deviatoric part of a symmetric 3x3 tensor: S_dev = S - (1/3)*tr(S)*I."""
    result: NDArray = S - (np.trace(S) / 3.0) * np.eye(3)
    return result


# ---------------------------------------------------------------------------
# Elastic tangent
# ---------------------------------------------------------------------------


def elastic_tangent(lam: float, mu: float) -> NDArray:
    """Fourth-order isotropic elastic tangent C_IJKL.

    C_IJKL = lambda * delta_IJ * delta_KL + mu * (delta_IK * delta_JL + delta_IL * delta_JK)

    Returns shape (3, 3, 3, 3).
    """
    I2 = np.eye(3)
    C: NDArray = lam * np.einsum("ij,kl->ijkl", I2, I2) + mu * (
        np.einsum("ik,jl->ijkl", I2, I2) + np.einsum("il,jk->ijkl", I2, I2)
    )
    return C


# ---------------------------------------------------------------------------
# Deviatoric projector
# ---------------------------------------------------------------------------


def deviatoric_projector() -> NDArray:
    """Fourth-order deviatoric projector P_dev_IJKL.

    P_dev = I_sym - (1/3) * I x I

    where I_sym_IJKL = 0.5 * (delta_IK * delta_JL + delta_IL * delta_JK).

    Returns shape (3, 3, 3, 3).
    """
    I2 = np.eye(3)
    I_sym = 0.5 * (np.einsum("ik,jl->ijkl", I2, I2) + np.einsum("il,jk->ijkl", I2, I2))
    P_dev: NDArray = I_sym - (1.0 / 3.0) * np.einsum("ij,kl->ijkl", I2, I2)
    return P_dev


def assemble_j2_like_tangent(
    lam: float,
    mu: float,
    S_dev_trial: NDArray,
    sigma_eq_trial: float,
    dl: float,
    denominator: float,
) -> NDArray:
    """Assemble the J2-like algorithmic consistent tangent (Simo & Hughes §3.4, Box 3.5).

    This factored form is the canonical Simo-Hughes consistent tangent for any
    associative J2-type model.  Callers supply ``denominator`` which equals
    ``3*mu + H'`` for rate-independent J2, but differs for viscoplastic and
    thermally-coupled models:

    - Rate-independent J2:  denominator = 3*mu + H'
    - Perzyna viscoplasticity:  denominator = 3*mu + H' + eta_term   (§3.4 extended)
    - Johnson-Cook (Schur):  denominator = det(J_Newton) / J_Newton[1,1]

    The assembled tangent is:

        C_alg = kappa * (I ⊗ I)
              + 2*mu*theta * P_dev
              + (9*mu^2*dl/sigma_eq - 9*mu^2/denominator) * (n ⊗ n)

    where:
        kappa  = lam + 2*mu/3  (bulk modulus)
        theta  = 1 - 3*mu*dl/sigma_eq_trial  (return-map scaling)
        P_dev  = I4_sym - (1/3) I⊗I  (deviatoric projector)
        n      = S_dev_trial / sigma_eq_trial  (flow direction, |n|_F = sqrt(2/3))

    Parameters
    ----------
    lam : float
        First Lame parameter.
    mu : float
        Second Lame parameter (shear modulus).
    S_dev_trial : NDArray (3, 3)
        Deviatoric part of the trial stress.
    sigma_eq_trial : float
        Von Mises equivalent trial stress (> 0).
    dl : float
        Converged plastic multiplier increment (>= 0).
    denominator : float
        Effective hardening denominator ``(3*mu + H_eff)``; must be > 0 for a
        stable return.  Caller is responsible for computing this correctly.

    Returns
    -------
    NDArray (3, 3, 3, 3)
        Algorithmic consistent tangent.
    """
    kappa = lam + 2.0 * mu / 3.0
    beta = 1.0 - 3.0 * mu * dl / sigma_eq_trial

    P_dev = deviatoric_projector()
    n_flow = S_dev_trial / sigma_eq_trial  # flow direction, 2-norm = sqrt(2/3)
    n_outer_n = np.einsum("ij,kl->ijkl", n_flow, n_flow)
    I2 = np.eye(3)

    C_alg: NDArray = (
        kappa * np.einsum("ij,kl->ijkl", I2, I2)
        + 2.0 * mu * beta * P_dev
        + (9.0 * mu**2 * dl / sigma_eq_trial - 9.0 * mu**2 / denominator) * n_outer_n
    )
    return C_alg


# ---------------------------------------------------------------------------
# Return mapping result
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReturnMappingResult:
    """Result of the radial return mapping algorithm."""

    stress: NDArray  # Updated PK2 stress (3, 3)
    alpha_new: float  # Updated equivalent plastic strain
    delta_lambda: float  # Plastic multiplier increment
    is_plastic: bool  # Whether yielding occurred
    tangent: NDArray  # Algorithmic tangent (3, 3, 3, 3)


# ---------------------------------------------------------------------------
# Radial return mapping
# ---------------------------------------------------------------------------


def radial_return(
    mat: J2PowerLawMaterial,
    E_strain: NDArray,
    alpha_old: float,
    tol: float = 1e-12,
    max_iter: int = 50,
) -> ReturnMappingResult:
    """Radial return mapping for J2 plasticity with power-law hardening.

    Algorithm
    ---------
    1. Elastic trial: S_trial = lambda * tr(E) * I + 2 * mu * E
    2. Compute deviatoric trial stress and von Mises equivalent
    3. Check yield: f_trial = sigma_eq_trial - sigma_y(alpha_old)
    4. If f_trial <= 0: elastic — return trial stress with elastic tangent
    5. If f_trial > 0: plastic — solve for delta_lambda via Newton iteration
       f(dl) = sigma_eq_trial - 3*mu*dl - sigma_y(alpha_old + dl) = 0
    6. Update stress: S = S_vol + (1 - 3*mu*dl / sigma_eq_trial) * S_dev_trial
    7. Update alpha: alpha_new = alpha_old + delta_lambda

    Parameters
    ----------
    mat : J2PowerLawMaterial
        Material parameters.
    E_strain : NDArray
        Green-Lagrange strain tensor (3, 3).
    alpha_old : float
        Previous accumulated equivalent plastic strain.
    tol : float
        Newton convergence tolerance.
    max_iter : int
        Maximum Newton iterations for return mapping.

    Returns
    -------
    ReturnMappingResult
        Updated stress, internal variables, and algorithmic tangent.
    """
    lam = mat.lam
    mu = mat.mu

    # --- 1. Elastic trial stress (SVK-like) ---
    tr_E = float(np.trace(E_strain))
    S_trial = lam * tr_E * np.eye(3) + 2.0 * mu * E_strain

    # --- 2. Deviatoric trial and von Mises ---
    S_dev_trial = deviatoric(S_trial)
    S_vol_trial = S_trial - S_dev_trial  # volumetric part
    sigma_eq_trial = von_mises(S_dev_trial)

    # --- Von Mises near-zero guard (07-CONVENTIONS.md) ---
    sigma_y_old = yield_stress(mat, alpha_old)
    if sigma_eq_trial < 1e-12 * sigma_y_old:
        # Essentially zero deviatoric stress — elastic
        C_el = elastic_tangent(lam, mu)
        return ReturnMappingResult(
            stress=S_trial,
            alpha_new=alpha_old,
            delta_lambda=0.0,
            is_plastic=False,
            tangent=C_el,
        )

    # --- 3. Yield check ---
    f_trial = sigma_eq_trial - sigma_y_old

    if f_trial <= 0.0:
        # --- 4. Elastic: below yield ---
        C_el = elastic_tangent(lam, mu)
        return ReturnMappingResult(
            stress=S_trial,
            alpha_new=alpha_old,
            delta_lambda=0.0,
            is_plastic=False,
            tangent=C_el,
        )

    # --- 5. Plastic: Newton iteration for delta_lambda ---
    # The yield function f has units of stress (MPa). An absolute tolerance on f is only
    # reachable when f is already near machine precision in those units. Scale tol by the
    # stress reference so the effective tolerance is at least as loose as eps_rel * stress.
    stress_ref = max(abs(sigma_eq_trial), sigma_y_old, 1.0)
    effective_tol = max(tol, tol * stress_ref)
    dl = 0.0  # initial guess for delta_lambda
    f = float("inf")  # sentinel for the else clause if max_iter=0
    for _it in range(max_iter):
        alpha_trial = alpha_old + dl
        sy = yield_stress(mat, alpha_trial)
        H_prime = yield_stress_derivative(mat, alpha_trial)

        f = sigma_eq_trial - 3.0 * mu * dl - sy
        df = -3.0 * mu - H_prime

        if abs(df) < 1e-30:
            if abs(f) > effective_tol:
                raise RuntimeError(
                    f"Return mapping Newton stalled: |df| = {abs(df):.3e}, "
                    f"|f| = {abs(f):.3e}. Cannot reduce plastic residual."
                )
            break

        ddl = -f / df
        dl += ddl

        if abs(f) < effective_tol:
            break
    else:
        msg = f"Return mapping did not converge in {max_iter} iterations. |f| = {abs(f):.3e}"
        raise RuntimeError(msg)

    # Clamp tiny negative from Newton (07-CONVENTIONS.md: dl >= -1e-15)
    if dl < 0.0:
        if dl >= -1e-15:
            dl = 0.0
        else:
            msg = f"Negative plastic multiplier delta_lambda = {dl:.3e}"
            raise ValueError(msg)

    # --- 6. Update stress ---
    ratio = 3.0 * mu * dl / sigma_eq_trial
    S_updated = S_vol_trial + (1.0 - ratio) * S_dev_trial

    # --- 7. Update alpha ---
    alpha_new = alpha_old + dl

    # --- Algorithmic consistent tangent ---
    #
    # Derived from linearisation of the return map (Simo & Hughes §3.4, Box 3.5):
    #
    #   C_ep = kappa * (I x I)
    #        + 2*mu*beta * P_dev
    #        + (9*mu^2*dl/q - 9*mu^2/(3*mu+H')) * (n x n)
    #
    # where kappa = lam + 2*mu/3  (bulk modulus),
    #       beta  = 1 - 3*mu*dl/q (radial return scaling factor),
    #       q     = sigma_eq_trial,
    #       n     = S_dev_trial / q  (flow direction, norm = sqrt(2/3), not unity),
    #       H'    = d(sigma_y)/d(alpha)|_{alpha_new}.

    H_prime_final = yield_stress_derivative(mat, alpha_new)

    C_ep = assemble_j2_like_tangent(
        lam=lam,
        mu=mu,
        S_dev_trial=S_dev_trial,
        sigma_eq_trial=sigma_eq_trial,
        dl=dl,
        denominator=3.0 * mu + H_prime_final,
    )

    return ReturnMappingResult(
        stress=S_updated,
        alpha_new=alpha_new,
        delta_lambda=dl,
        is_plastic=True,
        tangent=C_ep,
    )


# ---------------------------------------------------------------------------
# ConstitutiveModel wrapper
# ---------------------------------------------------------------------------


class J2Model(ConstitutiveModel):
    """J2 plasticity wrapper implementing the ConstitutiveModel interface."""

    def __init__(self, mat: J2PowerLawMaterial) -> None:
        self._mat = mat

    def pk2_stress(self, E_strain: NDArray, **state: float) -> NDArray:
        """Return PK2 stress from radial return mapping."""
        alpha = state.get("alpha", 0.0)
        return radial_return(self._mat, E_strain, alpha).stress

    def material_tangent(self, E_strain: NDArray, **state: float) -> NDArray:
        """Return algorithmic consistent tangent (3,3,3,3)."""
        alpha = state.get("alpha", 0.0)
        return radial_return(self._mat, E_strain, alpha).tangent

    def voigt_tangent(self, E_strain: NDArray, **state: float) -> NDArray:
        """Return Voigt-form tangent (6,6) using tensorial Voigt ordering."""
        alpha = state.get("alpha", 0.0)
        C4 = radial_return(self._mat, E_strain, alpha).tangent
        return tangent_to_voigt_66(C4)

    @property
    def state_variables(self) -> tuple[str, ...]:
        return ("alpha",)

    @property
    def is_dissipative(self) -> bool:
        return True
