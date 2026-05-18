# Phase 5 Tasks Analysis

**Plan:** `dev/design_docs/PLAN-B.md`
**Branch:** `plan-b_phase-5`
**Baseline (before execution):** 1149 passed + 34 Phase 5 stub skips + 1 expected failure on `test_phase6_exit::test_no_resolved_todos_or_fixmes_remain` (auto-clears when all P5-* TODOs resolve).

## Complexity / Risk Scoring

| Task ID | Title | Complexity (1-5) | Risk (1-5) | Combined | Blocked By | Blocks |
|---------|-------|------------------|------------|----------|------------|--------|
| P5-1 | Tet4 (4-node linear, 1-pt) | 2 | 2 | 4 | P1-1 (soft) | P5-6, P5-7 |
| P5-2 | Tet10 (10-node quadratic, 4-pt) | 3 | 3 | 6 | P1-1 (soft) | P5-6, P5-7, P10-2, P10-3 |
| P5-3 | Hex20 (20-node serendipity, 27-pt) | 3 | 3 | 6 | P1-1 (soft) | P5-6, P5-7, P10-2, P10-5 |
| P5-4 | Hex8 reduced (1-pt) | 2 | 2 | 4 | P1-1 (soft) | P5-5, P5-6, P10-7 |
| P5-5 | Flanagan-Belytschko hourglass | 4 | 4 | 8 | P5-4 | P5-6, P5-7, P10-7 |
| P5-6 | ElementFactory (uniform API) | 2 | 3 | 5 | P5-1, P5-2, P5-3, P5-5 | P5-7, P9-1 |
| P5-7 | Patch test for all elements | 3 | 3 | 6 | P5-6 | P9-1, P10-1 |

## Model Assignment

| Task | Minimum model | Rationale |
|------|---------------|-----------|
| P5-1 | Sonnet 4.6 | score 4 (unit, well-known kernel) |
| P5-2 | Sonnet 4.6 | score 6 (quadrature transcription risk) |
| P5-3 | Sonnet 4.6 | score 6 (JIT budget monitoring) |
| P5-4 | Sonnet 4.6 | score 4 (variant of existing Hex8) |
| P5-5 | **Opus 4.6** | score 8 > 6 — sign conventions + physical subtlety |
| P5-6 | Sonnet 4.6 | score 5 (API stability matters, but mechanics are simple) |
| P5-7 | Sonnet 4.6 | score 6 (integration across four new element types) |

## Cross-phase blocker note

All four of P5-1, P5-2, P5-3, P5-4 are nominally blocked by P1-1 (ConfigurationIR UL extension). Phases 2-4 were executed despite the same nominal block because the new features (convected coords, viscoplastic, hyperelastic) extend TL kinematics without requiring UL. Phase 5 follows the same pattern: element topology + integration rules are orthogonal to formulation, so Phase 5 proceeds on the TL baseline. P1-1 remains a downstream requirement for P10-2 (TL/UL cantilever matrix) and P10-7 (UL Taylor impact).

## Execution Order

Within-phase dependencies force sequential execution of the final three tasks; the first four modify shared files (`element_ir.py`, `mechanics_ir.py`, `taichi_printer.py`) so they must also run sequentially to avoid merge conflicts.

1. **P5-1 Tet4** → commit → verify
2. **P5-2 Tet10** → commit → verify
3. **P5-3 Hex20** → commit → verify
4. **P5-4 Hex8 reduced** → commit → verify
5. **P5-5 FB hourglass** (blocked by P5-4) → commit → verify
6. **P5-6 ElementFactory** (blocked by P5-1..P5-3, P5-5) → commit → verify
7. **P5-7 Patch test all elements** (blocked by P5-6) → commit → verify → Phase 5 handoff

No parallel batching — every task touches the shared element-IR surface.
