# Phase 3 Scaffold Validation

| Task ID | Title | Missing / Incomplete Fields | Scaffold Action |
|---------|-------|-----------------------------|-----------------|
| P3-1 | Implement necking bar mesh generator with geometric imperfection | `risks`: empty | auto-filled |
| P3-1 | | `verification_commands`: placeholder | auto-filled (Step 4) |
| P3-1 | | `test_artifacts`: placeholder | auto-filled (Step 4) |
| P3-2 | Test necking bar mesh geometry and imperfection | `risks`: empty | auto-filled |
| P3-2 | | `verification_commands`: placeholder | auto-filled (Step 4) |
| P3-2 | | `test_artifacts`: placeholder | auto-filled (Step 4) |
| P3-3 | Generate self-converged reference data (fine mesh) | `verification_commands`: placeholder | auto-filled (Step 4) |
| P3-3 | | `test_artifacts`: placeholder | auto-filled (Step 4) |
| P3-4 | Implement necking bar benchmark with 2% load-displacement comparison | `verification_commands`: placeholder | auto-filled (Step 4) |
| P3-4 | | `test_artifacts`: placeholder | auto-filled (Step 4) |

## Auto-fill Details

### P3-1 risks (auto-filled)
- Imperfection taper function may create degenerate elements if taper zone is too narrow relative to element size
- Coordinate warping must preserve positive Jacobian determinants

### P3-2 risks (auto-filled)
- Test depends on P3-1 mesh generator being implemented first

---

## Scaffold Summary

| Metric | Value |
|--------|-------|
| Tasks scaffolded | 4 |
| Test cases assessed | 11 |
| Cases covered by existing tests | 2 |
| Cases partially covered (stubs not needed) | 2 |
| Cases with no existing tests (stubs generated) | 7 |
| New stub files created | 0 (stubs added to existing files) |
| Total new stubs generated | 10 |
| Tasks fully covered by existing tests (no stub needed) | 0 |
| Tasks needing human review | 0 |
| Auto-filled fields | P3-1 risks, P3-2 risks, all verification_commands, all test_artifacts |

## Existing Test Coverage Found

| Task ID | Test case | Existing test file | Function | Coverage |
|---------|-----------|-------------------|----------|----------|
| P3-4 | Plastic deformation occurs | test_benchmarks.py | TestNeckingBar::test_plastic_deformation_occurs | covered |
| P3-4 | Load-displacement monotonic | test_benchmarks.py | TestNeckingBar::test_load_displacement_monotonic | covered |
| P3-4 | Reference comparison 2% | test_benchmarks.py | TestNeckingBar::test_reference_comparison | partial (skipped) |
| P3-4 | Newton convergence all steps | test_benchmarks.py | TestNeckingBar::test_newton_converges_all_steps | partial (5 steps, needs 20) |

## Stubs Written

| File | Class | Stub methods | For task |
|------|-------|-------------|----------|
| tests/test_mesh_io.py | TestNeckingBarGeometry | test_geometry_dimensions, test_imperfection_reduces_cross_section, test_boundary_tags_symmetry_faces, test_node_element_counts, test_positive_jacobians, test_multi_density[1-1-2], test_multi_density[2-2-4], test_multi_density[4-4-8] | P3-1, P3-2 |
| tests/test_artifacts.py | TestGoldenFilesExist | test_golden_necking_bar_exists | P3-3 |
| tests/test_artifacts.py | TestGoldenNeckingBarMatches | test_golden_necking_bar_keys, test_golden_necking_bar_convergence | P3-3 |

## Tasks Needing Human Review Before Execute

None -- all core fields populated.

## Ready for Execute

Fully scaffolded:
- P3-1: Implement necking bar mesh generator with geometric imperfection
- P3-2: Test necking bar mesh geometry and imperfection
- P3-3: Generate self-converged reference data (fine mesh)
- P3-4: Implement necking bar benchmark with 2% load-displacement comparison
