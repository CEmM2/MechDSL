"""Pre-computed static tables for Tet10 element code generation.

Quadratic tetrahedron (10 nodes, 4-point Gauss quadrature).

Reference element convention (matches MFEM/VTK, same as Tet4):
  Corner nodes:
    N0 = (0, 0, 0)
    N1 = (1, 0, 0)
    N2 = (0, 1, 0)
    N3 = (0, 0, 1)
  Edge midpoint nodes (VTK/MFEM ordering):
    N4 = midpoint of edge N0-N1 = (0.5, 0,   0  )
    N5 = midpoint of edge N1-N2 = (0.5, 0.5, 0  )
    N6 = midpoint of edge N2-N0 = (0,   0.5, 0  )
    N7 = midpoint of edge N0-N3 = (0,   0,   0.5)
    N8 = midpoint of edge N1-N3 = (0.5, 0,   0.5)
    N9 = midpoint of edge N2-N3 = (0,   0.5, 0.5)

Volume coordinates:
  L0 = 1 - xi - eta - zeta,  L1 = xi,  L2 = eta,  L3 = zeta

Shape functions (Zienkiewicz formulation):
  Corner nodes:
    N0 = L0 (2 L0 - 1) = (1-xi-eta-zeta)(1-2xi-2eta-2zeta)
    N1 = L1 (2 L1 - 1) = xi (2 xi - 1)
    N2 = L2 (2 L2 - 1) = eta (2 eta - 1)
    N3 = L3 (2 L3 - 1) = zeta (2 zeta - 1)
  Edge midpoint nodes (4 L_a L_b for edge a-b):
    N4 = 4 L0 L1 = 4 xi (1-xi-eta-zeta)         (edge 0-1)
    N5 = 4 L1 L2 = 4 xi eta                      (edge 1-2)
    N6 = 4 L2 L0 = 4 eta (1-xi-eta-zeta)         (edge 2-0)
    N7 = 4 L0 L3 = 4 zeta (1-xi-eta-zeta)        (edge 0-3)
    N8 = 4 L1 L3 = 4 xi zeta                     (edge 1-3)
    N9 = 4 L2 L3 = 4 eta zeta                    (edge 2-3)

4-point Gauss quadrature (Keast/Zienkiewicz §5.5, symmetric):
  a = (5 - sqrt(5)) / 20 ≈ 0.138197
  b = (5 + 3*sqrt(5)) / 20 ≈ 0.585410
  At each quadrature point one volume coordinate = b, the other three = a.
  In (xi, eta, zeta) coordinates (L1, L2, L3):
    Q0: (a, a, a)  — L0 = b
    Q1: (b, a, a)  — L1 = b
    Q2: (a, b, a)  — L2 = b
    Q3: (a, a, b)  — L3 = b
  Weight = 1/24 each (sum = 1/6 = reference-tet volume).
  This rule integrates all polynomials up to degree 2 exactly.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from numpy.typing import NDArray

# ---------------------------------------------------------------------------
# Quadrature constants
# ---------------------------------------------------------------------------

_SQRT5 = math.sqrt(5.0)
_A = (5.0 - _SQRT5) / 20.0  # ≈ 0.138196601125011
_B = (5.0 + 3.0 * _SQRT5) / 20.0  # ≈ 0.585410196624969

# ---------------------------------------------------------------------------
# Reference node coordinates  (MFEM/VTK convention)
# ---------------------------------------------------------------------------

TET10_NODE_COORDS: NDArray = np.array(
    [
        [0.0, 0.0, 0.0],  # N0 — corner
        [1.0, 0.0, 0.0],  # N1 — corner
        [0.0, 1.0, 0.0],  # N2 — corner
        [0.0, 0.0, 1.0],  # N3 — corner
        [0.5, 0.0, 0.0],  # N4 — midpoint edge 0-1
        [0.5, 0.5, 0.0],  # N5 — midpoint edge 1-2
        [0.0, 0.5, 0.0],  # N6 — midpoint edge 2-0
        [0.0, 0.0, 0.5],  # N7 — midpoint edge 0-3
        [0.5, 0.0, 0.5],  # N8 — midpoint edge 1-3
        [0.0, 0.5, 0.5],  # N9 — midpoint edge 2-3
    ],
    dtype=np.float64,
)

# ---------------------------------------------------------------------------
# Shape function evaluation
# ---------------------------------------------------------------------------


def shape_functions(xi: float, eta: float, zeta: float) -> NDArray:
    """Evaluate 10 Tet10 shape functions at a parametric point.

    Volume coordinates:
      L0 = 1 - xi - eta - zeta,  L1 = xi,  L2 = eta,  L3 = zeta

    Corner nodes (Zienkiewicz):
      N_a = L_a (2 L_a - 1)
    Edge midpoint nodes:
      N_(ab) = 4 L_a L_b

    Returns shape (10,).
    """
    L0 = 1.0 - xi - eta - zeta
    L1 = xi
    L2 = eta
    L3 = zeta

    return np.array(
        [
            L0 * (2.0 * L0 - 1.0),  # N0 — corner 0
            L1 * (2.0 * L1 - 1.0),  # N1 — corner 1
            L2 * (2.0 * L2 - 1.0),  # N2 — corner 2
            L3 * (2.0 * L3 - 1.0),  # N3 — corner 3
            4.0 * L0 * L1,  # N4 — edge 0-1
            4.0 * L1 * L2,  # N5 — edge 1-2
            4.0 * L2 * L0,  # N6 — edge 2-0
            4.0 * L0 * L3,  # N7 — edge 0-3
            4.0 * L1 * L3,  # N8 — edge 1-3
            4.0 * L2 * L3,  # N9 — edge 2-3
        ],
        dtype=np.float64,
    )


def shape_gradients(xi: float, eta: float, zeta: float) -> NDArray:
    """Evaluate shape function gradients at a parametric point.

    Returns (10, 3) with columns [dN/dxi, dN/deta, dN/dzeta].

    Using L0 = 1 - xi - eta - zeta:
      dL0/dxi = -1, dL0/deta = -1, dL0/dzeta = -1
      dL1/dxi =  1, dL1/deta =  0, dL1/dzeta =  0
      dL2/dxi =  0, dL2/deta =  1, dL2/dzeta =  0
      dL3/dxi =  0, dL3/deta =  0, dL3/dzeta =  1

    Corner node gradients (dN_a/dxi_j = dL_a/dxi_j (4L_a - 1)):
      dN0/d. = (-1)(4L0-1), (-1)(4L0-1), (-1)(4L0-1)
      dN1/d. = (4L1-1), 0, 0
      dN2/d. = 0, (4L2-1), 0
      dN3/d. = 0, 0, (4L3-1)

    Edge midpoint gradients (d/d. (4 L_a L_b)):
      N4 = 4 L0 L1: dN4/dxi = 4(dL0/dxi L1 + L0 dL1/dxi) = 4(-L1 + L0) = 4(L0-L1)
                    dN4/deta = 4(-L1 + 0) = -4L1
                    dN4/dzeta = -4L1
      (and similarly for others)
    """
    L0 = 1.0 - xi - eta - zeta
    L1 = xi
    L2 = eta
    L3 = zeta

    # dN/dxi (column 0), dN/deta (column 1), dN/dzeta (column 2)
    return np.array(
        [
            # N0 = L0(2L0-1),  dL0/d(xi,eta,zeta)=(-1,-1,-1)
            # dN0/d. = (4L0-1) * dL0/d.
            [-(4.0 * L0 - 1.0), -(4.0 * L0 - 1.0), -(4.0 * L0 - 1.0)],  # N0
            # N1 = L1(2L1-1),  dL1/d(xi,eta,zeta)=(1,0,0)
            [(4.0 * L1 - 1.0), 0.0, 0.0],  # N1
            # N2 = L2(2L2-1),  dL2/d(xi,eta,zeta)=(0,1,0)
            [0.0, (4.0 * L2 - 1.0), 0.0],  # N2
            # N3 = L3(2L3-1),  dL3/d(xi,eta,zeta)=(0,0,1)
            [0.0, 0.0, (4.0 * L3 - 1.0)],  # N3
            # N4 = 4 L0 L1
            [4.0 * (L0 - L1), -4.0 * L1, -4.0 * L1],  # N4
            # N5 = 4 L1 L2
            [4.0 * L2, 4.0 * L1, 0.0],  # N5
            # N6 = 4 L2 L0
            [-4.0 * L2, 4.0 * (L0 - L2), -4.0 * L2],  # N6
            # N7 = 4 L0 L3
            [-4.0 * L3, -4.0 * L3, 4.0 * (L0 - L3)],  # N7
            # N8 = 4 L1 L3
            [4.0 * L3, 0.0, 4.0 * L1],  # N8
            # N9 = 4 L2 L3
            [0.0, 4.0 * L3, 4.0 * L2],  # N9
        ],
        dtype=np.float64,
    )


# ---------------------------------------------------------------------------
# 4-point Gauss quadrature (symmetric, Keast/Zienkiewicz §5.5)
# ---------------------------------------------------------------------------

TET10_QUAD_POINTS: NDArray = np.array(
    [
        [_A, _A, _A],  # Q0: L0 = b
        [_B, _A, _A],  # Q1: L1 = b
        [_A, _B, _A],  # Q2: L2 = b
        [_A, _A, _B],  # Q3: L3 = b
    ],
    dtype=np.float64,
)  # shape (4, 3)

TET10_QUAD_WEIGHTS: NDArray = np.full(4, 1.0 / 24.0, dtype=np.float64)  # shape (4,)

# ---------------------------------------------------------------------------
# Pre-evaluated tables (computed once at module load time)
# ---------------------------------------------------------------------------

# SHAPE_AT_QUAD[q, a] = N_a(xi_q, eta_q, zeta_q)
SHAPE_AT_QUAD: NDArray = np.array(
    [shape_functions(float(pt[0]), float(pt[1]), float(pt[2])) for pt in TET10_QUAD_POINTS],
    dtype=np.float64,
)  # shape (4, 10)

# GRAD_AT_QUAD[q, a, i] = dN_a / d(xi_i) at quadrature point q
GRAD_AT_QUAD: NDArray = np.array(
    [shape_gradients(float(pt[0]), float(pt[1]), float(pt[2])) for pt in TET10_QUAD_POINTS],
    dtype=np.float64,
)  # shape (4, 10, 3)

# ---------------------------------------------------------------------------
# Physical-space gradient computation
# ---------------------------------------------------------------------------


def reference_gradient_at_physical(
    X_elem: NDArray,  # (10, 3) element node coordinates in reference config
    q: int,  # quadrature point index (0..3)
) -> tuple[NDArray, float]:
    """Compute dN/dX and det(J0) at quadrature point *q* for a Tet10 element.

    The reference Jacobian maps from parametric to physical reference space:
        J0 = X^T @ dN/dxi   (3x3)

    Shape function gradients in physical reference space:
        dN/dX = dN/dxi @ J0^{-1}

    Parameters
    ----------
    X_elem : NDArray, shape (10, 3)
        Element nodal coordinates in the reference configuration.
    q : int
        Quadrature point index (0..3).

    Returns
    -------
    dNdX : NDArray, shape (10, 3)
        Shape function gradients w.r.t. reference coordinates X.
    detJ0 : float
        Determinant of the reference Jacobian.

    Raises
    ------
    ValueError
        If det(J0) <= 0 — the element is inverted or degenerate.
    """
    dN_dxi = GRAD_AT_QUAD[q]  # (10, 3)

    # Reference Jacobian: J0 = dX/dxi = X^T @ dN/dxi  ->  (3, 3)
    J0 = X_elem.T @ dN_dxi

    detJ0 = float(np.linalg.det(J0))
    if detJ0 <= 0.0:
        msg = f"Non-positive Jacobian determinant ({detJ0:.6e}) at quadrature point {q}."
        raise ValueError(msg)

    J0_inv = np.linalg.inv(J0)

    # dN/dX = dN/dxi @ J0^{-1}
    dNdX: NDArray = dN_dxi @ J0_inv  # (10, 3)

    return dNdX, detJ0
