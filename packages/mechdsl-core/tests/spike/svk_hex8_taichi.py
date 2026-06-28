r"""All-Taichi St. Venant-Kirchhoff Hex8 spike (PlanJune14 **PJ-1**).

This module is the *architecture gate* of PlanJune14: it demonstrates that the
**Seams & Bodies** model composes end-to-end into an all-Taichi nonlinear solve
with **no NumPy in the operator/solve hot path**, matching the handwritten NumPy
reference (``tests/ref/ref_hex8_elastic.solve_elastic``) to < 1e-10.

What it composes
----------------

* **Operator (the body PJ-3 will generate).** A matrix-free ``@ti.kernel`` SVK
  tangent that recomputes ``K_e · v_e`` on the fly per matvec — element tangents
  are *never stored* (locked decision **D-A**, 06-CODEGEN §3.3). The kinematics
  (F→E→S) and the consistent linearisation ``dP = grad_v·S + F·(C:dE)`` are
  evaluated inline using the Tier-1 ``ti_runtime.tensor_ti`` ``@ti.func`` helpers
  and ``ti_runtime.hex8`` shape gradients.
* **Seams (``ti_runtime``, PJ-0).** The operator is injected through
  :class:`ti_runtime.seams.LinearSolveContext` (``set_operator`` / ``apply_A``);
  the solver body calls only ``apply_A`` / ``apply_preconditioner`` plus the
  ``ti_runtime.vector_ops`` primitives.
* **Solver (the body PJ-2's algo2code backend will generate).** A matrix-free PCG
  whose lines map one-to-one to the canonical PCG algpseudocode
  (``algo2code.library.pcg``); here it operates over Taichi vector fields via the
  seams instead of a dense ``A`` field. The hand-written line-by-line numpy twin
  of the *same* LaTeX lives in ``mechdsl.solver.import_adapter.Algo2CodePCGSolver``.
* **Driver.** A thin Newton-Raphson loop; residual norms come from on-device
  reductions, so the operator and the linear solve never touch ``.to_numpy()``.

The ``@ti.kernel`` / ``@ti.func`` bodies and the :func:`pcg` driver are the
*operator/solve hot path*: they are deliberately free of ``np.`` / ``.to_numpy()``
(asserted by ``test_pj1_svk_spike``). NumPy appears only at the boundaries — host
setup (``_alloc_*``) and the final field→host extraction for verification.
"""

# NOTE: no ``from __future__ import annotations`` here — this module defines
# ``@ti.kernel`` / ``@ti.func`` bodies and Taichi requires *eager* annotation
# evaluation (PEP 563 would turn ``ti.template()`` into a string and break the
# JIT, the PJ-0 finding). Plain-Python forward references are quoted instead.

from dataclasses import dataclass

import numpy as np
import taichi as ti

from ti_runtime import fields, hex8
from ti_runtime import tensor_ti as tt
from ti_runtime import vector_ops as vops
from ti_runtime.seams import IdentityPreconditioner, LinearSolveContext

# Tiny pivot guard for the PCG breakdown test (matches the canonical LaTeX
# ``\If{$|pq| < 10^{-300}$}``).
_PQ_FLOOR = 1e-300


# ===========================================================================
# Operator body — matrix-free SVK Hex8 kernels (the body PJ-3 will generate)
# ===========================================================================


@ti.func
def _grad_col(dN: ti.template(), a: ti.template()):
    """Row ``a`` of an ``(8,3)`` shape-gradient matrix as a 3-vector."""
    return ti.Vector([dN[a, 0], dN[a, 1], dN[a, 2]], dt=ti.f64)


