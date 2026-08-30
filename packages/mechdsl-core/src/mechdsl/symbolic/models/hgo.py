"""Holzapfel-Gasser-Ogden (HGO / GOH 2006) anisotropic hyperelastic model.

Strain energy (compressible, isochoric-volumetric split + two fiber families):

    Psi_iso = (mu/2) * (I1_bar - 3)
    Psi_vol = (kappa/2) * (J - 1)^2
    Psi_fi  = (k1 / (2 * k2)) * (exp(k2 * E_fi^2) - 1)   if  E_fi > 0,  else 0
    Psi     = Psi_iso + Psi_vol + Psi_f1 + Psi_f2

with the dispersion-weighted fiber kinematic

    E_fi = kappa_disp * (I1_bar - 3) + (1 - 3 * kappa_disp) * (I4_bar_i - 1)

where I4_i = a_i · C · a_i and the overbar means isochoric (J^(-2/3) scaling).

The fiber family direction (a1, a2) is supplied per evaluation as a unit-vector
pair — the scope-level "fiber_data" array would be per-element at the IR layer;
this reference symbolic kernel takes two (3,) unit vectors directly.

PK2 stress (S = 2 dPsi/dC):

    S_iso = mu * J^(-2/3) * (I - (I1/3) * Cinv)                    (Neo-Hookean iso)
    S_vol = kappa * J * (J - 1) * Cinv
    S_fi  = 2 * k1 * E_fi * exp(k2 * E_fi^2) * dE_fi_dC             (gated on E_fi > 0)

with

    dE_fi_dC = kappa_disp * J^(-2/3) * (I - (I1/3) * Cinv)
             + (1 - 3 * kappa_disp) * J^(-2/3) * (A_i - (I4_i/3) * Cinv)

and  A_i = a_i outer a_i.

Material tangent C_IJKL = 2 dS/dC computed via central-difference FD of the
analytic PK2 stress — same pattern used in the Ogden reference implementation
(O(12) stress evaluations per point; acceptable for the reference symbolic
layer, and robust across the fiber-gating boundary).

At F = I and any admissible (a_i): I1_bar = 3, I4_bar_i = 1, E_fi = 0, J = 1;
all three stress contributions vanish.  When either fiber dispersion equals
0 (perfect alignment) or 1/3 (isotropic), the fiber pseudo-invariant reduces
to the familiar limits.

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
class HGOMaterial:
    """HGO / GOH anisotropic hyperelastic parameters.

    Parameters
    ----------
    mu : float
        Shear modulus of the isotropic Neo-Hookean matrix (> 0).
    k1 : float
        Fiber stress-like parameter (> 0).
    k2 : float
        Fiber exponential-stiffening parameter (> 0; dimensionless).
    kappa : float
        Bulk modulus (> 0).
    fiber_dispersion : float
        Gasser-Ogden-Holzapfel dispersion parameter kappa_disp in [0, 1/3].
        0 = perfectly aligned fibers; 1/3 = fully dispersed (isotropic fiber).
    """

    mu: float
    k1: float
    k2: float
    kappa: float
    fiber_dispersion: float

    def __post_init__(self) -> None:
        if self.mu <= 0:
            raise ValueError(f"mu must be > 0, got {self.mu}")
        if self.k1 <= 0:
            raise ValueError(f"k1 must be > 0, got {self.k1}")
        if self.k2 <= 0:
            raise ValueError(f"k2 must be > 0, got {self.k2}")
        if self.kappa <= 0:
            raise ValueError(f"kappa must be > 0, got {self.kappa}")
        if not (0.0 <= self.fiber_dispersion <= 1.0 / 3.0):
            raise ValueError(f"fiber_dispersion must be in [0, 1/3], got {self.fiber_dispersion}")


def _right_cauchy_green(E_strain: NDArray) -> NDArray:
    return 2.0 * E_strain + np.eye(3, dtype=np.float64)


def _unit(v: NDArray) -> NDArray:
    n = float(np.linalg.norm(v))
    if n <= 0.0:
        raise ValueError("Fiber direction must be non-zero")
    return np.asarray(v, dtype=np.float64) / n


def _fiber_contrib(
    mat: HGOMaterial,
    a: NDArray,
    C: NDArray,
    Cinv: NDArray,
    I1: float,
    J23m: float,
) -> NDArray:
    """Single-family PK2 fiber contribution; zero when E_fi <= 0."""
    A = np.outer(a, a)
    I4 = float(a @ C @ a)
    I1_bar = J23m * I1
    I4_bar = J23m * I4
    kd = mat.fiber_dispersion
    E_fi = kd * (I1_bar - 3.0) + (1.0 - 3.0 * kd) * (I4_bar - 1.0)
    if E_fi <= 0.0:
        return np.zeros((3, 3), dtype=np.float64)

    eye3 = np.eye(3, dtype=np.float64)
    dI1bar_dC = J23m * (eye3 - (I1 / 3.0) * Cinv)
    dI4bar_dC = J23m * (A - (I4 / 3.0) * Cinv)
    dE_dC = kd * dI1bar_dC + (1.0 - 3.0 * kd) * dI4bar_dC
    coeff = 2.0 * mat.k1 * E_fi * np.exp(mat.k2 * E_fi * E_fi)
    return coeff * dE_dC


def pk2_stress(mat: HGOMaterial, E_strain: NDArray, fiber_dirs: tuple[NDArray, NDArray]) -> NDArray:
    """Compute PK2 stress for the HGO material given two fiber unit vectors."""
    if E_strain.shape != (3, 3):
        msg = f"Expected (3,3) strain tensor, got {E_strain.shape}"
        raise ValueError(msg)

    a1 = _unit(fiber_dirs[0])
    a2 = _unit(fiber_dirs[1])

    C = _right_cauchy_green(E_strain)
    C = 0.5 * (C + C.T)
    detC = float(np.linalg.det(C))
    if detC <= 0.0:
        raise ValueError(f"det(C) must be > 0, got {detC:.3e}")
    J = float(np.sqrt(detC))
    Cinv = np.linalg.inv(C)
    eye3 = np.eye(3, dtype=np.float64)
    I1 = float(np.trace(C))
    J23m = J ** (-2.0 / 3.0)

    S_iso = mat.mu * J23m * (eye3 - (I1 / 3.0) * Cinv)
    S_vol = mat.kappa * J * (J - 1.0) * Cinv
    S_f1 = _fiber_contrib(mat, a1, C, Cinv, I1, J23m)
    S_f2 = _fiber_contrib(mat, a2, C, Cinv, I1, J23m)

    S = S_iso + S_vol + S_f1 + S_f2
    return 0.5 * (S + S.T)


def material_tangent_4th(
    mat: HGOMaterial, E_strain: NDArray, fiber_dirs: tuple[NDArray, NDArray]
) -> NDArray:
    """4th-order material tangent via central-difference FD of pk2_stress.

    Same 6-probe symmetric-perturbation scheme used for Ogden.  Robust across
    the fiber-gating boundary E_fi = 0 (the one-sided derivative is zero on
    the inactive side, and central-difference averages the two sides giving
    half the active-side tangent right at the boundary — acceptable since
    admissible test points avoid the exact boundary).
    """
    if E_strain.shape != (3, 3):
        msg = f"Expected (3,3) strain tensor, got {E_strain.shape}"
        raise ValueError(msg)

    eps = 1e-6
    C4 = np.zeros((3, 3, 3, 3), dtype=np.float64)
    for k in range(3):
        for ll in range(k, 3):
            dE_sym = np.zeros((3, 3), dtype=np.float64)
            if k == ll:
                dE_sym[k, k] = 1.0
            else:
                dE_sym[k, ll] = 0.5
                dE_sym[ll, k] = 0.5
            S_plus = pk2_stress(mat, E_strain + eps * dE_sym, fiber_dirs)
            S_minus = pk2_stress(mat, E_strain - eps * dE_sym, fiber_dirs)
            dS = (S_plus - S_minus) / (2.0 * eps)
            C4[:, :, k, ll] = dS
            if k != ll:
                C4[:, :, ll, k] = dS
    C4 = 0.5 * (C4 + C4.transpose(2, 3, 0, 1))
    return C4


def material_tangent_voigt(
    mat: HGOMaterial, E_strain: NDArray, fiber_dirs: tuple[NDArray, NDArray]
) -> NDArray:
    return tangent_to_voigt_66(material_tangent_4th(mat, E_strain, fiber_dirs))


class HGOModel(ConstitutiveModel):
    """ConstitutiveModel wrapper for HGO hyperelasticity.

    Fiber directions (a1, a2) are closed over at construction — they are
    per-element data in the full pipeline, so a separate wrapper instance is
    used per element.
    """

    def __init__(self, mat: HGOMaterial, fiber_dirs: tuple[NDArray, NDArray]) -> None:
        self._mat = mat
        self._fiber_dirs = (
            _unit(fiber_dirs[0]),
            _unit(fiber_dirs[1]),
        )

    def pk2_stress(self, E_strain: NDArray, **state: float) -> NDArray:
        return pk2_stress(self._mat, E_strain, self._fiber_dirs)

    def material_tangent(self, E_strain: NDArray, **state: float) -> NDArray:
        return material_tangent_4th(self._mat, E_strain, self._fiber_dirs)

    def voigt_tangent(self, E_strain: NDArray, **state: float) -> NDArray:
        return material_tangent_voigt(self._mat, E_strain, self._fiber_dirs)

    @property
    def state_variables(self) -> tuple[str, ...]:
        return ()

    @property
    def is_dissipative(self) -> bool:
        return False
