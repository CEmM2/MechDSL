# Phase 5 Scaffold Validation

| Task ID | Title | Missing / Incomplete Fields | Scaffold Action |
|---------|-------|-----------------------------|-----------------|
| P5-T1 | Audit symbolic (S1-S9) + parser (P1-P6) | `risks` empty | auto-filled |
| P5-T2 | Audit IR (M1-M6), Element (E1-E6), Einsum (N1-N5) | `risks` empty | auto-filled |
| P5-T3 | Audit Backend (T1-T4), BC (B1-B5), Artifact (A1-A3), Emission (C1-C3) | `risks` empty | auto-filled |
| P5-T4 | Create verification matrix | `risks` empty, `verification_commands` empty | auto-filled |

## Auto-filled Fields

- **P5-T1 risks**: "Risk: P3/P4 parser test IDs cannot be tested — parser is a stub. Mitigation: mark as deferred with justification."
- **P5-T2 risks**: "Risk: Gap-filling tests for M4, E3, N5 may require new test infrastructure. Mitigation: use minimal targeted tests."
- **P5-T3 risks**: "Risk: B5 BoundaryBindingError may not be implemented yet. Mitigation: verify error class exists before writing test."
- **P5-T4 risks**: "Risk: Matrix may become stale if test files change. Mitigation: use relative paths and link to test IDs."

---

## Scaffold Summary

| Metric | Value |
|--------|-------|
| Tasks scaffolded | 4 |
| Test cases assessed | 37 (9 categories) |
| Cases covered by existing tests | 28 |
| Cases partially covered (stubs generated) | 4 (E2, N3, T1) |
| Cases with no existing tests (stubs generated) | 3 (M4, E3/N5, B5) |
| Cases deferred by design | 2 (P3, P4) |
| New stub files created | 2 |
| Total new stubs generated | 7 |
| Tasks fully covered by existing tests (no stub needed) | 1 (P5-T1) |
| Tasks needing human review | 0 |
| Auto-filled fields | risks (all 4 tasks) |

## Existing Test Coverage Found

### P5-T1: Symbolic (S1-S9) + Parser (P1-P6)

| Task ID | Test case | Existing test file | Function | Coverage |
|---------|-----------|-------------------|----------|----------|
| P5-T1 | S1 (kinematics F=I) | test_kinematics.py | TestIdentityDeformation | covered |
| P5-T1 | S2 (known shear) | test_kinematics.py | TestSimpleShear | covered |
| P5-T1 | S3 (SVK stress) | test_svk.py | TestPK2Stress | covered |
| P5-T1 | S4 (power-law hardening) | test_j2.py | test_yield_stress_monotonicity, test_yield_stress_at_zero | covered |
| P5-T1 | S5 (Voigt round-trip) | test_voigt.py | TestTensorVoigtRoundTrip | covered |
| P5-T1 | S6 (Mandel round-trip) | test_voigt.py | TestMandel::test_voigt_mandel_roundtrip_vector | covered |
| P5-T1 | S7 (tangent symmetry) | test_svk.py | TestTangentSymmetries::test_major_symmetry | covered |
| P5-T1 | S8 (AD oracle) | test_ad_oracle.py | TestSVKStress::test_fd_stress_matches_pk2_stress | covered |
| P5-T1 | S9 (convected metric) | test_convected.py | TestComputeConvectedMetric | covered |
| P5-T1 | P1 (valid MVP source) | test_frontend_build_context.py | test_P1_valid_mvp_source_correct_dict_structure | covered |
| P5-T1 | P2 (unknown directive) | test_frontend_build_context.py | test_P2_unknown_material_error_with_suggestion | covered |
| P5-T1 | P3 (two-point tensor) | — | — | deferred (parser not implemented) |
| P5-T1 | P4 (index manifold clash) | — | — | deferred (parser not implemented) |
| P5-T1 | P5 (missing directive) | test_frontend_build_context.py | test_P5_missing_dim_error | covered |
| P5-T1 | P6 (convected coords) | test_frontend_build_context.py | test_P6_convected_coords_cartesian_default | covered |

### P5-T2: IR (M1-M6), Element (E1-E6), Einsum (N1-N5)

