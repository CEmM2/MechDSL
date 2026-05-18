# 04 — Mechanics IR

---

## 1  Purpose

Mechanics IR is the **semantic center** of the compiler pipeline. It owns the model meaning independently of any specific backend, symbolic library, or code generation strategy.

The rule is: **SymPDE symbolic forms do not emit backend code directly.** Instead, all symbolic information is first lowered into Mechanics IR, which serves as the single source of truth for the problem definition. Downstream stages (Element IR, Einsum IR, backend scheduling, code emission) consume Mechanics IR — never raw SymPy trees.

---

## 2  Core entities (MVP)

The MVP requires only the subset needed for 3D Hex8 Total Lagrangian elasto-plasticity with convected coordinates:

```python
@dataclass
class ProblemIR:
    """Top-level problem definition."""
    name: str
    dim: int                         # 3 for MVP
    cell_type: str                   # "hex8"
    kinematics: str                  # "total_lagrangian"
    formulation: str                 # "convected" | "cartesian"
    constitutive: str                # "hooke_power_law"
    fields: list[FieldIR]
    tests: list[FieldIR]
    parameters: dict[str, Symbol]
    material: MaterialIR
    bodyforce: BodyForceIR | None
    tractions: list[TractionIR]
    residual: ResidualFormIR
    dirichlet_bcs: list[DirichletBCIR]
    neumann_bcs: list[NeumannBCIR]
    domain: DomainIR
    mesh_contract: MeshContractIR

@dataclass
class DomainIR:
    """Domain and boundary region definitions."""
    name: str                        # e.g. "Omega_0"
    dim: int
    boundary_regions: list[BoundaryRegionIR]

@dataclass
class BoundaryRegionIR:
    """A named boundary region with mesh-tag association."""
    name: str                        # e.g. "Gamma_u", "Gamma_t"
    mesh_tag: str | int | None       # resolved at bind time
    kind: str                        # "dirichlet" | "neumann"

@dataclass
class FieldIR:
    """A vector or scalar field."""
    name: str                        # e.g. "u"
    components: int                  # 3 for 3D vector
    space: str                       # "H1"
    kind: str                        # "vector" | "scalar"

@dataclass
class MaterialIR:
    """Material model specification."""
    model: str                       # "hooke_power_law" for MVP
    params: dict[str, Symbol]        # E, nu, sigma_y0, K, n
    elastic_law: str                 # "st_venant_kirchhoff"
    hardening_law: str               # "power_law"
    has_state_variables: bool         # True for plasticity
    state_variables: list[str]       # ["peeq", "stress_old", ...]

@dataclass
class ResidualFormIR:
    """Variational residual in symbolic form."""
    integrand: Expr                  # SymPy expression
    domain_integral: bool
    boundary_integrals: list         # traction contributions

@dataclass
class DirichletBCIR:
    """Essential boundary condition."""
    region: str                      # references BoundaryRegionIR.name
    field: str                       # field name
    components: list[int] | None     # None = all, [0,2] = x and z
    value: Expr | float              # prescribed value

@dataclass
class NeumannBCIR:
    """Natural boundary condition (traction)."""
    region: str
    value: Expr | list[Expr]         # traction vector or expression

@dataclass
class MeshContractIR:
    """What the runtime expects from the mesh."""
    cell_type: str
    dim: int
    requires_boundary_tags: list[str]
    requires_orientation: bool
```

---

## 3  Future nonlinear entities

These are **not** required for the MVP but are reserved in the IR design for Plan B extensions:

