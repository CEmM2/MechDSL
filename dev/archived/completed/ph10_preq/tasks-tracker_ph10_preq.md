# ph10_preq Development Task Tracker

> ⚠️ **Superseded** — the active execution source is [`tasks-tracker_recovery_plan_latex_contract.md`](tasks-tracker_recovery_plan_latex_contract.md), driven by [`dev/plans/recovery_plan_latex_contract.md`](../plans/recovery_plan_latex_contract.md). This tracker is retained for historical reference only (Phase 7 / R6 archival, P7-5).

Generated on: 2026-04-25
This tracker records execution status for the Phase 10 prerequisite task set.

## ph10_preq Tracker

Plan source: `dev/plans/ph10_preq.md`
Task index: `dev/tasks/ph10_preq/all-tasks.md`

| Task ID | Title | Status | Owner | Blocked by (open) | Blocks | Plan lines | PR/Commit | Verified by | Completed on |
|---|---|---|---|---|---|---|---|---|---|
| P1-1 | Mesh datamodel and validation helpers | done | Codex | - | P1-2 | 62-99 | work/phase10-e1-mesh-utilities | `uv run pytest packages/mechdsl-core/tests/test_phase10_mesh_utils.py -v` -> 10/10 passed; ruff clean; mypy clean | 2026-04-25 |
| P1-2 | Phase 10 Hex8/Tet10/Hex20 mesh builders | done | Codex | - | P2-1, P2-2, P4-1, P6-1, P7-1 | 62-99 | work/phase10-e1-mesh-utilities | `uv run pytest packages/mechdsl-core/tests/test_phase10_mesh_utils.py -v` -> 10/10 passed; ruff clean; mypy clean | 2026-04-25 |
| P2-1 | TL J2 benchmark solver baseline | done | Codex | - | P2-2 | 171-207 | work/phase10-e4-j2-solver | `uv run pytest packages/mechdsl-core/tests/test_phase10_j2_solver.py -v` -> 5/5 passed; combined Phase 1+2 tests -> 15/15 passed; ruff clean; mypy clean | 2026-04-25 |
| P2-2 | UL and Tet10 J2 benchmark solver extension | done | Codex | - | P3-1, P3-2 | 171-207 | work/phase10-e4-j2-solver | `uv run pytest packages/mechdsl-core/tests/test_phase10_j2_solver.py -v` -> 5/5 passed; combined Phase 1+2 tests -> 15/15 passed; ruff clean; mypy clean | 2026-04-25 |
| P3-1 | Cook membrane original matrix closure | done | Codex | - | P9-1 | 208-240 | work/phase10-e5-cook-necking | `uv run pytest packages/mechdsl-core/tests/test_benchmarks_cook_membrane_matrix.py packages/mechdsl-core/tests/test_benchmarks_necking_bar_matrix.py -v` -> 10/10 passed; ruff clean; mypy clean | 2026-04-25 |
| P3-2 | Necking bar UL closure | done | Codex | - | P9-1 | 208-240 | work/phase10-e5-cook-necking | `uv run pytest packages/mechdsl-core/tests/test_benchmarks_cook_membrane_matrix.py packages/mechdsl-core/tests/test_benchmarks_necking_bar_matrix.py -v` -> 10/10 passed; ruff clean; mypy clean | 2026-04-25 |
| P4-1 | Elastic benchmark solver contracts | done | Codex | - | P4-2 | 101-135 | work/phase10-e2-elastic-solver | `uv run pytest packages/mechdsl-core/tests/test_phase10_elastic_solver.py -v` -> 9/9 passed; ruff clean; mypy clean | 2026-04-25 |
| P4-2 | Elastic element/material smoke and runtime budget | done | Codex | - | P5-1 | 101-135 | work/phase10-e2-elastic-solver | `uv run pytest packages/mechdsl-core/tests/test_phase10_elastic_solver.py -v` -> 9/9 passed; ruff clean; mypy clean | 2026-04-25 |
| P5-1 | Public cantilever benchmark API | done | Codex | - | P5-2 | 137-169 | work/phase10-e3-public-cantilever | `uv run pytest packages/mechdsl-core/tests/test_benchmarks_cantilever_matrix.py -v` -> 15/15 passed; ruff clean; mypy clean | 2026-04-25 |
| P5-2 | Cantilever matrix test activation | done | Codex | - | P9-1 | 137-169 | work/phase10-e3-public-cantilever | `uv run pytest packages/mechdsl-core/tests/test_benchmarks_cantilever_matrix.py -v` -> 15/15 passed; ruff clean; mypy clean | 2026-04-25 |
| P6-1 | MMS matrix API and result surface | done | Codex | - | P6-2 | 242-276 | work/phase10-e6-generalized-mms | `uv run pytest packages/mechdsl-core/tests/test_convergence.py packages/mechdsl-core/tests/test_mms_convergence_matrix.py -v` -> 30/30 passed; ruff clean; mypy clean | 2026-04-25 |
| P6-2 | MMS convergence matrix tests | done | Codex | - | P9-1 | 242-276 | work/phase10-e6-generalized-mms | `uv run pytest packages/mechdsl-core/tests/test_convergence.py packages/mechdsl-core/tests/test_mms_convergence_matrix.py -v` -> 30/30 passed; ruff clean; mypy clean | 2026-04-25 |
| P7-1 | Taylor explicit runtime, contact, and hourglass sanity | done | Claude (Opus subagent) | - | P7-2 | 278-315 | work/phase10-e7-taylor-runtime @ 861929d | `uv run pytest packages/mechdsl-core/tests/test_phase10_taylor_runtime.py -v` -> 5/5 passed; regression `test_hourglass_control.py + test_explicit_dynamics_acceptance.py + test_johnson_cook.py` -> 47/47 passed; ruff clean; mypy clean | 2026-04-26 |
| P7-2 | Taylor Johnson-Cook state and postprocessing | done | Claude (Opus subagent) | - | P8-1 | 278-315 | work/phase10-e7-taylor-runtime @ dbe3f6b | `uv run pytest packages/mechdsl-core/tests/test_phase10_taylor_state.py -v` -> 14/14 passed; combined Phase 7 + JC regression (test_phase10_taylor_runtime + test_phase10_taylor_state + test_johnson_cook + test_hourglass_control) -> 64/64 passed; ruff clean; mypy clean | 2026-04-26 |
| P8-1 | Public Taylor impact benchmark API | done | Claude (Opus subagent) | - | P8-2 | 317-348 | work/phase10-e8-public-taylor-benchmark @ 7aca187 | `uv run pytest packages/mechdsl-core/tests/test_phase10_taylor_benchmark.py packages/mechdsl-core/tests/test_phase10_taylor_runtime.py packages/mechdsl-core/tests/test_phase10_taylor_state.py -v` -> 22/22 passed; P10-7 stubs in test_taylor_impact.py still 3 skipped (deliberate, P8-2 owns activation); ruff clean; mypy clean | 2026-04-26 |
| P8-2 | Taylor impact benchmark test activation | done | Claude (Opus subagent) | - | P9-1 | 317-348 | work/phase10-e8-public-taylor-benchmark @ 5a49c63 | `uv run pytest packages/mechdsl-core/tests/test_taylor_impact.py -v` -> 6/6 passed (3 nightly + 3 smoke); `-m 'nightly or regression'` -> 3/3 passed, 3 deselected; Phase 7 + P8-1 regression -> 22/22 passed; ruff clean | 2026-04-26 |
| P9-1 | Benchmark registry and local baselines | done | Claude (Opus subagent + orchestrator TDD finish) | - | P9-2 | 350-385 | work/phase10-e9-perf-harness @ f539cdf | `uv run pytest packages/mechdsl-core/tests/test_phase10_benchmark_registry.py -v` -> 3/3 passed; Phase 7 + P8-1 regression -> 22/22 passed; ruff + mypy clean | 2026-04-26 |
| P9-2 | Nightly CI and performance regression harness | done | Claude (Opus subagent) | - | - | 350-385 | work/phase10-e9-perf-harness @ 11b1420 | `uv run pytest test_perf_regression.py -v -m 'nightly or regression'` -> 4/4 passed; full Phase 9 regression -> 25/25 passed; YAML parses with jobs nightly-tests + perf-regression; ruff + mypy clean | 2026-04-26 |

