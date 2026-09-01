# Installation

Every MechDSL package is published on PyPI under the MIT license, so the fastest way
in is `pip install`. Installing from source with [uv](https://docs.astral.sh/uv/) is
the path for contributors and for anyone who wants the runnable `examples/` tree.

!!! tip "In a hurry?"
    `pip install "mechdsl-workbench[mechdsl]"` then `mechdsl-workbench` gives you the
    whole toolchain behind a browser UI — LaTeX in the left pane, generated Taichi in
    the right. See [the workbench page](workbench.md).

## What's on PyPI

| Install | What it gives you |
|---|---|
| `pip install mechdsl-core` | The FEM compiler: LaTeX → emitted Taichi solver source. **Taichi-free.** ([PyPI](https://pypi.org/project/mechdsl-core/)) |
| `pip install "mechdsl-core[verify]"` | The full engine — adds `taichi`, `ti-runtime`, and `algo2code` so you can *run* and *verify* solves |
| `pip install algo2code` | The algorithm transpiler on its own. **Zero runtime dependencies**, stdlib only. ([PyPI](https://pypi.org/project/algo2code/)) |
| `pip install ti-runtime` | The neutral Taichi runtime: vector primitives, Tier-1 `@ti.func` helpers, injection seams. ([PyPI](https://pypi.org/project/ti-runtime/)) |
| `pip install "mechdsl-workbench[mechdsl]"` | The browser workbench plus the engine, in one command. ([PyPI](https://pypi.org/project/mechdsl-workbench/)) |

All five are released together and currently sit at **0.2.1**.

## Requirements

- **Python 3.11–3.13** for `mechdsl-core`, `algo2code`, and `ti-runtime`
  (`requires-python = ">=3.11,<3.14"`).
- **Python 3.12** for `mechdsl-workbench`, which pins `>=3.12,<3.13`.
- No compiler toolchain, no system FEM library. Taichi ships prebuilt wheels and
  JIT-compiles to CPU or GPU at run time.

## Install from PyPI

### Just the compiler (lean, Taichi-free)

```bash
pip install mechdsl-core
```

This is everything you need to **emit** code: parse `% mechanics` directives, derive
stress and tangent symbolically, plan contractions, and print Taichi source. It pulls
only `sympy`, `numpy`, `scipy`, `opt-einsum`, `pyyaml`, and `nrpylatex` — no Taichi, so
the install stays small and imports cleanly in Taichi-free environments.

```python
from mechdsl import compile_latex

bundle = compile_latex("% mechanics dim 3\n% mechanics cell hex8\n"
                       "% mechanics formulation total_lagrangian\n"
                       "% mechanics material svk --E 200e3 --nu 0.3\n")
print(bundle.content_hash())
```

### The full engine (run and verify solves)

```bash
pip install "mechdsl-core[verify]"
```

The `verify` extra adds `taichi`, `ti-runtime`, and `algo2code` — the complete
installation. Expect a noticeably larger download; Taichi alone is around 170 MB.
Take this one if you want to execute generated kernels, run the verification
harness, or use the generated matrix-free PCG solver.

!!! info "Why the split?"
    Only `mechdsl.integration.verify()` ever touches Taichi, and it imports it lazily
    at call time. The emit, transpile, `capabilities()`, and `model_catalog()`
    surfaces are proven Taichi-free by the test suite, so downstream consumers can
    depend on `mechdsl-core` for code generation without pulling Taichi into their
    dependency closure.

### The satellite packages alone

```bash
pip install algo2code     # LaTeX algpseudocode -> executable code; stdlib-only
pip install ti-runtime    # Taichi primitives + injection seams for generated code
```

`algo2code` never imports `mechdsl`, and `ti-runtime` never imports `mechdsl` either —
generated artifacts depend on `ti_runtime`, not on the compiler that produced them. Both
are usable standalone.

## Install from source

Use this if you want the `examples/` scripts, the test suite, or you intend to
contribute. The repository is a [uv](https://docs.astral.sh/uv/) workspace holding all
three monorepo packages.

```bash
git clone https://github.com/CEmM2/MechDSL.git
cd MechDSL
uv sync --all-packages --all-groups --all-extras
```

Verify the install with the fast test tier:

```bash
uv run pytest -m "not slow and not gpu" -q
```

!!! warning "Inside the workspace, always go through `uv run`"
    Never call `python`, `pytest`, `ruff`, or `mypy` directly in a source checkout —
    they may not be on your PATH or may pick up the wrong environment. Prefix every
    project command with `uv run`. (This applies to the source workflow only; a
    `pip install`ed MechDSL is an ordinary package in whatever environment you put it.)

## Command-line entry points

`mechdsl-core` installs one console script:

```bash
mechdsl-lawgen --help              # emit constitutive-law carriers for the ticonstit target
mechdsl-lawgen compile law.yaml    # ...with --dry-run to print the plan and write nothing
```

`mechdsl-workbench` installs its own launcher — see [the workbench page](workbench.md).

## Where to next

<div class="grid cards" markdown>

- :material-rocket-launch: **[mechdsl-core getting started](mechdsl-core/getting-started.md)** — compile your first solver bundle.
- :material-cog-transfer: **[algo2code getting started](algo2code/getting-started.md)** — transpile your first algorithm.
- :material-application-brackets: **[Browser workbench](workbench.md)** — try the language without writing a script.
- :material-help-circle: **[FAQ & troubleshooting](reference/faq.md)** — when something doesn't install or run.

</div>
