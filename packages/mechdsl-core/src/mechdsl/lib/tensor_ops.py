"""Tier-1 tensor operations: pure NumPy reference implementations.

These are low-level math helpers used by reference kernels and generated code.
Taichi-decorated (@ti.func) versions will be added later when actual Taichi
kernels need them; these pure-numpy versions serve as the ground truth for
testing and verification.

All tensors are 3x3 float64 arrays. Conventions follow 07-CONVENTIONS.md:
  - Index convention: lowercase i,j = spatial; uppercase I,J = material
  - Tension-positive stress, compression-positive pressure
"""

from __future__ import annotations

from typing import cast

import numpy as np
from numpy.typing import NDArray

type Mat33 = NDArray[np.float64]  # (3,3) array

_I3 = np.eye(3, dtype=np.float64)


def mat_mul_33(A: Mat33, B: Mat33) -> Mat33:
    """Matrix multiply: A @ B."""
    return cast("Mat33", A @ B)


def mat_mul_T_33(A: Mat33, B: Mat33) -> Mat33:
    """Transpose multiply: A^T @ B."""
    return cast("Mat33", A.T @ B)


def pk1_from_pk2(F: Mat33, S: Mat33) -> Mat33:
    """First Piola-Kirchhoff from Second PK: P = F @ S."""
    return cast("Mat33", F @ S)


def cauchy_from_pk1(P: Mat33, F: Mat33, J: float) -> Mat33:
    """Cauchy stress from PK1: sigma = (1/J) * P @ F^T."""
    return cast("Mat33", (1.0 / J) * (P @ F.T))


def right_cauchy_green(F: Mat33) -> Mat33:
    """Right Cauchy-Green tensor: C = F^T @ F."""
    return cast("Mat33", F.T @ F)


def green_lagrange(F: Mat33) -> Mat33:
    """Green-Lagrange strain: E = (C - I) / 2."""
    C = right_cauchy_green(F)
    return cast("Mat33", 0.5 * (C - _I3))


def det_33(F: Mat33) -> float:
    """Determinant of 3x3 matrix."""
    return float(np.linalg.det(F))


def inv_33(F: Mat33) -> Mat33:
    """Inverse of 3x3 matrix."""
    return cast("Mat33", np.linalg.inv(F))


def deformation_gradient(grad_u: Mat33) -> Mat33:
    """Deformation gradient: F = I + grad(u)."""
    return cast("Mat33", _I3 + grad_u)


# ---------------------------------------------------------------------------
# Updated Lagrangian primitives
#
# These mirror their reference-configuration counterparts used by the TL path:
#   J0 = X^T @ dN/dxi            (reference Jacobian)
#   dN/dX = dN/dxi @ J0^{-1}     (reference-config shape gradients)
#
# The UL versions replace the reference element nodes ``X`` with the current
# (deformed) element nodes ``x = X + u``. Both helpers are shape-generic so
# they work for any element type, not just Hex8 — the per-element assembler
# passes the appropriate ``dN_dxi`` table from ``mechdsl.codegen.hex8_tables``
# (or its element-specific equivalent).
# ---------------------------------------------------------------------------


def current_jacobian(dN_dxi: NDArray[np.float64], x_elem: NDArray[np.float64]) -> Mat33:
    """Current-configuration Jacobian :math:`j = x^T \\, \\partial N / \\partial \\xi`.

    Parameters
    ----------
    dN_dxi : NDArray, shape (n_nodes, 3)
        Shape function gradients in parametric coordinates, evaluated at a
        single quadrature point.
    x_elem : NDArray, shape (n_nodes, 3)
        Element nodal coordinates in the **current** (deformed) configuration.

    Returns
    -------
    j : Mat33
        3x3 current-configuration Jacobian. At ``F = I`` this equals the
        reference Jacobian ``J0``.

    Notes
    -----
    Plan B §B1.1 integrates the UL residual over the current configuration
    using spatial shape gradients ``dN_a / dx_i = (dN_a / dxi_j) * j^{-1}_{ji}``.
    This helper computes ``j``; :func:`spatial_shape_gradient` applies the
    inverse to produce ``dN/dx``.
    """
    return cast("Mat33", x_elem.T @ dN_dxi)


def spatial_shape_gradient(
    dN_dxi: NDArray[np.float64],
    j: Mat33,
) -> NDArray[np.float64]:
    """Spatial shape-function gradients ``dN_a / dx_i = (dN/dxi) @ j^{-1}``.

    Parameters
    ----------
    dN_dxi : NDArray, shape (n_nodes, 3)
        Parametric shape gradients at a single quadrature point.
    j : Mat33
        Current Jacobian at that quadrature point (from
        :func:`current_jacobian`).

    Returns
    -------
    NDArray, shape (n_nodes, 3)
        Shape gradients in the current configuration. Row ``a`` is
        :math:`\\partial N_a / \\partial x_i`.

    Raises
    ------
    numpy.linalg.LinAlgError
        If ``j`` is singular. The caller (per Plan B conventions) should
        guard against non-positive ``det(j)`` before invoking this helper;
        see :func:`mechdsl.codegen.hex8_tables.current_gradient_at_physical`.
    """
    j_inv = np.linalg.inv(j)
    return cast("NDArray[np.float64]", dN_dxi @ j_inv)
