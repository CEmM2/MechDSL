# Usage

## The `transpile` API

The package exposes one high-level entry point and the parser/codegen stages it composes:

```python
from algo2code import transpile

# Pass any algpseudocode block; get generated source back as a string.
code = transpile(latex_source, backend="taichi")   # 'taichi' is the only backend today
```

`transpile` is `parse_algorithm` → `infer_types` → `generate_taichi` wired together. The
individual stages are exported too (`parse_algorithm`, `infer_types`, `generate_taichi`,
`parse_latex_expr`) if you need to inspect the AST or the inferred types directly.

## The algorithm library

Canonical algorithms live in `algo2code.library`, each backed by a `.tex` source under
`dev/algorithms/`. Every module exposes the verbatim LaTeX as a constant, a getter, and a
convenience transpile wrapper.

| Algorithm | Module | LaTeX constant | Wrapper |
|---|---|---|---|
| PCG linear solver | `library.pcg` | `PCG_ALGORITHM_LATEX` | `transpile(PCG_ALGORITHM_LATEX)` |
| J2 isotropic power-law return-map | `library.radial_return_j2` | `RADIAL_RETURN_J2_LATEX` | `transpile_radial_return_j2()` |
| J2 linear-kinematic return-map | `library.radial_return_j2_kinematic` | `RADIAL_RETURN_J2_KINEMATIC_LATEX` | `transpile_radial_return_j2_kinematic()` |
| J2 mixed-hardening return-map | `library.radial_return_j2_mixed` | `RADIAL_RETURN_J2_MIXED_LATEX` | `transpile_radial_return_j2_mixed()` |

```python
from algo2code.library.radial_return_j2 import (
    RADIAL_RETURN_J2_LATEX,        # the verbatim algpseudocode
    transpile_radial_return_j2,    # convenience wrapper == transpile(RADIAL_RETURN_J2_LATEX)
)

# Either pass the LaTeX directly...
code = transpile(RADIAL_RETURN_J2_LATEX, backend="taichi")

# ...or use the library helper.
code = transpile_radial_return_j2(backend="taichi")
```

## How the J2 family is wired into the solver

The transpiled functions are the **scalar inner loops only** — they solve for the plastic
multiplier `Δλ` given the trial state. The tensor algebra (deviatoric split, von Mises,
stress reconstruction, back-stress update, algorithmic tangent) is orchestrated in Python
inside [mechdsl-core](../mechdsl-core/index.md):

- `mechdsl.lib.plasticity` — isotropic power-law orchestration
- `mechdsl.lib.plasticity_kinematic` — kinematic back-stress orchestration
- `mechdsl.lib.plasticity_mixed` — mixed (tracks both α and β)

Each orchestration wrapper execs the transpiled module at import and calls the resulting
scalar function inside its return-mapping step. This split — algorithm in `algpseudocode`,
tensor bookkeeping in Python — is the pattern any new dissipative model should follow.

## The solver seam

The Newton–Raphson driver (`mechdsl.solver.newton.newton_solve`) calls its linear solver
through the `LinearSolverInterface` protocol. The algo2code-generated PCG solver
(`Algo2CodePCGSolver`) satisfies that interface and is selectable via
`select_linear_solver("generated")` — a line-by-line translation of
`algo2code.library.pcg`, the single source of truth for the PCG algorithm.

This is the seam between the two packages: algo2code emits the PCG and return-map code;
mechdsl-core consumes it behind a stable protocol. algo2code stays runtime-free and never
depends on mechdsl-core. See [How it works → mechdsl-core ↔ algo2code](../reference/architecture.md)
for the full picture.
