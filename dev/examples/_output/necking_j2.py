"""Auto-generated Taichi FEM solver. DO NOT EDIT.

Formulation : total_lagrangian
Material    : j2_power_law
Element     : hex8
Dimension   : 3
"""

import taichi as ti
import numpy as np

ti.init(default_fp=ti.f64, arch=ti.cpu)

# ======================================================================
# Element constants: Hex8, 2x2x2 Gauss quadrature
# ======================================================================

N_NODES = 8
N_QP = 8
DIM = 3
N_DOF_ELEM = N_NODES * DIM  # 24

QUAD_WEIGHTS = [1, 1, 1, 1, 1, 1, 1, 1]

SHAPE_AT_QUAD = [
    [0.49056261216234409, 0.13144585576580212, 0.035220810900864506, 0.13144585576580212, 0.13144585576580212, 0.035220810900864506, 0.0094373878376559257, 0.035220810900864506],
    [0.13144585576580212, 0.035220810900864506, 0.0094373878376559257, 0.035220810900864506, 0.49056261216234409, 0.13144585576580212, 0.035220810900864506, 0.13144585576580212],
    [0.13144585576580212, 0.035220810900864506, 0.13144585576580212, 0.49056261216234409, 0.035220810900864506, 0.0094373878376559257, 0.035220810900864506, 0.13144585576580212],
    [0.035220810900864506, 0.0094373878376559257, 0.035220810900864506, 0.13144585576580212, 0.13144585576580212, 0.035220810900864506, 0.13144585576580212, 0.49056261216234409],
    [0.13144585576580212, 0.49056261216234409, 0.13144585576580212, 0.035220810900864506, 0.035220810900864506, 0.13144585576580212, 0.035220810900864506, 0.0094373878376559257],
    [0.035220810900864506, 0.13144585576580212, 0.035220810900864506, 0.0094373878376559257, 0.13144585576580212, 0.49056261216234409, 0.13144585576580212, 0.035220810900864506],
    [0.035220810900864506, 0.13144585576580212, 0.49056261216234409, 0.13144585576580212, 0.0094373878376559257, 0.035220810900864506, 0.13144585576580212, 0.035220810900864506],
    [0.0094373878376559257, 0.035220810900864506, 0.13144585576580212, 0.035220810900864506, 0.035220810900864506, 0.13144585576580212, 0.49056261216234409, 0.13144585576580212],
]