| Entity | Purpose | Plan B phase |
|--------|---------|-------------|
| `StateVariableIR` | Per-quadrature-point internal variables (beyond MVP's `peeq`) | B3 |
| `HistoryVariableIR` | Old-step copies of state variables | B3 |
| `ConfigurationIR` | Reference vs current config metadata on fields/gradients | B1 |
| `KinematicsIR` | Deformation measures (F, C, E, J, b) as first-class IR nodes | B1 |
| `FreeEnergyIR` | Strain energy potential for hyperelastic models | B4 |
| `DissipationPotentialIR` | For viscoplastic flow rules | B3 |
| `LocalUpdateRuleIR` | Return-mapping specification | B3 |
| `AlgorithmicTangentIR` | Consistent tangent operator specification | B3 |
| `IncrementControlIR` | Load stepping and adaptive control metadata | B5 |
| `FramePolicyIR` | Objective rate selection (Jaumann, Truesdell, Green-Naghdi) | B1 |
| `ConvectedCoordinateMapIR` | Metric tensors, Christoffel symbols | MVP (basic), B2 (full) |

The MVP uses `ConvectedCoordinateMapIR` in its basic form (metric tensors $G_{IJ}$, $g_{IJ}$ and the deformation gradient expressed in convected components). The full version with Christoffel symbols and covariant derivatives is Plan B phase B2.

---

## 4  IR lifecycle

```
LaTeX source
    │
    ▼
Layer 1 (Parser) ──→ context dict (raw parsed data)
    │
    ▼
Layer 2 (Symbolic Engine) ──→ symbolic expressions (stress, tangent, kinematics)
    │
    ▼
╔══════════════════════════════════════╗
║  Mechanics IR construction           ║
║                                      ║
║  Consumes: context dict + symbolic   ║
║  Produces: ProblemIR                 ║
║                                      ║
║  Validates:                          ║
║  • all referenced fields exist       ║
║  • boundary regions are named        ║
║  • material params match model       ║
║  • dim consistency across entities   ║
║  • supported-subset check            ║
╚══════════════════════════════════════╝
    │
    ▼
Element IR (05-ELEMENT-IR.md) ──→ Einsum IR ──→ Backend
```

The IR is constructed **once** per compilation and is **immutable** after construction. Downstream passes read it; they never mutate it.

---

## 5  Validation at IR construction

When a `ProblemIR` is constructed, the following checks run immediately:

| Check | Error if violated |
|-------|-------------------|
| `dim` is 2 or 3 | `DimensionError` |
| `cell_type` is in supported set | `UnsupportedElementError` |
| `kinematics` is in supported set | `UnsupportedKinematicsError` |
| `constitutive` is in supported set | `UnsupportedConstitutiveError` |
| All BC regions reference declared boundary regions | `BoundaryRegionError` |
| All BC fields reference declared fields | `FieldReferenceError` |
| Material params match the model's expected param set | `MaterialParamError` |
| `dim` matches field component count (for vector fields) | `DimensionError` |

Unsupported constructs are **explicitly rejected** with actionable error messages — never silently approximated. See `00-OVERVIEW.md §8` for the supported-subset contract.

---

## 6  Serialisation and artifact capture

The IR must be serialisable for debugging and regression testing:

```python
problem_ir.to_dict()   # → nested dict, JSON-serialisable
problem_ir.to_yaml()   # → YAML dump for human inspection
ProblemIR.from_dict(d) # → reconstruct from serialised form
```

Every compilation produces an IR artifact that is stored in the compiler artifact bundle (see `01-ARCHITECTURE.md §8`). This enables:

- Golden-file regression tests (diff IR artifacts across commits)
- User inspection of what the compiler understood from the LaTeX source
- Bug isolation (was the error in parsing, IR construction, or downstream?)

---

## 7  Relationship to other specs

| Spec | Relationship |
|------|-------------|
| `01-ARCHITECTURE.md` | IR sits between Layer 2 (symbolic) and the Element IR / codegen layers |
| `05-ELEMENT-IR.md` | Element IR is constructed **from** Mechanics IR by FE localisation |
| `06-CODEGEN.md` | Code generation consumes Element IR, not Mechanics IR directly |
| `07-CONVENTIONS.md` | IR stores convention choices (Voigt ordering, sign convention) as metadata |
| `10-BOUNDARIES.md` | Boundary IR entities are the authoritative representation for BC handling |
