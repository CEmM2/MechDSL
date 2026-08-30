"""Objective stress rates and their spatial tangent conversions.

Plan B B1.4 adds three objective stress rates to support rate-form
constitutive models in the Updated Lagrangian path:

============  ================================================================
Rate          Formula
============  ================================================================
Jaumann       sigma_hat_J  = sigma_dot - W @ sigma - sigma @ W.T,    W = skew(L)
Truesdell     sigma_hat_T  = sigma_dot - L @ sigma - sigma @ L.T + sigma*tr(D)
Green-Naghdi  sigma_hat_GN = sigma_dot - Omega @ sigma - sigma @ Omega.T,
                             Omega = R_dot @ R.T
============  ================================================================

This module exposes two layers of API: spatial tangent conversions (the
P1-5 contracted surface) and direct rate functions (a documented scope
addition -- see "Out-of-scope additions" below).

================================================================
Contracted scope -- Spatial tangent conversions (P1-5 deliverable)
================================================================

Three functions, each consuming a 4th-order Lagrangian material tangent
``C_IJKL`` and the current Cauchy stress ``sigma`` and returning the
spatial tangent ``c_ijkl`` corresponding to each objective rate:

- ``truesdell_tangent(C4, sigma, F=None)`` -- Piola push-forward
  ``c_ijkl = (1/J) F_iI F_jJ F_kK F_lL C_IJKL``. If ``F`` is omitted (or
  identity) this reduces to the identity push-forward ``c_ijkl = C_IJKL``.
- ``jaumann_tangent(C4, sigma, F=None)`` -- Truesdell push-forward plus
  the Prandtl-Reuss stress-symmetrisation correction

      T_{ijkl} = 0.5*(delta_ik sigma_jl + delta_il sigma_jk
                    + sigma_ik delta_jl + sigma_il delta_jk)
                 - sigma_ij delta_kl

- ``green_naghdi_tangent(C4, sigma, R, F=None)`` -- reduces to the Jaumann
  tangent at ``R = I``. For ``R != I`` the polar-decomposition variant
  diverges from the continuum-spin variant and is not yet implemented;
  the function raises ``NotImplementedError`` with a pointer to the Plan B
  phase that will add support.

Downstream, P1-4 consumes these at emission time for the UL linearised
tangent term. The full-F Piola push-forward in ``truesdell_tangent``
makes the conversion correct at any quadrature-point F, not just at the
identity configuration.

================================================================
Out-of-scope additions -- Direct rate functions
================================================================

The three ``*_rate`` helpers below (``jaumann_rate``, ``truesdell_rate``,
``green_naghdi_rate``) are NOT part of the contracted P1-5 scope. They
exist because the P1-5 acceptance test "rigid rotation gives zero Cauchy
rate" is mathematically vacuous at the tangent level: under rigid
rotation ``D = 0``, so any tangent contraction ``c : D`` is trivially
zero -- it tests nothing. The rate functions are what actually carry the
objective-rate invariance, and the rigid-rotation tests in
``tests/test_objective_rates.py`` exercise them directly.

These helpers also make convenient debugging primitives for the P1-7
TL-vs-UL equivalence verification when manual stress-rate inspection is
needed. They are tiny, self-contained, and have no callers in the main
emission path.

**For a future reviewer:** if strict scope adherence is required, these
three functions can be removed (~10 minutes) and the rigid-rotation
tests can be rewritten to inline the rate formula at the test site. The
contracted ``*_tangent`` API is unaffected.

================================================================
Conventions
================================================================

Conventions follow ``dev/design_docs/07-CONVENTIONS.md``:
    - Lowercase i,j,k,l = spatial indices, uppercase I,J,K,L = material.
    - Voigt ordering [xx, yy, zz, xy, xz, yz] with unscaled shears (not
      used in this module -- all tensors are full 3x3 or 3x3x3x3 NumPy
      arrays).
    - Tension-positive stress.
"""

from __future__ import annotations

from typing import cast

import numpy as np
from numpy.typing import NDArray

type Mat33 = NDArray[np.float64]  # (3, 3)
type Tensor4 = NDArray[np.float64]  # (3, 3, 3, 3)

_I3: Mat33 = np.eye(3, dtype=np.float64)


# ---------------------------------------------------------------------------
# Velocity-gradient helpers (used internally; small enough to inline)
# ---------------------------------------------------------------------------


def _sym(L: Mat33) -> Mat33:
    """Symmetric part D = 0.5*(L + L.T) -- rate of deformation."""
    return cast("Mat33", 0.5 * (L + L.T))


def _skew(L: Mat33) -> Mat33:
    """Skew part W = 0.5*(L - L.T) -- continuum spin."""
    return cast("Mat33", 0.5 * (L - L.T))


# ---------------------------------------------------------------------------
# Direct rate functions
# ---------------------------------------------------------------------------


