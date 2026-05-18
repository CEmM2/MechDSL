# Phase 1 Context Summary: Updated Lagrangian formulation

**Plan:** `dev/design_docs/PLAN-B.md`
**Original plan phase name:** B1 Updated Lagrangian formulation

## Conventions

- Lowercase Latin indices (`i, j, k, l`) are **spatial** (current configuration); uppercase (`I, J, K, L`) are **material** (reference). The two-point tensor convention from `07-CONVENTIONS.md` applies throughout.
- Voigt ordering remains `[xx, yy, zz, xy, xz, yz]` with unscaled shears. UL code must not switch to engineering Voigt.
- Sign convention: tension-positive stress, compression-positive pressure.
- The JIT budget (512/2000/5000 lines) applies per `@ti.func` / `@ti.kernel` / absolute ceiling — Phase 1 must not silently exceed.

## Key Principles

- **ConfigurationIR is the single source of truth** for which configuration (reference or current) a field, gradient, or stress lives in. Any emitter branching on configuration must read the enum, not sniff the material type or directive string.
- **Cauchy ↔ PK2 push-forward** happens at the emission site: σ = F S F^T / J for UL, and the constitutive layer always returns PK2 S. Do not re-implement constitutive models in Cauchy form.
- **Analytical consistent tangent**: Plan A §A7.5/§A9.2 already replaced the FD tangent with an analytical linearisation. Phase 1 UL tangent must keep the same pattern — element-by-element NumPy in the generated file, no FD, no fresh Taichi kernel for the tangent body.
- **Rigid body motion produces zero Cauchy stress rate** under any objective rate. Every objective-rate implementation is verified against this invariant.
- **TL and UL must agree to machine precision** on any quasi-static problem (the two formulations are mathematically equivalent for elasto-plasticity; differences > 1e-8 indicate a bug).

## Pre-resolved Design Decisions

- The UL residual integrates over the current configuration: R_i = ∫ σ_ij (∂N_a/∂x_j) dΩ − ∫ b_i v_i dΩ. Use spatial shape gradients and det(j), not reference gradients and det(J0).
- The UL tangent has exactly two terms: a Jaumann-rate material term and a geometric stiffness term. Don't try to collapse them — they live in different slots in the emitted code.
- Jaumann is the default objective rate for metals. Truesdell and Green-Naghdi are also implemented but only used when a material explicitly requests them.
- `formulation='updated_lagrangian'` flips the Plan A "unsupported" guard into a supported path. The rejection message must be removed, not worked around with a flag.
- The frontend `% mechanics formulation updated_lagrangian` directive already parses (P1-7 from Plan A §A3); this phase makes the parsed value actually reach the code generator.

## Allowed Deviations

- If the JIT budget for the combined UL residual + tangent kernel exceeds 512 lines, split into sub-functions at quadrature-loop boundaries. This deviation is pre-approved by the codegen rules and does not need a design review.

## Downstream Impact

- **Phase 2 (full convected)** extends Phase 1's ConfigurationIR to curvilinear reference configurations. Phase 1 sets the API; Phase 2 fills in the non-trivial metric tensors.
- **Phases 3-8** all depend on P1-1 (ConfigurationIR) as their phase entry point. Any API change to `ConfigurationIR` after Phase 1 closes is a breaking change that cascades across 40+ downstream tasks.
- **Phase 10 benchmarks** use TL + UL parametrisation heavily (P10-2 cantilever matrix, P10-6 necking bar matrix, P10-7 Taylor impact). P1-7's TL-vs-UL equivalence test is the regression guard for all of them.
