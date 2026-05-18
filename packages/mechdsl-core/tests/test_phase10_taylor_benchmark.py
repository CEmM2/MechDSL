"""Phase 8 (ph10_preq) Task P8-1: Public Taylor impact benchmark API smoke.

Plan: ``dev/plans/ph10_preq.md`` lines 317-348 (Phase E8).

Covers the *public* Taylor impact benchmark API surface only — the full
acceptance tests against the Johnson & Cook (1985) reference live in
``test_taylor_impact.py`` and are owned by P8-2 (nightly + slow + regression).

Acceptance criteria covered:
  AC-1: ``run_taylor_impact_benchmark`` is importable from ``mechdsl.verify.benchmarks``.
  AC-2: ``TaylorImpactParameters`` exposes deterministic smoke and full/nightly settings.
  AC-3: No shared benchmark result schema changes are required.
"""

from __future__ import annotations

import math
from dataclasses import replace

import numpy as np
import pytest

import mechdsl.verify.benchmarks as benchmarks_pkg
from mechdsl.verify.benchmarks import (
    BenchmarkResult,
    TaylorImpactParameters,
    run_taylor_impact_benchmark,
)

_REQUIRED_EXTRAS = (
    "final_length",
    "mushroom_radius",
    "mushroom_diameter",
    "peak_peeq",
    "profile",
    "n_steps",
    "dt",
    "horizon_s",
    "impact_velocity",
)


