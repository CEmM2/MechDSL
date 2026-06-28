"""Linear solver interface contract and concrete CG / PCG implementations.

This module defines the ``LinearSolverInterface`` protocol that any linear
solver adapter must satisfy, plus two ready-made implementations:

* ``CGSolver``  — standard Conjugate Gradient (matrix-free, numpy).
* ``PCGSolver`` — Preconditioned Conjugate Gradient with an optional
  preconditioner callback.

Both solvers operate on dense numpy arrays with ``float64`` precision and
accept the system matrix as a *matvec* callable (``A @ x`` without forming
``A`` explicitly).  This is the contract consumed by the Newton driver.
"""

from __future__ import annotations

import warnings
from typing import TYPE_CHECKING, Protocol

import numpy as np

if TYPE_CHECKING:
    from collections.abc import Callable

    from ti_runtime.seams import LinearSolveContext, PreconditionerBase


class LinearSolverInterface(Protocol):
    """Protocol every linear solver adapter must implement."""

    def solve(
        self,
        matvec_fn: Callable[[np.ndarray], np.ndarray],
        rhs: np.ndarray,
        x0: np.ndarray,
        tol: float,
        max_iter: int,
    ) -> tuple[np.ndarray, int, float]:
        """Solve *A x = b* where *A* is given as a matvec function.

        Parameters
        ----------
        matvec_fn : Callable[[np.ndarray], np.ndarray]
            Function computing ``A @ v`` for an arbitrary vector ``v``.
        rhs : np.ndarray
            Right-hand side vector *b*.
        x0 : np.ndarray
            Initial guess.
        tol : float
            Relative tolerance — convergence when ``||r|| < tol * ||r_0||``.
        max_iter : int
            Maximum number of iterations.

        Returns
        -------
        tuple[np.ndarray, int, float]
            ``(solution, iteration_count, final_residual_norm)``
        """
        ...


class CGSolver:
    """Conjugate Gradient solver (matrix-free, dense numpy).

    Solves symmetric positive-definite (SPD) systems ``A x = b`` using the
    standard CG algorithm.  The system matrix is never formed explicitly;
    instead the caller provides a ``matvec_fn`` callback.
    """

    def solve(
        self,
        matvec_fn: Callable[[np.ndarray], np.ndarray],
        rhs: np.ndarray,
        x0: np.ndarray,
        tol: float,
        max_iter: int,
    ) -> tuple[np.ndarray, int, float]:
        """Run the CG iteration.

        See ``LinearSolverInterface.solve`` for the full contract.
        """
        x = x0.astype(np.float64, copy=True)
        r = rhs.astype(np.float64) - matvec_fn(x)
        p = r.copy()

        r_norm_sq = float(np.dot(r, r))
        r0_norm = np.sqrt(r_norm_sq)

        # Handle trivial RHS (already solved).
        if r0_norm == 0.0:
            return x, 0, 0.0

        abs_tol = tol * r0_norm

        for k in range(1, max_iter + 1):
            ap = matvec_fn(p)
            p_dot_ap = float(np.dot(p, ap))

            # Guard against breakdown (non-SPD or near-singular).
            if abs(p_dot_ap) < 1e-300:
                warnings.warn(
                    f"CG breakdown at iteration {k}: p^T A p = {p_dot_ap:.3e}. "
                    "System may be non-SPD or singular.",
                    RuntimeWarning,
                    stacklevel=2,
                )
                break

            alpha = r_norm_sq / p_dot_ap
            x += alpha * p
            r -= alpha * ap

            r_norm_sq_new = float(np.dot(r, r))
            r_norm = np.sqrt(r_norm_sq_new)

            if r_norm < abs_tol:
                return x, k, r_norm

            beta = r_norm_sq_new / r_norm_sq
            p = r + beta * p
            r_norm_sq = r_norm_sq_new

        return x, max_iter, np.sqrt(float(np.dot(r, r)))


