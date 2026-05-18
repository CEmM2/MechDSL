# Phase 1 Task Analysis

| Task ID | Title | Complexity (1-5) | Risk (1-5) | Combined Score | Blocked By | Blocks |
|---------|-------|-----------------|------------|----------------|------------|--------|
| P1-T1 | Fix emit_main E/nu → Lamé conversion | 2 | 3 | 5 | — | P1-T5, P1-T6 |
| P1-T2 | Implement convected coordinate functions | 1 | 1 | 2 | — | P1-T3, P1-T4 |
| P1-T3 | Write convected coordinate tests | 1 | 1 | 2 | P1-T2 | — |
| P1-T4 | Update convected exports | 1 | 1 | 2 | P1-T2 | — |
| P1-T5 | Regenerate golden files after emit_main fix | 1 | 2 | 3 | P1-T1 | P4-T7 |
| P1-T6 | Write emit_main Lamé conversion test | 2 | 1 | 3 | P1-T1 | — |

## Model Assignment

All tasks have combined score ≤ 5 and no individual dimension ≥ 3 (except P1-T1 risk=3).

- **P1-T1** (risk=3): Sonnet 4.6 or Opus 4.6
- **P1-T2, P1-T3, P1-T4**: Sonnet 4.6 (all trivial)
- **P1-T5, P1-T6**: Sonnet 4.6

## Execution Order

**Parallel first pass (no blockers, all ≤3 complexity and ≤3 risk):**
- P1-T1 (no blockers)
- P1-T2 (no blockers)

**After P1-T1 completes:**
- P1-T5, P1-T6 (parallel, both depend only on P1-T1)

**After P1-T2 completes:**
- P1-T3, P1-T4 (parallel, both depend only on P1-T2)
