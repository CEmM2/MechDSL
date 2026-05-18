# ph10_preq Task Index

**Plan source:** `dev/plans/ph10_preq.md`
**Phases:** 9 prerequisite phases, mapped from the plan's recommended execution order.
**Total tasks:** 18
**GitHub mirroring:** skipped during initial generation because `gh auth status` reported an invalid token.

## Phase-ID mapping

Aut_Faciam requires sequential integer phase IDs. The source plan uses E-prefixed prerequisite names and a separate recommended execution order, so the numeric phases below follow that execution order.

| Phase ID | Plan section | Phase name |
|---|---|---|
| 1 | E1 | Shared Mesh Utilities |
| 2 | E4 | TL/UL J2 Benchmark Solver Layer |
| 3 | E5 | Cook And Necking Original-Scope Closure |
| 4 | E2 | Elastic Benchmark Solver Layer |
| 5 | E3 | Public Cantilever Benchmark |
| 6 | E6 | Generalized MMS Matrix |
| 7 | E7 | Taylor Impact Runtime Surface |
| 8 | E8 | Public Taylor Impact Benchmark |
| 9 | E9 | Performance And Nightly Harness |

## Task table

| Task ID | Phase | Title | Blocked by (immediate) | Blocks (immediate) | Derived from plan lines |
|---|---|---|---|---|---|
| P1-1 | 1 | Mesh datamodel and validation helpers | - | P1-2 | 62-99 |
| P1-2 | 1 | Phase 10 Hex8/Tet10/Hex20 mesh builders | P1-1 | P2-1, P2-2, P4-1, P6-1, P7-1 | 62-99 |
| P2-1 | 2 | TL J2 benchmark solver baseline | P1-2 | P2-2 | 171-207 |
| P2-2 | 2 | UL and Tet10 J2 benchmark solver extension | P2-1, P1-2 | P3-1, P3-2 | 171-207 |
| P3-1 | 3 | Cook membrane original matrix closure | P1-2, P2-2 | P9-1 | 208-240 |
| P3-2 | 3 | Necking bar UL closure | P2-2 | P9-1 | 208-240 |
| P4-1 | 4 | Elastic benchmark solver contracts | P1-2 | P4-2 | 101-135 |
| P4-2 | 4 | Elastic element/material smoke and runtime budget | P4-1 | P5-1 | 101-135 |
| P5-1 | 5 | Public cantilever benchmark API | P4-2 | P5-2 | 137-169 |
| P5-2 | 5 | Cantilever matrix test activation | P5-1 | P9-1 | 137-169 |
| P6-1 | 6 | MMS matrix API and result surface | P1-2 | P6-2 | 242-276 |
| P6-2 | 6 | MMS convergence matrix tests | P6-1 | P9-1 | 242-276 |
| P7-1 | 7 | Taylor explicit runtime, contact, and hourglass sanity | P1-2 | P7-2 | 278-315 |
| P7-2 | 7 | Taylor Johnson-Cook state and postprocessing | P7-1 | P8-1 | 278-315 |
| P8-1 | 8 | Public Taylor impact benchmark API | P7-2 | P8-2 | 317-348 |
| P8-2 | 8 | Taylor impact benchmark test activation | P8-1 | P9-1 | 317-348 |
| P9-1 | 9 | Benchmark registry and local baselines | P3-1, P3-2, P5-2, P6-2, P8-2 | P9-2 | 350-385 |
| P9-2 | 9 | Nightly CI and performance regression harness | P9-1 | - | 350-385 |

## Dependency-graph sanity checks

**No circular dependencies.** The graph is a DAG. The topological chain follows the recommended execution order in lines 387-397 of the plan.

**Cross-phase dependencies are explicit.** Plastic benchmark closure depends on the mesh utilities and J2 solver layer. Cantilever closure depends on the mesh utilities and elastic solver layer. MMS depends only on mesh utilities. Taylor closure depends on its runtime layer. The final performance harness waits for all open original-scope Phase 10 benchmarks to be active.

**High-impact shared APIs are intentionally avoided.** The generated task graph does not require edits to `BenchmarkResult`, frontend `build_context`, or `ElementFactory`; any future task that chooses to edit one of those must first run GitNexus impact and record the blast radius.

