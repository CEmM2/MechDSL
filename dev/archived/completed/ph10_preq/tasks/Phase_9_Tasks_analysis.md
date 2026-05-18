# Phase 9 Tasks Analysis

Plan: `dev/plans/ph10_preq.md` — Phase E9 Performance And Nightly Harness (terminal phase)
Branch: `work/phase10-e9-perf-harness` (off `2991845`, which is Phase 8 close + Phase 9 scaffold)

| Task ID | Title | Complexity (1-5) | Risk (1-5) | Combined Score | Blocked By | Blocks |
|---------|-------|-----------------|------------|----------------|------------|--------|
| P9-1 | Benchmark registry and local baselines | 4 | 3 | 7 | P3-1, P3-2, P5-2, P6-2, P8-2 (all done) | P9-2 |
| P9-2 | Nightly CI and performance regression harness | 3 | 3 | 6 | P9-1 | (terminal) |

## Model Assignment (per Step 2 rules)

- **P9-1**: combined 7 → **Opus 4.6**.
- **P9-2**: combined 6 → **Sonnet 4.6 or Opus 4.6** (Sonnet preferred — workflow + test-activation work, not heavy new physics).

For consistency across this phase and given its terminal status, dispatching both with **Opus** for stability.

## Complexity Justification

- **P9-1**: New `mechdsl.verify.perf` package with `BenchmarkRegistry`, `BenchmarkSpec`, `load_smoke_baseline`, `compare_to_baseline`, `run_smoke_registry`. Requires walking the 9 public runners with a uniform interface (each runner takes a different parameter dataclass — registry must hide that variance). Generates a baseline JSON artifact under `tests/golden/perf/` covering all 9 benchmarks. Three new active tests for completeness, baseline load, and delta reporting.
- **P9-2**: New GitHub Actions workflow at `.github/workflows/nightly.yml` (cron + manual dispatch). Activates the three existing `test_perf_regression.py` stubs against the P9-1 surface. Lower complexity than P9-1 — most of the heavy lifting is in the workflow YAML and the registry plumbing already done in P9-1.

## Risk Justification

- **P9-1 risk 3**: Touching the 9 public runners means the registry calls into every Phase 10 surface. Wrong default params → registry runs that take minutes or fail mid-baseline-generation. Mitigation: each runner already exposes `smoke()` / equivalent fast profile; the registry only invokes those. Baseline file is committed under `golden/perf/` so it inherits the project's "never auto-update" golden-file discipline.
- **P9-2 risk 3**: CI workflow changes are visible to every contributor and can break PR runs if misconfigured. Mitigation: add the nightly workflow as a separate file (`nightly.yml`), do not modify `ci.yml` or `ci-backends.yml`; trigger only on cron/manual_dispatch (not `push`/`pull_request`).

## Execution Order

Sequential: **P9-1 → P9-2**. P9-2 wires P9-1's registry into nightly CI.

## Files Likely Touched (within phase scope)

- `packages/mechdsl-core/src/mechdsl/verify/perf/__init__.py` (NEW — primary, P9-1)
- `packages/mechdsl-core/src/mechdsl/verify/perf/registry.py` (NEW — P9-1)
- `packages/mechdsl-core/src/mechdsl/verify/perf/baseline.py` (NEW — P9-1, load + compare)
- `packages/mechdsl-core/tests/golden/perf/baseline_smoke.json` (NEW artifact — P9-1)
- `packages/mechdsl-core/tests/golden/perf/README.md` (NEW — P9-1, regen recipe)
- `packages/mechdsl-core/tests/test_phase10_benchmark_registry.py` (existing stub, fleshed out by P9-1)
- `.github/workflows/nightly.yml` (NEW — P9-2)
- `packages/mechdsl-core/tests/test_perf_regression.py` (existing stubs, activated by P9-2)

## Forbidden Edits (per plan + cumulative invariants)

- `BenchmarkResult` schema (CRITICAL impact)
- All Phase 1-8 runtime + benchmark module symbol semantics
- `JohnsonCookMaterial`, `radial_return`, FB hourglass force, reduced Hex8 element
- `build_context`, `ElementFactory`
- Existing CI workflows (`ci.yml`, `ci-backends.yml`) — new workflow goes in a new file
- `pyproject.toml` markers (already registered)

