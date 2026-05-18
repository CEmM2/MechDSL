"""Mooney-Rivlin (compressible, two-invariant isochoric-volumetric split) model.

Strain energy:

    Psi = C1 * (I1_bar - 3) + C2 * (I2_bar - 3) + (kappa/2) * (J - 1)^2

where
    C         = 2*E + I
    J         = sqrt(det(C)) = det(F)
    I1        = tr(C)
    I2        = (1/2) * (I1^2 - tr(C*C))     = tr(C)^2/2 - tr(C^2)/2
    I1_bar    = J^(-2/3) * I1
    I2_bar    = J^(-4/3) * I2

PK2 stress  S = 2 * dPsi/dC:

    S = S_iso1 + S_iso2 + S_vol

    S_iso1 = 2*C1 * alpha * (I - (I1/3) * Cinv)               [alpha = J^(-2/3)]
    S_iso2 = 2*C2 * beta  * (I1*I - C - (2/3)*I2*Cinv)        [beta  = J^(-4/3)]
    S_vol  = kappa * J * (J - 1) * Cinv

Reduces exactly to Neo-Hookean with mu = 2*C1 when C2 = 0.

Material tangent  C_IJKL = 2 * dS_IJ/dC_KL:
Split into three additive contributions C1_tangent + C2_tangent + C_vol.
Derived analytically using
    dCinv_IJ/dC_KL = -(1/2)*(Cinv_IK*Cinv_JL + Cinv_IL*Cinv_JK)
    dJ/dC_KL       = (J/2) * Cinv_KL
    dI1/dC_KL      = delta_KL
    dI2/dC_KL      = I1*delta_KL - C_KL
    dC_IJ/dC_KL    = (1/2)*(delta_IK*delta_JL + delta_IL*delta_JK)   (minor-sym)
    d(J^(-2/3))/dC = -(1/3) * J^(-2/3) * Cinv
    d(J^(-4/3))/dC = -(2/3) * J^(-4/3) * Cinv

At F = I (C = I, J = 1, I1 = I2 = 3):
    S = 0, and the tangent reduces to the isotropic linear-elastic form with
    mu_eff = 2*(C1 + C2) and lam_eff = kappa - (2/3) * mu_eff.

Conventions (07-CONVENTIONS.md):
- Tension-positive stress
- Voigt ordering [xx, yy, zz, xy, xz, yz], unscaled shears
- float64
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
class MooneyRivlinMaterial:
    """Mooney-Rivlin material parameters.

    Parameters
    ----------
    C1, C2 : float
        Material constants (> 0 for C1; C2 >= 0 allowed, >= 0 by convention).
    kappa : float
        Bulk modulus (> 0).
    """

    C1: float
    C2: float
    kappa: float

    def __post_init__(self) -> None:
        if self.C1 <= 0:
            raise ValueError(f"C1 must be > 0, got {self.C1}")
        if self.C2 < 0:
            raise ValueError(f"C2 must be >= 0, got {self.C2}")
        if self.kappa <= 0:
            raise ValueError(f"kappa (bulk modulus) must be > 0, got {self.kappa}")


def _right_cauchy_green(E_strain: NDArray) -> NDArray:
    return 2.0 * E_strain + np.eye(3, dtype=np.float64)


def _kinematics(E_strain: NDArray) -> tuple[NDArray, float, float, float, NDArray]:
    if E_strain.shape != (3, 3):
        msg = f"Expected (3,3) strain tensor, got {E_strain.shape}"
        raise ValueError(msg)
    C = _right_cauchy_green(E_strain)
    det_C = float(np.linalg.det(C))
    if det_C <= 0.0:
        raise ValueError(f"det(C) must be > 0 for a valid deformation, got {det_C:.3e}")
    J = float(np.sqrt(det_C))
    I1 = float(np.trace(C))
    # I2 = 0.5 * (I1^2 - tr(C @ C))
    I2 = 0.5 * (I1 * I1 - float(np.trace(C @ C)))
    Cinv = np.linalg.inv(C)
    return C, J, I1, I2, Cinv


def pk2_stress(mat: MooneyRivlinMaterial, E_strain: NDArray) -> NDArray:
    """PK2 stress for Mooney-Rivlin.

    S = 2*C1*J^(-2/3) * (I - (I1/3) Cinv)
        + 2*C2*J^(-4/3) * (I1*I - C - (2/3) I2 Cinv)
        + kappa*J*(J-1) Cinv
    """
    C, J, I1, I2, Cinv = _kinematics(E_strain)
    eye3 = np.eye(3, dtype=np.float64)
    alpha = J ** (-2.0 / 3.0)
    beta = J ** (-4.0 / 3.0)

    S_iso1 = 2.0 * mat.C1 * alpha * (eye3 - (I1 / 3.0) * Cinv)
    S_iso2 = 2.0 * mat.C2 * beta * (I1 * eye3 - C - (2.0 / 3.0) * I2 * Cinv)
    S_vol = mat.kappa * J * (J - 1.0) * Cinv
    return S_iso1 + S_iso2 + S_vol


def material_tangent_4th(mat: MooneyRivlinMaterial, E_strain: NDArray) -> NDArray:
    """4th-order material tangent C_IJKL = 2 dS_IJ/dC_KL.

    Additive split: C = C1_tangent + C2_tangent + C_vol.

    C1_tangent (same structure as Neo-Hookean iso with mu -> 2*C1):
        -(2/3)*2*C1*alpha * (Cinv_KL*delta_IJ + delta_KL*Cinv_IJ)
        + (2/9)*2*C1*alpha*I1 * Cinv_IJ*Cinv_KL
        + (1/3)*2*C1*alpha*I1 * (Cinv_IK*Cinv_JL + Cinv_IL*Cinv_JK)

    C2_tangent = 4*C2*beta * {
            -(2*I1/3)*(Cinv_KL*delta_IJ + delta_KL*Cinv_IJ)
            + (2/3)*(Cinv_KL*C_IJ + C_KL*Cinv_IJ)
            + (4*I2/9)*Cinv_IJ*Cinv_KL
            + delta_IJ*delta_KL
            - (1/2)*(delta_IK*delta_JL + delta_IL*delta_JK)
            + (I2/3)*(Cinv_IK*Cinv_JL + Cinv_IL*Cinv_JK)
          }

    C_vol:
        kappa*(2J-1)*J * Cinv_IJ*Cinv_KL
        - kappa*J*(J-1) * (Cinv_IK*Cinv_JL + Cinv_IL*Cinv_JK)
    """
    C, J, I1, I2, Cinv = _kinematics(E_strain)
    eye3 = np.eye(3, dtype=np.float64)
    alpha = J ** (-2.0 / 3.0)
    beta = J ** (-4.0 / 3.0)

    # Building blocks
    # delta_IJ*delta_KL
    II = np.einsum("ij,kl->ijkl", eye3, eye3)
    # minor-symmetric identity: (1/2)(delta_IK*delta_JL + delta_IL*delta_JK)
    I_sym = 0.5 * (np.einsum("ik,jl->ijkl", eye3, eye3) + np.einsum("il,jk->ijkl", eye3, eye3))
    # Cinv_KL*delta_IJ + delta_KL*Cinv_IJ
    cross_cinv_eye = np.einsum("ij,kl->ijkl", eye3, Cinv) + np.einsum("ij,kl->ijkl", Cinv, eye3)
    # Cinv_IJ*Cinv_KL
    cinv2 = np.einsum("ij,kl->ijkl", Cinv, Cinv)
    # Cinv_IK*Cinv_JL + Cinv_IL*Cinv_JK  (minor-symmetric in IJ, KL and major-symmetric)
    cinv_sym = np.einsum("ik,jl->ijkl", Cinv, Cinv) + np.einsum("il,jk->ijkl", Cinv, Cinv)
    # Cinv_KL*C_IJ + C_KL*Cinv_IJ
    cross_cinv_C = np.einsum("ij,kl->ijkl", C, Cinv) + np.einsum("ij,kl->ijkl", Cinv, C)

    # --- C1 contribution (Neo-Hookean iso with mu = 2*C1) ---
    C1_t = (
        -(2.0 / 3.0) * 2.0 * mat.C1 * alpha * cross_cinv_eye
        + (2.0 / 9.0) * 2.0 * mat.C1 * alpha * I1 * cinv2
        + (1.0 / 3.0) * 2.0 * mat.C1 * alpha * I1 * cinv_sym
    )

    # --- C2 contribution ---
    C2_t = (
        4.0
        * mat.C2
        * beta
        * (
            -(2.0 * I1 / 3.0) * cross_cinv_eye
            + (2.0 / 3.0) * cross_cinv_C
            + (4.0 * I2 / 9.0) * cinv2
            + II
            - I_sym
            + (I2 / 3.0) * cinv_sym
        )
    )

    # --- Volumetric ---
    C_vol = mat.kappa * (2.0 * J - 1.0) * J * cinv2 - mat.kappa * J * (J - 1.0) * cinv_sym

    return C1_t + C2_t + C_vol


def material_tangent_voigt(mat: MooneyRivlinMaterial, E_strain: NDArray) -> NDArray:
    return tangent_to_voigt_66(material_tangent_4th(mat, E_strain))


class MooneyRivlinModel(ConstitutiveModel):
    """ConstitutiveModel wrapper for Mooney-Rivlin hyperelasticity."""

    def __init__(self, mat: MooneyRivlinMaterial) -> None:
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
