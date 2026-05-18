# Phase 10 Prerequisite Implementation Plan

> ⚠️ **Superseded** by [`recovery_plan_latex_contract.md`](recovery_plan_latex_contract.md) (Phase 7 / R6 archival, P7-5). This Plan-B Phase 10 prerequisite plan is retained for historical reference only; the active execution source for the LaTeX-input contract recovery is the recovery plan. See [`STATUS_LEGEND.md`](../tracking/STATUS_LEGEND.md) and [`frontend_drift_history.md`](../reviews/frontend_drift_history.md).

Generated: 2026-04-25

## Summary

Phase 10 is blocked by missing prerequisite surfaces rather than by the already
completed benchmark cells. The current executable benchmark surface covers
`P10-4`, `P10-5`, `P10-8`, and `P10-9`; `P10-3` and `P10-6` are only partially
complete against the original plan; `P10-1`, `P10-2`, `P10-7`, and `P10-10`
remain blocked.

This plan decomposes the prerequisite work into small phases with separable
write scopes. The implementation rule is to prefer additive modules under
`mechdsl.verify.*`, preserve existing public signatures where possible, and
avoid high-blast-radius shared API edits unless a phase explicitly accepts that
risk.

## Analysis Basis

The prerequisite analysis used three sources of truth:

- `inspect` over the current Python API surface.
- `ast` over the Phase 10 test files and relevant benchmark/source modules.
- GitNexus query, context, and impact analysis after refreshing the local index.

Concrete findings:

- Public benchmark API currently exports `run_thick_cylinder_benchmark`,
  `run_plate_with_hole_benchmark`, `run_cook_membrane_benchmark`,
  `run_necking_bar_benchmark`, `run_notched_bar_benchmark`, and
  `run_hgo_uniaxial`.
- Public benchmark API does not export `run_cantilever_benchmark` or
  `run_taylor_impact_benchmark`.
- `run_mms_convergence(lam, mu, ...)` remains a uniform Hex8 MMS path.
- Phase 10 tests are fully stubbed for `P10-1`, `P10-2`, `P10-7`, and
  `P10-10`; `P10-6` still has one UL skip.
- GitNexus impact showed `BenchmarkResult` as `CRITICAL`, `build_context` as
  `CRITICAL`, `ElementFactory` as `MEDIUM`, and existing Cook/necking benchmark
  runners as `LOW`.

Planning consequences:

- Do not change `BenchmarkResult` as part of prerequisite work.
- Do not change frontend `build_context` for benchmark enablement.
- Avoid changing `ElementFactory`; consume it through additive benchmark-local
  helpers.
- Prefer new phase-owned modules and narrow public runners over broad shared
  result/schema churn.

## Ground Rules

- Use one branch and one commit per phase, named `work/phase10-e<N>-<slug>`.
- Run `gitnexus impact` before editing any existing function, class, or method.
- Run `gitnexus detect_changes` before each phase commit.
- Before editing, run `bash .agents/hooks/protect-spec.sh <paths>`.
- After Python edits, run `bash .agents/hooks/post-edit.sh <paths>`.
- Use `uv run` for all Python, pytest, ruff, and mypy commands.
- Treat `dev/design_docs/` as read-only.
- Keep local smoke tests separate from nightly/full benchmark configurations.

## Phase E1: Shared Mesh Utilities

Purpose: remove geometry and boundary-surface blockers without touching solver
or material behavior.

Scope:

- Add benchmark-local mesh utilities for structured block, cantilever, and
  Cook-style meshes.
- Support `Hex8`, `Tet10`, and `Hex20` where those meshes are needed by Phase
  10.
- Provide coordinates, connectivity, deterministic boundary node sets, face
  tags, and Jacobian/orientation validation.
- Keep these utilities solver-agnostic.

Primary writes:

- New mesh utility module under `packages/mechdsl-core/src/mechdsl/verify/benchmarks/`.
- New tests for mesh topology, boundary sets, and positive Jacobians.

Must not do:

- Do not modify `ElementFactory`.
- Do not modify existing benchmark runners.
- Do not introduce material or solver logic.

Unlocks:

- `P10-2` mesh prerequisite.
- `P10-3` Tet10 Cook mesh prerequisite.
- Part of `P10-1` element-family MMS support.

Acceptance:

- Hex8, Tet10, and Hex20 generated meshes have positive Jacobians at relevant
  quadrature points.
- Boundary sets are deterministic and tested.
- Existing benchmark tests pass unchanged.

## Phase E2: Elastic Benchmark Solver Layer