GRAD_AT_QUAD = [
    [
        [-0.31100423396407312, -0.31100423396407312, -0.31100423396407312],
        [0.31100423396407312, -0.083333333333333315, -0.083333333333333315],
        [0.083333333333333315, 0.083333333333333315, -0.022329099369260218],
        [-0.083333333333333315, 0.31100423396407312, -0.083333333333333315],
        [-0.083333333333333315, -0.083333333333333315, 0.31100423396407312],
        [0.083333333333333315, -0.022329099369260218, 0.083333333333333315],
        [0.022329099369260218, 0.022329099369260218, 0.022329099369260218],
        [-0.022329099369260218, 0.083333333333333315, 0.083333333333333315],
    ],
    [
        [-0.083333333333333315, -0.083333333333333315, -0.31100423396407312],
        [0.083333333333333315, -0.022329099369260218, -0.083333333333333315],
        [0.022329099369260218, 0.022329099369260218, -0.022329099369260218],
        [-0.022329099369260218, 0.083333333333333315, -0.083333333333333315],
        [-0.31100423396407312, -0.31100423396407312, 0.31100423396407312],
        [0.31100423396407312, -0.083333333333333315, 0.083333333333333315],
        [0.083333333333333315, 0.083333333333333315, 0.022329099369260218],
        [-0.083333333333333315, 0.31100423396407312, 0.083333333333333315],
    ],
    [
        [-0.083333333333333315, -0.31100423396407312, -0.083333333333333315],
        [0.083333333333333315, -0.083333333333333315, -0.022329099369260218],
        [0.31100423396407312, 0.083333333333333315, -0.083333333333333315],
        [-0.31100423396407312, 0.31100423396407312, -0.31100423396407312],
        [-0.022329099369260218, -0.083333333333333315, 0.083333333333333315],
        [0.022329099369260218, -0.022329099369260218, 0.022329099369260218],
        [0.083333333333333315, 0.022329099369260218, 0.083333333333333315],
        [-0.083333333333333315, 0.083333333333333315, 0.31100423396407312],
    ],
    [
        [-0.022329099369260218, -0.083333333333333315, -0.083333333333333315],
        [0.022329099369260218, -0.022329099369260218, -0.022329099369260218],
        [0.083333333333333315, 0.022329099369260218, -0.083333333333333315],
        [-0.083333333333333315, 0.083333333333333315, -0.31100423396407312],
        [-0.083333333333333315, -0.31100423396407312, 0.083333333333333315],
        [0.083333333333333315, -0.083333333333333315, 0.022329099369260218],
        [0.31100423396407312, 0.083333333333333315, 0.083333333333333315],
        [-0.31100423396407312, 0.31100423396407312, 0.31100423396407312],
    ],
    [
        [-0.31100423396407312, -0.083333333333333315, -0.083333333333333315],
        [0.31100423396407312, -0.31100423396407312, -0.31100423396407312],
        [0.083333333333333315, 0.31100423396407312, -0.083333333333333315],
        [-0.083333333333333315, 0.083333333333333315, -0.022329099369260218],
        [-0.083333333333333315, -0.022329099369260218, 0.083333333333333315],
        [0.083333333333333315, -0.083333333333333315, 0.31100423396407312],
        [0.022329099369260218, 0.083333333333333315, 0.083333333333333315],
        [-0.022329099369260218, 0.022329099369260218, 0.022329099369260218],
    ],
    [
        [-0.083333333333333315, -0.022329099369260218, -0.083333333333333315],
        [0.083333333333333315, -0.083333333333333315, -0.31100423396407312],
        [0.022329099369260218, 0.083333333333333315, -0.083333333333333315],
        [-0.022329099369260218, 0.022329099369260218, -0.022329099369260218],
        [-0.31100423396407312, -0.083333333333333315, 0.083333333333333315],
        [0.31100423396407312, -0.31100423396407312, 0.31100423396407312],
        [0.083333333333333315, 0.31100423396407312, 0.083333333333333315],
        [-0.083333333333333315, 0.083333333333333315, 0.022329099369260218],
    ],
    [
        [-0.083333333333333315, -0.083333333333333315, -0.022329099369260218],
        [0.083333333333333315, -0.31100423396407312, -0.083333333333333315],
        [0.31100423396407312, 0.31100423396407312, -0.31100423396407312],
        [-0.31100423396407312, 0.083333333333333315, -0.083333333333333315],
        [-0.022329099369260218, -0.022329099369260218, 0.022329099369260218],
        [0.022329099369260218, -0.083333333333333315, 0.083333333333333315],
        [0.083333333333333315, 0.083333333333333315, 0.31100423396407312],
        [-0.083333333333333315, 0.022329099369260218, 0.083333333333333315],
    ],
    [
        [-0.022329099369260218, -0.022329099369260218, -0.022329099369260218],
        [0.022329099369260218, -0.083333333333333315, -0.083333333333333315],
        [0.083333333333333315, 0.083333333333333315, -0.31100423396407312],
        [-0.083333333333333315, 0.022329099369260218, -0.083333333333333315],
        [-0.083333333333333315, -0.083333333333333315, 0.022329099369260218],
        [0.083333333333333315, -0.31100423396407312, 0.083333333333333315],
        [0.31100423396407312, 0.31100423396407312, 0.31100423396407312],
        [-0.31100423396407312, 0.083333333333333315, 0.083333333333333315],
    ],
]


# ======================================================================
# Field declarations (dimensions set by mesh loader at runtime)
# ======================================================================

# Placeholder dimensions -- overwritten by load_mesh()
n_nodes = 0
n_elem = 0

