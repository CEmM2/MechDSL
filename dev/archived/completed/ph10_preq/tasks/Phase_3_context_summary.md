# Phase 3 Context Summary: Cook And Necking Original-Scope Closure

**Plan:** `dev/plans/ph10_preq.md`
**Original plan phase name:** E5 Cook And Necking Original-Scope Closure

## Must Know

- This phase consumes the mesh and J2 solver prerequisites to remove the remaining original-scope gaps for P10-3 and P10-6.
- Keep existing Cook and necking defaults backward-compatible.
- Do not change `BenchmarkResult`; GitNexus marked it critical impact.
- Do not alter completed unrelated benchmarks.

## Should Know

- Cook must widen to `TL/UL x J2 x Hex8/Tet10`.
- Necking must remove the UL skip and support original TL/UL Hex8 semantics.

## Allowed Deviations

- None. If an original-scope cell remains non-executable, record a blocker rather than silently narrowing the matrix.

## Downstream Impact

- Completion contributes two required upstream benchmark closures for the final performance harness.

