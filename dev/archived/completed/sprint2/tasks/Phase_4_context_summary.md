# Phase 4 Context Summary — J2 Plasticity E2E Integration

## Conventions
- **J2 radial return**: elastic predictor → deviatoric split → von Mises → yield check → scalar Newton for Δλ → stress update → alpha update
- **Von Mises**: σ_eq = sqrt(1.5·s_ij·s_ij) where s = S_dev = S - (tr(S)/3)·I
- **Power-law hardening**: σ_y(α) = σ_y0 + K·α^n
- **Yield function**: f = σ_eq - σ_y(α)
- **FD tangent**: central difference with h = 1e-7, precision floor ~4e-9
- **BC enforcement**: external to generated Newton driver — R[bc_mask] = 0, du[bc_mask] = 0, Kv[bc_flat] = v[bc_flat]
- **Tolerance for generated vs reference**: displacement max diff < 1e-10 (may need relaxation to 1e-8 for plastic)

## Key Principles
- **History variable management is the central challenge**: the generated code overwrites alpha[e,q] in-place during compute_internal_force(). For Newton iteration correctness, alpha must be saved before the loop and restored before each iteration.
- **FD tangent corrupts alpha**: the perturbed compute_internal_force call also updates alpha. The E2E test MUST save/restore alpha around tangent_matvec calls.
- **Follow test_e2e_taichi.py pattern**: the elastic E2E test's `_newton_with_bc()` (lines 89-161) is the template for the plastic version.
- **All Phase 4 tasks require Opus 4.6** due to high complexity and domain-specific numerics.

## Allowed Deviations from Specs
- **Displacement tolerance relaxation**: if FD tangent prevents meeting 1e-10 for plastic case, a relaxed tolerance of 1e-8 is acceptable with documented justification (plan line 213-214)
- **External Newton loop**: the generated newton_solve() lacks BC enforcement (Sprint 1 gap), so the E2E test drives Newton externally — this is an accepted workaround, not a spec violation
- **No history commit/rollback in generated code**: deferred to Sprint 3 (plan line 185)

## Pre-resolved Design Decisions
- **Material params for J2 E2E**: sigma_y0=200, K=100, n=0.3, E=200e3, nu=0.3 (plan line 198)
- **Alpha save/restore pattern**: `alpha_snapshot = mod.alpha.to_numpy().copy()` before Newton loop, `mod.alpha.from_numpy(alpha_snapshot)` before each residual evaluation (plan lines 337-348)
- **Load stepping**: incremental displacement past yield in N steps — same approach as ref_hex8_plastic.py
- **P4-T1 through P4-T4 are audit tasks**: they verify existing emission, potentially fix issues, before the E2E test (P4-T5)

## Downstream Impact
- **P4-T5 (test_e2e_plastic.py)** is the sprint's primary deliverable — proving the generated J2 solver works
- **P4-T6 (generated vs reference)** extends test ID C3 to plastic case
- **P4-T7 (golden file)** updates the plastic golden file baseline for future regression
- **Phase 4 results feed Phase 5 audit**: C3 now includes J2

## Key Files
- `packages/mechdsl-core/src/mechdsl/codegen/taichi_printer.py` — _emit_j2_constitutive() lines 281-379, emit_tangent_matvec_kernel() lines 507-607
- `packages/mechdsl-core/src/mechdsl/symbolic/models/j2_power_law.py` — radial_return() reference algorithm
- `packages/mechdsl-core/tests/test_e2e_taichi.py` — elastic E2E pattern to follow (especially _newton_with_bc)
- `packages/mechdsl-core/tests/ref/ref_hex8_plastic.py` — reference solver for comparison
- `packages/mechdsl-core/tests/golden/generated_plastic.py.golden` — current J2 golden file
- `packages/mechdsl-core/tests/test_plastic_emission.py` — existing J2 emission tests (40 tests)
