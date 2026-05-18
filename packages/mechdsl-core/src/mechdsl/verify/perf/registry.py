"""Benchmark registry, smoke profiles, and one-shot smoke run harness.

The registry catalogues the nine public Phase 10 benchmark runners and their
local smoke profiles. Every spec exposes:

* ``task_id``       — canonical Phase 10 task id (``P10-1`` .. ``P10-9``).
* ``runner``        — the public runner callable from
  :mod:`mechdsl.verify.benchmarks` or :mod:`mechdsl.verify.mms_matrix`.
* ``smoke_factory`` — zero-arg callable returning the kwargs dict consumed by
  ``runner``. Returning a dict (not the parameters dataclass) keeps the
  registry uniform across runners that take a parameters object, loose
  kwargs, or a ``Mesh + kwargs`` bundle.
* ``metrics_keys``  — tuple of metric names recorded into the baseline. Each
  metric is extracted by ``result_adapter``.
* ``result_adapter``— callable that maps the runner's return value to a
  ``dict[str, float]`` containing every key in ``metrics_keys`` (the
  ``wallclock_s`` slot is filled in by :func:`run_smoke_registry`).
* ``tolerance_pct`` — default per-benchmark tolerance for baseline diffs.
* ``notes``         — free-form context (e.g. carry-forward constraints).

Carry-forward constraints honoured here
---------------------------------------
* P10-7 (Taylor): the spec uses :meth:`TaylorImpactParameters.smoke` only.
  ``nightly()`` overruns the JC ``radial_return`` 50-iteration budget on the
  shipped 6x6x20 mesh, and PEEQ on long horizons (~16.6 at n_steps=200) is
  unphysical (P8-2 carry-forward). The smoke profile (2x2x8 Hex8, 10 steps,
  dt=2e-8 s, horizon=0.2 us) keeps PEEQ in the < ~3 range.
* P10-1 (MMS): the registry restricts the matrix to the cheap Hex8 SVK case
  with three coarse mesh levels (4, 6, 8) so the local smoke run finishes
  in O(seconds) on a developer laptop. Convergence rates from the resulting
  ``MMSMatrixResult`` are recorded in the baseline alongside wallclock.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import numpy as np

from mechdsl.symbolic.models.hgo import HGOMaterial
from mechdsl.verify.benchmarks import (
    BenchmarkResult,
    CantileverParameters,
    CookMembraneParameters,
    NeckingBarParameters,
    PlateWithHoleParameters,
    TaylorImpactParameters,
    build_notched_bar_mesh,
    run_cantilever_benchmark,
    run_cook_membrane_benchmark,
    run_hgo_uniaxial,
    run_necking_bar_benchmark,
    run_notched_bar_benchmark,
    run_plate_with_hole_benchmark,
    run_taylor_impact_benchmark,
    run_thick_cylinder_benchmark,
)
from mechdsl.verify.mms_matrix import (
    MMSMatrixCase,
    MMSMatrixResult,
    run_mms_convergence_matrix,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator
    from pathlib import Path


# ---------------------------------------------------------------------------
# Spec dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BenchmarkSpec:
    """A single registry entry over one Phase 10 public benchmark runner.

    Attributes
    ----------
    task_id
        Canonical Phase 10 task id (``"P10-1"`` .. ``"P10-9"``).
    runner
        The public runner callable from :mod:`mechdsl.verify.benchmarks` or
        :mod:`mechdsl.verify.mms_matrix`. Returns either a
        :class:`mechdsl.verify.benchmarks.BenchmarkResult` or (for MMS) a
        :class:`mechdsl.verify.mms_matrix.MMSMatrixResult`.
    smoke_factory
        Zero-arg callable returning the ``kwargs`` dict that ``runner`` is
        invoked with. Keeps the registry uniform across runners with very
        different parameter shapes (parameters dataclass, loose kwargs,
        Mesh + kwargs).
    metrics_keys
        Names of the metrics the registry extracts from the runner's result
        and records in the baseline. Always non-empty.
    result_adapter
        Callable mapping a runner result to a ``dict[str, float]`` with one
        entry per ``metrics_keys`` name.
    runner_kwargs
        Optional static kwargs merged into the runner invocation on top of
        ``smoke_factory()`` (e.g. shared ``tmp_path`` injection slot).
    tolerance_pct
        Default per-benchmark tolerance for baseline diffs. Overridable via
        ``compare_to_baseline(per_benchmark_overrides=...)``.
    notes
        Free-form context (e.g. ``"smoke profile only - P8-2 carry-forward"``).
    """

    task_id: str
    runner: Callable[..., Any]
    smoke_factory: Callable[[], dict[str, Any]]
    metrics_keys: tuple[str, ...]
    result_adapter: Callable[[Any], dict[str, float]]
    runner_kwargs: dict[str, Any] = field(default_factory=dict)
    tolerance_pct: float = 10.0
    notes: str = ""

    def __post_init__(self) -> None:
        if not callable(self.runner):
            raise TypeError(
                f"BenchmarkSpec.runner for {self.task_id!r} must be callable, "
                f"got {type(self.runner).__name__}."
            )
        if not callable(self.smoke_factory):
            raise TypeError(f"BenchmarkSpec.smoke_factory for {self.task_id!r} must be callable.")
        if not callable(self.result_adapter):
            raise TypeError(f"BenchmarkSpec.result_adapter for {self.task_id!r} must be callable.")
        if not isinstance(self.metrics_keys, tuple) or not self.metrics_keys:
            raise ValueError(
                f"BenchmarkSpec.metrics_keys for {self.task_id!r} must be a "
                f"non-empty tuple of metric names."
            )
        for key in self.metrics_keys:
            if not isinstance(key, str) or not key:
                raise ValueError(
                    f"BenchmarkSpec.metrics_keys for {self.task_id!r} must contain "
                    f"non-empty strings; got {key!r}."
                )


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class BenchmarkRegistry:
    """Frozen registry of the nine Phase 10 public benchmark runners."""

    def __init__(self, specs: tuple[BenchmarkSpec, ...]) -> None:
        seen: set[str] = set()
        for spec in specs:
            if spec.task_id in seen:
                raise ValueError(f"Duplicate task_id in registry: {spec.task_id!r}")
            seen.add(spec.task_id)
        self._specs: tuple[BenchmarkSpec, ...] = tuple(specs)
        self._by_id: dict[str, BenchmarkSpec] = {s.task_id: s for s in self._specs}

    @classmethod
    def default(cls) -> BenchmarkRegistry:
        """Return the canonical registry covering P10-1 .. P10-9."""

        return cls(_default_specs())

    def specs(self) -> tuple[BenchmarkSpec, ...]:
        """Return the registry's specs in canonical order."""

        return self._specs

    def task_ids(self) -> tuple[str, ...]:
        """Return the registered task ids in canonical order."""

        return tuple(s.task_id for s in self._specs)

    def __getitem__(self, task_id: str) -> BenchmarkSpec:
        try:
            return self._by_id[task_id]
        except KeyError as exc:
            raise KeyError(
                f"task_id {task_id!r} not in registry; known ids: {sorted(self._by_id)}"
            ) from exc

    def __iter__(self) -> Iterator[BenchmarkSpec]:
        return iter(self._specs)

    def __len__(self) -> int:
        return len(self._specs)

    def __contains__(self, task_id: object) -> bool:
        return task_id in self._by_id


