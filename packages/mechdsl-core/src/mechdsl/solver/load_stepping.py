"""Adaptive load stepping runtime for nonlinear FEM solvers.

Drives a Newton solver through incremental load factors from 0 to
``target_load``.  Step size adapts automatically: it grows when Newton
converges quickly and shrinks (cutback) when convergence fails.

Task P7.4 — adaptive load stepping.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable


@dataclass
class LoadStepResult:
    """Result of a single converged load step."""

    converged: bool
    load_factor: float  # Current cumulative load factor [0, 1]
    n_iterations: int
    residual_history: list[float]


@dataclass
class LoadSteppingResult:
    """Result of the complete load stepping procedure."""

    converged: bool
    final_load_factor: float
    steps: list[LoadStepResult]
    n_total_steps: int
    n_cutbacks: int


@dataclass
class LoadSteppingConfig:
    """Configuration for adaptive load stepping.

    Attributes:
        initial_step_size: Initial load factor increment.
        min_step_size: Minimum step size before declaring failure.
        max_step_size: Maximum step size (upper clamp).
        growth_factor: Multiplier applied when Newton converges fast.
        cutback_factor: Multiplier applied when Newton fails to converge.
        fast_convergence_iters: Threshold — if Newton converges in at most
            this many iterations the step size is grown.
        target_load: Total load factor to reach (normally 1.0).
    """

    initial_step_size: float = 0.1
    min_step_size: float = 1e-6
    max_step_size: float = 0.5
    growth_factor: float = 1.5
    cutback_factor: float = 0.5
    fast_convergence_iters: int = 4
    target_load: float = 1.0


def adaptive_load_stepping(
    newton_solve_fn: Callable[[float], tuple[bool, int, list[float]]],
    config: LoadSteppingConfig | None = None,
) -> LoadSteppingResult:
    """Run adaptive load stepping.

    Args:
        newton_solve_fn: Callable that takes a load_factor (float in [0, 1])
            and returns ``(converged, n_iters, residual_history)``.
            The function is responsible for its own state management
            (history commit on success, rollback on failure).
        config: Load stepping configuration.  Uses defaults if *None*.

    Returns:
        :class:`LoadSteppingResult` with full history.

    Algorithm
    ---------
    1. Start with ``dt = initial_step_size``, ``load_factor = 0``.
    2. Try ``load_factor += dt``.
    3. Call ``newton_solve_fn(load_factor)``.
    4. If converged:
       a. Record step.
       b. If ``n_iters <= fast_convergence_iters``: ``dt *= growth_factor``.
       c. Clamp ``dt`` to ``max_step_size``.
    5. If not converged:
       a. ``dt *= cutback_factor``.
       b. If ``dt < min_step_size``: fail.
       c. Retry from last converged ``load_factor``.
    6. Repeat until ``load_factor >= target_load``.
    """
    if config is None:
        config = LoadSteppingConfig()

    dt = config.initial_step_size
    load_factor = 0.0
    steps: list[LoadStepResult] = []
    n_cutbacks = 0

    while load_factor < config.target_load:
        # Clamp so we don't overshoot the target
        trial_dt = min(dt, config.target_load - load_factor)
        trial_load = load_factor + trial_dt

        converged, n_iters, residual_history = newton_solve_fn(trial_load)

        if converged:
            load_factor = trial_load
            steps.append(
                LoadStepResult(
                    converged=True,
                    load_factor=load_factor,
                    n_iterations=n_iters,
                    residual_history=list(residual_history),
                )
            )
            # Adapt step size
            if n_iters <= config.fast_convergence_iters:
                dt *= config.growth_factor
            dt = min(dt, config.max_step_size)
        else:
            # Cutback
            n_cutbacks += 1
            dt *= config.cutback_factor
            if dt < config.min_step_size:
                return LoadSteppingResult(
                    converged=False,
                    final_load_factor=load_factor,
                    steps=steps,
                    n_total_steps=len(steps),
                    n_cutbacks=n_cutbacks,
                )

    return LoadSteppingResult(
        converged=True,
        final_load_factor=load_factor,
        steps=steps,
        n_total_steps=len(steps),
        n_cutbacks=n_cutbacks,
    )
