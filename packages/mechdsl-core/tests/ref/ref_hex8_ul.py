"""Handwritten UL Hex8 elastic reference solver.

This is the Updated Lagrangian counterpart of ``ref_hex8_elastic.py``.
All quantities integrate over the **current** configuration:

- Cauchy stress sigma = (1/J) F @ S @ F^T (push-forward of PK2)
- Spatial shape gradients dN/dx (via current Jacobian j = x^T @ dN/dxi)
- Current volume element w_q * det(j)

The tangent uses the Truesdell spatial tangent c^tau (Piola push-forward of
the Lagrangian material tangent C4_svk) and the standard geometric stiffness
(initial-stress stiffness K_sigma).

For a quasi-static elastic problem the TL and UL formulations are
mathematically equivalent. Any discrepancy > ~1e-8 indicates a bug.

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
from mechdsl.symbolic.objective_rates import truesdell_tangent

# Re-export mesh generation from TL solver (single source of truth)
from tests.ref.ref_hex8_elastic import generate_hex8_mesh  # noqa: F401

if TYPE_CHECKING:
    from numpy.typing import NDArray

# Cache basis and quadrature (immutable, reusable)
_BASIS = hex8_basis()
_QUAD = hex8_quadrature()

_I3 = np.eye(3, dtype=np.float64)


# ---------------------------------------------------------------------------
# Element routines (Updated Lagrangian)
# ---------------------------------------------------------------------------


def _shape_grad_current(
    X_elem: NDArray, u_elem: NDArray, xi: float, eta: float, zeta: float
) -> tuple[NDArray, float]:
    """Compute spatial shape function gradients in current configuration.

    Parameters
    ----------
    X_elem : (8, 3)
        Element nodal reference coordinates.
    u_elem : (8, 3)
        Element nodal displacements.
    xi, eta, zeta : float
        Parametric coordinates.

    Returns
    -------
    dN_dx : (8, 3)
        Shape function gradients w.r.t. current coordinates x.
    detj : float
        Determinant of the current Jacobian j = x^T @ dN/dxi.
    """
    # dN/d(xi) in parametric space: (8, 3)
    dN_dxi = _BASIS.gradient(xi, eta, zeta)

    # Current coordinates: x = X + u
    x_elem = X_elem + u_elem

    # Current Jacobian: j = x^T @ dN/d(xi)  ->  (3, 3)
    j = x_elem.T @ dN_dxi

    detj = float(np.linalg.det(j))
    if detj <= 0.0:
        msg = f"Non-positive current Jacobian determinant ({detj:.6e}) — check element quality."
        raise ValueError(msg)

    j_inv = np.linalg.inv(j)

    # dN/dx = dN/d(xi) @ j^{-1}
    dN_dx = dN_dxi @ j_inv

    return dN_dx, detj


def element_internal_force_ul(
    u_elem: NDArray,
    X_elem: NDArray,
    lam: float,
    mu: float,
) -> NDArray:
    """Compute UL internal force vector for one Hex8 element.

    Integrates the UL residual over the current configuration:
        f_a_i = sum_q w_q * det(j) * dN_a/dx_j * sigma_ij

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

        # 1. Spatial shape function gradients in current config
        dN_dx, detj = _shape_grad_current(X_elem, u_elem, xi, eta, zeta)

        # 2. We still need the deformation gradient F for constitutive eval.
        #    Compute reference-config shape gradients for grad_u -> F.
        dN_dxi = _BASIS.gradient(xi, eta, zeta)
        J0 = X_elem.T @ dN_dxi
        J0_inv = np.linalg.inv(J0)
        dN_dX = dN_dxi @ J0_inv

        # 3. Displacement gradient and deformation gradient
        grad_u = u_elem.T @ dN_dX
        F = deformation_gradient(grad_u)
        J = float(np.linalg.det(F))

        # 4. Green-Lagrange strain and PK2 stress (SVK)
        E = green_lagrange(F)
        tr_E = np.trace(E)
        S = lam * tr_E * _I3 + 2.0 * mu * E

        # 5. Push-forward to Cauchy stress: sigma = (1/J) F @ S @ F^T
        sigma = (1.0 / J) * F @ S @ F.T

        # 6. Integrate over current config: f_a += w_q * det(j) * dN_dx @ sigma^T
        #    dN_dx is (8, 3); sigma^T is (3, 3)
        #    For node a: dN_dx[a, :] @ sigma^T  -> (3,)
        f_int += w_q * detj * (dN_dx @ sigma.T)

    return f_int