# ---------------------------------------------------------------------------
# Smoke runner (used by baseline regen + AC tests)
# ---------------------------------------------------------------------------


def run_smoke_registry(
    registry: BenchmarkRegistry | None = None,
    *,
    tmp_path: Path | None = None,
) -> dict[str, dict[str, float]]:
    """Run every spec's runner under its smoke profile.

    For each spec, the smoke kwargs are produced by ``smoke_factory()``,
    merged with ``runner_kwargs`` (so callers can inject e.g. a per-run
    ``tmp_path`` for runners that compile Taichi modules), the runner is
    timed, and the configured ``metrics_keys`` are extracted via
    ``result_adapter``. ``wallclock_s`` is always recorded.

    Parameters
    ----------
    registry
        Defaults to :meth:`BenchmarkRegistry.default`.
    tmp_path
        Optional per-call ``tmp_path`` injected into runners that need it
        (currently only P10-8 Notched bar). Ignored by other specs.

    Returns
    -------
    dict
        ``{task_id: {metric: float, ..., "wallclock_s": float}}``.
    """

    registry = registry or BenchmarkRegistry.default()
    out: dict[str, dict[str, float]] = {}
    for spec in registry.specs():
        kwargs = dict(spec.smoke_factory())
        kwargs.update(spec.runner_kwargs)
        if tmp_path is not None and "tmp_path" in _runner_signature_kwargs(spec.runner):
            kwargs.setdefault("tmp_path", tmp_path)
        t0 = time.perf_counter()
        result = spec.runner(**kwargs)
        wallclock = float(time.perf_counter() - t0)
        metrics = spec.result_adapter(result)
        # Ensure every advertised metric is present and finite.
        record: dict[str, float] = {}
        for key in spec.metrics_keys:
            if key not in metrics:
                raise KeyError(
                    f"Spec {spec.task_id!r} result_adapter did not return "
                    f"required metric {key!r}; got keys={sorted(metrics)}."
                )
            value = float(metrics[key])
            if not np.isfinite(value):
                raise ValueError(
                    f"Spec {spec.task_id!r} produced non-finite metric {key!r}={value!r}."
                )
            record[key] = value
        record["wallclock_s"] = wallclock
        out[spec.task_id] = record
    return out


