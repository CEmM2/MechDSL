"""Handwritten TL Hex8 J2 plastic reference solver.

Extends the elastic reference with:
- Radial return mapping for J2 plasticity
- Power-law isotropic hardening: sigma_y = sigma_y0 + K * alpha^n
- History variable storage (equivalent plastic strain per quadrature point)
- Consistent algorithmic tangent

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
from mechdsl.symbolic.models.j2_power_law import J2PowerLawMaterial, radial_return

if TYPE_CHECKING:
    from numpy.typing import NDArray

from tests.ref.ref_hex8_elastic import generate_hex8_mesh  # noqa: F401 — re-export

# Cache basis and quadrature (immutable, reusable)
_BASIS = hex8_basis()
_QUAD = hex8_quadrature()

_I3 = np.eye(3, dtype=np.float64)

# ---------------------------------------------------------------------------
# History field management
# ---------------------------------------------------------------------------


class HistoryFields:
    """Manages state variables for J2 plasticity.

    Stores equivalent plastic strain (alpha) at every quadrature point
    for every element. The two-level commit/rollback pattern supports
    Newton iterations within a load step.
    """

    def __init__(self, n_elem: int, n_qp: int = 8) -> None:
        self.n_elem = n_elem
        self.n_qp = n_qp
        self.alpha_current = np.zeros((n_elem, n_qp), dtype=np.float64)
        self.alpha_old = np.zeros((n_elem, n_qp), dtype=np.float64)

    def commit(self) -> None:
        """Copy current to old on converged step."""
        self.alpha_old[:] = self.alpha_current

    def rollback(self) -> None:
        """Restore current from old on non-convergence."""
        self.alpha_current[:] = self.alpha_old


# ---------------------------------------------------------------------------
# Element routines (shape function gradient — same as elastic ref)
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
    dN_dxi = _BASIS.gradient(xi, eta, zeta)
    J0 = X_elem.T @ dN_dxi
    detJ0 = float(np.linalg.det(J0))
    if detJ0 <= 0.0:
        msg = f"Non-positive Jacobian determinant ({detJ0:.6e}) — check element connectivity."
        raise ValueError(msg)
    J0_inv = np.linalg.inv(J0)
    dN_dX = dN_dxi @ J0_inv
    return dN_dX, detJ0


# ---------------------------------------------------------------------------
# Element routines with plasticity
# ---------------------------------------------------------------------------


def element_internal_force_plastic(
    u_elem: NDArray,
    X_elem: NDArray,
    mat: J2PowerLawMaterial,
    alpha_elem: NDArray,
) -> tuple[NDArray, NDArray]:
    """Compute internal force and updated alpha for one element.

    Parameters
    ----------
    u_elem : (8, 3)
        Element nodal displacements.
    X_elem : (8, 3)
        Element nodal reference coordinates.
    mat : J2PowerLawMaterial
        Material parameters.
    alpha_elem : (8,)
        Equivalent plastic strain at each quadrature point (old values
        from the beginning of the current load step).

    Returns
    -------
    f_int : (8, 3)
        Element internal force vector.
    alpha_new : (8,)
        Updated equivalent plastic strain at each quadrature point.
    """
    f_int = np.zeros((8, 3), dtype=np.float64)
    alpha_new = np.empty(8, dtype=np.float64)

    for q in range(_QUAD.n_points):
        xi, eta, zeta = _QUAD.points[q]
        w_q = _QUAD.weights[q]

        # 1. Shape function gradients in reference config
        dN_dX, detJ0 = _shape_grad_reference(X_elem, xi, eta, zeta)

        # 2. Displacement gradient: du/dX = u^T @ dN/dX -> (3, 3)
        grad_u = u_elem.T @ dN_dX

        # 3. Deformation gradient F = I + du/dX
        F = deformation_gradient(grad_u)

        # 4. Green-Lagrange strain E = (F^T F - I) / 2
        E = green_lagrange(F)

        # 5. Radial return mapping -> PK2 stress + updated alpha
        result = radial_return(mat, E, float(alpha_elem[q]))
        S = result.stress
        alpha_new[q] = result.alpha_new

        # 6. PK1 stress: P = F @ S
        P = F @ S

        # 7. Integrate: f_a += w_q * det(J0) * (dN_a/dX) @ P^T
        f_int += w_q * detJ0 * (dN_dX @ P.T)

    return f_int, alpha_new


def element_tangent_matvec_plastic(
    u_elem: NDArray,
    X_elem: NDArray,
    v_elem: NDArray,
    mat: J2PowerLawMaterial,
    alpha_elem: NDArray,
) -> NDArray:
    """Analytical tangent stiffness matvec for one J2 plastic Hex8 element.

    Computes K_e @ v via exact linearisation of the internal force:
        dP = grad_v @ S + F @ (C_ep : dE)
    where dE = sym(F^T @ grad_v) is the linearised Green-Lagrange strain
    and C_ep is the algorithmic consistent tangent from radial return.

    The history variables (alpha_elem) are held fixed — they represent
    the state at the beginning of the current load step.

    Parameters
    ----------
    u_elem : (8, 3)
        Element nodal displacements.
    X_elem : (8, 3)
        Element nodal reference coordinates.
    v_elem : (8, 3)
        Direction vector.
    mat : J2PowerLawMaterial
        Material parameters.
    alpha_elem : (8,)
        Equivalent plastic strain at each quadrature point (old values).

    Returns
    -------
    Kv : (8, 3)
        Tangent stiffness matvec result.
    """
    Kv = np.zeros((8, 3), dtype=np.float64)

    for q in range(_QUAD.n_points):
        xi, eta, zeta = _QUAD.points[q]
        w_q = _QUAD.weights[q]

        dN_dX, detJ0 = _shape_grad_reference(X_elem, xi, eta, zeta)

        # Current kinematics
        grad_u = u_elem.T @ dN_dX
        F = deformation_gradient(grad_u)
        E = green_lagrange(F)

        # Radial return gives PK2 stress and algorithmic tangent
        result = radial_return(mat, E, float(alpha_elem[q]))
        S = result.stress
        C4 = result.tangent

        # Linearisation in direction v
        grad_v = v_elem.T @ dN_dX
        dE = 0.5 * (F.T @ grad_v + grad_v.T @ F)  # linearised E
        dS = np.einsum("ijkl,kl->ij", C4, dE)  # linearised PK2
        dP = grad_v @ S + F @ dS  # linearised PK1

        Kv += w_q * detJ0 * (dN_dX @ dP.T)

    return Kv


# ---------------------------------------------------------------------------
# Global assembly (matrix-free)
# ---------------------------------------------------------------------------


def assemble_internal_force_plastic(
    u: NDArray,
    coords: NDArray,
    conn: NDArray,
    mat: J2PowerLawMaterial,
    history: HistoryFields,
) -> NDArray:
    """Assemble global internal force vector, updating history.alpha_current.

    Parameters
    ----------
    u : (n_nodes, 3)
        Global nodal displacements.
    coords : (n_nodes, 3)
        Reference coordinates.
    conn : (n_elem, 8)
        Element connectivity.
    mat : J2PowerLawMaterial
        Material parameters.
    history : HistoryFields
        History fields — alpha_old is read, alpha_current is written.

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
        alpha_elem = history.alpha_old[e]

        f_e, alpha_new_e = element_internal_force_plastic(u_elem, X_elem, mat, alpha_elem)

        # Update history for this element
        history.alpha_current[e] = alpha_new_e

        # Scatter element force to global
        for a in range(8):
            f_int[nodes[a]] += f_e[a]

    return f_int


