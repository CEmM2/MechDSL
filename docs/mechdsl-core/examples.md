# Examples gallery

Every example here is a runnable script in
[`examples/`](https://github.com/CEmM2/MechDSL/tree/main/examples). They share
a `gen_meshes.py` helper that builds the small structured meshes they use.

!!! tip "Run them with `uv`"
    All commands assume you've run `uv sync --all-packages --all-groups --all-extras`
    first. Prefix everything with `uv run`.

## Canonical: LaTeX → solver

The MVP-stable, documentation-preferred path. Parses `% mechanics` directives and runs
all six layers.

```bash
uv run python examples/run_compile_latex.py
```

See [Getting started](getting-started.md) for a line-by-line walk-through of what this
produces.

## Programmatic API examples

These build a `ProblemIR` directly (the secondary, testing-oriented contract surface) and
exercise classic FEM verification benchmarks.

| Script | What it demonstrates |
|---|---|
| `elastic_cantilever.py` | 3D SVK cantilever, fixed face + tip traction |
| `cook_membrane.py` | Cook's membrane — a standard tapered-panel bending benchmark |
| `necking_bar.py` | J2 plasticity necking bar (load–displacement vs. Simo & Hughes) |
| `plastic_uniaxial.py` | Uniaxial J2 plasticity stress–strain response |
| `patch_test.py` | Constant-strain patch test (must reproduce exactly) |
| `run_pipeline.py` | SVK + J2 end-to-end; writes the emitted Taichi source to disk |

```bash
uv run python examples/elastic_cantilever.py
uv run python examples/cook_membrane.py
uv run python examples/necking_bar.py
uv run python examples/plastic_uniaxial.py
uv run python examples/patch_test.py
uv run python examples/run_pipeline.py
```

## LaTeX energy snippets

The `.tex` files under `examples/` are the exact strain-energy inputs the parser
accepts for the derive-from-energy path:

| File | Model |
|---|---|
| `svk_energy.tex` | St. Venant–Kirchhoff |
| `neo_hookean_energy.tex` | Neo-Hookean |
| `mooney_rivlin_energy.tex` | Mooney-Rivlin |
| `ogden_energy.tex` | Ogden (spectral) |
| `hgo_energy.tex` | HGO (fiber-reinforced) |

```python
from mechdsl import compile_latex

bundle = compile_latex(problem_source, energy_file="examples/mooney_rivlin_energy.tex")
```

## Cyclic plasticity & the Bauschinger effect

The J2 kinematic and mixed hardening models (`mechdsl.lib.plasticity_kinematic` /
`plasticity_mixed`) are exercised on a uniaxial **cyclic** load path
(loading → unloading → reverse) in the test suite. The kinematic/mixed models re-yield in
reverse *below* the forward yield magnitude — the Bauschinger effect — which the isotropic
model cannot reproduce. The hand-written reference kernels that pin this behaviour are
[`ref_j2_kinematic.py`](https://github.com/CEmM2/MechDSL/blob/main/packages/mechdsl-core/tests/ref/ref_j2_kinematic.py)
and
[`ref_j2_mixed.py`](https://github.com/CEmM2/MechDSL/blob/main/packages/mechdsl-core/tests/ref/ref_j2_mixed.py);
see the
[constitutive model catalog](constitutive-models.md#j2-plasticity-kinematic-prager-hardening)
for the API.

## Verification benchmarks

The verification harness (`mechdsl.verify`) compares generated output against hand-written
reference kernels and analytical solutions. The benchmark suite covers the patch test
(exact reproduction), Cook's membrane (within 2% of literature), and the necking bar
(load–displacement within 2% of Simo & Hughes 1998). See
[How it works → verification](../reference/architecture.md#verification).