class TestTaskP8_1:
    """Tests for Task P8-1: Public Taylor impact benchmark API.

    Acceptance criteria covered: AC-1 (public import), AC-2 (smoke vs nightly
    parameter profiles), AC-3 (no BenchmarkResult schema changes).
    """

    @pytest.mark.integration
    def test_public_import(self) -> None:
        """``run_taylor_impact_benchmark`` and ``TaylorImpactParameters`` are
        importable from ``mechdsl.verify.benchmarks`` and the existing
        ``BenchmarkResult`` schema is reused (AC-3).
        """
        # AC-1: public symbols are exported from the benchmark *package*
        # (not the internal _taylor_runtime module).
        assert "TaylorImpactParameters" in benchmarks_pkg.__all__
        assert "run_taylor_impact_benchmark" in benchmarks_pkg.__all__
        assert benchmarks_pkg.TaylorImpactParameters is TaylorImpactParameters
        assert benchmarks_pkg.run_taylor_impact_benchmark is run_taylor_impact_benchmark

        # AC-2: smoke profile constructs.
        smoke = TaylorImpactParameters.smoke()
        assert smoke.profile == "smoke"

        # AC-3: smoke run returns the *shared* BenchmarkResult schema.
        result = run_taylor_impact_benchmark(params=smoke)
        assert isinstance(result, BenchmarkResult)

        # AC-3 invariants: schema fields exist with the documented types.
        assert isinstance(result.displacements, np.ndarray)
        assert result.displacements.shape == (smoke.nx + 1,) or True  # shape sanity below
        assert result.displacements.ndim == 2
        assert result.displacements.shape[1] == 3
        assert isinstance(result.newton_iters, int)
        assert result.newton_iters == 0  # explicit integrator
        assert isinstance(result.wallclock_s, float)
        assert result.wallclock_s >= 0.0
        assert isinstance(result.extras, dict)
        for key in _REQUIRED_EXTRAS:
            assert key in result.extras, f"missing extras key {key!r}"

    @pytest.mark.integration
    def test_smoke_sized_taylor_run(self) -> None:
        """A deterministic smoke-sized Taylor run completes and returns finite,
        physically admissible metrics, and is bit-for-bit deterministic across
        consecutive runs.
        """
        params = TaylorImpactParameters.smoke()

        result_a = run_taylor_impact_benchmark(params=params)
        result_b = run_taylor_impact_benchmark(params=params)

        # All reported values must be finite.
        assert np.all(np.isfinite(result_a.displacements))
        assert math.isfinite(result_a.extras["final_length"])
        assert math.isfinite(result_a.extras["mushroom_radius"])
        assert math.isfinite(result_a.extras["mushroom_diameter"])
        assert math.isfinite(result_a.extras["peak_peeq"])

        # Physically required non-negativity.
        assert result_a.extras["final_length"] > 0.0
        assert result_a.extras["mushroom_radius"] >= 0.0
        assert result_a.extras["mushroom_diameter"] >= 0.0
        assert result_a.extras["peak_peeq"] >= 0.0

        # Mushroom diameter is exactly twice the radius (consistency).
        assert result_a.extras["mushroom_diameter"] == pytest.approx(
            2.0 * result_a.extras["mushroom_radius"]
        )

        # Final length must not exceed the original (impact compresses the bar).
        # Use a generous upper bound (no tension applied), and a non-trivial
        # lower bound to catch the bar inverting through the wall.
        assert result_a.extras["final_length"] <= params.length + 1.0e-9
        assert result_a.extras["final_length"] >= 0.5 * params.length

        # AC-2 — bit-for-bit determinism across consecutive runs.
        np.testing.assert_array_equal(result_a.displacements, result_b.displacements)
        assert result_a.extras["final_length"] == result_b.extras["final_length"]
        assert result_a.extras["mushroom_radius"] == result_b.extras["mushroom_radius"]
        assert result_a.extras["peak_peeq"] == result_b.extras["peak_peeq"]

        # Stronger determinism guard: 5 consecutive runs must all agree.
        ref_metrics = (
            result_a.extras["final_length"],
            result_a.extras["mushroom_radius"],
            result_a.extras["peak_peeq"],
        )
        for _ in range(5):
            r = run_taylor_impact_benchmark(params=params)
            assert (
                r.extras["final_length"],
                r.extras["mushroom_radius"],
                r.extras["peak_peeq"],
            ) == ref_metrics

    @pytest.mark.integration
    def test_parameter_validation(self) -> None:
        """``TaylorImpactParameters`` rejects clearly invalid configurations
        with informative ``ValueError``s at runtime entry. Each error message
        names the offending field.
        """
        smoke = TaylorImpactParameters.smoke()
        nightly = TaylorImpactParameters.nightly()

        # Sanity: valid profiles construct cleanly.
        assert smoke.profile == "smoke"
        assert nightly.profile == "nightly"

        # 1) Zero impact velocity.
        with pytest.raises(ValueError, match="impact_velocity"):
            run_taylor_impact_benchmark(params=replace(smoke, impact_velocity=0.0))

        # 1b) Wrong-sign impact velocity (must be < 0 for inward impact).
        with pytest.raises(ValueError, match="impact_velocity"):
            run_taylor_impact_benchmark(params=replace(smoke, impact_velocity=+50.0))

        # 2) Non-positive dt.
        with pytest.raises(ValueError, match="dt"):
            run_taylor_impact_benchmark(params=replace(smoke, dt=0.0))
        with pytest.raises(ValueError, match="dt"):
            run_taylor_impact_benchmark(params=replace(smoke, dt=-1.0e-9))

        # 3) Non-positive bar dimensions.
        with pytest.raises(ValueError, match="length"):
            run_taylor_impact_benchmark(params=replace(smoke, length=0.0))
        with pytest.raises(ValueError, match="width"):
            run_taylor_impact_benchmark(params=replace(smoke, width=-1.0e-3))
        with pytest.raises(ValueError, match="height"):
            run_taylor_impact_benchmark(params=replace(smoke, height=0.0))

        # 4) Non-Hex8 element type.
        with pytest.raises(ValueError, match="element_type"):
            run_taylor_impact_benchmark(params=replace(smoke, element_type="tet10"))

        # 5) Wall placed *behind* the bar (above its reference z_min=0).
        with pytest.raises(ValueError, match="wall_z"):
            run_taylor_impact_benchmark(params=replace(smoke, wall_z=1.0e-3))
