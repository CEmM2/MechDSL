"""Injection plumbing — the *seams* generated bodies plug into (PlanJune14 PJ-0).

MechDSL owns the stable wrappers; algo2code generates the bodies. The same
``LinearSolveContext`` applies *whatever* operator / preconditioner / solver was
injected, so the plumbing is algorithm-agnostic.

A matrix-free operator is an in-place callable ``apply(out, x) -> None`` computing
``out = A @ x`` over Taichi fields (typically a generated ``@ti.kernel``).
Preconditioner protocol mirrors NumerixWeave ``tisolvers``: ``apply(z, r)`` sets
``z = M^{-1} r``.
"""

import math
from collections.abc import Callable

import taichi as ti

from . import vector_ops as vops

# out = A @ x, in place.
OperatorApply = Callable[..., None]


@ti.data_oriented
class PreconditionerBase:
    """SPD preconditioner interface: ``apply(z, r)`` sets ``z = M^{-1} r``."""

    def apply(self, z, r) -> None:
        raise NotImplementedError

    def assemble(self) -> None:
        """Rebuild internal state from the current operator/tangent.

        No-op for stateless preconditioners (Identity, point-Jacobi); stateful
        ones (block-Jacobi) override.
        """


@ti.data_oriented
class IdentityPreconditioner(PreconditionerBase):
    """``M = I`` — unpreconditioned."""

    def apply(self, z, r) -> None:
        vops.copy(z, r)


@ti.data_oriented
class DiagonalPreconditioner(PreconditionerBase):
    """Point-Jacobi: ``M = diag(d)``, ``M^{-1} = diag(1/d)``.

    ``diag`` is a Taichi field of the same layout as the vectors; division is
    guarded by ``max(d, eps)`` to avoid NaN on a zero/near-zero diagonal.
    """

    def __init__(self, diag: ti.template(), eps: float = 1e-12):
        self.diag = diag
        self.eps = eps

    @ti.kernel
    def _apply(self, z: ti.template(), r: ti.template(), eps: float):
        for I in ti.grouped(r):
            z[I] = r[I] / ti.max(self.diag[I], eps)

    def apply(self, z, r) -> None:
        self._apply(z, r, self.eps)


class Operator:
    """Holds the injected matrix-free operator ``apply(out, x): out = A @ x``."""

    def __init__(self) -> None:
        self._apply: OperatorApply | None = None

    def set_apply(self, fn: OperatorApply) -> "Operator":
        self._apply = fn
        return self

    def apply(self, out, x) -> None:
        if self._apply is None:
            raise RuntimeError("Operator has no body injected; call set_apply(...) first.")
        self._apply(out, x)


class Solver:
    """Holds an injected (generated) solver body ``solve(ctx, b, x, ...)``."""

    def __init__(self) -> None:
        self._solve: Callable[..., object] | None = None

    def set_solve(self, fn: Callable[..., object]) -> "Solver":
        self._solve = fn
        return self

    def solve(self, *args, **kwargs):
        if self._solve is None:
            raise RuntimeError("Solver has no body injected; call set_solve(...) first.")
        return self._solve(*args, **kwargs)


class LinearSolveContext:
    """The plumbing a generated linear solver targets.

    Bundles the injected matrix-free operator and preconditioner; the generated
    solver body calls :meth:`apply_A` / :meth:`apply_preconditioner` plus the
    :mod:`ti_runtime.vector_ops` primitives. Defaults to the identity
    preconditioner (unpreconditioned).
    """

    def __init__(self) -> None:
        self.operator = Operator()
        self.preconditioner: PreconditionerBase = IdentityPreconditioner()
        self.solver = Solver()

    def set_operator(self, fn: OperatorApply) -> "LinearSolveContext":
        self.operator.set_apply(fn)
        return self

    def set_preconditioner(self, precond: PreconditionerBase) -> "LinearSolveContext":
        self.preconditioner = precond
        return self

    def set_solver(self, fn: Callable[..., object]) -> "LinearSolveContext":
        self.solver.set_solve(fn)
        return self

    def apply_A(self, out, x) -> None:
        self.operator.apply(out, x)

    def apply_preconditioner(self, z, r) -> None:
        self.preconditioner.apply(z, r)


