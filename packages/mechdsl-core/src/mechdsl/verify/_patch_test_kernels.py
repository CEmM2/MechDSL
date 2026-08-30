"""Internal reference kernels for the parametric patch test (Plan B §B5.7).

Provides minimal single-element SVK internal-force kernels for every element
topology supported by :class:`mechdsl.ir.element_factory.ElementFactory`.
Each kernel uses the :class:`~mechdsl.ir.element_ir.BasisFunctions` and
:class:`~mechdsl.ir.element_ir.QuadratureRule` carried by the element IR,
evaluating shape gradients at each parametric quadrature point directly —
this avoids coupling the patch-test kernel to the pre-tabulated
``GRAD_AT_QUAD`` arrays, which are full-integration-only for Hex8.

Design notes
------------
* These are *not* public API.  They exist purely to support
  :func:`mechdsl.verify.patch_test.run_patch_test_parametric`.
* For Hex8, the canonical ground-truth kernel is
  :mod:`tests.ref.ref_hex8_elastic`; these helpers mirror its structure
  but stay inside the ``mechdsl`` package so the verify module has no
  reverse dependency on ``tests/``.
* For Hex8 reduced integration, :func:`element_svk_internal_force`
  returns only the SVK contribution at the 1-point centroid.  The
  Flanagan-Belytschko hourglass force
  (:func:`mechdsl.codegen.hourglass.flanagan_belytschko_force`) is added
  by :func:`run_patch_test_parametric` when the element IR requests it.

See ``dev/design_docs/PLAN-B.md §B5.7`` for the patch-test acceptance
specification and the list of supported ``(topology, integration,
hourglass)`` triples.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from mechdsl.lib.tensor_ops import deformation_gradient, green_lagrange

if TYPE_CHECKING:
    from numpy.typing import NDArray

    from mechdsl.ir.element_ir import ElementIR


_I3 = np.eye(3, dtype=np.float64)


# ---------------------------------------------------------------------------
# Reference-element node layouts  (single-element patch-test meshes)
# ---------------------------------------------------------------------------


def reference_nodes(topology: str) -> NDArray:
    """Return the canonical reference nodal coordinates for one element.

    The patch test uses a single element whose nodal coordinates are the
    element's own reference-space coordinates (i.e. the reference and
    physical configurations coincide).  A positive-Jacobian element layout
    is sufficient for the mathematical patch test: a constant Green-
    Lagrange strain reproduces a zero interior force.

    Parameters
    ----------
    topology
        One of ``"hex8"``, ``"tet4"``, ``"tet10"``, ``"hex20"``.

    Returns
    -------
    NDArray, shape (n_nodes, 3)
        Nodal coordinates in the reference configuration.
    """
    if topology == "hex8":
        from mechdsl.codegen.hex8_tables import HEX8_NODE_COORDS

        return HEX8_NODE_COORDS.copy()
    if topology == "tet4":
        from mechdsl.codegen.tet4_tables import TET4_NODE_COORDS

        return TET4_NODE_COORDS.copy()
    if topology == "tet10":
        from mechdsl.codegen.tet10_tables import TET10_NODE_COORDS

        return TET10_NODE_COORDS.copy()
    if topology == "hex20":
        from mechdsl.codegen.hex20_tables import HEX20_NODE_COORDS

        return HEX20_NODE_COORDS.copy()
    raise ValueError(
        f"Unknown topology {topology!r}. Plan B phase B5 supports hex8 / tet4 / tet10 / hex20."
    )


# ---------------------------------------------------------------------------
# Shape-gradient-from-basis helper
# ---------------------------------------------------------------------------


def _shape_grad_reference(
    element_ir: ElementIR,
    X_elem: NDArray,
    xi: float,
    eta: float,
    zeta: float,
) -> tuple[NDArray, float]:
    """Compute dN/dX and det(J0) at a parametric point for any topology.

    Evaluates the basis gradient at ``(xi, eta, zeta)`` via
    :meth:`ElementIR.basis.gradient`, then maps to physical reference
    coordinates using the standard Jacobian chain rule:

        J0   = X^T @ dN/dxi          (3, 3)
        dN/dX = dN/dxi @ J0^{-1}     (n_nodes, 3)

    This works uniformly for hex8 full, hex8 reduced, tet4, tet10, hex20 —
    including element/quadrature combinations (e.g. reduced Hex8 at the
    centroid) that are not pre-tabulated in the per-family GRAD_AT_QUAD
    arrays.
    """
    dN_dxi = element_ir.basis.gradient(xi, eta, zeta)
    J0 = X_elem.T @ dN_dxi
    detJ0 = float(np.linalg.det(J0))
    if detJ0 <= 0.0:
        msg = (
            f"Non-positive Jacobian determinant ({detJ0:.6e}) at parametric "
            f"point ({xi}, {eta}, {zeta})."
        )
        raise ValueError(msg)
    J0_inv = np.linalg.inv(J0)
    dN_dX = dN_dxi @ J0_inv
    return dN_dX, detJ0


# ---------------------------------------------------------------------------
# SVK single-element kernel (parametric over topology + quadrature)
# ---------------------------------------------------------------------------


def element_svk_internal_force(
    element_ir: ElementIR,
    u_elem: NDArray,
    X_elem: NDArray,
    lam: float,
    mu: float,
) -> NDArray:
    """SVK internal force for one element of any supported topology.

    Uses the basis functions and quadrature carried by ``element_ir`` — so
    the same routine serves Hex8 (full and reduced), Tet4, Tet10 and
    Hex20 without any element-family dispatch.

    Parameters
    ----------
    element_ir
        :class:`ElementIR` whose basis/quadrature drive the integration.
    u_elem
        Element nodal displacements, shape ``(element_ir.n_nodes, 3)``.
    X_elem
        Element nodal reference coordinates, shape
        ``(element_ir.n_nodes, 3)``.
    lam, mu
        Lame parameters for the SVK model.

    Returns
    -------
    NDArray, shape (n_nodes, 3)
        Element internal force vector (SVK only — hourglass
        stabilisation is added by the caller when requested).
    """
    quad = element_ir.quadrature
    n_nodes = element_ir.n_nodes
    f_int = np.zeros((n_nodes, 3), dtype=np.float64)

    for q in range(quad.n_points):
        xi, eta, zeta = (float(c) for c in quad.points[q])
        w_q = float(quad.weights[q])

        dN_dX, detJ0 = _shape_grad_reference(element_ir, X_elem, xi, eta, zeta)
        grad_u = u_elem.T @ dN_dX
        F = deformation_gradient(grad_u)
        E = green_lagrange(F)
        tr_E = float(np.trace(E))
        S = lam * tr_E * _I3 + 2.0 * mu * E  # PK2
        P = F @ S  # PK1
        f_int += w_q * detJ0 * (dN_dX @ P.T)

    return f_int
