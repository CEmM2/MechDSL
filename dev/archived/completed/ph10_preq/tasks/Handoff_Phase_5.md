# Handoff to Phase 5

Phase 4 completed the internal elastic benchmark solver layer required before
exposing the public cantilever benchmark.

## Completed Inputs

- P4-1 is done. Internal elastic solver contracts now cover TL/UL formulation
  selection, SVK/Neo-Hookean material dispatch, and benchmark-local result data.
- P4-2 is done. SVK and Neo-Hookean smoke cells run for Hex8, Tet10, and Hex20,
  and representative runtime data is captured in `ElasticSolveResult.wallclock_s`.

## Evidence

- `uv run pytest packages/mechdsl-core/tests/test_phase10_elastic_solver.py -v` -> 9/9 passed.
- `uv run ruff check packages/mechdsl-core/src/mechdsl/verify/benchmarks/_elastic_solver.py packages/mechdsl-core/tests/test_phase10_elastic_solver.py` -> clean.
- `uv run mypy packages/mechdsl-core/src/mechdsl/verify/benchmarks/_elastic_solver.py` -> clean.

## Phase 5 Notes

- Phase 5 can build `run_cantilever_benchmark` on top of
  `run_elastic_cantilever_smoke` or promote only the necessary internals.
- Keep smoke and nightly sizing separate; phase 4 runtime tests prove local
  feasibility only.
- No public benchmark API was changed in phase 4.
