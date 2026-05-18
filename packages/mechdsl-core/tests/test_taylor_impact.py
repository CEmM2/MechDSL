"""Task P10-7 / Phase 8 P8-2: Taylor impact benchmark acceptance tests.

Problem: A short bar strikes a rigid wall at high velocity. Total Lagrangian
explicit dynamics + Johnson-Cook viscoplasticity (radial-return) + reduced
Hex8 with Flanagan-Belytschko hourglass control + frictionless rigid-wall
contact.

This module exercises the public Taylor benchmark surface
(:mod:`mechdsl.verify.benchmarks.taylor_impact`) in **two tiers**:

1. ``TestTaskP10_7`` — ``@nightly @regression @slow`` — the canonical
   acceptance tests for final length, mushroom radius, and peak equivalent
   plastic strain (PEEQ). These run only in the nightly tier (``-m "nightly
   or regression"``); they are deselected from the fast default tier.

2. ``TestTaskP8_2Smoke`` — ``@integration`` — fast deterministic smoke layer
   that exercises the public API on every commit (finiteness, consistency,
   determinism, parameter sensitivity). Runs in O(seconds) on a developer
   laptop.

Reference path (Path A — frozen regression baseline)
----------------------------------------------------
The original task scope (PLAN-B P10-7) framed the three nightly tests as a
comparison against Johnson & Cook (1985) Taylor impact data on OFHC copper
(``L_f/L_0 ≈ 0.825``, ``D_f/D_0 ≈ 1.91``, peak PEEQ ≈ 1.4–2.0). The
Phase E8 / P8-1 public runner (commit ``7aca187``), however, is calibrated
for a steel-like JC profile (matching ``test_phase10_taylor_state.py``):
``E=200 GPa``, ``A=350 MPa``, ``B=275 MPa``, ``n=0.36``, ``rho=7800``, etc.
Furthermore, ``TaylorImpactParameters.nightly()`` (6×6×20 mesh,
``dt=5e-8`` s, ``n_steps=400``) currently overruns the radial-return
solver's iteration budget on the refined mesh.

Per the P8-2 task brief, we therefore adopt **Path A**: the three nightly
tests are *regression* tests against frozen reference values computed from
a documented calibrated profile (see ``_taylor_impact_reference_params``
below), **not** a literature comparison. The 5 % / 5 % / 10 % tolerances
guard against semantic drift in the runtime, not against J&C 1985. Path B
(literature copper match) is research scope and would belong in a future
calibration task.

Frozen reference values (computed on commit ``4c89098``,
``2026-04-26``)::

    profile      = "regression"  (smoke + nz=20, n_steps=100, dt=1e-8)
    final_length      = 0.02521              m
    mushroom_radius   = 0.005564278964663555 m
    mushroom_diameter = 0.01112855792932711  m
    peak_peeq         = 2.841188188807695

These were captured under :func:`_taylor_impact_reference_params` and
verified bit-for-bit deterministic across three consecutive runs (NumPy
only, no random state, no dict-iteration-order dependence). If the runtime
intentionally changes physics, regenerate via the snippet at the bottom of
this docstring and bump these constants in the same commit.

Acceptance criteria (frozen-baseline interpretation):
  1. Final bar length within 5 % of the frozen reference.
  2. Mushroom (impact-end) diameter within 5 % of the frozen reference.
  3. Peak equivalent plastic strain within 10 % of the frozen reference.

Cross-phase dependencies: Phase 1 (TL kinematics), Phase 3 (J2 plasticity
return map / JC variant), Phase 5 (Hex8 element), Phase 7 (reduced
integration + hourglass control + rigid-wall contact), Phase 8 P8-1
(public benchmark API).

Regenerating frozen references
------------------------------
::

    uv run python -c "
    from mechdsl.verify.benchmarks import (
        TaylorImpactParameters, run_taylor_impact_benchmark,
    )
    p = TaylorImpactParameters.smoke(
        nz=20, n_steps=100, dt=1e-8, profile='regression',
    )
    r = run_taylor_impact_benchmark(params=p)
    print(r.extras['final_length'], r.extras['mushroom_radius'],
          r.extras['peak_peeq'])
    "
"""

from __future__ import annotations

import math
from dataclasses import replace

import numpy as np
import pytest

from mechdsl.verify.benchmarks import (
    TaylorImpactParameters,
    run_taylor_impact_benchmark,
)

# --- Frozen regression baseline (see module docstring) ---------------------
#
# Computed from ``_taylor_impact_reference_params()`` below on commit
# ``4c89098`` (2026-04-26). NOT independently sourced from Johnson & Cook
# (1985). These guard against semantic regressions in the Phase E7 explicit
# Taylor runtime + Phase E8 public runner; they are intentionally tight
# (5 % / 5 % / 10 %) per the original test names.

_REFERENCE_FINAL_LENGTH: float = 0.02521  # m
_REFERENCE_MUSHROOM_RADIUS: float = 0.005564278964663555  # m
_REFERENCE_MUSHROOM_DIAMETER: float = 2.0 * _REFERENCE_MUSHROOM_RADIUS  # m
_REFERENCE_PEAK_PEEQ: float = 2.841188188807695  # dimensionless