Purpose: create the reusable elastic solve surface needed by cantilever
benchmarks while keeping it independent from plasticity and MMS.

Scope:

- Add benchmark-local TL/UL hyperelastic solver helpers.
- Support `SVK` and `Neo-Hookean`.
- Support `Hex8`, `Tet10`, and `Hex20` through existing element IR/factory
  outputs.
- Validate on cheap meshes before using the full cantilever matrix.

Primary writes:

- New internal elastic benchmark solver module.
- Focused tests for TL/UL small-displacement agreement and element-family
  execution.

Must not do:

- Do not expose a public cantilever runner yet.
- Do not change frontend or codegen APIs.
- Do not alter constitutive model semantics.

Unlocks:

- Solver prerequisite for `P10-2`.

Acceptance:

- TL and UL Hex8 agree in the small-displacement limit.
- SVK and Neo-Hookean run for Hex8, Tet10, and Hex20.
- Runtime for candidate cantilever cells is measured and recorded before the
  full matrix is attempted.

## Phase E3: Public Cantilever Benchmark

Purpose: complete `P10-2` in original scope using the E1 and E2 surfaces.

Scope:

- Add `CantileverParameters`.
- Add `run_cantilever_benchmark` to `mechdsl.verify.benchmarks`.
- Replace the P10-2 stub with active matrix tests for
  `TL/UL x SVK/Neo-Hookean x Hex8/Tet10/Hex20`.
- Keep benchmark mesh sizes configurable so local tests can use smoke settings
  while nightly can use the full plan-sized mesh.

Primary writes:

- New cantilever benchmark module.
- Benchmark package exports.
- `test_benchmarks_cantilever_matrix.py`.

Must not do:

- Do not widen unrelated benchmark result schemas.
- Do not couple cantilever tests to plastic/MMS/Taylor work.

Unlocks:

- `P10-2`.

Acceptance:

- Full original cantilever matrix is represented by active tests.
- Tip displacement stays within planned tolerance against beam theory.
- Existing Phase 10 benchmark tests still pass.

## Phase E4: TL/UL J2 Benchmark Solver Layer

Purpose: isolate the `UL + J2` blocker shared by original-scope `P10-3` and
`P10-6`.

Scope:

- Add benchmark-local TL/UL J2 assembly and solve helpers.
- Maintain history fields per element and quadrature point.
- Use existing J2 return-mapping behavior as the material contract.
- Validate with small reference problems before touching Cook or necking
  public APIs.

Primary writes:

- New internal J2 benchmark solver module.
- Focused tests for history updates, TL reference agreement, UL objectivity,
  and monotonic plastic work.

Must not do:

- Do not change J2 constitutive semantics.
- Do not change Cook or necking public defaults in this phase.
- Do not touch Johnson-Cook or Taylor impact code.

Unlocks:

- Original-scope `P10-3`.
- Original-scope `P10-6`.

Acceptance:

- TL Hex8 matches the existing plastic reference within tolerance.
- UL Hex8 passes rigid-rotation/objectivity checks.
- Plastic work and accumulated plastic strain are non-negative and finite.
- Tet10 J2 path runs with stable history updates.

## Phase E5: Cook And Necking Original-Scope Closure

Purpose: consume E1 and E4 to remove remaining plastic benchmark skips.

Scope:

- Widen Cook from the approved rescope to the original
  `TL/UL x J2 x Hex8/Tet10` matrix.
- Widen necking from TL-only behavior to original TL/UL Hex8 behavior.
- Keep old defaults backward-compatible for existing tests.
- Remove the UL skip from necking tests.

Primary writes:

- Cook benchmark module and tests.
- Necking benchmark module and tests.
- Task tracker and gate/report artifacts for the completed original scopes.

Must not do:

- Do not alter completed unrelated benchmarks.
- Do not change `BenchmarkResult`.

Unlocks:

- Original-scope `P10-3`.
- Original-scope `P10-6`.

Acceptance:

- Cook tests cover all original cells.
- Necking tests have no UL skip.
- Existing Cook and necking smoke/acceptance tests remain compatible.

## Phase E6: Generalized MMS Matrix

Purpose: complete the MMS prerequisite for `P10-1` without breaking the
existing Hex8 MMS API.

Scope:

- Add a new matrix-capable MMS API rather than changing
  `run_mms_convergence`.
- Use E1 mesh utilities and existing convergence helpers.
- Cover the planned element families and material entries.
- For dissipative materials, use a documented elastic-regime MMS policy unless
  true manufactured plastic/damage source terms are implemented in this phase.

