# Phase 7 Scaffold Validation

| Task ID | Title | Missing / Incomplete Fields | Scaffold Action |
|---------|-------|-----------------------------|-----------------|
| P7-1 | Taylor explicit runtime, contact, and hourglass sanity | `test_artifacts`, `verification_commands` were placeholder strings | auto-filled |
| P7-2 | Taylor Johnson-Cook state and postprocessing | `test_artifacts`, `verification_commands` were placeholder strings | auto-filled |

## Scaffold Summary

| Metric | Value |
|--------|-------|
| Tasks scaffolded | 2 |
| Test cases assessed | 7 |
| Cases covered by existing tests | 0 |
| Cases partially covered (stubs generated) | 0 |
| Cases with no existing tests (stubs generated) | 7 |
| New stub files created | 2 |
| Total new stubs generated | 7 |
| Tasks fully covered by existing tests (no stub needed) | 0 |
| Tasks needing human review | 0 |
| Auto-filled fields | `test_artifacts`, `verification_commands` |

## Existing Test Coverage Found

| Task ID | Test case | Existing test file | Function | Coverage |
|---------|-----------|-------------------|----------|----------|
| P7-1 | hourglass force boundedness (primitive only) | `packages/mechdsl-core/tests/test_hourglass_control.py` | `flanagan_belytschko_force` zero-on-constant-strain checks | partial — primitive verified, runtime integration not |
| P7-1 | explicit update smoke (primitive only) | `packages/mechdsl-core/tests/test_explicit_dynamics_acceptance.py` | free-vibration / equilibrium acceptance | partial — explicit pipeline verified, Taylor runtime path not |
| P7-2 | Johnson-Cook state primitive | `packages/mechdsl-core/tests/test_johnson_cook.py` | `radial_return`, `yield_stress`, JC tangent | partial — JC model verified, Taylor runtime integration not |
| P7-1 / P7-2 | Public Taylor benchmark API | `packages/mechdsl-core/tests/test_taylor_impact.py` | P10-7 stubs (skipped) | unrelated — public API is owned by Phase 8 (P8-1/P8-2), not Phase 7 |

Phase 7 owns the *internal* Taylor runtime, contact, hourglass integration, and postprocessing; the existing tests above verify the primitive symbols Phase 7 consumes but do not exercise the runtime composition. New stubs are required.

## Generated Stubs

| Task ID | Stub file | Test function | Acceptance criterion covered |
|---------|-----------|---------------|------------------------------|
| P7-1 | `packages/mechdsl-core/tests/test_phase10_taylor_runtime.py` | `TestTaskP7_1::test_explicit_update_smoke_step` | AC-3 (no upstream JC/hourglass drift, runtime exists) |
| P7-1 | `packages/mechdsl-core/tests/test_phase10_taylor_runtime.py` | `TestTaskP7_1::test_wall_contact_prevents_penetration` | AC-2 (rigid-wall contact prevents penetration) |
| P7-1 | `packages/mechdsl-core/tests/test_phase10_taylor_runtime.py` | `TestTaskP7_1::test_hourglass_force_boundedness` | AC-1 (hourglass boundedness in non-impact sanity case) |
| P7-2 | `packages/mechdsl-core/tests/test_phase10_taylor_state.py` | `TestTaskP7_2::test_finite_johnson_cook_state_update` | AC-1 (finite JC stress / temperature / PEEQ) |
| P7-2 | `packages/mechdsl-core/tests/test_phase10_taylor_state.py` | `TestTaskP7_2::test_equivalent_plastic_strain_extraction` | AC-1 (PEEQ extraction non-negative, monotonic) |
| P7-2 | `packages/mechdsl-core/tests/test_phase10_taylor_state.py` | `TestTaskP7_2::test_final_length_postprocessing` | AC-2 (deterministic final-length postprocessing) |
| P7-2 | `packages/mechdsl-core/tests/test_phase10_taylor_state.py` | `TestTaskP7_2::test_mushroom_radius_postprocessing` | AC-2 (deterministic mushroom-radius postprocessing) |

## Tasks Needing Human Review Before Execute

| Task ID | Title | Field | Issue |
|---------|-------|-------|-------|
| - | - | - | - |

## Ready for Execute

Fully scaffolded:
- Task P7-1: Taylor explicit runtime, contact, and hourglass sanity
- Task P7-2: Taylor Johnson-Cook state and postprocessing

Needs human review before execution:
- None

## GitHub Issue Mirroring

Skipped. `dev/tasks/ph10_preq/github_issue_map.json` does not exist; Plan-2-Tasks recorded that GitHub mirroring was disabled during initial generation due to an invalid token at the time. Re-running Plan-2-Tasks (or manually creating the issue map) is required before any phase can publish task issues. All local scaffold artifacts (this report, stubs, JSON updates, tracker pre-fill) are complete and unaffected.
