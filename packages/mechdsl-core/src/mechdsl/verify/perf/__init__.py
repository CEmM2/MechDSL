"""Phase 9 P9-1: benchmark registry, smoke runners, and baseline comparison.

The registry catalogues the nine public Phase 10 benchmark runners (P10-1 ..
P10-9) with smoke-sized parameter factories and metric extractors, and emits
a stable JSON-shaped comparison report against the committed local baseline.

Public API
----------
:class:`BenchmarkSpec`
    One registry entry: the public runner, its smoke parameter factory, the
    metrics extracted from the runner result, and the per-benchmark default
    tolerance.
:class:`BenchmarkRegistry`
    Frozen catalogue of the nine Phase 10 specs.
:func:`run_smoke_registry`
    Invoke every spec under its smoke profile and pack metrics + wallclock.
:class:`MetricDelta`, :class:`BenchmarkComparison`, :class:`ComparisonReport`
    Per-benchmark, per-metric deltas with JSON round-trip.
:func:`compare_to_baseline`
    Compute deltas against a committed baseline.
:func:`load_smoke_baseline`
    Load the committed baseline JSON.
"""

from mechdsl.verify.perf.baseline import (
    BenchmarkComparison,
    ComparisonReport,
    MetricDelta,
    compare_to_baseline,
    load_smoke_baseline,
)
from mechdsl.verify.perf.registry import (
    BenchmarkRegistry,
    BenchmarkSpec,
    run_smoke_registry,
)

__all__ = [
    "BenchmarkComparison",
    "BenchmarkRegistry",
    "BenchmarkSpec",
    "ComparisonReport",
    "MetricDelta",
    "compare_to_baseline",
    "load_smoke_baseline",
    "run_smoke_registry",
]
