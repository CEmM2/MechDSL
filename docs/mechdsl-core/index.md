# mechdsl-core

**Write your mechanics in LaTeX. Get a tested finite-element solver back.**

`mechdsl-core` is a LaTeX-to-code compiler for computational solid mechanics. You describe
a boundary-value problem — geometry dimension, element type, formulation, constitutive
model, boundary conditions — using `% mechanics` directives embedded in an ordinary LaTeX
document. The compiler parses that, derives the kinematics and stress/tangent
symbolically, and emits deterministic [Taichi](https://www.taichi-lang.org/) solver code.

The same `.tex` file renders normally through `pdflatex` (the directives are LaTeX
comments) **and** is executable input to the compiler. Your paper's source can be your
simulation's source.

It is published on PyPI under the MIT license:

```bash
pip install mechdsl-core              # emit code — Taichi-free, small install
pip install "mechdsl-core[verify]"    # the full engine — run and verify solves
```

---

## Why a colleague should care

| Without MechDSL | With MechDSL |
|---|---|
| Hand-code element routines, stress kernels, tangents | Write the energy / model in LaTeX; the compiler derives stress **S = ∂Ψ/∂E** and tangent **C = ∂²Ψ/∂E²** for you |
| Constitutive math drifts from the paper it came from | The model in the paper *is* the model that runs |
| Voigt ordering, sign, and index bugs cost days | Conventions are enforced in one place and verified against reference kernels |
| Every new material = a new error-prone kernel | New hyperelastic models are *derived*, not hand-written |

The core principle: **derive models from LaTeX; don't hand-code what the compiler
should generate.**

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
localise to an Element IR → plan the tensor contractions → emit Taichi. See
[Getting started](getting-started.md) to run it yourself.

---

## What it supports today

- **Elements:** Hex8 (MVP-stable), plus Hex8-R, Hex20, Tet4, Tet10 (experimental)
- **Formulations:** Total Lagrangian (MVP-stable), Updated Lagrangian, convected
  curvilinear coordinates
- **Elasticity:** St. Venant–Kirchhoff, Neo-Hookean
- **Hyperelasticity:** Mooney-Rivlin, Ogden, HGO (fiber-reinforced/anisotropic)
- **Plasticity:** J2 with power-law isotropic, linear kinematic, and mixed hardening
  (return-mapping, transpiled via [algo2code](../algo2code/index.md))
- **Viscoplasticity & damage:** Perzyna, Johnson-Cook, Lemaitre
- **Backends:** Taichi (MVP-stable, GPU-capable); MFEM and MOOSE (experimental)

See the full [constitutive model catalog](constitutive-models.md) and the
[support-tier policy](concepts.md#support-tiers).

---

## Where to go next

<div class="grid cards" markdown>

- :material-download: **[Installation](../installation.md)** — every package, extra, and the from-source workflow.
- :material-rocket-launch: **[Getting started](getting-started.md)** — `pip install`, then your first solver in a few minutes.
- :material-school: **[Core concepts](concepts.md)** — the LaTeX-first idea, the six-layer pipeline, and the support tiers.
- :material-code-tags: **[LaTeX directive reference](latex-directives.md)** — every `% mechanics` directive, with examples.
- :material-function-variant: **[Constitutive models](constitutive-models.md)** — the model catalog with runnable snippets.
- :material-cards: **[Examples gallery](examples.md)** — cantilever, Cook's membrane, necking bar, patch test, cyclic plasticity.
- :material-chip: **[ti-runtime](../ti-runtime/index.md)** — the runtime the emitted kernels actually land on.
- :material-application-brackets: **[Browser workbench](../workbench.md)** — the same compiler, driven from a UI.
- :material-help-circle: **[FAQ & troubleshooting](../reference/faq.md)** — common questions and fixes.

</div>
