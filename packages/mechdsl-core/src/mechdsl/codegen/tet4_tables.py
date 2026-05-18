"""Pre-computed static tables for Tet4 element code generation.

Linear tetrahedron (4 nodes, 1-point Gauss quadrature).

Reference element convention (matches MFEM/VTK):
  N0 = (0, 0, 0)
  N1 = (1, 0, 0)
  N2 = (0, 1, 0)
  N3 = (0, 0, 1)

Volume coordinates:
  L0 = 1 - xi - eta - zeta,  L1 = xi,  L2 = eta,  L3 = zeta
Shape functions:
  N_a = L_a  (linear)

1-point Gauss rule (integrates constants exactly — sufficient for linear basis):
  Quadrature point : centroid (1/4, 1/4, 1/4)
  Weight           : 1/6  (= reference-tet volume)

NOTE — Volumetric locking:
  Tet4 is low-order and susceptible to volumetric locking with near-incompressible
  materials (nu → 0.5). B-bar / F-bar stabilisation is deferred to a later task
  (Plan B §B5.3). Use Tet10 or Hex8 for near-incompressible problems in the
  meantime.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from numpy.typing import NDArray

# ---------------------------------------------------------------------------
# Reference node coordinates  (MFEM/VTK convention)
# ---------------------------------------------------------------------------

TET4_NODE_COORDS: NDArray = np.array(
    [
        [0.0, 0.0, 0.0],  # N0
        [1.0, 0.0, 0.0],  # N1
        [0.0, 1.0, 0.0],  # N2
        [0.0, 0.0, 1.0],  # N3
    ],
    dtype=np.float64,
)

# ---------------------------------------------------------------------------
# Shape function evaluation
# ---------------------------------------------------------------------------


def shape_functions(xi: float, eta: float, zeta: float) -> NDArray:
    """Evaluate 4 Tet4 shape functions at a parametric point.

    N0 = 1 - xi - eta - zeta
    N1 = xi
    N2 = eta
    N3 = zeta

    Returns shape (4,).
    """
    return np.array(
        [1.0 - xi - eta - zeta, xi, eta, zeta],
        dtype=np.float64,
    )


def shape_gradients(xi: float, eta: float, zeta: float) -> NDArray:
    """Evaluate shape function gradients at a parametric point.

    For Tet4 the gradients are constant (independent of xi, eta, zeta):
      dN0/d(xi,eta,zeta) = (-1, -1, -1)
      dN1/d(xi,eta,zeta) = ( 1,  0,  0)
      dN2/d(xi,eta,zeta) = ( 0,  1,  0)
      dN3/d(xi,eta,zeta) = ( 0,  0,  1)

    The ``xi``, ``eta``, ``zeta`` arguments are accepted for API symmetry
    with :func:`hex8_tables.shape_gradients` but are not used.

    Returns shape (4, 3) with columns [dN/dxi, dN/deta, dN/dzeta].
    """
    return np.array(
        [
            [-1.0, -1.0, -1.0],  # dN0
            [1.0, 0.0, 0.0],  # dN1
            [0.0, 1.0, 0.0],  # dN2
            [0.0, 0.0, 1.0],  # dN3
        ],
        dtype=np.float64,
    )


# ---------------------------------------------------------------------------
# 1-point Gauss quadrature  (centroid rule, weight = reference-tet volume)
# ---------------------------------------------------------------------------

TET4_QUAD_POINTS: NDArray = np.array(
    [[0.25, 0.25, 0.25]],
    dtype=np.float64,
)  # shape (1, 3)

TET4_QUAD_WEIGHTS: NDArray = np.array([1.0 / 6.0], dtype=np.float64)  # shape (1,)

# ---------------------------------------------------------------------------
# Pre-evaluated tables (computed once at module load time)
# ---------------------------------------------------------------------------

# SHAPE_AT_QUAD[q, a] = N_a(xi_q, eta_q, zeta_q)
SHAPE_AT_QUAD: NDArray = np.array(
    [shape_functions(float(pt[0]), float(pt[1]), float(pt[2])) for pt in TET4_QUAD_POINTS],
    dtype=np.float64,
)  # shape (1, 4)

# GRAD_AT_QUAD[q, a, i] = dN_a / d(xi_i) at quadrature point q
# For Tet4 the gradient is constant, so all q rows are identical.
GRAD_AT_QUAD: NDArray = np.array(
    [shape_gradients(float(pt[0]), float(pt[1]), float(pt[2])) for pt in TET4_QUAD_POINTS],
    dtype=np.float64,
)  # shape (1, 4, 3)

# ---------------------------------------------------------------------------
# Physical-space gradient computation
# ---------------------------------------------------------------------------


def reference_gradient_at_physical(
    X_elem: NDArray,  # (4, 3) element node coordinates in reference config
    q: int,  # quadrature point index
) -> tuple[NDArray, float]:
    """Compute dN/dX and det(J0) at quadrature point *q*.

    The reference Jacobian maps from parametric to physical reference space:
        J0 = X^T @ dN/dxi   (3x3)

    Shape function gradients in physical reference space:
        dN/dX = dN/dxi @ J0^{-1}

    For Tet4, the gradient is constant over the element (dN/dxi is constant),
    so this function produces the same result for all interior points.

    Parameters
    ----------
    X_elem : NDArray, shape (4, 3)
        Element nodal coordinates in the reference configuration.
    q : int
        Quadrature point index (0 for the single Gauss point).

    Returns
    -------
    dNdX : NDArray, shape (4, 3)
        Shape function gradients w.r.t. reference coordinates X.
    detJ0 : float
        Determinant of the reference Jacobian.

    Raises
    ------
    ValueError
        If det(J0) <= 0 — the element is inverted or degenerate.
    """
    dN_dxi = GRAD_AT_QUAD[q]  # (4, 3)

    # Reference Jacobian: J0 = dX/dxi = X^T @ dN/dxi  ->  (3, 3)
    J0 = X_elem.T @ dN_dxi

    detJ0 = float(np.linalg.det(J0))
    if detJ0 <= 0.0:
        msg = f"Non-positive Jacobian determinant ({detJ0:.6e}) at quadrature point {q}."
        raise ValueError(msg)

    J0_inv = np.linalg.inv(J0)

    # dN/dX = dN/dxi @ J0^{-1}
    dNdX: NDArray = dN_dxi @ J0_inv  # (4, 3)

    return dNdX, detJ0