def element_tangent_matvec_ul(
    u_elem: NDArray,
    X_elem: NDArray,
    v_elem: NDArray,
    lam: float,
    mu: float,
) -> NDArray:
    """UL tangent stiffness matvec for one SVK Hex8 element.

    Computes K_e @ v via the Truesdell spatial tangent (Piola push-forward
    of the Lagrangian material tangent) plus the geometric (initial-stress)
    stiffness. Two contributions at each quadrature point:

    1. **Material**: dsigma_mat_{ij} = c^tau_{ijkl} * grad_v_{kl}
       Assembled as: dN_dx @ dsigma_mat.T  (standard sigma-row contraction)

    2. **Geometric** (initial-stress stiffness):
       K_geo_{ab,ik} = delta_ik * (dN_a/dx_j * sigma_jl * dN_b/dx_l)
       In matvec form this produces G_{ji} = sigma_jl * grad_v_il, assembled
       as: dN_dx @ G  (note: G directly, NOT G.T)

    Combined: Kv_e += w_q * det(j) * (dN_dx @ dsigma_mat.T + dN_dx @ G)

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
    C4 = material_tangent_4th(SVKMaterial(lam, mu))
    Kv = np.zeros((8, 3), dtype=np.float64)

    for q in range(_QUAD.n_points):
        xi, eta, zeta = _QUAD.points[q]
        w_q = _QUAD.weights[q]

        # 1. Spatial shape gradients in current config
        dN_dx, detj = _shape_grad_current(X_elem, u_elem, xi, eta, zeta)

        # 2. Deformation gradient F (for constitutive + tangent)
        dN_dxi = _BASIS.gradient(xi, eta, zeta)
        J0 = X_elem.T @ dN_dxi
        J0_inv = np.linalg.inv(J0)
        dN_dX = dN_dxi @ J0_inv
        grad_u = u_elem.T @ dN_dX
        F = deformation_gradient(grad_u)
        J = float(np.linalg.det(F))

        # 3. PK2 stress and Cauchy stress
        E = green_lagrange(F)
        tr_E = np.trace(E)
        S = lam * tr_E * _I3 + 2.0 * mu * E
        sigma = (1.0 / J) * F @ S @ F.T

        # 4. Truesdell spatial tangent: c^tau = (1/J) F_iI F_jJ F_kK F_lL C_IJKL
        c_tau = truesdell_tangent(C4, sigma, F=F)

        # 5. Velocity gradient in current config: grad_v = v^T @ dN_dx
        grad_v = v_elem.T @ dN_dx

        # 6. Material contribution: dsigma_mat_{ij} = c^tau_{ijkl} * grad_v_{kl}
        dsigma_mat = np.einsum("ijkl,kl->ij", c_tau, grad_v)

        # 7. Geometric (initial-stress) stiffness:
        #    G_{ji} = sum_l sigma_{jl} * grad_v_{il}  =  (sigma @ grad_v.T)_{ji}
        #    Assembled as dN_dx @ G (NOT dN_dx @ G.T)
        G_geo = sigma @ grad_v.T  # (3, 3): G[j, i]

        # 8. Integrate: Kv += w_q * det(j) * (material + geometric)
        Kv += w_q * detj * (dN_dx @ dsigma_mat.T + dN_dx @ G_geo)

    return Kv


# ---------------------------------------------------------------------------
# Global assembly (matrix-free)
# ---------------------------------------------------------------------------


def assemble_internal_force_ul(
    u: NDArray,
    coords: NDArray,
    conn: NDArray,
    lam: float,
    mu: float,
) -> NDArray:
    """Assemble global UL internal force vector.

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
        f_e = element_internal_force_ul(u_elem, X_elem, lam, mu)
        # Scatter
        for a in range(8):
            f_int[nodes[a]] += f_e[a]

    return f_int


def apply_tangent_matvec_ul(
    u: NDArray,
    v: NDArray,
    coords: NDArray,
    conn: NDArray,
    lam: float,
    mu: float,
    bc_mask: NDArray,
) -> NDArray:
    """Global UL tangent matvec with Dirichlet BC enforcement.

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
        Kv_e = element_tangent_matvec_ul(u_elem, X_elem, v_elem, lam, mu)
        for a in range(8):
            Kv[nodes[a]] += Kv_e[a]

    # Identity for constrained DOFs (preserves non-singularity for CG)
    Kv[bc_mask] = v[bc_mask]

    return Kv


# ---------------------------------------------------------------------------
# Newton-Raphson solver (UL)
# ---------------------------------------------------------------------------


def solve_elastic_ul(
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
    """Solve elastic BVP using UL Newton-Raphson with CG linear solver.

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
    from tests.ref.ref_hex8_elastic import apply_dirichlet

    n_nodes = coords.shape[0]
    ndof = n_nodes * 3

    # Initialize: prescribed values at constrained DOFs, zero elsewhere
    u = np.zeros((n_nodes, 3), dtype=np.float64)
    u = apply_dirichlet(u, bc_mask, bc_values)

    cg_solver = ScipyCGSolver()
    residual_history: list[float] = []
    R0_norm: float | None = None

    for newton_iter in range(max_iter):
        # Compute UL residual: R = f_ext - f_int_ul(u)
        f_int = assemble_internal_force_ul(u, coords, conn, lam, mu)
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

        assert R0_norm is not None
        if R_norm < tol * R0_norm:
            break

        # Solve UL tangent system K_ul(u) @ du = R using CG
        def matvec(v_flat: NDArray, _u: NDArray = u) -> NDArray:
            v = v_flat.reshape((n_nodes, 3))
            Kv = apply_tangent_matvec_ul(_u, v, coords, conn, lam, mu, bc_mask)
            return Kv.ravel()

        R_flat = R.ravel()
        du_flat, _cg_iters, _cg_res = cg_solver.solve(
            matvec, R_flat, np.zeros(ndof, dtype=np.float64), cg_tol, cg_max_iter
        )

        du = du_flat.reshape((n_nodes, 3))
        # Ensure constrained DOFs are not modified
        du[bc_mask] = 0.0

        u = u + du
    else:
        raise RuntimeError(
            f"UL Newton did not converge after {max_iter} iterations. "
            f"Final |R| = {residual_history[-1]:.3e}"
        )

    return u, residual_history