Primary writes:

- New convergence matrix module or additive API in `mechdsl.verify`.
- `test_mms_convergence_matrix.py`.

Must not do:

- Do not change the existing `run_mms_convergence(lam, mu, ...)` contract.
- Do not use `BenchmarkResult`; keep MMS result types local to convergence.
- Do not require Taylor or cantilever phases.

Unlocks:

- `P10-1`.

Acceptance:

- Existing `test_convergence.py` remains unchanged and passing.
- Matrix tests are active for the planned element/material combinations.
- Fitted rates and failure diagnostics are returned in structured convergence
  results.

## Phase E7: Taylor Impact Runtime Surface

Purpose: isolate the high-risk runtime work needed before `P10-7` can become a
normal benchmark task.

Scope:

- Add a benchmark-local explicit impact engine.
- Use existing `JohnsonCookMaterial`, Johnson-Cook return mapping, reduced
  Hex8, and Flanagan-Belytschko hourglass force.
- Add rigid-wall contact behavior.
- Add postprocessing for final length, mushroom radius, and equivalent plastic
  strain.

Primary writes:

- New internal Taylor/explicit benchmark runtime module.
- Focused unit tests for explicit update, contact, hourglass boundedness, and
  Johnson-Cook state output.

Must not do:

- Do not change Johnson-Cook model behavior unless focused tests prove a real
  defect.
- Do not change hourglass implementation unless focused tests prove a real
  defect.
- Do not expose the public Taylor benchmark runner yet.

Unlocks:

- Runtime prerequisite for `P10-7`.

Acceptance:

- Reduced Hex8 hourglass energy remains bounded in a non-impact sanity case.
- Rigid-wall contact prevents penetration.
- Johnson-Cook state update produces finite stress, temperature, and equivalent
  plastic strain.

## Phase E8: Public Taylor Impact Benchmark

Purpose: complete `P10-7` after E7 proves the runtime.

Scope:

- Add `TaylorImpactParameters`.
- Add `run_taylor_impact_benchmark` to `mechdsl.verify.benchmarks`.
- Replace Taylor stubs with active benchmark tests.
- Provide smoke and nightly configurations.

Primary writes:

- Taylor impact benchmark module.
- Benchmark package exports.
- `test_taylor_impact.py`.

Must not do:

- Do not couple Taylor benchmark closure to MMS or cantilever work.
- Do not change shared benchmark result schemas.

Unlocks:

- `P10-7`.

Acceptance:

- Final length, mushroom radius, and equivalent plastic strain localization
  tests are active.
- Tests are deterministic under smoke settings.
- Full benchmark remains marked slow/nightly.

## Phase E9: Performance And Nightly Harness

Purpose: complete `P10-10` only after all original-scope benchmark tasks are
active.

Scope:

- Add a benchmark registry over public benchmark runners.
- Capture wall time, solver iteration counts where available, and benchmark
  metrics.
- Add checked-in baselines for smoke/local comparison.
- Wire nightly CI to full benchmark settings.

Primary writes:

- Performance/regression harness.
- Baseline artifact.
- Nightly workflow.
- `test_perf_regression.py`.

Must not do:

- Do not invent missing benchmark semantics here.
- Do not reopen upstream benchmark tasks.
- Do not require GPU-only execution for local tests.

Unlocks:

- `P10-10`.

Acceptance:

- `P10-1` through `P10-9` are represented in the registry.
- Local performance test uses smoke settings.
- Nightly workflow uses full benchmark settings.
- Baseline comparison reports clear per-benchmark deltas.

## Recommended Execution Order

1. E1 mesh utilities.
2. E4 TL/UL J2 solver layer.
3. E5 Cook and necking original-scope closure.
4. E2 elastic benchmark solver layer.
5. E3 public cantilever benchmark.
6. E6 generalized MMS matrix.
7. E7 Taylor impact runtime surface.
8. E8 public Taylor impact benchmark.
9. E9 performance and nightly harness.

This order closes the partially completed tasks first, keeps cantilever
separate from plasticity, keeps MMS separate from benchmark runners, and delays
Taylor impact until the end because it has the widest new runtime surface.

## Verification Per Phase

Each phase must run:

- Targeted pytest for newly touched tests.
- Existing benchmark tests affected by the phase.
- `uv run ruff check` on touched package/test paths.
- `uv run mypy` on touched source package paths.
- `gitnexus detect_changes` before commit.

For Python source edits, also run:

- `bash .agents/hooks/post-edit.sh <changed-python-files>`

