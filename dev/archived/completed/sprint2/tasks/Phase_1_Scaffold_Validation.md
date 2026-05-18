# Phase 1 Scaffold Validation

| Task ID | Title | Missing / Incomplete Fields | Scaffold Action |
|---------|-------|-----------------------------|-----------------|
| P1-T1 | Fix emit_main E/nu → Lamé conversion | — | all fields complete |
| P1-T2 | Implement convected coordinate functions | `risks` was empty | auto-filled (low risk) |
| P1-T3 | Write convected coordinate tests | `risks` was empty | auto-filled (low risk) |
| P1-T4 | Update convected exports | `risks` was empty | auto-filled (low risk) |
| P1-T5 | Regenerate golden files after emit_main fix | — | all fields complete |
| P1-T6 | Write emit_main Lamé conversion test | `risks` was empty | auto-filled (low risk) |

---

## Scaffold Summary

| Metric | Value |
|--------|-------|
| Tasks scaffolded | 6 |
| Test cases assessed | 17 |
| Cases covered by existing tests | 0 |
| Cases partially covered (stubs generated) | 3 |
| Cases with no existing tests (stubs generated) | 14 |
| New stub files created | 2 |
| Total new stubs generated | 12 |
| Tasks fully covered by existing tests (no stub needed) | 2 (P1-T4 via import check, P1-T5 via existing golden regression) |
| Tasks needing human review | 0 |
| Auto-filled fields | `risks` for P1-T2, P1-T3, P1-T4, P1-T6 |

## Existing Test Coverage Found

| Task ID | Test case | Existing test file | Function | Coverage |
|---------|-----------|-------------------|----------|----------|
| P1-T1 | Direct lam/mu → unchanged | test_emission_phase5.py | TestEmitMain::test_emit_main_produces_name_block | partial |
| P1-T2 | F=I → g=G=I, E=0 | test_kinematics.py | TestConvectedMetric::test_g_equals_C_zero_deformation | partial |
| P1-T2 | Simple shear → g=C | test_kinematics.py | TestConvectedMetric::test_g_equals_C_shear | partial |
| P1-T5 | Golden file regression | test_codegen.py | TestGoldenSnapshot::test_generated_elastic_golden_snapshot | covered (structural) |
| P1-T5 | Golden file regression | test_codegen.py | TestGoldenSnapshot::test_generated_plastic_golden_snapshot | covered (structural) |

## Tasks Needing Human Review Before execute-phase

None — all tasks are fully scaffolded.

## Ready for execute-phase

Fully scaffolded:
- P1-T1: Fix emit_main E/nu → Lamé conversion
- P1-T2: Implement convected coordinate functions
- P1-T3: Write convected coordinate tests
- P1-T4: Update convected exports
- P1-T5: Regenerate golden files after emit_main fix
- P1-T6: Write emit_main Lamé conversion test

Stub files created:
- `packages/mechdsl-core/tests/test_convected.py` — 7 test stubs across 4 classes
- `packages/mechdsl-core/tests/test_emit_lame_conversion.py` — 5 test stubs in 1 class
