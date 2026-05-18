# Phase 2 Task Analysis

## Task Scoring

| Task ID | Title | Complexity (1-5) | Risk (1-5) | Combined Score | Blocked By | Blocks | Model |
|---------|-------|-----------------|------------|----------------|------------|--------|-------|
| P2-T1 | Implement extract_einsum_specs() | 2 | 1 | 3 | — | P2-T2 | Sonnet 4.6 |
| P2-T2 | Refactor fe_localise + update exports | 2 | 3 | 5 | P2-T1 | P2-T3, P4-T1 | Sonnet 4.6 |
| P2-T3 | Write einsum extraction tests | 2 | 1 | 3 | P2-T2 | — | Sonnet 4.6 |

## Execution Order

1. **P2-T1** (no blockers) — first
2. **P2-T2** (blocked by P2-T1, risk=3 → sequential) — after P2-T1 verified
3. **P2-T3** (blocked by P2-T2) — after P2-T2 verified

## Rationale

- P2-T1 is a straightforward code move with a new signature — low risk
- P2-T2 is the riskiest: removes ~100 lines from fe_localise.py and replaces with delegation — must verify all existing tests pass
- P2-T3 is test-only, depends on both implementations being in place
- All sequential due to strict dependency chain