## Update protocol

1. When a task starts, set `Status` to `in_progress`, assign `Owner`, and keep unresolved blockers in `Blocked by (open)`.
2. When a task is done, set `Status` to `done`, fill `PR/Commit`, `Verified by`, and `Completed on` (YYYY-MM-DD).
3. For each newly completed task, remove its ID from downstream rows in `Blocked by (open)` when applicable.

## Verification status

### Phase 1 aggregate verification:

#### Phase 1 mapping between test and task:

| Task ID | Title | Test file |
|---|---|---|
| P1-1 | Mesh datamodel and validation helpers | packages/mechdsl-core/tests/test_phase10_mesh_utils.py |
| P1-2 | Phase 10 Hex8/Tet10/Hex20 mesh builders | packages/mechdsl-core/tests/test_phase10_mesh_utils.py |

#### Verification outcomes:

`uv run pytest packages/mechdsl-core/tests/test_phase10_mesh_utils.py -v` -> 10/10 passed.

`uv run ruff check packages/mechdsl-core/src/mechdsl/verify/benchmarks/_meshes.py packages/mechdsl-core/tests/test_phase10_mesh_utils.py` -> clean.

`uv run mypy packages/mechdsl-core/src/mechdsl/verify/benchmarks/_meshes.py` -> clean.

