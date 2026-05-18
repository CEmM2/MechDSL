# ph10_preq — Plan Completion Summary

**Plan:** `dev/plans/ph10_preq.md`
**Tracker:** `dev/tracking/tasks-tracker_ph10_preq.md`
**Closed:** 2026-04-26
**Final commit:** `11b1420` (Phase 9 P9-2) on `work/phase10-e9-perf-harness`

The full original-scope **P10-1 … P10-10** prerequisite track is complete. Every Phase 10 benchmark task has either an active public runner + nightly regression coverage or, where the plan rescoped, a documented carry-forward.

## Plan Map: Phases × Tasks × P10 Closures

| Plan phase | Tasks | P10 closure | Branch |
|---|---|---|---|
| Phase 1 (E1: Shared Mesh Utilities) | P1-1, P1-2 | enables P10-2/3/7 mesh prerequisites | `work/phase10-e1-mesh-utilities` |
| Phase 2 (E4: TL/UL J2 Solver) | P2-1, P2-2 | enables P10-3/6 plastic surfaces | `work/phase10-e4-j2-solver` |
| Phase 3 (E5: Cook + Necking) | P3-1, P3-2 | **P10-3** Cook membrane, **P10-6** necking bar | `work/phase10-e5-cook-necking` |
| Phase 4 (E2: Elastic Solver) | P4-1, P4-2 | enables P10-2 cantilever | `work/phase10-e2-elastic-solver` |
| Phase 5 (E3: Public Cantilever) | P5-1, P5-2 | **P10-2** cantilever | `work/phase10-e3-public-cantilever` |
| Phase 6 (E6: Generalized MMS) | P6-1, P6-2 | **P10-1** MMS convergence matrix | `work/phase10-e6-generalized-mms` |
| Phase 7 (E7: Taylor Runtime) | P7-1, P7-2 | enables P10-7 Taylor public runner | `work/phase10-e7-taylor-runtime` |
| Phase 8 (E8: Public Taylor) | P8-1, P8-2 | **P10-7** Taylor impact | `work/phase10-e8-public-taylor-benchmark` |
| Phase 9 (E9: Perf Harness) | P9-1, P9-2 | **P10-10** perf harness + nightly CI | `work/phase10-e9-perf-harness` |

P10-4 (thick cylinder), P10-5 (plate with hole), P10-8 (notched bar), P10-9 (HGO uniaxial) were already complete via PLAN-B before `ph10_preq` started; they are now also covered by the P9-1 registry + P9-2 nightly workflow.

## Public API Delivered

`mechdsl.verify.benchmarks` exports the 8 public benchmark runners + parameter dataclasses:
- `run_thick_cylinder_benchmark`, `run_plate_with_hole_benchmark` + `PlateWithHoleParameters`
- `run_cook_membrane_benchmark` + `CookMembraneParameters`
- `run_necking_bar_benchmark` + `NeckingBarParameters`
- `run_notched_bar_benchmark` + `NotchedBarMesh`, `build_notched_bar_mesh`
- `run_hgo_uniaxial` + `generate_strip_mesh`, `fiber_direction_field`, `hgo_analytical_uniaxial_stress`
- `run_cantilever_benchmark` + `CantileverParameters` (Phase 5)
- `run_taylor_impact_benchmark` + `TaylorImpactParameters` (Phase 8)

`mechdsl.verify.mms_matrix` exports the 9th runner + result types:
- `run_mms_convergence_matrix` + `MMSMatrixCase`, `MMSMatrixResult`, `MMSConvergenceEntry`, `default_mms_matrix_cases` (Phase 6)

`mechdsl.verify.perf` (new — Phase 9):
- `BenchmarkRegistry`, `BenchmarkSpec`, `run_smoke_registry`
- `MetricDelta`, `BenchmarkComparison`, `ComparisonReport` (JSON round-trip)
- `load_smoke_baseline`, `compare_to_baseline`
- CLI: `python -m mechdsl.verify.perf.run_compare`

`mechdsl.verify.benchmarks._taylor_runtime` (Phase 7 — internal but exported through `taylor_impact.py`):
- `ExplicitTaylorState`, `RigidWallSpec`
- `init_taylor_runtime`, `init_taylor_runtime_jc`, `explicit_step`, `explicit_step_jc`
- `apply_rigid_wall_contact`, `hourglass_energy_increment`
- `extract_equivalent_plastic_strain`, `final_length`, `mushroom_radius`

## Test Surface Delivered

| Test file | Tests | Coverage |
|---|---|---|
| `tests/test_phase10_mesh_utils.py` | 10 | P1-1, P1-2 |
| `tests/test_phase10_j2_solver.py` | 5 | P2-1, P2-2 |
| `tests/test_benchmarks_cook_membrane_matrix.py` | 5 | P3-1 |
| `tests/test_benchmarks_necking_bar_matrix.py` | 5 | P3-2 |
| `tests/test_phase10_elastic_solver.py` | 9 | P4-1, P4-2 |
| `tests/test_benchmarks_cantilever_matrix.py` | 15 | P5-1, P5-2 |
| `tests/test_mms_convergence_matrix.py` | 10 | P6-1, P6-2 |
| `tests/test_phase10_taylor_runtime.py` | 5 | P7-1 |
| `tests/test_phase10_taylor_state.py` | 14 | P7-2 |
| `tests/test_phase10_taylor_benchmark.py` | 3 | P8-1 (API smoke) |
| `tests/test_taylor_impact.py` | 6 | P8-2 (3 nightly + 3 smoke) |
| `tests/test_phase10_benchmark_registry.py` | 3 | P9-1 |
| `tests/test_perf_regression.py` | 4 | P9-2 (all `@nightly @regression`) |

