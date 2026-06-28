"""Tests for Task P6-1 (PlanJune14 Phase 6) — time integrators through a seam.

**OPTIONAL phase** (plan lines 136–137, "optional/next"). Author Newmark-β (HHT
optional) as a LaTeX algorithm box (``dev/algorithms/newmark.tex``), transpile it
via algo2code, and inject it through a **new ``ti_runtime`` time-integration seam**
(``set_integrator`` / ``step``, mirroring the ``LinearSolveContext.set_operator`` /
``set_solver`` linear-solve seam from P2-2/P4) — proving the "any algorithm box"
claim end-to-end. Validate a small dynamic problem against an analytic SDOF
response.

This is distinct from the existing **explicit** central-difference integrator
(``test_explicit_integrator.py`` — lumped mass, P7-1 explicit dynamics), which is
a different scheme and is NOT seam-injected. That test's single-step analytic
hand-calc is a useful *pattern* for case 1, and explicit dynamics is a regression
baseline (the new seam must not break it), but it covers neither P6-1 case.

Acceptance criteria covered:
  AC-1  The generated Newmark-β integrator advances a dynamic problem correctly —
        matches an analytic single-DOF (SDOF) response within tolerance (slow —
        Taichi JIT; e2e — LaTeX → algo2code → injected step → verify).
  AC-2  The integrator is injected via the ``ti_runtime`` time-integration seam,
        with **no NumPy in the step hot path**.

NOTE: no ``from __future__ import annotations`` — the seam-injected step imports
Taichi-templated generated code that needs eager ``@ti.template()`` evaluation
(PEP 563 stringifies the annotations and breaks the JIT — the
test_p3_2 / test_p4_3 / test_p5_1 finding).

algo2code grammar result (2026-06-15): the Newmark box transpiles **directly** —
no grammar gap. The predictor/corrector updates are all ``scalar*vector`` /
``vector +/- vector`` (fused ``_v.vec_add``), the coefficients are scalar
arithmetic, and the acceleration solve is an in-place ``callable`` (the
matrix-free seam). The generated ``newmark_step`` body is pure
``_v.vec_add`` / ``_v.copy`` / ``solve_a(...)`` — no NumPy.
"""

import ast
import math

import numpy as np
import pytest

from mechdsl.solver.seam_integrate import (
    bind_generated_newmark_integrator,
    build_seam_newmark,
    transpile_seam_newmark,
)

# Average-acceleration (trapezoidal) Newmark: unconditionally stable, second
# order, no algorithmic damping. gamma = 1/2 is what makes the scheme 2nd order.
_BETA = 0.25
_GAMMA = 0.5


def _make_undamped_sdof_solve_a(k: float, m: float, dt: float):
    """Build the in-place acceleration solve for an undamped SDOF: m·ü + k·u = 0.

    Newmark's only system solve is for ``a_{n+1}``:
        (M + γ·dt·C + β·dt²·K) a_{n+1} = F_{n+1} − C·v_pred − K·u_pred.
    Undamped (C = 0), free (F = 0): (m + β·dt²·k) a_{n+1} = −k·u_pred.

    Returned as a ``@ti.kernel``-backed in-place callable
    ``solve_a(u_pred, v_pred, a_out)`` (out LAST — the seam convention). The
    coefficients ride as runtime kernel args (not closure-baked) so the kernel
    JITs once regardless of dt (the ti_runtime scalar-arg discipline).
    """
    import taichi as ti

    denom = m + _BETA * dt * dt * k

    @ti.kernel
    def _solve(
        u_pred: ti.template(), v_pred: ti.template(), a_out: ti.template(), kk: ti.f64, dn: ti.f64
    ):
        for i in a_out:
            a_out[i] = (-kk * u_pred[i]) / dn

    def solve_a(u_pred, v_pred, a_out):
        _solve(u_pred, v_pred, a_out, k, denom)

    return solve_a


