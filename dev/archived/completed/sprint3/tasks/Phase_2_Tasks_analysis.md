# Phase 2 Task Analysis

**Plan:** `dev/plans/sprint3.md`
**Phase:** Cook's Membrane -- Trapezoidal Mesh & J2 Benchmark

## Task Assessment

| Task ID | Title | Complexity (1-5) | Risk (1-5) | Combined Score | Blocked By | Blocks | Model |
|---------|-------|------------------|------------|----------------|------------|--------|-------|
| P2-1 | Implement generate_cook_membrane_mesh() | 2 | 2 | 4 | -- | P2-2, P2-3, P5-2 | Sonnet 4.6 |
| P2-2 | Test trapezoidal mesh geometry | 1 | 1 | 2 | P2-1 | P2-3 | Sonnet 4.6 |
| P2-3 | Cook's membrane benchmark with J2 and reference | 4 | 4 | 8 | P2-1, P2-2 | P4-1 | **Opus 4.6** |

## Model Assignment Rationale

- **P2-1** (score 4): Straightforward mesh generation following existing `generate_hex8_mesh` pattern. Y-coordinate warping is simple algebra. Sonnet 4.6.
- **P2-2** (score 2): Fleshing out existing test stubs -- mechanical, low risk. Sonnet 4.6.
- **P2-3** (score 8 > 6): Complex integration task requiring J2 plasticity solve, self-converged reference generation, and 2% tolerance comparison. Multiple physics decisions (load stepping, convergence, tip displacement extraction). **Opus 4.6 only** per model assignment rules.

## Execution Order

All tasks are sequential due to dependency chain:

1. **P2-1** (no blockers) -- mesh generator, gates everything
2. **P2-2** (blocked by P2-1) -- test stubs become real tests
3. **P2-3** (blocked by P2-1, P2-2) -- J2 benchmark, high-risk, sequential

No parallel dispatch possible: P2-2 and P2-3 both depend on P2-1, and they share test files.

## Phase 1 Failure Patterns to Watch For

From `gates/phase_1_gates.md`:
- **P1-4 physics_error**: Tolerance 1e-12 too tight for reference solver float64 Gauss quadrature roundoff. Resolution: relaxed to 1e-9 with documented justification.
- **Lesson**: When setting tolerance assertions for reference solver output, account for float64 roundoff accumulation on multi-element assembly. The reference solver produces O(1e-10) roundoff on multi-element meshes with steel-like material parameters.

## Key Design Decisions (from context summary and handoff)

- nu=0.3 (not 0.4999) to avoid Hex8 volumetric locking
- Self-converged fine-mesh reference instead of literature values
- 2% tolerance against own reference
- Y-coordinate warping formula: `y_warped = y * (44 - 28*x/48) / 44`