# Taichi fields -- allocated after mesh is loaded
x_ref = ti.Vector.field(3, dtype=ti.f64)       # reference coords
x_cur = ti.Vector.field(3, dtype=ti.f64)       # current coords
u = ti.Vector.field(3, dtype=ti.f64)            # displacement
f_int = ti.Vector.field(3, dtype=ti.f64)        # internal force
f_ext = ti.Vector.field(3, dtype=ti.f64)        # external force
residual = ti.Vector.field(3, dtype=ti.f64)     # residual = f_int - f_ext
du = ti.Vector.field(3, dtype=ti.f64)           # displacement increment
Kv = ti.Vector.field(3, dtype=ti.f64)           # tangent matvec result
elem_nodes = ti.field(dtype=ti.i32)             # connectivity
# History fields for J2 plasticity
alpha = ti.field(dtype=ti.f64)                    # accumulated plastic strain (n_elem x N_QP)


def allocate_fields(nn: int, ne: int) -> None:
    """Allocate Taichi fields after mesh dimensions are known."""
    global n_nodes, n_elem
    n_nodes = nn
    n_elem = ne
    ti.root.dense(ti.i, n_nodes).place(x_ref, x_cur, u, f_int, f_ext, residual, du, Kv)
    ti.root.dense(ti.ij, (n_elem, N_NODES)).place(elem_nodes)
    ti.root.dense(ti.ij, (n_elem, N_QP)).place(alpha)


# ======================================================================
# Constitutive model: j2_power_law
# ======================================================================

@ti.func
def constitutive_update_plastic(
    F: ti.types.matrix(3, 3, ti.f64),
    lam: ti.f64, mu: ti.f64,
    sigma_y0: ti.f64, K_hard: ti.f64, n_hard: ti.f64,
    alpha_old: ti.f64,
):
    """J2 power-law plasticity: radial return with Newton iteration.

    Returns (S, alpha_new) -- updated 2nd Piola-Kirchhoff stress
    and accumulated plastic strain.
    """
    # 1. Kinematics: right Cauchy-Green and Green-Lagrange strain
    C = F.transpose() @ F
    I3 = ti.Matrix.identity(ti.f64, 3)
    E = 0.5 * (C - I3)

    # 2. Elastic trial stress
    tr_E = ti.f64(0.0)
    for i in ti.static(range(3)):
        tr_E += E[i, i]
    S_trial = lam * tr_E * I3 + 2.0 * mu * E

    # 3. Deviatoric / volumetric split
    tr_S = S_trial[0, 0] + S_trial[1, 1] + S_trial[2, 2]
    S_dev = S_trial - (tr_S / 3.0) * I3

    # 4. Von Mises equivalent stress
    s_sq = ti.f64(0.0)
    for i in ti.static(range(3)):
        for j in ti.static(range(3)):
            s_sq += S_dev[i, j] * S_dev[i, j]
    sigma_eq = ti.sqrt(1.5 * s_sq)

    # 5. Yield check
    sigma_y = sigma_y0 + K_hard * ti.pow(alpha_old, n_hard)
    alpha_new = alpha_old
    S = S_trial

    if sigma_eq > 1e-12 * sigma_y and sigma_eq > sigma_y:
        # 6. Radial return: Newton iteration for delta_lambda
        dl = ti.f64(0.0)
        for _it in range(20):
            alpha_trial = alpha_old + dl
            sy = sigma_y0 + K_hard * ti.pow(alpha_trial, n_hard)
            f = sigma_eq - 3.0 * mu * dl - sy
            if ti.abs(f) < 1e-12:  # tol per 07-CONVENTIONS.md §6
                break
            H_prime = K_hard * n_hard * ti.pow(alpha_trial, n_hard - 1.0) if alpha_trial > 1e-30 else 0.0
            df = -3.0 * mu - H_prime
            dl -= f / df

        # Guard: check Newton convergence for return mapping
        f_final = sigma_eq - 3.0 * mu * dl - (sigma_y0 + K_hard * ti.pow(alpha_old + dl, n_hard))
        if ti.abs(f_final) > 1e-8:
            # Non-converged: set NaN flag (propagates to Newton driver)
            dl = ti.f64(float('nan'))

        # Clamp dl >= 0 (negative plastic multiplier is non-physical)
        dl = ti.max(dl, 0.0)

        # 7. Update stress and hardening variable
        factor = 1.0 - 3.0 * mu * dl / sigma_eq
        S_vol = (tr_S / 3.0) * I3
        S = S_vol + factor * S_dev
        alpha_new = alpha_old + dl

    return S, alpha_new

