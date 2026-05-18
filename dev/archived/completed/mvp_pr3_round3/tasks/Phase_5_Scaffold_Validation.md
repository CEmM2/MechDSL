# Phase 5 Scaffold Validation

Phase 5 tasks ARE test-writing tasks — the deliverables are the tests themselves. No stubs needed; the tasks will be implemented directly as test code.

## Task JSON Field Validation

| Task ID | Title | Missing / Incomplete Fields | Scaffold Action |
|---------|-------|-----------------------------|-----------------|
| R3.5.1 | T1-T2: radial_return error paths | — | N/A |
| R3.5.2 | T3-T4: degenerate element + invalid face | risks: empty | auto-filled (low risk) |
| R3.5.3 | T5: __post_init__ validation tests | risks: empty | auto-filled (low risk) |
| R3.5.4 | G1/G4/G3: tolerance + Dirichlet fix | — | N/A |

## Test File Targets

| Task ID | Test Files to Modify/Create |
|---------|---------------------------|
| R3.5.1 | `test_j2.py` (add 3 test functions) |
| R3.5.2 | `test_hex8_tables.py` + `test_boundary_codegen.py` (add 1 each) |
| R3.5.3 | `test_j2.py`, `test_svk.py`, `test_mesh_io.py`, `test_element_ir.py`, `test_boundary_codegen.py` (add validation tests) |
| R3.5.4 | `test_ref_elastic.py:260`, `test_j2.py:226`, `ref_hex8_elastic.py:271`, `ref_hex8_plastic.py` |

## Scaffold Summary

| Metric | Value |
|--------|-------|
| Tasks scaffolded | 4 |
| Test cases assessed | 12 |
| New stub files needed | 0 (tasks ARE test code) |
| Tasks needing human review | 0 |

## Ready for execute-phase

Fully scaffolded:
- R3.5.1: Add tests T1-T2: radial_return error paths
- R3.5.2: Add tests T3-T4: degenerate element + invalid face
- R3.5.3: Add tests T5: __post_init__ validation tests
- R3.5.4: Tighten test tolerances (G1, G4) + ref solver Dirichlet fix (G3)
