# Phase 2 Scaffold Validation

## Task JSON Field Validation

| Task ID | Title | Missing / Incomplete Fields | Scaffold Action |
|---------|-------|-----------------------------|-----------------|
| R3.2.1 | CG/PCG breakdown warning (C3) | test_artifacts empty, risks empty | auto-filled |
| R3.2.2 | J2 radial_return stall guard (H3) | test_artifacts empty, risks empty | auto-filled |
| R3.2.3 | Emitted CG failure counter (H4) | test_artifacts empty | auto-filled |
| R3.2.4 | Einsum FLOPS sentinel (H5) | test_artifacts empty | auto-filled |
| R3.2.5 | Ref elastic Newton non-convergence (H6) | test_artifacts empty, risks empty | auto-filled |
| R3.2.6 | Boundary codegen guards (H7+H8) | test_artifacts empty, risks empty | auto-filled |

## Existing Test Coverage Analysis

### R3.2.1 (CG/PCG breakdown warning)
- **No existing tests** for breakdown warnings. test_solver.py tests CG convergence but not breakdown path.
- All 3 cases: **missing**

### R3.2.2 (J2 stall guard)
- **No existing tests** for the stall path. test_j2.py has no `max_iter` or `stall` tests.
- All 3 cases: **missing** (Phase 5 T1-T2 will add the behavioral tests after this fix)

### R3.2.3 (CG failure counter)
- test_emission_verification.py:613 has `test_cg_convergence_warning` — **partial** (checks cg_res but not the counter)
- New stubs needed for counter init, increment, and raise-after-3

### R3.2.4 (FLOPS sentinel)
- test_einsum_optimizer.py:206 asserts `estimated_flops > 0.0` — **will break** after sentinel change
- test_einsum_optimizer.py:153,161 use `estimated_flops=0.0` in construction — need review
- Cases: 1 **must update**, 1 **missing** (warning emission test)

### R3.2.5 (Ref elastic non-convergence)
- test_ref_elastic.py uses `max_iter=50` in all solve calls — tests should pass since they converge
- Cases: 1 **covered** (existing tests pass), 1 **missing** (no test for the raise path)

### R3.2.6 (Boundary codegen guards)
- test_boundary_codegen.py:105 tests face area computation — **partial** (no zero-area test)
- No axis validation tests
- Cases: 3 **missing**, 1 **partial**

## Scaffold Summary

| Metric | Value |
|--------|-------|
| Tasks scaffolded | 6 |
| Test cases assessed | 16 |
| Cases covered by existing tests | 1 |
| Cases partially covered | 3 |
| Cases with no existing tests (stubs needed) | 12 |
| New stub files created | 1 |
| Total new stubs generated | 12 |
| Tasks fully covered by existing tests (no stub needed) | 0 |
| Tasks needing human review | 0 |
| Auto-filled fields | test_artifacts, risks (where empty) |

## Existing Tests That MUST BE UPDATED

| Existing Test | File:Line | Currently Asserts | Breaks After | Action |
|---------------|-----------|-------------------|--------------|--------|
| `test_optimize_flops` | test_einsum_optimizer.py:206 | `estimated_flops > 0.0` | H5 (sentinel → -1.0) | Update: handle -1.0 sentinel |

## Ready for execute-phase

Fully scaffolded:
- R3.2.1: Add CG/PCG breakdown warning (C3)
- R3.2.2: Fix J2 radial_return stall guard (H3)
- R3.2.3: Add emitted CG failure counter (H4)
- R3.2.4: Fix einsum FLOPS fallback to sentinel (H5)
- R3.2.5: Add Newton non-convergence to ref elastic solver (H6)
- R3.2.6: Add boundary codegen zero-area and axis guards (H7+H8)
