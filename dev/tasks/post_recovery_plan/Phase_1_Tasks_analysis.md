# Phase 1 Tasks Analysis

| Task ID | Title | Complexity (1-5) | Risk (1-5) | Combined Score | Blocked By | Blocks |
|---------|-------|-----------------|------------|----------------|------------|--------|
| P1-1 | Extend BoundaryCondition IR slot | 2 | 2 | 4 | — | P1-2, P1-3 |
| P1-2 | Extend Neumann directive parser | 2 | 2 | 4 | P1-1 | P1-3 |
| P1-3 | Lower Neumann BC to per-node forces | 4 | 3 | 7 | P1-1, P1-2 | P1-4 |
| P1-4 | Emit f_ext init Taichi kernel | 4 | 4 | 8 | P1-3 | P1-5, P1-7 |
| P1-5 | Façade compile_latex extension | 3 | 3 | 6 | P1-4 | P1-6 |
| P1-6 | Replace numeric f_ext injection in test_p7_2 | 2 | 2 | 4 | P1-5 | — |
| P1-7 | Golden test test_boundary_neumann.py | 2 | 2 | 4 | P1-4 | — |

**Model assignments:**
- P1-3 (score 7): Opus 4.6 only (combined > 6)
- P1-4 (score 8): Opus 4.6 only (combined > 6)
- P1-5 (score 6): Sonnet 4.6 or Opus 4.6 (complexity 3)
- P1-1, P1-2, P1-6, P1-7 (score 4): Sonnet 4.6 or Opus 4.6 (risk 2 acceptable lower bound, but plan facade contract demands care)

**Execution order:** Strictly sequential. Chain is a single critical path: P1-1 → P1-2 → P1-3 → P1-4 → {P1-5, P1-7 in parallel} → P1-6.

**Parallel opportunities:** P1-5 and P1-7 have non-overlapping file scopes after P1-4 lands — P1-7 touches only `tests/test_boundary_neumann.py` and `tests/golden/`, P1-5 touches only `src/mechdsl/__init__.py`. Eligible for parallel dispatch (both ≤3 complexity, ≤3 risk).

**Recurring failure-pattern scan:** No prior phase gate files exist for this plan. Cross-plan scan flagged `physics_error` patterns from earlier MechDSL plans around BC enforcement; relevant for P1-3.