_FINAL_LENGTH_TOL: float = 0.05  # 5 %
_MUSHROOM_DIAMETER_TOL: float = 0.05  # 5 %
_PEAK_PEEQ_TOL: float = 0.10  # 10 %


def _taylor_impact_reference_params() -> TaylorImpactParameters:
    """Construct the calibrated reference profile used to freeze the regression
    baseline.

    Built from :meth:`TaylorImpactParameters.smoke` with the following
    overrides to refine the mesh and lengthen the integration horizon while
    staying comfortably below the radial-return solver's iteration budget
    (which the shipped ``nightly()`` profile currently overruns):

    - ``nz=20`` (axial refinement; cross section stays at 2 x 2 to bound
      runtime in O(1 s) on a developer laptop while still resolving
      mushroom development).
    - ``n_steps=100``, ``dt=1e-8`` s -> horizon 1.0 us.
      Long enough to develop measurable plastic strain (peak PEEQ ≈ 2.84);
      short enough that the explicit loop completes in ~1 s.
    - ``profile="regression"`` for telemetry.

    All other JC / geometry fields stay at the steel-like P8-1 defaults.
    Bit-for-bit deterministic across consecutive runs.
    """
    return TaylorImpactParameters.smoke(
        nz=20,
        n_steps=100,
        dt=1.0e-8,
        profile="regression",
    )


def _within_relative_tolerance(actual: float, reference: float, tol: float) -> bool:
    """``True`` iff ``|actual - reference| <= tol * |reference|``."""
    return abs(actual - reference) <= tol * abs(reference)


# ---------------------------------------------------------------------------
# Tier 1 — Nightly acceptance (frozen-reference regression)
# ---------------------------------------------------------------------------


class TestTaskP10_7:
    """Tests for Task P10-7 / P8-2: Taylor impact frozen-reference regression.

    These are the canonical acceptance tests; they remain marked
    ``@nightly @regression @slow`` per the P8-2 acceptance criteria so they
    run only under ``uv run pytest -m "nightly or regression"`` (the nightly
    tier), not in the fast default tier. The configured profile completes
    in ~1 s on a developer laptop, well below the slow-marker budget.
    """

    @pytest.mark.nightly
    @pytest.mark.regression
    @pytest.mark.slow
    def test_taylor_impact_final_length_within_5pct(self) -> None:
        """Final bar length within 5 % of the frozen regression reference."""
        params = _taylor_impact_reference_params()
        result = run_taylor_impact_benchmark(params=params)

        actual = result.extras["final_length"]
        assert math.isfinite(actual), f"final_length is not finite: {actual!r}"
        assert _within_relative_tolerance(actual, _REFERENCE_FINAL_LENGTH, _FINAL_LENGTH_TOL), (
            f"final_length={actual!r} drifted more than "
            f"{_FINAL_LENGTH_TOL * 100:.0f}% from frozen reference "
            f"{_REFERENCE_FINAL_LENGTH!r} "
            f"(rel error = {abs(actual - _REFERENCE_FINAL_LENGTH) / abs(_REFERENCE_FINAL_LENGTH):.4e}). "
            "If this drift is intentional, regenerate _REFERENCE_* per the module docstring."
        )

    @pytest.mark.nightly
    @pytest.mark.regression
    @pytest.mark.slow
    def test_taylor_impact_mushroom_diameter_within_5pct(self) -> None:
        """Mushroom (impact-end) diameter within 5 % of the frozen reference."""
        params = _taylor_impact_reference_params()
        result = run_taylor_impact_benchmark(params=params)

        actual = result.extras["mushroom_diameter"]
        assert math.isfinite(actual), f"mushroom_diameter is not finite: {actual!r}"
        # Consistency: diameter must equal twice the radius (no schema drift).
        assert actual == pytest.approx(2.0 * result.extras["mushroom_radius"]), (
            "mushroom_diameter is not 2 * mushroom_radius — extras schema drifted."
        )
        assert _within_relative_tolerance(
            actual, _REFERENCE_MUSHROOM_DIAMETER, _MUSHROOM_DIAMETER_TOL
        ), (
            f"mushroom_diameter={actual!r} drifted more than "
            f"{_MUSHROOM_DIAMETER_TOL * 100:.0f}% from frozen reference "
            f"{_REFERENCE_MUSHROOM_DIAMETER!r} "
            f"(rel error = {abs(actual - _REFERENCE_MUSHROOM_DIAMETER) / abs(_REFERENCE_MUSHROOM_DIAMETER):.4e}). "
            "If this drift is intentional, regenerate _REFERENCE_* per the module docstring."
        )

    @pytest.mark.nightly
    @pytest.mark.regression
    @pytest.mark.slow
    def test_taylor_impact_peak_peeq_within_10pct(self) -> None:
        """Peak equivalent plastic strain within 10 % of the frozen reference."""
        params = _taylor_impact_reference_params()
        result = run_taylor_impact_benchmark(params=params)

        actual = result.extras["peak_peeq"]
        assert math.isfinite(actual), f"peak_peeq is not finite: {actual!r}"
        assert actual >= 0.0, f"peak_peeq must be non-negative; got {actual!r}"
        assert _within_relative_tolerance(actual, _REFERENCE_PEAK_PEEQ, _PEAK_PEEQ_TOL), (
            f"peak_peeq={actual!r} drifted more than "
            f"{_PEAK_PEEQ_TOL * 100:.0f}% from frozen reference "
            f"{_REFERENCE_PEAK_PEEQ!r} "
            f"(rel error = {abs(actual - _REFERENCE_PEAK_PEEQ) / abs(_REFERENCE_PEAK_PEEQ):.4e}). "
            "If this drift is intentional, regenerate _REFERENCE_* per the module docstring."
        )


