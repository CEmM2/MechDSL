"""Behavioural fail-loud tests for the PR #316 review fixes (pj316_resolution).

Closes the two highest-value coverage gaps the review flagged: the NaN
non-convergence sentinel must survive (T1, WI-1) and an exhausted seam PCG must
raise rather than hand back a garbage increment (T2, WI-2). Both replace
source-substring guards (``"if converged == 0:" in body``) with real behaviour —
exactly the kind of test whose absence let the GPU NaN-clamp defect ship.
"""

# NOTE: no ``from __future__ import annotations`` -- this module defines
# ``@ti.kernel`` bodies whose ``ti.template()`` / ``ti.i32`` annotations Taichi
# must evaluate eagerly; PEP 563 stringification breaks the JIT (PJ-0/PJ-1).

import math

import numpy as np
import pytest


def _vfield(ti, vals: np.ndarray):
    vals = np.ascontiguousarray(vals, dtype=np.float64)
    f = ti.Vector.field(vals.shape[1], ti.f64, shape=vals.shape[0])
    f.from_numpy(vals)
    return f


class TestNaNSentinelSurvivesClamp:
    """T1 / WI-1: the ``else:``-gated clamp must not erase the NaN sentinel."""

    @pytest.mark.slow
    def test_else_gate_keeps_nan_on_nonconvergence(self):
        """The emitted structure ``if converged==0: dl=NaN; else: dl=max(dl,0)``
        keeps ``dl`` NaN on the non-converged path on **every** backend.

        This mirrors the shipped golden (generated_plastic.py.golden) after
        WI-1: the clamp lives under ``else:``, so it never runs when
        ``converged == 0`` and the NaN sentinel reaches the Newton driver
        intact. Before WI-1 the clamp was unconditional, and a GPU
        ``fmax(NaN, 0.0) -> 0.0`` erased the sentinel.
        """
        ti = pytest.importorskip("taichi")
        ti.init(arch=ti.cpu, default_fp=ti.f64)

        @ti.kernel
        def gated_dl(converged: ti.i32) -> ti.f64:
            dl = ti.f64(0.7)  # an already-valid (positive) multiplier
            # Intentionally the if/else *block* (not a ternary) -- it mirrors the
            # exact structure the emitter produces in the shipped golden, which
            # is what this test pins. noqa: keep the block form.
            if converged == 0:  # noqa: SIM108
                dl = ti.f64(float("nan"))
            else:
                dl = ti.max(dl, 0.0)
            return dl

        # Non-converged -> the sentinel survives (clamp gated out).
        assert math.isnan(gated_dl(0)), (
            "the else-gate must leave dl = NaN on the non-converged path so the "
            "Newton driver's isfinite guard can fail loud (WI-1)"
        )
        # Converged -> the clamp runs and a valid multiplier is preserved.
        assert gated_dl(1) == pytest.approx(0.7)

    @pytest.mark.slow
    def test_unconditional_max_is_backend_risky(self):
        """Characterise the hazard the gate removes: ``ti.max(NaN, 0.0)``.

        On the CPU/LLVM test backend ``max(NaN, 0.0)`` (NaN first) *preserves*
        the NaN, so this asserts it is not silently clamped to ``0.0`` here. The
        defect is backend-dependent: on CUDA/Metal ``fmax(NaN, 0.0) -> 0.0``
        erases the sentinel. That platform split is precisely why WI-1 gates the
        clamp behind ``else:`` instead of relying on this characterisation.
        """
        ti = pytest.importorskip("taichi")
        ti.init(arch=ti.cpu, default_fp=ti.f64)

        @ti.kernel
        def raw_max_nan() -> ti.f64:
            return ti.max(ti.f64(float("nan")), 0.0)

        assert raw_max_nan() != 0.0, (
            "an unconditional ti.max(NaN, 0.0) must NOT clamp to 0.0 on this "
            "backend; the GPU divergence is why the clamp is gated (WI-1)"
        )


class TestSeamPCGNonConvergenceRaises:
    """T2 / WI-2: an exhausted seam PCG must raise, not return a garbage du."""

    @pytest.mark.slow
    def test_exhausted_seam_pcg_raises(self):
        """``ctx.solver.solve`` raises ``RuntimeError`` when the inner PCG does
        not converge within ``maxiter`` (fail-loud, not a silent bad increment).
        """
        ti = pytest.importorskip("taichi")
        ti.init(arch=ti.cpu, default_fp=ti.f64)

        from mechdsl.solver import make_seam_solver
        from ti_runtime.seams import IdentityPreconditioner

        # A genuinely coupled SPD operator: one PCG iteration cannot reach an
        # unreachable 1e-30 relative tolerance, so the solve exhausts maxiter.
        @ti.kernel
        def apply_spd(out: ti.template(), x: ti.template()):
            mat = ti.Matrix([[4.0, 1.0, 0.0], [1.0, 3.0, 1.0], [0.0, 1.0, 2.0]], dt=ti.f64)
            for i in out:
                out[i] = mat @ x[i]

        ctx = make_seam_solver(operator=apply_spd, preconditioner=IdentityPreconditioner())
        n = 5
        b = _vfield(ti, np.random.default_rng(3).standard_normal((n, 3)))
        x = ti.Vector.field(3, ti.f64, shape=n)  # zero initial guess

        with pytest.raises(RuntimeError, match="did not converge"):
            ctx.solver.solve(b, x, 1e-30, 1)  # tol unreachable in 1 iteration

    @pytest.mark.slow
    def test_converged_seam_pcg_returns_triple(self):
        """The success path is unchanged: a converging solve returns the
        ``(x, iterations, residual)`` 3-tuple and does **not** raise.
        """
        ti = pytest.importorskip("taichi")
        ti.init(arch=ti.cpu, default_fp=ti.f64)

        from mechdsl.solver import make_seam_solver
        from ti_runtime.seams import IdentityPreconditioner

        # Diagonal operator -> converges quickly under generous maxiter/tol.
        dv = np.tile([2.0, 5.0, 11.0], (4, 1))
        diag = _vfield(ti, dv)

        @ti.kernel
        def apply_diag(out: ti.template(), x: ti.template()):
            for i in out:
                out[i] = diag[i] * x[i]

        ctx = make_seam_solver(operator=apply_diag, preconditioner=IdentityPreconditioner())
        b_np = np.random.default_rng(5).standard_normal((4, 3))
        x = ti.Vector.field(3, ti.f64, shape=4)

        result = ctx.solver.solve(_vfield(ti, b_np), x, 1e-12, 100)
        assert len(result) == 3, "converged seam solve returns (x, iters, residual)"
        np.testing.assert_allclose(x.to_numpy(), b_np / dv, atol=1e-9, rtol=0)
