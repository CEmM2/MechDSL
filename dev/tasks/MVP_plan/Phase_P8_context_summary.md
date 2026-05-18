# Phase 8 — Plasticity Runtime Integration: Context Summary

## Must Know

### Conventions
- **Von Mises guard**: `sigma_eq < 1e-12 * sigma_y` → treat as elastic (skip return mapping). Ref: `07-CONVENTIONS.md §6`.
- **Plastic multiplier**: `delta_lambda >= -1e-15` (allow tiny negative from Newton). Ref: `07-CONVENTIONS.md §6`.
- **Voigt ordering**: `[xx, yy, zz, xy, xz, yz]` unscaled shears for 6x6 tangent. Ref: `07-CONVENTIONS.md §2`.
- **Sign**: Tension-positive stress throughout.

### Key Principles
- Plasticity adds **state** (history variables) and **non-smoothness** (yield surface) to the pipeline.
- The algorithmic tangent (P8.2) is the most error-prone component — **always verify with finite differences**.
- P8.1 and P8.3 are **parallel-safe** (different files). P8.2 depends on P8.1. P8.4 depends on all three.
- Below-yield loading MUST produce results identical to the elastic path — this is the key regression check.

### Pre-resolved Design Decisions
- **Radial return**: Predictor-corrector with Newton iteration on delta_lambda.
- **Power-law hardening**: `sigma_y(alpha) = sigma_y0 + K*alpha^n`.
- **History variables**: Equivalent plastic strain (alpha), stored per integration point.
- **Commit/rollback**: Current→old copy on converged step, restore from old on non-convergence.
- **Dispatch**: Elastic/plastic constitutive call is configurable in the internal force kernel.

## Should Know

### Downstream Impact
- P8.4 (kernel switch) feeds P9.1 (e2e test) and P9.3 (physical benchmarks).
- Cook's membrane and necking bar benchmarks (P9.3) depend on correct plasticity implementation.
- The necking bar is the **MVP acceptance test**: load-displacement within 2% of Simo & Hughes (1998).
- History field lifecycle (P8.3) must be robust — incorrect commit/rollback causes silent result corruption.
- Adaptive load stepping (P7.4) may need tuning for plasticity convergence behavior.
