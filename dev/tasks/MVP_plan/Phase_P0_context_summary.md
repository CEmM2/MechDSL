# Phase 0 — Foundation & Interfaces: Context Summary

## Must Know

### Conventions
- **Tooling**: All commands via `uv run` — never invoke python/pytest/ruff/mypy directly.
- **Precision**: `ti.f64` only, `default_fp=ti.f64` in `ti.init()`. No f32 code paths.
- **Package manager**: `uv sync --all-packages --all-groups --all-extras` for full install.

### Key Principles
- This phase establishes the foundation that ALL subsequent phases depend on.
- Every Phase 1–9 task is blocked until Phase 0 completes.
- The `LinearSolverInterface` must match the exact signature from PLAN-A (line 71–76): `solve(matvec_fn, rhs, x0, tol, max_iter) -> tuple[field, int, float]`.
- Tensor ops must be `@ti.func` decorated and use `ti.f64`.

### Pre-resolved Design Decisions
- **Solver is imported, not reimplemented**: LinearSolverInterface wraps an external CG/PCG library.
- **mechdsl-core structure**: 8 subpackages — `frontend`, `symbolic`, `symbolic/models`, `ir`, `lowering`, `codegen`, `solver`, `verify`, `lib`.
- **CI jobs**: Ruff lint, mypy (scoped to each package), pytest (excluding slow/gpu), contraction-budget regression.

## Should Know

### Downstream Impact
- P0.1 (deps): If deps are wrong, nothing installs. Blocks P0.2/P0.4/P0.5.
- P0.2 (skeleton): If subpackages are missing, no module can be implemented. Blocks nearly everything.
- P0.3 (CI): Budget regression stage is a placeholder until Phase 5 (P5.3) wires real tests.
- P0.4 (solver interface): Signature is consumed by reference kernels (P1.1/P1.2) and Newton driver (P7.1).
- P0.5 (tensor ops): Used directly by reference kernels (P1.1/P1.2) and indirectly by generated code.
