# Phase 5 Context Summary: Test Coverage + Tolerance Fixes

## Must Know

### Files modified
- `tests/test_j2.py` — T1 (non-convergence), T2 (stall/negative dl), validation tests, G4 (FD tolerance)
- `tests/test_hex8_tables.py` — T3 (degenerate element)
- `tests/test_boundary_codegen.py` — T4 (invalid face), BC validation tests
- `tests/test_ref_elastic.py` — G1 (rigid body tolerance)
- `tests/test_svk.py` — SVK validation tests
- `tests/test_mesh_io.py` — HexMesh validation tests
- `tests/test_element_ir.py` — QuadratureRule validation tests
- `tests/ref/ref_hex8_elastic.py` — G3 (Dirichlet identity on diagonal)
- `tests/ref/ref_hex8_plastic.py` — G3 (same fix)

### Conventions
- **Test markers**: No `@pytest.mark.slow` for these tests — they are fast unit tests.
- **Error path tests**: Use `pytest.raises(ErrorType, match="expected message pattern")` for deterministic error paths. Use try/except for paths where the outcome depends on numerical behavior.

### Key principles
- **T1**: Force non-convergence with `max_iter=1` — deterministic, always raises.
- **T2**: Uses extreme hardening params (K=1e8, n=0.1) — the outcome (converge or raise) depends on numerical behavior. The test verifies "no silent failure" — either a valid result with `delta_lambda >= 0` or a RuntimeError.
- **G1**: SVK Green-Lagrange strain is rotationally invariant — rigid body rotation forces should be zero to machine precision (1e-10), not 1e-2 * MU (~769 MPa).
- **G4**: Central FD with h=1e-7 on a smooth analytical tangent should match to 1e-8 in the elastic regime. Keep 1e-4 for the plastic regime where the tangent has kinks.
- **G3**: Changing Dirichlet enforcement from zeroing to identity (`Kv[bc_mask] = v[bc_mask]`) is a functional change to both reference solvers. This improves CG conditioning but may change converged solutions slightly.

### Pre-resolved design decisions
- **G3 is marked "deferred" in the plan** but included in Phase 5 with a "test carefully" note. If tests fail after G3, revert G3 and defer to a follow-up.

## Should Know

### Downstream impact
- G3 (Dirichlet identity fix) may change golden files and benchmark results. Phase 6 regenerates golden files.
- The `__post_init__` validation tests (R3.5.3) depend on all Phase 3 tasks completing first.
- T1-T2 tests depend on R3.2.2 (H3 fix) and R3.3.1 (J2 validation).
