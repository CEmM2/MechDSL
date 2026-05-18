# Phase 3 Scaffold Validation

| Task ID | Title | Missing / Incomplete Fields | Scaffold Action |
|---------|-------|-----------------------------|-----------------|
| P3-T1 | Implement check_convergence_rate() | `risks` (empty array) | auto-filled |
| P3-T2 | Implement MMS driver | — | — |
| P3-T3 | Write convergence rate test | — | — |
| P3-T4 | Implement run_patch_test() and run_rigid_body_test() | — | — |
| P3-T5 | Write patch test | — | — |

### Auto-fill Details

- **P3-T1 `risks`**: auto-filled — "Risk: log-log slope fitting may be imprecise with exactly 3 data points. Mitigation: require minimum 3 points, recommend 4+ for production use."

## Existing Test Coverage Found

| Task ID | Test case | Existing test file | Function | Coverage |
|---------|-----------|-------------------|----------|----------|
| P3-T4 | Patch test on regular mesh | `tests/test_benchmarks.py` | `TestPatchTest::test_uniaxial_strain` | partial (ref kernel only, not generated solver) |
| P3-T4 | Rigid body identity | `tests/test_benchmarks.py` | `TestRigidBodyMotion::test_zero_displacement` | partial (ref kernel only) |
| P3-T4 | Rigid body rotation | `tests/test_ref_elastic.py` | `TestRigidBodyRotation::test_small_rotation_about_z` | partial (single element, ref kernel) |
| P3-T5 | SVK patch test on irregular mesh | `tests/test_ref_elastic.py` | `TestPatchTest::test_uniaxial_strain` | partial (regular mesh, single element) |
| P3-T5 | Rigid body rotation -> zero force | `tests/test_ref_elastic.py` | `TestRigidBodyRotation::test_small_rotation_about_z` | partial (single element only) |

## Scaffold Summary

| Metric | Value |
|--------|-------|
| Tasks scaffolded | 5 |
| Test cases assessed | 15 |
| Cases covered by existing tests | 0 |
| Cases partially covered (stubs generated) | 5 |
| Cases with no existing tests (stubs generated) | 10 |
| New stub files created | 2 |
| Total new stubs generated | 19 |
| Tasks fully covered by existing tests (no stub needed) | 0 |
| Tasks needing human review | 0 |
| Auto-filled fields | P3-T1 `risks` |

## Tasks Needing Human Review Before execute-phase

None — all tasks are fully scaffolded.

## Ready for execute-phase

Fully scaffolded:
- P3-T1: Implement check_convergence_rate()
- P3-T2: Implement MMS driver
- P3-T3: Write convergence rate test
- P3-T4: Implement run_patch_test() and run_rigid_body_test()
- P3-T5: Write patch test
