"""Internal SVK assembly routines for the verify harnesses.

Provides the minimal element-level and global assembly functions needed
by :mod:`mechdsl.verify.patch_test` and :mod:`mechdsl.verify.convergence`.
All routines compose from shipped building blocks
(:mod:`mechdsl.ir.element_ir`, :mod:`mechdsl.lib.tensor_ops`,
:mod:`mechdsl.solver`).

These are **not** public API.  Test-level code should continue importing
from ``tests.ref.ref_hex8_elastic`` (the canonical ground truth).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import numpy as np

from mechdsl.ir.element_ir import hex8_basis, hex8_quadrature
from mechdsl.lib.tensor_ops import deformation_gradient, green_lagrange

if TYPE_CHECKING:
    from numpy.typing import NDArray

# Cache basis and quadrature (immutable, reusable)
_BASIS = hex8_basis()
_QUAD = hex8_quadrature()
_I3 = np.eye(3, dtype=np.float64)


# ---------------------------------------------------------------------------
# Element routines
# ---------------------------------------------------------------------------


def _shape_grad_reference(
    X_elem: NDArray, xi: float, eta: float, zeta: float
) -> tuple[NDArray, float]:
    """Shape function gradients in reference configuration.

    Returns
    -------
    dN_dX : (8, 3)
        Shape function gradients w.r.t. reference coordinates X.
    detJ0 : float
        Determinant of the reference Jacobian.
    """
    dN_dxi = _BASIS.gradient(xi, eta, zeta)
    J0 = X_elem.T @ dN_dxi
    detJ0 = float(np.linalg.det(J0))
    if detJ0 <= 0.0:
        msg = f"Non-positive Jacobian determinant ({detJ0:.6e}) — check element connectivity."
        raise ValueError(msg)
    J0_inv = np.linalg.inv(J0)
    dN_dX = dN_dxi @ J0_inv
    return dN_dX, detJ0


def element_internal_force(
    u_elem: NDArray,
    X_elem: NDArray,
    lam: float,
    mu: float,
) -> NDArray:
    """Internal force vector for one Hex8 element (SVK, 2x2x2 Gauss).

    Parameters
    ----------
    u_elem : (8, 3)
        Element nodal displacements.
    X_elem : (8, 3)
        Element nodal reference coordinates.
    lam, mu : float
        Lame parameters.

    Returns
    -------
    f_int : (8, 3)
        Element internal force vector.
    """
    f_int = np.zeros((8, 3), dtype=np.float64)

    for q in range(_QUAD.n_points):
        xi, eta, zeta = _QUAD.points[q]
        w_q = _QUAD.weights[q]

        dN_dX, detJ0 = _shape_grad_reference(X_elem, xi, eta, zeta)
        grad_u = u_elem.T @ dN_dX
        F = deformation_gradient(grad_u)
        E = green_lagrange(F)
        tr_E = np.trace(E)
        S = lam * tr_E * _I3 + 2.0 * mu * E
        P = F @ S
        f_int += w_q * detJ0 * (dN_dX @ P.T)

    return f_int


def element_tangent_matvec(
    u_elem: NDArray,
    X_elem: NDArray,
    v_elem: NDArray,
    lam: float,
    mu: float,
) -> NDArray:
    """Analytical tangent stiffness matvec for one SVK Hex8 element.

    Computes K_e @ v via exact linearisation of the internal force:
        dP = grad_v @ S + F @ (C : dE)
    where dE = sym(F^T @ grad_v) is the linearised Green-Lagrange strain.
    """
    from mechdsl.symbolic.models.svk import SVKMaterial, material_tangent_4th

    C4 = material_tangent_4th(SVKMaterial(lam, mu))  # constant (3,3,3,3)
    Kv = np.zeros((8, 3), dtype=np.float64)

    for q in range(_QUAD.n_points):
        xi, eta, zeta = _QUAD.points[q]
        w_q = _QUAD.weights[q]

        dN_dX, detJ0 = _shape_grad_reference(X_elem, xi, eta, zeta)

        # Current kinematics
        grad_u = u_elem.T @ dN_dX  # (3, 3)
        F = deformation_gradient(grad_u)
        E = green_lagrange(F)
        tr_E = np.trace(E)
        S = lam * tr_E * _I3 + 2.0 * mu * E  # PK2 stress

        # Linearisation in direction v
        grad_v = v_elem.T @ dN_dX  # (3, 3)
        dE = 0.5 * (F.T @ grad_v + grad_v.T @ F)  # linearised E
        dS = np.einsum("ijkl,kl->ij", C4, dE)  # linearised PK2
        dP = grad_v @ S + F @ dS  # linearised PK1

        Kv += w_q * detJ0 * (dN_dX @ dP.T)

    return Kv


# ---------------------------------------------------------------------------
# Global assembly (matrix-free)
# ---------------------------------------------------------------------------


def assemble_internal_force(
    u: NDArray,
    coords: NDArray,
    conn: NDArray,
    lam: float,
    mu: float,
) -> NDArray:
    """Assemble global internal force vector.

    Parameters
    ----------
    u : (n_nodes, 3)
        Global nodal displacements.
    coords : (n_nodes, 3)
        Reference coordinates.
    conn : (n_elem, 8)
        Element connectivity.
    lam, mu : float
        Lame parameters.

    Returns
    -------
    f_int : (n_nodes, 3)
        Global internal force vector.
    """
    n_nodes = coords.shape[0]
    f_int = np.zeros((n_nodes, 3), dtype=np.float64)

    for e in range(conn.shape[0]):
        nodes = conn[e]
        f_e = element_internal_force(u[nodes], coords[nodes], lam, mu)
        for a in range(8):
            f_int[nodes[a]] += f_e[a]

    return f_int


def _assemble_tangent_matvec(
    u: NDArray,
    v: NDArray,
    coords: NDArray,
    conn: NDArray,
    lam: float,
    mu: float,
) -> NDArray:
    """Global tangent matvec **without** Dirichlet BC enforcement.

    ``newton_solve`` wraps this callback and applies BC enforcement
    internally, so this must return the bare assembly result.
    """
    n_nodes = coords.shape[0]
    Kv = np.zeros((n_nodes, 3), dtype=np.float64)

    for e in range(conn.shape[0]):
        nodes = conn[e]
        Kv_e = element_tangent_matvec(u[nodes], coords[nodes], v[nodes], lam, mu)
        for a in range(8):
            Kv[nodes[a]] += Kv_e[a]

    return Kv


# ---------------------------------------------------------------------------
# SVK elastic solver (wraps newton_solve)
# ---------------------------------------------------------------------------


def solve_svk_elastic(
    coords: NDArray,
    conn: NDArray,
    lam: float,
    mu: float,
    bc_mask: NDArray,
    bc_values: NDArray,
    f_ext: NDArray,
    tol: float = 1e-8,
    max_iter: int = 50,
    cg_tol: float = 1e-10,
    cg_max_iter: int = 2000,
) -> tuple[NDArray, list[float]]:
    """Solve elastic BVP (SVK) using the shipped Newton-Raphson driver.

    Parameters match ``ref_hex8_elastic.solve_elastic`` for drop-in use.

    Returns
    -------
    u : (n_nodes, 3)
        Converged displacement field.
    residual_history : list[float]
        Residual norm at each Newton iteration.

    Raises
    ------
    RuntimeError
        If Newton iteration does not converge.
    """
    from mechdsl.solver.newton import NewtonConfig, newton_solve

    n_nodes = coords.shape[0]

    # Initialize displacement with prescribed BCs
    u = np.zeros((n_nodes, 3), dtype=np.float64)
    u[bc_mask] = bc_values[bc_mask]

    # Assembly callbacks (closures over mesh and material)
    def residual_fn(u_cur: NDArray) -> NDArray:
        return cast("NDArray", f_ext - assemble_internal_force(u_cur, coords, conn, lam, mu))

    def tangent_fn(u_cur: NDArray, v: NDArray) -> NDArray:
        return _assemble_tangent_matvec(u_cur, v, coords, conn, lam, mu)

    config = NewtonConfig(
        tol=tol,
        max_iter=max_iter,
        cg_tol=cg_tol,
        cg_max_iter=cg_max_iter,
    )

    result = newton_solve(
        assemble_residual=residual_fn,
        tangent_matvec=tangent_fn,
        u=u,
        bc_mask=bc_mask,
        config=config,
    )

    if not result.converged:
        raise RuntimeError(
            f"Newton did not converge after {result.n_iterations} iterations. "
            f"Final |R| = {result.residual_history[-1]:.3e}"
        )

    return u, result.residual_history