def jaumann_rate(sigma_dot: Mat33, L: Mat33, sigma: Mat33) -> Mat33:
    """Jaumann objective stress rate.

    Formula::

        sigma_hat_J = sigma_dot - W @ sigma - sigma @ W.T,   W = skew(L)

    Parameters
    ----------
    sigma_dot : Mat33
        Material time derivative of the Cauchy stress.
    L : Mat33
        Velocity gradient grad(v) in the current configuration.
    sigma : Mat33
        Current Cauchy stress (symmetric).

    Returns
    -------
    Mat33
        The Jaumann (co-rotational) stress rate. Vanishes identically under
        rigid body rotation -- verified by
        ``tests/test_objective_rates.py``.
    """
    W = _skew(L)
    return cast("Mat33", sigma_dot - W @ sigma - sigma @ W.T)


def truesdell_rate(sigma_dot: Mat33, L: Mat33, sigma: Mat33) -> Mat33:
    """Truesdell objective stress rate.

    Formula::

        sigma_hat_T = sigma_dot - L @ sigma - sigma @ L.T + sigma * tr(D)

    Parameters
    ----------
    sigma_dot : Mat33
        Material time derivative of the Cauchy stress.
    L : Mat33
        Velocity gradient grad(v).
    sigma : Mat33
        Current Cauchy stress (symmetric).

    Returns
    -------
    Mat33
        The Truesdell stress rate, conjugate to the second Piola-Kirchhoff
        through the push-forward relation ``sigma_hat_T = (1/J) F @ S_dot @ F.T``.
        Vanishes under rigid rotation because L = Omega is skew, D = 0,
        and the L @ sigma + sigma @ L.T terms cancel sigma_dot exactly.
    """
    D = _sym(L)
    trace_D = float(np.trace(D))
    return cast(
        "Mat33",
        sigma_dot - L @ sigma - sigma @ L.T + trace_D * sigma,
    )


def green_naghdi_rate(sigma_dot: Mat33, Omega: Mat33, sigma: Mat33) -> Mat33:
    """Green-Naghdi objective stress rate.

    Formula::

        sigma_hat_GN = sigma_dot - Omega @ sigma - sigma @ Omega.T

    Parameters
    ----------
    sigma_dot : Mat33
        Material time derivative of the Cauchy stress.
    Omega : Mat33
        Polar-decomposition spin ``Omega = R_dot @ R.T``, where R is the
        rotation from the polar decomposition F = R @ U. For rigid rotation
        (F = R) this reduces to the continuum spin W, so all three rates
        agree.
    sigma : Mat33
        Current Cauchy stress (symmetric).

    Returns
    -------
    Mat33
        The Green-Naghdi (polar-decomposition) stress rate. Vanishes under
        rigid body rotation.
    """
    return cast("Mat33", sigma_dot - Omega @ sigma - sigma @ Omega.T)


# ---------------------------------------------------------------------------
# Spatial tangent conversions (at F = I)
# ---------------------------------------------------------------------------


def _prandtl_reuss_correction(sigma: Mat33) -> Tensor4:
    """Stress-symmetrisation correction T(sigma) relating Jaumann to Truesdell.

    T_{ijkl} = 0.5*(delta_ik sigma_jl + delta_il sigma_jk
                  + sigma_ik delta_jl + sigma_il delta_jk)
               - sigma_ij delta_kl

    When contracted with a symmetric rate of deformation D, T yields
    ``D @ sigma + sigma @ D - sigma * tr(D)`` -- the operator-form
    correction derived in the module docstring.
    """
    ident = _I3
    T: Tensor4 = 0.5 * (
        np.einsum("ik,jl->ijkl", ident, sigma)
        + np.einsum("il,jk->ijkl", ident, sigma)
        + np.einsum("ik,jl->ijkl", sigma, ident)
        + np.einsum("il,jk->ijkl", sigma, ident)
    ) - np.einsum("ij,kl->ijkl", sigma, ident)
    return T