# ── Time-integration seam (PlanJune14 P6-1) ──────────────────────────────────
#
# The temporal analogue of LinearSolveContext: a generated *time integrator*
# (e.g. the Newmark-beta step transpiled from dev/algorithms/newmark.tex) plugs
# into a stable wrapper here, exactly as a generated linear solver plugs into
# set_solver. The wrapper is integrator-agnostic — it applies *whatever* step
# body was injected (Newmark-beta, central difference, HHT, ...).
#
# An integrator step is an in-place callable advancing the dynamic state one
# step. The seam-injected acceleration solve mirrors the matrix-free operator:
# accel_solve(u_pred, v_pred, a_out) sets a_out = a_{n+1} (out LAST), folding the
# mass/damping/stiffness/external-force data — the box itself stays
# mass-/material-agnostic, just as the PCG box is operator-agnostic.

# (u, v, a, accel_solve, dt, beta, gamma) -> (u, v, a); advances state in place.
IntegratorStep = Callable[..., object]

# accel_solve(u_pred, v_pred, a_out): a_out = a_{n+1}, in place (out LAST).
# Returns an optional status (WI-3): ``None`` for a solve that cannot fail
# (e.g. an elementwise SDOF/diagonal-mass solve), or a convergence flag for an
# iterative solve (a falsy flag == not converged). TimeIntegrationContext.step
# consumes it to roll back and fail loud rather than advancing on a bad solve.
AccelSolveApply = Callable[..., object]


class Integrator:
    """Holds an injected (generated) time-integrator step body.

    The body advances ``(u, v, a)`` one step in place, calling the injected
    acceleration solve plus the :mod:`ti_runtime.vector_ops` primitives — the
    shape ``dev/algorithms/newmark.tex`` transpiles to.
    """

    def __init__(self) -> None:
        self._step: IntegratorStep | None = None

    def set_step(self, fn: IntegratorStep) -> "Integrator":
        self._step = fn
        return self

    def step(self, *args, **kwargs):
        if self._step is None:
            raise RuntimeError("Integrator has no body injected; call set_integrator(...) first.")
        return self._step(*args, **kwargs)


class AccelSolve:
    """Holds the injected acceleration solve ``apply(u_pred, v_pred, a_out)``.

    Sets ``a_out = a_{n+1}`` — the solution of
    ``(M + gamma*dt*C + beta*dt^2*K) a_{n+1} = F_{n+1} - C*v_pred - K*u_pred``.
    For an SDOF / diagonal-mass problem this is an elementwise solve; for a full
    FEM system it is itself a (linear) solve. Matrix-free: the wrapper applies
    whatever callable was injected.
    """

    def __init__(self) -> None:
        self._apply: AccelSolveApply | None = None

    def set_apply(self, fn: AccelSolveApply) -> "AccelSolve":
        self._apply = fn
        return self

    def apply(self, u_pred, v_pred, a_out) -> object:
        if self._apply is None:
            raise RuntimeError("AccelSolve has no body injected; call set_accel_solve(...) first.")
        # Forward the injected solve's return value (WI-3): a convergence status
        # when the solve is iterative, else ``None``. The caller (step) decides.
        return self._apply(u_pred, v_pred, a_out)