@ti.kernel
def _svk_internal_force(
    fout: ti.template(),
    u: ti.template(),
    coords: ti.template(),
    conn: ti.template(),
    lam: ti.f64,
    mu: ti.f64,
    n_elem: ti.i32,
):
    """Matrix-free assembly of the global internal force ``f_int(u)``.

    Total-Lagrangian SVK; mirrors ``ref_hex8_elastic.element_internal_force``
    integrated over 2×2×2 Gauss points and scattered to nodes. ``fout`` is
    assumed zeroed by the caller; the element→node scatter uses Taichi's
    implicit atomic add.
    """
    I3 = tt.identity3()
    for e in range(n_elem):
        for q in ti.static(range(hex8.N_QP)):
            xi, eta, zeta = ti.static(hex8.QUAD_POINTS[q])
            w = ti.static(hex8.QUAD_WEIGHTS[q])
            dN_xi = hex8.shape_grad_natural(xi, eta, zeta)  # (8,3) ∂N/∂ξ

            # Reference Jacobian J0 = X_elem^T · ∂N/∂ξ  and  ∂N/∂X = ∂N/∂ξ · J0^{-1}
            J0 = ti.Matrix.zero(ti.f64, 3, 3)
            for a in ti.static(range(hex8.N_NODES)):
                J0 += coords[conn[e, a]].outer_product(_grad_col(dN_xi, a))
            detJ0 = tt.det3(J0)
            J0inv_T = tt.inv3(J0).transpose()

            # Material displacement gradient  grad_u = u_elem^T · ∂N/∂X
            grad_u = ti.Matrix.zero(ti.f64, 3, 3)
            for a in ti.static(range(hex8.N_NODES)):
                grad_u += u[conn[e, a]].outer_product(J0inv_T @ _grad_col(dN_xi, a))

            F = tt.deformation_gradient(grad_u)
            E = tt.green_lagrange(F)
            S = lam * tt.trace3(E) * I3 + 2.0 * mu * E  # PK2 (SVK)
            P = F @ S  # PK1

            scale = w * detJ0
            for a in ti.static(range(hex8.N_NODES)):
                grad_N_a = J0inv_T @ _grad_col(dN_xi, a)
                fout[conn[e, a]] += scale * (P @ grad_N_a)


@ti.kernel
def _svk_tangent_matvec(
    out: ti.template(),
    v: ti.template(),
    u: ti.template(),
    coords: ti.template(),
    conn: ti.template(),
    lam: ti.f64,
    mu: ti.f64,
    n_elem: ti.i32,
):
    """Matrix-free tangent matvec ``out = K(u) · v`` — recomputed per call (D-A).

    Exact linearisation of the SVK internal force (06-CODEGEN §3.3): with
    ``dE = sym(F^T·grad_v)`` and the constant SVK tangent ``C:dE = lam·tr(dE)·I +
    2·mu·dE``, the linearised PK1 is ``dP = grad_v·S + F·(C:dE)``. Element
    contributions are scattered to nodes (implicit atomic add); ``out`` is assumed
    zeroed by the caller. No element stiffness is ever formed or stored.
    """
    I3 = tt.identity3()
    for e in range(n_elem):
        for q in ti.static(range(hex8.N_QP)):
            xi, eta, zeta = ti.static(hex8.QUAD_POINTS[q])
            w = ti.static(hex8.QUAD_WEIGHTS[q])
            dN_xi = hex8.shape_grad_natural(xi, eta, zeta)

            J0 = ti.Matrix.zero(ti.f64, 3, 3)
            for a in ti.static(range(hex8.N_NODES)):
                J0 += coords[conn[e, a]].outer_product(_grad_col(dN_xi, a))
            detJ0 = tt.det3(J0)
            J0inv_T = tt.inv3(J0).transpose()

            grad_u = ti.Matrix.zero(ti.f64, 3, 3)
            grad_v = ti.Matrix.zero(ti.f64, 3, 3)
            for a in ti.static(range(hex8.N_NODES)):
                grad_N_a = J0inv_T @ _grad_col(dN_xi, a)
                grad_u += u[conn[e, a]].outer_product(grad_N_a)
                grad_v += v[conn[e, a]].outer_product(grad_N_a)

            F = tt.deformation_gradient(grad_u)
            E = tt.green_lagrange(F)
            S = lam * tt.trace3(E) * I3 + 2.0 * mu * E  # current PK2

            dE = 0.5 * (F.transpose() @ grad_v + grad_v.transpose() @ F)
            dS = lam * tt.trace3(dE) * I3 + 2.0 * mu * dE  # C : dE  (SVK)
            dP = grad_v @ S + F @ dS  # linearised PK1

            scale = w * detJ0
            for a in ti.static(range(hex8.N_NODES)):
                grad_N_a = J0inv_T @ _grad_col(dN_xi, a)
                out[conn[e, a]] += scale * (dP @ grad_N_a)


