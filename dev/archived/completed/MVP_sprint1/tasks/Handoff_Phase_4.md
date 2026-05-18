# Phase 3 Handoff

> **From**: Phase 3 agent  
> **To**: Phase 4 agent  
> **Date**: 2026-04-03  
> **Branch**: `sprint1_phase-3`  
> **Plan**: `.claude/plans/serialized-booping-quokka.md`  

---

## Phase 3 Completion Summary

| Task ID | Title | Commit | Tests (pass/total) | Failing Tests |
|---------|-------|--------|--------------------|---------------|
| P3-T1 | Implement newton_solve() | sprint1_phase-3 | 10/10 (smoke) | None |
| P3-T2 | Newton driver unit tests | sprint1_phase-3 | 8/8 (unit: import 3 + unit 5) | None |
| P3-T3 | Newton + load_stepping integration | sprint1_phase-3 | 10/10 (all newton tests) | None |

**Overall test status**: 10/10 task-dedicated tests passing. 725/725 total tests passing (715 Phase 2 baseline + 10 new).

---

## Architecture and State After Phase 3

- **New files created**:
  - `tests/test_newton.py` — 10 tests (3 import, 5 unit, 2 integration)

- **Modified files**:
  - `src/mechdsl/solver/newton.py` — stub → full implementation (~195 lines). Contains `NewtonConfig`, `NewtonResult`, `newton_solve()`
  - `src/mechdsl/solver/__init__.py` — added `newton_solve`, `NewtonConfig`, `NewtonResult` to exports

- **New Taichi fields/kernels**: None (runtime numpy-level code)

- **Interfaces added or changed**:
  - `newton_solve(assemble_residual, tangent_matvec, u, bc_mask, ...)` — callback-based Newton-Raphson driver
  - `NewtonConfig` dataclass: `tol=1e-8`, `max_iter=50`, `cg_tol=1e-10`, `cg_max_iter=2000`
  - `NewtonResult` dataclass: `converged`, `n_iterations`, `residual_history`
  - Compatible with `adaptive_load_stepping` callback contract

---

## Assumptions Made During Phase 3

| Assumption | Where it applies | Rationale | Risk if wrong |
|------------|-----------------|-----------|---------------|
| `tangent_matvec` callback must NOT apply BC enforcement | newton.py contract | newton_solve wraps the callback with `_bc_matvec` that applies identity rows + zeros constrained DOFs in v. Double-enforcement breaks CG. | High — documented in docstring, tested in integration test |
| `assemble_residual` callback returns `R = f_ext - f_int(u)` | newton.py contract | Caller is responsible for including external forces. Newton driver only applies BC zeroing. | Medium — documented in docstring |
| `_bc_matvec` zeros constrained DOFs in direction vector v BEFORE passing to callback | newton.py:159-160 | Matches reference pattern `apply_tangent_matvec` line 308-309. Without this, element-level assembly produces garbage at constrained nodes. | Critical — this was the root cause of the initial test failure |

---

## Known Issues and Deferred Concerns

### Failing tests
None.

### Known bugs or behavioral limitations
- Integration test runs ~170 seconds due to FD tangent matvec on every CG iteration. Not a correctness issue.
- The `_bc_matvec` closure captures `u` by reference (mutable). This is correct for Newton (u changes each iteration) but could be surprising.

### Test coverage gaps
- No test for NaN/Inf detection in residual (newton.py doesn't explicitly guard this — relies on CG failure or residual divergence)
- No test for non-zero Dirichlet BCs (bc_values). The current newton_solve doesn't handle prescribed non-zero displacements — callers must set u[bc_mask] = bc_values before calling.

---

## What Phase 4 Must Know Before Starting

- **Critical dependencies**: Phase 4 (`compile()`) does NOT use `newton_solve` — it chains `localise_and_optimize()` → `ArtifactBundle.from_pipeline()` → `emit()`. The Newton driver is for runtime use, not codegen.

- **High-risk tasks in Phase 4**: P4-T1 is low risk (extract existing `_run_full_pipeline` pattern from test_e2e.py into a proper public API). The main risk is that adding `compile` as a builtin name shadow — use `from mechdsl.codegen import compile` carefully.

- **Recommended starting point**: P4-T1 — simple function, ~25 lines.

- **Key files to read**: `test_e2e.py:74-88` (the `_run_full_pipeline` pattern to extract), `codegen/__init__.py` (where compile() will live).
