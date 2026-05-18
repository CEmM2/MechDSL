"""Ogden (compressible, spectral-stretch, isochoric-volumetric split) model.

Strain energy (N-term Ogden with decoupled volumetric part):

    Psi_iso = sum_p (mu_p / alpha_p) * (lambda_bar_1^alpha_p + lambda_bar_2^alpha_p
                                         + lambda_bar_3^alpha_p - 3)
    Psi_vol = (kappa / 2) * (J - 1)^2
    Psi     = Psi_iso + Psi_vol

where lambda_i are the principal stretches (square roots of the C eigenvalues)
and lambda_bar_i = J^(-1/3) * lambda_i are the isochoric principal stretches.
J = lambda_1 * lambda_2 * lambda_3.

PK2 stress via the spectral form.  Let e_i = lambda_i^2 be the C eigenvalues
and N_i the corresponding unit eigenvectors (from `numpy.linalg.eigh`). Then
C = sum_i e_i * M_i with M_i = N_i (x) N_i. The principal Kirchhoff stresses
are

    tau_iso_i = sum_p mu_p * (lambda_bar_i^alpha_p
                              - (1/3) * sum_k lambda_bar_k^alpha_p)
    tau_vol_i = kappa * J * (J - 1)                    (isotropic; same on all axes)

and the principal PK2 stresses follow from the pull-back

    S_i = (tau_iso_i + tau_vol_i) / e_i

so S = sum_i S_i * M_i. This form has NO eigenvalue-difference denominators,
so it is robust under repeated eigenvalues — when e_i = e_j, tau_i = tau_j in
the degenerate subspace and the eigenvector ambiguity cancels in M_i + M_j =
projector onto the repeated subspace (spectral-decomposition invariance).

Material tangent C_IJKL = 2 * dS/dC.  The closed-form spectral tangent
contains a `1/(e_b - e_a)` term that diverges at repeated eigenvalues (the
Holzapfel L'Hopital limit in Ch 6.5 handles this, but introduces its own
branch conditions and numerical sensitivity). We instead compute the tangent
via central-difference FD of the analytical spectral stress with respect to
C, which yields a fully-correct consistent tangent without any 0/0 handling:

    C_IJKL ~= [S_IJ(C + eps * dC_KL_sym) - S_IJ(C - eps * dC_KL_sym)] / (2 * eps)

This is O(12 stress evaluations) per point — acceptable for the reference
symbolic layer. The alternative spectral-tangent closed form with L'Hopital
remains available should a user need an analytical form; see
`dev/tasks/PLAN-B/gates/phase_4_gates.md` for the rationale.

At F = I, S = 0 (lambda_i = 1, lambda_bar_i = 1, tau_iso = 0, J = 1, tau_vol = 0).
The N = 1, alpha_1 = 2 case reduces to Neo-Hookean with mu = mu_1.

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
class OgdenMaterial:
    """Ogden material parameters.

    Parameters
    ----------
    mus : tuple[float, ...]
        Shear-modulus-like coefficients (length N, must satisfy sum > 0).
    alphas : tuple[float, ...]
        Exponents (length N, nonzero).
    kappa : float
        Bulk modulus (> 0).
    """

    mus: tuple[float, ...]
    alphas: tuple[float, ...]
    kappa: float

    def __post_init__(self) -> None:
        if len(self.mus) != len(self.alphas):
            raise ValueError(
                f"mus and alphas must have equal length, got {len(self.mus)} and {len(self.alphas)}"
            )
        if len(self.mus) == 0:
            raise ValueError("Ogden model requires at least one term (N >= 1)")
        for k, a in enumerate(self.alphas):
            if a == 0.0:
                raise ValueError(f"alphas[{k}] must be nonzero")
        if self.kappa <= 0:
            raise ValueError(f"kappa (bulk modulus) must be > 0, got {self.kappa}")

    @property
    def N(self) -> int:
        return len(self.mus)


def _right_cauchy_green(E_strain: NDArray) -> NDArray:
    return 2.0 * E_strain + np.eye(3, dtype=np.float64)


def _principal_stresses(
    e_vals: NDArray, mus: tuple[float, ...], alphas: tuple[float, ...], kappa: float
) -> tuple[NDArray, float]:
    """Return principal PK2 stresses S_i and J, given the C eigenvalues e_i = lambda_i^2."""
    # Guard against negative eigenvalues (numerical noise near zero)
    e_safe = np.maximum(e_vals, 1e-300)
    lam = np.sqrt(e_safe)
    J = float(lam[0] * lam[1] * lam[2])
    if J <= 0.0:
        raise ValueError(f"J must be > 0 for a valid deformation, got {J:.3e}")

    J_m13 = J ** (-1.0 / 3.0)
    lam_bar = J_m13 * lam  # length-3 isochoric principal stretches

    tau_iso = np.zeros(3, dtype=np.float64)
    for mu_p, alpha_p in zip(mus, alphas, strict=True):
        lb_a = lam_bar**alpha_p  # (3,)
        mean_lb_a = float(lb_a.sum()) / 3.0
        tau_iso += mu_p * (lb_a - mean_lb_a)

    tau_vol = kappa * J * (J - 1.0)
    # S_i = (tau_iso_i + tau_vol) / e_i
    S_prin = (tau_iso + tau_vol) / e_safe
    return S_prin, J


def pk2_stress(mat: OgdenMaterial, E_strain: NDArray) -> NDArray:
    """Compute PK2 stress for the Ogden material via spectral reassembly."""
    if E_strain.shape != (3, 3):
        msg = f"Expected (3,3) strain tensor, got {E_strain.shape}"
        raise ValueError(msg)

    C = _right_cauchy_green(E_strain)
    # Symmetrise to hedge against accumulated asymmetry in E_strain
    C_sym = 0.5 * (C + C.T)
    e_vals, N_vecs = np.linalg.eigh(C_sym)  # ascending eigenvalues, orthonormal N_vecs
    if float(e_vals.min()) <= 0.0:
        raise ValueError(
            f"C must be positive-definite for a valid deformation, got min(e)={e_vals.min():.3e}"
        )

    S_prin, _J = _principal_stresses(e_vals, mat.mus, mat.alphas, mat.kappa)

    # S = sum_i S_prin_i * (N_i outer N_i)
    # N_vecs columns are the eigenvectors.
    S = np.zeros((3, 3), dtype=np.float64)
    for i in range(3):
        Ni = N_vecs[:, i]
        S += S_prin[i] * np.outer(Ni, Ni)
    # Force symmetric output (any asymmetry is numerical noise)
    return 0.5 * (S + S.T)


def material_tangent_4th(mat: OgdenMaterial, E_strain: NDArray) -> NDArray:
    """4th-order material tangent via central-difference FD of pk2_stress.

    The tangent is C_IJKL = 2 * dS_IJ/dC_KL = dS_IJ/dE_KL (since dC = 2 dE).
    Central-difference FD with a unit symmetric perturbation dE_sym gives
    dS_IJ = C_IJKL * dE_sym_KL, and we reconstruct C_IJKL by probing the
    six independent symmetric directions (K <= L) and folding via minor
    symmetry C_IJKL = C_IJLK.
    """
    if E_strain.shape != (3, 3):
        msg = f"Expected (3,3) strain tensor, got {E_strain.shape}"
        raise ValueError(msg)

    eps = 1e-6
    C4 = np.zeros((3, 3, 3, 3), dtype=np.float64)

    # Probe the 6 independent symmetric directions, and use minor symmetry
    # to fill the full tensor. For each (k, ll) with k <= ll we perturb E
    # along dE_sym = 0.5*(e_kl + e_lk) (or e_kk when k==ll), so the contraction
    # dS_IJ = C_IJKL * dE_sym_KL yields C_IJkl directly (minor symmetry folds
    # C_IJkl and C_IJlk together with equal 0.5 weights).
    for k in range(3):
        for ll in range(k, 3):
            dE_sym = np.zeros((3, 3), dtype=np.float64)
            if k == ll:
                dE_sym[k, k] = 1.0
            else:
                dE_sym[k, ll] = 0.5
                dE_sym[ll, k] = 0.5
            S_plus = pk2_stress(mat, E_strain + eps * dE_sym)
            S_minus = pk2_stress(mat, E_strain - eps * dE_sym)
            dS = (S_plus - S_minus) / (2.0 * eps)
            C4[:, :, k, ll] = dS
            if k != ll:
                C4[:, :, ll, k] = dS

    # Enforce major symmetry by averaging (only cosmetic for FD noise).
    C4 = 0.5 * (C4 + C4.transpose(2, 3, 0, 1))
    return C4


def material_tangent_voigt(mat: OgdenMaterial, E_strain: NDArray) -> NDArray:
    return tangent_to_voigt_66(material_tangent_4th(mat, E_strain))


class OgdenModel(ConstitutiveModel):
    """ConstitutiveModel wrapper for Ogden hyperelasticity."""

    def __init__(self, mat: OgdenMaterial) -> None:
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
