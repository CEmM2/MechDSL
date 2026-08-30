# LaTeX directive reference

Every MechDSL directive is a LaTeX comment that begins with `% mechanics` and sits on
its own line. This page documents the directives exercised by the canonical
`compile_latex` path. Examples here are taken from the runnable inputs in
[`examples/`](https://github.com/CEmM2/MechDSL/tree/main/examples).

!!! note "Authoritative grammar"
    The full DSL grammar (including planned directives) lives in
    `dev/design_docs/02-LATEX-DSL.md`. This page focuses on what the current
    `compile_latex` pipeline consumes, so the snippets you copy actually run.

## General form

```
% mechanics <command> [positional...] [--key value ...]
```

- Directives are processed **in order**; later ones may reference symbols defined
  earlier.
- Option values may be numbers, identifiers, quoted strings, or LaTeX-escaped Greek
  (`\mu`, `\kappa`, `\sigma_y`).

## A complete minimal input

```latex
% mechanics dim 3
% mechanics cell hex8
% mechanics formulation total_lagrangian
% mechanics material svk --E 200e3 --nu 0.3
% mechanics boundary fix  --type dirichlet --value 0 --components 0 1 2
% mechanics boundary load --type neumann --traction "0 0 -1000"
```

---

## `dim` — spatial dimension

```latex
% mechanics dim 3
```

Sets the spatial dimension (`2` or `3`). Affects index ranges, Voigt sizes, and element
defaults. Declare it first.

## `cell` — element type

```latex
% mechanics cell hex8
```

| Value | Element | Tier |
|---|---|---|
| `hex8` | 8-node hexahedron | **MVP-stable** |
| `hex8r` | reduced-integration Hex8 (+ hourglass control) | experimental |
| `hex20` | 20-node hexahedron | experimental |
| `tet4` | 4-node tetrahedron | experimental |
| `tet10` | 10-node tetrahedron | experimental |

## `coord` — coordinate systems

```latex
% mechanics coord spatial  x y z
% mechanics coord material  X Y Z
```

Small-strain problems need only `spatial`. Large-deformation formulations
(Total/Updated Lagrangian) require **both** `spatial` and `material` — that is what lets
the deformation gradient `F_{iI}` carry a spatial index `i` and a material index `I` on
separate manifolds.

## `formulation` — kinematic formulation

```latex
% mechanics formulation total_lagrangian
```

| Value | Meaning | Tier |
|---|---|---|
| `total_lagrangian` | reference-config, PK2/Green–Lagrange | **MVP-stable** |
| `updated_lagrangian` | current-config | experimental |

## `material` — constitutive model

```latex
% mechanics material svk           --E 200e3 --nu 0.3
% mechanics material neo_hookean   --mu  \mu  --kappa \kappa
% mechanics material j2_power_law  --E 200e3 --nu 0.3 --sigma_y0 250 --K 500 --n 0.5
```

The first token after `material` is the model name; each `--key value` maps a parameter
to a value or symbol. See the [constitutive model catalog](constitutive-models.md) for
the full parameter list per model. Model names available include `svk`, `neo_hookean`,
`mooney_rivlin`, `ogden`, `hgo`, `j2_power_law`, `johnson_cook`, `perzyna`, and
`lemaitre`.

## `boundary` — boundary conditions

```latex
% mechanics boundary fix  --type dirichlet --field u --components 0 1 2 --value 0
% mechanics boundary load --type neumann   --traction "0 0 -1000"
```

The first token names the BC. Options:

| Option | Applies to | Meaning |
|---|---|---|
| `--type` | all | `dirichlet`, `neumann` |
| `--field` | all | solution field the BC acts on (default `u`) |
| `--components` | dirichlet | constrained DOF indices, e.g. `0 1 2` |
| `--value` | dirichlet | prescribed value |
| `--traction` | neumann | traction vector as a quoted string, e.g. `"0 0 -1000"` |
| `--surface` | neumann | named surface the traction acts on |

!!! tip "`bc` vs `boundary`"
    There is also a `% mechanics bc <type> ...` form (e.g. `bc dirichlet --boundary left
    --value 0`, `bc body_force --field u --value "0, -rho*g"`). The `boundary
    <name> --type ...` form used in the examples is the one wired through the canonical
    `compile_latex` path — prefer it unless you specifically need `body_force`.

## `fiber` — fiber directions (anisotropic materials)

```latex
% mechanics fiber --family "1, 0, 0"
% mechanics fiber --family "0, 1, 0"
```

Declares a fiber family direction for anisotropic models such as HGO. One directive per
family; the directions become per-element field data
([`FiberFieldSpec`](constitutive-models.md#hgo-anisotropic)).

## `constitutive` — auto-generate a quantity

```latex
% mechanics constitutive Psi   --strain_energy
% mechanics constitutive S     --pk2
% mechanics constitutive sigma --cauchy
```

Tells the engine to auto-derive the named quantity from the material/energy:
`--strain_energy` differentiates Ψ to stress + tangent, `--pk2` produces the PK2 stress,
`--cauchy` push-forwards to the Cauchy stress.

## `field` — solution fields

```latex
% mechanics field u --type vector --space V --order 1
% mechanics field p --type scalar --space Q --order 0
```

Declares solution fields. `--type` is `scalar` or `vector`; `--order` sets the default
polynomial order for codegen.

## `verify` — verification hooks

```latex
% mechanics verify --patch_test
```

Marks the problem for a verification benchmark (e.g. constant-strain patch test). The
[verification harness](../reference/architecture.md#verification) compares generated output against
reference solutions.

---

## Deriving a model from a user-written energy

Directives compose with ordinary LaTeX math. Write Ψ as an equation and point a
`constitutive` directive at it:

```latex
% mechanics constitutive Psi --strain_energy

\Psi = \frac{\mu}{2}\left(\bar{I}_1 - 3\right) + \frac{\kappa}{2}\left(J - 1\right)^2
```

The parser locates the equation defining `\Psi`, parses it to SymPy, and hands it to the
symbolic layer for auto-differentiation — giving you a **user-defined constitutive
model** without touching the compiler source. See
[Constitutive models → user-defined energies](constitutive-models.md#user-defined-energies).
