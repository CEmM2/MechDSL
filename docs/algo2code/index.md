# algo2code

`algo2code` transpiles **algorithm boxes** written in LaTeX `algpseudocode` into
executable code (Taichi). Where [mechdsl-core](../mechdsl-core/index.md) derives
*constitutive math* from LaTeX, `algo2code` derives *algorithms* — the iterative solvers
and return-mapping loops that don't come from differentiating an energy.

It is deliberately tiny: **zero runtime dependencies** (stdlib only), and it never imports
`mechdsl`. The relationship is strict producer/consumer — mechdsl-core consumes
`algo2code`-generated artifacts, not the other way around.

---

## Why a separate package

Dissipative models (J2 plasticity, viscoplasticity) and linear solvers (PCG) are
*algorithms*, not closed-form expressions. You can't `sympy.diff` your way to a
return-mapping Newton loop. So MechDSL authors those algorithms once, in LaTeX
`algpseudocode`, and transpiles them — keeping the algorithm in the paper identical to the
algorithm that runs.

Because the package has no runtime dependencies, it's also usable on its own: point it at
any `algpseudocode` block and get a deterministic Python/Taichi function back.

---

## Pipeline

```text
algpseudocode (LaTeX)
   │  algo_parser        parse \State / \For / \If / \Return into an Algorithm AST
   ▼
   │  expr_parser        parse the math expressions in each statement
   ▼
   │  type_inference     infer scalar/array types for declared args + scratch vars
   ▼
backends/taichi_codegen  emit a Taichi-compatible Python function
```

The emitted output is **deterministic** (golden-stable): transpiling the same source
twice yields byte-identical code, which is what lets the codegen be regression-tested.
The authoritative reference is `dev/design_docs/11-ALGO2CODE.md`.

---

## Where to go next

<div class="grid cards" markdown>

- :material-rocket-launch: **[Getting started](getting-started.md)** — install and transpile your first algorithm.
- :material-code-tags: **[Usage](usage.md)** — the `transpile` API, the algorithm library, and the solver seam.
- :material-cards: **[Examples](examples.md)** — runnable transpile snippets for the J2 family and PCG.

</div>
