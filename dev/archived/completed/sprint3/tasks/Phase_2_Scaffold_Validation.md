# Phase 2 Scaffold Validation

## JSON Field Validation

| Task ID | Title | Missing / Incomplete Fields | Scaffold Action |
|---------|-------|-----------------------------|-----------------|
| P2-1 | Implement generate_cook_membrane_mesh() | `verification_commands`: empty, `test_artifacts`: empty | auto-filled |
| P2-2 | Test trapezoidal mesh geometry | `verification_commands`: empty, `test_artifacts`: empty, `risks`: empty | auto-filled |
| P2-3 | Cook's membrane benchmark with J2 and reference | `verification_commands`: empty, `test_artifacts`: empty | auto-filled |

## Scaffold Summary

| Metric | Value |
|--------|-------|
| Tasks scaffolded | 3 |
| Test cases assessed | 7 |
| Cases covered by existing tests | 2 |
| Cases partially covered (stubs not needed) | 1 |
| Cases with no existing tests (stubs generated) | 4 |
| New stub files created | 0 (appended to existing test_mesh_io.py) |
| Total new stubs generated | 6 |
| Tasks fully covered by existing tests (no stub needed) | 0 |
| Tasks needing human review | 0 |
| Auto-filled fields | verification_commands (3), test_artifacts (3), risks (1) |

## Existing Test Coverage Found

| Task ID | Test case | Existing test file | Function | Coverage |
|---------|-----------|-------------------|----------|----------|
| P2-3 | Newton convergence all steps | tests/test_benchmarks.py | TestCooksMembrane::test_newton_converges | covered (elastic; needs swap to solve_plastic) |
| P2-3 | Tip displacement direction | tests/test_benchmarks.py | TestCooksMembrane::test_displacement_direction | covered (elastic; needs swap to solve_plastic) |
| P2-3 | Reference comparison 2% | tests/test_benchmarks.py | TestCooksMembrane::test_reference_comparison | partial (skipped; needs trapezoidal mesh + reference value) |

## New Stubs Generated

| Stub file | Class | Function | Covers |
|-----------|-------|----------|--------|
| tests/test_mesh_io.py | TestCookMembraneGeometry | test_corner_coordinates_match_trapezoid | P2-1 AC1, P2-2 AC1 |
| tests/test_mesh_io.py | TestCookMembraneGeometry | test_boundary_tags_present_and_nonempty | P2-1 AC2, P2-2 AC2 |
| tests/test_mesh_io.py | TestCookMembraneGeometry | test_node_and_element_counts | P2-1 AC3 |
| tests/test_mesh_io.py | TestCookMembraneGeometry | test_positive_jacobians | P2-1 risk mitigation |
| tests/test_mesh_io.py | TestCookMembraneGeometry | test_fixed_face_x0_nodes | P2-2 AC2 (fixed face detail) |
| tests/test_mesh_io.py | TestCookMembraneGeometry | test_loaded_face_x1_nodes | P2-2 AC2 (loaded face detail) |

## Tasks Needing Human Review Before Execute

None -- all tasks have complete objectives, acceptance criteria, and implementation steps.

## Ready for Execute

Fully scaffolded:
- P2-1: Implement generate_cook_membrane_mesh() trapezoidal mesh generator
- P2-2: Test trapezoidal mesh geometry
- P2-3: Implement Cook's membrane benchmark with J2 and reference comparison
