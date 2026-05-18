---
paths:
  - "packages/mechdsl-core/src/mechdsl/codegen/**"
---

# Code Generation Rules

## Einsum tier classification is mandatory

Every contraction must be classified into Tier 1/2/3 before code emission. Never emit Taichi code without checking the JIT budget first.

- **Tier 1** (native `ti.Matrix @`): rank ≤ 2, dims ≤ 6, output ≤ 36 entries. Use pre-written `@ti.func` from `mechdsl.lib.tensor_ops`.
- **Tier 2** (emitted `ti.static` loops): ≤ 512 unrolled lines per `@ti.func`.
- **Tier 3** (runtime fallback): outer indices become runtime loops, only innermost stays `ti.static`.

## Index treatment

- **Physics indices** (spatial i,j,k,l; material I,J,K,L; Voigt V,W — range ≤ 6): always `ti.static`.
- **Mesh indices** (nodes a,b; elements e — range > 6): always runtime loops. **Never unroll mesh indices.**
- **Quadrature points** (q — typically range 8 for Hex8 2×2×2 Gauss): `ti.static` when the count is an element-type constant AND the loop body accesses Python list constants (e.g., `GRAD_AT_QUAD[q]`). Use runtime when N_QP is mesh-dependent (e.g., adaptive quadrature).
- **Node indices** (a,b — range 8 for Hex8): runtime by default (range > 6). Exception: `ti.static` when the loop body indexes Python list constants (e.g., the `GRAD_AT_QUAD` gather loop).

## Budget enforcement

- 512 max unrolled lines per `@ti.func`.
- 2000 max total per `@ti.kernel`.
- 5000 absolute ceiling — never exceeded.
- If budget is exceeded: restructure (split into sub-functions) or fall back to Tier 3. Never silently exceed.

## Taichi-specific

- Generated code must be a self-contained `.py` file (imports taichi, mesh I/O, driver, etc.).
- Use `ti.field` for global arrays, `ti.Matrix` for small dense tensors.
- The linear solver is imported from the user's existing Taichi library — never reimplement CG/PCG.
- Always emit artifact bundles alongside generated code for debugging and regression testing.
