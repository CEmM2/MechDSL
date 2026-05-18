"""Smoke baseline loader and per-benchmark delta reporter.

The committed baseline at ``packages/mechdsl-core/tests/golden/perf/
baseline_smoke.json`` records, for every Phase 10 task in the registry,
the smoke-run wallclock plus a small set of dimensionless metrics. Nightly
CI (P9-2) loads the baseline and calls :func:`compare_to_baseline` to flag
per-benchmark, per-metric drift relative to the configured tolerance.

The :class:`ComparisonReport` shape is stable and JSON round-trippable so
downstream tooling can parse it without depending on this package.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_DEFAULT_BASELINE_PATH = (
    Path(__file__).resolve().parents[4]  # .../packages/mechdsl-core
    / "tests"
    / "golden"
    / "perf"
    / "baseline_smoke.json"
)


# ---------------------------------------------------------------------------
# Report dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MetricDelta:
    """One metric's delta between current and baseline runs."""

    metric: str
    baseline: float
    current: float
    abs_delta: float
    pct_delta: float  # signed: (current - baseline) / |baseline| * 100
    within_tolerance: bool
    tolerance_pct: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric": self.metric,
            "baseline": self.baseline,
            "current": self.current,
            "abs_delta": self.abs_delta,
            "pct_delta": self.pct_delta,
            "within_tolerance": self.within_tolerance,
            "tolerance_pct": self.tolerance_pct,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MetricDelta:
        return cls(
            metric=str(data["metric"]),
            baseline=float(data["baseline"]),
            current=float(data["current"]),
            abs_delta=float(data["abs_delta"]),
            pct_delta=float(data["pct_delta"]),
            within_tolerance=bool(data["within_tolerance"]),
            tolerance_pct=float(data["tolerance_pct"]),
        )


@dataclass(frozen=True)
class BenchmarkComparison:
    """All metric deltas for one benchmark, plus the aggregated pass flag."""

    task_id: str
    deltas: tuple[MetricDelta, ...]
    overall_pass: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "deltas": [d.to_dict() for d in self.deltas],
            "overall_pass": self.overall_pass,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BenchmarkComparison:
        deltas = tuple(MetricDelta.from_dict(d) for d in data["deltas"])
        return cls(
            task_id=str(data["task_id"]),
            deltas=deltas,
            overall_pass=bool(data["overall_pass"]),
        )


@dataclass(frozen=True)
class ComparisonReport:
    """Per-benchmark comparison bundle with JSON round-trip."""

    benchmarks: tuple[BenchmarkComparison, ...]
    overall_pass: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "benchmarks": [b.to_dict() for b in self.benchmarks],
            "overall_pass": self.overall_pass,
        }

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ComparisonReport:
        benchmarks = tuple(BenchmarkComparison.from_dict(b) for b in data["benchmarks"])
        return cls(
            benchmarks=benchmarks,
            overall_pass=bool(data["overall_pass"]),
        )

    @classmethod
    def from_json(cls, payload: str) -> ComparisonReport:
        return cls.from_dict(json.loads(payload))


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


def load_smoke_baseline(path: Path | None = None) -> dict[str, dict[str, float]]:
    """Load the committed smoke baseline JSON, keyed by task_id.

    Parameters
    ----------
    path
        Override path. Defaults to ``packages/mechdsl-core/tests/golden/perf/
        baseline_smoke.json``.

    Returns
    -------
    dict
        ``{task_id: {metric: float, ..., "wallclock_s": float}}``.
    """

    target = Path(path) if path is not None else _DEFAULT_BASELINE_PATH
    if not target.exists():
        raise FileNotFoundError(
            f"Smoke baseline file not found at {target}. Regenerate via "
            "the recipe in tests/golden/perf/README.md."
        )
    with target.open("r", encoding="utf-8") as fh:
        payload = json.load(fh)

    if not isinstance(payload, dict) or "tasks" not in payload:
        raise ValueError(
            f"Malformed baseline at {target}: expected top-level dict with a "
            f"'tasks' key, got {type(payload).__name__}."
        )

    tasks = payload["tasks"]
    if not isinstance(tasks, dict):
        raise ValueError(
            f"Malformed baseline at {target}: 'tasks' must be a dict mapping "
            f"task_id -> metrics dict; got {type(tasks).__name__}."
        )

    out: dict[str, dict[str, float]] = {}
    for task_id, metrics in tasks.items():
        if not isinstance(metrics, dict):
            raise ValueError(
                f"Malformed baseline entry for {task_id!r}: expected dict, "
                f"got {type(metrics).__name__}."
            )
        out[str(task_id)] = {str(k): float(v) for k, v in metrics.items()}
    return out


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------


