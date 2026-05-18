# Phase 9 Gate History

Generated during ExecPhase execution.
Plan: `dev/plans/ph10_preq.md`
Branch: `work/phase10-e9-perf-harness`

Phase scope: Performance + nightly harness (E9, terminal phase) —
benchmark registry over the 9 public runners + local smoke baseline
artifact + nightly CI workflow + activation of `test_perf_regression.py`
stubs. Closes P10-10 and the full ph10_preq plan.

Cross-phase warnings carried forward:
- Phase 8 P8-2 (active): `TaylorImpactParameters.nightly()` overruns JC
  radial_return 50-iter budget on 6×6×20 mesh — registry MUST use
  smoke-derived Taylor profile (`smoke(nz=20, n_steps=100, dt=1e-8)`).
- Phase 8 P8-2 (active): PEEQ on long horizons unphysical — Taylor
  baseline horizon must be ≤ ~1 µs to keep PEEQ physical.
- Phase 7 P7-2: dt must respect wave-traversal time for explicit runners.
- Phase 6 P6-1: convergence-rate runners (MMS matrix) need rate-fitting
  metrics, not single-mesh wallclock.

---

## P9-1: Benchmark registry and local baselines

**Issue:** _none — github_issue_map.json absent_
**Started:** 2026-04-26
**Completed:** 2026-04-26
**Branch:** `work/phase10-e9-perf-harness`

### Gate A — Spec Compliance

#### Attempt 1 — PASS

The implementer added a new `mechdsl.verify.perf` package with `BenchmarkSpec`, `BenchmarkRegistry`, `run_smoke_registry`, `MetricDelta`, `BenchmarkComparison`, `ComparisonReport` (with full JSON round-trip), `load_smoke_baseline`, and `compare_to_baseline`. `BenchmarkRegistry.default()` catalogues all 9 P10-1..P10-9 public runners with smoke factories, metric extractors, and per-benchmark tolerances. The committed baseline at `packages/mechdsl-core/tests/golden/perf/baseline_smoke.json` covers every expected task with finite metrics + wallclock; sibling `README.md` documents the regen recipe. P10-7 Taylor uses `smoke()` only per the Phase 8 P8-2 carry-forward; P10-1 MMS uses Hex8 SVK only with coarse mesh levels (4, 6, 8) for fast local execution.

```json
{"gate": "A", "attempt": 1, "result": "pass", "timestamp": "2026-04-26"}
```

### Gate B — Domain Quality

#### Attempt 1 — PASS

`BenchmarkSpec` is frozen; `BenchmarkRegistry` exposes mapping (`__getitem__`) + iteration. `MetricDelta.pct_delta` is signed `(current - baseline) / |baseline| * 100` (sign-aware — a metric that decreased reports as negative pct_delta). `compare_to_baseline` handles `baseline == 0.0` cleanly (returns 0.0 if both zero else `±inf`). `ComparisonReport.to_json/from_json` round-trips losslessly (verified by the test). Default tolerance 10%; per-benchmark overrides supported. Implementer surfaced and the orchestrator fixed two minor cleanup items: (1) the regenerated baseline JSON had Taichi import-banner stderr noise polluting the top of the file — stripped before commit; (2) `Callable` and `Iterator` imports in registry.py were not in `TYPE_CHECKING` block (TC003) — moved.

```json
{"gate": "B", "attempt": 1, "result": "pass", "timestamp": "2026-04-26"}
```

### Gate C — Verification

#### Attempt 1 — PASS

Fresh runs:
- `uv run pytest packages/mechdsl-core/tests/test_phase10_benchmark_registry.py -v` -> 3/3 passed (0.18s)
- `uv run pytest packages/mechdsl-core/tests/test_phase10_taylor_benchmark.py packages/mechdsl-core/tests/test_phase10_taylor_runtime.py packages/mechdsl-core/tests/test_phase10_taylor_state.py -v` -> 22/22 passed (0.55s — Phase 7 + P8-1 regression, zero drift)
- ruff: `All checks passed!` (after TC003 fix-up)
- mypy: `Success: no issues found in 4 source files`

```json
{"gate": "C", "attempt": 1, "result": "pass", "timestamp": "2026-04-26", "test_results": {"passed": 3, "total": 3, "percentage": 100}, "regression_results": {"passed": 22, "total": 22, "percentage": 100}, "commit": "f539cdf"}
```

---

## P9-2: Nightly CI and performance regression harness

**Issue:** _none — github_issue_map.json absent_
**Started:** 2026-04-26
**Completed:** 2026-04-26
**Branch:** `work/phase10-e9-perf-harness`

### Gate A — Spec Compliance

#### Attempt 1 — PASS

The implementer added `.github/workflows/nightly.yml` (cron `0 6 * * *` + `workflow_dispatch`; `nightly-tests` job runs `pytest -m "nightly or regression"` on `ubuntu-latest` with no GPU; `perf-regression` job runs the new `mechdsl.verify.perf.run_compare` CLI which loads the committed baseline, runs the smoke registry, compares with the default 10% tolerance, writes the report as a workflow artifact, and exits non-zero on >10% regression). New `mechdsl/verify/perf/run_compare.py` CLI factored out so the same compare logic can run locally for dev verification. Activated all three existing P10-10 stubs in `test_perf_regression.py` and added a fourth `test_baseline_failure_threshold_reporting` (Path b — preferred per the brief). All four `@pytest.mark.nightly @pytest.mark.regression`. The third stub's premise was rescoped by the implementer (the original PLAN-B P10-10 author asserted "all P10 tests carry @nightly" which doesn't match reality — most Phase 10 tests are `@integration`); the rewritten assertion checks what is actually load-bearing for the nightly tier (perf-harness tests carry `@nightly @regression`, the registry test carries `@regression`, the corpus has ≥6 modules). Existing `ci.yml` and `ci-backends.yml` are untouched.

