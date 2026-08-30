"""Pre-computed static tables for Hex8 element code generation.

These tables are used by Taichi code generation templates. They provide
literal numeric arrays that can be emitted directly into generated code,
avoiding callable-function overhead at codegen time.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from numpy.typing import NDArray

# ---------------------------------------------------------------------------
# Hex8 reference node coordinates in [-1,1]^3  (MFEM/VTK convention)
# ---------------------------------------------------------------------------

HEX8_NODE_COORDS: NDArray = np.array(
    [
        [-1, -1, -1],
        [+1, -1, -1],
        [+1, +1, -1],
        [-1, +1, -1],
        [-1, -1, +1],
        [+1, -1, +1],
        [+1, +1, +1],
        [-1, +1, +1],
    ],
    dtype=np.float64,
)

# ---------------------------------------------------------------------------
# Shape function evaluation
# ---------------------------------------------------------------------------


def shape_functions(xi: float, eta: float, zeta: float) -> NDArray:
    """Evaluate 8 Hex8 shape functions at a parametric point.

    N_a(xi, eta, zeta) = (1/8)(1 + xi_a*xi)(1 + eta_a*eta)(1 + zeta_a*zeta)

    Returns shape (8,).
    """
    vals = np.empty(8, dtype=np.float64)
    for a in range(8):
        xi_a, eta_a, zeta_a = HEX8_NODE_COORDS[a]
        vals[a] = 0.125 * (1.0 + xi_a * xi) * (1.0 + eta_a * eta) * (1.0 + zeta_a * zeta)
    return vals


def shape_gradients(xi: float, eta: float, zeta: float) -> NDArray:
    """Evaluate shape function gradients at a parametric point.

    Returns shape (8, 3) with columns [dN/dxi, dN/deta, dN/dzeta].
    """
    grad = np.empty((8, 3), dtype=np.float64)
    for a in range(8):
        xi_a, eta_a, zeta_a = HEX8_NODE_COORDS[a]
        grad[a, 0] = 0.125 * xi_a * (1.0 + eta_a * eta) * (1.0 + zeta_a * zeta)
        grad[a, 1] = 0.125 * (1.0 + xi_a * xi) * eta_a * (1.0 + zeta_a * zeta)
        grad[a, 2] = 0.125 * (1.0 + xi_a * xi) * (1.0 + eta_a * eta) * zeta_a
    return grad


# ---------------------------------------------------------------------------
# 2x2x2 Gauss quadrature
# ---------------------------------------------------------------------------

_g: float = 1.0 / np.sqrt(3.0)

HEX8_QUAD_POINTS: NDArray = np.array(
    [[xi, eta, zeta] for xi in (-_g, +_g) for eta in (-_g, +_g) for zeta in (-_g, +_g)],
    dtype=np.float64,
)

HEX8_QUAD_WEIGHTS: NDArray = np.ones(8, dtype=np.float64)

# ---------------------------------------------------------------------------
# Pre-evaluated tables (computed once at module load time)
# ---------------------------------------------------------------------------

# SHAPE_AT_QUAD[q, a] = N_a(xi_q, eta_q, zeta_q)
SHAPE_AT_QUAD: NDArray = np.array(
    [shape_functions(float(pt[0]), float(pt[1]), float(pt[2])) for pt in HEX8_QUAD_POINTS],
    dtype=np.float64,
)

# GRAD_AT_QUAD[q, a, i] = dN_a / d(xi_i) at quadrature point q
GRAD_AT_QUAD: NDArray = np.array(
    [shape_gradients(float(pt[0]), float(pt[1]), float(pt[2])) for pt in HEX8_QUAD_POINTS],
    dtype=np.float64,
)

# ---------------------------------------------------------------------------
# Physical-space gradient computation
# ---------------------------------------------------------------------------


def reference_gradient_at_physical(
    X_elem: NDArray,  # (8, 3) element node coordinates in reference config
    q: int,  # quadrature point index
) -> tuple[NDArray, float]:
    """Compute dN/dX and det(J0) at quadrature point *q*.

    The reference Jacobian maps from parametric to physical reference space:
        J0 = X^T @ dN/dxi   (3x3)

    Shape function gradients in physical reference space:
        dN/dX = dN/dxi @ J0^{-1}

    Parameters
    ----------
    X_elem : NDArray, shape (8, 3)
        Element nodal coordinates in the reference configuration.
    q : int
        Quadrature point index (0..7).

    Returns
    -------
    dNdX : NDArray, shape (8, 3)
        Shape function gradients w.r.t. reference coordinates X.
    detJ0 : float
        Determinant of the reference Jacobian.
    """
    dN_dxi = GRAD_AT_QUAD[q]

    # Reference Jacobian: J0 = dX/dxi = X^T @ dN/dxi  ->  (3, 3)
    J0 = X_elem.T @ dN_dxi

    detJ0 = float(np.linalg.det(J0))
    if detJ0 <= 0.0:
        msg = f"Non-positive Jacobian determinant ({detJ0:.6e}) at quadrature point {q}."
        raise ValueError(msg)

    J0_inv = np.linalg.inv(J0)

    # dN/dX = dN/dxi @ J0^{-1}
    dNdX: NDArray = dN_dxi @ J0_inv

    return dNdX, detJ0


def current_gradient_at_physical(
    X_elem: NDArray,  # (8, 3) element node coordinates in reference config (unused at F=I)
    x_elem: NDArray,  # (8, 3) element node coordinates in the CURRENT configuration
    q: int,  # quadrature point index
) -> tuple[NDArray, float]:
    """Compute dN/dx and det(j) at quadrature point *q* for Updated Lagrangian.

    Mirror of :func:`reference_gradient_at_physical` — Plan B §B1.1 integrates
    the UL residual over the **current** configuration, so the Jacobian maps
    parametric coordinates to the deformed element geometry:

        j = dx/dxi = x^T @ dN/dxi   (3x3)

    Shape function gradients in current (spatial) coordinates:

        dN/dx = dN/dxi @ j^{-1}

    The ``X_elem`` argument is retained for API symmetry with
    :func:`reference_gradient_at_physical` and for future callers that need
    to compute both J0 and j in a single pass (e.g. the P1-4 tangent
    emission where the Jaumann material term needs J0 and the geometric
    stiffness term needs j). At ``F = I`` (``x_elem == X_elem``) the two
    helpers return byte-identical output.

    Parameters
    ----------
    X_elem : NDArray, shape (8, 3)
        Element nodal coordinates in the reference configuration.
    x_elem : NDArray, shape (8, 3)
        Element nodal coordinates in the current configuration, i.e.
        ``x = X + u`` where ``u`` is the displacement field.
    q : int
        Quadrature point index (0..7).

    Returns
    -------
    dNdx : NDArray, shape (8, 3)
        Shape function gradients w.r.t. current coordinates ``x``.
    detj : float
        Determinant of the current Jacobian ``j``.

    Raises
    ------
    ValueError
        If ``det(j) <= 0`` at the quadrature point — the element is inverted
        or degenerate in the current configuration. Tolerance matches the
        reference-config helper for numerical consistency.
    """
    del X_elem  # not used at F = I; retained for API symmetry (see docstring).
    dN_dxi = GRAD_AT_QUAD[q]

    # Current Jacobian: j = dx/dxi = x^T @ dN/dxi  ->  (3, 3)
    j = x_elem.T @ dN_dxi

    detj = float(np.linalg.det(j))
    if detj <= 0.0:
        msg = (
            f"Non-positive current Jacobian determinant ({detj:.6e}) "
            f"at quadrature point {q}. Element inverted in the deformed "
            "configuration — check load step size or mesh quality."
        )
        raise ValueError(msg)

    j_inv = np.linalg.inv(j)

    # dN/dx = dN/dxi @ j^{-1}
    dNdx: NDArray = dN_dxi @ j_inv

    return dNdx, detj