def apply_tangent_matvec_plastic(
    u: NDArray,
    v: NDArray,
    coords: NDArray,
    conn: NDArray,
    mat: J2PowerLawMaterial,
    history: HistoryFields,
    bc_mask: NDArray,
) -> NDArray:
    """Global tangent matvec with Dirichlet BC enforcement for plastic problem.

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
    mat : J2PowerLawMaterial
        Material parameters.
    history : HistoryFields
        History fields — alpha_old is used for the tangent.
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
        alpha_elem = history.alpha_old[e]

        Kv_e = element_tangent_matvec_plastic(u_elem, X_elem, v_elem, mat, alpha_elem)
        for a in range(8):
            Kv[nodes[a]] += Kv_e[a]

    # Identity for constrained DOFs (preserves non-singularity for CG)
    Kv[bc_mask] = v[bc_mask]

    return Kv


# ---------------------------------------------------------------------------
# Boundary conditions (reuse from elastic ref)
# ---------------------------------------------------------------------------


def apply_dirichlet(
    u: NDArray,
    bc_mask: NDArray,
    bc_values: NDArray,
) -> NDArray:
    """Apply Dirichlet boundary conditions (same as elastic reference)."""
    u = u.copy()
    u[bc_mask] = bc_values[bc_mask]
    return u


# ---------------------------------------------------------------------------
# Newton-Raphson solver with load stepping
# ---------------------------------------------------------------------------


def solve_plastic(
    coords: NDArray,
    conn: NDArray,
    mat: J2PowerLawMaterial,
    bc_mask: NDArray,
    bc_values: NDArray,
    f_ext: NDArray,
    n_steps: int = 10,
    tol: float = 1e-8,
    max_iter: int = 50,
    cg_tol: float = 1e-10,
    cg_max_iter: int = 2000,
) -> tuple[NDArray, HistoryFields, list[list[float]]]:
    """Solve elasto-plastic BVP with uniform load stepping.

    Simple uniform load stepping: external force and prescribed displacements
    are ramped linearly over ``n_steps`` equal increments. Within each step,
    Newton-Raphson iteration drives the residual to convergence.

    Parameters
    ----------
    coords : (n_nodes, 3)
        Reference coordinates.
    conn : (n_elem, 8)
        Element connectivity.
    mat : J2PowerLawMaterial
        Material parameters.
    bc_mask : (n_nodes, 3), dtype bool
        True for constrained DOFs.
    bc_values : (n_nodes, 3)
        Prescribed displacement values (full load level).
    f_ext : (n_nodes, 3)
        External force vector (full load level).
    n_steps : int
        Number of load steps.
    tol : float
        Relative Newton tolerance: ||R|| < tol * ||R_0||.
    max_iter : int
        Maximum Newton iterations per step.
    cg_tol : float
        Relative CG tolerance.
    cg_max_iter : int
        Maximum CG iterations.

    Returns
    -------
    u : (n_nodes, 3)
        Converged displacement field at full load.
    history : HistoryFields
        Final history state.
    residual_history : list[list[float]]
        Residual norm at each Newton iteration for each load step.
    """
    n_nodes = coords.shape[0]
    n_elem = conn.shape[0]
    ndof = n_nodes * 3

    u = np.zeros((n_nodes, 3), dtype=np.float64)
    history = HistoryFields(n_elem)
    cg_solver = ScipyCGSolver()
    residual_history: list[list[float]] = []

    for step in range(1, n_steps + 1):
        load_fraction = step / n_steps

        # Scale external force and BCs for this step
        f_ext_step = load_fraction * f_ext
        bc_values_step = load_fraction * bc_values

        # Apply BCs for this step
        u = apply_dirichlet(u, bc_mask, bc_values_step)

        step_residuals: list[float] = []
        R0_norm: float | None = None

        for newton_iter in range(max_iter):
            # Compute residual: R = f_ext - f_int(u)
            f_int = assemble_internal_force_plastic(u, coords, conn, mat, history)
            R = f_ext_step - f_int

            # Zero constrained DOFs in residual
            R[bc_mask] = 0.0

            R_norm = float(np.linalg.norm(R))
            step_residuals.append(R_norm)

            # First iteration: store reference norm
            if newton_iter == 0:
                R0_norm = R_norm
                if R0_norm < 1e-15:
                    break

            assert R0_norm is not None
            if R_norm < tol * R0_norm:
                break

            # Solve tangent system K(u) @ du = R using CG
            def matvec(v_flat: NDArray, _u: NDArray = u) -> NDArray:
                v = v_flat.reshape((n_nodes, 3))
                Kv = apply_tangent_matvec_plastic(_u, v, coords, conn, mat, history, bc_mask)
                return Kv.ravel()

            R_flat = R.ravel()
            du_flat, _cg_iters, _cg_res = cg_solver.solve(
                matvec, R_flat, np.zeros(ndof, dtype=np.float64), cg_tol, cg_max_iter
            )

            du = du_flat.reshape((n_nodes, 3))
            du[bc_mask] = 0.0

            u = u + du
        else:
            # Newton did not converge — rollback and raise
            history.rollback()
            msg = (
                f"Newton did not converge at step {step}/{n_steps} "
                f"after {max_iter} iterations. "
                f"Final |R| = {step_residuals[-1]:.3e}, |R0| = {step_residuals[0]:.3e}"
            )
            raise RuntimeError(msg)

        # Converged — commit history
        history.commit()
        residual_history.append(step_residuals)

    return u, history, residual_history
