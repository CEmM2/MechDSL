# Phase 3 Scaffold Validation

## Task JSON Field Validation

| Task ID | Title | Missing / Incomplete Fields | Scaffold Action |
|---------|-------|-----------------------------|-----------------|
| P3-T1 | Implement newton_solve() | `test_plan.tier`: was "fast" | auto-filled → "unit" |
| P3-T2 | Newton driver unit tests | `test_plan.tier`: was "fast"; `risks`: empty `[]` | auto-filled tier → "unit"; risks: auto-filled (callback mismatch risk from P3-T1 applies here too) |
| P3-T3 | Newton + load_stepping integration test | `test_plan.tier`: was "fast" | auto-filled → "integration" |

All `objective`, `acceptance_criteria`, `implementation_steps`, and `deliverables` fields are populated. No `needs-human-review` flags.

## Scaffold Summary

| Metric | Value |
|--------|-------|
| Tasks scaffolded | 3 |
| Test cases assessed | 10 |
| Cases covered by existing tests | 0 |
| Cases partially covered (stubs generated) | 0 |
| Cases with no existing tests (stubs generated) | 10 |
| New stub files created | 1 |
| Total new stubs generated | 10 |
| Tasks fully covered by existing tests (no stub needed) | 0 |
| Tasks needing human review | 0 |
| Auto-filled fields | test_plan.tier (3), test_artifacts (1) |

## Existing Test Coverage Found

| Task ID | Test case | Existing test file | Function | Coverage |
|---------|-----------|-------------------|----------|----------|
| — | — | — | — | No existing tests cover the runtime newton_solve(). All newton-related tests in the repo test the *emitted* Newton driver (codegen output in test_emission_verification.py, test_taichi_printer.py), not the runtime solver module. |

## Tasks Needing Human Review Before execute-phase

None — all tasks are fully specified.

## Ready for execute-phase

Fully scaffolded:
- P3-T1: Implement newton_solve() with config, BC enforcement, history, exports
- P3-T2: Newton driver unit tests
- P3-T3: Newton + load_stepping integration test
