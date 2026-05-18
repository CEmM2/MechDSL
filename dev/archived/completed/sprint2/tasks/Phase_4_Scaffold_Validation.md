# Phase 4 Scaffold Validation

| Task ID | Title | Missing / Incomplete Fields | Scaffold Action |
|---------|-------|-----------------------------|-----------------|
| P4-T1 | Audit J2 constitutive emission | — | — |
| P4-T2 | Validate FD tangent for J2 | — | — |
| P4-T3 | Verify history field emission | — | — |
| P4-T4 | Verify numerical safeguards | `risks` empty | auto-filled |
| P4-T5 | Create test_e2e_plastic.py | — | — |
| P4-T6 | Compare generated vs reference | — | — |
| P4-T7 | Validate/update golden file | `risks` empty | auto-filled |

## Scaffold Summary

| Metric | Value |
|--------|-------|
| Tasks scaffolded | 7 |
| Test cases assessed | 15 |
| Cases covered by existing tests | 8 |
| Cases partially covered (stubs generated) | 3 |
| Cases with no existing tests (stubs generated) | 4 |
| New stub files created | 1 (`test_e2e_plastic.py`) |
| Total new stubs generated | 10 |
| Tasks fully covered by existing tests (no stub needed) | 2 (P4-T3, P4-T7) |
| Tasks needing human review | 0 |
| Auto-filled fields | P4-T4 risks, P4-T7 risks |

## Existing Test Coverage Found

| Task ID | Test case | Existing test file | Function | Coverage |
|---------|-----------|-------------------|----------|----------|
| P4-T1 | Existing plastic emission tests pass | test_plastic_emission.py | TestJ2ConstitutiveEmitted (2), TestRadialReturnLoop (4), TestYieldFunction (2) | covered |
| P4-T1 | Symbolic radial return correct | test_j2.py | test_below_yield_elastic, test_above_yield_plastic, test_return_mapping_consistency | covered |
| P4-T2 | FD tangent saves alpha | test_plastic_emission.py | TestTangentForBoth::test_j2_tangent_saves_alpha | partial |
| P4-T2 | FD tangent convergence plastic | test_j2.py | test_tangent_fd_plastic | covered |
| P4-T3 | alpha field declared | test_plastic_emission.py | TestHistoryFieldInKernel::test_alpha_field_declared | covered |
| P4-T3 | alpha read/write | test_plastic_emission.py | TestHistoryFieldInKernel::test_alpha_field_read, test_alpha_field_write | covered |
| P4-T3 | alpha update logic | test_plastic_emission.py | TestAlphaUpdate::test_alpha_new_assigned | covered |
| P4-T4 | sigma_eq guard | test_plastic_emission.py | TestVonMisesGuard::test_sigma_eq_near_zero_guard | covered |
| P4-T4 | delta_lambda guard | test_phase1_codegen_fixes.py | TestH2DeltaLambdaClamp::test_emitted_j2_dl_clamp_present | covered |
| P4-T5 | Elastic regime (ref solver) | test_ref_plastic.py | test_elastic_path_is_still_elastic | partial |
| P4-T5 | Return mapping (ref solver) | test_ref_plastic.py | test_return_mapping_residual | partial |
| P4-T7 | Golden file matches generation | test_codegen.py | TestGoldenSnapshot::test_generated_plastic_golden_snapshot | covered |

## Tasks Needing Human Review Before execute-phase

(none)

## Ready for execute-phase

Fully scaffolded:
- P4-T1: Audit J2 constitutive emission
- P4-T2: Validate FD tangent for J2
- P4-T3: Verify history field emission
- P4-T4: Verify numerical safeguards
- P4-T5: Create test_e2e_plastic.py
- P4-T6: Compare generated vs reference
- P4-T7: Validate/update golden file