# ===========================================================================
# Dirichlet seam kernels (a "free mask": 1.0 on free DOFs, 0.0 on constrained)
# ===========================================================================


@ti.kernel
def _apply_dirichlet(u: ti.template(), free: ti.template(), bc_val: ti.template()):
    """``u = free·u + (1-free)·bc_val`` — set prescribed values on constrained DOFs."""
    for I in u:
        one = ti.Vector([1.0, 1.0, 1.0], dt=ti.f64)
        u[I] = free[I] * u[I] + (one - free[I]) * bc_val[I]


@ti.kernel
def _mask_free(dst: ti.template(), src: ti.template(), free: ti.template()):
    """``dst = free·src`` — copy with constrained DOFs zeroed."""
    for I in dst:
        dst[I] = free[I] * src[I]


@ti.kernel
def _set_constrained(out: ti.template(), src: ti.template(), free: ti.template()):
    """``out = free·out + (1-free)·src`` — overwrite constrained DOFs with ``src``."""
    for I in out:
        one = ti.Vector([1.0, 1.0, 1.0], dt=ti.f64)
        out[I] = free[I] * out[I] + (one - free[I]) * src[I]


# ===========================================================================
# Solver body — matrix-free PCG over the seams (the body PJ-2 will generate)
# ===========================================================================


@dataclass
class _PCGWorkspace:
    """Pre-allocated scratch fields reused across every Newton linear solve."""

    r: "ti.Field"
    z: "ti.Field"
    p: "ti.Field"
    q: "ti.Field"
    Ax: "ti.Field"

    @staticmethod
    def alloc(n: int) -> "_PCGWorkspace":
        return _PCGWorkspace(
            r=fields.vector_field(3, n),
            z=fields.vector_field(3, n),
            p=fields.vector_field(3, n),
            q=fields.vector_field(3, n),
            Ax=fields.vector_field(3, n),
        )


def pcg(
    ctx: LinearSolveContext,
    ws: "_PCGWorkspace",
    b: "ti.Field",
    x: "ti.Field",
    tol: float,
    maxiter: int,
) -> tuple[int, float]:
    """Preconditioned Conjugate Gradient over the injection seams.

    A line-by-line realisation of the canonical PCG algpseudocode
    (``algo2code.library.pcg.PCG_ALGORITHM_LATEX``) operating on Taichi *vector
    fields*: the LaTeX ``A · p`` is the injected matrix-free operator
    (``ctx.apply_A``) and ``M^{-1}(r)`` is ``ctx.apply_preconditioner``; every
    other line is a ``ti_runtime.vector_ops`` primitive. Solves ``A x = b`` in
    place (``x`` carries the initial guess). Returns ``(iterations, residual)``.

    No ``np.`` / ``.to_numpy()`` here: ``dot`` / ``norm2`` are on-device kernel
    reductions returning Python floats.
    """
    apply_A = ctx.apply_A
    apply_M_inv = ctx.apply_preconditioner

    # r = b - A·x
    apply_A(ws.Ax, x)
    vops.copy(ws.r, b)
    vops.axpy(ws.r, -1.0, ws.Ax)

    r0 = vops.norm2(ws.r)
    if r0 == 0.0:
        return 0, 0.0

    apply_M_inv(ws.z, ws.r)  # z = M^{-1} r
    vops.copy(ws.p, ws.z)  # p = z
    rho = vops.dot(ws.r, ws.z)  # ρ = rᵀz

    for k in range(1, maxiter + 1):
        apply_A(ws.q, ws.p)  # q = A·p
        pq = vops.dot(ws.p, ws.q)  # pᵀq
        if abs(pq) < _PQ_FLOOR:
            break
        alpha = rho / pq
        vops.axpy(x, alpha, ws.p)  # x += α p
        vops.axpy(ws.r, -alpha, ws.q)  # r -= α q
        r_norm = vops.norm2(ws.r)
        if r_norm < tol * r0:
            return k, r_norm
        apply_M_inv(ws.z, ws.r)  # z = M^{-1} r
        rho_new = vops.dot(ws.r, ws.z)  # ρ_new = rᵀz
        beta = rho_new / rho
        vops.xpay(ws.p, beta, ws.z)  # p = β p + z
        rho = rho_new

    return maxiter, vops.norm2(ws.r)


# ===========================================================================
# Operator factory — bind the mesh/state to the seam's apply(out, x) contract
# ===========================================================================