def _runner_signature_kwargs(fn: Callable[..., Any]) -> set[str]:
    import inspect

    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):
        return set()
    return set(sig.parameters)


# ---------------------------------------------------------------------------
# Result adapters (one per runner family)
# ---------------------------------------------------------------------------


def _benchmark_result_adapter(*keys: str) -> Callable[[BenchmarkResult], dict[str, float]]:
    """Build an adapter that pulls scalar floats from ``BenchmarkResult.extras``."""

    def adapter(result: BenchmarkResult) -> dict[str, float]:
        out: dict[str, float] = {}
        extras = result.extras
        for key in keys:
            if key == "newton_iters":
                out[key] = float(result.newton_iters)
                continue
            if key not in extras:
                raise KeyError(
                    f"BenchmarkResult.extras missing key {key!r}; available keys: {sorted(extras)}."
                )
            out[key] = float(extras[key])
        return out

    return adapter


def _mms_matrix_adapter(result: MMSMatrixResult) -> dict[str, float]:
    """Pack measured L2/H1 convergence rates per case into a flat dict."""

    out: dict[str, float] = {}
    for entry in result.entries:
        case_id = entry.case.id  # e.g. "hex8:svk:elastic_regime_interpolation"
        slug = case_id.replace(":", "_")
        out[f"l2_rate_{slug}"] = float(entry.l2_check.measured_rate)
        out[f"h1_rate_{slug}"] = float(entry.h1_check.measured_rate)
    return out


# ---------------------------------------------------------------------------
# Per-runner smoke factories
# ---------------------------------------------------------------------------


# P10-1: cheap Hex8 SVK MMS matrix at three coarse levels.
_P10_1_SMOKE_CASES = (MMSMatrixCase("hex8", "svk", expected_l2_rate=2.0, expected_h1_rate=1.0),)
_P10_1_SMOKE_LEVELS = (3, 4, 5)
_P10_1_METRICS = (
    "l2_rate_hex8_svk_elastic_regime_interpolation",
    "h1_rate_hex8_svk_elastic_regime_interpolation",
)


def _p10_1_factory() -> dict[str, Any]:
    return {"cases": _P10_1_SMOKE_CASES, "mesh_levels": _P10_1_SMOKE_LEVELS}


def _p10_2_factory() -> dict[str, Any]:
    return {"params": CantileverParameters.smoke()}


def _p10_3_factory() -> dict[str, Any]:
    # Defaults are smoke-sized (2x2x1 mesh, 10 steps, prescribed-displacement
    # smoke path because no `solve_plastic` injection is provided).
    return {"params": CookMembraneParameters()}


def _p10_4_factory() -> dict[str, Any]:
    # Thick cylinder needs an injected NumPy elastic Newton-CG solver. The
    # `tests.ref.ref_hex8_elastic.solve_elastic` helper is the canonical
    # injection: importing it lazily keeps the registry usable inside pytest
    # (testpaths puts `packages/mechdsl-core/tests` on sys.path) without
    # turning it into a hard runtime dep of the production package.
    from tests.ref.ref_hex8_elastic import solve_elastic

    return {
        "r_inner": 1.0,
        "r_outer": 2.0,
        "height": 0.1,
        "nr": 4,
        "ntheta": 4,
        "nz": 1,
        "pressure": 10.0,
        "E": 200e3,
        "nu": 0.3,
        "solve_elastic": solve_elastic,
        "sample_radii": np.array([1.25, 1.5, 1.75]),
        "tol": 1e-6,
        "max_iter": 30,
    }


