"""Hex8 reference element: shape functions, gradients, quadrature (PlanJune14 PJ-0).

Trilinear 8-node hexahedron with 2×2×2 Gauss quadrature — the minimal element
the SVK spike (PJ-1) and the matrix-free tangent operator build on. Shape
functions/gradients are ``@ti.func`` (call from a kernel); quadrature tables are
Python constants iterated with ``ti.static``. Standard node ordering (corner
signs below). Adapted from NumerixWeave ``apps/tifem`` ``Ref_elements/HEX8``.
"""

import taichi as ti

N_NODES = 8
DIM = 3
N_QP = 8

# Natural-coordinate corner signs (standard Hex8 node ordering).
_CORNERS = (
    (-1.0, -1.0, -1.0),
    (1.0, -1.0, -1.0),
    (1.0, 1.0, -1.0),
    (-1.0, 1.0, -1.0),
    (-1.0, -1.0, 1.0),
    (1.0, -1.0, 1.0),
    (1.0, 1.0, 1.0),
    (-1.0, 1.0, 1.0),
)

_G = 1.0 / (3.0**0.5)
# 2×2×2 Gauss points (corner sign pattern, scaled by 1/√3) and unit weights.
QUAD_POINTS = tuple((sx * _G, sy * _G, sz * _G) for (sx, sy, sz) in _CORNERS)
QUAD_WEIGHTS = (1.0,) * N_QP


@ti.func
def shape(xi, eta, zeta):
    """Trilinear shape functions at natural coords → ``ti.Vector(8)``."""
    N = ti.Vector.zero(ti.f64, 8)
    for a in ti.static(range(8)):
        sx, sy, sz = ti.static(_CORNERS[a])
        N[a] = 0.125 * (1.0 + sx * xi) * (1.0 + sy * eta) * (1.0 + sz * zeta)
    return N


@ti.func
def shape_grad_natural(xi, eta, zeta):
    """``∂N_a/∂(ξ,η,ζ)`` → ``ti.Matrix(8, 3)``."""
    dN = ti.Matrix.zero(ti.f64, 8, 3)
    for a in ti.static(range(8)):
        sx, sy, sz = ti.static(_CORNERS[a])
        dN[a, 0] = 0.125 * sx * (1.0 + sy * eta) * (1.0 + sz * zeta)
        dN[a, 1] = 0.125 * sy * (1.0 + sx * xi) * (1.0 + sz * zeta)
        dN[a, 2] = 0.125 * sz * (1.0 + sx * xi) * (1.0 + sy * eta)
    return dN
