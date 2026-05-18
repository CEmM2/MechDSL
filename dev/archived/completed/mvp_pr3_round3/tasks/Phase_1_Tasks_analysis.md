# Phase 1 Task Analysis

## Complexity and Risk Assessment

| Task ID | Title | Complexity (1-5) | Risk (1-5) | Combined Score | Blocked By | Blocks | Model |
|---------|-------|:-:|:-:|:-:|------------|--------|-------|
| R3.1.1 | Fix J2 Newton ti.static → runtime (C1) | 1 | 1 | 2 | — | R3.6.1 | Any |
| R3.1.2 | Fix quadrature loop to ti.static (C2) | 2 | 2 | 4 | — | R3.1.5, R3.6.1 | Any |
| R3.1.3 | Emit RuntimeError on non-convergence (C4) | 2 | 2 | 4 | — | R3.6.1 | Any |
| R3.1.4 | Add NaN/Inf guard in emitted Newton driver (C4b) | 1 | 2 | 3 | R3.1.8 | R3.6.1 | Any |
| R3.1.5 | Change node loops to runtime (C5) | 2 | 3 | 5 | R3.1.2 | R3.6.1 | Sonnet+ |
| R3.1.6 | Add material model validation in emit() (H9) | 1 | 1 | 2 | — | R3.6.1 | Any |
| R3.1.7 | Add emitted J2 convergence check (H1) | 3 | 3 | 6 | — | R3.1.4, R3.6.1 | Sonnet+ |
| R3.1.8 | Add emitted J2 negative dl guard (H2) | 1 | 1 | 2 | R3.1.7 | R3.1.4, R3.6.1 | Any |
| R3.1.9 | Fix comments + rename (CM3-7) | 2 | 2 | 4 | — | R3.6.1 | Any |
| R3.1.10 | Update convention docs | 1 | 1 | 2 | R3.1.2 | — | Any |

## Execution Strategy

**All 9 code tasks (R3.1.1–R3.1.9) modify the same file** (`taichi_printer.py`). Parallel dispatch would cause merge conflicts. Strategy: implement all 9 as a single coordinated pass, respecting the internal dependency chain:

1. **Batch A** (unblocked, parallel-safe since different line ranges): R3.1.1, R3.1.2, R3.1.3, R3.1.6, R3.1.9
2. **Batch B** (depends on A): R3.1.5 (needs R3.1.2), R3.1.7 (unblocked but prerequisite for C)
3. **Batch C** (depends on B): R3.1.8 (needs R3.1.7)
4. **Batch D** (depends on C): R3.1.4 (needs R3.1.8)
5. **Separate**: R3.1.10 (convention docs, needs R3.1.2)

Since all are in the same file, the practical approach is a single agent pass implementing all changes top-to-bottom, then updating existing tests.

## Existing Test Updates Required

5 existing test assertions must be updated alongside the code changes:
1. `test_plastic_emission.py:114` — ti.static(range(20)) → range(20) [C1]
2. `test_taichi_printer.py:229` — range(N_QP) → ti.static(range(N_QP)) [C2]
3. `test_taichi_printer.py:220,232-234` — N_NODES static → runtime [C5]
4. `test_emission_verification.py:371-373` — node loop ti.static → runtime [C5]
