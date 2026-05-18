# Phase 4 Scaffold Validation

## Task JSON Field Validation

| Task ID | Title | Missing / Incomplete Fields | Scaffold Action |
|---------|-------|-----------------------------|-----------------|
| P4-T1 | Implement compile() | `test_plan.tier`: was "fast"; `risks`: empty `[]` | auto-filled tier → "integration"; risks: low (simple pipeline wiring) |
| P4-T2 | Write compile pipeline tests | `test_plan.tier`: was "fast"; `risks`: empty `[]` | auto-filled tier → "integration"; risks: low (test-only task) |

All `objective`, `acceptance_criteria`, `implementation_steps`, and `deliverables` fields are populated.

## Scaffold Summary

| Metric | Value |
|--------|-------|
| Tasks scaffolded | 2 |
| Test cases assessed | 10 |
| Cases covered by existing tests | 0 |
| Cases partially covered (stubs generated) | 4 (test_e2e has _run_full_pipeline; test_taichi_printer has ast.parse) |
| Cases with no existing tests (stubs generated) | 6 |
| New stub files created | 1 |
| Total new stubs generated | 8 |
| Tasks fully covered by existing tests (no stub needed) | 0 |
| Tasks needing human review | 0 |
| Auto-filled fields | test_plan.tier (2), test_artifacts (1) |

## Existing Test Coverage Found

| Task ID | Test case | Existing test file | Function | Coverage |
|---------|-----------|-------------------|----------|----------|
| P4-T1 | compile() produces bundle | `test_e2e.py` | `_run_full_pipeline` (lines 75-88) | partial — tests pipeline but not `compile()` API |
| P4-T1 | Deterministic | `test_e2e.py` | `test_pipeline_deterministic` | partial — tests _run_full_pipeline determinism |
| P4-T2 | ast.parse | `test_taichi_printer.py` | `test_ast_parse_svk`, `test_ast_parse_j2` | partial — tests emission, not compile() output |
| P4-T2 | Deterministic | `test_e2e.py` | `test_pipeline_deterministic` | partial — tests _run_full_pipeline |

## Tasks Needing Human Review Before execute-phase

None.

## Ready for execute-phase

Fully scaffolded:
- P4-T1: Implement compile() function and top-level export
- P4-T2: Write compile pipeline tests
