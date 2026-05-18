# Phase 5 Context Summary: Public Cantilever Benchmark

**Plan:** `dev/plans/ph10_preq.md`
**Original plan phase name:** E3 Public Cantilever Benchmark

## Must Know

- This phase closes P10-2 in original scope.
- Add `CantileverParameters` and `run_cantilever_benchmark` only after the elastic solver layer is proven.
- Matrix coverage is `TL/UL x SVK/Neo-Hookean x Hex8/Tet10/Hex20`.
- Keep local smoke settings separate from nightly/full mesh settings.

## Should Know

- Beam-theory tip displacement is the acceptance reference.
- Do not widen shared benchmark result schemas.

## Allowed Deviations

- The plan allows configurable mesh sizes so local tests can remain smoke-sized while nightly runs the full matrix.

## Downstream Impact

- Completion contributes the cantilever prerequisite for the final performance harness.

