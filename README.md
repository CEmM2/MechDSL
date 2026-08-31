# MechDSL

[![CI](https://github.com/CEmM2/MechDSL/actions/workflows/ci.yml/badge.svg)](https://github.com/CEmM2/MechDSL/actions/workflows/ci.yml)

> **Write your mechanics in LaTeX. Get a tested finite-element solver back.**
>
> Describe a boundary-value problem with `% mechanics` directives in an ordinary LaTeX
> document; MechDSL derives the kinematics and stress/tangent symbolically and emits
> deterministic Taichi solver code. The same `.tex` renders normally through `pdflatex`,
> so your paper's source can be your simulation's source. The guiding principle: **derive
> models from LaTeX; don't hand-code what the compiler should generate.**

📖 **New here? Start with the [documentation](docs/index.md)** —
[Getting started](docs/mechdsl-core/getting-started.md) ·
[Core concepts](docs/mechdsl-core/concepts.md) ·
[LaTeX directive reference](docs/mechdsl-core/latex-directives.md) ·
[Constitutive models](docs/mechdsl-core/constitutive-models.md) ·
[Examples](docs/mechdsl-core/examples.md) ·
[FAQ](docs/reference/faq.md)

MechDSL is a monorepo for LaTeX-to-code compilers aimed at computational mechanics.
`mechdsl-core` compiles 3D solid mechanics problems — Total Lagrangian and Updated
Lagrangian formulations with curvilinear reference coordinates — into deterministic
solver code. Supported elements: Hex8, Hex8-R (reduced), Hex20, Tet4, Tet10.
Supported constitutive models: SVK and Neo-Hookean elasticity, Mooney-Rivlin, Ogden,
HGO anisotropic hyperelasticity, J2 power-law plasticity, Perzyna and Johnson-Cook
viscoplasticity, and Lemaitre continuum damage. Backends: Taichi (MVP-stable), MFEM (experimental), MOOSE (experimental).

## Packages

| Package | Path | Description |
|---------|------|-------------|
| `mechdsl-core` | `packages/mechdsl-core/` | LaTeX tensor expressions and programmatic mechanics contexts to FEM solver code |
| `algo2code` | `packages/algo2code/` | LaTeX algorithm boxes (`algpseudocode`) to executable code |
| `ti-runtime` | `packages/ti-runtime/` | Neutral Taichi runtime: vector primitives and solver/operator injection seams |

## Try it in the browser

[`mechdsl-workbench`](https://github.com/CEmM2/mechdsl-workbench) is a companion
browser workbench: LaTeX on the left, the compiled mechanics or transpiled
algorithm on the right. It installs this repository's packages at a pinned
release and is the fastest way to try the language before committing to the
pipeline documentation.

## Installation

### From PyPI

```bash
pip install mechdsl-core              # emission only: LaTeX -> emitted solver source (Taichi-free)
pip install "mechdsl-core[verify]"    # full install: run and verify solves
pip install algo2code                 # just the algorithm transpiler (stdlib-only)
pip install ti-runtime                # just the Taichi runtime
```

The `[verify]` extra is the complete installation — it pulls in `taichi`,
`ti-runtime`, and `algo2code` so compiled problems can actually be solved and
verified. Expect a noticeably larger download (Taichi alone is ~170 MB); the
base `mechdsl-core` install stays lean and is all you need for code emission,
transpilation, and the `mechdsl.integration` capability surface.

### From source

Clone the repository, install the workspace with `uv`, and keep all commands under `uv run`:

```bash
git clone https://github.com/CEmM2/MechDSL.git
cd MechDSL
uv sync
```

Common developer commands:

```bash
uv run pytest -m "not slow and not gpu" --tb=short -q
uv run ruff check packages/
uv run mypy packages/mechdsl-core/src/mechdsl/
```

## Quickstart

### Canonical: LaTeX source → Taichi (via `compile_latex`)

The MVP-stable contract is LaTeX-driven. Pass a LaTeX source string with
`% mechanics` directives to the canonical façade:

```python
from mechdsl import compile_latex

source = r"""
% mechanics dim 3
% mechanics cell hex8
% mechanics formulation total_lagrangian
% mechanics material svk --E 200e3 --nu 0.3
% mechanics boundary fix --type dirichlet --value 0 --components 0 1 2
% mechanics boundary load --type neumann --traction "t_bar"
"""

bundle = compile_latex(source)
print(bundle.element_ir_summary)
print(bundle.content_hash())
```

`compile_latex` parses the directives, adapts them to a `ProblemIR`, and runs
localisation, einsum planning, and Taichi emission.

A runnable version of this canonical first-run example lives in
[`examples/run_compile_latex.py`](examples/run_compile_latex.py):

```bash
uv run python examples/run_compile_latex.py
```

### Programmatic API (advanced / testing aid)

When no LaTeX source is available — for example, in tests or when embedding
the compiler in another tool — you can build the context dict directly with
`build_context()` and forward to `compile()`. This path is **secondary**;
the LaTeX façade above is preferred for documentation, examples, and
production use.

```python
from mechdsl import compile
from mechdsl.frontend import build_context
from mechdsl.ir import (
    BCType,
    BoundaryCondition,
    ElementType,
    Formulation,
    MaterialSpec,
    ProblemIR,
)


def problem_ir_from_context(ctx: dict) -> ProblemIR:
    boundaries = tuple(
        BoundaryCondition(
            name=raw.get("name", raw.get("face", f"bc_{index}")),
            bc_type=BCType(raw["type"]),
            components=tuple(raw.get("dofs", (0, 1, 2))),
            value=raw.get("value", 0.0),
            traction=raw.get("traction"),
        )
        for index, raw in enumerate(ctx["boundaries"])
    )
    return ProblemIR(
        dim=ctx["dim"],
        formulation=Formulation(ctx["formulation"]),
        element_type=ElementType(ctx["cell_type"]),
        material=MaterialSpec(model=ctx["material_type"], params=ctx["params"]),
        boundaries=boundaries,
    )


ctx = build_context(
    dim=3,
    cell_type="hex8",
    formulation="total_lagrangian",
    material_type="svk",
    params={"E": 200e3, "nu": 0.3},
    boundaries=[
        {"name": "fix", "face": "x0", "type": "dirichlet", "dofs": [0, 1, 2], "value": 0.0},
        {"name": "load", "face": "x1", "type": "neumann", "traction": "t_bar"},
    ],
)

bundle = compile(problem_ir_from_context(ctx))
print(bundle.element_ir_summary)
print(bundle.content_hash())
```

Runnable examples live in `examples/`. The canonical LaTeX-first
script is listed first; the remaining scripts use the programmatic API
and are kept as advanced/testing aids:

```bash
uv run python examples/run_compile_latex.py   # canonical: LaTeX -> compile_latex
# Programmatic API examples (advanced / testing aids):
uv run python examples/elastic_cantilever.py
uv run python examples/plastic_uniaxial.py
uv run python examples/cook_membrane.py
uv run python examples/necking_bar.py
uv run python examples/patch_test.py
uv run python examples/run_pipeline.py    # SVK + J2, write emitted Taichi source to disk
```

## Usage examples

### Neo-Hookean hyperelasticity

```python
import numpy as np
from mechdsl.symbolic.models.neo_hookean import NeoHookeanMaterial, pk2_stress, material_tangent_voigt

mat = NeoHookeanMaterial.from_E_nu(E=200e3, nu=0.3)
E_strain = np.diag([0.1, -0.03, -0.03])          # uniaxial stretch
S = pk2_stress(mat, E_strain)                      # PK2 stress (3×3)
C_voigt = material_tangent_voigt(mat, E_strain)    # material tangent (6×6 Voigt)
```

### HGO fiber-reinforced hyperelasticity

```python
import numpy as np
from mechdsl.symbolic.models.hgo import HGOMaterial, HGOModel

mat = HGOMaterial(mu=10.0, k1=2.36, k2=0.84, kappa=1000.0, fiber_dispersion=0.1)
a1 = np.array([1.0, 0.0, 0.0])   # fiber family 1 (axial)
a2 = np.array([0.0, 1.0, 0.0])   # fiber family 2 (circumferential)

model = HGOModel(mat, fiber_dirs=(a1, a2))
E_strain = np.diag([0.2, -0.05, -0.05])
S = model.pk2_stress(E_strain)           # PK2 stress (3×3)
C_voigt = model.voigt_tangent(E_strain)  # material tangent (6×6 Voigt)
```

### Emitting to the MFEM backend (experimental)

> **Support tier: experimental.** The MFEM backend is preserved in tree but is not
> part of the MVP-stable canonical compile path. See the Support tiers section below.

```python
from mechdsl.codegen import compile
from mechdsl.codegen.mfem_printer import emit as emit_mfem
from mechdsl.ir.mechanics_ir import BCType, BoundaryCondition, ElementType, Formulation, MaterialSpec, ProblemIR

problem = ProblemIR(
    dim=3,
    formulation=Formulation.TOTAL_LAGRANGIAN,
    element_type=ElementType.HEX8,
    material=MaterialSpec(model="svk", params={"E": 200e3, "nu": 0.3}),
    boundaries=(
        BoundaryCondition(name="fix", bc_type=BCType.DIRICHLET, field_name="u", components=(0, 1, 2), value=0.0),
        BoundaryCondition(name="load", bc_type=BCType.NEUMANN, field_name="u", traction="0 0 -1000"),
    ),
)
bundle = compile(problem)
mfem_source = emit_mfem(bundle)   # returns C++ source string
```

### Quadratic Tet10 element

```python
from mechdsl.ir.mechanics_ir import BCType, BoundaryCondition, ElementType, Formulation, MaterialSpec, ProblemIR
from mechdsl.codegen import compile

problem = ProblemIR(
    dim=3,
    formulation=Formulation.TOTAL_LAGRANGIAN,
    element_type=ElementType.TET10,
    material=MaterialSpec(model="neo_hookean", params={"mu": 80e3, "kappa": 160e3}),
    boundaries=(
        BoundaryCondition(name="fix", bc_type=BCType.DIRICHLET, field_name="u", components=(0, 1, 2), value=0.0),
    ),
)
bundle = compile(problem)
print(bundle.element_ir_summary)
```

## Documentation

User-facing documentation lives in [`docs/`](docs/) and is built as a
[MkDocs Material](https://squidfunk.github.io/mkdocs-material/) site:

| Page | What it covers |
|------|----------------|
| [Home](docs/index.md) | What MechDSL is and why to use it |
| [Getting started](docs/mechdsl-core/getting-started.md) | Install with `uv`, first solver, `.tex` and energy-derived inputs |
| [Core concepts](docs/mechdsl-core/concepts.md) | LaTeX-first idea, six-layer pipeline, hyperelastic vs. dissipative, support tiers |
| [LaTeX directive reference](docs/mechdsl-core/latex-directives.md) | Every `% mechanics` directive with examples |
| [Constitutive models](docs/mechdsl-core/constitutive-models.md) | Model catalog with runnable snippets |
| [Algorithm transpiler (algo2code)](docs/algo2code/index.md) | How return-maps/PCG are transpiled from `algpseudocode` |
| [Examples gallery](docs/mechdsl-core/examples.md) | Cantilever, Cook's membrane, necking bar, patch test, cyclic plasticity |
| [How it works](docs/reference/architecture.md) | Layers, IR discipline, determinism, verification |
| [FAQ & troubleshooting](docs/reference/faq.md) | Common questions and fixes |

Build or preview the site locally:

```bash
uv sync --group docs
uv run mkdocs serve     # live preview at http://127.0.0.1:8000
uv run mkdocs build     # static site into ./site
```

The authoritative design specs live in the internal `dev/design_docs/` tree of the
private development repository (read-only); the `docs/` site is the friendly,
task-oriented entry point.

## Architecture

The `mechdsl-core` compiler uses a six-layer pipeline:

```text
Layer 1  Frontend       build_context() + LaTeX directives (formulation, metric assignment)
Layer 2  Symbolic       kinematics (TL/UL), objective rates, convected coordinates, constitutive models
Layer 3  Mechanics IR   ProblemIR with formulation, reference frame, stress measure
Layer 4  Element IR     localisation builds element metadata and einsum specs (Hex8/20, Tet4/10)
Layer 5  Einsum IR      contraction-family registry, plans, and JIT-budget-aware optimisation
Layer 6  Codegen        deterministic source emission — Taichi (MVP-stable), MFEM (experimental, C++), MOOSE (experimental)
```

The design-doc set (document map, pipeline structure, verification matrix, and the
post-MVP roadmap) is maintained in the internal `dev/design_docs/` tree of the
private development repository.

Per-layer architecture notes (live alongside the source they describe):

- [`packages/mechdsl-core/src/mechdsl/frontend/ARCHITECTURE.md`](packages/mechdsl-core/src/mechdsl/frontend/ARCHITECTURE.md) — Layer 1 split: NRPyLaTeX as parser of record (math grammar) vs the local adapter / normalizer / validator triad (`parser.py` + `directives.py` + `build_context` + `two_point.py`).

### `mechdsl-core` ↔ `algo2code` integration

The two workspace packages have a strict consumer/producer relationship:
`mechdsl-core` consumes `algo2code`-generated artifacts; `algo2code` is
runtime-free and never imports `mechdsl`. The seam is the
**`LinearSolverInterface`** protocol in `mechdsl.solver.import_adapter`,
which the Newton–Raphson driver (`mechdsl.solver.newton.newton_solve`)
calls through. Concrete adapters (`ScipyCGSolver`, `CGSolver`, `PCGSolver`,
and `Algo2CodePCGSolver`) all satisfy that interface and are selected via
`mechdsl.solver.integration.select_linear_solver(...)`.

The canonical PCG path: `Algo2CodePCGSolver` is a verbatim line-by-line Python translation of the
LaTeX algpseudocode held in `algo2code.library.pcg.PCG_ALGORITHM_LATEX`,
which is the single source of truth for the PCG algorithm. It is opt-in
via `select_linear_solver("generated")` or
`newton_solve(..., linear_solver=...)` — the default remains
`ScipyCGSolver` until further validation.

The authoritative architecture reference for this seam is the `11-ALGO2CODE`
design doc in the internal `dev/design_docs/` tree (§1.1 for the integration
points, §2.5 for the canonical PCG algpseudocode).

## Support tiers

MechDSL classifies every public feature into one of two support tiers:

- **`MVP-stable`** — features supporting the canonical LaTeX-driven compile path:
  Hex8 element, Total Lagrangian formulation, convected curvilinear coordinates,
  St. Venant–Kirchhoff elasticity, J2 plasticity with power-law hardening, and the
  Taichi backend. These are the only surfaces guaranteed to remain stable across
  releases.
- **`experimental`** — features preserved in the tree but not part of the
  canonical contract: MFEM and MOOSE codegen backends, explicit dynamics, non-MVP
  materials (Mooney-Rivlin, Ogden, HGO, viscoplasticity, damage), and non-canonical
  elements (Hex8-R, Hex20, Tet4, Tet10). These remain available for use but may
  shift, lose tests, or become labeled deprecated as development progresses.

The tier split is additive: experimental scope is **not** deleted; it is
labeled so the canonical story is unambiguous.

### `mechdsl.integration` — MVP-stable machine-readable façade

`mechdsl.integration` is the stable, machine-readable Tier-1 surface.
Downstream adapters (Tier-2 AKMS bridge, `MechDSLRunner`) should call only
these five entry points:

| Function | Description | Taichi required? |
|----------|-------------|-----------------|
| `capabilities()` | Returns a machine-readable manifest: version, profiles, backends, actions, models | No |
| `model_catalog()` | Enumerates all constitutive models with tier, dissipative flag, params, and state variables | No |
| `compile_from_sources(*, problem_source, energy_source, energy_file, profile)` | Wraps `compile_latex`; returns `{element_ir_summary, emitted_source, content_hash, derived_energy_present}` | No |
| `transpile_algorithm(algpseudocode, backend)` | Wraps `algo2code.transpile`; returns `{code, entry_point, line_count, valid_python}` | No |
| `verify(kind, params)` | Runs a verification harness; returns `{kind, passed, details}` | **Yes** — only this function |

**Taichi-required-for contract:** `capabilities()` declares
`taichi_required_for: ["verify"]`.  The other four entry points are
guaranteed to never trigger `ti.init` — importing `mechdsl.integration`
and calling them is safe in Taichi-free environments.  Only `verify()`
is permitted to pay the Taichi cost, and it does so lazily (import at
call time, not at module import time).

```python
from mechdsl.integration import capabilities, compile_from_sources, verify

caps = capabilities()          # Taichi-free; returns version, profiles, models, …
print(caps["taichi_required_for"])  # → ["verify"]

result = compile_from_sources(
    problem_source="% mechanics dim 3\n% mechanics cell hex8\n...",
)
print(result["content_hash"])   # 64-char sha-256 hex digest

vr = verify("patch_test", {"lam": 1.0, "mu": 1.0})  # pays the Taichi cost
print(vr["passed"])
```

Do not add entry points to this module without a deliberate design decision; the
surface is a machine API contract, not a convenience library.

### Stability policy

The two tiers carry different commitments:

- **MVP-stable** features have a stable public API and a passing test suite
  on every commit to `main`. Breaking changes require a documented design decision and a
  changelog entry.
- **experimental** features may evolve, lose tests, or be deprecated without
  a release-note entry. They live behind module docstrings that say so
  (see e.g. `packages/mechdsl-core/src/mechdsl/codegen/mfem_printer.py`).
  Reaching for an experimental feature is supported, but only with the
  understanding that the contract is provisional.

## CI and Verification

The repository currently runs three CI tiers:

- `fast` on pushes for the non-slow, non-GPU suites
- `slow` on pull requests for broader validation
- `nightly e2e` for benchmark and full-pipeline coverage, with regression failures filed as issues

Phase 4 added `packages/mechdsl-core/tests/test_full_pipeline.py` to exercise all six compiler layers
from `build_context()` through emitted Taichi source generation.

## Post-MVP progress (Plan B)

| Phase | Feature | Status |
|-------|---------|--------|
| B1 | Updated Lagrangian formulation | Done |
| B2 | Convected curvilinear coordinates | Done |
| B3 | Viscoplasticity (Perzyna, Johnson-Cook) | Done |
| B4 | Hyperelastic models (Neo-Hookean, Mooney-Rivlin, Ogden, HGO) | Done |
| B5 | Additional elements (Tet4, Tet10, Hex20, Hex8-R + hourglass) | Done |
| B6 | Continuum damage (Lemaitre) | Done |
| B7 | Explicit dynamics (lumped mass, central-difference) | Done |
| B8 | MFEM + MOOSE backends with cross-backend verification | Done |
| B9 | Contraction-family registry + family-aware emission dispatch | Done |
| B10 | Verification benchmark suite (thick cylinder, necking, HGO strip) | Done |

The full roadmap lives in the internal `dev/design_docs/` tree of the private
development repository.