| Task ID | Test case | Existing test file | Function | Coverage |
|---------|-----------|-------------------|----------|----------|
| P5-T2 | M1 (valid IR) | test_mechanics_ir.py | TestProblemIRConstruction | covered |
| P5-T2 | M2 (unsupported model) | test_mechanics_ir.py | TestInvalidMaterial::test_unknown_model_rejected | covered |
| P5-T2 | M3 (dim mismatch) | test_mechanics_ir.py | TestInvalidDim | covered |
| P5-T2 | M4 (missing BC region) | — | — | missing |
| P5-T2 | M5 (IR round-trip) | test_mechanics_ir.py | TestRoundTrip | covered |
| P5-T2 | M6 (cell type rejection) | test_mechanics_ir.py | TestInvalidElementType | covered |
| P5-T2 | E1 (partition of unity) | test_element_ir.py, test_hex8_tables.py | TestPartitionOfUnity | covered |
| P5-T2 | E2 (constant field) | test_hex8_tables.py | test_constant_strain_recovery | partial |
| P5-T2 | E3 (Jacobian det) | — | — | missing |
| P5-T2 | E4 (physical gradients) | test_element_ir.py | TestGradientConsistency::test_gradient_sum_is_zero | covered |
| P5-T2 | E5 (einsum extraction) | test_einsum.py | test_strain_displacement_einsum_string | covered |
| P5-T2 | E6 (convected geometry) | test_convected.py | test_convected_metric_matches_kinematics_g | covered |
| P5-T2 | N1 (budget count) | test_einsum_optimizer.py | test_within_budget_passes_kernel_check | covered |
| P5-T2 | N2 (tier classification) | test_einsum_optimizer.py | test_matrix_multiply_3x3_is_tier1 | covered |
| P5-T2 | N3 (overflow fallback) | test_einsum_optimizer.py | test_artificially_large_func_over_budget | partial |
| P5-T2 | N4 (contraction correctness) | test_einsum_optimizer.py | test_opt_einsum_valid_path | covered |
| P5-T2 | N5 (speedup factor) | — | — | missing |

### P5-T3: Backend (T1-T4), BC (B1-B5), Artifact (A1-A3), Emission (C1-C3)

| Task ID | Test case | Existing test file | Function | Coverage |
|---------|-----------|-------------------|----------|----------|
| P5-T3 | T1 (Tier 1 GEMM emission) | test_codegen.py | — | partial |
| P5-T3 | T2 (Tier 2 loop nest) | test_codegen.py | test_elastic_index_partitioning | covered |
| P5-T3 | T3 (budget cutoff) | test_einsum_optimizer.py | test_over_budget_ti_func_detection | covered |
| P5-T3 | T4 (static vs runtime) | test_codegen.py | test_elastic_index_partitioning | covered |
| P5-T3 | B1 (boundary tag) | test_boundary_codegen.py | — | covered |
| P5-T3 | B2 (Dirichlet enforcement) | test_boundary_codegen.py | — | covered |
| P5-T3 | B3 (component-wise BC) | test_boundary_codegen.py | — | covered |
| P5-T3 | B4 (Neumann integration) | test_boundary_codegen.py | — | covered |
| P5-T3 | B5 (missing binding) | — | — | missing |
| P5-T3 | A1 (bundle completeness) | test_artifact_bundle.py | — | covered |
| P5-T3 | A2 (golden-file diff) | test_codegen.py | TestGoldenSnapshot | covered |
| P5-T3 | A3 (artifact round-trip) | test_artifact_bundle.py | — | covered |
| P5-T3 | C1 (syntax check) | test_codegen.py | test_golden_is_valid_python | covered |
| P5-T3 | C2 (import correctness) | test_e2e_taichi.py | test_jit_compile_elastic | covered |
| P5-T3 | C3 (gen vs handwritten) | test_e2e_taichi.py, test_e2e_plastic.py | TestTaskP4T6 | covered |

## Tasks Needing Human Review Before execute-phase

| Task ID | Title | Field | Issue |
|---------|-------|-------|-------|
| (none) | | | |

## Ready for execute-phase

Fully scaffolded:
- P5-T1: Audit symbolic (S1-S9) + parser (P1-P6) — all covered/deferred, no stubs needed
- P5-T2: Audit IR (M1-M6), Element (E1-E6), Einsum (N1-N5) — stubs for M4, E2, E3, N3, N5
- P5-T3: Audit Backend (T1-T4), BC (B1-B5), Artifact (A1-A3), Emission (C1-C3) — stubs for T1, B5
- P5-T4: Create verification matrix — documentation only, no stubs
