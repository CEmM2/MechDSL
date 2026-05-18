# Phase 3 Task Analysis

## Task Scoring

| Task ID | Title | Complexity (1-5) | Risk (1-5) | Combined Score | Blocked By | Blocks | Model |
|---------|-------|-----------------|------------|----------------|------------|--------|-------|
| P3-T1 | Implement newton_solve() | 3 | 3 | 6 | — | P3-T2, P3-T3 | Sonnet 4.6 |
| P3-T2 | Newton driver unit tests | 3 | 2 | 5 | P3-T1 | P6-T1 | Sonnet 4.6 |
| P3-T3 | Newton + load_stepping integration test | 4 | 3 | 7 | P3-T1 | P6-T1 | **Opus 4.6** |

## Execution Order

All sequential due to strict dependency chain:
1. **P3-T1** (risk=3 → sequential) — implements newton_solve()
2. **P3-T2** (blocked by P3-T1) — unit tests
3. **P3-T3** (blocked by P3-T1, combined > 6 → Opus only) — integration test against reference

## Rationale

- P3-T1 is the most substantial new code in the sprint (~200 lines). Callback design must match reference patterns exactly.
- P3-T2 requires understanding the reference solver assembly to build callbacks for unit tests.
- P3-T3 is the highest-risk task: numerical comparison against ref_hex8_plastic at atol=1e-10. Must use Opus for implementation.
