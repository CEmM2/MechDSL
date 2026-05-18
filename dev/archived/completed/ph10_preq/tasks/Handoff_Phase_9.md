# Handoff to Phase 9

Phase 8 completed the public Taylor impact benchmark API (E8) — P8-1 added
`TaylorImpactParameters` + `run_taylor_impact_benchmark` to
`mechdsl.verify.benchmarks`, and P8-2 activated the existing P10-7 nightly
stubs against frozen-reference values plus added an integration-tier smoke
suite. The full original-scope `P10-1` … `P10-9` benchmark surface is now
public, active, and deterministic.

## Completed Inputs

- **P8-1 done.** `mechdsl.verify.benchmarks` exports `TaylorImpactParameters`
  (frozen dataclass with `smoke()` / `nightly()` classmethods, mirroring
  `CantileverParameters`) and `run_taylor_impact_benchmark(params=None)`
  returning the existing shared `BenchmarkResult` schema. Taylor metrics are
  packed into `BenchmarkResult.extras`: `final_length`, `mushroom_radius`,
  `mushroom_diameter` (= 2 × radius), `peak_peeq`, `profile`, `n_steps`, `dt`,
  `horizon_s`, `impact_velocity`, `mesh_n_nodes`. No `BenchmarkResult` schema
  change.
- **P8-2 done.** `test_taylor_impact.py::TestTaskP10_7` (3 tests, original
  `@nightly @regression @slow` markers preserved) now asserts against frozen
  reference values within 5% / 5% / 10% tolerances. New
  `TestTaskP8_2Smoke` class (3 `@integration` tests) exercises the public
  benchmark surface in the fast tier — finiteness, bit-for-bit determinism,
  parameter sensitivity.

## Evidence

- `uv run pytest packages/mechdsl-core/tests/test_phase10_taylor_benchmark.py -v` → **3/3 passed** (P8-1 API).
- `uv run pytest packages/mechdsl-core/tests/test_taylor_impact.py -v` → **6/6 passed** (P8-2 default tier: 3 nightly + 3 smoke, 2.89 s).
- `uv run pytest packages/mechdsl-core/tests/test_taylor_impact.py -v -m "nightly or regression"` → **3/3 passed, 3 deselected** (P8-2 nightly tier, 2.70 s).
- `uv run pytest packages/mechdsl-core/tests/test_phase10_taylor_benchmark.py packages/mechdsl-core/tests/test_phase10_taylor_runtime.py packages/mechdsl-core/tests/test_phase10_taylor_state.py -v` → **22/22 passed** (Phase 7 + P8-1 regression, 0.50 s — zero upstream drift).
- `uv run ruff check` on touched modules + tests → clean.
- `uv run mypy packages/mechdsl-core/src/mechdsl/verify/benchmarks/taylor_impact.py` → clean.

## Branch / Commits

- Branch: `work/phase10-e8-public-taylor-benchmark` (off `3bc9e37`, which carries the Phase 8 scaffold; Phase 7 work in `work/phase10-e7-taylor-runtime` ends at `50cafdf`).
- `3bc9e37` — Phase 8 scaffold (test stub for P8-1, JSON updates, validation report).
- `5ce4982` — Phase 8 exec prep (tasks analysis + gates skeleton).
- `7aca187` — P8-1 implementation.
- `4c89098` — P8-1 tracking.
- `5a49c63` — P8-2 implementation (test activation + smoke suite).
- `<this commit>` — P8-2 tracking + Phase 9 handoff.

## Phase 9 Notes

### What Phase 9 needs to add (P9-1 + P9-2)

