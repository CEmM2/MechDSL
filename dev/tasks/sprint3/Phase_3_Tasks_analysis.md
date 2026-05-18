# Phase 3 Task Analysis

| Task ID | Title | Complexity (1-5) | Risk (1-5) | Combined Score | Model | Blocked By | Blocks |
|---------|-------|-----------------|------------|----------------|-------|------------|--------|
| P3-1 | Necking bar mesh generator | 3 | 2 | 5 | Sonnet 4.6 | -- | P3-2, P3-3, P3-4 |
| P3-2 | Mesh geometry tests | 2 | 1 | 3 | Sonnet 4.6 | P3-1 | P3-4 |
| P3-3 | Self-converged reference data | 3 | 3 | 6 | Sonnet 4.6 | P3-1 | P3-4 |
| P3-4 | Necking bar benchmark (MVP) | 4 | 4 | 8 | **Opus 4.6** | P3-1, P3-2, P3-3 | P4-1 |

## Execution Order

1. **P3-1** (sequential) — no blockers, unblocks everything
2. **P3-2 + P3-3** (parallel) — both complexity ≤ 3 AND risk ≤ 3, no file overlap
3. **P3-4** (sequential, Opus) — high complexity + risk, MVP acceptance criterion

## Previous Phase Failure Patterns

- Phase 1 Gate A: physics_error — tolerance 1e-12 too tight for multi-element Gauss quadrature (O(1e-10) roundoff). **Relevant to P3-2 (mesh Jacobian tests) and P3-4 (2% benchmark).**