def _p10_5_factory() -> dict[str, Any]:
    return {
        "params": PlateWithHoleParameters(
            element_type="hex8",
            n_radial=4,
            n_theta=8,
            n_z=1,
            newton_max_iter=20,
        )
    }


def _p10_6_factory() -> dict[str, Any]:
    # Defaults trigger the prescribed-displacement smoke path inside
    # run_necking_bar_benchmark (no ref-solver injections supplied).
    return {"params": NeckingBarParameters()}


def _p10_7_factory() -> dict[str, Any]:
    # P8-2 carry-forward: smoke profile only — never `nightly()`.
    return {"params": TaylorImpactParameters.smoke()}


def _p10_8_factory() -> dict[str, Any]:
    # Tiny mesh + 2 load steps to cap the Taichi compile + solve cost.
    # `tmp_path` is provided by run_smoke_registry through its tmp_path arg.
    mesh = build_notched_bar_mesh(
        n_len=4,
        n_height=2,
        n_thick=1,
        L=4.0,
        H=2.0,
        T=1.0,
        notch_depth=0.5,
        notch_halfwidth=0.5,
    )
    material = {
        "E": 200.0e3,
        "nu": 0.3,
        "sigma_y0": 200.0,
        "K": 100.0,
        "n": 1.0,
        "S_d": 2.0,
        "s_d": 1.0,
        "eps_D": 0.0,
        "D_crit": 0.95,
    }
    return {
        "mesh": mesh,
        "material_params": material,
        "total_displacement": 0.02,
        "n_steps": 2,
        "newton_tol": 1e-6,
        "newton_max_iter": 20,
    }


def _p10_9_factory() -> dict[str, Any]:
    # HGO uniaxial smoke: 1-element mesh, single mild stretch, fiber along x.
    # Lazy import of the NumPy reference solver mirrors the P10-4 strategy.
    from tests.ref.ref_hex8_hgo import assemble_internal_force, solve_hgo

    return {
        "stretch_lambda": 1.05,
        "fiber_dir": np.array([1.0, 0.0, 0.0]),
        "material": HGOMaterial(
            mu=7.64,
            k1=996.6,
            k2=524.6,
            kappa=7.64e3,
            fiber_dispersion=0.226,
        ),
        "solve_hgo": solve_hgo,
        "assemble_internal_force": assemble_internal_force,
        "Lx": 1.0,
        "Ly": 1.0,
        "Lz": 1.0,
        "nx": 1,
        "ny": 1,
        "nz": 1,
        "load_axis": 0,
        "n_load_steps": 2,
        "tol": 1e-6,
        "max_iter": 20,
    }


# ---------------------------------------------------------------------------
# Default spec list
# ---------------------------------------------------------------------------


