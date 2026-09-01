# Getting started

This page takes you from an empty environment to a transpiled algorithm.

## Install

`algo2code` is on PyPI and installs on its own — you do not need `mechdsl-core`, and
you do not need the monorepo:

```bash
pip install algo2code
```

It requires Python 3.11, 3.12, or 3.13 (`requires-python = ">=3.11,<3.14"`) and
nothing else.

!!! tip "Zero runtime dependencies"
    `algo2code` is **standard-library only** — its `dependencies` list is literally
    empty, it imports nothing at runtime beyond the Python stdlib, and it never imports
    `mechdsl`. That also means the package directory
    (`packages/algo2code/src/algo2code/`) is self-contained and can be vendored into
    another project by copying it, with no dependency footprint.

`algo2code` also arrives automatically with `pip install "mechdsl-core[verify]"`, since
the full engine uses it to generate the matrix-free PCG solver.

??? note "Installing from source instead"
    `algo2code` is one of the three packages in the MechDSL
    [uv](https://docs.astral.sh/uv/) workspace. For the test suite or to contribute:

    ```bash
    git clone https://github.com/CEmM2/MechDSL.git
    cd MechDSL
    uv sync --all-packages --all-groups --all-extras
    ```

    Inside a source checkout, never call `python` or `pytest` directly — prefix every
    command with `uv run` so it uses the project's locked environment.

See [Installation](../installation.md) for the full matrix across all packages.

## Your first transpile

The single entry point is `transpile(source, backend="taichi")`. Hand it any LaTeX
`algpseudocode` block and it returns generated source as a string. Create `first_algo.py`:

```python
from algo2code import transpile, PCG_ALGORITHM_LATEX

code = transpile(PCG_ALGORITHM_LATEX, backend="taichi")
print(code)        # Taichi-compatible Python source, as text
```

Run it:

```bash
python first_algo.py
```

### What just happened

`transpile` ran the full pipeline on the LaTeX source:

1. **`algo_parser`** parsed the `\State` / `\For` / `\If` / `\Return` statements into an
   `Algorithm` AST.
2. **`expr_parser`** parsed the math expression inside each statement.
3. **`type_inference`** inferred scalar/array types for the declared arguments and scratch
   variables.
4. **`backends/taichi_codegen`** emitted a Taichi-compatible Python function.

The output is **deterministic** — transpiling the same source twice yields byte-identical
code, which is what makes it regression-testable with golden files.

## Turning generated code into a callable

`transpile` returns *source text*. To get a function you can call, `exec` it into a
namespace:

```python
from algo2code import transpile
from algo2code.library.radial_return_j2 import RADIAL_RETURN_J2_LATEX

code = transpile(RADIAL_RETURN_J2_LATEX, backend="taichi")

ns: dict = {}
exec(compile(code, "<algo2code>", "exec"), ns)
radial_return_j2 = ns["radial_return_j2"]   # now a real callable
```

## Next steps

- [Usage](usage.md) — the `transpile` API in full, the canonical algorithm library, and
  how the transpiled code is wired into the mechdsl-core solver.
- [Examples](examples.md) — runnable snippets for the J2 return-map family and the PCG
  solver.
- [Browser workbench](../workbench.md) — paste an `algorithmic` block into a pane and
  read the generated Taichi next to it.
