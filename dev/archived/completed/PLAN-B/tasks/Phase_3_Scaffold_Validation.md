# Phase 3 Scaffold Validation

| Task ID | Title | Missing / Incomplete Fields | Scaffold Action |
|---------|-------|-----------------------------|-----------------|
| P3-1 | Perzyna viscoplasticity with backward Euler return map | `verification_commands`, `test_artifacts` | auto-filled |
| P3-2 | Johnson-Cook flow stress + adiabatic temperature evolution | `verification_commands`, `test_artifacts` | auto-filled |
| P3-3 | Consistent viscoplastic algorithmic tangent | `verification_commands`, `test_artifacts` | auto-filled |
| P3-4 | Rate sensitivity + quasi-static limit + thermal softening verification | `verification_commands`, `test_artifacts` | auto-filled |

## Scaffold Summary

| Metric | Value |
|--------|-------|
| Tasks scaffolded | 4 |
| Test cases assessed | 17 |
| Cases covered by existing tests | 0 |
| Cases partially covered (stubs generated) | 0 |
| Cases with no existing tests (stubs generated) | 17 |
| New stub files created | 3 |
| Total new stubs generated | 17 |
| Tasks fully covered by existing tests (no stub needed) | 0 |
| Tasks needing human review | 0 |
| Auto-filled fields | `verification_commands` (4 tasks), `test_artifacts` (4 tasks) |

## Existing Test Coverage Found

| Task ID | Test case | Existing test file | Function | Coverage |
|---------|-----------|-------------------|----------|----------|
| P3-1 | Rate-independent limit matches J2 power-law | tests/test_j2.py | test_plastic_stress_above_yield | partial (J2 reference only) |
| P3-2 | Baseline match to power-law J2 at reference state | tests/test_j2.py | test_plastic_stress_above_yield | partial (J2 reference only) |

No existing tests directly cover Perzyna, Johnson-Cook, or viscoplastic tangent functionality.

## Tasks Needing Human Review Before Execute

| Task ID | Title | Field | Issue |
|---------|-------|-------|-------|
| (none) | | | |

## Ready for Execute

Fully scaffolded:
- P3-1: Perzyna viscoplasticity with backward Euler return map
- P3-2: Johnson-Cook flow stress + adiabatic temperature evolution
- P3-3: Consistent viscoplastic algorithmic tangent
- P3-4: Rate sensitivity + quasi-static limit + thermal softening verification

All 4 tasks have complete `objective`, `acceptance_criteria`, `implementation_steps`, `deliverables`, `risks`, `test_plan`, `verification_commands`, and `test_artifacts`. No human review needed before execution.
