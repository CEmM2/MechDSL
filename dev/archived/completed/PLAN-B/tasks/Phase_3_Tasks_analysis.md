# Phase 3 Task Analysis

| Task ID | Title | Complexity (1-5) | Risk (1-5) | Combined Score | Blocked By | Blocks | Model |
|---------|-------|-----------------|------------|----------------|------------|--------|-------|
| P3-1 | Perzyna viscoplasticity | 3 | 2 | 5 | P1-1 (done) | P3-2, P3-3 | Sonnet 4.6 |
| P3-2 | Johnson-Cook flow stress + thermal | 4 | 3 | 7 | P3-1 | P3-3, P3-4 | Opus 4.6 |
| P3-3 | Consistent viscoplastic tangent | 4 | 4 | 8 | P3-2 | P3-4 | Opus 4.6 |
| P3-4 | Acceptance tests | 2 | 1 | 3 | P3-3 | P10-7 | Sonnet 4.6 |

## Execution Order

All tasks form a linear chain: P3-1 → P3-2 → P3-3 → P3-4. No parallelism possible.

- P3-1: Sonnet — follows J2 pattern closely, complexity=3 from Newton iteration
- P3-2: Opus — coupled 2D Newton with thermal, score > 6
- P3-3: Opus — tangent derivation from implicit differentiation, highest risk (silent degradation)
- P3-4: Sonnet — acceptance suite using completed APIs, straightforward

## Risk patterns from Phase 1+2

- `test_gap` was the most common Gate A failure mode — implementers test acceptance criteria but miss code branches
- `physics_error` hit P2-1 (wrong formula F^T G F vs G^T C G) — constitutive formula verification is critical
- P3-3 tangent is the highest-risk task: wrong tangent silently degrades Newton convergence. FD check is the primary safeguard.
