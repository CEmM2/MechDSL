# Phase 5 Scaffold Validation

## Task JSON Field Check

| Task ID | Title | Missing / Incomplete Fields | Scaffold Action |
|---------|-------|-----------------------------|-----------------|
| P5-1 | Tet4 element (4-node, 1-point quadrature) | verification_commands, test_artifacts | auto-filled |
| P5-2 | Tet10 element (10-node quadratic, 4-point quadrature) | verification_commands, test_artifacts | auto-filled |
| P5-3 | Hex20 element (20-node serendipity, 3x3x3 quadrature) | verification_commands, test_artifacts | auto-filled |
| P5-4 | Hex8 reduced integration (1-point quadrature) | verification_commands, test_artifacts | auto-filled |
| P5-5 | Flanagan-Belytschko hourglass control for reduced Hex8 | verification_commands, test_artifacts | auto-filled |
| P5-6 | ElementFactory (uniform element/integration/hourglass API) | verification_commands, test_artifacts | auto-filled |
| P5-7 | Patch test for all elements + hourglass sanity test | verification_commands, test_artifacts | auto-filled |

No `objective`, `acceptance_criteria`, `implementation_steps`, `deliverables`, `risks`, `test_plan.tier`, or `test_plan.cases` fields were missing — all 7 task JSONs were fully populated at Plan-2-Tasks time.

## Existing Test Coverage Search

Searched `packages/mechdsl-core/tests/` for pre-existing coverage of the Phase 5 surface (Tet4, Tet10, Hex20, reduced-Hex8 tables, hourglass control, ElementFactory, patch-test-across-element-types). Grep hits in 11 files were limited to ElementType enum dispatch + rejection tests — no existing tests actually exercise the new element kernels, the integration-rule parameter, the hourglass scheme, or the element factory. Classification: **every test_plan.cases entry is `missing`** — stubs were generated for all 34 cases.

`test_patch_test.py` exists for the Plan A Hex8 full patch test, but it is not parametrised over element type. P5-7's patch-test-all-elements stub supersedes it via explicit parametrisation.

## Stubs Generated

| Task | Stub file | Tests | Tier |
|------|-----------|-------|------|
| P5-1 | `packages/mechdsl-core/tests/test_tet4_basis.py` | 4 | unit |
| P5-2 | `packages/mechdsl-core/tests/test_tet10_basis.py` | 4 | unit |
| P5-3 | `packages/mechdsl-core/tests/test_hex20_basis.py` | 4 | unit |
| P5-4 | `packages/mechdsl-core/tests/test_hex8_reduced.py` | 3 | unit |
| P5-5 | `packages/mechdsl-core/tests/test_hourglass_control.py` | 4 | unit |
| P5-6 | `packages/mechdsl-core/tests/test_element_factory.py` | 8 | unit |
| P5-7 | `packages/mechdsl-core/tests/test_patch_test_all_elements.py` | 5 | integration |
| P5-7 | `packages/mechdsl-core/tests/test_hourglass_suppression.py` | 2 | integration |

Collection verified: 34 stub tests collected, 0 errors.

## Scaffold Summary

| Metric | Value |
|--------|-------|
| Tasks scaffolded | 7 |
| Test cases assessed | 34 |
| Cases covered by existing tests | 0 |
| Cases partially covered (stubs generated) | 0 |
| Cases with no existing tests (stubs generated) | 34 |
| New stub files created | 8 |
| Total new stubs generated | 34 |
| Tasks fully covered by existing tests (no stub needed) | 0 |
| Tasks needing human review | 0 |
| Auto-filled fields | verification_commands, test_artifacts |

## Existing Test Coverage Found

| Task ID | Test case | Existing test file | Function | Coverage |
|---------|-----------|-------------------|----------|----------|
| — | (none) | — | — | — |

## Tasks Needing Human Review Before Execute

| Task ID | Title | Field | Issue |
|---------|-------|-------|-------|
| — | (none) | — | — |

## Ready for Execute

Fully scaffolded:
- P5-1: Tet4 element (4-node, 1-point quadrature)
- P5-2: Tet10 element (10-node quadratic, 4-point quadrature)
- P5-3: Hex20 element (20-node serendipity, 3x3x3 quadrature)
- P5-4: Hex8 reduced integration (1-point quadrature)
- P5-5: Flanagan-Belytschko hourglass control for reduced Hex8
- P5-6: ElementFactory (uniform element/integration/hourglass API)
- P5-7: Patch test for all elements + hourglass sanity test

Needs human review before execution: none.
