# Phase 1 — Trusted Handwritten References: Context Summary

## Must Know

### Conventions
- **Sign convention**: Tension-positive stress, compression-positive pressure (`p = -m`). Ref: `07-CONVENTIONS.md §4`.
- **Voigt ordering**: `[xx, yy, zz, xy, xz, yz]` with **unscaled shears** (tensorial, not engineering). Ref: `07-CONVENTIONS.md §2`.
- **Tolerances**: Patch test < 1e-12 relative error, rigid body force norm < 1e-12, cantilever within 5%.
- **Precision**: All computations in f64. No mixed precision.

### Key Principles
- These are **trusted references** — the generated code (Phases 6–8) will be compared against them.
- Correctness is paramount: bugs here propagate as false-positive acceptance in Phase 9.
- Golden files (P1.3) must use tolerance-based comparison to handle platform-dependent floating-point.

### Pre-resolved Design Decisions
- **Total Lagrangian formulation**: all quantities in reference configuration.
- **SVK elastic**: `S = lambda*tr(E)*I + 2*mu*E`.
- **J2 plasticity**: radial return with power-law hardening `sigma_y = sigma_y0 + K*alpha^n`.
- **Linear solver**: via `LinearSolverInterface` from P0.4 (CG tolerance 1e-10).
- **Hex8 only**: 8-node trilinear hexahedral, 2x2x2 Gauss quadrature.

## Should Know

### Downstream Impact
- P1.1 + P1.2 provide the **ground truth** for equivalence testing in P9.2.
- P1.3 golden files are the **regression baseline** for P9.2 and P9.3.
- Any error in the reference kernels will require re-running all Phase 9 acceptance tests.
- The plastic reference (P1.2) validates return mapping correctness before it's automated in P8.1.