### Phase 2 aggregate verification:

#### Phase 2 mapping between test and task:

| Task ID | Title | Test file |
|---|---|---|
| P2-1 | TL J2 benchmark solver baseline | packages/mechdsl-core/tests/test_phase10_j2_solver.py |
| P2-2 | UL and Tet10 J2 benchmark solver extension | packages/mechdsl-core/tests/test_phase10_j2_solver.py |

#### Verification outcomes:

`uv run pytest packages/mechdsl-core/tests/test_phase10_j2_solver.py -v` -> 5/5 passed.

`uv run pytest packages/mechdsl-core/tests/test_phase10_mesh_utils.py packages/mechdsl-core/tests/test_phase10_j2_solver.py -v` -> 15/15 passed.

`uv run ruff check packages/mechdsl-core/src/mechdsl/verify/benchmarks/_meshes.py packages/mechdsl-core/src/mechdsl/verify/benchmarks/_j2_solver.py packages/mechdsl-core/tests/test_phase10_mesh_utils.py packages/mechdsl-core/tests/test_phase10_j2_solver.py` -> clean.

`uv run mypy packages/mechdsl-core/src/mechdsl/verify/benchmarks/_meshes.py packages/mechdsl-core/src/mechdsl/verify/benchmarks/_j2_solver.py` -> clean.

### Phase 3 aggregate verification:

#### Phase 3 mapping between test and task:

| Task ID | Title | Test file |
|---|---|---|
| P3-1 | Cook membrane original matrix closure | packages/mechdsl-core/tests/test_benchmarks_cook_membrane_matrix.py |
| P3-2 | Necking bar UL closure | packages/mechdsl-core/tests/test_benchmarks_necking_bar_matrix.py |

#### Verification outcomes:

`uv run pytest packages/mechdsl-core/tests/test_benchmarks_cook_membrane_matrix.py packages/mechdsl-core/tests/test_benchmarks_necking_bar_matrix.py -v` -> 10/10 passed.

`uv run ruff check packages/mechdsl-core/src/mechdsl/verify/benchmarks/cook_membrane.py packages/mechdsl-core/src/mechdsl/verify/benchmarks/necking_bar.py packages/mechdsl-core/tests/test_benchmarks_cook_membrane_matrix.py packages/mechdsl-core/tests/test_benchmarks_necking_bar_matrix.py` -> clean.

`uv run mypy packages/mechdsl-core/src/mechdsl/verify/benchmarks/cook_membrane.py packages/mechdsl-core/src/mechdsl/verify/benchmarks/necking_bar.py` -> clean.

### Phase 4 aggregate verification:

#### Phase 4 mapping between test and task:

| Task ID | Title | Test file |
|---|---|---|
| P4-1 | Elastic benchmark solver contracts | packages/mechdsl-core/tests/test_phase10_elastic_solver.py |
| P4-2 | Elastic element/material smoke and runtime budget | packages/mechdsl-core/tests/test_phase10_elastic_solver.py |

#### Verification outcomes:

`uv run pytest packages/mechdsl-core/tests/test_phase10_elastic_solver.py -v` -> 9/9 passed.

`uv run ruff check packages/mechdsl-core/src/mechdsl/verify/benchmarks/_elastic_solver.py packages/mechdsl-core/tests/test_phase10_elastic_solver.py` -> clean.

