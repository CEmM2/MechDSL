"""PJ-0 — injection seams + a mini-CG composition (PJ-1 preview).

The composition test is the important one: it injects a matrix-free operator and
runs a hand-written CG (the shape algo2code will *generate*) using only the seam
(`apply_A`) and `vector_ops` primitives — proving the seams + primitives compose
into a working solver with no NumPy in the operator/solve hot path.
"""

import numpy as np
import pytest
import taichi as ti

from ti_runtime import vector_ops as v
from ti_runtime.seams import (
    DiagonalPreconditioner,
    IdentityPreconditioner,
    LinearSolveContext,
    Operator,
)

pytestmark = pytest.mark.slow  # executes Taichi kernels (JIT)


def _vfield(vals: np.ndarray):
    vals = np.ascontiguousarray(vals, dtype=np.float64)
    f = ti.Vector.field(vals.shape[1], ti.f64, shape=vals.shape[0])
    f.from_numpy(vals)
    return f


def test_operator_requires_body():
    op = Operator()
    out = ti.Vector.field(3, ti.f64, shape=2)
    x = ti.Vector.field(3, ti.f64, shape=2)
    with pytest.raises(RuntimeError, match="no body injected"):
        op.apply(out, x)


def test_identity_preconditioner_copies():
    r = _vfield(np.arange(6.0).reshape(2, 3))
    z = ti.Vector.field(3, ti.f64, shape=2)
    IdentityPreconditioner().apply(z, r)
    np.testing.assert_allclose(z.to_numpy(), r.to_numpy())


def test_diagonal_preconditioner_inverts():
    rv = np.array([[2.0, 4.0, 6.0]])
    dv = np.array([[2.0, 4.0, 8.0]])
    r, d = _vfield(rv), _vfield(dv)
    z = ti.Vector.field(3, ti.f64, shape=1)
    DiagonalPreconditioner(d).apply(z, r)
    np.testing.assert_allclose(z.to_numpy(), rv / dv, rtol=1e-12)


# Block-diagonal SPD operator: out[i] = M @ x[i] with a fixed SPD 3x3 M.
_M = np.array([[4.0, 1.0, 0.0], [1.0, 3.0, 1.0], [0.0, 1.0, 2.0]])


@ti.kernel
def _apply_M(out: ti.template(), x: ti.template()):
    M = ti.Matrix([[4.0, 1.0, 0.0], [1.0, 3.0, 1.0], [0.0, 1.0, 2.0]], dt=ti.f64)
    for i in out:
        out[i] = M @ x[i]


def _cg(ctx: LinearSolveContext, b, x, tol=1e-12, maxiter=100):
    """Hand-written CG (the body algo2code generates) over the seam + primitives."""
    n = b.shape[0]
    r = ti.Vector.field(3, ti.f64, shape=n)
    p = ti.Vector.field(3, ti.f64, shape=n)
    ap = ti.Vector.field(3, ti.f64, shape=n)
    v.copy(r, b)  # x0 = 0  ->  r = b - A x0 = b
    v.copy(p, r)
    rz = v.dot(r, r)
    for _ in range(maxiter):
        ctx.apply_A(ap, p)
        alpha = rz / v.dot(p, ap)
        v.axpy(x, alpha, p)
        v.axpy(r, -alpha, ap)
        rz_new = v.dot(r, r)
        if rz_new**0.5 < tol:
            break
        v.xpay(p, rz_new / rz, r)  # p = beta*p + r
        rz = rz_new
    return x


def test_cg_composition_solves_spd_system():
    rng = np.random.default_rng(7)
    n = 5
    bv = rng.standard_normal((n, 3))
    b = _vfield(bv)
    x = ti.Vector.field(3, ti.f64, shape=n)  # zero initial guess

    ctx = LinearSolveContext().set_operator(_apply_M)
    _cg(ctx, b, x)

    expected = np.linalg.solve(_M, bv.T).T  # per-node M^{-1} b
    np.testing.assert_allclose(x.to_numpy(), expected, atol=1e-9)