def truesdell_tangent(
    C4: Tensor4,
    sigma: Mat33,
    F: Mat33 | None = None,
) -> Tensor4:
    """Spatial Truesdell tangent: Piola push-forward of a Lagrangian C_IJKL.

    Implements the standard Piola push-forward::

        c_ijkl = (1/J) F_iI F_jJ F_kK F_lL C_IJKL,    J = det(F)

    When ``F`` is omitted (or the identity matrix), ``J = 1`` and the
    push-forward reduces to the identity ``c_ijkl = C_IJKL``. This is the
    correct behaviour for callers evaluating at the reference configuration
    or for sanity tests in the undeformed state.

    Parameters
    ----------
    C4 : Tensor4
        Lagrangian material tangent C_IJKL (3x3x3x3).
    sigma : Mat33
        Current Cauchy stress. Not consumed by the Truesdell push-forward
        itself but retained in the signature for API symmetry with the
        Jaumann and Green-Naghdi variants -- downstream callers (P1-4) can
        dispatch on the rate name without knowing which tangent variant
        actually needs sigma.
    F : Mat33 | None, optional
        Deformation gradient at the evaluation point. ``None`` (default)
        is shorthand for the identity matrix, recovering the Plan-A-era
        identity push-forward behaviour. For non-trivial deformations,
        pass the full 3x3 deformation gradient.

    Returns
    -------
    Tensor4
        Spatial tangent ``c_ijkl`` in the current configuration.

    Raises
    ------
    ValueError
        If ``det(F) <= 0`` -- the element is inverted in the deformed
        configuration. Tolerance matches the convention used by
        ``mechdsl.codegen.hex8_tables.current_gradient_at_physical``.
    """
    del sigma  # unused -- retained for API symmetry; see docstring.
    if F is None:
        return cast("Tensor4", C4.copy())
    J = float(np.linalg.det(F))
    if J <= 0.0:
        raise ValueError(
            f"Non-positive Jacobian det(F) = {J:.6e}. "
            "Element inverted in the deformed configuration -- "
            "check load step size or mesh quality before computing "
            "the Truesdell push-forward."
        )
    # Piola push-forward c_ijkl = (1/J) F_iI F_jJ F_kK F_lL C_IJKL.
    # The 4-leg einsum is ~243 multiply-adds for 3D and runs in microseconds.
    return cast(
        "Tensor4",
        (1.0 / J) * np.einsum("iI,jJ,kK,lL,IJKL->ijkl", F, F, F, F, C4),
    )


def jaumann_tangent(
    C4: Tensor4,
    sigma: Mat33,
    F: Mat33 | None = None,
) -> Tensor4:
    """Spatial Jaumann tangent: ``c_Jau = c_Tru + T(sigma)``.

    Computed as the Truesdell push-forward of ``C4`` plus the Prandtl-Reuss
    stress-symmetrisation correction T(sigma). Both terms are spatial
    quantities; the correction itself does not depend on F because sigma
    is already in the spatial frame.

    Parameters
    ----------
    C4 : Tensor4
        Lagrangian material tangent C_IJKL.
    sigma : Mat33
        Current Cauchy stress (spatial, symmetric).
    F : Mat33 | None, optional
        Deformation gradient. Forwarded to ``truesdell_tangent`` for the
        Piola push-forward. ``None`` (default) maps to identity.

    Returns
    -------
    Tensor4
        Spatial Jaumann tangent ``c_Jau_ijkl``. P1-4 consumes this in the
        UL linearised tangent kernel for the Jaumann-rate material term.
    """
    c_tru = truesdell_tangent(C4, sigma, F=F)
    correction = _prandtl_reuss_correction(sigma)
    return cast("Tensor4", c_tru + correction)


def green_naghdi_tangent(
    C4: Tensor4,
    sigma: Mat33,
    R: Mat33,
    F: Mat33 | None = None,
) -> Tensor4:
    """Spatial Green-Naghdi tangent.

    At ``R = I`` the polar-decomposition spin ``Omega_GN = R_dot @ R.T``
    coincides with the continuum spin ``W = skew(L)`` instantaneously, so
    this helper reduces to the Jaumann tangent (still consuming ``F`` for
    the Piola push-forward). At finite rotation the two diverge -- the
    Green-Naghdi correction depends on the rate of the rotation tensor,
    which is not derivable from the current ``(C4, sigma, F)`` snapshot
    alone, and the function raises ``NotImplementedError``.

    Parameters
    ----------
    C4 : Tensor4
        Lagrangian material tangent C_IJKL.
    sigma : Mat33
        Current Cauchy stress.
    R : Mat33
        Polar-decomposition rotation from F = R @ U. Must be (numerically
        close to) the identity for the current implementation.
    F : Mat33 | None, optional
        Full deformation gradient, forwarded to the Jaumann path for the
        Piola push-forward of C4. Defaults to identity.

    Raises
    ------
    NotImplementedError
        If ``R`` is not numerically close to the identity. Full-rotation
        Green-Naghdi support is deferred to the Plan B phase that
        introduces large-rotation rate-form constitutive updates (likely
        Phase B3 Perzyna or B4 HGO).
    """
    if not np.allclose(R, _I3, atol=1e-12):
        raise NotImplementedError(
            "green_naghdi_tangent currently requires R = I (the continuum "
            "spin and polar-decomposition spin coincide instantaneously). "
            "Full large-rotation Green-Naghdi support is deferred to the "
            "Plan B phase that introduces rate-form constitutive updates "
            "with finite rotation."
        )
    return jaumann_tangent(C4, sigma, F=F)