# ======================================================================
# Internal force kernel
# ======================================================================

@ti.kernel
def compute_internal_force(lam: ti.f64, mu: ti.f64,
                           sigma_y0: ti.f64, K_hard: ti.f64,
                           n_hard: ti.f64):
    """Compute internal force vector over all elements."""
    # Zero internal force
    for i in range(n_nodes):
        f_int[i] = ti.Vector([0.0, 0.0, 0.0], dt=ti.f64)

    # Loop over elements (runtime -- mesh index)
    for e in range(n_elem):
        # Gather element nodal coordinates (reference and current)
        X_elem = ti.Matrix.zero(ti.f64, N_NODES, DIM)
        x_elem = ti.Matrix.zero(ti.f64, N_NODES, DIM)
        for a in range(N_NODES):
            nid = elem_nodes[e, a]
            for d in ti.static(range(DIM)):
                X_elem[a, d] = x_ref[nid][d]
                x_elem[a, d] = x_ref[nid][d] + u[nid][d]

        # Quadrature loop (ti.static -- N_QP=8 is element-type constant,
        #   enables Python list access for GRAD_AT_QUAD and QUAD_WEIGHTS)
        for q in ti.static(range(N_QP)):
            # Shape function gradients in parametric space
            dN_dxi = ti.Matrix.zero(ti.f64, N_NODES, DIM)
            for a in ti.static(range(N_NODES)):
                for d in ti.static(range(DIM)):
                    dN_dxi[a, d] = GRAD_AT_QUAD[q][a][d]

            # Reference Jacobian J0 = X^T @ dN/dxi  (3x3)
            J0 = X_elem.transpose() @ dN_dxi
            detJ0 = J0.determinant()
            # Guard: degenerate element (07-CONVENTIONS.md §6) -- skip QP if detJ0 <= 1e-15
            if detJ0 > 1e-15:
                J0_inv = J0.inverse()

                # dN/dX = dN/dxi @ J0^{-1}  (N_NODES x DIM)
                dNdX = dN_dxi @ J0_inv

                # Deformation gradient F = I + grad_u
                # grad_u_{iI} = sum_a u_{ai} * dN_a/dX_I
                F = ti.Matrix.identity(ti.f64, DIM)
                for a in range(N_NODES):
                    nid = elem_nodes[e, a]
                    for i in ti.static(range(DIM)):
                        for I in ti.static(range(DIM)):
                            F[i, I] += u[nid][i] * dNdX[a, I]

                # Constitutive update (J2 plasticity): read alpha, compute, write back
                alpha_old = alpha[e, q]
                S, alpha_new = constitutive_update_plastic(F, lam, mu, sigma_y0, K_hard, n_hard, alpha_old)
                alpha[e, q] = alpha_new

                # 1st Piola-Kirchhoff stress P = F @ S
                P = F @ S

                # Integrate internal force: f_a_i += w_q * detJ0 * P_{iI} * dNdX_{aI}
                w_q = QUAD_WEIGHTS[q]
                for a in range(N_NODES):
                    nid = elem_nodes[e, a]
                    force_a = ti.Vector([0.0, 0.0, 0.0], dt=ti.f64)
                    for i in ti.static(range(DIM)):
                        val = ti.f64(0.0)
                        for I in ti.static(range(DIM)):
                            val += P[i, I] * dNdX[a, I]
                        force_a[i] = val
                    for i in ti.static(range(DIM)):
                        f_int[nid][i] += w_q * detJ0 * force_a[i]

