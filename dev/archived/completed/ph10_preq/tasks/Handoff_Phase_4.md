# Handoff to Phase 4

Phase 3 completed Cook and necking original-scope closure without changing
`BenchmarkResult`, `ElementFactory`, frontend, or codegen APIs.

## Completed Inputs

- P3-1 Cook membrane matrix closure is done. The public runner now accepts
  `formulation` and `element_type` while preserving the existing TL Hex8
  reference default.
- P3-2 necking UL closure is done. The previous UL skip is removed, the UL
  benchmark cell is active, and a benchmark-local UL J2 smoke-history path is
  covered.

## Evidence

- `uv run pytest packages/mechdsl-core/tests/test_benchmarks_cook_membrane_matrix.py packages/mechdsl-core/tests/test_benchmarks_necking_bar_matrix.py -v` -> 10/10 passed.
- `uv run ruff check packages/mechdsl-core/src/mechdsl/verify/benchmarks/cook_membrane.py packages/mechdsl-core/src/mechdsl/verify/benchmarks/necking_bar.py packages/mechdsl-core/tests/test_benchmarks_cook_membrane_matrix.py packages/mechdsl-core/tests/test_benchmarks_necking_bar_matrix.py` -> clean.
- `uv run mypy packages/mechdsl-core/src/mechdsl/verify/benchmarks/cook_membrane.py packages/mechdsl-core/src/mechdsl/verify/benchmarks/necking_bar.py` -> clean.

## Phase 4 Notes

- The elastic solver layer should remain internal and avoid public cantilever exports.
- Phase 4 can consume the existing Phase 1 mesh utilities directly.
- No phase 3 changes require touching `BenchmarkResult` or shared frontend/codegen APIs.
