"""Pre-computed static tables for Hex20 element code generation.

Hex20 serendipity hexahedron: 20 nodes (8 corners + 12 edge midpoints),
3x3x3 = 27-point Gauss quadrature.

Reference element convention (MFEM/VTK/ParaView Hex20 ordering):

  Corner nodes 0..7 (same as Hex8, vertices of [-1,1]^3):
    N0  = (-1, -1, -1)   N1  = (+1, -1, -1)
    N2  = (+1, +1, -1)   N3  = (-1, +1, -1)
    N4  = (-1, -1, +1)   N5  = (+1, -1, +1)
    N6  = (+1, +1, +1)   N7  = (-1, +1, +1)

  Edge midpoint nodes 8..19 (VTK Hex20 ordering):
    N8  = ( 0, -1, -1)  midpoint N0-N1
    N9  = (+1,  0, -1)  midpoint N1-N2
    N10 = ( 0, +1, -1)  midpoint N3-N2
    N11 = (-1,  0, -1)  midpoint N0-N3
    N12 = ( 0, -1, +1)  midpoint N4-N5
    N13 = (+1,  0, +1)  midpoint N5-N6
    N14 = ( 0, +1, +1)  midpoint N7-N6
    N15 = (-1,  0, +1)  midpoint N4-N7
    N16 = (-1, -1,  0)  midpoint N0-N4
    N17 = (+1, -1,  0)  midpoint N1-N5
    N18 = (+1, +1,  0)  midpoint N2-N6
    N19 = (-1, +1,  0)  midpoint N3-N7

Serendipity shape functions (Bathe §4 / Zienkiewicz):
  Corner node a with parametric coords (xi_a, eta_a, zeta_a) in {-1,+1}^3:
    N_a = (1/8)(1 + xi_a xi)(1 + eta_a eta)(1 + zeta_a zeta)(xi_a xi + eta_a eta + zeta_a zeta - 2)

  Edge midpoint nodes (zero in one natural coordinate):
    (0, eta_a, zeta_a): N = (1/4)(1 - xi^2)(1 + eta_a eta)(1 + zeta_a zeta)
    (xi_a, 0, zeta_a): N = (1/4)(1 + xi_a xi)(1 - eta^2)(1 + zeta_a zeta)
    (xi_a, eta_a, 0):  N = (1/4)(1 + xi_a xi)(1 + eta_a eta)(1 - zeta^2)

3x3x3 Gauss quadrature (27 points):
  1-D nodes: xi_i in {-sqrt(3/5), 0, +sqrt(3/5)}, weights w_i in {5/9, 8/9, 5/9}.
  3-D tensor product: 27 points, 27 weights w_i*w_j*w_k.
  Sum of weights = (5/9 + 8/9 + 5/9)^3 = 2^3 = 8 (volume of [-1,1]^3).

JIT budget note:
  27 quadrature points x 20 nodes = 540 element-level ops per quadrature traversal.
  This is close to the 512-line-per-@ti.func budget (see .claude/rules/codegen.md).
  When emitting Taichi kernel code for Hex20, the element-level inner loop MUST be
  split into sub-functions (e.g., one per quadrature row or per group of nodes).
  Sub-function split strategy is deferred to Plan B phase B5 (JIT budget restructure).
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from numpy.typing import NDArray

# ---------------------------------------------------------------------------
# Reference node coordinates  (MFEM/VTK convention)
# ---------------------------------------------------------------------------

HEX20_NODE_COORDS: NDArray = np.array(
    [
        # Corner nodes 0..7
        [-1.0, -1.0, -1.0],  # N0
        [+1.0, -1.0, -1.0],  # N1
        [+1.0, +1.0, -1.0],  # N2
        [-1.0, +1.0, -1.0],  # N3
        [-1.0, -1.0, +1.0],  # N4
        [+1.0, -1.0, +1.0],  # N5
        [+1.0, +1.0, +1.0],  # N6
        [-1.0, +1.0, +1.0],  # N7
        # Edge midpoint nodes 8..19
        [0.0, -1.0, -1.0],  # N8  — midpoint N0-N1
        [+1.0, 0.0, -1.0],  # N9  — midpoint N1-N2
        [0.0, +1.0, -1.0],  # N10 — midpoint N3-N2
        [-1.0, 0.0, -1.0],  # N11 — midpoint N0-N3
        [0.0, -1.0, +1.0],  # N12 — midpoint N4-N5
        [+1.0, 0.0, +1.0],  # N13 — midpoint N5-N6
        [0.0, +1.0, +1.0],  # N14 — midpoint N7-N6
        [-1.0, 0.0, +1.0],  # N15 — midpoint N4-N7
        [-1.0, -1.0, 0.0],  # N16 — midpoint N0-N4
        [+1.0, -1.0, 0.0],  # N17 — midpoint N1-N5
        [+1.0, +1.0, 0.0],  # N18 — midpoint N2-N6
        [-1.0, +1.0, 0.0],  # N19 — midpoint N3-N7
    ],
    dtype=np.float64,
)  # shape (20, 3)

# ---------------------------------------------------------------------------
# Shape function evaluation
# ---------------------------------------------------------------------------

# Corner node parametric coordinates — (xi_a, eta_a, zeta_a) in {-1,+1}^3
_CORNER_COORDS: NDArray = HEX20_NODE_COORDS[:8]

# Edge midpoint node parametric coordinates with their "zero axis" index
# Each entry: (node_index, xi_a, eta_a, zeta_a, zero_axis)
# zero_axis: 0=xi, 1=eta, 2=zeta
_EDGE_DATA: list[tuple[int, float, float, float, int]] = [
    (8, 0.0, -1.0, -1.0, 0),  # N8:  xi=0,  edge N0-N1
    (9, +1.0, 0.0, -1.0, 1),  # N9:  eta=0, edge N1-N2
    (10, 0.0, +1.0, -1.0, 0),  # N10: xi=0,  edge N3-N2
    (11, -1.0, 0.0, -1.0, 1),  # N11: eta=0, edge N0-N3
    (12, 0.0, -1.0, +1.0, 0),  # N12: xi=0,  edge N4-N5
    (13, +1.0, 0.0, +1.0, 1),  # N13: eta=0, edge N5-N6
    (14, 0.0, +1.0, +1.0, 0),  # N14: xi=0,  edge N7-N6
    (15, -1.0, 0.0, +1.0, 1),  # N15: eta=0, edge N4-N7
    (16, -1.0, -1.0, 0.0, 2),  # N16: zeta=0, edge N0-N4
    (17, +1.0, -1.0, 0.0, 2),  # N17: zeta=0, edge N1-N5
    (18, +1.0, +1.0, 0.0, 2),  # N18: zeta=0, edge N2-N6
    (19, -1.0, +1.0, 0.0, 2),  # N19: zeta=0, edge N3-N7
]


def shape_functions(xi: float, eta: float, zeta: float) -> NDArray:
    """Evaluate 20 Hex20 serendipity shape functions at a parametric point.

    Corner node formula (Bathe §4):
      N_a = (1/8)(1 + xi_a xi)(1 + eta_a eta)(1 + zeta_a zeta)(xi_a xi + eta_a eta + zeta_a zeta - 2)

    Edge midpoint formulas:
      xi=0 node:   N = (1/4)(1 - xi^2)(1 + eta_a eta)(1 + zeta_a zeta)
      eta=0 node:  N = (1/4)(1 + xi_a xi)(1 - eta^2)(1 + zeta_a zeta)
      zeta=0 node: N = (1/4)(1 + xi_a xi)(1 + eta_a eta)(1 - zeta^2)

    Returns shape (20,).
    """
    N = np.empty(20, dtype=np.float64)

    # Corner nodes 0..7
    for a in range(8):
        xi_a, eta_a, zeta_a = (
            float(_CORNER_COORDS[a, 0]),
            float(_CORNER_COORDS[a, 1]),
            float(_CORNER_COORDS[a, 2]),
        )
        N[a] = (
            0.125
            * (1.0 + xi_a * xi)
            * (1.0 + eta_a * eta)
            * (1.0 + zeta_a * zeta)
            * (xi_a * xi + eta_a * eta + zeta_a * zeta - 2.0)
        )

    # Edge midpoint nodes 8..19
    for node_idx, xi_a, eta_a, zeta_a, zero_axis in _EDGE_DATA:
        if zero_axis == 0:  # xi = 0
            N[node_idx] = 0.25 * (1.0 - xi * xi) * (1.0 + eta_a * eta) * (1.0 + zeta_a * zeta)
        elif zero_axis == 1:  # eta = 0
            N[node_idx] = 0.25 * (1.0 + xi_a * xi) * (1.0 - eta * eta) * (1.0 + zeta_a * zeta)
        else:  # zeta = 0
            N[node_idx] = 0.25 * (1.0 + xi_a * xi) * (1.0 + eta_a * eta) * (1.0 - zeta * zeta)

    return N


def shape_gradients(xi: float, eta: float, zeta: float) -> NDArray:
    """Evaluate shape function gradients at a parametric point.

    Returns (20, 3) with columns [dN/dxi, dN/deta, dN/dzeta].

    Corner node derivatives (from the serendipity formula):
      Let A = 1 + xi_a xi,  B = 1 + eta_a eta,  C = 1 + zeta_a zeta,  S = xi_a xi + eta_a eta + zeta_a zeta - 2
      N_a = (1/8) A B C S
      dN_a/dxi   = (1/8)[xi_a B C S + A B C xi_a]  = (1/8) xi_a B C (S + A) = (1/8) xi_a B C (2 xi_a xi + eta_a eta + zeta_a zeta - 1)
      dN_a/deta  = (1/8) eta_a A C (xi_a xi + 2 eta_a eta + zeta_a zeta - 1)
      dN_a/dzeta = (1/8) zeta_a A B (xi_a xi + eta_a eta + 2 zeta_a zeta - 1)

    Edge midpoint node derivatives:
      xi=0 node:   N = (1/4)(1 - xi^2)(1 + eta_a eta)(1 + zeta_a zeta)
        dN/dxi   = (1/4)(-2 xi)(1 + eta_a eta)(1 + zeta_a zeta)
        dN/deta  = (1/4)(1 - xi^2)(eta_a)(1 + zeta_a zeta)
        dN/dzeta = (1/4)(1 - xi^2)(1 + eta_a eta)(zeta_a)

      eta=0 node:  N = (1/4)(1 + xi_a xi)(1 - eta^2)(1 + zeta_a zeta)
        dN/dxi   = (1/4)(xi_a)(1 - eta^2)(1 + zeta_a zeta)
        dN/deta  = (1/4)(1 + xi_a xi)(-2 eta)(1 + zeta_a zeta)
        dN/dzeta = (1/4)(1 + xi_a xi)(1 - eta^2)(zeta_a)

      zeta=0 node: N = (1/4)(1 + xi_a xi)(1 + eta_a eta)(1 - zeta^2)
        dN/dxi   = (1/4)(xi_a)(1 + eta_a eta)(1 - zeta^2)
        dN/deta  = (1/4)(1 + xi_a xi)(eta_a)(1 - zeta^2)
        dN/dzeta = (1/4)(1 + xi_a xi)(1 + eta_a eta)(-2 zeta)
    """
    G = np.empty((20, 3), dtype=np.float64)

    # Corner nodes 0..7
    for a in range(8):
        xi_a = float(_CORNER_COORDS[a, 0])
        eta_a = float(_CORNER_COORDS[a, 1])
        zeta_a = float(_CORNER_COORDS[a, 2])
        A = 1.0 + xi_a * xi
        B = 1.0 + eta_a * eta
        C = 1.0 + zeta_a * zeta
        G[a, 0] = 0.125 * xi_a * B * C * (2.0 * xi_a * xi + eta_a * eta + zeta_a * zeta - 1.0)
        G[a, 1] = 0.125 * eta_a * A * C * (xi_a * xi + 2.0 * eta_a * eta + zeta_a * zeta - 1.0)
        G[a, 2] = 0.125 * zeta_a * A * B * (xi_a * xi + eta_a * eta + 2.0 * zeta_a * zeta - 1.0)

    # Edge midpoint nodes 8..19
    for node_idx, xi_a, eta_a, zeta_a, zero_axis in _EDGE_DATA:
        if zero_axis == 0:  # xi = 0
            B = 1.0 + eta_a * eta
            C = 1.0 + zeta_a * zeta
            G[node_idx, 0] = 0.25 * (-2.0 * xi) * B * C
            G[node_idx, 1] = 0.25 * (1.0 - xi * xi) * eta_a * C
            G[node_idx, 2] = 0.25 * (1.0 - xi * xi) * B * zeta_a
        elif zero_axis == 1:  # eta = 0
            A = 1.0 + xi_a * xi
            C = 1.0 + zeta_a * zeta
            G[node_idx, 0] = 0.25 * xi_a * (1.0 - eta * eta) * C
            G[node_idx, 1] = 0.25 * A * (-2.0 * eta) * C
            G[node_idx, 2] = 0.25 * A * (1.0 - eta * eta) * zeta_a
        else:  # zeta = 0
            A = 1.0 + xi_a * xi
            B = 1.0 + eta_a * eta
            G[node_idx, 0] = 0.25 * xi_a * B * (1.0 - zeta * zeta)
            G[node_idx, 1] = 0.25 * A * eta_a * (1.0 - zeta * zeta)
            G[node_idx, 2] = 0.25 * A * B * (-2.0 * zeta)

    return G


# ---------------------------------------------------------------------------
# 3x3x3 Gauss quadrature (27 points, tensor product)
# ---------------------------------------------------------------------------

_SQRT35 = math.sqrt(3.0 / 5.0)  # ≈ 0.7745966692414834

# 1-D Gauss points and weights
_GP_1D = np.array([-_SQRT35, 0.0, +_SQRT35], dtype=np.float64)
_GW_1D = np.array([5.0 / 9.0, 8.0 / 9.0, 5.0 / 9.0], dtype=np.float64)

# Build 27 tensor-product points and weights
HEX20_QUAD_POINTS: NDArray = np.array(
    [[xi, eta, zeta] for xi in _GP_1D for eta in _GP_1D for zeta in _GP_1D],
    dtype=np.float64,
)  # shape (27, 3)

HEX20_QUAD_WEIGHTS: NDArray = np.array(
    [wx * wy * wz for wx in _GW_1D for wy in _GW_1D for wz in _GW_1D],
    dtype=np.float64,
)  # shape (27,)

# ---------------------------------------------------------------------------
# Pre-evaluated tables (computed once at module load time)
# ---------------------------------------------------------------------------

# SHAPE_AT_QUAD[q, a] = N_a(xi_q, eta_q, zeta_q)
SHAPE_AT_QUAD: NDArray = np.array(
    [shape_functions(float(pt[0]), float(pt[1]), float(pt[2])) for pt in HEX20_QUAD_POINTS],
    dtype=np.float64,
)  # shape (27, 20)

# GRAD_AT_QUAD[q, a, i] = dN_a / d(xi_i) at quadrature point q
GRAD_AT_QUAD: NDArray = np.array(
    [shape_gradients(float(pt[0]), float(pt[1]), float(pt[2])) for pt in HEX20_QUAD_POINTS],
    dtype=np.float64,
)  # shape (27, 20, 3)

# ---------------------------------------------------------------------------
# Physical-space gradient computation
# ---------------------------------------------------------------------------


def reference_gradient_at_physical(
    X_elem: NDArray,  # (20, 3) element node coordinates in reference config
    q: int,  # quadrature point index (0..26)
) -> tuple[NDArray, float]:
    """Compute dN/dX and det(J0) at quadrature point *q* for a Hex20 element.

    The reference Jacobian maps from parametric to physical reference space:
        J0 = X^T @ dN/dxi   (3x3)

    Shape function gradients in physical reference space:
        dN/dX = dN/dxi @ J0^{-1}

    Parameters
    ----------
    X_elem : NDArray, shape (20, 3)
        Element nodal coordinates in the reference configuration.
    q : int
        Quadrature point index (0..26).

    Returns
    -------
    dNdX : NDArray, shape (20, 3)
        Shape function gradients w.r.t. reference coordinates X.
    detJ0 : float
        Determinant of the reference Jacobian.

    Raises
    ------
    ValueError
        If det(J0) <= 0 — the element is inverted or degenerate.
    """
    dN_dxi = GRAD_AT_QUAD[q]  # (20, 3)

    # Reference Jacobian: J0 = dX/dxi = X^T @ dN/dxi  ->  (3, 3)
    J0 = X_elem.T @ dN_dxi

    detJ0 = float(np.linalg.det(J0))
    if detJ0 <= 0.0:
        msg = f"Non-positive Jacobian determinant ({detJ0:.6e}) at quadrature point {q}."
        raise ValueError(msg)

    J0_inv = np.linalg.inv(J0)

    # dN/dX = dN/dxi @ J0^{-1}
    dNdX: NDArray = dN_dxi @ J0_inv  # (20, 3)

    return dNdX, detJ0
