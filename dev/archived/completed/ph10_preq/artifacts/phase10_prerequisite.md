# Phase 10 Prerequisite Audit

Generated: 2026-04-24

## Purpose

This note audits Phase 10 against the **original** `dev/design_docs/PLAN-B.md`
scope, not against the narrower rescopes that were approved for some tasks
during execution.

The goal is to answer three questions:

1. Which Phase 10 tasks can plausibly complete in their original scope on the
   current repository surface?
2. Which tasks are blocked by the same class of issue already seen in P10-2
   and the original form of P10-3?
3. What enablements are required to complete Phase 10 without further scope
   cuts?

## Evidence base

This audit is based on:

- the Phase 10 plan rows in `dev/design_docs/PLAN-B.md`
- the task JSON files `dev/tasks/PLAN-B/json/P10-*.json`
- the current test surfaces under `packages/mechdsl-core/tests/`
- the current public benchmark API under `mechdsl.verify.benchmarks`
- the current MMS API under `mechdsl.verify.convergence`
- existing Phase 10 gate history in `dev/tasks/PLAN-B/gates/phase_10_gates.md`

Two concrete inspection results drive the classification:

| Surface | Current contract |
|---|---|
| Public benchmark API (`inspect`) | exports `run_thick_cylinder_benchmark`, `run_plate_with_hole_benchmark`, `run_cook_membrane_benchmark`, `run_necking_bar_benchmark`, `run_notched_bar_benchmark`, `run_hgo_uniaxial`; **does not** export `run_cantilever_benchmark` or `run_taylor_impact_benchmark` |
| MMS API (`inspect`) | `run_mms_convergence(lam, mu, ...)` and its docstring still state **uniform Hex8 meshes** |
| Phase 10 task tests (`ast`) | fully stubbed: `P10-1`, `P10-2`, `P10-7`, `P10-10`; partially stubbed: `P10-6`; fully implemented: `P10-3`, `P10-4`, `P10-5`, `P10-8`, `P10-9` |

## Executive Classification

| Task | Original-scope status today | Classification |
|---|---|---|
| P10-1 MMS convergence matrix | not executable in original scope | blocked |
| P10-2 Cantilever matrix | not executable in original scope | blocked |
| P10-3 Cook's membrane matrix | executable only after approved rescope to `TL × J2 × Hex8` | partially complete |
| P10-4 Thick cylinder | complete in original scope | viable |
| P10-5 Plate with hole | complete in original scope | viable |
| P10-6 Necking bar | TL path complete, UL path still deferred | partially complete |
| P10-7 Taylor impact | no executable benchmark surface yet | blocked |
| P10-8 Notched bar | complete in original scope | viable |
| P10-9 Fiber-reinforced strip | complete in original scope | viable |
| P10-10 Nightly regression harness | blocked on upstream original-scope gaps | blocked |

## Repeated Failure Pattern

The recurring Phase 10 failure mode is:

1. The plan row assumes a **benchmark matrix** over formulation, material, or
   element family.
2. The repo has unit-level or narrow reference coverage for some cells.
3. The repo does **not** yet have a reusable benchmark harness or mesh surface
   for the whole matrix.
4. The task stub therefore exists, but the benchmark surface needed to replace
   it does not.

This pattern applies directly to:

- `P10-1` MMS matrix
- `P10-2` cantilever matrix
- original-scope `P10-3` Cook matrix
- original-scope `P10-6` necking-bar matrix

`P10-7` is worse than this pattern: it also needs missing runtime capability,
not just a generalized benchmark harness.

## Task-by-Task Blockers And Required Enablements

### P10-1 — MMS convergence study

**Original plan scope**

- every element type × constitutive model
- 4 refinement levels
- fitted convergence rates

**Current blockers**

- `packages/mechdsl-core/tests/test_mms_convergence_matrix.py` is `8/8` stubbed.
- `mechdsl.verify.convergence.run_mms_convergence` still takes only `lam, mu`
  and documents a **uniform Hex8 mesh** path.
- No generalized MMS driver exists for `Tet4`, `Tet10`, or `Hex20`.
- No explicit manufactured-solution policy exists for dissipative models
  `J2`, `Perzyna`, and `Lemaitre`.
- The current convergence infrastructure is elastic-Hex8-centric, not a
  matrix over `(element, constitutive model)`.

**Required enablements**

- `E1` Generalized MMS driver over `ElementFactory`.
- `E2` Uniform refinement + mesh builder support for `Tet4`, `Tet10`, `Hex20`.
- `E3` Material-scope policy for MMS:
  either true manufactured solutions for dissipative models, or a formally
  documented elastic-regime restriction that still satisfies the plan.
- `E4` Public result structure for convergence studies so Phase 10 can consume
  them as benchmarks rather than ad hoc test-local tuples.

**Assessment**

Blocked by the same family of issue as P10-2: the task is written as a matrix
extension, but the underlying reusable verification surface is still a single
Hex8 path.

### P10-2 — Cantilever benchmark matrix

**Original plan scope**

