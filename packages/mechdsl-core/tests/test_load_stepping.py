"""Tests for the adaptive load stepping runtime (Task P7.4)."""

from __future__ import annotations

import pytest

from mechdsl.solver.load_stepping import (
    LoadSteppingConfig,
    adaptive_load_stepping,
)

# ---------------------------------------------------------------------------
# Synthetic Newton solve callbacks
# ---------------------------------------------------------------------------


def make_always_converging(n_iters: int = 3):
    """Newton that always converges in *n_iters* iterations."""

    def solve(load_factor: float) -> tuple[bool, int, list[float]]:
        return True, n_iters, [1.0 / (10**i) for i in range(n_iters)]

    return solve


def make_failing_at(threshold: float, n_iters: int = 3):
    """Newton that fails when load_factor exceeds *threshold*."""

    def solve(load_factor: float) -> tuple[bool, int, list[float]]:
        if load_factor > threshold:
            return False, 50, [1.0] * 50
        return True, n_iters, [1.0 / (10**i) for i in range(n_iters)]

    return solve


def make_always_failing():
    """Newton that never converges."""

    def solve(load_factor: float) -> tuple[bool, int, list[float]]:
        return False, 50, [1.0] * 50

    return solve


# ---------------------------------------------------------------------------
# 1. Fast convergence: step grows
# ---------------------------------------------------------------------------


def test_fast_convergence_grows_step():
    """When Newton converges in few iters, step size should increase."""
    cfg = LoadSteppingConfig(
        initial_step_size=0.1,
        max_step_size=0.5,
        growth_factor=2.0,
        fast_convergence_iters=4,
    )
    # Track the load factors at which the solver is called
    call_log: list[float] = []

    def solve(load_factor: float) -> tuple[bool, int, list[float]]:
        call_log.append(load_factor)
        return True, 2, [1.0, 0.1]  # 2 iters < 4 threshold → fast

    result = adaptive_load_stepping(solve, cfg)
    assert result.converged

    # After first step (dt=0.1), dt should grow to 0.2, then 0.4, then 0.5 (max)
    # The load increments should be increasing (up to max)
    increments = [
        result.steps[i].load_factor - (result.steps[i - 1].load_factor if i > 0 else 0.0)
        for i in range(len(result.steps))
    ]
    # First increment is 0.1, second should be 0.2, third 0.4, then capped at 0.5
    assert increments[0] == pytest.approx(0.1)
    assert increments[1] == pytest.approx(0.2)
    assert increments[2] == pytest.approx(0.4)
    # After 0.4, dt becomes 0.8 but capped to 0.5
    # Remaining load = 1.0 - 0.7 = 0.3, so trial_dt = min(0.5, 0.3) = 0.3
    assert increments[3] == pytest.approx(0.3)


# ---------------------------------------------------------------------------
# 2. Slow convergence: step maintained
# ---------------------------------------------------------------------------


def test_slow_convergence_maintains_step():
    """When Newton converges slowly, step size should NOT grow."""
    cfg = LoadSteppingConfig(
        initial_step_size=0.2,
        max_step_size=0.5,
        growth_factor=2.0,
        fast_convergence_iters=4,
    )

    def solve(load_factor: float) -> tuple[bool, int, list[float]]:
        # 10 iters > 4 threshold → slow convergence
        return True, 10, [1.0 / (10**i) for i in range(10)]

    result = adaptive_load_stepping(solve, cfg)
    assert result.converged

    # Step size should stay at 0.2 throughout (no growth for slow convergence)
    increments = [
        result.steps[i].load_factor - (result.steps[i - 1].load_factor if i > 0 else 0.0)
        for i in range(len(result.steps))
    ]
    for inc in increments[:-1]:  # Last step may be smaller (clamped to target)
        assert inc == pytest.approx(0.2)


# ---------------------------------------------------------------------------
# 3. Non-convergence: step cut back
# ---------------------------------------------------------------------------


def test_non_convergence_cuts_back():
    """Step size should decrease on non-convergence and retry."""
    cfg = LoadSteppingConfig(
        initial_step_size=0.5,
        min_step_size=1e-6,
        cutback_factor=0.5,
        fast_convergence_iters=4,
        max_step_size=0.5,
    )
    # Track attempts to verify cutback behaviour
    attempts: list[float] = []

    def solve(load_factor: float) -> tuple[bool, int, list[float]]:
        attempts.append(load_factor)
        # Fail on increments > 0.3 from zero (first attempt at 0.5 fails)
        # but succeed once the step is small enough
        if len(attempts) == 1:
            # First attempt: dt=0.5, load_factor=0.5 → fail
            return False, 50, [1.0] * 50
        return True, 3, [1.0, 0.1, 0.01]

    result = adaptive_load_stepping(solve, cfg)

    assert result.converged
    assert result.n_cutbacks >= 1
    # First attempt was 0.5 (failed), second was 0.25 (cutback) which succeeded
    assert attempts[0] == pytest.approx(0.5)
    assert attempts[1] == pytest.approx(0.25)
    assert result.steps[0].load_factor == pytest.approx(0.25)