def make_svk_operator(
    u: "ti.Field",
    coords: "ti.Field",
    conn: "ti.Field",
    free: "ti.Field",
    lam: float,
    mu: float,
    n_elem: int,
):
    """Build the injected matrix-free operator ``apply_A(out, v): out = K(u)·v``.

    Wraps :func:`_svk_tangent_matvec` with the same Dirichlet treatment as the
    reference (``ref_hex8_elastic.apply_tangent_matvec``): the input direction is
    masked to free DOFs, the matvec scatters element contributions, and the
    constrained rows are set to identity (``out = v`` there) so the global system
    stays non-singular for CG. ``u`` is read live, so the operator always reflects
    the current Newton iterate without rebinding.

    No ``np.`` / ``.to_numpy()``: a per-operator scratch field ``v_bc`` holds the
    masked direction so the caller's ``v`` is never mutated.
    """
    v_bc = fields.vector_field(3, u.shape[0])

    def apply_A(out: "ti.Field", v: "ti.Field") -> None:
        _mask_free(v_bc, v, free)  # v_bc = free · v
        out.fill(0.0)
        _svk_tangent_matvec(out, v_bc, u, coords, conn, lam, mu, n_elem)
        _set_constrained(out, v, free)  # identity rows on constrained DOFs

    return apply_A


# ===========================================================================
# Thin Newton driver
# ===========================================================================


@dataclass
class SVKProblem:
    """A single-material SVK BVP on a Hex8 mesh (host/NumPy description)."""

    coords: np.ndarray  # (n_nodes, 3) reference coordinates
    conn: np.ndarray  # (n_elem, 8) connectivity (int)
    lam: float
    mu: float
    bc_mask: np.ndarray  # (n_nodes, 3) bool — True on constrained DOFs
    bc_values: np.ndarray  # (n_nodes, 3) prescribed displacements
    f_ext: np.ndarray  # (n_nodes, 3) external force


def _alloc_fields(prob: SVKProblem):
    """Boundary: move the host problem description onto Taichi fields."""
    n_nodes = prob.coords.shape[0]
    n_elem = prob.conn.shape[0]

    coords = fields.vector_field(3, n_nodes)
    conn = fields.index_field((n_elem, hex8.N_NODES))
    free = fields.vector_field(3, n_nodes)
    bc_val = fields.vector_field(3, n_nodes)
    f_ext = fields.vector_field(3, n_nodes)
    u = fields.vector_field(3, n_nodes)

    coords.from_numpy(np.ascontiguousarray(prob.coords, dtype=np.float64))
    conn.from_numpy(np.ascontiguousarray(prob.conn, dtype=np.int32))
    free.from_numpy(np.ascontiguousarray(~prob.bc_mask, dtype=np.float64))  # 1=free
    bc_val.from_numpy(np.ascontiguousarray(prob.bc_values, dtype=np.float64))
    f_ext.from_numpy(np.ascontiguousarray(prob.f_ext, dtype=np.float64))
    u.fill(0.0)

    return n_nodes, n_elem, coords, conn, free, bc_val, f_ext, u