class PCGSolver:
    """Preconditioned Conjugate Gradient solver (matrix-free, dense numpy).

    Parameters
    ----------
    precond_fn : Callable[[np.ndarray], np.ndarray] | None
        Function computing ``M^{-1} v`` for an arbitrary vector ``v``.
        If ``None``, falls back to unpreconditioned CG.
    """

    def __init__(
        self,
        precond_fn: Callable[[np.ndarray], np.ndarray] | None = None,
    ) -> None:
        self._precond_fn = precond_fn

    def solve(
        self,
        matvec_fn: Callable[[np.ndarray], np.ndarray],
        rhs: np.ndarray,
        x0: np.ndarray,
        tol: float,
        max_iter: int,
    ) -> tuple[np.ndarray, int, float]:
        """Run the PCG iteration.

        See ``LinearSolverInterface.solve`` for the full contract.
        """
        precond = self._precond_fn if self._precond_fn is not None else _identity

        x = x0.astype(np.float64, copy=True)
        r = rhs.astype(np.float64) - matvec_fn(x)

        r0_norm = float(np.linalg.norm(r))
        if r0_norm == 0.0:
            return x, 0, 0.0

        abs_tol = tol * r0_norm

        z = precond(r)
        p = z.copy()
        rz = float(np.dot(r, z))

        for k in range(1, max_iter + 1):
            ap = matvec_fn(p)
            p_dot_ap = float(np.dot(p, ap))

            if abs(p_dot_ap) < 1e-300:
                warnings.warn(
                    f"PCG breakdown at iteration {k}: p^T A p = {p_dot_ap:.3e}. "
                    "System may be non-SPD or singular.",
                    RuntimeWarning,
                    stacklevel=2,
                )
                break

            alpha = rz / p_dot_ap
            x += alpha * p
            r -= alpha * ap

            r_norm = float(np.linalg.norm(r))
            if r_norm < abs_tol:
                return x, k, r_norm

            z = precond(r)
            rz_new = float(np.dot(r, z))
            beta = rz_new / rz
            p = z + beta * p
            rz = rz_new

        return x, max_iter, float(np.linalg.norm(r))


class ScipyCGSolver:
    """Conjugate Gradient solver using scipy.sparse.linalg.cg.

    Wraps scipy's compiled CG implementation behind the
    ``LinearSolverInterface`` protocol.  Significantly faster than the
    pure-numpy ``CGSolver`` for systems beyond ~50 DOFs.
    """

    def solve(
        self,
        matvec_fn: Callable[[np.ndarray], np.ndarray],
        rhs: np.ndarray,
        x0: np.ndarray,
        tol: float,
        max_iter: int,
    ) -> tuple[np.ndarray, int, float]:
        """Run scipy CG.

        See ``LinearSolverInterface.solve`` for the full contract.
        """
        from scipy.sparse.linalg import LinearOperator, cg

        n = rhs.shape[0]
        A_op = LinearOperator((n, n), matvec=matvec_fn, dtype=np.float64)

        # Track iteration count via callback
        iter_count = 0

        def _count(_xk: np.ndarray) -> None:
            nonlocal iter_count
            iter_count += 1

        x, info = cg(A_op, rhs, x0=x0, rtol=tol, maxiter=max_iter, callback=_count)

        if info > 0:
            warnings.warn(
                f"scipy CG did not converge after {max_iter} iterations (info={info}).",
                RuntimeWarning,
                stacklevel=2,
            )

        residual_norm = float(np.linalg.norm(rhs - matvec_fn(x)))
        return x, iter_count, residual_norm


def _identity(v: np.ndarray) -> np.ndarray:
    """Trivial preconditioner (identity)."""
    return v.copy()