`uv run mypy packages/mechdsl-core/src/mechdsl/verify/benchmarks/_elastic_solver.py` -> clean.

### Phase 5 aggregate verification:

#### Phase 5 mapping between test and task:

| Task ID | Title | Test file |
|---|---|---|
| P5-1 | Public cantilever benchmark API | packages/mechdsl-core/tests/test_benchmarks_cantilever_matrix.py |
| P5-2 | Cantilever matrix test activation | packages/mechdsl-core/tests/test_benchmarks_cantilever_matrix.py |

#### Verification outcomes:

`uv run pytest packages/mechdsl-core/tests/test_benchmarks_cantilever_matrix.py -v` -> 15/15 passed.

`uv run ruff check packages/mechdsl-core/src/mechdsl/verify/benchmarks/cantilever.py packages/mechdsl-core/src/mechdsl/verify/benchmarks/__init__.py packages/mechdsl-core/tests/test_benchmarks_cantilever_matrix.py` -> clean.

`uv run mypy packages/mechdsl-core/src/mechdsl/verify/benchmarks/cantilever.py` -> clean.

### Phase 6 aggregate verification:

#### Phase 6 mapping between test and task:

| Task ID | Title | Test file |
|---|---|---|
| P6-1 | MMS matrix API and result surface | packages/mechdsl-core/tests/test_mms_convergence_matrix.py |
| P6-2 | MMS convergence matrix tests | packages/mechdsl-core/tests/test_mms_convergence_matrix.py |

#### Verification outcomes:

`uv run pytest packages/mechdsl-core/tests/test_mms_convergence_matrix.py -v` -> 10/10 passed.

`uv run pytest packages/mechdsl-core/tests/test_convergence.py packages/mechdsl-core/tests/test_mms_convergence_matrix.py -v` -> 30/30 passed.

`uv run ruff check packages/mechdsl-core/src/mechdsl/verify/mms_matrix.py packages/mechdsl-core/tests/test_mms_convergence_matrix.py` -> clean.

`uv run mypy packages/mechdsl-core/src/mechdsl/verify/mms_matrix.py` -> clean.

### Phase 7 aggregate verification:

#### Phase 7 mapping between test and task:

| Task ID | Title | Test file |
|---|---|---|
| P7-1 | Taylor explicit runtime, contact, and hourglass sanity | packages/mechdsl-core/tests/test_phase10_taylor_runtime.py; cross-checks: test_hourglass_control.py, test_explicit_dynamics_acceptance.py, test_johnson_cook.py |
| P7-2 | Taylor Johnson-Cook state and postprocessing | packages/mechdsl-core/tests/test_phase10_taylor_state.py; cross-checks: test_johnson_cook.py |

#### Verification outcomes:

`uv run pytest packages/mechdsl-core/tests/test_phase10_taylor_runtime.py -v` -> 5/5 passed (P7-1, 2026-04-26).

`uv run pytest packages/mechdsl-core/tests/test_hourglass_control.py packages/mechdsl-core/tests/test_explicit_dynamics_acceptance.py packages/mechdsl-core/tests/test_johnson_cook.py -v` -> 47/47 passed (P7-1 regression cross-check, 2026-04-26).

`uv run ruff check packages/mechdsl-core/src/mechdsl/verify/benchmarks/_taylor_runtime.py packages/mechdsl-core/tests/test_phase10_taylor_runtime.py` -> clean.

`uv run mypy packages/mechdsl-core/src/mechdsl/verify/benchmarks/_taylor_runtime.py` -> clean.

`uv run pytest packages/mechdsl-core/tests/test_phase10_taylor_state.py -v` -> 14/14 passed (P7-2, 2026-04-26).

`uv run pytest packages/mechdsl-core/tests/test_phase10_taylor_runtime.py packages/mechdsl-core/tests/test_phase10_taylor_state.py packages/mechdsl-core/tests/test_johnson_cook.py packages/mechdsl-core/tests/test_hourglass_control.py -v` -> 64/64 passed (Phase 7 aggregate, 2026-04-26).

`uv run ruff check packages/mechdsl-core/src/mechdsl/verify/benchmarks/_taylor_runtime.py packages/mechdsl-core/tests/test_phase10_taylor_runtime.py packages/mechdsl-core/tests/test_phase10_taylor_state.py` -> clean.

