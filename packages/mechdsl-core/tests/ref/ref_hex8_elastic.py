"""Handwritten TL Hex8 elastic reference solver.

This is the ground truth for verifying generated code. It implements:
- 3D Hex8 trilinear elements with 2x2x2 Gauss quadrature
- Total Lagrangian formulation
- St. Venant-Kirchhoff constitutive model
- Newton-Raphson nonlinear solver with CG linear solver

All computations use float64. Conventions follow 07-CONVENTIONS.md:
  - Tension-positive stress
  - Index convention: lowercase = spatial, uppercase = material
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from mechdsl.ir.element_ir import hex8_basis, hex8_quadrature
from mechdsl.lib.tensor_ops import deformation_gradient, green_lagrange
from mechdsl.solver.import_adapter import ScipyCGSolver
from mechdsl.symbolic.models.svk import SVKMaterial, material_tangent_4th

if TYPE_CHECKING:
    from numpy.typing import NDArray

# Cache basis and quadrature (immutable, reusable)
_BASIS = hex8_basis()
_QUAD = hex8_quadrature()

_I3 = np.eye(3, dtype=np.float64)

# ---------------------------------------------------------------------------
# Mesh utilities
# ---------------------------------------------------------------------------


def generate_hex8_mesh(
    nx: int, ny: int, nz: int, Lx: float, Ly: float, Lz: float
) -> tuple[NDArray, NDArray]:
    """Generate structured Hex8 mesh on [0,Lx] x [0,Ly] x [0,Lz].

    Node ordering within each element follows the standard Hex8 convention
    matching ``_HEX8_NODES`` in element_ir: bottom face (-z) CCW then
    top face (+z) CCW.

    Returns
    -------
    coords : NDArray, shape (n_nodes, 3)
        Nodal reference coordinates.
    conn : NDArray, shape (n_elem, 8)
        Element connectivity (0-based node indices).
    """
    n_nodes = (nx + 1) * (ny + 1) * (nz + 1)
    coords = np.empty((n_nodes, 3), dtype=np.float64)

    idx = 0
    for k in range(nz + 1):
        for j in range(ny + 1):
            for i in range(nx + 1):
                coords[idx, 0] = i * Lx / nx
                coords[idx, 1] = j * Ly / ny
                coords[idx, 2] = k * Lz / nz
                idx += 1

    n_elem = nx * ny * nz
    conn = np.empty((n_elem, 8), dtype=np.int64)

    def node_id(i: int, j: int, k: int) -> int:
        return k * (ny + 1) * (nx + 1) + j * (nx + 1) + i

    eidx = 0
    for k in range(nz):
        for j in range(ny):
            for i in range(nx):
                # Bottom face (k), CCW when viewed from -z
                n0 = node_id(i, j, k)
                n1 = node_id(i + 1, j, k)
                n2 = node_id(i + 1, j + 1, k)
                n3 = node_id(i, j + 1, k)
                # Top face (k+1), CCW when viewed from -z
                n4 = node_id(i, j, k + 1)
                n5 = node_id(i + 1, j, k + 1)
                n6 = node_id(i + 1, j + 1, k + 1)
                n7 = node_id(i, j + 1, k + 1)
                conn[eidx] = [n0, n1, n2, n3, n4, n5, n6, n7]
                eidx += 1

    return coords, conn


# ---------------------------------------------------------------------------
# Element routines
# ---------------------------------------------------------------------------


def _shape_grad_reference(
    X_elem: NDArray, xi: float, eta: float, zeta: float
) -> tuple[NDArray, float]:
    """Compute shape function gradients in reference configuration.

    Parameters
    ----------
    X_elem : (8, 3)
        Element nodal reference coordinates.
    xi, eta, zeta : float
        Parametric coordinates.

    Returns
    -------
    dN_dX : (8, 3)
        Shape function gradients w.r.t. reference coordinates X.
    detJ0 : float
        Determinant of the reference Jacobian.
    """
    # dN/d(xi) in parametric space: (8, 3)
    dN_dxi = _BASIS.gradient(xi, eta, zeta)

    # Reference Jacobian: J0 = dX/d(xi) = X^T @ dN/d(xi)  ->  (3, 3)
    J0 = X_elem.T @ dN_dxi

    detJ0 = float(np.linalg.det(J0))
    if detJ0 <= 0.0:
        msg = f"Non-positive Jacobian determinant ({detJ0:.6e}) — check element connectivity."
        raise ValueError(msg)

    J0_inv = np.linalg.inv(J0)

    # dN/dX = dN/d(xi) @ J0^{-1}
    dN_dX = dN_dxi @ J0_inv  # (8, 3)

    return dN_dX, detJ0


def element_internal_force(
    u_elem: NDArray,
    X_elem: NDArray,
    lam: float,
    mu: float,
) -> NDArray:
    """Compute internal force vector for one Hex8 element.

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

        # 1. Shape function gradients in reference config
        dN_dX, detJ0 = _shape_grad_reference(X_elem, xi, eta, zeta)

        # 2. Displacement gradient: du/dX = u^T @ dN/dX  ->  (3, 3)
        grad_u = u_elem.T @ dN_dX

        # 3. Deformation gradient F = I + du/dX
        F = deformation_gradient(grad_u)

        # 4. Green-Lagrange strain E = (F^T F - I) / 2
        E = green_lagrange(F)

        # 5. PK2 stress (SVK): S = lambda * tr(E) * I + 2 * mu * E
        tr_E = np.trace(E)
        S = lam * tr_E * _I3 + 2.0 * mu * E

        # 6. PK1 stress: P = F @ S
        P = F @ S

        # 7. Integrate: f_a += w_q * det(J0) * (dN_a/dX) @ P^T
        #    dN_dX is (8, 3); P^T is (3, 3)
        #    Contribution for node a: dN_dX[a, :] @ P^T  -> (3,)
        #    Equivalently: P @ dN_dX[a, :]  -> (3,)
        f_int += w_q * detJ0 * (dN_dX @ P.T)  # (8, 3)

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
    where dE = sym(F^T @ grad_v) is the linearised Green-Lagrange strain
    and C is the constant SVK material tangent.

    Parameters
    ----------
    u_elem : (8, 3)
        Element nodal displacements.
    X_elem : (8, 3)
        Element nodal reference coordinates.
    v_elem : (8, 3)
        Direction vector.
    lam, mu : float
        Lame parameters.

    Returns
    -------
    Kv : (8, 3)
        Tangent stiffness matvec result.
    """
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
        u_elem = u[nodes]
        X_elem = coords[nodes]
        f_e = element_internal_force(u_elem, X_elem, lam, mu)
        # Scatter
        for a in range(8):
            f_int[nodes[a]] += f_e[a]

    return f_int


def apply_tangent_matvec(
    u: NDArray,
    v: NDArray,
    coords: NDArray,
    conn: NDArray,
    lam: float,
    mu: float,
    bc_mask: NDArray,
) -> NDArray:
    """Global tangent matvec with Dirichlet BC enforcement.

    Constrained DOFs in ``v`` are zeroed before the matvec, and constrained
    DOFs in the result are also zeroed (homogeneous BC on increment).

    Parameters
    ----------
    u : (n_nodes, 3)
        Current displacement.
    v : (n_nodes, 3)
        Direction vector.
    coords : (n_nodes, 3)
        Reference coordinates.
    conn : (n_elem, 8)
        Element connectivity.
    lam, mu : float
        Lame parameters.
    bc_mask : (n_nodes, 3), dtype bool
        True for constrained DOFs.

    Returns
    -------
    Kv : (n_nodes, 3)
        Matvec result with constrained DOFs zeroed.
    """
    n_nodes = coords.shape[0]

    # Zero constrained DOFs in direction vector
    v_free = v.copy()
    v_free[bc_mask] = 0.0

    Kv = np.zeros((n_nodes, 3), dtype=np.float64)

    for e in range(conn.shape[0]):
        nodes = conn[e]
        u_elem = u[nodes]
        X_elem = coords[nodes]
        v_elem = v_free[nodes]
        Kv_e = element_tangent_matvec(u_elem, X_elem, v_elem, lam, mu)
        for a in range(8):
            Kv[nodes[a]] += Kv_e[a]

    # Identity for constrained DOFs (preserves non-singularity for CG)
    Kv[bc_mask] = v[bc_mask]

    return Kv


# ---------------------------------------------------------------------------
# Boundary conditions
# ---------------------------------------------------------------------------


def apply_dirichlet(
    u: NDArray,
    bc_mask: NDArray,
    bc_values: NDArray,
) -> NDArray:
    """Apply Dirichlet boundary conditions.

    Parameters
    ----------
    u : (n_nodes, 3)
        Displacement field (modified in place and returned).
    bc_mask : (n_nodes, 3), dtype bool
        True for constrained DOFs.
    bc_values : (n_nodes, 3)
        Prescribed displacement values (only used where bc_mask is True).

    Returns
    -------
    u : (n_nodes, 3)
        Updated displacement field.
    """
    u = u.copy()
    u[bc_mask] = bc_values[bc_mask]
    return u


# ---------------------------------------------------------------------------
# Newton-Raphson solver
# ---------------------------------------------------------------------------


def solve_elastic(
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
    """Solve elastic BVP using Newton-Raphson with CG linear solver.

    Parameters
    ----------
    coords : (n_nodes, 3)
        Reference coordinates.
    conn : (n_elem, 8)
        Element connectivity.
    lam, mu : float
        Lame parameters.
    bc_mask : (n_nodes, 3), dtype bool
        True for constrained DOFs.
    bc_values : (n_nodes, 3)
        Prescribed displacement values.
    f_ext : (n_nodes, 3)
        External force vector.
    tol : float
        Relative Newton tolerance: ||R|| < tol * ||R_0||.
    max_iter : int
        Maximum Newton iterations.
    cg_tol : float
        Relative CG tolerance.
    cg_max_iter : int
        Maximum CG iterations.

    Returns
    -------
    u : (n_nodes, 3)
        Converged displacement field.
    residual_history : list[float]
        Residual norm at each Newton iteration.
    """
    n_nodes = coords.shape[0]
    ndof = n_nodes * 3

    # Initialize: prescribed values at constrained DOFs, zero elsewhere
    u = np.zeros((n_nodes, 3), dtype=np.float64)
    u = apply_dirichlet(u, bc_mask, bc_values)

    cg_solver = ScipyCGSolver()
    residual_history: list[float] = []
    R0_norm: float | None = None

    for newton_iter in range(max_iter):
        # Compute residual: R = f_ext - f_int(u)
        f_int = assemble_internal_force(u, coords, conn, lam, mu)
        R = f_ext - f_int

        # Zero constrained DOFs in residual
        R[bc_mask] = 0.0

        R_norm = float(np.linalg.norm(R))
        residual_history.append(R_norm)

        # First iteration: store reference norm
        if newton_iter == 0:
            R0_norm = R_norm
            if R0_norm < 1e-15:
                # Already at equilibrium
                break

        # Convergence check
        assert R0_norm is not None
        if R_norm < tol * R0_norm:
            break

        # Solve tangent system K(u) @ du = R using CG
        def matvec(v_flat: NDArray, _u: NDArray = u) -> NDArray:
            v = v_flat.reshape((n_nodes, 3))
            Kv = apply_tangent_matvec(_u, v, coords, conn, lam, mu, bc_mask)
            return Kv.ravel()

        R_flat = R.ravel()
        du_flat, _cg_iters, _cg_res = cg_solver.solve(
            matvec, R_flat, np.zeros(ndof, dtype=np.float64), cg_tol, cg_max_iter
        )

        du = du_flat.reshape((n_nodes, 3))
        # Ensure constrained DOFs are not modified
        du[bc_mask] = 0.0

        # Update
        u = u + du
    else:
        raise RuntimeError(
            f"Newton did not converge after {max_iter} iterations. "
            f"Final |R| = {residual_history[-1]:.3e}"
        )

    return u, residual_history
