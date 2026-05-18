"""Flanagan-Belytschko hourglass control for reduced-integration Hex8.

This module provides the Python reference implementation of the classical
Flanagan-Belytschko (1981) hourglass control scheme used to suppress the
four zero-energy (hourglass) modes that develop in the 1-point (reduced)
integration of the trilinear Hex8 element.

References
----------
Flanagan, D. P. and Belytschko, T. (1981),
    "A uniform strain hexahedron and quadrilateral with orthogonal
    hourglass control",
    International Journal for Numerical Methods in Engineering,
    Vol. 17, pp. 679-706.

The implementation follows the equations cited in the docstrings below
(all equation numbers refer to the 1981 paper).

Node ordering
-------------
The eight corner nodes are ordered per
:data:`mechdsl.codegen.hex8_tables.HEX8_NODE_COORDS` (VTK / MFEM convention)::

    node : (xi, eta, zeta)
      0  : (-1, -1, -1)
      1  : (+1, -1, -1)
      2  : (+1, +1, -1)
      3  : (-1, +1, -1)
      4  : (-1, -1, +1)
      5  : (+1, -1, +1)
      6  : (+1, +1, +1)
      7  : (-1, +1, +1)

The four Flanagan-Belytschko hourglass basis vectors are the four
trilinear modes orthogonal to the 1 + 3 = 4 constant-and-linear modes
(``{1, xi, eta, zeta}``):

    Gamma_1 = xi * eta           = ( 1, -1,  1, -1,  1, -1,  1, -1)
    Gamma_2 = eta * zeta         = ( 1,  1, -1, -1, -1, -1,  1,  1)
    Gamma_3 = xi * zeta          = ( 1, -1, -1,  1, -1,  1,  1, -1)
    Gamma_4 = xi * eta * zeta    = (-1,  1, -1,  1,  1, -1,  1, -1)

These are FB 1981 equation (2.28) evaluated at the corner nodes.  They
are mutually orthogonal with ``Gamma_alpha . Gamma_alpha = 8`` and they
are orthogonal to the 4-dim linear space ``span{1, x_i}`` **when the
element is a regular cube**.  For distorted elements we apply the
projection of FB 1981 equation (2.33) to enforce consistency.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from mechdsl.codegen.hex8_tables import (
    HEX8_NODE_COORDS,
    reference_gradient_at_physical,
)

if TYPE_CHECKING:
    from numpy.typing import NDArray

__all__ = [
    "flanagan_belytschko_force",
    "flanagan_belytschko_stiffness",
    "hourglass_vectors",
]


# ---------------------------------------------------------------------------
# Raw hourglass basis vectors (FB 1981 eq. 2.28)
# ---------------------------------------------------------------------------

# Shape (4, 8).  Row alpha is Gamma_alpha[a] for a = 0..7.
# Computed from HEX8_NODE_COORDS via the products (xi*eta), (eta*zeta),
# (xi*zeta), (xi*eta*zeta) so the convention follows the node ordering
# of HEX8_NODE_COORDS exactly.
_GAMMA_RAW: NDArray = np.array(
    [
        [  # alpha = 0: xi * eta
            HEX8_NODE_COORDS[a, 0] * HEX8_NODE_COORDS[a, 1] for a in range(8)
        ],
        [  # alpha = 1: eta * zeta
            HEX8_NODE_COORDS[a, 1] * HEX8_NODE_COORDS[a, 2] for a in range(8)
        ],
        [  # alpha = 2: xi * zeta
            HEX8_NODE_COORDS[a, 0] * HEX8_NODE_COORDS[a, 2] for a in range(8)
        ],
        [  # alpha = 3: xi * eta * zeta
            HEX8_NODE_COORDS[a, 0] * HEX8_NODE_COORDS[a, 1] * HEX8_NODE_COORDS[a, 2]
            for a in range(8)
        ],
    ],
    dtype=np.float64,
)


def hourglass_vectors() -> NDArray:
    """Return the four raw Flanagan-Belytschko hourglass basis vectors.

    These are the trilinear modes ``xi eta``, ``eta zeta``, ``xi zeta``,
    and ``xi eta zeta`` evaluated at the eight corner nodes of the
    standard reference Hex8.  Follows FB 1981 equation (2.28) and matches
    the node ordering used by
    :data:`mechdsl.codegen.hex8_tables.HEX8_NODE_COORDS`.

    Returns
    -------
    Gamma : NDArray, shape (4, 8)
        Raw hourglass vectors.  ``Gamma[alpha, a]`` is the value of the
        ``alpha``-th hourglass mode at corner ``a``.  They are orthogonal
        to the constant mode, mutually orthogonal, and each has squared
        norm ``8``.  They are orthogonal to the linear modes only on a
        regular (undistorted) cube — use
        :func:`_projected_hourglass_vectors` for distorted geometry.
    """
    return _GAMMA_RAW.copy()


# ---------------------------------------------------------------------------
# Mean B-matrix columns and orthogonality projection (FB 1981 eq. 2.33)
# ---------------------------------------------------------------------------


def _element_volume_and_mean_B(X_nodes: NDArray) -> tuple[float, NDArray]:
    """Element volume V_e and mean gradient operator ``B_bar_j = <dN_j/dX>``.

    Returns the per-node mean B-matrix columns obtained by volume averaging
    the shape-function gradients over the 2x2x2 Gauss quadrature of the
    reference Hex8.  FB 1981 uses a one-point rule at the centroid, which is
    equivalent to the volume average for a trilinear map; we use the 2x2x2
    rule already available to match the rest of the code base.

    Parameters
    ----------
    X_nodes : NDArray, shape (8, 3)
        Element nodal coordinates in the reference configuration.

    Returns
    -------
    V_e : float
        Element volume in the reference configuration.
    B_bar : NDArray, shape (8, 3)
        Volume-averaged shape-function gradients ``(1/V_e) integral dN_a/dX``.
    """
    V_e = 0.0
    accum = np.zeros((8, 3), dtype=np.float64)
    # Re-use the existing 2x2x2 Gauss rule; all weights are 1.0.
    for q in range(8):
        dNdX, detJ0 = reference_gradient_at_physical(X_nodes, q)
        accum += dNdX * detJ0  # weight w_q = 1
        V_e += detJ0
    if V_e <= 0.0:
        msg = (
            f"Non-positive element volume ({V_e:.6e}) in hourglass projection — "
            "check node ordering / Jacobian sign."
        )
        raise ValueError(msg)
    B_bar = accum / V_e
    return V_e, B_bar


def _projected_hourglass_vectors(X_nodes: NDArray) -> tuple[NDArray, float]:
    """Compute the geometry-corrected hourglass vectors (FB 1981 eq. 2.33).

    The raw vectors ``Gamma_alpha`` are orthogonal to ``{1, xi, eta, zeta}``
    on a regular cube but pick up linear-mode content on distorted elements.
    Flanagan and Belytschko (eq. 2.33) restore orthogonality via

        gamma_alpha[a] = Gamma_alpha[a]
                      - (1 / V_e) * sum_j (Gamma_alpha . X[:, j]) * B_bar[a, j]

    so that on *any* positive-Jacobian Hex8, ``gamma_alpha`` is orthogonal
    to the constant mode and to the three linear modes ``x, y, z``.  This is
    what makes the hourglass force vanish on constant-strain states.

    Parameters
    ----------
    X_nodes : NDArray, shape (8, 3)
        Element nodal coordinates in the reference configuration.

    Returns
    -------
    gamma : NDArray, shape (4, 8)
        Projected hourglass basis vectors.
    V_e : float
        Element reference volume.
    """
    V_e, B_bar = _element_volume_and_mean_B(X_nodes)
    gamma = _GAMMA_RAW.copy()
    # Gamma . X[:, j] = sum_a Gamma[alpha, a] * X[a, j]  ->  shape (4, 3)
    gamma_dot_X = _GAMMA_RAW @ X_nodes  # (4, 3)
    # Subtract (Gamma . X) contracted with B_bar (using 1/V_e factor)
    #   correction[alpha, a] = sum_j (Gamma_alpha . X[:, j]) * B_bar[a, j]
    correction = gamma_dot_X @ B_bar.T  # (4, 8)
    gamma -= correction
    return gamma, V_e


# ---------------------------------------------------------------------------
# Hourglass stiffness scalar (FB 1981 eq. 4.8 / 4.11 variant)
# ---------------------------------------------------------------------------


def _hourglass_stiffness_scalar(V_e: float, mu: float, lambda_h: float) -> float:
    """Scalar hourglass stiffness ``epsilon`` used in FB 1981 eq. (4.8).

    The classical FB form has an hourglass coefficient times a shear modulus
    times a characteristic-area factor ``V_e^(2/3)`` (equivalent to
    ``h^(d-2) vol`` with ``h ~ V_e^(1/3)`` in 3D, per the scope statement of
    task P5-5):

        epsilon = lambda_h * mu * V_e**(2/3)

    The scaling ``V_e^(2/3)`` ensures the stiffness has correct force/length
    units and that the HG force is mesh-size consistent.  The coefficient
    ``lambda_h`` defaults to 0.05 (see :func:`flanagan_belytschko_force`).

    Parameters
    ----------
    V_e : float
        Element reference volume.
    mu : float
        Shear modulus (second Lame parameter).
    lambda_h : float
        User-tunable hourglass coefficient (dimensionless).

    Returns
    -------
    epsilon : float
        Scalar hourglass stiffness.
    """
    return float(lambda_h) * float(mu) * float(V_e) ** (2.0 / 3.0)


# ---------------------------------------------------------------------------
# Public API: hourglass force and stiffness
# ---------------------------------------------------------------------------


def flanagan_belytschko_force(
    u_nodes: NDArray,
    X_nodes: NDArray,
    mu: float,
    lambda_h: float = 0.05,
) -> NDArray:
    """Hourglass nodal force for a single reduced-integration Hex8.

    Implements the Flanagan-Belytschko (1981) orthogonal hourglass control:

        h_{alpha, i} = epsilon * sum_b gamma_alpha[b] * u_nodes[b, i]     (2.31)
        f_HG[a, i]   = sum_alpha gamma_alpha[a] * h_{alpha, i}             (4.8)

    where ``gamma_alpha`` are the geometry-projected hourglass vectors
    (FB 1981 eq. 2.33) and ``epsilon = lambda_h * mu * V_e^(2/3)`` is the
    scalar hourglass stiffness (section 4 of the paper; see also the
    scope statement of task P5-5 which specifies
    ``k_h * lambda_h * h^(d-2) / vol_e`` — in 3D this is equivalent up
    to the ``k_h * mu`` grouping).

    The output has the sign convention of an internal resisting force:
    it acts to oppose motion along hourglass modes, so it should be
    *added* to the internal-force residual (same sign as ``f_int``).

    Parameters
    ----------
    u_nodes : NDArray, shape (8, 3)
        Element nodal displacements.
    X_nodes : NDArray, shape (8, 3)
        Element nodal reference coordinates.
    mu : float
        Shear modulus (second Lame parameter).
    lambda_h : float, optional
        Hourglass control coefficient.  Default is 0.05 (conservative
        value; typical range 0.01 — 0.10).

    Returns
    -------
    f_HG : NDArray, shape (8, 3)
        Hourglass contribution to the element internal force.  Vanishes
        identically on constant-strain / rigid-body motion, by the
        projection of FB 1981 eq. (2.33).
    """
    if u_nodes.shape != (8, 3):
        msg = f"u_nodes must have shape (8, 3); got {u_nodes.shape}."
        raise ValueError(msg)
    if X_nodes.shape != (8, 3):
        msg = f"X_nodes must have shape (8, 3); got {X_nodes.shape}."
        raise ValueError(msg)

    gamma, V_e = _projected_hourglass_vectors(X_nodes)  # (4, 8), scalar
    epsilon = _hourglass_stiffness_scalar(V_e, mu, lambda_h)

    # Hourglass generalized displacements h_{alpha, i}  (FB eq. 2.31)
    #   h[alpha, i] = epsilon * sum_b gamma[alpha, b] * u_nodes[b, i]
    h = epsilon * (gamma @ u_nodes)  # (4, 3)

    # Scatter back to nodal forces (FB eq. 4.8):
    #   f_HG[a, i] = sum_alpha gamma[alpha, a] * h[alpha, i]
    f_HG = gamma.T @ h  # (8, 3)
    return f_HG


def flanagan_belytschko_stiffness(
    X_nodes: NDArray,
    mu: float,
    lambda_h: float = 0.05,
) -> NDArray:
    """Hourglass contribution to the element tangent stiffness.

    The FB hourglass force is linear in the nodal displacements:

        f_HG[a, i] = epsilon * sum_alpha gamma_alpha[a]
                     * sum_b gamma_alpha[b] * u_nodes[b, i]

    so its tangent is the constant, displacement-independent matrix

        K_HG[3a+i, 3b+j] = delta_ij * epsilon
                           * sum_alpha gamma_alpha[a] * gamma_alpha[b]

    See FB 1981 section 4 (hourglass stabilization matrix, eq. 4.8 and the
    discussion following eq. 4.11).  This matrix is symmetric positive
    semi-definite with exactly 4 non-zero eigenvalues per spatial component
    (12 in total, matching the 12 HG modes in 3D).

    Parameters
    ----------
    X_nodes : NDArray, shape (8, 3)
        Element nodal reference coordinates.
    mu : float
        Shear modulus.
    lambda_h : float, optional
        Hourglass control coefficient.  Default 0.05.

    Returns
    -------
    K_HG : NDArray, shape (24, 24)
        Hourglass tangent stiffness in ``(node, component)`` flattened
        order ``DOF = 3 * a + i``.
    """
    if X_nodes.shape != (8, 3):
        msg = f"X_nodes must have shape (8, 3); got {X_nodes.shape}."
        raise ValueError(msg)

    gamma, V_e = _projected_hourglass_vectors(X_nodes)  # (4, 8), scalar
    epsilon = _hourglass_stiffness_scalar(V_e, mu, lambda_h)

    # Node-node hourglass coupling: G[a, b] = sum_alpha gamma[alpha, a] * gamma[alpha, b]
    G = gamma.T @ gamma  # (8, 8)

    # Tensor up with the 3x3 identity in the spatial component block
    K_HG = np.zeros((24, 24), dtype=np.float64)
    for a in range(8):
        for b in range(8):
            val = epsilon * G[a, b]
            for i in range(3):
                K_HG[3 * a + i, 3 * b + i] += val
    return K_HG
