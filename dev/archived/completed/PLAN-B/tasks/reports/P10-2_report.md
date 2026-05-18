# Task P10-2: Cantilever benchmark matrix — Blocked at Gate A

The original task scope is still:

- formulations: `TL`, `UL`
- materials: `svk`, `neo_hookean`
- elements: `Hex8`, `Tet10`, `Hex20`
- acceptance: all 12 cells within 5% of Euler-Bernoulli beam theory

I did not implement code for this task because the current repository surface is
not yet an honest execution path for that matrix.

## Why it is blocked

The task-specific file
`packages/mechdsl-core/tests/test_benchmarks_cantilever_matrix.py` is still a
12-cell skip stub. There is no public `run_cantilever_benchmark` harness under
`mechdsl.verify.benchmarks`, no reusable Tet10 cantilever mesh builder, and no
generic UL benchmark-local cantilever path beyond the handwritten Hex8 + SVK
reference solver in `tests/ref/ref_hex8_ul.py`.

This is not just missing glue code. The only refined executable benchmark slice
already available in the repo is the Hex8 TL benchmark in
`tests/test_benchmarks.py::TestCantilever::test_tip_displacement_within_5_percent`,
and on this machine that single cell was still running past 100 seconds during
gate evaluation. Treating the full 12-cell matrix as a routine benchmark patch
would understate both the missing infrastructure and the runtime cost.

## Evidence collected

- `uv run pytest packages/mechdsl-core/tests/test_benchmarks_cantilever_matrix.py -v`
  -> `12 skipped in 0.02s`
- `uv run pytest packages/mechdsl-core/tests/test_ul_equivalence.py::TestTaskP1_7::test_tl_vs_ul_cantilever_equivalence -q`
  -> `1 passed in 3.18s`
- `uv run pytest packages/mechdsl-core/tests/test_benchmarks.py::TestCantilever::test_tip_displacement_within_5_percent -q`
  -> still running past 100s for one refined Hex8 cell during the gate-evaluation window

## Gate result

- Gate A: fail
- Gate B: not run
- Gate C: fail

The task remains pending. The two honest recovery paths are:

1. rescope P10-2 to an executable subset, or
2. create a dedicated enablement task for a generic cantilever benchmark
   surface covering mesh generation and TL/UL hyperelastic solves across the
   required element families.
