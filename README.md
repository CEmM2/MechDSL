# MechDSL

[![CI](https://github.com/SOSOVSKI/MechDSL/actions/workflows/ci.yml/badge.svg)](https://github.com/SOSOVSKI/MechDSL/actions/workflows/ci.yml)

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

## Installation

Clone the repository, install the workspace with `uv`, and keep all commands under `uv run`:

```bash
git clone https://github.com/SOSOVSKI/MechDSL.git
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
[`dev/examples/run_compile_latex.py`](dev/examples/run_compile_latex.py):

```bash
uv run python dev/examples/run_compile_latex.py
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

Runnable examples live in `dev/examples/`. The canonical LaTeX-first
script is listed first; the remaining scripts use the programmatic API
and are kept as advanced/testing aids:

```bash
uv run python dev/examples/run_compile_latex.py   # canonical: LaTeX -> compile_latex
# Programmatic API examples (advanced / testing aids):
uv run python dev/examples/elastic_cantilever.py
uv run python dev/examples/plastic_uniaxial.py
uv run python dev/examples/cook_membrane.py
uv run python dev/examples/necking_bar.py
uv run python dev/examples/patch_test.py
uv run python dev/examples/run_pipeline.py    # SVK + J2, write emitted Taichi source to disk
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

Design docs are authoritative and read-only:

- [`dev/design_docs/00-OVERVIEW.md`](dev/design_docs/00-OVERVIEW.md) for the document map
- [`dev/design_docs/01-ARCHITECTURE.md`](dev/design_docs/01-ARCHITECTURE.md) for pipeline structure
- [`dev/design_docs/08-VERIFICATION.md`](dev/design_docs/08-VERIFICATION.md) for the verification matrix
- [`dev/design_docs/PLAN-B.md`](dev/design_docs/PLAN-B.md) for post-MVP roadmap phases

Per-layer architecture notes (live alongside the source they describe):

- [`packages/mechdsl-core/src/mechdsl/frontend/ARCHITECTURE.md`](packages/mechdsl-core/src/mechdsl/frontend/ARCHITECTURE.md) — Layer 1 split: NRPyLaTeX as parser of record (math grammar) vs the local adapter / normalizer / validator triad (`parser.py` + `directives.py` + `build_context` + `two_point.py`). Introduced by recovery-plan Phase 2 (R1.3).

### `mechdsl-core` ↔ `algo2code` integration

The two workspace packages have a strict consumer/producer relationship:
`mechdsl-core` consumes `algo2code`-generated artifacts; `algo2code` is
runtime-free and never imports `mechdsl`. The seam is the
**`LinearSolverInterface`** protocol in `mechdsl.solver.import_adapter`,
which the Newton–Raphson driver (`mechdsl.solver.newton.newton_solve`)
calls through. Concrete adapters (`ScipyCGSolver`, `CGSolver`, `PCGSolver`,
and `Algo2CodePCGSolver`) all satisfy that interface and are selected via
`mechdsl.solver.integration.select_linear_solver(...)`.

Recovery-plan Phase 6 landed the canonical PCG path (P6-1 through P6-3):
`Algo2CodePCGSolver` is a verbatim line-by-line Python translation of the
LaTeX algpseudocode held in `algo2code.library.pcg.PCG_ALGORITHM_LATEX`,
which is the single source of truth for the PCG algorithm. It is opt-in
via `select_linear_solver("generated")` or
`newton_solve(..., linear_solver=...)` — the default remains
`ScipyCGSolver` until further validation. The `algo2code`-generated
radial-return constitutive seam (Plan A Phase A9) is deferred per
recovery plan §P6-4.

The authoritative architecture reference for this seam is
[`dev/design_docs/11-ALGO2CODE.md`](dev/design_docs/11-ALGO2CODE.md)
(see §1.1 for the integration points and §2.5 for the canonical PCG
algpseudocode).

## Support tiers

MechDSL classifies every public feature into one of two support tiers (introduced by
[`dev/plans/recovery_plan_latex_contract.md`](dev/plans/recovery_plan_latex_contract.md)
Phase 1):

- **`MVP-stable`** — features supporting the canonical LaTeX-driven compile path:
  Hex8 element, Total Lagrangian formulation, convected curvilinear coordinates,
  St. Venant–Kirchhoff elasticity, J2 plasticity with power-law hardening, and the
  Taichi backend. These are the only surfaces guaranteed to remain stable across
  recovery work.
- **`experimental`** — features preserved in the tree but not part of the
  canonical contract: MFEM and MOOSE codegen backends, explicit dynamics, non-MVP
  materials (Mooney-Rivlin, Ogden, HGO, viscoplasticity, damage), and non-canonical
  elements (Hex8-R, Hex20, Tet4, Tet10). These remain available for use but may
  shift, lose tests, or become labeled deprecated as the recovery plan
  progresses.

The recovery plan is additive: experimental scope is **not** deleted; it is
labeled so the canonical story is unambiguous.

### Stability policy

The two tiers carry different commitments:

- **MVP-stable** features have a stable public API and a passing test suite
  on every commit to `main`. Breaking changes require an entry in the
  recovery plan (or a follow-up plan) and a tracker row that follows the
  status vocabulary in [`dev/tracking/STATUS_LEGEND.md`](dev/tracking/STATUS_LEGEND.md).
- **experimental** features may evolve, lose tests, or be deprecated without
  a release-note entry. They live behind module docstrings that say so
  (see e.g. `packages/mechdsl-core/src/mechdsl/codegen/mfem_printer.py`).
  Reaching for an experimental feature is supported, but only with the
  understanding that the contract is provisional.

The full motivation, including the historical drift that led to this
policy, is in [`dev/plans/recovery_plan_latex_contract.md`](dev/plans/recovery_plan_latex_contract.md)
and [`dev/reviews/frontend_drift_history.md`](dev/reviews/frontend_drift_history.md).

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

See [`dev/design_docs/PLAN-B.md`](dev/design_docs/PLAN-B.md) for the full roadmap.
