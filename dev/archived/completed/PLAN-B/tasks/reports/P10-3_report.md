# Task P10-3: Cook's membrane benchmark (TL x J2 x Hex8) — Complete

**Task completed via user-approved rescope.**

## Implementation Summary

Added a reusable Cook's membrane harness at
`packages/mechdsl-core/src/mechdsl/verify/benchmarks/cook_membrane.py` and
exported it from `mechdsl.verify.benchmarks`. The harness wraps the existing
handwritten TL + J2 + Hex8 reference solver via dependency injection, locks the
benchmark to the committed `2x2x1` Hex8 mesh + 100 N shear + 10 load-step setup,
and returns a standard `BenchmarkResult`.

The task-specific benchmark file
`packages/mechdsl-core/tests/test_benchmarks_cook_membrane_matrix.py` is no
longer a 4-skip placeholder. It now exercises the public harness and checks:
1. mean tip displacement within 2% of the committed Cook reference
2. Newton convergence at every load step

## Gate History

**Gate A:** 2 attempts -> Pass after rescope
**Gate B:** 1 attempt -> Pass
**Gate C:** 15/15 verification checks passed

Attempt 1 failed against the original 4-cell `(TL/UL) x (Hex8/Tet10)` matrix
because the repository still lacks a handwritten UL plastic reference kernel and
the Tet10 benchmark path was not part of the runnable benchmark surface. The
user then approved the narrower TL + J2 + Hex8 rescope, after which the task
passed cleanly.

## Files Changed

| File | Change |
|------|--------|
| `packages/mechdsl-core/src/mechdsl/verify/benchmarks/cook_membrane.py` | New reusable Cook benchmark harness with locked parameters and regression metadata |
| `packages/mechdsl-core/src/mechdsl/verify/benchmarks/__init__.py` | Exported the Cook harness from the public benchmark API |
| `packages/mechdsl-core/tests/test_benchmarks_cook_membrane_matrix.py` | Replaced the 4-skip stub matrix with two real TL + J2 + Hex8 regression tests |
| `dev/tasks/PLAN-B/json/P10-3.json` | Recorded the approved rescope and final verification results |
| `dev/tasks/PLAN-B/all-tasks.md` | Updated the task index title to match the new scope |
| `dev/tracking/tasks-tracker_PLAN-B.md` | Marked P10-3 done with verification evidence |
| `dev/tasks/PLAN-B/gates/phase_10_gates.md` | Replaced the blocked-only record with the final rescope + completion history |

## Test Evidence

- `uv run pytest packages/mechdsl-core/tests/test_benchmarks_cook_membrane_matrix.py -v` -> **2 passed** in 2.38s
- `uv run pytest packages/mechdsl-core/tests/test_benchmarks.py -k cook -v` -> **4 passed**, 22 deselected in 2.39s
- `uv run pytest packages/mechdsl-core/tests/test_phase6_exit.py -v` -> **9 passed** in 0.40s
- `uv run mypy packages/mechdsl-core/src/mechdsl/verify/benchmarks` -> **success: no issues found in 7 source files**
- `uv run ruff check packages/mechdsl-core/src/mechdsl/verify/benchmarks packages/mechdsl-core/tests/test_benchmarks_cook_membrane_matrix.py` -> **clean**

## Scope Note

This completion closes the user-approved TL + J2 + Hex8 Cook benchmark slice.
UL plastic and Tet10 benchmark cells remain out of scope for this task after
the respecification.
