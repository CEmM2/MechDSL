"""Neo-Hookean (compressible, isochoric-volumetric split) constitutive model.

Strain energy (classical form, not Simo-Taylor):

    Psi = (mu/2) * (I1_bar - 3) + (kappa/2) * (J - 1)^2

where
    C       = 2*E + I                       (right Cauchy-Green from Green-Lagrange)
    J       = sqrt(det(C)) = det(F)         (Jacobian)
    I1      = tr(C)                         (first invariant)
    I1_bar  = J^(-2/3) * I1                 (isochoric first invariant)

PK2 stress  S = 2 * dPsi/dC:
    S_iso = mu * J^(-2/3) * (I - (1/3) * I1 * Cinv)
    S_vol = kappa * J * (J - 1) * Cinv
    S     = S_iso + S_vol

Material tangent  C_IJKL = 2 * dS_IJ/dC_KL = 4 * d^2 Psi/dC dC:
    Uses dCinv_IJ/dC_KL = -(1/2) * (Cinv_IK*Cinv_JL + Cinv_IL*Cinv_JK)
    and dJ/dC_KL = (J/2) * Cinv_KL.

At F = I (C = I, J = 1, I1 = 3):
    S = 0 exactly, and the tangent reduces to the isotropic linear elastic form
    with Lame constants  lam_eff = kappa - (2/3)*mu,  mu_eff = mu.

Conventions (07-CONVENTIONS.md):
- Tension-positive stress (§4)
- Voigt ordering [xx, yy, zz, xy, xz, yz], unscaled shears (§2)
- All float64
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from numpy.typing import NDArray

from mechdsl.symbolic.constitutive import ConstitutiveModel
from mechdsl.symbolic.voigt import tangent_to_voigt_66


@dataclass(frozen=True)
class NeoHookeanMaterial:
    """Neo-Hookean material parameters.

    Parameters
    ----------
    mu : float
        Shear modulus (> 0).
    kappa : float
        Bulk modulus (> 0).
    """

    mu: float
    kappa: float

    def __post_init__(self) -> None:
        if self.mu <= 0:
            raise ValueError(f"mu (shear modulus) must be > 0, got {self.mu}")
        if self.kappa <= 0:
            raise ValueError(f"kappa (bulk modulus) must be > 0, got {self.kappa}")

    @staticmethod
    def from_E_nu(E: float, nu: float) -> NeoHookeanMaterial:
        """Create from Young's modulus and Poisson's ratio.

        Uses kappa = E / (3*(1 - 2*nu)), mu = E / (2*(1 + nu)).
        """
        if E <= 0:
            raise ValueError(f"E must be > 0, got {E}")
        if not (-1 < nu < 0.5):
            raise ValueError(f"nu must be in (-1, 0.5), got {nu}")
        mu = E / (2.0 * (1.0 + nu))
        kappa = E / (3.0 * (1.0 - 2.0 * nu))
        return NeoHookeanMaterial(mu=mu, kappa=kappa)


def _right_cauchy_green(E_strain: NDArray) -> NDArray:
    """C = 2*E + I from Green-Lagrange strain E."""
    return 2.0 * E_strain + np.eye(3, dtype=np.float64)


def pk2_stress(mat: NeoHookeanMaterial, E_strain: NDArray) -> NDArray:
    """Compute PK2 stress for Neo-Hookean material.

    S = mu * J^(-2/3) * (I - (1/3) * I1 * Cinv)  +  kappa * J * (J - 1) * Cinv

    Parameters
    ----------
    mat : NeoHookeanMaterial
        Material parameters.
    E_strain : (3, 3) NDArray
        Green-Lagrange strain tensor.

    Returns
    -------
    NDArray (3, 3)
        Second Piola-Kirchhoff stress tensor S.
    """
    if E_strain.shape != (3, 3):
        msg = f"Expected (3,3) strain tensor, got {E_strain.shape}"
        raise ValueError(msg)

    C = _right_cauchy_green(E_strain)
    det_C = float(np.linalg.det(C))
    if det_C <= 0.0:
        raise ValueError(f"det(C) must be > 0 for a valid deformation, got {det_C:.3e}")
    J = float(np.sqrt(det_C))
    I1 = float(np.trace(C))
    Cinv = np.linalg.inv(C)
    eye3 = np.eye(3, dtype=np.float64)

    alpha = J ** (-2.0 / 3.0)
    S_iso = mat.mu * alpha * (eye3 - (I1 / 3.0) * Cinv)
    S_vol = mat.kappa * J * (J - 1.0) * Cinv
    return S_iso + S_vol


def material_tangent_4th(mat: NeoHookeanMaterial, E_strain: NDArray) -> NDArray:
    """Compute the 4th-order material tangent C_IJKL = 2 dS_IJ/dC_KL.

    Closed form:

        C_IJKL =
            -(2/3) * mu * alpha * (Cinv_KL * delta_IJ + delta_KL * Cinv_IJ)
            + (2/9) * mu * alpha * I1 * Cinv_KL * Cinv_IJ
            + (1/3) * mu * alpha * I1 * (Cinv_IK * Cinv_JL + Cinv_IL * Cinv_JK)
            + kappa * (2*J - 1) * J * Cinv_KL * Cinv_IJ
            - kappa * J * (J - 1) * (Cinv_IK * Cinv_JL + Cinv_IL * Cinv_JK)

    where alpha = J^(-2/3).

    Parameters
    ----------
    mat : NeoHookeanMaterial
    E_strain : (3, 3) NDArray
        Green-Lagrange strain tensor.

    Returns
    -------
    NDArray (3, 3, 3, 3)
        Major- and minor-symmetric material tangent.
    """
    if E_strain.shape != (3, 3):
        msg = f"Expected (3,3) strain tensor, got {E_strain.shape}"
        raise ValueError(msg)

    C = _right_cauchy_green(E_strain)
    det_C = float(np.linalg.det(C))
    if det_C <= 0.0:
        raise ValueError(f"det(C) must be > 0 for a valid deformation, got {det_C:.3e}")
    J = float(np.sqrt(det_C))
    I1 = float(np.trace(C))
    Cinv = np.linalg.inv(C)
    eye3 = np.eye(3, dtype=np.float64)
    alpha = J ** (-2.0 / 3.0)

    # Kronecker outer products assembled via einsum
    # term1_IJKL = Cinv_KL * delta_IJ + delta_KL * Cinv_IJ
    term_cross = np.einsum("ij,kl->ijkl", eye3, Cinv) + np.einsum("ij,kl->ijkl", Cinv, eye3)
    term_cinv2 = np.einsum("ij,kl->ijkl", Cinv, Cinv)
    # term_sym_IJKL = Cinv_IK * Cinv_JL + Cinv_IL * Cinv_JK  (minor-symmetric)
    term_sym = np.einsum("ik,jl->ijkl", Cinv, Cinv) + np.einsum("il,jk->ijkl", Cinv, Cinv)

    C_iso = (
        -(2.0 / 3.0) * mat.mu * alpha * term_cross
        + (2.0 / 9.0) * mat.mu * alpha * I1 * term_cinv2
        + (1.0 / 3.0) * mat.mu * alpha * I1 * term_sym
    )
    C_vol = mat.kappa * (2.0 * J - 1.0) * J * term_cinv2 - mat.kappa * J * (J - 1.0) * term_sym
    return C_iso + C_vol


def material_tangent_voigt(mat: NeoHookeanMaterial, E_strain: NDArray) -> NDArray:
    """Compute the 6x6 Voigt form of the Neo-Hookean material tangent."""
    return tangent_to_voigt_66(material_tangent_4th(mat, E_strain))


class NeoHookeanModel(ConstitutiveModel):
    """ConstitutiveModel wrapper for Neo-Hookean hyperelasticity."""

    def __init__(self, mat: NeoHookeanMaterial) -> None:
        self._mat = mat

    def pk2_stress(self, E_strain: NDArray, **state: float) -> NDArray:
        return pk2_stress(self._mat, E_strain)

    def material_tangent(self, E_strain: NDArray, **state: float) -> NDArray:
        return material_tangent_4th(self._mat, E_strain)

    def voigt_tangent(self, E_strain: NDArray, **state: float) -> NDArray:
        return material_tangent_voigt(self._mat, E_strain)

    @property
    def state_variables(self) -> tuple[str, ...]:
        return ()

    @property
    def is_dissipative(self) -> bool:
        return False