class TestTaskP61:
    """Tests for Task P6-1: time integrators through a seam. AC covered: 1, 2."""

    @pytest.mark.slow
    @pytest.mark.e2e
    def test_generated_newmark_matches_analytic_sdof(self):
        """AC-1: the generated Newmark-β integrator (LaTeX → algo2code → injected
        step) advances an SDOF oscillator and matches the analytic response.

        SDOF, undamped, free vibration:  m·ü + k·u = 0,  u(0)=1, v(0)=0.
        Closed form:  u(t) = cos(ω t),  ω = sqrt(k/m).

        Tolerance justification (Newmark-β order of accuracy):
          Newmark-β with γ = 1/2 is **second-order** accurate; its global error
          over a fixed interval scales as O((ω·Δt)²) (period elongation, no
          amplitude error for the trapezoidal rule). We integrate one full period
          at Δt = T/80, so (ω·Δt) = 2π/80 ≈ 0.0785 and the error floor is
          ~O(6e-3). A 5e-3 bound is therefore accuracy-appropriate (NOT a
          machine-precision 1e-10 bound, which a 2nd-order scheme cannot meet at a
          finite Δt). We additionally **prove** the order is genuinely 2 by a
          step-refinement check: halving Δt must quarter the error (ratio ≈ 4).
        """
        import taichi as ti

        ti.init(arch=ti.cpu, default_fp=ti.f64)

        from ti_runtime.seams import TimeIntegrationContext

        m, k = 2.0, 50.0
        omega = math.sqrt(k / m)
        period = 2.0 * math.pi / omega

        def _integrate(steps_per_period: int) -> float:
            """Run one period at the given resolution; return the max |error|."""
            dt = period / steps_per_period
            n_steps = steps_per_period  # exactly one period

            u = ti.Vector.field(1, ti.f64, shape=1)
            v = ti.Vector.field(1, ti.f64, shape=1)
            a = ti.Vector.field(1, ti.f64, shape=1)
            u.from_numpy(np.array([[1.0]]))  # u(0) = 1
            v.from_numpy(np.array([[0.0]]))  # v(0) = 0
            a.from_numpy(np.array([[-k * 1.0 / m]]))  # a(0) = M⁻¹(F − K u₀) = −k/m

            # ── Time-integration seam: inject the acceleration solve + the
            #    GENERATED Newmark step, then advance via ctx.step(...) ──────────
            ctx = TimeIntegrationContext(dt=dt, beta=_BETA, gamma=_GAMMA)
            ctx.set_accel_solve(_make_undamped_sdof_solve_a(k, m, dt))
            bind_generated_newmark_integrator(ctx)

            max_err = 0.0
            for s in range(n_steps):
                ctx.step(u, v, a)
                t = (s + 1) * dt
                # .to_numpy() is a step-boundary archival read only — NOT in the
                # generated step's hot path (which is all on-device _v.* calls).
                max_err = max(max_err, abs(float(u.to_numpy()[0, 0]) - math.cos(omega * t)))
            return max_err

        err_coarse = _integrate(40)
        err_fine = _integrate(80)

        # Accuracy: one period at Δt = T/80 tracks cos(ω t) to well within 5e-3.
        assert err_fine < 5.0e-3, (
            f"generated Newmark-β SDOF error {err_fine:.3e} exceeds the "
            f"2nd-order bound 5e-3 at Δt = T/80"
        )
        # Order: halving Δt must quarter the error (2nd order ⇒ ratio ≈ 4),
        # proving the scheme is genuinely 2nd order and not coincidentally close.
        ratio = err_coarse / err_fine
        assert 3.0 < ratio < 5.0, (
            f"step-refinement ratio {ratio:.2f} is not ≈4: the generated "
            f"Newmark-β step is not 2nd-order accurate (err40={err_coarse:.3e}, "
            f"err80={err_fine:.3e})"
        )

    @pytest.mark.slow
    def test_integrator_injects_via_time_integration_seam(self):
        """AC-2: the transpiled integrator advances via the new ti_runtime
        time-integration seam (set_integrator / set_accel_solve / step),
        analogous to the linear-solve seam — AND the step hot path has no NumPy.

        Two halves:
          (a) Behaviour: the seam-injected generated step actually advances the
              state (and matches a hand-rolled Newmark reference step), proving
              the body is driven *through* the seam, not bypassed.
          (b) No NumPy in the step hot path: source + AST check on the generated
              ``newmark_step`` body (mirrors test_p4_2 AC-3). ``.to_numpy()`` only
              at step-boundary archival, never inside the generated step.
        """
        import taichi as ti

        ti.init(arch=ti.cpu, default_fp=ti.f64)

        from ti_runtime.seams import TimeIntegrationContext

        # ── (a) Behaviour through the seam ───────────────────────────────────
        m, k = 1.0, 100.0
        dt = 1.0e-2
        denom = m + _BETA * dt * dt * k

        u = ti.Vector.field(1, ti.f64, shape=1)
        v = ti.Vector.field(1, ti.f64, shape=1)
        a = ti.Vector.field(1, ti.f64, shape=1)
        u.from_numpy(np.array([[1.0]]))
        v.from_numpy(np.array([[0.0]]))
        a.from_numpy(np.array([[-k / m]]))

        ctx = TimeIntegrationContext(dt=dt, beta=_BETA, gamma=_GAMMA)
        ctx.set_accel_solve(_make_undamped_sdof_solve_a(k, m, dt))
        bind_generated_newmark_integrator(ctx)

        # Seam must refuse to step before an integrator is injected.
        bare = TimeIntegrationContext(dt=dt, beta=_BETA, gamma=_GAMMA)
        bare.set_accel_solve(_make_undamped_sdof_solve_a(k, m, dt))
        with pytest.raises(RuntimeError, match="no body injected"):
            bare.step(u, v, a)

        # Hand-rolled single Newmark step (the reference the seam must reproduce).
        u0, v0, a0 = 1.0, 0.0, -k / m
        u_pred = u0 + dt * v0 + dt * dt * (0.5 - _BETA) * a0
        v_pred = v0 + dt * (1.0 - _GAMMA) * a0
        a1 = (-k * u_pred) / denom
        u1 = u_pred + _BETA * dt * dt * a1
        v1 = v_pred + _GAMMA * dt * a1

        ctx.step(u, v, a)  # advance one step through the seam

        np.testing.assert_allclose(u.to_numpy()[0, 0], u1, rtol=0, atol=1e-12)
        np.testing.assert_allclose(v.to_numpy()[0, 0], v1, rtol=0, atol=1e-12)
        np.testing.assert_allclose(a.to_numpy()[0, 0], a1, rtol=0, atol=1e-12)
        # The state genuinely moved (the seam is not a no-op).
        assert abs(float(u.to_numpy()[0, 0]) - u0) > 1e-9

        # ── (b) No NumPy in the generated step hot path ──────────────────────
        code = transpile_seam_newmark()

        # Source level.
        assert "import numpy" not in code, f"generated Newmark must not import numpy:\n{code}"
        assert ".to_numpy(" not in code, f"generated Newmark must not call .to_numpy():\n{code}"
        assert "np." not in code, f"generated Newmark must not reference np.:\n{code}"
        # Matrix-free: no dense _matvec emitted or called.
        assert "def _matvec(" not in code and "_matvec(" not in code, (
            f"generated Newmark must be matrix-free (no dense _matvec):\n{code}"
        )

        # AST level: isolate the newmark_step driver, walk every node, assert no
        # `.to_numpy()` attribute access and no `np`/`numpy` name in the body.
        tree = ast.parse(code)
        step_fn = next(
            (
                node
                for node in ast.walk(tree)
                if isinstance(node, ast.FunctionDef) and node.name == "newmark_step"
            ),
            None,
        )
        assert step_fn is not None, "generated module is missing the `newmark_step` driver"
        for node in ast.walk(step_fn):
            if isinstance(node, ast.Attribute):
                assert node.attr != "to_numpy", "newmark_step must not call .to_numpy()"
            if isinstance(node, ast.Name):
                assert node.id not in ("np", "numpy"), (
                    "newmark_step must not reference numpy in the step hot path"
                )

        # The on-device primitives the body DOES use are the ti_runtime ones, and
        # the only non-primitive call is the injected acceleration solve.
        assert "from ti_runtime import vector_ops as _v" in code
        assert "_v.vec_add(" in code, "expected the fused AXPBY primitive in the generated body"
        assert "_v.copy(" in code, "expected the ti_runtime copy primitive in the generated body"
        assert "solve_a(" in code, "expected the injected acceleration-solve seam call"

        # build_seam_newmark returns the same cached generated callable used above.
        assert build_seam_newmark().__name__ == "newmark_step"
