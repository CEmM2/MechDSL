"""Analytical solution library for verification benchmarks.

Provides four ground-truth reference functions used by Phase 3 and Phase 4
verification harnesses:

- patch_test_reference      — constant Green-Lagrange strain → nodal displacements
- rigid_body_reference      — rigid body motion → nodal displacements
- cantilever_euler_bernoulli — Euler-Bernoulli beam tip deflection
- uniaxial_tension_hardening — uniaxial stress-strain for power-law J2 hardening
"""

from __future__ import annotations

from typing import cast

import numpy as np


def patch_test_reference(
    coords: np.ndarray,
    strain: np.ndarray,
) -> np.ndarray:
    """Compute exact nodal displacement field for a constant Green-Lagrange strain.

    For a constant strain field E (3x3), the linearised displacement is

        u_I = E_{IJ} * X_J

    which corresponds to u = E @ X for each node.

    Parameters
    ----------
    coords : np.ndarray, shape (N, 3)
        Reference (material) coordinates of N nodes.
    strain : np.ndarray, shape (3, 3)
        Green-Lagrange strain tensor.  Must be symmetric:
        ``np.allclose(strain, strain.T)`` must hold.

    Returns
    -------
    np.ndarray, shape (N, 3)
        Nodal displacement vectors.

    Raises
    ------
    ValueError
        If *strain* is not (3, 3) or not symmetric.
    """
    coords = np.asarray(coords, dtype=float)
    strain = np.asarray(strain, dtype=float)

    if strain.shape != (3, 3):
        raise ValueError(f"strain must be shape (3, 3), got {strain.shape}")
    if not np.allclose(strain, strain.T, atol=1e-12):
        raise ValueError(
            f"strain tensor must be symmetric; max asymmetry = {np.max(np.abs(strain - strain.T))}"
        )
    if coords.ndim != 2 or coords.shape[1] != 3:
        raise ValueError(f"coords must be shape (N, 3), got {coords.shape}")

    # u_i = E_ij * X_j  →  (N,3) = (N,3) @ (3,3).T
    return cast("np.ndarray", coords @ strain.T)


def rigid_body_reference(
    coords: np.ndarray,
    rotation: np.ndarray,
    translation: np.ndarray,
) -> np.ndarray:
    """Compute nodal displacements for a rigid body motion.

    The deformed position is  x = R @ X + t,  so the displacement is

        u = R @ X + t - X = (R - I) @ X + t

    The Cauchy-Green strain C = R^T R = I, so the Green-Lagrange strain
    E = 0, and the internal force should be exactly zero.

    Parameters
    ----------
    coords : np.ndarray, shape (N, 3)
        Reference nodal coordinates.
    rotation : np.ndarray, shape (3, 3)
        Proper orthogonal rotation matrix.  Must satisfy
        ``np.allclose(R @ R.T, I)`` and ``det(R) ≈ +1``.
    translation : np.ndarray, shape (3,)
        Rigid-body translation vector.

    Returns
    -------
    np.ndarray, shape (N, 3)
        Nodal displacement vectors.

    Raises
    ------
    ValueError
        If *rotation* is not a proper orthogonal matrix.
    """
    coords = np.asarray(coords, dtype=float)
    rotation = np.asarray(rotation, dtype=float)
    translation = np.asarray(translation, dtype=float)

    if rotation.shape != (3, 3):
        raise ValueError(f"rotation must be shape (3, 3), got {rotation.shape}")

    # Check orthogonality: R^T R = I
    RtR = rotation.T @ rotation
    if not np.allclose(RtR, np.eye(3), atol=1e-10):
        raise ValueError(
            "rotation matrix is not orthogonal; "
            f"max deviation from I = {np.max(np.abs(RtR - np.eye(3)))}"
        )

    # Check proper rotation: det(R) = +1
    det = np.linalg.det(rotation)
    if not np.isclose(det, 1.0, atol=1e-10):
        raise ValueError(f"rotation matrix must have det = +1 (proper rotation), got det = {det}")

    if translation.shape != (3,):
        raise ValueError(f"translation must be shape (3,), got {translation.shape}")
    if coords.ndim != 2 or coords.shape[1] != 3:
        raise ValueError(f"coords must be shape (N, 3), got {coords.shape}")

    R_minus_I = rotation - np.eye(3)
    return cast("np.ndarray", coords @ R_minus_I.T + translation[np.newaxis, :])


