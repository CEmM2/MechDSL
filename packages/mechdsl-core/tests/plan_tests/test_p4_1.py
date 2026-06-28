"""Tests for Task P4-1 (PlanJune14 Phase 4).

Generated Jacobi (point-diagonal) preconditioner from `dev/algorithms/jacobi.tex`,
realised via `mechdsl.solver.jacobi_preconditioner.GeneratedJacobiPreconditioner`
(the `ti_runtime.vector_ops.ediv` primitive + the `PreconditionerBase` seam) and
injected through `ti_runtime` `set_preconditioner`. All-Taichi (Option 1) — no
NumPy in the apply hot path.

Grammar-gap note: algo2code cannot yet express elementwise vector divide
(`z = r / d`) for `ti.Vector.field`; the body is the authorized minimal fallback
(a `@ti.kernel` `ediv` wired to the seam), with `jacobi.tex` as the LaTeX source.
"""

# NOTE: no `from __future__ import annotations` — these tests define a @ti.kernel
# whose ti.template() annotations Taichi must evaluate eagerly (PEP 563 breaks JIT).

import numpy as np
import pytest
import taichi as ti

from mechdsl.solver.jacobi_preconditioner import GeneratedJacobiPreconditioner
from ti_runtime import vector_ops as vops
from ti_runtime.seams import (
    DiagonalPreconditioner,
    IdentityPreconditioner,
    LinearSolveContext,
)

pytestmark = pytest.mark.slow  # executes Taichi kernels (JIT)


def _vfield(vals: np.ndarray):
    vals = np.ascontiguousarray(vals, dtype=np.float64)
    f = ti.Vector.field(vals.shape[1], ti.f64, shape=vals.shape[0])
    f.from_numpy(vals)
    return f


class TestTaskP4_1:
    """Tests for Task P4-1: generated Jacobi preconditioner. AC 1-3."""

    def test_generated_jacobi_equals_diagonal_preconditioner(self):
        """AC-1: generated Jacobi M^{-1}r == ti_runtime DiagonalPreconditioner on a known diagonal."""
        ti.init(arch=ti.cpu, default_fp=ti.f64)
        rng = np.random.default_rng(3)
        rv = rng.standard_normal((4, 3))
        dv = np.abs(rng.standard_normal((4, 3))) + 0.5  # strictly positive diagonal

        r = _vfield(rv)
        d_gen = _vfield(dv)
        d_ref = _vfield(dv)
        z_gen = ti.Vector.field(3, ti.f64, shape=4)
        z_ref = ti.Vector.field(3, ti.f64, shape=4)

        GeneratedJacobiPreconditioner(diag=d_gen, eps=1e-12).apply(z_gen, r)
        DiagonalPreconditioner(d_ref, eps=1e-12).apply(z_ref, r)

        np.testing.assert_allclose(z_gen.to_numpy(), z_ref.to_numpy(), rtol=1e-12, atol=1e-14)
        # And it is genuinely M^{-1} r = r / d.
        np.testing.assert_allclose(z_gen.to_numpy(), rv / dv, rtol=1e-12)

    def test_generated_jacobi_injects_via_set_preconditioner(self):
        """AC-2: the generated body injects via set_preconditioner and apply_preconditioner(z, r) works."""
        ti.init(arch=ti.cpu, default_fp=ti.f64)
        rv = np.array([[2.0, 4.0, 6.0], [8.0, 10.0, 12.0]])
        dv = np.array([[2.0, 4.0, 8.0], [4.0, 5.0, 6.0]])
        r = _vfield(rv)
        d = _vfield(dv)
        z = ti.Vector.field(3, ti.f64, shape=2)

        ctx = LinearSolveContext().set_preconditioner(GeneratedJacobiPreconditioner(diag=d))
        ctx.apply_preconditioner(z, r)

        np.testing.assert_allclose(z.to_numpy(), rv / dv, rtol=1e-12)

    def test_jacobi_reduces_pcg_iterations_vs_identity(self):
        """AC-3: PCG with the generated Jacobi converges in fewer iters than identity (conditioned SPD)."""
        from tests.spike.svk_hex8_taichi import _PCGWorkspace, pcg

        ti.init(arch=ti.cpu, default_fp=ti.f64)
        n = 6
        # Diagonal SPD operator A = diag(d) with 3 distinct eigenvalues {2,5,11}.
        # Unpreconditioned CG converges in #distinct-eigenvalues (=3) iterations;
        # Jacobi (M = A) gives M^{-1}A = I → 1 iteration.
        dv = np.tile([2.0, 5.0, 11.0], (n, 1))
        diag = _vfield(dv)

        @ti.kernel
        def _apply_diag_op(out: ti.template(), x: ti.template(), d: ti.template()):
            for i in out:
                out[i] = d[i] * x[i]

        def make_apply_A(d):
            def apply_A(out, x):
                _apply_diag_op(out, x, d)

            return apply_A

        rng = np.random.default_rng(11)
        bv = rng.standard_normal((n, 3))

        def _solve(precond):
            b = _vfield(bv)
            x = ti.Vector.field(3, ti.f64, shape=n)  # zero initial guess
            ws = _PCGWorkspace.alloc(n)
            ctx = LinearSolveContext().set_operator(make_apply_A(diag)).set_preconditioner(precond)
            iters, _res = pcg(ctx, ws, b, x, tol=1e-12, maxiter=50)
            return iters, x.to_numpy()

        jac_iters, x_jac = _solve(GeneratedJacobiPreconditioner(diag=diag))
        id_iters, x_id = _solve(IdentityPreconditioner())

        expected = bv / dv  # A = diag(d) → x = b / d
        np.testing.assert_allclose(x_jac, expected, atol=1e-9)
        np.testing.assert_allclose(x_id, expected, atol=1e-9)

        assert jac_iters < id_iters, (
            f"Jacobi should converge in fewer iters than identity; "
            f"jacobi={jac_iters}, identity={id_iters}"
        )
        assert jac_iters <= 2, (
            f"Jacobi on a diagonal operator should converge ~1 iter; got {jac_iters}"
        )


def test_ediv_primitive_guards_near_zero_diagonal():
    """The ti_runtime ediv primitive guards against a near-zero diagonal via max(d, eps)."""
    ti.init(arch=ti.cpu, default_fp=ti.f64)
    r = _vfield(np.array([[1.0, 1.0, 1.0]]))
    d = _vfield(np.array([[0.0, 1e-20, 2.0]]))  # zero / tiny / normal
    z = ti.Vector.field(3, ti.f64, shape=1)
    vops.ediv(z, r, d, 1e-12)
    out = z.to_numpy()[0]
    assert np.isfinite(out).all(), "ediv must produce finite output on a near-zero diagonal"
    assert out[0] == pytest.approx(1.0 / 1e-12)  # guarded by eps
    assert out[2] == pytest.approx(0.5)