# ---------------------------------------------------------------------------
# 4. Repeated cutback: min step reached → failure
# ---------------------------------------------------------------------------


def test_repeated_cutback_fails_at_min_step():
    """When Newton never converges, cutbacks reach min_step and fail."""
    cfg = LoadSteppingConfig(
        initial_step_size=0.1,
        min_step_size=1e-4,
        cutback_factor=0.5,
    )
    solve = make_always_failing()
    result = adaptive_load_stepping(solve, cfg)

    assert not result.converged
    assert result.final_load_factor == 0.0
    assert result.n_cutbacks > 0
    assert len(result.steps) == 0


# ---------------------------------------------------------------------------
# 5. Full load reached
# ---------------------------------------------------------------------------


def test_full_load_reached():
    """Always-converging solver should reach target_load == 1.0."""
    solve = make_always_converging(n_iters=3)
    result = adaptive_load_stepping(solve)

    assert result.converged
    assert result.final_load_factor == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# 6. Step size bounds: never exceeds max_step_size
# ---------------------------------------------------------------------------


def test_step_size_never_exceeds_max():
    """No step increment should exceed max_step_size."""
    cfg = LoadSteppingConfig(
        initial_step_size=0.1,
        max_step_size=0.3,
        growth_factor=10.0,  # aggressive growth
        fast_convergence_iters=100,  # always "fast"
        target_load=2.0,  # use bigger target to get more steps
    )
    solve = make_always_converging(n_iters=2)
    result = adaptive_load_stepping(solve, cfg)

    assert result.converged
    increments = [
        result.steps[i].load_factor - (result.steps[i - 1].load_factor if i > 0 else 0.0)
        for i in range(len(result.steps))
    ]
    for inc in increments:
        assert inc <= cfg.max_step_size + 1e-12


# ---------------------------------------------------------------------------
# 7. Total step count: reasonable for uniform convergence
# ---------------------------------------------------------------------------


def test_reasonable_step_count():
    """With default config and uniform convergence, step count should be bounded."""
    solve = make_always_converging(n_iters=3)
    result = adaptive_load_stepping(solve)

    assert result.converged
    # With growth factor 1.5 starting at 0.1, should reach 1.0 well under 20 steps
    assert result.n_total_steps <= 20
    assert result.n_total_steps >= 2  # At least 2 steps needed


# ---------------------------------------------------------------------------
# 8. Load factor monotonic
# ---------------------------------------------------------------------------


def test_load_factor_monotonic():
    """Each converged step must have a strictly higher load_factor."""
    solve = make_always_converging(n_iters=2)
    result = adaptive_load_stepping(solve)

    assert result.converged
    load_factors = [s.load_factor for s in result.steps]
    for i in range(1, len(load_factors)):
        assert load_factors[i] > load_factors[i - 1]


# ---------------------------------------------------------------------------
# 9. Custom config
# ---------------------------------------------------------------------------


def test_custom_config():
    """Different initial_step_size and growth_factor should work correctly."""
    cfg = LoadSteppingConfig(
        initial_step_size=0.05,
        growth_factor=3.0,
        fast_convergence_iters=10,
        max_step_size=0.4,
        target_load=1.0,
    )
    solve = make_always_converging(n_iters=5)
    result = adaptive_load_stepping(solve, cfg)

    assert result.converged
    assert result.final_load_factor == pytest.approx(1.0)
    # First increment should be 0.05
    assert result.steps[0].load_factor == pytest.approx(0.05)


# ---------------------------------------------------------------------------
# 10. Edge case: target reached exactly — no overshoot
# ---------------------------------------------------------------------------


def test_no_overshoot_beyond_target():
    """Load factor must never exceed target_load."""
    cfg = LoadSteppingConfig(
        initial_step_size=0.3,
        growth_factor=2.0,
        fast_convergence_iters=100,
        max_step_size=1.0,
        target_load=1.0,
    )
    solve = make_always_converging(n_iters=1)
    result = adaptive_load_stepping(solve, cfg)

    assert result.converged
    for step in result.steps:
        assert step.load_factor <= cfg.target_load + 1e-15
    assert result.final_load_factor == pytest.approx(cfg.target_load)