def compare_to_baseline(
    current: dict[str, dict[str, float]],
    baseline: dict[str, dict[str, float]],
    *,
    tolerance_pct: float = 10.0,
    per_benchmark_overrides: dict[str, float] | None = None,
) -> ComparisonReport:
    """Compute per-benchmark, per-metric deltas vs the baseline.

    For every ``task_id`` present in both dicts, every metric in
    ``baseline[task_id]`` is paired with its counterpart in
    ``current[task_id]``. The signed percent change is

    .. code-block:: text

       pct_delta = (current - baseline) / |baseline| * 100   (baseline != 0)

    A metric **passes** when ``abs(pct_delta) <= tolerance``. The benchmark's
    ``overall_pass`` is the conjunction of its per-metric flags. The report's
    top-level ``overall_pass`` is the conjunction across benchmarks.

    Parameters
    ----------
    current, baseline
        Maps ``task_id -> {metric: float}``. Both should include
        ``wallclock_s`` per benchmark.
    tolerance_pct
        Default tolerance in percent (e.g. ``10.0`` means +/-10%).
    per_benchmark_overrides
        Optional ``{task_id: tolerance_pct}`` overrides — applied per
        benchmark when present.

    Returns
    -------
    ComparisonReport
        One :class:`BenchmarkComparison` per ``task_id`` shared by both
        dicts, with deltas in deterministic (alphabetical) metric order.
    """

    overrides = dict(per_benchmark_overrides or {})
    benchmarks: list[BenchmarkComparison] = []

    shared_ids = sorted(set(current) & set(baseline))
    for task_id in shared_ids:
        tol = float(overrides.get(task_id, tolerance_pct))
        cur_metrics = current[task_id]
        base_metrics = baseline[task_id]
        deltas: list[MetricDelta] = []
        for metric in sorted(base_metrics):
            if metric not in cur_metrics:
                continue
            base_val = float(base_metrics[metric])
            cur_val = float(cur_metrics[metric])
            abs_delta = cur_val - base_val
            if base_val == 0.0:
                # Avoid div-by-zero; flag any non-zero current as 100% drift.
                pct_delta = 0.0 if cur_val == 0.0 else math.copysign(float("inf"), abs_delta)
            else:
                pct_delta = (cur_val - base_val) / abs(base_val) * 100.0
            within = math.isfinite(pct_delta) and abs(pct_delta) <= tol
            deltas.append(
                MetricDelta(
                    metric=metric,
                    baseline=base_val,
                    current=cur_val,
                    abs_delta=abs_delta,
                    pct_delta=pct_delta,
                    within_tolerance=within,
                    tolerance_pct=tol,
                )
            )
        overall = all(d.within_tolerance for d in deltas) if deltas else False
        benchmarks.append(
            BenchmarkComparison(
                task_id=task_id,
                deltas=tuple(deltas),
                overall_pass=overall,
            )
        )

    overall_pass = all(b.overall_pass for b in benchmarks) if benchmarks else False
    return ComparisonReport(
        benchmarks=tuple(benchmarks),
        overall_pass=overall_pass,
    )
