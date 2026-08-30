# Getting started

This page takes you from a fresh clone to a compiled solver bundle.

## Prerequisites

- **Python 3.12** (the workspace pins `>=3.12,<3.13`).
- **[uv](https://docs.astral.sh/uv/)** — the package/environment manager this project
  uses. Install it with `curl -LsSf https://astral.sh/uv/install.sh | sh` or `brew install uv`.

!!! warning "Always go through `uv run`"
    Never call `python`, `pytest`, `ruff`, or `mypy` directly — they may not be on your
    PATH or may pick up the wrong environment. Prefix every project command with
    `uv run`.

## Install

```bash
git clone https://github.com/CEmM2/MechDSL.git
cd MechDSL
uv sync --all-packages --all-groups --all-extras
```

`uv sync` installs both workspace packages (`mechdsl-core` and `algo2code`) and their
dependencies into a local `.venv`.

Verify the install by running the fast test suite:

```bash
uv run pytest -m "not slow and not gpu" -q
```

## Your first solver bundle

The canonical entry point is `compile_latex`. Create a file `first_run.py`:

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
print(bundle.element_ir_summary)
print("content hash:", bundle.content_hash())
```

Run it:

```bash
uv run python first_run.py
```

A runnable copy of this lives at
[`examples/run_compile_latex.py`](https://github.com/CEmM2/MechDSL/blob/main/examples/run_compile_latex.py):

```bash
uv run python examples/run_compile_latex.py
```

### What just happened

`compile_latex` ran all six compiler layers:

1. **Frontend** parsed the `% mechanics` directives into a context.
2. **Symbolic** derived the kinematics (F → C → E → J) and the SVK stress/tangent.
3. **Mechanics IR** captured the problem as an immutable `ProblemIR`.
4. **Lowering** localised it to an **Element IR** (Hex8 metadata + einsum specs).
5. **Einsum optimiser** planned the tensor contractions within the JIT budget.
6. **Codegen** emitted deterministic Taichi source.

The returned `bundle` carries the Element IR summary and a `content_hash()` — identical
inputs always produce an identical hash, which is what makes the output testable with
golden files.

## Compiling from a `.tex` file

Because the directives are plain LaTeX comments, you can keep them in a real document.
See [`examples/elastic_cantilever.tex`](https://github.com/CEmM2/MechDSL/blob/main/examples/elastic_cantilever.tex):

```latex
% mechanics dim 3
% mechanics cell hex8
% mechanics coord spatial x y z
% mechanics coord material X Y Z
% mechanics material svk --E 200e3 --nu 0.3
% mechanics formulation total_lagrangian
% mechanics boundary fix  --type dirichlet --field u --components 0 1 2 --value 0
% mechanics boundary load --type neumann --traction "0 0 -1000"
```

Read it and pass the contents to `compile_latex`:

```python
from pathlib import Path
from mechdsl import compile_latex

source = Path("examples/elastic_cantilever.tex").read_text()
bundle = compile_latex(source)
```

That same `.tex` renders as a normal PDF through `pdflatex` — the `% mechanics` lines
are invisible to LaTeX.

## Deriving a model from a LaTeX energy

For energy-based hyperelastic models you can hand `compile_latex` the strain-energy
function and let it auto-differentiate. The energy lives in a `.tex` snippet (see
[`examples/neo_hookean_energy.tex`](https://github.com/CEmM2/MechDSL/blob/main/examples/neo_hookean_energy.tex)):

```python
from mechdsl import compile_latex

bundle = compile_latex(problem_source, energy_file="examples/neo_hookean_energy.tex")
```

The compiler parses Ψ, differentiates to get **S = ∂Ψ/∂E** and **C = ∂²Ψ/∂E²**, and
wires the result through the solver. See [Constitutive models](constitutive-models.md)
for the full list of derivable energies.

## Next steps

- [Core concepts](concepts.md) — understand the pipeline and the support tiers before
  going deeper.
- [LaTeX directive reference](latex-directives.md) — the complete directive grammar.
- [Examples gallery](examples.md) — runnable benchmarks (Cook's membrane, necking bar,
  patch test, cyclic plasticity).
