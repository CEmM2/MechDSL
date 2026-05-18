---
name: tests
description: "Skill for the Tests area of MechDSL. 1077 symbols across 88 files."
---

# Tests

1077 symbols | 88 files | Cohesion: 75%

## When to Use

- Working with code in `packages/`
- Understanding how test_svk_stress_uses_correct_lame_parameters, test_green_lagrange_strain, test_green_lagrange_strain_half_factor work
- Modifying tests-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `packages/mechdsl-core/tests/test_emission_verification.py` | _get_source_lines_for_function, test_svk_stress_uses_correct_lame_parameters, test_green_lagrange_strain, test_green_lagrange_strain_half_factor, test_right_cauchy_green (+65) |
| `packages/mechdsl-core/tests/test_analytical.py` | test_uniaxial_below_yield_elastic, test_uniaxial_at_yield_elastic, test_uniaxial_above_yield_hardening_law, test_uniaxial_continuity_at_yield_point, test_uniaxial_large_strain_monotonic (+34) |
| `packages/mechdsl-core/tests/test_mesh_io.py` | mesh, mesh, test_indices_in_range, test_no_duplicate_nodes_in_element, test_all_six_faces_present (+29) |
| `packages/mechdsl-core/tests/test_localise.py` | test_non_tl_rejected, test_non_hex8_rejected, _make_mvp_problem, _find_spec, test_mvp_input_produces_result (+26) |
| `packages/mechdsl-core/tests/test_j2.py` | test_yield_stress_monotonicity, test_yield_stress_at_zero, test_return_mapping_consistency, test_von_mises_zero_tensor, test_von_mises_pure_shear (+26) |
| `packages/mechdsl-core/tests/test_documentation.py` | _read_text, test_readme_has_installation_section, test_readme_has_quickstart_section, test_readme_has_architecture_overview_and_design_doc_links, test_changelog_has_mvp_release_entry (+25) |
| `packages/mechdsl-core/tests/test_boundary_codegen.py` | mesh_2x2x2, test_total_force_equals_traction_times_area, test_total_force_custom_dimensions, test_only_face_nodes_have_force, test_uniform_distribution (+23) |
| `packages/mechdsl-core/tests/test_tensor_ops.py` | test_mat_mul_identity, test_inv_identity, test_inv_roundtrip, test_det_product, test_det_identity (+22) |
| `packages/mechdsl-core/tests/test_ref_elastic.py` | test_apply_dirichlet, test_does_not_modify_input, test_newton_converges, test_tip_displacement_sign, test_fixed_face_zero (+21) |
| `packages/mechdsl-core/tests/test_einsum.py` | test_budget_regression_mvp_per_func, test_budget_regression_mvp_tier_assignments, test_budget_regression_mvp_all_within_budget_flag, test_budget_regression_over_budget_huge_einsum, _make_mvp_problem (+20) |

## Entry Points

Start here when exploring this area:

- **`test_svk_stress_uses_correct_lame_parameters`** (Function) — `packages/mechdsl-core/tests/test_emission_verification.py:118`
- **`test_green_lagrange_strain`** (Function) — `packages/mechdsl-core/tests/test_emission_verification.py:143`
- **`test_green_lagrange_strain_half_factor`** (Function) — `packages/mechdsl-core/tests/test_emission_verification.py:148`
- **`test_right_cauchy_green`** (Function) — `packages/mechdsl-core/tests/test_emission_verification.py:155`
- **`test_cauchy_green_before_strain`** (Function) — `packages/mechdsl-core/tests/test_emission_verification.py:160`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `Formulation` | Class | `packages/mechdsl-core/src/mechdsl/ir/mechanics_ir.py` | 24 |
| `ElementType` | Class | `packages/mechdsl-core/src/mechdsl/ir/mechanics_ir.py` | 29 |
| `BCType` | Class | `packages/mechdsl-core/src/mechdsl/ir/mechanics_ir.py` | 35 |
| `BoundaryCondition` | Class | `packages/mechdsl-core/src/mechdsl/ir/mechanics_ir.py` | 41 |
| `MaterialSpec` | Class | `packages/mechdsl-core/src/mechdsl/ir/mechanics_ir.py` | 76 |
| `ProblemIR` | Class | `packages/mechdsl-core/src/mechdsl/ir/mechanics_ir.py` | 99 |
| `LocalisationResult` | Class | `packages/mechdsl-core/src/mechdsl/lowering/fe_localise.py` | 44 |
| `HistoryFields` | Class | `packages/mechdsl-core/src/mechdsl/solver/history_fields.py` | 23 |
| `EmissionContext` | Class | `packages/mechdsl-core/src/mechdsl/codegen/taichi_printer.py` | 41 |
| `ConvergenceResult` | Class | `packages/mechdsl-core/src/mechdsl/verify/convergence.py` | 11 |
| `ReturnMappingResult` | Class | `packages/mechdsl-core/src/mechdsl/symbolic/models/j2_power_law.py` | 165 |
| `SVKMaterial` | Class | `packages/mechdsl-core/src/mechdsl/symbolic/models/svk.py` | 32 |
| `NeumannBC` | Class | `packages/mechdsl-core/src/mechdsl/codegen/boundary_codegen.py` | 48 |
| `HistoryFields` | Class | `packages/mechdsl-core/tests/ref/ref_hex8_plastic.py` | 40 |
| `J2PowerLawMaterial` | Class | `packages/mechdsl-core/src/mechdsl/symbolic/models/j2_power_law.py` | 32 |
| `BasisFunctions` | Class | `packages/mechdsl-core/src/mechdsl/ir/element_ir.py` | 55 |
| `NewtonConfig` | Class | `packages/mechdsl-core/src/mechdsl/solver/newton.py` | 32 |
| `NewtonResult` | Class | `packages/mechdsl-core/src/mechdsl/solver/newton.py` | 49 |
| `ElementIR` | Class | `packages/mechdsl-core/src/mechdsl/ir/element_ir.py` | 94 |
| `LoadStepResult` | Class | `packages/mechdsl-core/src/mechdsl/solver/load_stepping.py` | 19 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Main → ElementIR` | cross_community | 6 |
| `Main → ElementIR` | cross_community | 6 |
| `Main → ElementIR` | cross_community | 6 |
| `Main → ElementIR` | cross_community | 6 |
| `Main → ElementIR` | cross_community | 6 |
| `Main → Gradient` | cross_community | 6 |
| `Main → Right_cauchy_green` | cross_community | 6 |
| `Run_pipeline → BasisFunctions` | cross_community | 6 |
| `Run_pipeline → QuadratureRule` | cross_community | 6 |
| `Main → LocalisationResult` | cross_community | 5 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Codegen | 7 calls |
| Verify | 5 calls |
| Ref | 3 calls |

## How to Explore

1. `gitnexus_context({name: "test_svk_stress_uses_correct_lame_parameters"})` — see callers and callees
2. `gitnexus_query({query: "tests"})` — find related execution flows
3. Read key files listed above for implementation details
