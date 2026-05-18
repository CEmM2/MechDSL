# Phase 3 Context Summary — Newton-Raphson Driver

## Conventions

- **Residual sign**: `R = f_ext - f_int(u)` (external minus internal). Newton solves `R → 0`.
- **Convergence criterion**: `||R|| < tol * ||R_0||` (relative tolerance)
- **Dirichlet enforcement**: algebraic elimination — zero constrained DOFs in residual, zero in increment, identity row in matvec
- **float64** throughout, numpy arrays at Python level
- Per `07-CONVENTIONS.md`: tension-positive stress

## Key Principles

- `newton.py` is a **runtime numpy-level** module, NOT generated code. It orchestrates the solver at the Python level using numpy arrays.
- The **emitted** Newton driver in `taichi_printer.py` (lines 609-730) is separate — it operates on Taichi fields in the generated `.py` file.
- `newton_solve()` is **callback-based**: accepts `assemble_residual(u) -> R` and `tangent_matvec(u, v) -> Kv` callables. This allows the same driver for both elastic and plastic problems.
- The Newton driver does NOT assemble forces directly — it delegates to callbacks.
- `adaptive_load_stepping()` (in `load_stepping.py`) expects a callback `newton_solve_fn(load_factor) -> (converged, n_iters, residual_history)`. The `NewtonResult` fields are compatible.
- The reference implementation pattern is in `tests/ref/ref_hex8_elastic.py:solve_elastic` (lines 364-466).

## Pre-resolved Design Decisions

- `assemble_residual: Callable[[NDArray], NDArray]` — takes `u (n_nodes, 3)`, returns `R (n_nodes, 3)`. Caller is responsible for including f_ext.
- `tangent_matvec: Callable[[NDArray, NDArray], NDArray]` — takes `(u, v)`, returns `K(u) @ v`. Caller provides the element-level assembly.
- Dirichlet enforcement is built into `newton_solve()`, not delegated to callbacks:
  - `R[bc_mask] = 0.0` each iteration
  - `du[bc_mask] = 0.0` after CG solve
  - Matvec wrapper: `Kv[bc_mask] = v[bc_mask]` (identity row per `ref_hex8_elastic.py:322`)
- Neumann is handled via the `assemble_residual` callback — caller includes traction in `f_ext`.
- Default linear solver: `CGSolver()` from `import_adapter.py`
- History commit/rollback: `history.commit()` on convergence, `history.rollback()` on failure
- Convergence diagnostics via Python `logging` module (not print)

## Downstream Impact

- Phase 6 (E2E) uses `newton_solve` indirectly — the generated code has its own Newton driver, but the unit/integration tests in P3-T2/P3-T3 validate the runtime driver
- The `newton_solve` callback contract is designed to be compatible with both the reference solver assembly functions AND future Taichi-kernel-based assembly

## Key Files

| File | Current state | Action |
|------|--------------|--------|
| `src/mechdsl/solver/newton.py` | 1-line stub | → ~200 lines |
| `src/mechdsl/solver/__init__.py` | Exports CGSolver, load_stepping, etc. | Add newton_solve, NewtonConfig, NewtonResult |
| `src/mechdsl/solver/import_adapter.py` | 200 lines, CGSolver/PCGSolver | Read only (consume LinearSolverInterface) |
| `src/mechdsl/solver/load_stepping.py` | 144 lines | Read only (consume adaptive_load_stepping) |
| `src/mechdsl/solver/history_fields.py` | 93 lines | Read only (consume HistoryFields) |
| `tests/ref/ref_hex8_elastic.py` | Reference pattern | Read only (use as callback source in tests) |
| `tests/ref/ref_hex8_plastic.py` | Reference pattern | Read only (use in integration test) |
| `tests/test_newton.py` | Does not exist | New test file |

## Reference Pattern: solve_elastic (ref_hex8_elastic.py:364-466)

```
1. u = zeros; u[bc_mask] = bc_values
2. for iter in range(max_iter):
     f_int = assemble_internal_force(u, coords, conn, lam, mu)
     R = f_ext - f_int
     R[bc_mask] = 0.0
     if ||R|| < tol * ||R_0||: break
     matvec = lambda v: apply_tangent_matvec(u, v, coords, conn, lam, mu, bc_mask)
     du = cg_solver.solve(matvec, R, x0, cg_tol, cg_max_iter)
     du[bc_mask] = 0.0
     u += du
```