class TimeIntegrationContext:
    """The plumbing a generated time integrator targets (PlanJune14 P6-1).

    The temporal twin of :class:`LinearSolveContext`. Bundles the injected
    acceleration solve and the injected integrator step; the generated step body
    calls :meth:`apply_accel_solve` (the matrix-free seam) plus the
    :mod:`ti_runtime.vector_ops` primitives. :meth:`step` advances the dynamic
    state ``(u, v, a)`` one step in place by applying the injected integrator,
    with no NumPy in the hot path.

    Parameters ``dt`` / ``beta`` / ``gamma`` are the Newmark step controls; they
    default to the average-acceleration scheme (``beta = 1/4``, ``gamma = 1/2``)
    — unconditionally stable, second-order, no algorithmic damping.
    """

    def __init__(self, dt: float = 1.0, beta: float = 0.25, gamma: float = 0.5) -> None:
        self.integrator = Integrator()
        self.accel = AccelSolve()
        self.dt = dt
        self.beta = beta
        self.gamma = gamma

    def set_integrator(self, fn: IntegratorStep) -> "TimeIntegrationContext":
        self.integrator.set_step(fn)
        return self

    def set_accel_solve(self, fn: AccelSolveApply) -> "TimeIntegrationContext":
        self.accel.set_apply(fn)
        return self

    def apply_accel_solve(self, u_pred, v_pred, a_out) -> object:
        return self.accel.apply(u_pred, v_pred, a_out)

    def step(self, u, v, a):
        """Advance the state ``(u, v, a)`` one step via the injected integrator.

        Wires the seam conventions to the generated body's callable arguments:
        the integrator's ``solve_a(u_pred, v_pred, a_out)`` argument is bound to
        :meth:`apply_accel_solve` (the injected acceleration solve), and the
        ``(dt, beta, gamma)`` controls come from this context. Returns whatever
        the generated step returns (typically ``(u, v, a)``).

        Fail-loud contract (WI-3). The step is committed only if the injected
        acceleration solve succeeded and the advanced state is finite. Before
        stepping we snapshot ``(u, v, a)``; if the injected solve **raises**
        (e.g. the WI-2 seam PCG on non-convergence), **reports** a falsy
        convergence status, or the advanced acceleration is **non-finite**, we
        restore the snapshot and raise ``RuntimeError`` rather than leaving the
        dynamic state half-advanced on a bad solve. This mirrors the host
        Newton driver's snapshot/rollback + isfinite guard (newton.py). P6-1 is
        not yet production-wired, so this establishes the contract without
        redesigning the matrix-free body; the per-step snapshot is a
        step-boundary archival copy (the same ``.to_numpy()`` round-trip the
        P6-1 tests use at step boundaries), not a hot-path operation.
        """
        # Step-boundary snapshot for rollback (not the generated hot path).
        u_snap = u.to_numpy()
        v_snap = v.to_numpy()
        a_snap = a.to_numpy()

        def _restore() -> None:
            u.from_numpy(u_snap)
            v.from_numpy(v_snap)
            a.from_numpy(a_snap)

        status: dict[str, object] = {}

        def accel_solve(u_pred, v_pred, a_out):
            status["accel"] = self.apply_accel_solve(u_pred, v_pred, a_out)

        try:
            result = self.integrator.step(u, v, a, accel_solve, self.dt, self.beta, self.gamma)
        except Exception:
            # A raising solve (e.g. the WI-2 seam PCG) may have left state
            # half-advanced -- restore before propagating.
            _restore()
            raise

        # A reported non-convergence status (a falsy flag that is not ``None``;
        # ``None`` means "no status / cannot fail", e.g. an elementwise solve).
        accel_status = status.get("accel")
        if accel_status is not None and not accel_status:
            _restore()
            raise RuntimeError(
                "Time-integration acceleration solve did not converge "
                f"(status={accel_status!r}); restored the pre-step state rather "
                "than advancing (u, v, a) on a non-converged acceleration."
            )

        # Non-finite advanced acceleration poisons all subsequent steps; catch
        # it here (mirrors the Newton driver's isfinite residual guard).
        if not math.isfinite(vops.norm2(a)):
            _restore()
            raise RuntimeError(
                "Time-integration step produced a non-finite acceleration "
                "(||a|| is NaN/Inf); restored the pre-step state rather than "
                "advancing on a corrupt acceleration."
            )

        return result
