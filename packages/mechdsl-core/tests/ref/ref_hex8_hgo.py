"""Handwritten TL Hex8 reference solver for HGO anisotropic hyperelasticity.

Mirrors ``ref_hex8_elastic.py`` (SVK) but uses the HGO (Holzapfel-Gasser-Ogden)
constitutive model with per-element fiber directions.

Design notes
------------
- Identical Hex8 kinematics, 2x2x2 Gauss quadrature and Newton-CG outer loop as
  the SVK reference, so the FEM pipeline is shared.
- Stress comes from ``mechdsl.symbolic.models.hgo.pk2_stress`` and the tangent
  from ``material_tangent_4th`` (central-difference FD of the analytic stress).
- Fiber directions are supplied per element as a pair of unit vectors
  ``fiber_dirs[e] = (a1, a2)``.  For the P10-9 strip benchmark only one fiber
  family is active; the second is set equal to the first (a zero fiber family
  would hit the ``norm == 0`` guard in ``pk2_stress``).

This reference runs on small meshes (1..8 elements for the P10-9 benchmark), so
the O(12) FD stress evaluations per quadrature point are acceptable.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from mechdsl.ir.element_ir import hex8_basis, hex8_quadrature
from mechdsl.lib.tensor_ops import deformation_gradient, green_lagrange
from mechdsl.solver.import_adapter import ScipyCGSolver
from mechdsl.symbolic.models.hgo import (
    HGOMaterial,
    material_tangent_4th,
    pk2_stress,
)

if TYPE_CHECKING:
    from numpy.typing import NDArray

_BASIS = hex8_basis()
_QUAD = hex8_quadrature()
_I3 = np.eye(3, dtype=np.float64)


# ---------------------------------------------------------------------------
# Element routines
# ---------------------------------------------------------------------------


def _shape_grad_reference(
    X_elem: NDArray, xi: float, eta: float, zeta: float
) -> tuple[NDArray, float]:
    dN_dxi = _BASIS.gradient(xi, eta, zeta)
    J0 = X_elem.T @ dN_dxi
    detJ0 = float(np.linalg.det(J0))
    if detJ0 <= 0.0:
        msg = f"Non-positive Jacobian determinant ({detJ0:.6e})."
        raise ValueError(msg)
    dN_dX = dN_dxi @ np.linalg.inv(J0)
    return dN_dX, detJ0


def element_internal_force(
    u_elem: NDArray,
    X_elem: NDArray,
    material: HGOMaterial,
    fiber_dirs: tuple[NDArray, NDArray],
) -> NDArray:
    """Internal force vector for one Hex8 element, HGO material."""
    f_int = np.zeros((8, 3), dtype=np.float64)

    for q in range(_QUAD.n_points):
        xi, eta, zeta = _QUAD.points[q]
        w_q = _QUAD.weights[q]

        dN_dX, detJ0 = _shape_grad_reference(X_elem, xi, eta, zeta)
        grad_u = u_elem.T @ dN_dX
        F = deformation_gradient(grad_u)
        E = green_lagrange(F)

        S = pk2_stress(material, E, fiber_dirs)
        P = F @ S

        f_int += w_q * detJ0 * (dN_dX @ P.T)

    return f_int


def element_tangent_matvec(
    u_elem: NDArray,
    X_elem: NDArray,
    v_elem: NDArray,
    material: HGOMaterial,
    fiber_dirs: tuple[NDArray, NDArray],
) -> NDArray:
    """K_e @ v via exact linearisation: dP = grad_v @ S + F @ (C : dE)."""
    Kv = np.zeros((8, 3), dtype=np.float64)

    for q in range(_QUAD.n_points):
        xi, eta, zeta = _QUAD.points[q]
        w_q = _QUAD.weights[q]

        dN_dX, detJ0 = _shape_grad_reference(X_elem, xi, eta, zeta)
        grad_u = u_elem.T @ dN_dX
        F = deformation_gradient(grad_u)
        E = green_lagrange(F)

        S = pk2_stress(material, E, fiber_dirs)
        C4 = material_tangent_4th(material, E, fiber_dirs)

        grad_v = v_elem.T @ dN_dX
        dE = 0.5 * (F.T @ grad_v + grad_v.T @ F)
        dS = np.einsum("ijkl,kl->ij", C4, dE)
        dP = grad_v @ S + F @ dS

        Kv += w_q * detJ0 * (dN_dX @ dP.T)

    return Kv


# ---------------------------------------------------------------------------
# Global assembly
# ---------------------------------------------------------------------------


def assemble_internal_force(
    u: NDArray,
    coords: NDArray,
    conn: NDArray,
    material: HGOMaterial,
    fiber_dirs: list[tuple[NDArray, NDArray]],
) -> NDArray:
    n_nodes = coords.shape[0]
    f_int = np.zeros((n_nodes, 3), dtype=np.float64)

    for e in range(conn.shape[0]):
        nodes = conn[e]
        u_elem = u[nodes]
        X_elem = coords[nodes]
        f_e = element_internal_force(u_elem, X_elem, material, fiber_dirs[e])
        for a in range(8):
            f_int[nodes[a]] += f_e[a]

    return f_int


def apply_tangent_matvec(
    u: NDArray,
    v: NDArray,
    coords: NDArray,
    conn: NDArray,
    material: HGOMaterial,
    fiber_dirs: list[tuple[NDArray, NDArray]],
    bc_mask: NDArray,
) -> NDArray:
    n_nodes = coords.shape[0]
    v_free = v.copy()
    v_free[bc_mask] = 0.0

    Kv = np.zeros((n_nodes, 3), dtype=np.float64)
    for e in range(conn.shape[0]):
        nodes = conn[e]
        u_elem = u[nodes]
        X_elem = coords[nodes]
        v_elem = v_free[nodes]
        Kv_e = element_tangent_matvec(u_elem, X_elem, v_elem, material, fiber_dirs[e])
        for a in range(8):
            Kv[nodes[a]] += Kv_e[a]

    Kv[bc_mask] = v[bc_mask]
    return Kv


def apply_dirichlet(u: NDArray, bc_mask: NDArray, bc_values: NDArray) -> NDArray:
    u = u.copy()
    u[bc_mask] = bc_values[bc_mask]
    return u


# ---------------------------------------------------------------------------
# Newton-Raphson solver with displacement-control load stepping
# ---------------------------------------------------------------------------


def solve_hgo(
    coords: NDArray,
    conn: NDArray,
    material: HGOMaterial,
    fiber_dirs: list[tuple[NDArray, NDArray]],
    bc_mask: NDArray,
    bc_values: NDArray,
    f_ext: NDArray,
    *,
    n_steps: int = 1,
    tol: float = 1e-8,
    max_iter: int = 40,
    cg_tol: float = 1e-10,
    cg_max_iter: int = 2000,
) -> tuple[NDArray, list[float]]:
    """Solve the HGO TL BVP using Newton-Raphson + CG, with load stepping.

    The Dirichlet values ``bc_values`` and external force ``f_ext`` are
    linearly ramped over ``n_steps`` steps.  Every Newton step uses the
    converged state of the previous load step as its initial guess.

    Returns
    -------
    u : (n_nodes, 3)  converged displacement
    residual_history : list of residual norms for the FINAL load step
    """
    n_nodes = coords.shape[0]
    ndof = n_nodes * 3

    u = np.zeros((n_nodes, 3), dtype=np.float64)
    cg_solver = ScipyCGSolver()
    residual_history: list[float] = []

    for step in range(1, n_steps + 1):
        alpha = step / n_steps
        bc_values_step = alpha * bc_values
        f_ext_step = alpha * f_ext

        u = apply_dirichlet(u, bc_mask, bc_values_step)

        residual_history = []
        R0_norm: float | None = None

        for newton_iter in range(max_iter):
            f_int = assemble_internal_force(u, coords, conn, material, fiber_dirs)
            R = f_ext_step - f_int
            R[bc_mask] = 0.0

            R_norm = float(np.linalg.norm(R))
            residual_history.append(R_norm)

            if newton_iter == 0:
                R0_norm = R_norm
                if R0_norm < 1e-15:
                    break

            assert R0_norm is not None
            if R_norm < tol * max(R0_norm, 1.0):
                break

            def matvec(v_flat: NDArray, _u: NDArray = u) -> NDArray:
                v = v_flat.reshape((n_nodes, 3))
                Kv = apply_tangent_matvec(_u, v, coords, conn, material, fiber_dirs, bc_mask)
                return Kv.ravel()

            R_flat = R.ravel()
            du_flat, _cg_iters, _cg_res = cg_solver.solve(
                matvec, R_flat, np.zeros(ndof, dtype=np.float64), cg_tol, cg_max_iter
            )

            du = du_flat.reshape((n_nodes, 3))
            du[bc_mask] = 0.0
            u = u + du
        else:
            raise RuntimeError(
                f"HGO Newton did not converge at load step {step}/{n_steps} "
                f"after {max_iter} iterations. Final |R| = {residual_history[-1]:.3e}"
            )

    return u, residual_history