class Algo2CodePCGSolver:
    """PCG solver whose body comes from the ``algo2code`` canonical PCG algorithm.

    The algorithm text lives in the sibling ``algo2code`` package
    (:func:`algo2code.library.pcg.get_pcg_algorithm_latex`) and is the
    verbatim source mirrored from
    ``dev/tasks/recovery_plan_latex_contract/json/P6-1.json``
    (``pcg_algorithm_latex.latex``).  The Python body of :meth:`solve`
    below is a line-by-line translation of that LaTeX.

    Why a hand-translated body and not ``algo2code.transpile`` output?
    -----------------------------------------------------------------

    The current ``algo2code`` parser cannot consume the canonical LaTeX as
    written: the scratch identifier ``pq`` (used as the LHS of
    ``\\State $pq = p^\\top q$``) tokenises as two single-letter tokens,
    so the expression parser interprets it as ``p * q`` and rejects it as
    an assignment target.  Adding multi-letter identifier support is
    tracked as follow-up work for ``algo2code``.  Per the P6-1 directive
    "do NOT modify the algorithm text", we (a) keep the canonical LaTeX
    untouched in :mod:`algo2code.library.pcg` and (b) ship a verbatim
    Python translation here.  The two are kept in sync by Phase-6 tests.

    Parameters
    ----------
    precond_fn : Callable[[np.ndarray], np.ndarray] | None
        Optional ``M^{-1} v`` callable.  When ``None``, the adapter binds
        ``apply_M_inv = lambda v: v.copy()`` at construction time, exactly
        as the P6-1 specification demands ("do not encode None-handling
        in the LaTeX").
    """

    def __init__(
        self,
        precond_fn: Callable[[np.ndarray], np.ndarray] | None = None,
    ) -> None:
        # Bind the identity preconditioner at construction time so the
        # algorithm body never sees `None`. Matches the contract in the
        # P6-1 task JSON (`preconditioner_contract` field).
        self._apply_M_inv: Callable[[np.ndarray], np.ndarray] = (
            precond_fn if precond_fn is not None else _identity
        )
        # Sanity check: the canonical LaTeX must be reachable through the
        # algo2code interface hook. This makes the runtime dependency
        # *direction* explicit (mechdsl-core -> algo2code, never the
        # reverse).  We import lazily so the rest of mechdsl does not pay
        # the import cost when this adapter is unused.
        from algo2code.library.pcg import (
            get_pcg_algorithm_latex,
        )

        self._algorithm_source: str = get_pcg_algorithm_latex()

    @property
    def algorithm_source(self) -> str:
        """The canonical PCG LaTeX consumed at construction time.

        Exposed for introspection / regression tests; not used by
        :meth:`solve`.
        """
        return self._algorithm_source

    def solve(
        self,
        matvec_fn: Callable[[np.ndarray], np.ndarray],
        rhs: np.ndarray,
        x0: np.ndarray,
        tol: float,
        max_iter: int,
    ) -> tuple[np.ndarray, int, float]:
        """Run the algo2code-canonical PCG iteration.

        See :class:`LinearSolverInterface.solve` for the full contract.

        Body is a verbatim translation of
        :data:`algo2code.library.pcg.PCG_ALGORITHM_LATEX`.  Each
        ``\\State`` line in the LaTeX maps to exactly one Python line
        below; see the inline ``# LaTeX:`` comments.
        """
        apply_M_inv = self._apply_M_inv
        A = matvec_fn  # The "A" of the LaTeX is realised as a matvec callable.

        # LaTeX: \State $r = b - A \cdot x$
        x = x0.astype(np.float64, copy=True)
        r = rhs.astype(np.float64) - A(x)

        # LaTeX: \State $r_0 = \lVert r \rVert_2$
        r0_norm = float(np.linalg.norm(r))

        # LaTeX: \If{$r_0 = 0$} \Return $x, 0, 0$ \EndIf
        if r0_norm == 0.0:
            return x, 0, 0.0

        # LaTeX: \State $z = \text{apply\_M\_inv}(r)$
        z = apply_M_inv(r)
        # LaTeX: \State $p = z$
        p = z.copy()
        # LaTeX: \State $\rho = r^\top z$
        rho = float(np.dot(r, z))

        # LaTeX: \For{$k = 1, 2, \ldots, \text{maxiter}$}
        for k in range(1, max_iter + 1):
            # LaTeX: \State $q = A \cdot p$
            q = A(p)
            # LaTeX: \State $pq = p^\top q$
            pq = float(np.dot(p, q))

            # LaTeX: \If{$|pq| < 10^{-300}$} \State \textbf{break} \EndIf
            if abs(pq) < 1e-300:
                warnings.warn(
                    f"Algo2CodePCG breakdown at iteration {k}: "
                    f"p^T A p = {pq:.3e}. System may be non-SPD or singular.",
                    RuntimeWarning,
                    stacklevel=2,
                )
                break

            # LaTeX: \State $\alpha = \frac{\rho}{pq}$
            alpha = rho / pq
            # LaTeX: \State $x = x + \alpha \, p$
            x = x + alpha * p
            # LaTeX: \State $r = r - \alpha \, q$
            r = r - alpha * q

            # LaTeX: \State $r_n = \lVert r \rVert_2$
            r_norm = float(np.linalg.norm(r))

            # LaTeX: \If{$r_n < \text{tol} \cdot r_0$} \Return $x, k, r_n$ \EndIf
            if r_norm < tol * r0_norm:
                return x, k, r_norm

            # LaTeX: \State $z = \text{apply\_M\_inv}(r)$
            z = apply_M_inv(r)
            # LaTeX: \State $\rho_{\text{new}} = r^\top z$
            rho_new = float(np.dot(r, z))
            # LaTeX: \State $\beta = \frac{\rho_{\text{new}}}{\rho}$
            beta = rho_new / rho
            # LaTeX: \State $p = z + \beta \, p$
            p = z + beta * p
            # LaTeX: \State $\rho = \rho_{\text{new}}$
            rho = rho_new

        # LaTeX: \Return $x, \text{maxiter}, \lVert r \rVert_2$
        # (Reached when the for-loop exhausts maxiter or breaks on breakdown.)
        return x, max_iter, float(np.linalg.norm(r))


