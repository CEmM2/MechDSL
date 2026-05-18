# Phase 2 Task Analysis

| Task ID | Title | Complexity (1-5) | Risk (1-5) | Combined Score | Blocked By | Blocks |
|---------|-------|-----------------|------------|----------------|------------|--------|
| P2-1 | Covariant/contravariant bases + metric tensors | 3 | 2 | 5 | P1-1 (done) | P2-2, P2-4 |
| P2-2 | Christoffel symbols from metric | 3 | 2 | 5 | P2-1 | P2-3, P2-4 |
| P2-3 | Covariant derivatives (vectors and tensors) | 3 | 3 | 6 | P2-2 | P2-5 |
| P2-4 | NRPyLaTeX metric-assignment directives | 3 | 2 | 5 | P2-1, P2-2 | P2-5 |
| P2-5 | Curvilinear patch test + Cartesian equivalence | 4 | 4 | 8 | P2-3, P2-4 | P10-1 |

## Model Assignment

- P2-1 (combined 5): **Sonnet 4.6** — well-understood math, extends existing module
- P2-2 (combined 5): **Sonnet 4.6** — SymPy symbolic differentiation, known closed forms
- P2-3 (combined 6): **Sonnet 4.6** — index gymnastics but formula is textbook
- P2-4 (combined 5): **Sonnet 4.6** — follows existing directive parser pattern
- P2-5 (combined 8, >6): **Opus 4.6 only** — curvilinear mesh construction, Newton solve, subtle BCs

## Execution Order

1. **P2-1** — no in-phase blockers (P1-1 done), gates P2-2 and P2-4
2. **P2-2** — blocked by P2-1, gates P2-3 and P2-4
3. **P2-3 ∥ P2-4** — can run in parallel after P2-2 completes (no file scope overlap: P2-3 touches convected.py + test_convected_curvilinear.py; P2-4 touches directives.py + test_metric_assign_directives.py)
4. **P2-5** — blocked by both P2-3 and P2-4, high-risk, Opus-only

## Parallel Analysis

P2-3 and P2-4 are candidates for parallel dispatch:
- P2-3 deliverables: `convected.py`, `test_convected_curvilinear.py`
- P2-4 deliverables: `directives.py`, `test_metric_assign_directives.py`, `test_frontend_parser.py`
- No file overlap → safe to parallelize

## Prior Phase Patterns

Phase 1 gate history shows clean execution — all 7 tasks passed on first attempt for all three gates. Two minor scope-drift issues (m1 on P1-2 YAGNI, m1+m2 on P1-5 direct rates). No physics errors, no integration breaks.
