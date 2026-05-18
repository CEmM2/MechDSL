# Phase 4 Task Analysis — J2 Plasticity E2E Integration

| Task ID | Title | Complexity (1-5) | Risk (1-5) | Combined Score | Blocked By | Blocks | Model |
|---------|-------|-----------------|------------|----------------|------------|--------|-------|
| P4-T1 | Audit J2 constitutive emission | 3 | 3 | 6 | — | P4-T5 | Sonnet/Opus |
| P4-T2 | Validate FD tangent for J2 | 3 | 4 | **7** | — | P4-T5 | **Opus** |
| P4-T3 | Verify history field emission | 3 | 3 | 6 | — | P4-T5 | Sonnet/Opus |
| P4-T4 | Verify numerical safeguards | 2 | 2 | 4 | — | P4-T5 | Any |
| P4-T5 | Create test_e2e_plastic.py | 4 | 5 | **9** | P4-T1..T4, P2-T4 | P4-T6 | **Opus** |
| P4-T6 | Compare generated vs reference | 3 | 4 | **7** | P4-T5 | P4-T7 | **Opus** |
| P4-T7 | Validate/update golden file | 1 | 2 | 3 | P4-T6, P1-T5 | — | Any |

## Execution Order

1. **Parallel first pass** (complexity ≤ 3 AND risk ≤ 3): P4-T1, P4-T3, P4-T4
2. **Sequential high-risk**: P4-T2 (risk=4)
3. **Dependency chain**: P4-T5 → P4-T6 → P4-T7

## Notes

- P4-T1 through P4-T4 are audit/analysis tasks — primary deliverables are findings + potential fixes
- P4-T5 (combined 9) is the sprint's primary deliverable and highest-risk single task
- P4-T2 concerns (FD tangent alpha corruption) directly inform P4-T5's implementation
- P2-T4 dependency is already satisfied (done in Phase 2)
- P1-T5 dependency for P4-T7 is already satisfied (done in Phase 1)
