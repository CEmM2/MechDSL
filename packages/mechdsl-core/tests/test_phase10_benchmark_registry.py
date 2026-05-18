"""Phase 9 (ph10_preq) Task P9-1: Benchmark registry + local smoke baselines.

Plan: ``dev/plans/ph10_preq.md`` lines 350-385 (Phase E9).

Covers the *registry* surface and *local smoke baseline* artifacts that
P9-2 will then wire into nightly CI. The nightly tests themselves (full
benchmark + injected-slowdown detection + workflow command verification)
live in ``test_perf_regression.py`` and are owned by P9-2.

Acceptance criteria covered:
  AC-1: P10-1 through P10-9 are represented in the registry.
  AC-2: Local performance test uses smoke settings.
  AC-3: Baseline comparison reports clear per-benchmark deltas.

All tests skip until P9-1 is implemented.
"""

from __future__ import annotations

import math

import pytest

from mechdsl.verify.perf import (
    BenchmarkRegistry,
    BenchmarkSpec,
    ComparisonReport,
    compare_to_baseline,
    load_smoke_baseline,
)

# Baseline file location: packages/mechdsl-core/tests/golden/perf/baseline_smoke.json


_EXPECTED_REGISTRY_TASKS = (
    "P10-1",  # MMS convergence matrix (Phase 6)
    "P10-2",  # Cantilever (Phase 5)
    "P10-3",  # Cook membrane (PLAN-B + Phase 3 closure)
    "P10-4",  # Thick cylinder (PLAN-B)
    "P10-5",  # Plate with hole (PLAN-B)
    "P10-6",  # Necking bar (PLAN-B + Phase 3 closure)
    "P10-7",  # Taylor impact (Phase 8)
    "P10-8",  # Notched bar (PLAN-B)
    "P10-9",  # HGO uniaxial (PLAN-B)
)


