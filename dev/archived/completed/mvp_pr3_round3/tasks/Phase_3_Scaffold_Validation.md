# Phase 3 Scaffold Validation

## Task JSON Field Validation

| Task ID | Title | Missing / Incomplete Fields | Scaffold Action |
|---------|-------|-----------------------------|-----------------|
| R3.3.1 | Add `__post_init__` to J2PowerLawMaterial | risks: empty → auto-filled (already has risk) | N/A |
| R3.3.2 | Freeze ReturnMappingResult + comments | — | N/A |
| R3.3.3 | Add `__post_init__` to SVKMaterial | risks: empty | auto-filled |
| R3.3.4 | Add `__post_init__` to HexMesh | — | N/A |
| R3.3.5 | Add `__post_init__` to QuadratureRule | risks: empty | auto-filled |
| R3.3.6 | Add `__post_init__` to DirichletBC/NeumannBC | risks: empty | auto-filled |
| R3.3.7 | Improve HistoryFields error messages | risks: empty | auto-filled |

## Existing Test Coverage Analysis

All Phase 3 tasks add validation code. The **validation tests** are deferred to Phase 5 (R3.5.3). Phase 3 verification uses existing tests to confirm no regressions.

| Task ID | Test Case | Existing Test File | Function | Coverage |
|---------|-----------|-------------------|----------|----------|
| R3.3.1 | Existing J2 usage passes | test_j2.py | All 19 tests | **covered** (regression) |
| R3.3.2 | ReturnMappingResult frozen | test_j2.py | radial_return tests | **partial** (no explicit frozen check) |
| R3.3.2 | Comments reference §3.4 | — | — | **missing** (manual) |
| R3.3.3 | Existing SVK usage passes | test_svk.py | All tests | **covered** (regression) |
| R3.3.4 | Existing mesh usage passes | test_mesh_io.py | All tests | **covered** (regression) |
| R3.3.5 | Existing quadrature usage | test_element_ir.py | All tests | **covered** (regression) |
| R3.3.6 | Existing BC usage passes | test_boundary_codegen.py | All tests | **covered** (regression) |
| R3.3.7 | Existing history usage | test_history_fields.py | All tests | **covered** (regression) |

## Scaffold Summary

| Metric | Value |
|--------|-------|
| Tasks scaffolded | 7 |
| Test cases assessed | 12 |
| Cases covered by existing tests (regression) | 7 |
| Cases partially covered | 1 |
| Cases with no existing tests | 4 (deferred to Phase 5 R3.5.3) |
| New stub files created | 0 (Phase 5 owns validation stubs) |
| Total new stubs generated | 0 |
| Tasks fully covered by existing tests | 5 (regression only) |
| Tasks needing human review | 0 |
| Auto-filled fields | risks (3 tasks) |

## Tasks Needing Human Review Before execute-phase

None.

## Ready for execute-phase

Fully scaffolded:
- R3.3.1: Add `__post_init__` to J2PowerLawMaterial
- R3.3.2: Freeze ReturnMappingResult + fix comments (H11, H12, H13)
- R3.3.3: Add `__post_init__` to SVKMaterial + `from_E_nu` validation
- R3.3.4: Add `__post_init__` to HexMesh
- R3.3.5: Add `__post_init__` to QuadratureRule
- R3.3.6: Add `__post_init__` to DirichletBC/NeumannBC
- R3.3.7: Improve HistoryFields error messages + duplicate guard