# ======================================================================
# Tangent matvec (analytical consistent tangent)
# ======================================================================

def tangent_matvec(v_flat: np.ndarray, lam: float, mu: float,
                   sigma_y0: float, K_hard: float,
                   n_hard: float) -> np.ndarray:
    """Matrix-free tangent matvec: K(u) @ v via analytical linearisation.

    Parameters
    ----------
    v_flat : np.ndarray, shape (n_nodes * 3,)
        Direction vector.
    lam, mu : float
        Lame parameters.
    sigma_y0, K_hard, n_hard : float
        J2 plasticity parameters (used to reconstruct the
        algorithmic consistent tangent per quadrature point).

    Returns
    -------
    np.ndarray, shape (n_nodes * 3,)
        Exact tangent-vector product K @ v.
    """
    from mechdsl.symbolic.models.j2_power_law import (
        J2PowerLawMaterial,
        radial_return,
    )

    # Reconstruct the material object used by the symbolic return map.
    # The J2 material dataclass takes (E, nu) rather than (lam, mu);
    # recover them algebraically.
    _E = mu * (3.0 * lam + 2.0 * mu) / (lam + mu)
    _nu = lam / (2.0 * (lam + mu))
    _j2_mat = J2PowerLawMaterial(E=_E, nu=_nu, sigma_y0=sigma_y0, K=K_hard, n=n_hard)

    v = v_flat.reshape((-1, 3))
    Kv = np.zeros_like(v)

    # Snapshot Taichi fields into NumPy for the serial element loop.
    u_np = u.to_numpy()
    coords_np = x_ref.to_numpy()
    conn_np = elem_nodes.to_numpy()
    alpha_np = alpha.to_numpy()

    I3 = np.eye(3, dtype=np.float64)
    grad_at_quad_np = np.asarray(GRAD_AT_QUAD, dtype=np.float64)  # (N_QP, N_NODES, DIM)

    for e in range(n_elem):
        nodes = conn_np[e]
        u_elem = u_np[nodes]
        X_elem = coords_np[nodes]
        v_elem = v[nodes]
        Kv_e = np.zeros((N_NODES, DIM), dtype=np.float64)

        for q in range(N_QP):
            dN_dxi = grad_at_quad_np[q]  # (N_NODES, DIM)
            w_q = QUAD_WEIGHTS[q]

            J0 = X_elem.T @ dN_dxi
            detJ0 = float(np.linalg.det(J0))
            if detJ0 <= 1e-15:
                # Mirrors the runtime guard in compute_internal_force.
                continue
            dN_dX = dN_dxi @ np.linalg.inv(J0)

            # Current kinematics at this quadrature point.
            grad_u = u_elem.T @ dN_dX
            F = I3 + grad_u
            E = 0.5 * (F.T @ F - I3)

            # Linearised strain in direction v.
            grad_v = v_elem.T @ dN_dX
            dE = 0.5 * (F.T @ grad_v + grad_v.T @ F)

            # J2 algorithmic consistent tangent: re-run the return map
            # with the stored alpha.  The result supplies both the
            # current PK2 stress and the 4th-order tangent C_ep.
            rm = radial_return(_j2_mat, E, float(alpha_np[e, q]))
            S = rm.stress
            dS = np.einsum('ijkl,kl->ij', rm.tangent, dE)

            # dP = (geometric term) + (material term)
            dP = grad_v @ S + F @ dS

            Kv_e += w_q * detJ0 * (dN_dX @ dP.T)

        # Scatter element contribution to global tangent-vector product.
        for a in range(N_NODES):
            Kv[nodes[a]] += Kv_e[a]

    return Kv.ravel()

# ======================================================================
# Mesh validation
# ======================================================================