## CI / Nightly Wiring

- `.github/workflows/ci.yml` — fast tier (existing, untouched). Excludes `slow / gpu / e2e`.
- `.github/workflows/ci-backends.yml` — backend matrix (existing, untouched).
- `.github/workflows/nightly.yml` — **NEW (Phase 9)**. Cron `0 6 * * *` + `workflow_dispatch`. Two jobs:
  - `nightly-tests`: `uv run pytest -m "nightly or regression" --tb=short -q`.
  - `perf-regression`: runs `python -m mechdsl.verify.perf.run_compare`, writes the `ComparisonReport` JSON as a workflow artifact, exits non-zero on >10% regression.

## Baseline Artifact

`packages/mechdsl-core/tests/golden/perf/baseline_smoke.json` — checked-in smoke baseline covering all 9 P10-1..P10-9 tasks. Total smoke wallclock ~12 s on the dev laptop. Regen recipe in sibling `README.md`. Inherits the project's golden-file discipline (regen requires explicit intent).

## Open Carry-Forwards (NOT blocking plan closure)

These are tracked here so a future maintenance task picks them up. None of them gate `ph10_preq` closure.

1. **`TaylorImpactParameters.nightly()` overruns the JC `radial_return` 50-iter budget** on the shipped 6×6×20 mesh + dt=5e-8 + n_steps=400. P8-2 worked around with a smoke-derived reference profile; P9-1 registry uses smoke only. *Fix path*: tune `nightly()` to a converging configuration (lower `dt`, smaller mesh per step, or split integration into chunks). Or raise the JC `radial_return` `max_iter` from 50 to ~200 (knob change, but the plan forbids JC semantic edits — confirm before editing). Or document `nightly()` as a placeholder pending tuning.
2. **PEEQ on long horizons (~16.6 at n_steps=200) is unphysical** on the smoke mesh. Suggests JC hardening / thermal softening calibration may need a sanity pass. Not in any baseline (Taylor baseline uses smoke profile only), so does not currently affect nightly regression. *Fix path*: separate calibration task; until then, do NOT extend the Taylor smoke horizon.
3. **`@nightly`-marked tests run in the default tier** (the project's `pyproject.toml` `addopts` excludes `slow / gpu / e2e` but not `nightly`). Impact is negligible — the four P9-2 perf-harness tests run in 0.18 s. *Fix path*: if strict tier separation is desired, add `not nightly` to `addopts` (would exclude every `@nightly` test from fast CI; check whether any other Phase 10 tests depend on running there).
4. **GitNexus CLI repo-disambiguation** — duplicate-named repos (one in `~/Github/Personal/MechDSL`, one in this conductor workspace) make `npx gitnexus impact --repo "MechDSL (/path/...)"` reject inputs with spaces and parens. Workaround: `Grep` fallback (used throughout this plan). *Fix path*: GitNexus CLI flag handling improvement.
5. **PLAN-B P10-10 stub premise drift** — the original PLAN-B P10-10 author asserted "all P10 tests carry @nightly" but the actual Phase 10 test corpus uses `@integration` for most files. P9-2 rescoped the test to assert what is actually load-bearing. Worth noting in any future plan-vs-reality reconciliation.

## Branch Topology

Each phase has its own `work/phase10-e<N>-<slug>` branch, off the previous phase's final commit:

```
main
 ↓
 ... (PLAN-B Phase 10 partial work)
  ↓
 e23035f (codex folder — last linear ancestor)
  ↓
work/phase10-e1-mesh-utilities ─→ ... ─→ work/phase10-e7-taylor-runtime (50cafdf)
                                                  ↓
                                  work/phase10-e8-public-taylor-benchmark (16e0df9)
                                                                    ↓
                                                 work/phase10-e9-perf-harness (11b1420 + tracking + this summary)
```

Each phase branch is suitable as the source of an independent PR against `origin/main`. Recommended order for review/merge: same as the execution order (E1 → E4 → E5 → E2 → E3 → E6 → E7 → E8 → E9).

## What's Next

`ph10_preq` is closed. Natural next steps (not specified by this plan):
- Open PRs for each Phase branch in execution order.
- After Phase 6 (MMS) and Phase 8 (Taylor) merge, the perf baseline will need one regen pass on `main` to capture the post-merge wallclocks (the committed baseline was generated on `f539cdf` — the baseline JSON's `commit` field documents this).
- Address the open carry-forwards above as separate maintenance tasks.
- Future Phase 11+ can plan against the now-stable `mechdsl.verify.benchmarks` + `mechdsl.verify.perf` surfaces.
