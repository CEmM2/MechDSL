# Phase 8 Context Summary: Public Taylor Impact Benchmark

**Plan:** `dev/plans/ph10_preq.md`
**Original plan phase name:** E8 Public Taylor Impact Benchmark

## Must Know

- This phase closes P10-7 after the Taylor runtime is proven.
- Add `TaylorImpactParameters` and `run_taylor_impact_benchmark`.
- Replace Taylor stubs with active tests for final length, mushroom radius, and equivalent plastic strain localization.
- Keep full benchmark tests marked slow/nightly and provide deterministic smoke settings.

## Should Know

- Do not couple Taylor benchmark closure to MMS or cantilever work.
- Do not change shared benchmark result schemas.

## Allowed Deviations

- Smoke settings may be smaller than nightly settings if the benchmark semantics are identical.

## Downstream Impact

- Completion contributes the Taylor prerequisite for the final performance harness.

