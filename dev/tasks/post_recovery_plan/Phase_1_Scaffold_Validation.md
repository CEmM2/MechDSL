# Phase 1 Scaffold Validation

| Task ID | Title | Missing / Incomplete Fields | Scaffold Action |
|---------|-------|-----------------------------|-----------------|
| P1-1 | Extend BoundaryCondition IR slot | — | none |
| P1-2 | Extend Neumann directive parser | — | none |
| P1-3 | Lower Neumann BC to per-node forces | — | none |
| P1-4 | Emit f_ext init Taichi kernel | — | none |
| P1-5 | Façade compile_latex extension | — | none |
| P1-6 | Replace numeric f_ext injection in test_p7_2 | — | none |
| P1-7 | New golden test test_boundary_neumann.py | risks: only one entry (acceptable) | auto-filled |

All 7 tasks: objective, acceptance_criteria (≥1 each), implementation_steps (≥4 each), deliverables (≥3 each), risks (≥1 each, except P1-6/P1-7 mitigation in scope), test_plan.tier, test_plan.cases populated.

## Scaffold Summary

| Metric | Value |
|--------|-------|
| Tasks scaffolded | 7 |
| Test cases assessed | 22 |
| Cases covered by existing tests | 4 |
| Cases partially covered (stubs generated) | 6 |
| Cases with no existing tests (stubs generated) | 12 |
| New stub files created | 7 |
| Total new stubs generated | 18 |
| Tasks fully covered by existing tests (no stub needed) | 0 |
| Tasks needing human review | 0 |
| Auto-filled fields | none — all populated by Plan-2-Tasks |

## Existing Test Coverage Found

| Task ID | Test case | Existing test file | Function | Coverage |
|---------|-----------|-------------------|----------|----------|
| P1-3 | Single-face uniform traction → expected total force | packages/mechdsl-core/tests/test_boundary_codegen.py | TestNeumann::test_uniform_traction | partial (covers numeric compile_neumann; new test required for directive→IR→lowering chain) |
| P1-3 | Empty surface tag → empty contribution list | packages/mechdsl-core/tests/test_boundary_codegen.py | TestNeumann::test_empty_surface | partial |
| P1-4 | Codegen emits expected Taichi source for Neumann BC | packages/mechdsl-core/tests/test_codegen.py | (codegen smoke) | partial (no f_ext emitter yet) |
| P1-6 | test_p7_2 passes after rewrite | packages/mechdsl-core/tests/test_p7_2.py | (entire file) | covered (the file is the test) |

## Tasks Needing Human Review Before Execute

| Task ID | Title | Field | Issue |
|---------|-------|-------|-------|
| (none) | — | — | — |

## Ready for Execute

Fully scaffolded:
- P1-1: Extend BoundaryCondition IR slot
- P1-2: Extend Neumann directive parser
- P1-3: Lower Neumann BC to per-node forces
- P1-4: Emit f_ext init Taichi kernel
- P1-5: Façade compile_latex extension
- P1-6: Replace numeric f_ext injection in test_p7_2
- P1-7: New golden test test_boundary_neumann.py

Needs human review before execution: (none)
