# Phase 3 Context Summary: Viscoplasticity

**Plan:** `dev/design_docs/PLAN-B.md`
**Original plan phase name:** B3 Viscoplasticity

## Conventions

- State variables: `alpha` (equivalent plastic strain, same as Plan A J2) and — for Johnson-Cook only — `T` (temperature).
- Temperature evolution is adiabatic: dT = β σ : D_p / (ρ c_p) with β = 0.9 (Taylor-Quinney) as the default.
- Rate-dependent yield consistency equations are Newton-iterated with the same effective-tolerance scaling pattern used by Plan A J2 (`effective_tol = max(tol, tol * stress_ref)`).

## Key Principles

- **Rate-independent limit is non-negotiable.** At `eta → 0` (Perzyna) or `eps_dot = eps_dot_0` (JC at reference rate), the model must reduce byte-for-byte to Plan A `j2_power_law`. Regression guard.
- **Thermal softening is monotonic in T.** JC's temperature-softening term lowers yield stress as T rises; this is an invariant, not an approximation.
- **Algorithmic consistent tangent, not continuum.** The tangent that Phase 1 UL emission consumes is the linearisation of the discrete return map at convergence, NOT the thermodynamic tangent from differentiating Ψ. This matches Plan A §A9.2's approach.
- **FD cross-check is the primary safeguard.** Every new tangent must be checked against a central difference of the stress update on 10 random strain states before being merged. Bugs here silently degrade Newton convergence without wrong stresses.
- **Simo & Hughes §3.4** is the canonical reference for the algorithmic-tangent derivation. Cite the specific box number in the module docstring.

## Pre-resolved Design Decisions

- Perzyna and JC both extend the existing Plan A J2 code path — they don't replace it. At viscosity/rate-insensitivity parameters, they fall back to the J2 power-law return map.
- Johnson-Cook coupled (dl, dT) Newton iteration is 2D; use a small dense 2x2 Jacobian, not a sparse solver.
- Taylor impact test (B3 exit criterion in the plan) is SPLIT across phases: the viscoplastic unit tests go in P3-4, the full Taylor benchmark goes in P10-7 because it also needs UL + explicit dynamics + reduced Hex8.

## Allowed Deviations

- The plan lists "Taylor impact test: reproduced within 5%" as B3's exit criterion. Phase 3 itself only delivers the unit-level viscoplastic tests (rate sensitivity, quasi-static limit, thermal softening); the full Taylor benchmark is deferred to P10-7.

## Downstream Impact

- **P10-7 Taylor impact benchmark** depends on P3-4's viscoplastic unit verification.
- Phase 6 (Lemaitre damage) extends J2 with damage coupling and is independent of Phase 3 — damage is coupled with rate-*independent* plasticity first, rate-dependent as a follow-up.
- Phase 8 (MFEM/MOOSE printers) needs to know about the new material types so the backend dispatch table covers `perzyna` and `johnson_cook`.