- `TL, UL`
- `SVK, Neo-Hookean`
- `Hex8, Tet10, Hex20`
- `40×8×4` mesh

**Current blockers**

- `packages/mechdsl-core/tests/test_benchmarks_cantilever_matrix.py` is still
  a full stub.
- No public `run_cantilever_benchmark` exists in `mechdsl.verify.benchmarks`.
- The only executable UL cantilever path is the handwritten `Hex8 + SVK`
  reference solver in `tests/ref/ref_hex8_ul.py`.
- No reusable Tet10 cantilever mesh builder was found in `src/` or `tests/`.
- No generalized `TL/UL × hyperelastic × element-family` cantilever harness
  exists.
- The existing refined Hex8 benchmark cell is already expensive enough that
  the 12-cell matrix cannot be treated as a small parametrization patch.

**Required enablements**

- `E5` Public cantilever benchmark harness in `mechdsl.verify.benchmarks`.
- `E6` Mesh builders for cantilever runs across `Hex8`, `Tet10`, `Hex20`.
- `E7` Generic TL/UL hyperelastic benchmark-local solver over
  `ElementFactory`, not just handwritten `Hex8 + SVK`.
- `E8` Runtime/benchmark budget review for the full matrix, especially the
  refined quadratic-element cells.

**Assessment**

Blocked by the benchmark-surface gap already observed in live execution.

### P10-3 — Cook's membrane benchmark

**Original plan scope**

- `TL, UL`
- `J2`
- `Hex8, Tet10`

**Current blockers against original scope**

- The task is only complete after a user-approved rescope to `TL × J2 × Hex8`.
- No honest `UL + J2` benchmark path exists.
- No Tet10 Cook benchmark mesh/harness exists.
- The public harness `run_cook_membrane_benchmark` is locked to the Hex8
  regression slice rather than the original matrix.

**Required enablements**

- `E9` UL plastic reference or benchmark-local `UL + J2` solve surface.
- `E10` Tet10 Cook mesh and benchmark harness support.
- `E11` Matrix-capable Cook benchmark API instead of the current locked Hex8
  regression wrapper.

**Assessment**

Same blocker family as P10-2, plus the `UL + plastic` dead end also seen in
P10-6.

### P10-4 — Thick cylinder benchmark

**Original plan scope**

- `TL × SVK × Hex8`

**Current blockers**

- None for the original task.

**Required enablements**

- None to satisfy the plan row itself.

**Assessment**

Already completes in original scope and is not part of the repeated blocker
pattern.

### P10-5 — Plate with hole benchmark

**Original plan scope**

- `TL × SVK × Hex8/Hex20`

**Current blockers**

- None for the original task.

**Required enablements**

- None to satisfy the plan row itself.

**Assessment**

Already completes in original scope. This is a useful proof that a
benchmark-local `ElementFactory` solver can carry higher-order elastic
elements when the missing surface is only geometric/harness-related.

### P10-6 — Necking bar benchmark

**Original plan scope**

- `TL, UL`
- `J2 + SVK`
- `Hex8`

**Current blockers against original scope**

- `packages/mechdsl-core/tests/test_benchmarks_necking_bar_matrix.py` still
  has `1/3` stubbed via the UL skip.
- `run_necking_bar_benchmark` exists, but the UL acceptance criteria are
  explicitly deferred.
- The repo has UL elastic reference support, but not a handwritten or
  benchmark-local `UL + J2 + Hex8` path.

**Required enablements**

- `E9` UL plastic reference or benchmark-local `UL + J2` solve surface.
- `E12` Public necking-bar API widened from TL-only benchmark semantics to the
  original TL/UL matrix semantics.

**Assessment**

Partially complete. Same `UL + plastic` dead end as original-scope P10-3.

### P10-7 — Taylor impact benchmark

**Original plan scope**

- `UL × Johnson-Cook × reduced Hex8 + hourglass`
- explicit dynamics
- rigid-wall impact

**Current blockers**

- `packages/mechdsl-core/tests/test_taylor_impact.py` is `3/3` stubbed.
- No public `run_taylor_impact_benchmark` exists.
- No benchmark-local Taylor-impact runtime exists.
- No rigid-wall contact capability is wired into a benchmark surface.
- No production benchmark path combines:
  `UL + Johnson-Cook + reduced Hex8 + hourglass + explicit dynamics`.
- No benchmark-side extraction path for final mushroom geometry + `PEEQ` was
  found.
- The Taichi printer still documents Perzyna/Johnson-Cook emission as a future
  integration task for some paths, which is a warning sign for end-to-end use.

**Required enablements**

- `E13` Explicit Johnson-Cook benchmark/runtime path.
- `E14` Reduced-Hex8 + Flanagan-Belytschko support in a production benchmark
  solve, not just patch-test coverage.
- `E15` Simple rigid-wall impact/contact treatment suitable for the Taylor bar.
- `E16` Taylor-impact postprocessing for final length, mushroom diameter, and
  peak `PEEQ`.

**Assessment**

Blocked, but not by the same shallow harness problem. This task needs new
runtime capability on top of new harness code.

### P10-8 — Notched bar benchmark