# ---------------------------------------------------------------------------
# Tier 2 — Smoke layer (fast tier, runs on every commit)
# ---------------------------------------------------------------------------


class TestTaskP8_2Smoke:
    """Phase 8 P8-2 fast-tier smoke layer for the Taylor impact benchmark.

    These tests use :meth:`TaylorImpactParameters.smoke` (2 x 2 x 8 mesh,
    n_steps=10, ~0.04 s wallclock) and assert only on shape / finiteness /
    determinism / parameter sensitivity — NOT on absolute reference values
    (which is the job of ``TestTaskP10_7``). They satisfy the
    "deterministic under smoke settings" half of P8-2's AC-2 and ensure the
    public benchmark surface gets exercised in the fast CI tier on every
    commit.
    """

    @pytest.mark.integration
    def test_smoke_run_returns_finite_metrics(self) -> None:
        """A smoke-tier Taylor run completes and returns finite, physically
        admissible metrics with the documented extras schema intact.
        """
        params = TaylorImpactParameters.smoke()
        result = run_taylor_impact_benchmark(params=params)

        # Shape: result.displacements is (n_nodes, 3) and finite.
        assert result.displacements.ndim == 2
        assert result.displacements.shape[1] == 3
        assert np.all(np.isfinite(result.displacements))

        # All Taylor-specific metrics are finite.
        for key in ("final_length", "mushroom_radius", "mushroom_diameter", "peak_peeq"):
            value = result.extras[key]
            assert isinstance(value, float)
            assert math.isfinite(value), f"{key}={value!r} is not finite"

        # Physical admissibility: non-negativity + bounded compression.
        assert result.extras["final_length"] > 0.0
        assert result.extras["mushroom_radius"] >= 0.0
        assert result.extras["peak_peeq"] >= 0.0
        # Smoke run is short — bar should not be more than mildly compressed.
        assert result.extras["final_length"] <= params.length + 1.0e-12
        assert result.extras["final_length"] >= 0.5 * params.length

        # Diameter == 2 * radius (extras schema consistency).
        assert result.extras["mushroom_diameter"] == pytest.approx(
            2.0 * result.extras["mushroom_radius"]
        )

        # Profile telemetry round-trips.
        assert result.extras["profile"] == "smoke"

    @pytest.mark.integration
    def test_smoke_run_is_bit_for_bit_deterministic(self) -> None:
        """Two consecutive smoke runs produce bit-for-bit identical metrics
        and displacement fields. Guards against accidental random-state /
        dict-ordering / float-reduction-order regressions in the runtime.
        """
        params = TaylorImpactParameters.smoke()
        result_a = run_taylor_impact_benchmark(params=params)
        result_b = run_taylor_impact_benchmark(params=params)

        np.testing.assert_array_equal(result_a.displacements, result_b.displacements)
        for key in ("final_length", "mushroom_radius", "mushroom_diameter", "peak_peeq"):
            assert result_a.extras[key] == result_b.extras[key], (
                f"smoke run is non-deterministic on extras[{key!r}]: "
                f"{result_a.extras[key]!r} vs {result_b.extras[key]!r}"
            )

    @pytest.mark.integration
    def test_smoke_run_is_parameter_sensitive(self) -> None:
        """Distinct ``impact_velocity`` / ``wall_z`` settings produce distinct
        ``final_length``. Guards against the runner silently ignoring its
        physics inputs.
        """
        baseline_params = TaylorImpactParameters.smoke()
        baseline = run_taylor_impact_benchmark(params=baseline_params).extras

        # Faster impact -> larger compression -> different final length.
        faster = run_taylor_impact_benchmark(
            params=replace(baseline_params, impact_velocity=-300.0),
        ).extras
        assert faster["final_length"] != baseline["final_length"], (
            "Doubling impact velocity left final_length unchanged — "
            "the runner appears to ignore impact_velocity."
        )

        # Wall placed strictly below the bar -> bar is free to translate
        # before contact -> different final length.
        moved_wall = run_taylor_impact_benchmark(
            params=replace(baseline_params, wall_z=-1.0e-3),
        ).extras
        assert moved_wall["final_length"] != baseline["final_length"], (
            "Moving the wall left final_length unchanged — the runner appears to ignore wall_z."
        )
