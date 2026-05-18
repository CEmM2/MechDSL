---
paths:
  - "packages/mechdsl-core/src/mechdsl/codegen/**"
---

# Code Generation Rules

## Einsum tier classification is mandatory

Every contraction must be classified into Tier 1, 2, or 3 before code emission. Never emit Taichi code without checking the JIT budget first.

- Tier 1: native `ti.Matrix @`, rank <= 2, dims <= 6, output <= 36 entries. Prefer pre-written `@ti.func` helpers from `mechdsl.lib.tensor_ops`.
- Tier 2: emitted `ti.static` loops, capped at 512 unrolled lines per `@ti.func`.
- Tier 3: runtime fallback. Outer indices become runtime loops and only the innermost loop stays `ti.static`.

## Index treatment

- Physics indices (`i,j,k,l`, `I,J,K,L`, `V,W`) with range <= 6 stay `ti.static`.
- Mesh indices (`a,b,e`) stay runtime loops. Never unroll mesh indices.
- Quadrature points (`q`) may use `ti.static` only when the count is element-constant and the loop body indexes Python-side constants.
- Node indices (`a,b`) are runtime by default even for Hex8; only use `ti.static` when the loop body is gathering from fixed Python-side constants.

## Budget enforcement

- 512 max unrolled lines per `@ti.func`
- 2000 max lines per `@ti.kernel`
- 5000 absolute ceiling

If a contraction exceeds the budget, restructure it or fall back to Tier 3. Never silently exceed the limit.

## Taichi-specific requirements

- Generated output must be a self-contained `.py` file with the needed imports and driver wiring.
- Use `ti.field` for global arrays and `ti.Matrix` for small dense tensors.
- Import the linear solver from the existing Taichi library; do not reimplement CG or PCG.
- Emit artifact bundles alongside generated code for regression analysis.

