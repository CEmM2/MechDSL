# Phase 5 Tasks Analysis

| Task ID | Title | Complexity (1-5) | Risk (1-5) | Combined Score | Blocked By | Blocks | Model |
|---------|-------|-----------------|------------|----------------|------------|--------|-------|
| P5-T1 | Audit symbolic (S1-S9) + parser (P1-P6) | 2 | 1 | 3 | P1-T3 (done), P2-T8 (done) | P5-T4 | Sonnet 4.6 |
| P5-T2 | Audit IR (M1-M6), Element (E1-E6), Einsum (N1-N5) | 2 | 1 | 3 | — | P5-T4 | Sonnet 4.6 |
| P5-T3 | Audit Backend (T1-T4), BC (B1-B5), Artifact (A1-A3), Emission (C1-C3) | 2 | 1 | 3 | P4-T6 (done) | P5-T4 | Sonnet 4.6 |
| P5-T4 | Create verification matrix | 1 | 1 | 2 | P5-T1, P5-T2, P5-T3 | — | Sonnet 4.6 |

## Execution Order

**Parallel batch 1**: P5-T1, P5-T2, P5-T3 (all blockers resolved, all complexity ≤ 3 and risk ≤ 3)
**Sequential after batch 1**: P5-T4 (depends on all three audit tasks)

## Notes

- All Phase 5 tasks are audit/documentation tasks — no new source code created
- Gap-filling tests are the primary code output
- Scaffold stubs exist in `test_verification_gaps_p5t2.py` (5 stubs) and `test_verification_gaps_p5t3.py` (2 stubs)
- P5-T1 has no stubs — all S-IDs covered, P3/P4 deferred per plan
