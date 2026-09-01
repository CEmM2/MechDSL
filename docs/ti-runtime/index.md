# ti-runtime

`ti-runtime` is the **neutral Taichi runtime** that MechDSL-generated code lands on. It
holds seams and primitives — and nothing algorithmic. Where
[mechdsl-core](../mechdsl-core/index.md) derives constitutive math from LaTeX and
[algo2code](../algo2code/index.md) derives algorithms from LaTeX, `ti-runtime` is the
stable floor both of them emit against.

```bash
pip install ti-runtime
```

It is a genuinely standalone package: it depends on `taichi` and nothing else, and it
never imports `mechdsl`. It also arrives automatically with
`pip install "mechdsl-core[verify]"`.

---

## Seams & Bodies

The architecture has a one-line summary:

> MechDSL owns the **seams and primitives** (this package); algo2code generates the
> **bodies** — solvers, preconditioners, constitutive updates, time integrators — from
> LaTeX, injected into those seams.

The payoff is portability. Generated artifacts depend on `ti_runtime`, **never** on
`mechdsl`, so an emitted kernel can be lifted out of the compiler that produced it and
run wherever `ti-runtime` is installed.

---

## What's in it

| Module | Contents |
|---|---|
| `vector_ops` | `@ti.kernel` vector primitives: `copy`, `axpy`, `xpay`, `scal`, `zero`, `dot`, `norm2`, `vec_add`, `ediv` |
| `tensor_ti` | Tier-1 `@ti.func` helpers: `det3` / `inv3`, the F→C→E→J kinematic chain, Voigt conversion, deviatoric split, von Mises |
| `seams` | Injection plumbing: `Operator`, `PreconditionerBase` / `IdentityPreconditioner` / `DiagonalPreconditioner`, `Solver`, `LinearSolveContext`, `Integrator`, `TimeIntegrationContext`, `AccelSolve` |
| `fields` | `ti.init` and field-allocation boilerplate |
| `hex8` | Hex8 shape functions, natural-coordinate gradients, 2×2×2 Gauss quadrature |

Everything above is re-exported from the package root:

```python
from ti_runtime import LinearSolveContext, DiagonalPreconditioner, axpy, dot, norm2
```

---

## The operator / solver contract

A matrix-free operator is an in-place callable `apply(out, x) -> None` computing
`out = A @ x` over Taichi fields — typically a generated `@ti.kernel`. A preconditioner
mirrors the same shape: `apply(z, r)` sets `z = M⁻¹ r`.

```python
from ti_runtime import LinearSolveContext, DiagonalPreconditioner

ctx = LinearSolveContext()
ctx.set_operator(my_tangent_matvec)              # out = K(u) @ x, matrix-free @ti.kernel
ctx.set_preconditioner(DiagonalPreconditioner(diag))
# a generated PCG body then calls ctx.apply_A / ctx.apply_preconditioner + vector_ops
```

Because `LinearSolveContext` applies *whatever* operator, preconditioner, and solver were
injected, the plumbing is algorithm-agnostic — swapping in a different generated solver
body changes no runtime code.

---

## How mechdsl-core uses it

The generated matrix-free SVK tangent kernel emits `from ti_runtime import ...` for the
Tier-1 tensor helpers, the Hex8 shape gradients, and the `apply_A` injection seam. That
is the `mechdsl-core → ti-runtime` production dependency edge. Since `ti-runtime` carries
Taichi, it rides in the `verify` extra alongside it — keeping the base `mechdsl-core`
install Taichi-free. See [Installation](../installation.md) for the split.

---

## Provenance & conventions

- **One-time harvest.** Adapted from NumerixWeave (`libs/tisolvers`, `libs/ticonstit`,
  `apps/tifem`) in a single pass; there is no ongoing sync.
- **Conventions match the rest of MechDSL:** Voigt order `[xx, yy, zz, xy, xz, yz]`,
  tensorial (unscaled shears), metric `diag(1, 1, 1, 2, 2, 2)`. See
  [Core concepts → conventions](../mechdsl-core/concepts.md#conventions).