```json
{"gate": "A", "attempt": 1, "result": "pass", "timestamp": "2026-04-26"}
```

### Gate B — Domain Quality

#### Attempt 1 — PASS

`run_compare.py` is a clean CLI with `main()` exposed for testing in addition to the entry-point `python -m`. The workflow YAML uses `uv run` exclusively (no bare `python` / `pytest`); the test that asserts this strips `uv\s+run\s+\S+` chunks first then scans the residue for bare invocations to avoid false matches on `uv run pytest`. The PyYAML 1.1 bool-coercion of the bare `on:` key is handled in the test (looks up both `workflow["on"]` and `workflow[True]`) so the workflow file stays idiomatic GitHub Actions. The injected-slowdown test does NOT live-run `run_smoke_registry` — it operates on the committed baseline as both inputs and perturbs in-memory, keeping the test ~100 ms (the registry already gets a single live exercise from P9-1's tests). The fourth test (`test_baseline_failure_threshold_reporting`) covers per-benchmark tolerance overrides in addition to the global default.

**Minor observation (non-blocking)**: the implementer reported "4 deselected in default tier" but the actual fresh run shows 4/4 passed in the default tier as well — pytest's project-level `addopts` in `pyproject.toml` excludes `slow / gpu / e2e` but NOT `nightly`, so `@nightly` tests run anywhere unless `-m "not nightly"` is added. Negligible impact (the 4 tests run in 0.18 s and provide useful coverage everywhere); the nightly workflow is still the canonical home, and the nightly tier selector (`-m "nightly or regression"`) correctly picks them up. If the project ever wants strict tier separation, add `not nightly` to `pyproject.toml` `addopts` (out of P9-2 scope).

```json
{"gate": "B", "attempt": 1, "result": "pass", "timestamp": "2026-04-26"}
```

### Gate C — Verification

#### Attempt 1 — PASS

Fresh runs:
- `uv run pytest packages/mechdsl-core/tests/test_perf_regression.py -v` -> 4/4 passed (0.18s)
- `uv run pytest packages/mechdsl-core/tests/test_perf_regression.py -v -m "nightly or regression"` -> 4/4 passed (0.18s) — nightly tier selector correctly picks all four
- `uv run pytest packages/mechdsl-core/tests/test_phase10_benchmark_registry.py packages/mechdsl-core/tests/test_phase10_taylor_benchmark.py packages/mechdsl-core/tests/test_phase10_taylor_runtime.py packages/mechdsl-core/tests/test_phase10_taylor_state.py -v` -> 25/25 passed (0.56s — P9-1 + Phase 7 + P8-1 regression, zero drift)
- YAML parse: `yaml.safe_load(open('.github/workflows/nightly.yml'))` returns workflow with jobs `['nightly-tests', 'perf-regression']`
- ruff: `All checks passed!`; mypy: `Success: no issues found in 5 source files`
- `git diff --stat HEAD~1 HEAD` -> 3 files (nightly.yml +60, run_compare.py +119, test_perf_regression.py +382/-25)

```json
{"gate": "C", "attempt": 1, "result": "pass", "timestamp": "2026-04-26", "test_results": {"passed": 4, "total": 4, "percentage": 100, "default_tier": "4/4", "nightly_tier": "4/4"}, "regression_results": {"passed": 25, "total": 25, "percentage": 100}, "yaml_jobs": ["nightly-tests", "perf-regression"], "commit": "11b1420"}
```

---

## Static Checks (phase-aggregate, recorded after both tasks complete)

```json
{
  "ruff": "uv run ruff check packages/mechdsl-core/src/mechdsl/verify/perf/ packages/mechdsl-core/tests/test_phase10_benchmark_registry.py packages/mechdsl-core/tests/test_perf_regression.py .github/workflows -> All checks passed",
  "mypy": "uv run mypy packages/mechdsl-core/src/mechdsl/verify/perf/ -> Success: no issues found in 5 source files"
}
```

## Phase Aggregate Verification (2026-04-26, fresh runs)

```json
{
  "p9_1_targeted": "uv run pytest test_phase10_benchmark_registry.py -v -> 3/3 passed (0.18s)",
  "p9_2_default_tier": "uv run pytest test_perf_regression.py -v -> 4/4 passed (0.18s)",
  "p9_2_nightly_tier": "uv run pytest test_perf_regression.py -v -m 'nightly or regression' -> 4/4 passed (0.18s)",
  "phase_9_full_regression": "uv run pytest test_phase10_benchmark_registry + test_phase10_taylor_benchmark + test_phase10_taylor_runtime + test_phase10_taylor_state -v -> 25/25 passed",
  "yaml_validation": "yaml.safe_load(open('.github/workflows/nightly.yml')) -> workflow with jobs ['nightly-tests', 'perf-regression']"
}
```

## Plan Closure

Phase 9 is the terminal phase of `ph10_preq`. P9-2 closes P10-10. The full original-scope P10-1..P10-10 prerequisite track is now complete:
- P10-1 (MMS convergence matrix) — Phase 6
- P10-2 (Cantilever) — Phase 5
- P10-3 (Cook membrane) — Phase 3
- P10-4 (Thick cylinder) — PLAN-B (already complete pre-`ph10_preq`)
- P10-5 (Plate with hole) — PLAN-B
- P10-6 (Necking bar) — Phase 3
- P10-7 (Taylor impact) — Phase 8
- P10-8 (Notched bar) — PLAN-B
- P10-9 (HGO uniaxial) — PLAN-B
- P10-10 (Performance harness) — Phase 9

See `dev/tasks/ph10_preq/Plan_Completion_Summary.md` for the full project completion summary.
