"""Row-sum lumped mass for explicit dynamics (Plan B §B7, task P7-1).

Support tier: **experimental**. Explicit dynamics is outside the canonical
MVP-stable compile path (which is static / quasi-static only). See
``README.md`` Support tiers and ``dev/plans/recovery_plan_latex_contract.md``
Phase 1 (R0). Code preserved in tree; not part of the contract surface.


The consistent element mass matrix for a displacement-based FEM is

    M_ab = integral_Omega_e  rho * N_a * N_b  dV

where ``N_a`` are the element shape functions.  For explicit time
integration we lump the consistent mass to a diagonal by row-summing:

    M_a = sum_b M_ab = integral_Omega_e  rho * N_a * (sum_b N_b)  dV
        = integral_Omega_e  rho * N_a  dV

(because the shape functions partition unity, ``sum_b N_b = 1``).  This
is the standard row-sum lumping — it preserves total mass and (for
positive shape functions) gives strictly positive nodal masses.

Each spatial DoF carries the same lumped nodal scalar, so the returned
array has shape ``(n_nodes, 3)`` with identical values in all three
components.  Callers use ``M_inv = 1 / M`` per DoF in the central-
difference update.

Scope
-----
This MVP supports :class:`ElementType.HEX8` only (Plan B §B7).  Higher-
order topologies (TET10, HEX20) need specialised lumping rules (HRZ or
diagonal scaling) and are deferred to a post-B7 follow-up — TET4 is
deferred for symmetry with the rest of the Plan B §B7 scope.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from mechdsl.codegen.hex8_tables import (
    GRAD_AT_QUAD,
    HEX8_QUAD_WEIGHTS,
    SHAPE_AT_QUAD,
)
from mechdsl.ir.mechanics_ir import ElementType

if TYPE_CHECKING:
    from numpy.typing import NDArray

__all__ = ["compute_lumped_mass"]


def compute_lumped_mass(
    coords: NDArray,
    conn: NDArray,
    rho: float,
    element_type: ElementType,
) -> NDArray:
    """Compute the row-sum lumped mass vector.

    Parameters
    ----------
    coords
        Nodal coordinates, shape ``(n_nodes, 3)``.
    conn
        Element connectivity, shape ``(n_elem, n_nodes_per_elem)``.
    rho
        Mass density (constant, isotropic).  Variable-density materials
        are out of scope for the MVP.
    element_type
        Element topology selector.  Only :attr:`ElementType.HEX8` is
        implemented in Plan B phase B7.

    Returns
    -------
    numpy.ndarray
        Lumped mass per DoF, shape ``(n_nodes, 3)``.  All three columns
        carry the same nodal scalar because mass is isotropic across
        translational DoFs.

    Raises
    ------
    NotImplementedError
        When *element_type* is not :attr:`ElementType.HEX8`.  Plan B
        phase B7 scopes lumped mass to Hex8 only; TET4/TET10/HEX20 are a
        post-B7 follow-up.
    ValueError
        When ``coords`` or ``conn`` carry inconsistent shapes, or when
        ``rho`` is non-positive.
    """
    if element_type is not ElementType.HEX8:
        raise NotImplementedError(
            f"Row-sum lumping for {element_type.value} is a Plan B post-B7 follow-up."
        )

    coords = np.asarray(coords, dtype=np.float64)
    conn = np.asarray(conn, dtype=np.int64)

    if coords.ndim != 2 or coords.shape[1] != 3:
        raise ValueError(f"coords must have shape (n_nodes, 3); got {coords.shape}.")
    if conn.ndim != 2 or conn.shape[1] != 8:
        raise ValueError(f"Hex8 connectivity must have shape (n_elem, 8); got {conn.shape}.")
    if rho <= 0.0:
        raise ValueError(f"rho must be positive; got {rho}.")

    n_nodes = coords.shape[0]
    n_elem = conn.shape[0]

    # Scalar lumped nodal mass -- same value for each of the 3 translational DoFs.
    m_node = np.zeros(n_nodes, dtype=np.float64)

    # Loop elements; for each QP compute det(J0) and accumulate
    #     m_a += rho * N_a(xi_q) * det(J0_q) * w_q.
    # With partition of unity sum_b N_b = 1 the element mass sum equals rho * V_e
    # (within float tolerance), so the row-sum lumping conserves total mass.
    for e in range(n_elem):
        X_elem = coords[conn[e]]  # (8, 3)
        for q in range(SHAPE_AT_QUAD.shape[0]):
            # Reference Jacobian J0 = X^T @ dN/dxi
            J0 = X_elem.T @ GRAD_AT_QUAD[q]  # (3, 3)
            detJ0 = float(np.linalg.det(J0))
            if detJ0 <= 0.0:
                raise ValueError(
                    f"Non-positive Jacobian determinant ({detJ0:.6e}) at "
                    f"element {e}, quadrature point {q}."
                )
            w = float(HEX8_QUAD_WEIGHTS[q])
            # Row-sum: m_a += integral rho * N_a * (sum_b N_b) dV
            #                = integral rho * N_a dV  (partition of unity).
            N_q = SHAPE_AT_QUAD[q]  # (8,)
            contrib = rho * N_q * detJ0 * w
            for a in range(8):
                m_node[conn[e, a]] += contrib[a]

    # Broadcast the scalar nodal mass across 3 translational DoFs.
    M = np.repeat(m_node[:, None], 3, axis=1)
    return M