## Cross-Phase Failure-Pattern Lookup

Scan of `gates/phase_1_gates.md` … `gates/phase_8_gates.md`:

- **Phase 8 P8-2 carry-forward (active)**: (1) `TaylorImpactParameters.nightly()` overruns JC `radial_return` 50-iter budget on the shipped 6×6×20 mesh; (2) PEEQ on long horizons (~16.6 at n_steps=200) is unphysical. P9-1's smoke baseline must use the smoke-derived Taylor profile (e.g. `smoke(nz=20, n_steps=100, dt=1e-8)` from P8-2's reference) and a horizon ≤ ~1 µs to keep PEEQ physical. **Do NOT call `TaylorImpactParameters.nightly()` from the registry until that calibration is fixed.**
- **Phase 7 P7-2 (`physics_error`)**: dt sizing must respect element wave-traversal time. Same rule applies to any benchmark in the registry that integrates explicit dynamics (only Taylor at present, but documented for future runners).
- **Phase 6 P6-1 (`physics_error`)**: too-coarse mesh refinement under-measured asymptotic rates. The MMS matrix `run_mms_convergence_matrix` baseline must capture rate-fitting metrics, not just a single-mesh wallclock — convergence is the meaningful metric for that runner.
- No `integration_break` patterns in earlier phases. Public-API surfaces are stable; the main regression risk is `__init__.py` export drift, which the registry test will catch.

## Phase 9 Implementer Notes (from handoff + scaffold validation)

- **Registry public surface**: new `mechdsl.verify.perf` package, additive — do not extend `mechdsl.verify.benchmarks`. Each `BenchmarkSpec` carries `task_id` (e.g. "P10-7"), `runner` callable, `smoke_params` factory, `metrics_keys` tuple naming `extras` keys to compare, optional `notes` string. The registry walks specs to produce a uniform `{task_id: {metric_key: float, ..., wallclock_s: float}}` snapshot.
- **Baseline file**: `packages/mechdsl-core/tests/golden/perf/baseline_smoke.json` — JSON for human readability + diffability. Schema: `{"generated_on": "2026-04-26", "commit": "<sha>", "tasks": {"P10-1": {...}, ...}}`. Include a sibling `README.md` documenting the regen recipe (e.g. `uv run python -m mechdsl.verify.perf.regenerate_baseline`).
- **Tolerances**: default ±10% per the plan ("baseline comparison reports clear per-benchmark deltas"). Per-benchmark overrides allowed via `BenchmarkSpec.tolerance_pct` for benchmarks with intrinsically more variance (none expected at smoke sizes, but the knob should exist).
- **Nightly workflow** (`.github/workflows/nightly.yml`):
  - Trigger: `schedule: cron: "0 6 * * *"` (06:00 UTC daily) + `workflow_dispatch:`.
  - Jobs: install deps, run `uv run pytest packages/mechdsl-core/tests/ -m "nightly or regression" --tb=short -q`, then a `compare.py` step that reads the latest perf snapshot and exits non-zero on >10% regression. Mirror the structure of `ci.yml` job blocks.
  - Do NOT modify `ci.yml` or `ci-backends.yml`.
- **P9-2 stub renaming**: existing `test_perf_regression.py::test_all_p10_tests_collected_under_nightly_marker` covers a different concern (marker coverage) than the P9-2 AC-3 case "baseline failure threshold reporting". Keep the existing test (it's still useful — guards against future P10-N tests forgetting the `@nightly` mark) and ADD a fourth test for baseline-threshold reporting against the registry. The 3 stubs become 4 active tests, still all `@nightly @regression`.

## Plan Completion

P9-2 is the terminal task of `ph10_preq`. After it lands, the full original-scope **P10-1 … P10-10** is closed. There is no Phase 10 in `ph10_preq` (the plan tops out at E9 / Phase 9). The Phase 10 handoff written at the end of P9-2 should be a *project completion summary* rather than a "next phase" handoff — close the plan loop.