# ---------------------------------------------------------------------------
# P6-2 — Solver-mode factories.
#
# Purely additive surface introduced by Task P6-2 of the recovery plan.
# Everything above this banner (including ``LinearSolverInterface``,
# ``CGSolver``, ``PCGSolver``, ``ScipyCGSolver``, ``_identity``, and
# ``Algo2CodePCGSolver``) MUST remain byte-identical to its P6-1 form; this
# block only appends new module-level callables and a private alias.
# ---------------------------------------------------------------------------

# ``Literal`` is imported here at the bottom of the module — after the
# byte-identity-protected block (lines 1-391, P6-1 Gate-A invariant) — so that
# ``LinearSolverInterface``, ``CGSolver``, ``PCGSolver``, ``ScipyCGSolver``,
# ``_identity``, and ``Algo2CodePCGSolver`` remain byte-identical to their
# P6-1 form (verified via SHA-256 of ``ast.dump``). Once that protection
# is lifted, this import can move into the ``TYPE_CHECKING`` block at the
# top of the module (``from __future__ import annotations`` on line 15
# already makes the annotation lazy at runtime).
from typing import Literal as _Literal  # noqa: E402  (intentional bottom-of-module import)

_SolverMode = _Literal["fallback", "generated"]


def get_default_solver() -> LinearSolverInterface:
    """Return the default fallback solver — the imported ``ScipyCGSolver``.

    Per recovery plan Phase 6 (R5.2)
    ``dev/plans/recovery_plan_latex_contract.md`` line 318: the imported
    solver remains the default fallback until the ``algo2code``-generated
    PCG path (P6-1) is proven stable through P6-3's integration test and
    broader regression. Do not flip this default until that work lands.

    PlanJune14 P4-3 status
    ----------------------
    The all-Taichi on-device **seam** solve path (generated matrix-free PCG
    via ``ti_runtime`` ``set_solver`` + the P3-2 generated tangent operator
    via ``set_operator``, optionally the P4-1 generated Jacobi via
    ``set_preconditioner``) is now *validated to <1e-10 against this fallback*
    on the reference SVK patch (see ``tests/plan_tests/test_p4_3.py``) and is
    **selectable** through :func:`make_seam_solver` (and the
    ``mechdsl.solver.seam_solve`` entry points). It is intentionally a
    *different interface* — it drives a ``ti_runtime.LinearSolveContext`` over
    on-device ``ti.Vector.field`` DOF vectors, not the host-NumPy
    ``LinearSolverInterface`` matvec callback consumed by ``newton.py`` — so it
    is exposed as a distinct opt-in path rather than a ``build_solver`` mode.

    Per the Option-1 architecture decision, this function's global default is
    **intentionally NOT flipped**: ``ScipyCGSolver`` stays the fallback default
    and the guarded global flip to the generated seam path is deferred until
    broader regression coverage (Phase 5 J2 + Phase 7 governance) lands.
    """
    return ScipyCGSolver()


def build_solver(
    mode: _SolverMode = "fallback",
    *,
    precond_fn: Callable[[np.ndarray], np.ndarray] | None = None,
) -> LinearSolverInterface:
    """Construct a linear solver by mode.

    Parameters
    ----------
    mode
        ``"fallback"`` (default) — imported ``ScipyCGSolver`` (the stable
        path).  ``"generated"`` — ``Algo2CodePCGSolver``, opt-in until P6-3
        validates it.
    precond_fn
        Optional preconditioner callable forwarded to ``Algo2CodePCGSolver``
        when ``mode == "generated"``. Ignored for the fallback mode
        (``ScipyCGSolver`` does not currently expose a preconditioner hook).

    Returns
    -------
    LinearSolverInterface
        The constructed solver.

    Raises
    ------
    ValueError
        If ``mode`` is not one of the recognised modes.
    """
    if mode == "fallback":
        return ScipyCGSolver()
    if mode == "generated":
        return Algo2CodePCGSolver(precond_fn=precond_fn)
    raise ValueError(f"Unknown solver mode {mode!r}; expected 'fallback' or 'generated'.")


