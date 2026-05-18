# Phase 2 Task Analysis — Analytical Solutions & Frontend Stubs

| Task ID | Title | Complexity (1-5) | Risk (1-5) | Combined Score | Blocked By | Blocks | Model |
|---------|-------|-----------------|------------|----------------|------------|--------|-------|
| P2-T1 | Implement patch_test_reference() | 2 | 2 | 4 | — | P2-T5, P3-T4 | Sonnet |
| P2-T2 | Implement rigid_body_reference() | 2 | 1 | 3 | — | P2-T5, P3-T4 | Sonnet |
| P2-T3 | Implement cantilever_euler_bernoulli() | 1 | 1 | 2 | — | P2-T5 | Sonnet |
| P2-T4 | Implement uniaxial_tension_hardening() | 3 | 2 | 5 | — | P2-T5, P4-T5 | Sonnet |
| P2-T5 | Write analytical solution tests | 2 | 1 | 3 | P2-T1..T4 | — | Sonnet |
| P2-T6 | Implement frontend.build_context() | 2 | 2 | 4 | — | P2-T7, P2-T8 | Sonnet |
| P2-T7 | Implement build_context validation | 2 | 1 | 3 | P2-T6 | P2-T8 | Sonnet |
| P2-T8 | Write frontend tests | 2 | 1 | 3 | P2-T6, P2-T7 | — | Sonnet |

## Execution Plan

**Parallel batch 1 (5 root tasks, all complexity ≤ 3, risk ≤ 3):**
- P2-T1, P2-T2, P2-T3, P2-T4, P2-T6

**Sequential after batch 1:**
- P2-T5 (after T1-T4 verified)
- P2-T7 (after T6 verified)
- P2-T8 (after T7 verified)

## Notes
- No task exceeds combined score 6 → no Opus-only requirements
- P2-T4 has complexity 3 → Sonnet minimum (Sonnet assigned)
- P2-T4 is the most complex: implicit solve via Brent's method for J2 hardening law
- P2-T4 is critical path: Phase 4 J2 E2E test depends on it