def validate_mesh() -> None:
    """Check all elements for degenerate Jacobians before solving.

    Raises ValueError if any quadrature point has det(J0) <= 0.
    """
    coords_np = x_ref.to_numpy()
    conn_np = elem_nodes.to_numpy()
    n_elem_val = conn_np.shape[0]
    for e in range(n_elem_val):
        X_e = coords_np[conn_np[e]]  # (8, 3)
        for q in range(N_QP):
            dN = np.array(GRAD_AT_QUAD[q])  # (8, 3)
            J0 = X_e.T @ dN  # (3, 3)
            detJ0 = np.linalg.det(J0)
            if detJ0 <= 0.0:
                raise ValueError(f"Degenerate element {e}: det(J0) = {detJ0:.6e} at quadrature point {q}. "
                f"Check element connectivity and node coordinates.")


# ======================================================================
# Newton-Raphson driver
# ======================================================================


def newton_solve(lam: float, mu: float,
                 sigma_y0: float, K_hard: float, n_hard: float,
                 bc_dofs: np.ndarray | None = None,
                 bc_values: np.ndarray | None = None,
                 max_iter: int = 20,
                 tol_abs: float = 1.0e-10,
                 tol_rel: float = 1.0e-8) -> int:
    """Newton-Raphson nonlinear solver with Dirichlet BC enforcement.

    Convergence is declared when ``res_norm < max(tol_abs, tol_rel * r0_norm)``.

    Parameters
    ----------
    lam, mu : float
        Lame parameters.
    sigma_y0, K_hard, n_hard : float
        J2 plasticity parameters.
    bc_dofs : np.ndarray | None
        Flat indices of constrained DOFs.  Residual, tangent matvec,
        and displacement update are zeroed at these DOFs.
    bc_values : np.ndarray | None
        Flat array of prescribed displacement values at constrained DOFs.
        Must have the same length as bc_dofs.  When provided, ``u`` is
        seeded with these values before the Newton loop (10-BOUNDARIES.md §6).
    max_iter : int
        Maximum Newton iterations.
    tol_abs : float
        Absolute convergence tolerance on residual norm.
    tol_rel : float
        Relative convergence tolerance (multiplied by initial residual norm).

    Returns
    -------
    int
        Number of iterations performed.
    """
    from mechdsl.solver.import_adapter import CGSolver

    # Pre-flight: reject degenerate elements before solving
    validate_mesh()

    n_dof = n_nodes * DIM
    res_norm = float('inf')
    r0_norm: float | None = None

    # Seed prescribed displacements (10-BOUNDARIES.md §4.2, §6)
    if bc_dofs is not None and bc_values is not None:
        u_arr = u.to_numpy().reshape(-1)
        u_arr[bc_dofs] = bc_values
        u.from_numpy(u_arr.reshape((-1, 3)))

    for iteration in range(max_iter):
        # Step 1: Compute internal force
        compute_internal_force(lam, mu, sigma_y0, K_hard, n_hard)

        # Step 2: Form residual = f_int - f_ext
        r = f_int.to_numpy() - f_ext.to_numpy()
        r_flat = r.ravel()

        # Enforce Dirichlet BCs: zero residual at constrained DOFs
        if bc_dofs is not None:
            r_flat[bc_dofs] = 0.0

        res_norm = np.linalg.norm(r_flat)

        # Record initial residual for relative tolerance
        if r0_norm is None:
            r0_norm = res_norm

        if not np.isfinite(res_norm):
            raise RuntimeError("NaN or Inf detected in Newton residual. Constitutive model may have failed to converge.")

        print(f"  Newton iter {iteration}: ||R|| = {res_norm:.6e}")

        # Converge when residual is below absolute OR relative threshold
        conv_threshold = max(tol_abs, tol_rel * r0_norm)
        if res_norm < conv_threshold:
            print(f"  Converged in {iteration} iterations.")
            return iteration

        # Step 3: Solve K @ du = -R using CG with tangent matvec
        def matvec(v: np.ndarray) -> np.ndarray:
            v_bc = v.copy() if bc_dofs is not None else v
            if bc_dofs is not None:
                v_bc[bc_dofs] = 0.0
            Kv = tangent_matvec(v_bc, lam, mu, sigma_y0, K_hard, n_hard)
            if bc_dofs is not None:
                Kv[bc_dofs] = v[bc_dofs]
            return Kv

        solver = CGSolver()
        du_flat, cg_iters, cg_res = solver.solve(
            matvec_fn=matvec, rhs=-r_flat,
            x0=np.zeros(n_dof), tol=1.0e-10, max_iter=2000,
        )

        # Enforce Dirichlet BCs on displacement update
        if bc_dofs is not None:
            du_flat[bc_dofs] = 0.0

        # Step 4: Update displacement
        du_arr = du_flat.reshape((-1, 3))
        u_arr = u.to_numpy()
        u.from_numpy(u_arr + du_arr)

    raise RuntimeError(f"Newton did not converge in {max_iter} iterations. Final |R| = {res_norm:.3e}")