def cantilever_euler_bernoulli(
    L: float,
    I: float,
    E: float,
    P: float,
) -> float:
    """Compute the tip deflection of a cantilever beam (Euler-Bernoulli theory).

    The classical formula for the vertical tip deflection of a cantilever
    loaded by a point force *P* at its free end is::

        delta = P * L^3 / (3 * E * I)

    Sign convention: positive *P* (downward load, tension-positive convention)
    gives a positive (downward) tip deflection.

    Parameters
    ----------
    L : float
        Beam length (> 0).
    I : float
        Second moment of area of the cross-section (> 0).
    E : float
        Young's modulus (> 0).
    P : float
        Applied tip load (positive = in the direction of deflection).

    Returns
    -------
    float
        Tip deflection ``delta = P * L**3 / (3 * E * I)``.

    Raises
    ------
    ValueError
        If any of *L*, *I*, *E* are non-positive.
    """
    if L <= 0:
        raise ValueError(f"Beam length L must be positive, got {L}")
    if I <= 0:
        raise ValueError(f"Second moment of area I must be positive, got {I}")
    if E <= 0:
        raise ValueError(f"Young's modulus E must be positive, got {E}")

    return P * L**3 / (3.0 * E * I)


def uniaxial_tension_hardening(
    E: float,
    nu: float,
    sigma_y0: float,
    K: float,
    n: float,
    eps_total: float,
) -> tuple[float, float]:
    """Compute the analytical uniaxial stress-strain response with power-law J2 hardening.

    Implements the uniaxial return mapping for isotropic power-law hardening:

        sigma_y(alpha) = sigma_y0 + K * alpha^n

    where *alpha* is the accumulated equivalent plastic strain (eps_p here).

    **Elastic regime** (``E * eps_total < sigma_y0``):

        sigma = E * eps_total,  eps_p = 0

    **Plastic regime** — solve for eps_p from the consistency condition::

        sigma_y0 + K * eps_p^n + E * eps_p = E * eps_total

    i.e.  f(eps_p) = sigma_y0 + K * eps_p^n + E * eps_p - E * eps_total = 0

    The stress is then recovered as::

        sigma = E * (eps_total - eps_p)

    Root-finding uses Brent's method (``scipy.optimize.brentq``) with the
    bracket ``[0, eps_total]``.

    Parameters
    ----------
    E : float
        Young's modulus (> 0).
    nu : float
        Poisson's ratio (unused in uniaxial case but kept for API consistency
        with the 3-D constitutive model).
    sigma_y0 : float
        Initial yield stress (> 0).
    K : float
        Hardening modulus (>= 0).
    n : float
        Hardening exponent (> 0).
    eps_total : float
        Total axial strain (>= 0).

    Returns
    -------
    tuple[float, float]
        ``(stress, eps_p)`` where *stress* is the Cauchy (1-D) stress and
        *eps_p* is the accumulated equivalent plastic strain.

    Raises
    ------
    ValueError
        If *E*, *sigma_y0*, or *n* are non-positive, or *K* is negative,
        or *eps_total* is negative.
    RuntimeError
        If Brent's method fails to converge.

    Notes
    -----
    Tension-positive sign convention (per 07-CONVENTIONS.md).
    """
    if E <= 0:
        raise ValueError(f"Young's modulus E must be positive, got {E}")
    if sigma_y0 <= 0:
        raise ValueError(f"Initial yield stress sigma_y0 must be positive, got {sigma_y0}")
    if K < 0:
        raise ValueError(f"Hardening modulus K must be non-negative, got {K}")
    if n <= 0:
        raise ValueError(f"Hardening exponent n must be positive, got {n}")
    if eps_total < 0:
        raise ValueError(f"Total strain eps_total must be non-negative, got {eps_total}")

    # Elastic regime check
    if E * eps_total <= sigma_y0:
        return (E * eps_total, 0.0)

    # Plastic regime: solve f(eps_p) = 0 on [0, eps_total]
    # f(eps_p) = sigma_y0 + K * eps_p^n + E * eps_p - E * eps_total
    from scipy.optimize import brentq

    def f(eps_p: float) -> float:
        return float(sigma_y0 + K * eps_p**n + E * eps_p - E * eps_total)

    # Verify bracket (f(0) < 0 and f(eps_total) > 0 in the plastic regime)
    f_lo = f(0.0)
    f_hi = f(eps_total)

    if f_lo >= 0.0:
        # Should not happen since we passed the elastic check above
        return (E * eps_total, 0.0)

    if f_hi <= 0.0:
        raise RuntimeError(
            f"Bracket failure: f(eps_total={eps_total}) = {f_hi} <= 0. "
            "The plastic strain exceeds total strain — check material parameters."
        )

    try:
        eps_p = brentq(f, 0.0, eps_total, xtol=1e-14, rtol=1e-12, maxiter=200)
    except ValueError as exc:
        raise RuntimeError(f"brentq failed to find root in [0, {eps_total}]: {exc}") from exc

    stress = E * (eps_total - eps_p)
    return (stress, float(eps_p))
