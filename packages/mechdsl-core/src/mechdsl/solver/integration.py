"""Solver integration layer — single mode-selector entry point.

Per recovery plan Phase 6 (R5.2)
``dev/plans/recovery_plan_latex_contract.md`` line 318:
:func:`select_linear_solver` is the integration-layer hook that callers
(tests, future Newton wiring) use to request the imported fallback or the
``algo2code``-generated PCG without reaching past the interface. The default
mode remains ``"fallback"`` until the generated path is stabilised by P6-3.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from mechdsl.solver.import_adapter import build_solver

if TYPE_CHECKING:
    from collections.abc import Callable

    import numpy as np

    from mechdsl.solver.import_adapter import LinearSolverInterface

_SolverMode = Literal["fallback", "generated"]


def select_linear_solver(
    mode: _SolverMode = "fallback",
    *,
    precond_fn: Callable[[np.ndarray], np.ndarray] | None = None,
) -> LinearSolverInterface:
    """Select a linear solver by mode (``fallback`` | ``generated``).

    Thin wrapper around :func:`mechdsl.solver.import_adapter.build_solver`
    that lives at the integration boundary so external callers can stay
    decoupled from the adapter module.

    Parameters
    ----------
    mode
        ``"fallback"`` (default) — imported ``ScipyCGSolver``.
        ``"generated"`` — ``Algo2CodePCGSolver`` (opt-in).
    precond_fn
        Optional preconditioner callable forwarded to the generated solver.
        Ignored for the fallback mode.

    Returns
    -------
    LinearSolverInterface
        The constructed solver.

    Raises
    ------
    ValueError
        If ``mode`` is not one of the recognised modes.
    """
    return build_solver(mode, precond_fn=precond_fn)


__all__ = ["select_linear_solver"]