**Original plan scope**

- `TL × Lemaitre × Hex8`

**Current blockers**

- None for the original task.

**Required enablements**

- None to satisfy the plan row itself.

**Assessment**

Already completes in original scope.

### P10-9 — Fiber-reinforced strip benchmark

**Original plan scope**

- `TL × HGO × Hex8`

**Current blockers**

- None for the original task.

**Required enablements**

- None to satisfy the plan row itself.

**Assessment**

Already completes in original scope.

### P10-10 — Performance + regression harness + nightly CI

**Original plan scope**

- nightly workflow
- baseline metrics
- regression detection
- all P10 benchmarks collected under the nightly marker

**Current blockers**

- `packages/mechdsl-core/tests/test_perf_regression.py` is `3/3` stubbed.
- Several upstream P10 tasks are not complete in original scope:
  `P10-1`, `P10-2`, original `P10-3`, original `P10-6`, `P10-7`.
- Without the original benchmark matrix surfaces, the nightly harness cannot
  honestly claim to cover the full Phase 10 plan.
- Benchmark metrics are not yet normalized across the existing harnesses.

**Required enablements**

- Completion of upstream original-scope Phase 10 tasks.
- `E17` Shared metrics schema across benchmark results.
- `E18` Baseline capture + comparison tooling.
- `E19` Nightly workflow wiring and artifact publication.

**Assessment**

Blocked downstream aggregator. It cannot be considered complete until the
physics/benchmark surfaces above exist in original scope.

## Enablement Bundles

The minimal prerequisite bundles are:

| Enablement | What it adds | Unblocks |
|---|---|---|
| `E1` Generalized MMS driver | element/material-parametric MMS surface | P10-1 |
| `E2` Higher-order MMS mesh/refinement support | `Tet4`, `Tet10`, `Hex20` refinement studies | P10-1 |
| `E3` MMS material policy | principled treatment of `J2`, `Perzyna`, `Lemaitre` in MMS | P10-1 |
| `E5` Public cantilever benchmark harness | reusable cantilever entrypoint | P10-2 |
| `E6` Cantilever mesh builders | `Hex8`, `Tet10`, `Hex20` cantilever meshes | P10-2 |
| `E7` Generic TL/UL hyperelastic benchmark solver | matrix-capable elastic cantilever execution | P10-2 |
| `E9` UL plastic benchmark layer | `UL + J2` benchmark execution | original P10-3, P10-6 |
| `E10` Tet10 Cook support | Tet10 benchmark mesh/harness for Cook | original P10-3 |
| `E11` Matrix-capable Cook API | exposes original Cook benchmark row | original P10-3 |
| `E13` Explicit Johnson-Cook runtime | benchmark-usable JC dynamics | P10-7 |
| `E14` Reduced-Hex8 hourglass production path | moves reduced Hex8 beyond patch tests | P10-7 |
| `E15` Simple impact contact | rigid wall for Taylor impact | P10-7 |
| `E16` Taylor-impact postprocessing | final geometry + `PEEQ` extraction | P10-7 |
| `E17` Shared benchmark metrics schema | uniform perf/regression payloads | P10-10 |
| `E18` Baseline comparison tooling | regression detection | P10-10 |
| `E19` Nightly CI workflow | scheduled execution + artifacts | P10-10 |

## Practical Completion Order

If the goal is to finish Phase 10 in the original plan scope with the fewest
round-trips, the dependency order is:

1. `E9` UL plastic benchmark layer
2. `E5 + E6 + E7` cantilever benchmark surface
3. `E1 + E2 + E3` generalized MMS framework
4. `E10 + E11` original-scope Cook matrix restore
5. `E13 + E14 + E15 + E16` Taylor-impact runtime + harness
6. `E17 + E18 + E19` nightly regression harness

This ordering is pragmatic:

- `E9` closes two partially-complete tasks at once (`P10-3`, `P10-6`).
- `E5/E6/E7` address the broadest single blocked benchmark task (`P10-2`).
- `E1/E2/E3` isolate the MMS stack rather than mixing it into benchmark work.
- `E13-E16` are the heaviest new runtime work and should not be hidden inside
  a generic “finish Phase 10” bucket.

## Final Conclusion

Phase 10 is **not** mostly blocked by one missing feature. It is blocked by
three distinct categories of missing prerequisite:

1. **Generalized verification surfaces** that never got built beyond the
   original Hex8 paths.
2. **UL plastic benchmark capability**, which blocks both original-scope Cook
   and necking-bar tasks.
3. **Explicit impact runtime capability**, which is unique to Taylor impact.

The tasks that already prove the current repo can carry original-scope Phase 10
work are:

- `P10-4`
- `P10-5`
- `P10-8`
- `P10-9`

The tasks that will keep failing in the same way unless the missing
benchmark/MMS surfaces are built are:

- `P10-1`
- `P10-2`
- original-scope `P10-3`
- original-scope `P10-6`

The task that needs a deeper runtime tranche before it is even a realistic
benchmark task is:

- `P10-7`

And until those are resolved in original scope, `P10-10` cannot honestly close
the phase.
