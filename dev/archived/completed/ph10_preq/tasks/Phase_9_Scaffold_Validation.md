# Phase 9 Scaffold Validation

| Task ID | Title | Missing / Incomplete Fields | Scaffold Action |
|---------|-------|-----------------------------|-----------------|
| P9-1 | Benchmark registry and local baselines | `test_artifacts`, `verification_commands` were placeholder strings | auto-filled |
| P9-2 | Nightly CI and performance regression harness | `test_artifacts`, `verification_commands` were placeholder strings | auto-filled |

## Scaffold Summary

| Metric | Value |
|--------|-------|
| Tasks scaffolded | 2 |
| Test cases assessed | 6 |
| Cases covered by existing tests | 0 |
| Cases partially covered (stubs already exist) | 3 |
| Cases with no existing tests (new stubs generated) | 3 |
| New stub files created | 1 |
| Total new stubs generated | 3 |
| Tasks fully covered by existing tests (no stub needed) | 0 |
| Tasks needing human review | 0 |
| Auto-filled fields | `test_artifacts`, `verification_commands` |

## Existing Test Coverage Found

| Task ID | Test case | Existing test file | Function | Coverage |
|---------|-----------|-------------------|----------|----------|
| P9-2 | local smoke perf regression | `packages/mechdsl-core/tests/test_perf_regression.py` | `TestTaskP10_10::test_regression_script_detects_injected_slowdown` | partial — stub at `@nightly @regression`, currently `pytest.skip`; P9-2 activates it. May need to relax marker to also run a smoke variant in the default tier. |
| P9-2 | nightly workflow includes full benchmark command | `packages/mechdsl-core/tests/test_perf_regression.py` | `TestTaskP10_10::test_nightly_workflow_runs_end_to_end` | partial — same posture; P9-2 activates against the new `.github/workflows/nightly.yml` |
| P9-2 | baseline failure threshold reporting | `packages/mechdsl-core/tests/test_perf_regression.py` | `TestTaskP10_10::test_all_p10_tests_collected_under_nightly_marker` | partial — current stub is "all p10 tests carry @nightly"; this is a *different* check than baseline-threshold reporting. P9-2 should keep the marker-coverage stub AND add (or rename to) a baseline-threshold test. |
| P9-1 cross-check | runtime composition | `test_phase10_taylor_benchmark.py`, `test_phase10_taylor_runtime.py`, `test_phase10_taylor_state.py` | full P8-1 + Phase 7 suites | covered (22/22 must remain green as P9 regression guard) |

The existing `test_perf_regression.py` was created during PLAN-B P10-10 scaffolding and was stubbed out pending the registry that Phase 9 now builds. P9-2 owns activating its three stubs.

## Generated Stubs

| Task ID | Stub file | Test function | Acceptance criterion covered |
|---------|-----------|---------------|------------------------------|
| P9-1 | `packages/mechdsl-core/tests/test_phase10_benchmark_registry.py` | `TestTaskP9_1::test_registry_includes_all_benchmark_runners` | AC-1 (registry covers P10-1..P10-9) |
| P9-1 | `packages/mechdsl-core/tests/test_phase10_benchmark_registry.py` | `TestTaskP9_1::test_smoke_baseline_load` | AC-2 (local smoke baseline loads, no GPU) |
| P9-1 | `packages/mechdsl-core/tests/test_phase10_benchmark_registry.py` | `TestTaskP9_1::test_metric_delta_reporting` | AC-3 (per-benchmark delta reporting with sign + tolerance flag) |

## Tasks Needing Human Review Before Execute

| Task ID | Title | Field | Issue |
|---------|-------|-------|-------|
| - | - | - | - |

## Notes for the P9 Implementer

- **Registry public surface lives in a new package**: `mechdsl.verify.perf` (parallel to `mechdsl.verify.benchmarks`). Keep the perf module additive; do not edit `BenchmarkResult` (CRITICAL impact).
- **Baseline file convention**: `packages/mechdsl-core/tests/golden/perf/baseline_smoke.json` — under the existing `golden/` tree to inherit the project's golden-file regression discipline ("Golden-file updates require explicit intent — never auto-update."). Document a regen recipe in the file's header or a sibling `README.md`.
- **Smoke vs nightly tier split**: P9-1's tests are pure `@regression` (fast tier — registry completeness, baseline loadability, delta-report shape are unit/regression checks). P9-2 keeps the existing `@nightly @regression` markers on the heavy end-to-end tests and may add a fast `@regression` smoke layer that exercises the same `compare_to_baseline` pipeline on a tiny mesh.
- **Carry-forward from Phase 8 P8-2** (two flagged calibration issues):
  1. `TaylorImpactParameters.nightly()` overruns the JC `radial_return` 50-iter budget. P9-1's smoke baseline should NOT call `nightly()` for Taylor; use a smoke-derived profile (the same pattern P8-2 used: `smoke(nz=20, n_steps=100, dt=1e-8)`). Document in the baseline regen recipe.
  2. PEEQ on long horizons is unphysical. P9-1's baseline must use a horizon ≤ ~1 µs for Taylor or this metric will be misleading. The baseline schema may want to skip storing PEEQ for Taylor, or store it with a "calibration-pending" sentinel.
- **Nightly CI workflow**: a new `.github/workflows/nightly.yml` triggered on schedule (cron) and manual dispatch. Should run `uv run pytest packages/mechdsl-core/tests/ -m "nightly or regression" --tb=short -q`. Can mirror the structure of the existing `ci.yml` job blocks. Include a job that runs `compare.py` against the committed baseline and fails on the documented threshold (default ~10%).
- **No GPU in local tests**: AC-3 explicitly forbids GPU dependencies in the local tier. Any benchmark that needs GPU should be `@gpu` marked (not registered for the local smoke registry) or use a CPU fallback path.

## GitHub Issue Mirroring

Skipped. `dev/tasks/ph10_preq/github_issue_map.json` does not exist; same posture as Phases 7-8.