def _default_specs() -> tuple[BenchmarkSpec, ...]:
    return (
        BenchmarkSpec(
            task_id="P10-1",
            runner=run_mms_convergence_matrix,
            smoke_factory=_p10_1_factory,
            metrics_keys=_P10_1_METRICS,
            result_adapter=_mms_matrix_adapter,
            tolerance_pct=10.0,
            notes=(
                "MMS convergence matrix — smoke restricts to Hex8/SVK "
                "elastic-regime interpolation at three coarse mesh levels."
            ),
        ),
        BenchmarkSpec(
            task_id="P10-2",
            runner=run_cantilever_benchmark,
            smoke_factory=_p10_2_factory,
            metrics_keys=("tip_displacement", "relative_error", "newton_iters"),
            result_adapter=_benchmark_result_adapter(
                "tip_displacement", "relative_error", "newton_iters"
            ),
            tolerance_pct=10.0,
            notes="Cantilever — smoke uses CantileverParameters.smoke().",
        ),
        BenchmarkSpec(
            task_id="P10-3",
            runner=run_cook_membrane_benchmark,
            smoke_factory=_p10_3_factory,
            metrics_keys=("tip_uy", "newton_iters"),
            result_adapter=_benchmark_result_adapter("tip_uy", "newton_iters"),
            tolerance_pct=10.0,
            notes="Cook membrane — prescribed-displacement smoke path (no ref injection).",
        ),
        BenchmarkSpec(
            task_id="P10-4",
            runner=run_thick_cylinder_benchmark,
            smoke_factory=_p10_4_factory,
            metrics_keys=("max_u_r_rel_err", "max_sigma_tt_rel_err", "newton_iters"),
            result_adapter=_thick_cylinder_adapter,
            tolerance_pct=10.0,
            notes=(
                "Thick cylinder — coarse 4x4x1 mesh; injects "
                "tests.ref.ref_hex8_elastic.solve_elastic lazily."
            ),
        ),
        BenchmarkSpec(
            task_id="P10-5",
            runner=run_plate_with_hole_benchmark,
            smoke_factory=_p10_5_factory,
            metrics_keys=("k_t", "relative_error", "newton_iters"),
            result_adapter=_benchmark_result_adapter("k_t", "relative_error", "newton_iters"),
            tolerance_pct=15.0,
            notes="Plate-with-hole — Hex8, coarse 4x8x1 mesh.",
        ),
        BenchmarkSpec(
            task_id="P10-6",
            runner=run_necking_bar_benchmark,
            smoke_factory=_p10_6_factory,
            metrics_keys=("max_alpha", "force_norm", "newton_iters"),
            result_adapter=_benchmark_result_adapter("max_alpha", "force_norm", "newton_iters"),
            tolerance_pct=10.0,
            notes="Necking bar — prescribed-displacement smoke path (no ref injection).",
        ),
        BenchmarkSpec(
            task_id="P10-7",
            runner=run_taylor_impact_benchmark,
            smoke_factory=_p10_7_factory,
            metrics_keys=("final_length", "mushroom_radius", "peak_peeq"),
            result_adapter=_benchmark_result_adapter(
                "final_length", "mushroom_radius", "peak_peeq"
            ),
            tolerance_pct=10.0,
            notes=(
                "Taylor impact — smoke profile only (P8-2 carry-forward: nightly() "
                "overruns JC return-map iter budget; long-horizon PEEQ is unphysical)."
            ),
        ),
        BenchmarkSpec(
            task_id="P10-8",
            runner=run_notched_bar_benchmark,
            smoke_factory=_p10_8_factory,
            metrics_keys=("max_damage", "peak_load", "newton_iters"),
            result_adapter=_notched_bar_adapter,
            tolerance_pct=15.0,
            notes=(
                "Notched bar — coarse 4x2x1 mesh + 2 steps; Taichi JIT compile dominates "
                "wallclock (slow even at smoke). Requires per-run tmp_path."
            ),
        ),
        BenchmarkSpec(
            task_id="P10-9",
            runner=run_hgo_uniaxial,
            smoke_factory=_p10_9_factory,
            metrics_keys=("P_axial_fem", "P_axial_analytical", "rel_err"),
            result_adapter=_benchmark_result_adapter(
                "P_axial_fem", "P_axial_analytical", "rel_err"
            ),
            tolerance_pct=10.0,
            notes=(
                "HGO uniaxial — 1-element strip, lambda=1.05; injects "
                "tests.ref.ref_hex8_hgo helpers lazily."
            ),
        ),
    )


# ---------------------------------------------------------------------------
# Specialised result adapters (post-process arrays into scalars)
# ---------------------------------------------------------------------------


def _thick_cylinder_adapter(result: BenchmarkResult) -> dict[str, float]:
    extras = result.extras
    u_r_rel_err = np.asarray(extras["u_r_rel_err"], dtype=np.float64)
    sigma_tt_rel_err = np.asarray(extras["sigma_tt_rel_err"], dtype=np.float64)
    return {
        "max_u_r_rel_err": float(np.max(u_r_rel_err)),
        "max_sigma_tt_rel_err": float(np.max(sigma_tt_rel_err)),
        "newton_iters": float(result.newton_iters),
    }


def _notched_bar_adapter(result: BenchmarkResult) -> dict[str, float]:
    extras = result.extras
    load_history = np.asarray(extras["load_history"], dtype=np.float64)
    return {
        "max_damage": float(extras["max_damage"]),
        "peak_load": float(np.max(np.abs(load_history))),
        "newton_iters": float(result.newton_iters),
    }
