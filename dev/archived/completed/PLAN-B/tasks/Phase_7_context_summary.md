# Phase 7 Context Summary: Explicit dynamics

**Plan:** `dev/design_docs/PLAN-B.md`
**Original plan phase name:** B7 Explicit dynamics

## Conventions

- Explicit integration uses central difference: `v^{n+1/2} = v^{n-1/2} + dt · M_inv · (f_ext − f_int)`, `u^{n+1} = u^n + dt · v^{n+1/2}`.
- Lumped mass matrix is diagonal by row-sum from the consistent mass matrix. Storage: one `ti.field` of shape `(n_nodes, 3)` for the lumped DOFs.
- Critical time step from the Courant condition: `dt_crit = L_min / c_d` with a safety factor of 0.9.

## Key Principles

- **No linear solver needed.** Central difference is matrix-free by construction — the generated explicit driver is ~60% the size of the implicit Newton driver.
- **Mass lumping is element-type dependent.** Hex8 row-sum is trivial; higher-order elements (Hex20) need special lumping rules (HRZ or diagonal scaling). Scope MVP to Hex8 and stub the others.
- **dt_crit is state-dependent** in nonlinear problems — the wave speed changes with strain. Recompute `dt_crit` every N steps (default N=100) in the generated driver.
- **Quasi-static problems need mass scaling** to finish in reasonable wall-clock time. Document the scaling factor in the test (typically `rho_scaled = rho * 1e6`).
- **Explicit and implicit must agree** on quasi-static final equilibrium within 1e-6. This is the cross-check test that binds Phase 7 to Plan A's Newton solver.

## Pre-resolved Design Decisions

- `DynamicsMode` enum: `STATIC` (Newton, default) or `EXPLICIT` (central difference). Chosen at compile time, not at runtime.
- The generated explicit driver exposes `advance_one_step(dt)` (not `newton_solve(...)`). Users call it in a loop and manage time themselves.
- Velocity is a new Taichi field `v` alongside `u`. Plan A generated code does NOT have `v`; Phase 7 adds it conditionally.
- Taylor impact test (the big explicit benchmark) lives in P10-7, NOT Phase 7 — it needs UL + JC + reduced Hex8 + hourglass control as well.

## Allowed Deviations

- Mass lumping for Hex20/Tet10 is OUT OF SCOPE for Phase 7 MVP. Stub with `raise NotImplementedError` and document as a post-MVP follow-up.

## Downstream Impact

- **P10-7 Taylor impact** is the big consumer of Phase 7. It combines Phase 7 with Phase 1 (UL), Phase 3 (JC), Phase 5 (reduced Hex8 + hourglass).
- Phase 7 does not extend to adaptive time stepping or contact. Those are post-MVP.
