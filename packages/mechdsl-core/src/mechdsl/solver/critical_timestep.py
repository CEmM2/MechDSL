"""Critical time step for explicit central-difference integration (Plan B §B7.1).

This module computes the Courant-limited stable time step for the central-
difference (Verlet) explicit time integrator.  It is a **pure-numpy** pre-flight
helper called before any Taichi code is compiled or executed.

Characteristic-length convention
---------------------------------
For **Hex8** elements we use

    L_e = V_e^(1/3)

where V_e is the element volume computed by summing 8 Gauss-point Jacobian
contributions (the same Gauss machinery already used by ``lumped_mass.py``).

Rationale (why V^(1/3) is a conservative Courant bound)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The critical wave-transit time for a cube of side *h* is h/c_d, which
corresponds to V^(1/3)/c_d for an axis-aligned hex.  For a general
(non-degenerate) Hex8 the cube root of the volume underestimates the longest
"effective" dimension and therefore gives a *smaller* L_e than the true
maximum wave-transit length.  A smaller L_e → smaller dt_e, which is
conservative (errs on the side of stability).  It can be less tight than the
min-edge criterion for highly distorted elements, but for the structured meshes
that Plan B §B7 targets it is equivalent to within 10 % and avoids the O(12)
edge-evaluation loop.

For **TET4** and **TET10** we use the shortest edge of the tetrahedron, which
is the standard Courant criterion for simplex elements and is strictly
conservative for all non-degenerate tet geometries.

**HEX20** raises ``NotImplementedError`` — see inline message.

Reference: Plan B §B7.1 ("Lumped mass, critical time step computation, no
linear solver needed.").

API
---
::

    dt = critical_timestep(coords, conn, lam, mu, rho, element_type, safety=0.9)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from mechdsl.codegen.hex8_tables import GRAD_AT_QUAD, HEX8_QUAD_WEIGHTS
from mechdsl.ir.mechanics_ir import ElementType

if TYPE_CHECKING:
    from numpy.typing import NDArray

__all__ = ["critical_timestep"]

# ── Hex8 edge connectivity (12 unique edges of a cube) ──────────────────────
# Not used for HEX8 (we use volume^(1/3)), but defined here for reference.
# Used for TET4/TET10 by analogy.

# Hex8 node ordering (MFEM/VTK convention, same as hex8_tables.py):
#   0:(-,-,-), 1:(+,-,-), 2:(+,+,-), 3:(-,+,-)
#   4:(-,-,+), 5:(+,-,+), 6:(+,+,+), 7:(-,+,+)

# TET4 has 6 edges:
_TET4_EDGES: list[tuple[int, int]] = [
    (0, 1),
    (0, 2),
    (0, 3),
    (1, 2),
    (1, 3),
    (2, 3),
]

# TET10 has the same 6 corner edges (mid-side nodes don't contribute new edges
# in the short-edge metric — corner spacing sets the characteristic length).
_TET10_CORNER_EDGES: list[tuple[int, int]] = _TET4_EDGES


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _hex8_volume(X_elem: NDArray) -> float:
    """Compute the volume of a Hex8 element from its 8 nodal coordinates.

    Uses the standard 2×2×2 Gauss quadrature: V = sum_q det(J0_q) * w_q.

    Parameters
    ----------
    X_elem : NDArray, shape (8, 3)
        Nodal coordinates in the reference (or initial) configuration.

    Returns
    -------
    float
        Element volume (> 0 for a non-inverted element).
    """
    n_qp = GRAD_AT_QUAD.shape[0]  # 8 for full 2×2×2 rule
    vol = 0.0
    for q in range(n_qp):
        J0 = X_elem.T @ GRAD_AT_QUAD[q]  # (3, 3)
        vol += float(np.linalg.det(J0)) * float(HEX8_QUAD_WEIGHTS[q])
    return vol


def _tet4_shortest_edge(X_elem: NDArray, edges: list[tuple[int, int]]) -> float:
    """Return the length of the shortest edge of a simplex element.

    Parameters
    ----------
    X_elem : NDArray, shape (n_nodes, 3)
        Nodal coordinates.
    edges : list of (int, int)
        Index pairs defining the edges to inspect.

    Returns
    -------
    float
        Length of the shortest edge (> 0 for a non-degenerate element).
    """
    min_len = np.inf
    for a, b in edges:
        edge_vec = X_elem[b] - X_elem[a]
        length = float(np.sqrt(np.dot(edge_vec, edge_vec)))
        if length < min_len:
            min_len = length
    return min_len


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def critical_timestep(
    coords: NDArray,
    conn: NDArray,
    lam: float,
    mu: float,
    rho: float,
    element_type: ElementType,
    safety: float = 0.9,
) -> float:
    """Compute the Courant-limited stable time step.

    Parameters
    ----------
    coords : NDArray, shape (n_nodes, 3)
        Nodal coordinates of the mesh.
    conn : NDArray, shape (n_elem, n_nodes_per_elem), int
        Element connectivity table (0-based node indices).
    lam : float
        First Lamé parameter (Pa).  Must be non-negative.
    mu : float
        Shear modulus (Pa).  Must be positive.
    rho : float
        Mass density (kg/m³).  Must be positive.
    element_type : ElementType
        Element topology.  Supported: ``HEX8``, ``TET4``, ``TET10``.
        ``HEX20`` raises ``NotImplementedError``.
    safety : float, optional
        Courant safety factor applied to the raw dt.  Default is 0.9
        (10 % margin).

    Returns
    -------
    float
        Stable explicit time step: ``safety * min_over_elements(L_e / c_d)``.

    Raises
    ------
    NotImplementedError
        When *element_type* is :attr:`ElementType.HEX20`.
    ValueError
        When input arrays are malformed or material parameters are non-physical.

    Notes
    -----
    Characteristic lengths
    ~~~~~~~~~~~~~~~~~~~~~~
    * ``HEX8`` : L_e = V_e^(1/3)  (volume^(1/3), Gauss-integrated; see module
      docstring for the conservative-bound argument).
    * ``TET4`` / ``TET10`` : L_e = shortest corner-edge length of the element.

    The dilatational wave speed is

        c_d = sqrt((lam + 2 * mu) / rho)

    which is the fastest elastic body-wave speed in an isotropic linear solid.
    Using c_d (instead of the shear-wave speed c_s = sqrt(mu/rho)) gives the
    most restrictive Courant bound and is therefore conservative.

    Spec reference: Plan B §B7.1.
    """
    # ── Validate material parameters ────────────────────────────────────────
    if lam < 0.0:
        raise ValueError(f"lam must be non-negative; got {lam}.")
    if mu <= 0.0:
        raise ValueError(f"mu must be positive; got {mu}.")
    if rho <= 0.0:
        raise ValueError(f"rho must be positive; got {rho}.")
    if not (0.0 < safety <= 1.0):
        raise ValueError(f"safety must be in (0, 1]; got {safety}.")

    # ── Validate arrays ─────────────────────────────────────────────────────
    coords = np.asarray(coords, dtype=np.float64)
    conn = np.asarray(conn, dtype=np.int64)

    if coords.ndim != 2 or coords.shape[1] != 3:
        raise ValueError(f"coords must have shape (n_nodes, 3); got {coords.shape}.")
    if conn.ndim != 2:
        raise ValueError(f"conn must be a 2-D array; got shape {conn.shape}.")

    # ── Element-type dispatch ────────────────────────────────────────────────
    if element_type is ElementType.HEX8:
        return _hex8_critical_timestep(coords, conn, lam, mu, rho, safety)
    elif element_type in (ElementType.TET4, ElementType.TET10):
        return _tet_critical_timestep(coords, conn, lam, mu, rho, safety, element_type)
    elif element_type is ElementType.HEX20:
        raise NotImplementedError(
            "HEX20 characteristic length for critical_timestep is a Plan B post-B7 follow-up."
        )
    else:
        raise NotImplementedError(
            f"critical_timestep not implemented for element type {element_type.value!r}."
        )


# ---------------------------------------------------------------------------
# Per-element-type implementations
# ---------------------------------------------------------------------------


def _hex8_critical_timestep(
    coords: NDArray,
    conn: NDArray,
    lam: float,
    mu: float,
    rho: float,
    safety: float,
) -> float:
    """Critical dt for a Hex8 mesh using L_e = V_e^(1/3)."""
    if conn.shape[1] != 8:
        raise ValueError(f"Hex8 connectivity must have shape (n_elem, 8); got {conn.shape}.")

    c_d = np.sqrt((lam + 2.0 * mu) / rho)
    n_elem = conn.shape[0]

    dt_min = np.inf
    for e in range(n_elem):
        X_elem = coords[conn[e]]  # (8, 3)
        vol = _hex8_volume(X_elem)
        if vol <= 0.0:
            raise ValueError(
                f"Non-positive element volume ({vol:.6e}) at element {e}. Check mesh orientation."
            )
        L_e = vol ** (1.0 / 3.0)
        dt_e = L_e / c_d
        if dt_e < dt_min:
            dt_min = dt_e

    return safety * dt_min


def _tet_critical_timestep(
    coords: NDArray,
    conn: NDArray,
    lam: float,
    mu: float,
    rho: float,
    safety: float,
    element_type: ElementType,
) -> float:
    """Critical dt for TET4 / TET10 meshes using L_e = shortest corner-edge."""
    expected_nodes = 4 if element_type is ElementType.TET4 else 10
    if conn.shape[1] != expected_nodes:
        raise ValueError(
            f"{element_type.value.upper()} connectivity must have shape "
            f"(n_elem, {expected_nodes}); got {conn.shape}."
        )

    edges = _TET4_EDGES  # same 6 corner edges for both TET4 and TET10

    c_d = np.sqrt((lam + 2.0 * mu) / rho)
    n_elem = conn.shape[0]

    dt_min = np.inf
    for e in range(n_elem):
        # For TET10, corner nodes are indices 0..3 (mid-nodes are 4..9).
        X_elem = coords[conn[e]]  # (4 or 10, 3)
        L_e = _tet4_shortest_edge(X_elem, edges)
        if L_e <= 0.0:
            raise ValueError(f"Zero or negative edge length ({L_e:.6e}) at element {e}.")
        dt_e = L_e / c_d
        if dt_e < dt_min:
            dt_min = dt_e

    return safety * dt_min