# ======================================================================
# Postprocessing
# ======================================================================


def save_results(output_path: str = 'results.npz') -> None:
    """Save displacement results to .npz file."""
    u_arr = u.to_numpy()
    x_ref_arr = x_ref.to_numpy()
    np.savez(
        output_path,
        displacement=u_arr,
        reference_coords=x_ref_arr,
    )
    print(f"Results saved to {output_path}")

    # Optional VTK export via meshio
    try:
        import meshio
        points = x_ref_arr + u_arr
        conn_arr = elem_nodes.to_numpy()
        mesh = meshio.Mesh(
            points=points,
            cells=[("hexahedron", conn_arr)],
            point_data={"displacement": u_arr},
        )
        vtk_path = output_path.replace('.npz', '.vtk')
        meshio.write(vtk_path, mesh)
        print(f"VTK written to {vtk_path}")
    except ImportError:
        pass  # meshio not available


# ======================================================================
# Main entry point
# ======================================================================


if __name__ == "__main__":
    import sys

    # Load mesh
    mesh_path = sys.argv[1] if len(sys.argv) > 1 else "mesh.npz"
    print(f"Loading mesh from {mesh_path}")
    mesh_data = np.load(mesh_path)
    coords = mesh_data["coords"]
    conn = mesh_data["conn"]

    # Allocate Taichi fields and load mesh data
    n_nodes_mesh = coords.shape[0]
    n_elem_mesh = conn.shape[0]
    allocate_fields(n_nodes_mesh, n_elem_mesh)
    x_ref.from_numpy(coords)
    elem_nodes.from_numpy(conn)

    # Load boundary conditions from mesh file
    if "f_ext" in mesh_data:
        f_ext.from_numpy(mesh_data['f_ext'])
    else:
        print("Warning: no f_ext in mesh file; external forces default to zero.")

    bc_dofs = mesh_data["bc_dofs"] if "bc_dofs" in mesh_data else None

    # Normalize bc_values: accept (n_nodes, 3) or flat array matching bc_dofs
    bc_values_raw = mesh_data["bc_values"] if "bc_values" in mesh_data else None
    bc_values = None
    if bc_values_raw is not None and bc_dofs is not None:
        if bc_values_raw.ndim == 2:
            bc_values = bc_values_raw.ravel()[bc_dofs]
        else:
            bc_values = bc_values_raw

    # Material parameters
    lam_val = 115384.61538461538
    mu_val = 76923.076923076922
    sigma_y0_val = 250
    K_hard_val = 1000
    n_hard_val = 1

    # Run Newton solver
    # NOTE: Displacement-controlled plastic loading requires incremental
    # load stepping with alpha snapshot/rollback.  The standalone __main__
    # path does not implement this; use the newton_solve() API directly
    # with your own load-stepping driver (see test_e2e_plastic.py for an
    # example).  bc_values is intentionally NOT forwarded here.
    if bc_values is not None:
        print("WARNING: bc_values ignored for plastic __main__ path. "
        "Displacement-controlled J2 requires load stepping with alpha "
        "management. Use newton_solve() API with a custom driver.")
    n_iters = newton_solve(lam_val, mu_val,
                           sigma_y0_val, K_hard_val, n_hard_val,
                           bc_dofs=bc_dofs)

    print(f"Newton converged in {n_iters} iterations.")

    # Save results
    save_results()

