# Phase 1 Scaffold Validation

## Task JSON Field Validation

| Task ID | Title | Missing / Incomplete Fields | Scaffold Action |
|---------|-------|-----------------------------|-----------------|
| R3.1.1 | Fix J2 Newton ti.static (C1) | test_artifacts empty | auto-filled |
| R3.1.2 | Fix quadrature loop ti.static (C2) | test_artifacts empty | auto-filled |
| R3.1.3 | Emit RuntimeError on non-convergence (C4) | test_artifacts empty | auto-filled |
| R3.1.4 | Add NaN/Inf guard (C4b) | test_artifacts empty | auto-filled |
| R3.1.5 | Change node loops to runtime (C5) | test_artifacts empty | auto-filled |
| R3.1.6 | Add material model validation (H9) | test_artifacts empty | auto-filled |
| R3.1.7 | Add J2 convergence check (H1) | test_artifacts empty | auto-filled |
| R3.1.8 | Add J2 negative dl guard (H2) | test_artifacts empty | auto-filled |
| R3.1.9 | Fix comments (CM3-7) | test_artifacts empty | auto-filled |
| R3.1.10 | Update convention docs | no test artifacts needed | N/A (manual review) |

## Existing Test Coverage Analysis

### Tests that MUST BE UPDATED (will break after Phase 1 changes)

| Existing Test | File:Line | Currently Asserts | Breaks After | Action |
|---------------|-----------|-------------------|--------------|--------|
| `test_ti_static_physics_loops` | test_taichi_printer.py:220 | `ti.static(range(N_NODES))` present | C5 (R3.1.5) | Update: assert `range(N_NODES)` for node loops, keep `ti.static(range(DIM))` |
| `test_runtime_quad_loop` | test_taichi_printer.py:229 | `for q in range(N_QP):` present | C2 (R3.1.2) | Update: assert `for q in ti.static(range(N_QP)):` |
| `test_no_static_mesh_indices` | test_taichi_printer.py:232-234 | No `ti.static(range(n_elem))` | C2 (R3.1.2) | Update: add exception note for quad loop |
| `test_newton_iteration_loop` | test_plastic_emission.py:114 | `for _it in ti.static(range(20)):` | C1 (R3.1.1) | Update: assert `for _it in range(20):` |
| `test_node_loops_static` | test_emission_verification.py:371-373 | `for a in ti.static(range(N_NODES)):` | C5 (R3.1.5) | Update: assert only GRAD_AT_QUAD gather loop keeps ti.static |

### Tests with PARTIAL coverage (verify behavior but not the specific change)

| Existing Test | File | Covers | For Task |
|---------------|------|--------|----------|
| `test_convergence_check` | test_plastic_emission.py:120-121 | Newton convergence check exists | R3.1.7 (H1) — partial: checks for convergence but not the NaN flag |
| `test_delta_lambda_variable` | test_plastic_emission.py:116-117 | dl variable exists | R3.1.8 (H2) — partial: checks dl exists but not the clamp |
| `test_convergence_check_against_tol` | test_emission_verification.py:573-576 | `res_norm < tol` check | R3.1.3 (C4) — partial: checks convergence but not the RuntimeError on failure |
| `test_cg_convergence_warning` | test_emission_verification.py:608-610 | CG warning print exists | R3.1.3 (C4) — partial |

### Tests with NO coverage (new stubs needed)

| Test Case Needed | For Task | Coverage |
|-----------------|----------|----------|
| Newton non-convergence emits RuntimeError | R3.1.3 (C4) | missing |
| NaN/Inf guard on res_norm in emitted code | R3.1.4 (C4b) | missing |
| Invalid material model raises ValueError | R3.1.6 (H9) | missing |
| J2 return mapping convergence check + NaN flag | R3.1.7 (H1) | missing |
| J2 negative dl clamp in emitted code | R3.1.8 (H2) | missing |
| emit_constitutive_update function rename | R3.1.9 (CM3) | missing |

## Scaffold Summary

| Metric | Value |
|--------|-------|
| Tasks scaffolded | 10 |
| Test cases assessed | 18 |
| Cases covered by existing tests (need update) | 5 |
| Cases partially covered | 4 |
| Cases with no existing tests (stubs needed) | 6 |
| New stub files created | 1 |
| Total new stubs generated | 6 |
| Tasks fully covered by existing tests (no stub needed) | 0 (all need some update or stub) |
| Tasks needing human review | 0 |
| Auto-filled fields | test_artifacts, verification_commands |

## Existing Test Coverage Found

| Task ID | Test case | Existing test file | Function | Coverage |
|---------|-----------|-------------------|----------|----------|
| R3.1.1 | Newton loop uses range(20) | test_plastic_emission.py | test_newton_iteration_loop | **must update** (currently asserts ti.static) |
| R3.1.2 | Quad loop uses ti.static | test_taichi_printer.py | test_runtime_quad_loop | **must update** (currently asserts runtime) |
| R3.1.3 | Newton convergence pattern | test_emission_verification.py | test_convergence_check_against_tol | partial |
| R3.1.4 | NaN guard | — | — | missing |
| R3.1.5 | Node loops runtime | test_taichi_printer.py, test_emission_verification.py | test_ti_static_physics_loops, test_node_loops_static | **must update** |
| R3.1.6 | Invalid material raises | — | — | missing |
| R3.1.7 | J2 convergence + NaN | test_plastic_emission.py | test_convergence_check | partial |
| R3.1.8 | dl clamp | test_plastic_emission.py | test_delta_lambda_variable | partial |
| R3.1.9 | Function rename | — | — | missing |
| R3.1.10 | Convention docs | — | — | N/A (manual) |

## Tasks Needing Human Review Before execute-phase

None — all tasks have sufficient objective, acceptance criteria, and implementation steps.

## CRITICAL: Existing tests that will FAIL after Phase 1

The following 5 existing test assertions must be updated as part of Phase 1 implementation:

1. `test_taichi_printer.py:220` — `ti.static(range(N_NODES))` → `range(N_NODES)` (C5)
2. `test_taichi_printer.py:229` — `for q in range(N_QP):` → `for q in ti.static(range(N_QP)):` (C2)
3. `test_plastic_emission.py:114` — `for _it in ti.static(range(20)):` → `for _it in range(20):` (C1)
4. `test_emission_verification.py:371-373` — Node loop assertions need updating (C5)
5. `test_taichi_printer.py:232-234` — Static mesh index check needs quad exception (C2)

These are NOT optional — if the codegen changes are made without updating these tests, the test suite will fail.

## Ready for execute-phase

Fully scaffolded:
- R3.1.1: Fix J2 Newton ti.static → runtime (C1)
- R3.1.2: Fix quadrature loop to ti.static (C2)
- R3.1.3: Emit raise RuntimeError on Newton non-convergence (C4)
- R3.1.4: Add NaN/Inf guard in emitted Newton driver (C4b)
- R3.1.5: Change node loops to runtime (C5)
- R3.1.6: Add material model validation in emit() (H9)
- R3.1.7: Add emitted J2 convergence check (H1)
- R3.1.8: Add emitted J2 negative dl guard (H2)
- R3.1.9: Fix comments CM3, CM4, CM5, CM7
- R3.1.10: Update convention docs for C2 carve-out