`uv run mypy packages/mechdsl-core/src/mechdsl/verify/benchmarks/_taylor_runtime.py` -> clean.

### Phase 8 aggregate verification:

#### Phase 8 mapping between test and task:

| Task ID | Title | Test file |
|---|---|---|
| P8-1 | Public Taylor impact benchmark API | packages/mechdsl-core/tests/test_phase10_taylor_benchmark.py (new stub); cross-checks: test_phase10_taylor_runtime.py, test_phase10_taylor_state.py |
| P8-2 | Taylor impact benchmark test activation | packages/mechdsl-core/tests/test_taylor_impact.py (existing P10-7 stubs to be activated); cross-check: test_phase10_taylor_benchmark.py |

#### Verification outcomes:

Pending execution. Planned commands:

`uv run pytest packages/mechdsl-core/tests/test_phase10_taylor_benchmark.py -v` -> 3/3 passed (P8-1, 2026-04-26).

`uv run pytest packages/mechdsl-core/tests/test_taylor_impact.py -v` -> 6/6 passed (P8-2 default tier: 3 nightly + 3 smoke, 2026-04-26).

`uv run pytest packages/mechdsl-core/tests/test_taylor_impact.py -v -m 'nightly or regression'` -> 3/3 passed, 3 deselected (P8-2 nightly tier, 2026-04-26).

`uv run pytest packages/mechdsl-core/tests/test_phase10_taylor_benchmark.py packages/mechdsl-core/tests/test_phase10_taylor_runtime.py packages/mechdsl-core/tests/test_phase10_taylor_state.py -v` -> 22/22 passed (Phase 7 + P8-1 regression, 2026-04-26).

`uv run ruff check packages/mechdsl-core/src/mechdsl/verify/benchmarks/taylor_impact.py packages/mechdsl-core/src/mechdsl/verify/benchmarks/__init__.py packages/mechdsl-core/tests/test_phase10_taylor_benchmark.py packages/mechdsl-core/tests/test_taylor_impact.py` -> clean.

`uv run mypy packages/mechdsl-core/src/mechdsl/verify/benchmarks/taylor_impact.py` -> clean.

### Phase 9 aggregate verification:

#### Phase 9 mapping between test and task:

| Task ID | Title | Test file |
|---|---|---|
| P9-1 | Benchmark registry and local baselines | packages/mechdsl-core/tests/test_phase10_benchmark_registry.py (new stub); artifact: packages/mechdsl-core/tests/golden/perf/baseline_smoke.json |
| P9-2 | Nightly CI and performance regression harness | packages/mechdsl-core/tests/test_perf_regression.py (existing P10-10 stubs to be activated); artifact: .github/workflows/nightly.yml |

#### Verification outcomes:

Pending execution. Planned commands:

`uv run pytest packages/mechdsl-core/tests/test_phase10_benchmark_registry.py -v` -> 3/3 passed (P9-1, 2026-04-26).

`uv run pytest packages/mechdsl-core/tests/test_perf_regression.py -v` -> 4/4 passed (P9-2 default tier, 2026-04-26).

`uv run pytest packages/mechdsl-core/tests/test_perf_regression.py -v -m 'nightly or regression'` -> 4/4 passed (P9-2 nightly tier, 2026-04-26).

`uv run pytest packages/mechdsl-core/tests/test_phase10_benchmark_registry.py packages/mechdsl-core/tests/test_phase10_taylor_benchmark.py packages/mechdsl-core/tests/test_phase10_taylor_runtime.py packages/mechdsl-core/tests/test_phase10_taylor_state.py -v` -> 25/25 passed (Phase 7 + P8-1 + P9-1 regression, 2026-04-26).

`uv run ruff check packages/mechdsl-core/src/mechdsl/verify/perf/ packages/mechdsl-core/tests/test_phase10_benchmark_registry.py packages/mechdsl-core/tests/test_perf_regression.py .github/workflows` -> clean.

`uv run mypy packages/mechdsl-core/src/mechdsl/verify/perf/` -> clean.

YAML validation: `yaml.safe_load(open('.github/workflows/nightly.yml'))` -> workflow with jobs `['nightly-tests', 'perf-regression']`.

**Phase 9 is the terminal phase. P10-10 closed; full P10-1..P10-10 prerequisite track is complete.**