class TestTaskP9_1:
    """Tests for Task P9-1: Benchmark registry and local baselines.

    Acceptance criteria covered: AC-1 (registry completeness P10-1..P10-9),
    AC-2 (local smoke profile), AC-3 (per-benchmark delta reporting).
    """

    @pytest.mark.regression
    def test_registry_includes_all_benchmark_runners(self) -> None:
        """The benchmark registry exposes every P10-1..P10-9 public runner.

        Acceptance criterion: AC-1 — P10-1..P10-9 represented.
        """
        registry = BenchmarkRegistry.default()
        specs = list(registry)

        # Every expected task_id is present, exactly once.
        registered_ids = [spec.task_id for spec in specs]
        for task_id in _EXPECTED_REGISTRY_TASKS:
            assert task_id in registered_ids, (
                f"task_id {task_id!r} missing from BenchmarkRegistry.default()"
            )
            assert registered_ids.count(task_id) == 1, (
                f"task_id {task_id!r} registered more than once"
            )

        # Each spec has the required public-API shape.
        for spec in specs:
            assert isinstance(spec, BenchmarkSpec)
            assert callable(spec.runner), (
                f"{spec.task_id}: runner must be callable, got {type(spec.runner).__name__}"
            )
            assert callable(spec.smoke_factory), f"{spec.task_id}: smoke_factory must be callable"
            assert isinstance(spec.metrics_keys, tuple), (
                f"{spec.task_id}: metrics_keys must be a tuple"
            )
            assert len(spec.metrics_keys) >= 1, f"{spec.task_id}: metrics_keys must be non-empty"
            for key in spec.metrics_keys:
                assert isinstance(key, str) and key, (
                    f"{spec.task_id}: every metrics_keys entry must be a non-empty string"
                )

            # Runners come from the public benchmark surfaces (no leading-underscore modules).
            runner_module = getattr(spec.runner, "__module__", "")
            assert "._" not in runner_module, (
                f"{spec.task_id}: runner {runner_module} appears to be from a private module"
            )

        # Indexing by task_id round-trips.
        for task_id in _EXPECTED_REGISTRY_TASKS:
            spec = registry[task_id]
            assert spec.task_id == task_id

    @pytest.mark.regression
    def test_smoke_baseline_load(self) -> None:
        """The committed smoke baseline artifact loads and is keyed by ``task_id``.

        Acceptance criterion: AC-2 — local smoke baseline exists, loads without
        GPU or external services, and covers every expected task_id with finite
        values.
        """
        baseline = load_smoke_baseline()

        assert isinstance(baseline, dict)
        for task_id in _EXPECTED_REGISTRY_TASKS:
            assert task_id in baseline, f"baseline missing entry for {task_id!r}"
            metrics = baseline[task_id]
            assert isinstance(metrics, dict) and metrics, (
                f"{task_id}: baseline metrics must be a non-empty dict"
            )

            # Wallclock is required and must be a finite, non-negative float.
            assert "wallclock_s" in metrics, f"{task_id}: missing wallclock_s in baseline"
            wall = metrics["wallclock_s"]
            assert isinstance(wall, float)
            assert math.isfinite(wall) and wall >= 0.0, (
                f"{task_id}: wallclock_s must be finite and non-negative, got {wall!r}"
            )

            # Every other metric is finite. newton_iters (when present) is non-negative.
            for key, value in metrics.items():
                assert isinstance(value, float), (
                    f"{task_id}: baseline metric {key!r} must be float, got {type(value).__name__}"
                )
                assert math.isfinite(value), (
                    f"{task_id}: baseline metric {key!r} is not finite ({value!r})"
                )
                if key in {"newton_iters", "wallclock_s"}:
                    assert value >= 0.0, (
                        f"{task_id}: baseline metric {key!r} must be non-negative, got {value!r}"
                    )

    @pytest.mark.regression
    def test_metric_delta_reporting(self) -> None:
        """``compare_to_baseline`` returns clear per-benchmark deltas with named
        metrics and signed percentage changes.

        Acceptance criterion: AC-3 — per-benchmark deltas reported clearly,
        sign-aware, with overall_pass flag flipped only for benchmarks above
        tolerance.
        """
        baseline = load_smoke_baseline()

        # Synthetic "current": +5% on every metric in every benchmark.
        # +5% sits inside the default 10% tolerance so every flag should pass.
        scale_small = 1.05
        current_5pct = {
            task_id: {key: scale_small * val for key, val in metrics.items()}
            for task_id, metrics in baseline.items()
        }

        report_5pct = compare_to_baseline(current_5pct, baseline)
        assert isinstance(report_5pct, ComparisonReport)
        assert report_5pct.overall_pass is True

        # Sign + magnitude check on every metric of every benchmark.
        for benchmark in report_5pct.benchmarks:
            assert benchmark.overall_pass is True, (
                f"{benchmark.task_id}: +5% perturbation should not flip overall_pass under "
                f"default 10% tolerance"
            )
            for delta in benchmark.deltas:
                if delta.baseline == 0.0:
                    # Compare-to-zero edge case: +5% of 0 is 0; pct_delta defined as 0.
                    assert delta.current == 0.0
                    assert delta.pct_delta == 0.0
                    continue
                # Signed percent should be ~+5% (positive — current is larger).
                assert delta.pct_delta == pytest.approx(5.0, rel=1e-9), (
                    f"{benchmark.task_id}.{delta.metric}: expected pct_delta ~+5.0, got "
                    f"{delta.pct_delta}"
                )
                assert delta.within_tolerance is True
                # abs_delta sign: positive (current > baseline).
                assert delta.abs_delta > 0.0
                # Sanity: abs_delta and pct_delta share sign.
                assert math.copysign(1.0, delta.abs_delta) == math.copysign(1.0, delta.pct_delta)

        # +20% on a single targeted benchmark; others stay at +5%. The targeted
        # benchmark must flip overall_pass; all others must stay passing.
        targeted = "P10-2"
        scale_large = 1.20
        current_mixed = {
            task_id: {
                key: (scale_large if task_id == targeted else scale_small) * val
                for key, val in metrics.items()
            }
            for task_id, metrics in baseline.items()
        }

        report_mixed = compare_to_baseline(current_mixed, baseline)
        assert report_mixed.overall_pass is False
        for benchmark in report_mixed.benchmarks:
            if benchmark.task_id == targeted:
                # The +20% benchmark must flip — at least one metric outside tolerance.
                assert benchmark.overall_pass is False
                # Find at least one delta with pct_delta ~ +20 and within_tolerance False.
                exceeded = [
                    d for d in benchmark.deltas if d.baseline != 0.0 and not d.within_tolerance
                ]
                assert exceeded, (
                    f"{targeted}: +20% perturbation should flag at least one metric "
                    "as outside the 10% default tolerance"
                )
                for delta in exceeded:
                    assert delta.pct_delta == pytest.approx(20.0, rel=1e-9), (
                        f"{targeted}.{delta.metric}: expected pct_delta ~+20.0, got "
                        f"{delta.pct_delta}"
                    )
            else:
                assert benchmark.overall_pass is True, (
                    f"{benchmark.task_id}: +5% perturbation should NOT flip overall_pass "
                    "while only P10-2 is at +20%"
                )

        # JSON round-trip: report -> dict -> report must preserve structure.
        round_trip = ComparisonReport.from_dict(report_mixed.to_dict())
        assert round_trip.overall_pass == report_mixed.overall_pass
        assert len(round_trip.benchmarks) == len(report_mixed.benchmarks)
        for original, restored in zip(report_mixed.benchmarks, round_trip.benchmarks, strict=True):
            assert restored.task_id == original.task_id
            assert restored.overall_pass == original.overall_pass
            assert len(restored.deltas) == len(original.deltas)
            for od, rd in zip(original.deltas, restored.deltas, strict=True):
                assert rd.metric == od.metric
                assert rd.baseline == od.baseline
                assert rd.current == od.current
                assert rd.pct_delta == od.pct_delta
                assert rd.within_tolerance == od.within_tolerance
