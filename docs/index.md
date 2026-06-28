# MechDSL

**Write your mechanics in LaTeX. Get tested code back.**

MechDSL is a monorepo of two cooperating LaTeX-to-code compilers for computational solid
mechanics. You describe the math — a boundary-value problem, a strain-energy function, a
return-mapping algorithm — in an ordinary LaTeX document, and the toolchain emits
deterministic, tested [Taichi](https://www.taichi-lang.org/) solver code.

The same `.tex` file renders normally through `pdflatex` **and** is executable input to
the compiler. Your paper's source can be your simulation's source. The guiding principle:

> **Derive models from LaTeX; don't hand-code what the compiler should generate.**

---

## The two packages

<div class="grid cards" markdown>

- :material-function-variant: **[mechdsl-core](mechdsl-core/index.md)**

    ---

    The FEM compiler. Turns `% mechanics` directives and strain-energy functions into
    element kernels, deriving stress **S = ∂Ψ/∂E** and tangent **C = ∂²Ψ/∂E²**
    symbolically. Six-layer pipeline, Total Lagrangian, Hex8, Taichi backend.

    [:octicons-arrow-right-24: Introduction](mechdsl-core/index.md) ·
    [Getting started](mechdsl-core/getting-started.md)

- :material-cog-transfer: **[algo2code](algo2code/index.md)**

    ---

    The algorithm transpiler. Turns LaTeX `algpseudocode` boxes — return-mapping loops,
    the PCG solver — into executable code. Zero runtime dependencies. Consumed by
    mechdsl-core for everything that *isn't* a closed-form expression.

    [:octicons-arrow-right-24: Introduction](algo2code/index.md) ·
    [Getting started](algo2code/getting-started.md)

</div>

The relationship is strict producer/consumer: **mechdsl-core consumes algo2code-generated
artifacts**; algo2code is runtime-free and never imports `mechdsl`. Together they cover
both halves of a constitutive model — the closed-form energy (differentiated by
mechdsl-core) and the iterative algorithm (transpiled by algo2code).

---

## A 60-second taste

```python
from mechdsl import compile_latex

source = r"""
% mechanics dim 3
% mechanics cell hex8
% mechanics formulation total_lagrangian
% mechanics material svk --E 200e3 --nu 0.3
% mechanics boundary fix  --type dirichlet --value 0 --components 0 1 2
% mechanics boundary load --type neumann --traction "0 0 -1000"
"""

bundle = compile_latex(source)
print(bundle.element_ir_summary)   # what got localised (element, quadrature, einsum specs)
print(bundle.content_hash())       # deterministic — same input, same hash, every time
```

That call runs the full pipeline: parse the directives → build the Mechanics IR →
localise to an Element IR → plan the tensor contractions → emit Taichi.

---

## Where to go next

- New here? Start with the **[mechdsl-core introduction](mechdsl-core/index.md)** — it's
  the main package.
- Want to run something? **[Getting started](mechdsl-core/getting-started.md)** takes you
  from a fresh clone to a compiled solver bundle.
- Curious about the design? **[How it works](reference/architecture.md)** is a guided tour
  of the six layers, and the **[FAQ](reference/faq.md)** answers the common questions.