def solve_svk_hex8(
    prob: SVKProblem,
    *,
    arch: str = "cpu",
    newton_tol: float = 1e-10,
    newton_max_iter: int = 50,
    cg_tol: float = 1e-12,
    cg_max_iter: int = 2000,
) -> tuple[np.ndarray, list[float]]:
    """Solve an SVK Hex8 BVP fully on-device, returning ``(u, residual_history)``.

    Re-initialises Taichi for ``arch`` (clean field state), then runs Newton with
    the matrix-free SVK tangent operator injected into the ``ti_runtime`` seams and
    solved by :func:`pcg`. The operator and linear solve stay entirely on-device;
    only the final ``u.to_numpy()`` (verification output) crosses the boundary.
    """
    fields.init(arch=arch, default_fp=ti.f64)
    n_nodes, n_elem, coords, conn, free, bc_val, f_ext, u = _alloc_fields(prob)

    # Newton/PCG scratch — allocated once, reused every iteration.
    f_int = fields.vector_field(3, n_nodes)
    resid = fields.vector_field(3, n_nodes)
    du = fields.vector_field(3, n_nodes)
    ws = _PCGWorkspace.alloc(n_nodes)

    # Initial guess: prescribed values on constrained DOFs, zero elsewhere.
    _apply_dirichlet(u, free, bc_val)

    ctx = LinearSolveContext()
    ctx.set_operator(make_svk_operator(u, coords, conn, free, prob.lam, prob.mu, n_elem))
    ctx.set_preconditioner(IdentityPreconditioner())  # unpreconditioned (PJ-4 adds Jacobi)

    residual_history: list[float] = []
    r0_norm: float | None = None

    for newton_iter in range(newton_max_iter):
        # Residual  R = f_ext - f_int(u),  constrained DOFs zeroed.
        f_int.fill(0.0)
        _svk_internal_force(f_int, u, coords, conn, prob.lam, prob.mu, n_elem)
        vops.copy(resid, f_ext)
        vops.axpy(resid, -1.0, f_int)  # R = f_ext - f_int
        _mask_free(resid, resid, free)  # zero constrained rows

        r_norm = vops.norm2(resid)
        residual_history.append(r_norm)

        if newton_iter == 0:
            r0_norm = r_norm
            if r0_norm < 1e-15:
                break
        assert r0_norm is not None
        if r_norm < newton_tol * r0_norm:
            break

        # Solve  K(u) · du = R  (matrix-free, injected operator + PCG).
        du.fill(0.0)
        pcg(ctx, ws, resid, du, cg_tol, cg_max_iter)
        _mask_free(du, du, free)  # keep constrained DOFs fixed
        vops.axpy(u, 1.0, du)  # u += du
    else:
        raise RuntimeError(
            f"Newton did not converge after {newton_max_iter} iterations; "
            f"final |R| = {residual_history[-1]:.3e}"
        )

    return u.to_numpy(), residual_history


# ===========================================================================
# Element-level helpers (boundary NumPy) — used by the convention-parity tests
# ===========================================================================


def single_element_internal_force(
    u_elem: np.ndarray, X_elem: np.ndarray, lam: float, mu: float, arch: str = "cpu"
) -> np.ndarray:
    """Run the Taichi internal-force kernel on one Hex8 element → ``(8,3)`` array.

    Isolates the operator's kinematics/quadrature convention from the solver so
    parity vs ``ref_hex8_elastic.element_internal_force`` can be checked directly.
    """
    fields.init(arch=arch, default_fp=ti.f64)
    coords = fields.vector_field(3, hex8.N_NODES)
    u = fields.vector_field(3, hex8.N_NODES)
    conn = fields.index_field((1, hex8.N_NODES))
    fout = fields.vector_field(3, hex8.N_NODES)

    coords.from_numpy(np.ascontiguousarray(X_elem, dtype=np.float64))
    u.from_numpy(np.ascontiguousarray(u_elem, dtype=np.float64))
    conn.from_numpy(np.arange(hex8.N_NODES, dtype=np.int32).reshape(1, hex8.N_NODES))
    fout.fill(0.0)

    _svk_internal_force(fout, u, coords, conn, lam, mu, 1)
    return fout.to_numpy()


def single_element_tangent_matvec(
    u_elem: np.ndarray,
    X_elem: np.ndarray,
    v_elem: np.ndarray,
    lam: float,
    mu: float,
    arch: str = "cpu",
) -> np.ndarray:
    """Run the Taichi tangent kernel on one Hex8 element → ``(8,3)`` array."""
    fields.init(arch=arch, default_fp=ti.f64)
    coords = fields.vector_field(3, hex8.N_NODES)
    u = fields.vector_field(3, hex8.N_NODES)
    v = fields.vector_field(3, hex8.N_NODES)
    conn = fields.index_field((1, hex8.N_NODES))
    out = fields.vector_field(3, hex8.N_NODES)

    coords.from_numpy(np.ascontiguousarray(X_elem, dtype=np.float64))
    u.from_numpy(np.ascontiguousarray(u_elem, dtype=np.float64))
    v.from_numpy(np.ascontiguousarray(v_elem, dtype=np.float64))
    conn.from_numpy(np.arange(hex8.N_NODES, dtype=np.int32).reshape(1, hex8.N_NODES))
    out.fill(0.0)

    _svk_tangent_matvec(out, v, u, coords, conn, lam, mu, 1)
    return out.to_numpy()