# ---------------------------------------------------------------------------
# PlanJune14 P4-3 — selectable all-Taichi seam solve path (Option 1, opt-in).
#
# The seam path is NOT a ``build_solver`` mode: it does not implement the
# host-NumPy ``LinearSolverInterface`` (matvec-callback) contract consumed by
# ``newton.py``.  It drives a ``ti_runtime.LinearSolveContext`` over on-device
# ``ti.Vector.field`` DOF vectors — a deliberately distinct interface.  This
# factory is therefore a sibling of ``build_solver``, not an extra mode, so the
# two interface boundaries are never conflated.
# ---------------------------------------------------------------------------


def make_seam_solver(
    *,
    operator: Callable[..., None],
    preconditioner: PreconditionerBase | None = None,
) -> LinearSolveContext:
    """Construct the all-Taichi on-device **seam** linear solver (opt-in).

    This is the selectable entry point for the PlanJune14 Phase-4 *Option 1*
    all-Taichi seam path: a generated matrix-free PCG (transpiled from
    ``dev/algorithms/pcg.tex`` via ``algo2code`` in runtime mode and injected
    through ``ti_runtime`` ``set_solver``) solving against an injected
    matrix-free operator (e.g. the P3-2 generated SVK tangent) with an optional
    generated preconditioner (e.g. the P4-1 Jacobi).

    Unlike :func:`build_solver`, this path does **not** return a host-NumPy
    :class:`LinearSolverInterface`.  It returns a bound
    ``ti_runtime.LinearSolveContext`` whose ``ctx.solver.solve(b, x, tol,
    maxiter)`` runs the generated PCG entirely on device (no NumPy in the hot
    path) over ``ti.Vector.field`` DOF vectors.  The seam interface and the
    NumPy matvec-callback interface are intentionally kept separate — do not
    route the seam solver through ``newton.py``'s NumPy callback.

    Parameters
    ----------
    operator
        The matrix-free operator ``apply(out, x)`` (out FIRST) injected via
        ``LinearSolveContext.set_operator`` — e.g. the P3-2 generated SVK
        tangent ``apply_A``.
    preconditioner
        Optional ``ti_runtime.seams.PreconditionerBase`` injected via
        ``set_preconditioner`` (e.g. the P4-1 ``GeneratedJacobiPreconditioner``
        or an ``IdentityPreconditioner``).  When ``None`` the context keeps its
        default ``IdentityPreconditioner`` (unpreconditioned).

    The device/arch is owned by the caller's ``ti.init`` — the generated PCG
    body is device-agnostic and is transpiled+imported once per process.

    Returns
    -------
    ti_runtime.seams.LinearSolveContext
        A context with the generated PCG bound at ``set_solver`` and the given
        operator (and preconditioner) injected; ready to drive
        ``ctx.solver.solve(b, x, tol, maxiter)``.

    Failure contract
    ----------------
    ``ctx.solver.solve`` solves in place and returns ``(x, iterations,
    residual)`` on success. If the inner PCG does **not** converge (maxiter
    exhaustion or a ``|pq| < 1e-300`` breakdown) it raises ``RuntimeError``
    rather than returning a garbage increment -- so an outer Newton / time step
    cannot silently advance on a failed solve (WI-2; see
    :func:`mechdsl.solver.seam_solve.bind_generated_pcg_solver`).
    """
    # Lazy imports: the seam path pulls in Taichi / ti_runtime, which the
    # host-NumPy adapters above deliberately do not depend on.
    from mechdsl.solver.seam_solve import bind_generated_pcg_solver
    from ti_runtime.seams import LinearSolveContext

    ctx = LinearSolveContext()
    ctx.set_operator(operator)
    if preconditioner is not None:
        ctx.set_preconditioner(preconditioner)
    bind_generated_pcg_solver(ctx)
    return ctx
