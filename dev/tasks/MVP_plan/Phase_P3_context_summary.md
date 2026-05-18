# Phase 3 — Symbolic Mechanics Engine: Context Summary

## Must Know

### Conventions
- **Voigt ordering**: `[xx, yy, zz, xy, xz, yz]` unscaled shears. `VOIGT_MAP_3D = [(0,0),(1,1),(2,2),(0,1),(0,2),(1,2)]`. Ref: `07-CONVENTIONS.md §2`.
- **Mandel scaling**: `P = diag(1,1,1,sqrt(2),sqrt(2),sqrt(2))`. Ref: `07-CONVENTIONS.md §3`.
- **Sign**: Tension-positive stress. `S_IJ` for PK2. Ref: `07-CONVENTIONS.md §4`.
- **Von Mises guard**: `sigma_eq < 1e-12 * sigma_y` → treat as elastic. Ref: `07-CONVENTIONS.md §6`.
- **AD oracle tolerance**: Relative error < 1e-10 over 100 random states. Ref: PLAN-A line 292.

### Key Principles
- All symbolic work uses SymPy. Expressions must be factored (not fully expanded) to avoid simplification bottlenecks.
- Constitutive models inherit from a common `ConstitutiveModel` base (P3.2 establishes the pattern).
- The AD oracle (P3.5) is the **independent verification** of symbolic correctness — it uses torch/numpy autodiff, not SymPy.
- P3.1–P3.4 are **parallel-safe**: they touch distinct files and have no mutual dependencies.

### Pre-resolved Design Decisions
- **Kinematics**: F = I + grad(u), C = F^T F, J = det(F), E = (C-I)/2, convected metric g = C.
- **SVK model**: S = lambda*tr(E)*I + 2*mu*E; tangent C_IJKL = lambda*delta_IJ*delta_KL + mu*(delta_IK*delta_JL + delta_IL*delta_JK).
- **J2 model**: Von Mises yield with power-law hardening sigma_y = sigma_y0 + K*alpha^n. Symbolic scaffolding only — numerical return mapping is P8.1.

## Should Know

### Downstream Impact
- P3.2 (SVK) feeds P6.3 (elastic constitutive emission). The symbolic expressions are what get code-generated.
- P3.3 (J2) feeds P8.1 (plastic constitutive emission). The symbolic scaffolding defines the emission structure.
- P3.4 (Voigt) feeds P4.3 (FE localization). Voigt conversion is needed for einsum extraction.
- P3.5 (AD oracle) feeds P9.3 (benchmark hardening) as an independent verification oracle.
- Phase 3 blocks constitutive portions of Phase 6 and all of Phase 8.
