"""St. Venant-Kirchhoff (SVK) constitutive model.

Hyperelastic model with strain energy:
    Psi = (lambda / 2) * (tr E)^2 + mu * (E : E)

PK2 stress:
    S_IJ = lambda * tr(E) * delta_IJ + 2 * mu * E_IJ

Material tangent (constant, independent of strain):
    C_IJKL = lambda * delta_IJ * delta_KL + mu * (delta_IK * delta_JL + delta_IL * delta_JK)

Conventions:
- Tension-positive stress (07-CONVENTIONS.md §4)
- Voigt ordering: [xx, yy, zz, xy, xz, yz], unscaled shears (§2)
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
class SVKMaterial:
    """St. Venant-Kirchhoff material parameters (Lame constants)."""

    lam: float  # First Lame parameter (lambda)
    mu: float  # Second Lame parameter (shear modulus)

    def __post_init__(self) -> None:
        if self.mu <= 0:
            raise ValueError(f"mu (shear modulus) must be > 0, got {self.mu}")

    @staticmethod
    def from_E_nu(E: float, nu: float) -> SVKMaterial:
        """Create from Young's modulus and Poisson's ratio.

        Args:
            E: Young's modulus (> 0)
            nu: Poisson's ratio (-1 < nu < 0.5)

        Returns:
            SVKMaterial with computed Lame parameters.
        """
        if E <= 0:
            raise ValueError(f"E must be > 0, got {E}")
        if not (-1 < nu < 0.5):
            raise ValueError(f"nu must be in (-1, 0.5), got {nu}")
        lam = E * nu / ((1 + nu) * (1 - 2 * nu))
        mu = E / (2 * (1 + nu))
        return SVKMaterial(lam=lam, mu=mu)


def pk2_stress(mat: SVKMaterial, E_strain: NDArray) -> NDArray:
    """Compute PK2 stress for SVK material.

    S = lambda * tr(E) * I + 2 * mu * E

    Args:
        mat: SVK material parameters.
        E_strain: Green-Lagrange strain tensor (3x3).

    Returns:
        PK2 stress tensor S (3x3).
    """
    if E_strain.shape != (3, 3):
        msg = f"Expected (3,3) strain tensor, got {E_strain.shape}"
        raise ValueError(msg)
    eye3 = np.eye(3, dtype=np.float64)
    tr_E = np.trace(E_strain)
    S: NDArray = mat.lam * tr_E * eye3 + 2.0 * mat.mu * E_strain
    return S


def material_tangent_4th(mat: SVKMaterial) -> NDArray:
    """Compute the 4th-order material tangent for SVK.

    C_IJKL = lambda * delta_IJ * delta_KL
             + mu * (delta_IK * delta_JL + delta_IL * delta_JK)

    This tangent is constant (independent of strain state).

    Returns:
        (3,3,3,3) numpy array.
    """
    d = np.eye(3, dtype=np.float64)  # Kronecker delta
    C4 = np.zeros((3, 3, 3, 3), dtype=np.float64)
    for i in range(3):
        for j in range(3):
            for k in range(3):
                for el in range(3):  # el = l (tensor index)
                    C4[i, j, k, el] = mat.lam * d[i, j] * d[k, el] + mat.mu * (
                        d[i, k] * d[j, el] + d[i, el] * d[j, k]
                    )
    return C4


def material_tangent_voigt(mat: SVKMaterial) -> NDArray:
    """Compute the 6x6 Voigt form of SVK material tangent.

    Uses tensorial Voigt ordering [xx, yy, zz, xy, xz, yz] with unscaled shears.

    Returns:
        (6,6) numpy array.
    """
    return tangent_to_voigt_66(material_tangent_4th(mat))


class SVKModel(ConstitutiveModel):
    """ConstitutiveModel wrapper for St. Venant-Kirchhoff elasticity."""

    def __init__(self, mat: SVKMaterial) -> None:
        self._mat = mat

    def pk2_stress(self, E_strain: NDArray, **state: float) -> NDArray:
        """Delegate to standalone pk2_stress."""
        return pk2_stress(self._mat, E_strain)

    def material_tangent(self, E_strain: NDArray, **state: float) -> NDArray:
        """Delegate to standalone material_tangent_4th."""
        return material_tangent_4th(self._mat)

    def voigt_tangent(self, E_strain: NDArray, **state: float) -> NDArray:
        """Delegate to standalone material_tangent_voigt."""
        return material_tangent_voigt(self._mat)

    @property
    def state_variables(self) -> tuple[str, ...]:
        return ()

    @property
    def is_dissipative(self) -> bool:
        return False
