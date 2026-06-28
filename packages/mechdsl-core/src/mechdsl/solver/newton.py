"""Newton-Raphson driver — calls imported linear solver.

Runtime numpy-level module that orchestrates Newton iteration with:
- Callback-based assembly (residual + tangent matvec)
- Dirichlet BC enforcement (algebraic elimination)
- Optional history field commit/rollback for plasticity
- Convergence diagnostics via Python logging

Compatible with :func:`mechdsl.solver.load_stepping.adaptive_load_stepping`
via the ``(converged, n_iters, residual_history)`` return contract.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from collections.abc import Callable

    from numpy.typing import NDArray

    from mechdsl.solver.history_fields import HistoryFields
    from mechdsl.solver.import_adapter import LinearSolverInterface

logger = logging.getLogger(__name__)


@dataclass
class NewtonConfig:
    """Configuration for the Newton-Raphson solver."""

    tol: float = 1e-8
    """Relative tolerance: converged when ``||R|| < tol * ||R_0||``."""

    max_iter: int = 50
    """Maximum Newton iterations."""

    cg_tol: float = 1e-10
    """Relative tolerance for the CG linear solver."""

    cg_max_iter: int = 2000
    """Maximum CG iterations."""


@dataclass
class NewtonResult:
    """Result of a Newton-Raphson solve."""

    converged: bool
    """Whether the solve converged within tolerance."""

    n_iterations: int
    """Number of Newton iterations performed."""

    residual_history: list[float] = field(default_factory=list)
    """Residual norm at each iteration."""


def newton_solve(
    assemble_residual: Callable[[NDArray], NDArray],
    tangent_matvec: Callable[[NDArray, NDArray], NDArray],
    u: NDArray,
    bc_mask: NDArray,
    linear_solver: LinearSolverInterface | None = None,
    config: NewtonConfig | None = None,
    history: HistoryFields | None = None,
) -> NewtonResult:
    """Run Newton-Raphson iteration.

    Parameters
    ----------
    assemble_residual
        ``u (n_nodes, 3) -> R (n_nodes, 3)``.  Caller is responsible for
        including external forces: ``R = f_ext - f_int(u)``.
    tangent_matvec
        ``(u, v) -> K(u) @ v``, both ``(n_nodes, 3)``.  Must NOT apply
        Dirichlet enforcement — the driver wraps it internally.
    u
        Initial displacement ``(n_nodes, 3)``, **modified in place**.
    bc_mask
        Boolean mask ``(n_nodes, 3)``; ``True`` = constrained DOF.
    linear_solver
        CG or PCG solver satisfying :class:`LinearSolverInterface`.
        Defaults to :class:`CGSolver`.
    config
        Solver parameters.  Uses :class:`NewtonConfig` defaults if *None*.
    history
        If provided, ``commit()`` on convergence, ``rollback()`` on failure.

    Returns
    -------
    NewtonResult
        Result whose ``(converged, n_iterations, residual_history)``
        matches the contract expected by
        :func:`~mechdsl.solver.load_stepping.adaptive_load_stepping`.

    Raises
    ------
    RuntimeError
        If the assembled residual norm is non-finite (NaN/Inf) at any
        iteration -- e.g. a generated return map that did not converge set
        ``dl = NaN`` and it propagated into ``R`` (WI-1). The pre-iteration
        ``u`` is restored and ``history.rollback()`` is called before raising,
        so the caller is left on the last good state rather than advancing on a
        corrupt one.
    Exception
        Propagates exceptions raised by ``assemble_residual``,
        ``tangent_matvec``, or the configured linear solver backend.
    """
    if config is None:
        config = NewtonConfig()
    if linear_solver is None:
        from mechdsl.solver.import_adapter import ScipyCGSolver

        linear_solver = ScipyCGSolver()

    n_nodes = u.shape[0]
    ndof = n_nodes * 3
    u_snapshot = u.copy()  # snapshot for rollback on failure
    residual_history: list[float] = []
    R0_norm: float | None = None

    for iteration in range(config.max_iter):
        # --- Step 1: Compute residual ---
        R = assemble_residual(u)

        # Dirichlet enforcement: zero constrained DOFs in residual
        R[bc_mask] = 0.0

        R_norm = float(np.linalg.norm(R))
        residual_history.append(R_norm)

        # Fail-loud on a non-finite residual. A NaN/Inf ``||R||`` means the
        # assembled residual is poisoned -- e.g. the generated J2 return map
        # set ``dl = NaN`` on non-convergence (WI-1, taichi_printer) and it
        # propagated through stress -> internal force -> R. A magnitude-only
        # convergence test cannot catch this: ``NaN < tol`` is False, so the
        # loop would silently exhaust ``max_iter`` (or, on a backend that
        # clamps the NaN, accept a return map that never converged). Restore
        # the pre-iteration state and raise instead of advancing on garbage.
        if not np.isfinite(R_norm):
            u[:] = u_snapshot
            if history is not None:
                history.rollback()
            raise RuntimeError(
                f"Newton residual is non-finite (||R|| = {R_norm}) at "
                f"iteration {iteration}: the assembled residual is poisoned "
                "(e.g. a return map that did not converge set dl = NaN). "
                "Aborting rather than advancing on a corrupt state."
            )

        logger.debug(
            "Newton iter %d: ||R|| = %.6e",
            iteration,
            R_norm,
        )

        # First iteration: store reference norm
        if iteration == 0:
            R0_norm = R_norm
            if R0_norm < 1e-15:
                # Already at equilibrium
                logger.debug("Already at equilibrium (||R_0|| < 1e-15)")
                if history is not None:
                    history.commit()
                return NewtonResult(
                    converged=True,
                    n_iterations=0,
                    residual_history=residual_history,
                )

        # --- Step 2: Convergence check ---
        assert R0_norm is not None
        if R_norm < config.tol * R0_norm:
            logger.debug("Converged in %d iterations", iteration)
            if history is not None:
                history.commit()
            return NewtonResult(
                converged=True,
                n_iterations=iteration,
                residual_history=residual_history,
            )

        # --- Step 3: Solve K(u) @ du = R ---
        def _bc_matvec(v_flat: NDArray, _u_bound: NDArray = u) -> NDArray:
            v = v_flat.reshape((n_nodes, 3))
            # Zero constrained DOFs before assembly
            v_free = v.copy()
            v_free[bc_mask] = 0.0
            Kv = tangent_matvec(_u_bound, v_free)
            # Identity row for constrained DOFs (keeps CG SPD)
            Kv[bc_mask] = v[bc_mask]
            return Kv.ravel()

        R_flat = R.ravel()
        du_flat, cg_iters, cg_res = linear_solver.solve(
            _bc_matvec,
            R_flat,
            np.zeros(ndof, dtype=np.float64),
            config.cg_tol,
            config.cg_max_iter,
        )

        logger.debug(
            "  CG: %d iters, residual %.3e",
            cg_iters,
            cg_res,
        )

        du = du_flat.reshape((n_nodes, 3))
        # Dirichlet enforcement: zero increment at constrained DOFs
        du[bc_mask] = 0.0

        # --- Step 4: Update ---
        u += du

    # Did not converge
    logger.warning(
        "Newton did not converge after %d iterations. Final ||R|| = %.3e",
        config.max_iter,
        residual_history[-1] if residual_history else float("nan"),
    )
    # Restore displacement to last converged state (critical for load stepping retries)
    u[:] = u_snapshot
    if history is not None:
        history.rollback()
    return NewtonResult(
        converged=False,
        n_iterations=config.max_iter,
        residual_history=residual_history,
    )
