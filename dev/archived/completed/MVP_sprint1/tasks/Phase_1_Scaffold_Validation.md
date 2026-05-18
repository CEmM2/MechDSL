# Phase 1 Scaffold Validation

## Task JSON Field Validation

| Task ID | Title | Missing / Incomplete Fields | Scaffold Action |
|---------|-------|-----------------------------|-----------------|
| P1-T1 | Implement ConstitutiveModel ABC | `risks`: only 1 entry (acceptable) | — |
| P1-T2 | Add SVKModel wrapper class | `risks`: empty array | auto-filled: no material-specific risk identified |
| P1-T3 | Add J2Model wrapper class | `risks`: empty array | auto-filled: no material-specific risk identified |
| P1-T4 | Update fe_localise model validation | `risks`: empty array | auto-filled: no risk — minor 5-line change |
| P1-T5 | Write constitutive ABC tests | `risks`: empty array | auto-filled: no risk — test-only task |

All `objective`, `acceptance_criteria`, `implementation_steps`, and `deliverables` fields are populated and specific. No `needs-human-review` flags.

## Auto-filled Fields

| Task ID | Field | Before | After |
|---------|-------|--------|-------|
| P1-T1 | `test_plan.tier` | `fast` | `unit` |
| P1-T1 | `test_plan.cases` | 2 entries | 3 entries (added "ABC defines all 5 abstract methods") |
| P1-T2 | `test_plan.tier` | `fast` | `unit` |
| P1-T2 | `test_plan.cases` | 3 entries | 5 entries (split into individual property checks) |
| P1-T3 | `test_plan.tier` | `fast` | `unit` |
| P1-T3 | `test_plan.cases` | 3 entries | 5 entries (split into individual property checks) |
| P1-T4 | `test_plan.tier` | `fast` | `integration` |
| P1-T4 | `test_plan.cases` | 2 entries | 3 entries (split SVK/J2 acceptance) |
| P1-T5 | `test_plan.tier` | `fast` | `unit` |
| All | `test_artifacts` | empty/incomplete | populated with stub + existing test paths |
| All | `verification_commands` | generic | scoped to specific test classes |

---

## Scaffold Summary

| Metric | Value |
|--------|-------|
| Tasks scaffolded | 5 |
| Test cases assessed | 21 |
| Cases covered by existing tests | 0 |
| Cases partially covered (stubs generated) | 1 |
| Cases with no existing tests (stubs generated) | 20 |
| New stub files created | 2 |
| Total new stubs generated | 19 |
| Tasks fully covered by existing tests (no stub needed) | 0 |
| Tasks needing human review | 0 |
| Auto-filled fields | test_plan.tier (5), test_plan.cases (5), test_artifacts (5), verification_commands (5) |

## Existing Test Coverage Found

| Task ID | Test case | Existing test file | Function | Coverage |
|---------|-----------|-------------------|----------|----------|
| P1-T2 | SVK stress correctness | `test_svk.py` | `test_uniaxial_strain`, `test_pure_shear`, `test_hydrostatic_strain` | partial — tests standalone `pk2_stress()`, not SVKModel wrapper |
| P1-T2 | SVK tangent correctness | `test_svk.py` | `test_major_symmetry`, `test_tangent_matches_numerical_dSdE` | partial — tests standalone `material_tangent_4th()`, not SVKModel |
| P1-T3 | J2 stress/tangent correctness | `test_j2.py` | `test_below_yield_elastic`, `test_above_yield_plastic`, etc. | partial — tests standalone `radial_return()`, not J2Model wrapper |
| P1-T4 | SVK model string accepted | `test_localise.py` | `test_svk_elastic_hex8_localisation` (implicit) | partial — uses 'svk' but doesn't explicitly test model validation |

## New Stub Files Created

| File | Task IDs | Stubs |
|------|----------|-------|
| `packages/mechdsl-core/tests/test_constitutive_abc.py` | P1-T1, P1-T2, P1-T3, P1-T5 | 16 |
| `packages/mechdsl-core/tests/test_localise_model_validation.py` | P1-T4 | 3 |

### Stub functions in test_constitutive_abc.py

| Class | Function | Covers task | Covers criterion |
|-------|----------|-------------|-----------------|
| `TestConstitutiveModelABC` | `test_import_constitutive_model` | P1-T1 | AC1: importable |
| `TestConstitutiveModelABC` | `test_abc_cannot_be_instantiated` | P1-T1 | AC3: raises TypeError |
| `TestConstitutiveModelABC` | `test_abc_defines_five_abstract_methods` | P1-T1 | AC2: 5 abstract methods |
| `TestSVKModelWrapper` | `test_svk_stress_matches_standalone` | P1-T2 | numerical identity |
| `TestSVKModelWrapper` | `test_svk_tangent_matches_standalone` | P1-T2 | numerical identity |
| `TestSVKModelWrapper` | `test_svk_voigt_tangent_matches_standalone` | P1-T2 | numerical identity |
| `TestSVKModelWrapper` | `test_svk_state_variables` | P1-T2 | state_variables == () |
| `TestSVKModelWrapper` | `test_svk_is_not_dissipative` | P1-T2 | is_dissipative == False |
| `TestJ2ModelWrapper` | `test_j2_stress_matches_radial_return` | P1-T3 | numerical identity |
| `TestJ2ModelWrapper` | `test_j2_tangent_matches_radial_return` | P1-T3 | numerical identity |
| `TestJ2ModelWrapper` | `test_j2_handles_alpha_state` | P1-T3 | alpha state passing |
| `TestJ2ModelWrapper` | `test_j2_state_variables` | P1-T3 | state_variables == ('alpha',) |
| `TestJ2ModelWrapper` | `test_j2_is_dissipative` | P1-T3 | is_dissipative == True |
| `TestConstitutiveABCIntegration` | `test_svk_is_instance_of_abc` | P1-T5 | isinstance check |
| `TestConstitutiveABCIntegration` | `test_j2_is_instance_of_abc` | P1-T5 | isinstance check |
| `TestConstitutiveABCIntegration` | `test_shape_validation_wrong_strain` | P1-T5 | shape validation |

### Stub functions in test_localise_model_validation.py

| Class | Function | Covers task | Covers criterion |
|-------|----------|-------------|-----------------|
| `TestModelStringValidation` | `test_svk_model_string_accepted` | P1-T4 | valid strings accepted |
| `TestModelStringValidation` | `test_j2_model_string_accepted` | P1-T4 | valid strings accepted |
| `TestModelStringValidation` | `test_unknown_model_string_raises_error` | P1-T4 | unknown string raises error |

## Tasks Needing Human Review Before execute-phase

None — all tasks are fully specified.

## Ready for execute-phase

Fully scaffolded:
- P1-T1: Implement ConstitutiveModel ABC
- P1-T2: Add SVKModel wrapper class
- P1-T3: Add J2Model wrapper class
- P1-T4: Update fe_localise model validation
- P1-T5: Write constitutive ABC tests
