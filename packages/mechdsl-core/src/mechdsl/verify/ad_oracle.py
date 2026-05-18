"""AD oracle: finite-difference verification of constitutive models.

Verifies constitutive models by comparing:
1. Model stress output vs numerically differentiated strain energy
2. Model tangent output vs numerically differentiated stress

Uses central finite differences (O(h^2) accurate) rather than torch autodiff
to keep verify dependency-free for core testing.

Conventions (from 07-CONVENTIONS.md):
- All float64
- Tension-positive stress
- Green-Lagrange strain E, PK2 stress S
- S_IJ = dW/dE_IJ, C_IJKL = dS_IJ/dE_KL
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from collections.abc import Callable

    from numpy.typing import NDArray

from mechdsl.lib.tensor_ops import det_33, green_lagrange
from mechdsl.symbolic.models.hgo import HGOMaterial
from mechdsl.symbolic.models.hgo import pk2_stress as hgo_pk2_stress
from mechdsl.symbolic.models.j2_power_law import J2PowerLawMaterial, radial_return
from mechdsl.symbolic.models.mooney_rivlin import MooneyRivlinMaterial
from mechdsl.symbolic.models.mooney_rivlin import pk2_stress as mr_pk2_stress
from mechdsl.symbolic.models.neo_hookean import NeoHookeanMaterial
from mechdsl.symbolic.models.neo_hookean import pk2_stress as nh_pk2_stress
from mechdsl.symbolic.models.ogden import OgdenMaterial
from mechdsl.symbolic.models.ogden import pk2_stress as ogden_pk2_stress
from mechdsl.symbolic.models.svk import SVKMaterial, material_tangent_4th, pk2_stress


def generate_random_deformation(rng: np.random.Generator) -> NDArray:
    """Generate a random deformation gradient F with J > 0 (physical).

    Uses F = I + eps * R where R is random and eps is chosen small enough
    that J = det(F) > 0. Retries with smaller eps if needed.

    Args:
        rng: NumPy random generator instance.

    Returns:
        (3,3) deformation gradient with det(F) > 0.
    """
    R = rng.standard_normal((3, 3))
    eps = 0.3
    for _ in range(20):
        F = np.eye(3, dtype=np.float64) + eps * R
        J = det_33(F)
        if J > 0.0:
            return F
        eps *= 0.5

    # Fallback: very small perturbation guaranteed to have J > 0
    F = np.eye(3, dtype=np.float64) + 1e-4 * R  # pragma: no cover
    return F  # pragma: no cover


def fd_stress_from_energy(
    energy_fn: Callable[[NDArray], float],
    E_strain: NDArray,
    h: float = 1e-7,
) -> NDArray:
    """Compute stress via finite differences of a strain energy function.

    S_IJ = dW/dE_IJ using central differences. Each (I,J) component is
    perturbed independently. Since E is symmetric, the result is symmetrised
    afterwards: S_sym = 0.5 * (S_raw + S_raw^T).

    Args:
        energy_fn: Maps a (3,3) strain tensor to a scalar energy.
        E_strain: Green-Lagrange strain tensor (3,3).
        h: Finite difference step size.

    Returns:
        (3,3) PK2 stress tensor (symmetric).
    """
    S_raw = np.zeros((3, 3), dtype=np.float64)
    for ii in range(3):
        for jj in range(3):
            E_plus = E_strain.copy()
            E_minus = E_strain.copy()
            E_plus[ii, jj] += h
            E_minus[ii, jj] -= h

            S_raw[ii, jj] = (energy_fn(E_plus) - energy_fn(E_minus)) / (2.0 * h)

    # Symmetrise: for a symmetric energy function W(E) = W(E^T),
    # the raw partials already satisfy S_IJ = S_JI, but symmetrising
    # removes any floating-point asymmetry.
    return 0.5 * (S_raw + S_raw.T)


def fd_tangent_from_stress(
    stress_fn: Callable[[NDArray], NDArray],
    E_strain: NDArray,
    h: float = 1e-7,
) -> NDArray:
    """Compute 4th-order tangent via finite differences of stress function.

    C_IJKL = dS_IJ/dE_KL using central differences with symmetric
    perturbation that respects the minor symmetry of E (perturb (K,L) and
    (L,K) together).

    Args:
        stress_fn: Maps a (3,3) strain tensor to a (3,3) stress tensor.
        E_strain: Green-Lagrange strain tensor (3,3).
        h: Finite difference step size.

    Returns:
        (3,3,3,3) material tangent tensor.
    """
    C4 = np.zeros((3, 3, 3, 3), dtype=np.float64)
    for K in range(3):
        for L in range(3):
            # Symmetric perturbation in the (K, L) direction
            dE = np.zeros((3, 3), dtype=np.float64)
            dE[K, L] = 1.0
            dE_sym = 0.5 * (dE + dE.T)

            E_plus = E_strain + h * dE_sym
            E_minus = E_strain - h * dE_sym

            S_plus = stress_fn(E_plus)
            S_minus = stress_fn(E_minus)

            C4[:, :, K, L] = (S_plus - S_minus) / (2.0 * h)

    return C4


def _svk_energy(mat: SVKMaterial, E_strain: NDArray) -> float:
    """SVK strain energy: W = (lambda/2) * tr(E)^2 + mu * tr(E^2).

    Args:
        mat: SVK material parameters.
        E_strain: Green-Lagrange strain tensor (3,3).

    Returns:
        Scalar strain energy density.
    """
    tr_E = np.trace(E_strain)
    tr_E2 = np.trace(E_strain @ E_strain)
    return float(0.5 * mat.lam * tr_E**2 + mat.mu * tr_E2)


def verify_svk(
    mat_params: dict,
    n_samples: int = 100,
    seed: int = 42,
) -> dict:
    """Verify SVK model: stress and tangent vs FD oracle.

    For each random deformation state:
    1. Compute E = green_lagrange(F)
    2. Compare pk2_stress(mat, E) vs fd_stress_from_energy(svk_energy, E)
    3. Compare material_tangent_4th(mat) vs fd_tangent_from_stress(pk2_stress, E)

    Args:
        mat_params: Dictionary with 'lam' and 'mu', or 'E' and 'nu'.
        n_samples: Number of random deformation states to test.
        seed: RNG seed for reproducibility.

    Returns:
        Dictionary with:
            max_stress_error: Maximum relative stress error across all samples.
            max_tangent_error: Maximum relative tangent error across all samples.
            all_passed: True if all errors below tolerance (1e-6).
    """
    if "E" in mat_params and "nu" in mat_params:
        mat = SVKMaterial.from_E_nu(mat_params["E"], mat_params["nu"])
    else:
        mat = SVKMaterial(lam=mat_params["lam"], mu=mat_params["mu"])

    rng = np.random.default_rng(seed)

    tol = 1e-6
    max_stress_err = 0.0
    max_tangent_err = 0.0

    C4_analytical = material_tangent_4th(mat)

    for _ in range(n_samples):
        F = generate_random_deformation(rng)
        E = green_lagrange(F)

        # --- Stress verification ---
        S_model = pk2_stress(mat, E)
        S_fd = fd_stress_from_energy(lambda e: _svk_energy(mat, e), E)

        S_norm = float(np.linalg.norm(S_model))
        if S_norm > 1e-15:
            stress_err = float(np.linalg.norm(S_model - S_fd)) / S_norm
        else:
            stress_err = float(np.linalg.norm(S_model - S_fd))
        max_stress_err = max(max_stress_err, stress_err)

        # --- Tangent verification ---
        C4_fd = fd_tangent_from_stress(lambda e: pk2_stress(mat, e), E)

        C_norm = float(np.linalg.norm(C4_analytical))
        if C_norm > 1e-15:
            tangent_err = float(np.linalg.norm(C4_analytical - C4_fd)) / C_norm
        else:
            tangent_err = float(np.linalg.norm(C4_analytical - C4_fd))  # pragma: no cover
        max_tangent_err = max(max_tangent_err, tangent_err)

    return {
        "max_stress_error": max_stress_err,
        "max_tangent_error": max_tangent_err,
        "all_passed": bool(max_stress_err < tol and max_tangent_err < tol),
    }


def verify_j2_elastic_branch(
    mat_params: dict,
    n_samples: int = 100,
    seed: int = 42,
) -> dict:
    """Verify J2 model elastic branch: stress matches SVK for below-yield strains.

    Generates small random deformation states that stay below yield and
    verifies that J2 radial_return produces the same stress as the SVK
    elastic formula.

    Args:
        mat_params: Dictionary with 'E', 'nu', 'sigma_y0', 'K', 'n'.
        n_samples: Number of random deformation states to test.
        seed: RNG seed for reproducibility.

    Returns:
        Dictionary with:
            max_stress_error: Maximum relative stress error across all samples.
            all_passed: True if all errors below tolerance (1e-6).
    """
    j2_mat = J2PowerLawMaterial(
        E=mat_params["E"],
        nu=mat_params["nu"],
        sigma_y0=mat_params["sigma_y0"],
        K=mat_params["K"],
        n=mat_params["n"],
    )
    svk_mat = SVKMaterial(lam=j2_mat.lam, mu=j2_mat.mu)

    rng = np.random.default_rng(seed)

    tol = 1e-6
    max_stress_err = 0.0

    # Scale factor to keep strains well below yield.
    # sigma_y0 / (2*mu) gives an approximate yield strain; use a fraction of it.
    scale = mat_params["sigma_y0"] / (6.0 * j2_mat.mu) * 0.1

    for _ in range(n_samples):
        # Small random symmetric strain — guaranteed below yield
        R = rng.standard_normal((3, 3))
        E_strain = scale * 0.5 * (R + R.T)

        # J2 stress from radial return
        result = radial_return(j2_mat, E_strain, alpha_old=0.0)
        S_j2 = result.stress

        # SVK stress (should match in elastic regime)
        S_svk = pk2_stress(svk_mat, E_strain)

        S_norm = float(np.linalg.norm(S_svk))
        if S_norm > 1e-15:
            err = float(np.linalg.norm(S_j2 - S_svk)) / S_norm
        else:
            err = float(np.linalg.norm(S_j2 - S_svk))
        max_stress_err = max(max_stress_err, err)

    return {
        "max_stress_error": max_stress_err,
        "all_passed": bool(max_stress_err < tol),
    }


# ---------------------------------------------------------------------------
# Hyperelastic strain-energy functions (P4-5 AD oracle)
# ---------------------------------------------------------------------------
#
# Each returns Psi(E) so FD central-differences recover PK2 via S = dPsi/dE.
# Tolerance is FD-limited: central-difference on double-precision with h=1e-7
# gives O(eps_machine/h) ~ 1e-9 roundoff + O(h^2) ~ 1e-14 truncation, so the
# attainable relative error is ~1e-6. We use tol=1e-6 matching verify_svk.


def _nh_energy(mat: NeoHookeanMaterial, E_strain: NDArray) -> float:
    C = 2.0 * E_strain + np.eye(3, dtype=np.float64)
    C = 0.5 * (C + C.T)
    detC = float(np.linalg.det(C))
    J = float(np.sqrt(detC))
    I1 = float(np.trace(C))
    I1_bar = J ** (-2.0 / 3.0) * I1
    return float(0.5 * mat.mu * (I1_bar - 3.0) + 0.5 * mat.kappa * (J - 1.0) ** 2)


def _mr_energy(mat: MooneyRivlinMaterial, E_strain: NDArray) -> float:
    C = 2.0 * E_strain + np.eye(3, dtype=np.float64)
    C = 0.5 * (C + C.T)
    detC = float(np.linalg.det(C))
    J = float(np.sqrt(detC))
    I1 = float(np.trace(C))
    I2 = float(0.5 * (I1**2 - np.trace(C @ C)))
    I1_bar = J ** (-2.0 / 3.0) * I1
    I2_bar = J ** (-4.0 / 3.0) * I2
    return float(
        mat.C1 * (I1_bar - 3.0) + mat.C2 * (I2_bar - 3.0) + 0.5 * mat.kappa * (J - 1.0) ** 2
    )


def _ogden_energy(mat: OgdenMaterial, E_strain: NDArray) -> float:
    C = 2.0 * E_strain + np.eye(3, dtype=np.float64)
    C = 0.5 * (C + C.T)
    e_vals = np.linalg.eigvalsh(C)
    e_safe = np.maximum(e_vals, 1e-300)
    lam = np.sqrt(e_safe)
    J = float(lam[0] * lam[1] * lam[2])
    lam_bar = (J ** (-1.0 / 3.0)) * lam
    psi_iso = 0.0
    for mu_p, alpha_p in zip(mat.mus, mat.alphas, strict=True):
        psi_iso += (mu_p / alpha_p) * (
            lam_bar[0] ** alpha_p + lam_bar[1] ** alpha_p + lam_bar[2] ** alpha_p - 3.0
        )
    psi_vol = 0.5 * mat.kappa * (J - 1.0) ** 2
    return float(psi_iso + psi_vol)


def _hgo_energy(mat: HGOMaterial, E_strain: NDArray, fiber_dirs: tuple[NDArray, NDArray]) -> float:
    C = 2.0 * E_strain + np.eye(3, dtype=np.float64)
    C = 0.5 * (C + C.T)
    detC = float(np.linalg.det(C))
    J = float(np.sqrt(detC))
    I1 = float(np.trace(C))
    J23m = J ** (-2.0 / 3.0)
    I1_bar = J23m * I1
    psi = 0.5 * mat.mu * (I1_bar - 3.0) + 0.5 * mat.kappa * (J - 1.0) ** 2
    kd = mat.fiber_dispersion
    for a_raw in fiber_dirs:
        a = np.asarray(a_raw, dtype=np.float64)
        a = a / float(np.linalg.norm(a))
        I4 = float(a @ C @ a)
        I4_bar = J23m * I4
        E_fi = kd * (I1_bar - 3.0) + (1.0 - 3.0 * kd) * (I4_bar - 1.0)
        if E_fi > 0.0:
            psi += (mat.k1 / (2.0 * mat.k2)) * (np.exp(mat.k2 * E_fi * E_fi) - 1.0)
    return float(psi)


def _rel_err(a: NDArray, b: NDArray) -> float:
    b_norm = float(np.linalg.norm(b))
    if b_norm < 1e-15:
        return float(np.linalg.norm(a - b))
    return float(np.linalg.norm(a - b)) / b_norm


def verify_neo_hookean(
    mat_params: dict, n_samples: int = 100, seed: int = 42, tol: float = 1e-6
) -> dict:
    """FD-of-Psi oracle for Neo-Hookean: verifies pk2_stress vs d(_nh_energy)/dE."""
    if "E" in mat_params and "nu" in mat_params:
        mat = NeoHookeanMaterial.from_E_nu(mat_params["E"], mat_params["nu"])
    else:
        mat = NeoHookeanMaterial(mu=mat_params["mu"], kappa=mat_params["kappa"])
    rng = np.random.default_rng(seed)
    max_err = 0.0
    for _ in range(n_samples):
        F = generate_random_deformation(rng)
        E = green_lagrange(F)
        S_model = nh_pk2_stress(mat, E)
        S_fd = fd_stress_from_energy(lambda e: _nh_energy(mat, e), E)
        max_err = max(max_err, _rel_err(S_model, S_fd))
    return {"max_stress_error": max_err, "n_samples": n_samples, "all_passed": bool(max_err < tol)}


def verify_mooney_rivlin(
    mat_params: dict, n_samples: int = 100, seed: int = 42, tol: float = 1e-6
) -> dict:
    """FD-of-Psi oracle for Mooney-Rivlin: verifies pk2_stress vs d(_mr_energy)/dE."""
    mat = MooneyRivlinMaterial(C1=mat_params["C1"], C2=mat_params["C2"], kappa=mat_params["kappa"])
    rng = np.random.default_rng(seed)
    max_err = 0.0
    for _ in range(n_samples):
        F = generate_random_deformation(rng)
        E = green_lagrange(F)
        S_model = mr_pk2_stress(mat, E)
        S_fd = fd_stress_from_energy(lambda e: _mr_energy(mat, e), E)
        max_err = max(max_err, _rel_err(S_model, S_fd))
    return {"max_stress_error": max_err, "n_samples": n_samples, "all_passed": bool(max_err < tol)}


def verify_ogden(
    mat_params: dict,
    n_samples: int = 100,
    seed: int = 42,
    tol: float = 1e-6,
    eig_sep_cutoff: float = 1e-4,
) -> dict:
    """FD-of-Psi oracle for Ogden.

    Skips deformation states whose C eigenvalues are within ``eig_sep_cutoff``
    of each other — the spectral PK2 formula is continuous there but FD of
    eigenvalue-dependent energies is ill-conditioned. Documented exclusion
    per task risk note.
    """
    mat = OgdenMaterial(
        mus=tuple(mat_params["mus"]),
        alphas=tuple(mat_params["alphas"]),
        kappa=mat_params["kappa"],
    )
    rng = np.random.default_rng(seed)
    max_err = 0.0
    n_used = 0
    n_skipped = 0
    attempts = 0
    while n_used < n_samples and attempts < 10 * n_samples:
        attempts += 1
        F = generate_random_deformation(rng)
        E = green_lagrange(F)
        C = 2.0 * E + np.eye(3)
        e_vals = np.linalg.eigvalsh(0.5 * (C + C.T))
        # separation of all pairs
        sep = min(
            abs(e_vals[0] - e_vals[1]), abs(e_vals[1] - e_vals[2]), abs(e_vals[0] - e_vals[2])
        )
        if sep < eig_sep_cutoff:
            n_skipped += 1
            continue
        S_model = ogden_pk2_stress(mat, E)
        S_fd = fd_stress_from_energy(lambda e: _ogden_energy(mat, e), E, h=1e-6)
        max_err = max(max_err, _rel_err(S_model, S_fd))
        n_used += 1
    return {
        "max_stress_error": max_err,
        "n_samples": n_used,
        "n_skipped_near_degenerate": n_skipped,
        "all_passed": bool(n_used >= n_samples and max_err < tol),
    }


def verify_hgo(
    mat_params: dict,
    n_samples: int = 100,
    seed: int = 42,
    tol: float = 1e-6,
) -> dict:
    """FD-of-Psi oracle for HGO with random unit fiber directions per sample."""
    mat = HGOMaterial(
        mu=mat_params["mu"],
        k1=mat_params["k1"],
        k2=mat_params["k2"],
        kappa=mat_params["kappa"],
        fiber_dispersion=mat_params["fiber_dispersion"],
    )
    rng = np.random.default_rng(seed)
    max_err = 0.0
    for _ in range(n_samples):
        F = generate_random_deformation(rng)
        E = green_lagrange(F)
        # Random unit fibers per sample.
        a1 = rng.standard_normal(3)
        a1 = a1 / float(np.linalg.norm(a1))
        a2 = rng.standard_normal(3)
        a2 = a2 / float(np.linalg.norm(a2))
        S_model = hgo_pk2_stress(mat, E, (a1, a2))

        def _energy_fn(e: np.ndarray, _a1: np.ndarray = a1, _a2: np.ndarray = a2) -> float:
            return _hgo_energy(mat, e, (_a1, _a2))

        S_fd = fd_stress_from_energy(_energy_fn, E)
        max_err = max(max_err, _rel_err(S_model, S_fd))
    return {"max_stress_error": max_err, "n_samples": n_samples, "all_passed": bool(max_err < tol)}
