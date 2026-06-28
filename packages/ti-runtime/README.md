# ti-runtime

Neutral Taichi runtime for **MechDSL** (PlanJune14, PJ-0).

This package is the *seam + primitive* layer of the "Seams & Bodies" architecture:

> MechDSL owns the **seams + primitives** (this package); algo2code generates the
> **bodies** (solvers, preconditioners, constitutive updates, time integrators)
> from LaTeX, injected into these seams.

It contains only stable infrastructure — nothing algorithmic is hardcoded here:

| Module | Contents |
|---|---|
| `vector_ops` | `@ti.kernel` vector primitives: `copy / axpy / xpay / scal / zero / dot / norm2` |
| `tensor_ti`  | Tier-1 `@ti.func` helpers: `det3 / inv3 / F→C→E→J / Voigt / deviatoric / von_mises` |
| `seams`      | injection plumbing: `Operator`, `PreconditionerBase`/`Identity`/`Diagonal`, `Solver`, `LinearSolveContext` |
| `fields`     | `ti.init` + field-allocation boilerplate |
| `hex8`       | Hex8 shape functions, natural-coord gradients, 2×2×2 Gauss quadrature (test harness / element operators) |

## Provenance & invariants

- **One-time harvest** (PlanJune14 D-B) — adapted from NumerixWeave
  (`libs/tisolvers`, `libs/ticonstit`, `apps/tifem`); no ongoing sync.
- **Portable output** (D-D) — generated artifacts depend on `ti_runtime`, never on
  `mechdsl`, so they can later feed NumerixWeave / MOOSE / MFEM.
- **Conventions** follow MechDSL `dev/design_docs/07-CONVENTIONS.md`: Voigt order
  `[xx, yy, zz, xy, xz, yz]`, tensorial (unscaled shears), metric `diag(1,1,1,2,2,2)`.

## Operator / solver contract

A matrix-free operator is an in-place callable `apply(out, x) -> None` computing
`out = A @ x` over Taichi fields. Inject it and run a (generated) solver against it:

```python
ctx = LinearSolveContext()
ctx.set_operator(my_tangent_matvec)        # out = K(u) @ x, matrix-free @ti.kernel
ctx.set_preconditioner(DiagonalPreconditioner(diag))
# a generated PCG body calls ctx.apply_A / ctx.apply_preconditioner + vector_ops
```