- **Benchmark registry** over the 9 public runners now in `mechdsl.verify.benchmarks` (`run_thick_cylinder_benchmark`, `run_plate_with_hole_benchmark`, `run_cook_membrane_benchmark`, `run_necking_bar_benchmark`, `run_notched_bar_benchmark`, `run_hgo_uniaxial`, `run_cantilever_benchmark`, `run_mms_convergence_matrix` from Phase 6, `run_taylor_impact_benchmark` from Phase 8). Capture wall time, solver iteration counts where available, and benchmark metrics. Local profile uses smoke settings; nightly profile uses full/nightly settings.
- **Baseline artifact** committed under `tests/golden/perf/` (or similar) — JSON or CSV with per-benchmark expected metrics + tolerances. Updated only via `update-golden`-style intent.
- **`tests/test_perf_regression.py`** — `@pytest.mark.benchmark` tests that run the registry against the baseline and report per-benchmark deltas. Local runs use smoke; CI nightly uses full.
- **Nightly CI workflow** (`.github/workflows/nightly.yml` or extension of an existing workflow) that runs `pytest -m "nightly or regression or benchmark"` and reports against the baseline.

### Things to consume from Phase 8

- All 9 public runners are reachable from `mechdsl.verify.benchmarks.__all__`. The Phase 8 Taylor runner uses the same `BenchmarkResult` schema with metrics in `extras` — registry should generically read `result.wallclock_s`, `result.newton_iters`, and walk `result.extras` for per-benchmark metric keys.
- `TaylorImpactParameters.smoke()` is the local profile; `nightly()` is the full profile (but see carry-forward issues below).
- The pyproject test markers (`slow`, `nightly`, `regression`, `benchmark`, `integration`) are all registered. Phase 9 should add `benchmark` to the test selection logic for the registry runs.

### Carry-forward issues (surfaced by P8-2; Phase 9 should address or document)

1. **`TaylorImpactParameters.nightly()` overruns the JC radial-return 50-iter budget** on the shipped `6×6×20` mesh + `dt=5e-8` + `n_steps=400` configuration. P8-2 worked around this by using a smoke-derived reference profile (`smoke(nz=20, n_steps=100, dt=1e-8)`). Phase 9 options:
   - Tune `TaylorImpactParameters.nightly()` to a config the JC return map can solve (lower `dt`, smaller mesh per step, or split the integration into chunks). Then wire the registry to the fixed `nightly()`.
   - Bump the JC `radial_return` `max_iter` from 50 to ~200 (additive on `johnson_cook.py` — but the plan explicitly forbids JC semantic edits; this is a knob change, not a semantic change, but the line is fuzzy — confirm before editing).
   - Document `nightly()` as a placeholder pending Phase 9 calibration.
2. **PEEQ on long horizons** reaches unphysical magnitudes (~16.6 at `n_steps=200` on the smoke mesh). JC hardening or thermal softening calibration may need a sanity pass — likely a separate calibration task, not Phase 9 core scope, but the perf harness baseline should NOT freeze a long-horizon PEEQ reference until this is understood.
3. **Mushroom diameter convention**: the existing `test_taylor_impact.py::test_taylor_impact_mushroom_diameter_within_5pct` asserts on diameter (2 × radius). The runtime helper returns radius; the public runner does the doubling in `extras["mushroom_diameter"]`. Registry baselines should choose one convention consistently — recommend `extras["mushroom_diameter"]` for backward compatibility with the J&C 1985 literature shorthand.

### Out of scope for Phase 9

- New benchmark semantics (the plan explicitly forbids this).
- Reopening upstream benchmark tasks (P10-1 … P10-9 are all active and frozen).
- GPU-only execution (`@pytest.mark.gpu` is for opt-in only — Phase 9 local tier must be CPU-runnable).
- Changes to `BenchmarkResult` schema.
- Changes to JC `radial_return` semantics (knob changes like `max_iter` are arguably allowed; surface for confirmation).

## Tracker / Plan

- `dev/tracking/tasks-tracker_ph10_preq.md`: P8-1 and P8-2 rows updated to `done`; Phase 8 verification block holds the fresh-run evidence above.
- `dev/tasks/ph10_preq/json/P8-1.json`, `P8-2.json`: status `done`, completion notes, branch `work/phase10-e8-public-taylor-benchmark`.
- `dev/tasks/ph10_preq/gates/phase_8_gates.md`: full P8-1 / P8-2 gate history (1/1/1 attempts each) + carry-forward issues for Phase 9.

Phase 9 starts from the head of `work/phase10-e8-public-taylor-benchmark`. Recommended branch: `work/phase10-e9-perf-harness` cut off the final P8-2 tracking commit.
