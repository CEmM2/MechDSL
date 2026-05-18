# Phase 2 Task Analysis

## Complexity and Risk Assessment

| Task ID | Title | Complexity (1-5) | Risk (1-5) | Combined Score | Blocked By | Blocks | Model |
|---------|-------|:-:|:-:|:-:|------------|--------|-------|
| R3.2.1 | CG/PCG breakdown warning (C3) | 1 | 1 | 2 | — | — | Any |
| R3.2.2 | J2 radial_return stall guard (H3) | 2 | 2 | 4 | — | R3.5.1 | Any |
| R3.2.3 | Emitted CG failure counter (H4) | 2 | 2 | 4 | — | R3.6.1 | Any |
| R3.2.4 | Einsum FLOPS sentinel (H5) | 1 | 2 | 3 | — | — | Any |
| R3.2.5 | Ref elastic Newton non-convergence (H6) | 1 | 1 | 2 | — | R3.6.1 | Any |
| R3.2.6 | Boundary codegen guards (H7+H8) | 2 | 1 | 3 | — | R3.5.2 | Any |

## Execution Strategy

All 6 tasks are unblocked and have complexity ≤ 3, risk ≤ 3. All modify DIFFERENT files (except R3.2.3 which shares taichi_printer.py with Phase 1, already complete). Can dispatch all 6 in parallel.

## Existing Test Update Required
- `test_einsum_optimizer.py:206` asserts `estimated_flops > 0.0` — must update after H5 changes sentinel to -1.0
