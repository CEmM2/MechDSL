# Getting started

This page takes you from an empty environment to a compiled solver bundle.

## Prerequisites

- **Python 3.11, 3.12, or 3.13** — `mechdsl-core` declares
  `requires-python = ">=3.11,<3.14"`.
- Nothing else. There is no compiler toolchain to set up and no system FEM library to
  build; Taichi ships prebuilt wheels and is only needed if you want to *run* solves.

## Install

`mechdsl-core` is on PyPI, so the quickest start is one command:

```bash
pip install mechdsl-core
```

That is all you need for everything on this page: parsing directives, deriving
stress and tangent, and emitting Taichi source. It pulls no Taichi, so the install
stays small.

If you want to **execute and verify** the code you generate, take the full engine
instead — it adds `taichi`, `ti-runtime`, and `algo2code`:

```bash
pip install "mechdsl-core[verify]"
```

??? note "Installing from source instead"
    If you want the runnable `examples/` tree, the test suite, or you intend to
    contribute, clone the [uv](https://docs.astral.sh/uv/) workspace:

    ```bash
    git clone https://github.com/CEmM2/MechDSL.git
    cd MechDSL
    uv sync --all-packages --all-groups --all-extras
    ```

    `uv sync` installs all three workspace packages (`mechdsl-core`, `algo2code`, and
    `ti-runtime`) and their dependencies into a local `.venv`. Inside a source
    checkout, prefix **every** command with `uv run` — never call `python`, `pytest`,
    `ruff`, or `mypy` directly, since they may not be on your PATH or may pick up the
    wrong environment. Verify with the fast test tier:

    ```bash
    uv run pytest -m "not slow and not gpu" -q
    ```

The full install matrix — every package, every extra, the workbench — is on the
[Installation](../installation.md) page.

!!! tip "The commands below"
    Snippets on this page are written for a `pip install`ed MechDSL, so they call
    `python` directly. In a **source checkout**, prefix them with `uv run`
    (`uv run python first_run.py`).

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
python first_run.py
```

A runnable copy of this lives in the repository at
[`examples/run_compile_latex.py`](https://github.com/CEmM2/MechDSL/blob/main/examples/run_compile_latex.py),
so from a source checkout you can skip straight to:

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
- [Browser workbench](../workbench.md) — the same compiler with a UI, if you'd rather
  edit LaTeX in a pane than in a script.
