# Phase 6 Task Analysis

| Task ID | Title | Complexity (1-5) | Risk (1-5) | Combined Score | Blocked By | Blocks | Model |
|---------|-------|-----------------|------------|----------------|------------|--------|-------|
| P6-T1 | Create E2E Taichi smoke test | 4 | 4 | 8 | P3-T2, P3-T3, P5-T3 (all done) | P6-T2 | Opus 4.6 |
| P6-T2 | CI integration for slow tests | 1 | 1 | 2 | P6-T1 | -- | Haiku / self |

## Rationale

### P6-T1 (Complexity 4, Risk 4)
- **Complexity**: Must wire the full pipeline (compile -> emit -> write -> importlib import -> Taichi JIT -> newton_solve -> compare). Involves understanding generated module API, reference solver API, mesh/BC setup, and Lame parameter handling (known issue from handoff: emit_main emits lam=0/mu=0).
- **Risk**: Taichi JIT may behave differently than expected. The generated module's internal API may not match assumptions. The lam/mu parameter gap requires careful handling.
- **Combined > 6 -> Opus 4.6 required.**

### P6-T2 (Complexity 1, Risk 1)
- **Complexity**: Add a YAML job to existing CI. Pytest markers already registered.
- **Risk**: Minimal -- adding a CI job is well-understood.
- **Can be done inline (no subagent needed).**

## Execution Order

1. P6-T1 (sequential, high-risk, Opus 4.6)
2. P6-T2 (after P6-T1 verified, inline)
