# 05 — Element IR

---

## 1  Purpose

Element IR is the **finite element execution model** — the bridge between the abstract variational forms in Mechanics IR and the concrete code emitted by the backend. It makes explicit everything that a generated element kernel needs: basis functions, quadrature, geometry mapping, material evaluation, and local assembly expressions.

The rule is: **code generation reads Element IR, not Mechanics IR or SymPDE trees.** This decoupling means the same Mechanics IR can target different element types, quadrature rules, or integration strategies without changing the symbolic layer.

---

## 2  Core schema

```python
@dataclass
class ElementIR:
    """Complete finite element execution specification for one cell type."""

    # ─── Cell topology ───
    cell_type: str            # "hex8"
    dim: int                  # 3
    n_nodes: int              # 8
    n_dof_per_node: int       # 3 (vector field in 3D)

    # ─── Quadrature ───
    quad_rule: QuadRuleIR

    # ─── Basis ───
    basis: BasisIR

    # ─── Geometry mapping ───
    geometry: GeometryIR

    # ─── Material evaluation ───
    material: MaterialEvalIR

    # ─── Local assembly expressions ───
    local_force: LocalForceIR       # internal force vector
    local_tangent: LocalTangentIR   # tangent stiffness (for Newton)

    # ─── Convected coordinate data (if applicable) ───
    convected: ConvectedIR | None

@dataclass
class QuadRuleIR:
    """Quadrature specification."""
    n_points: int                    # 8 for 2×2×2 Gauss
    points: list[tuple[float, ...]]  # parametric coordinates
    weights: list[float]
    integration: str                 # "full" | "reduced"

@dataclass
class BasisIR:
    """Shape function specification."""
    family: str                      # "lagrange"
    order: int                       # 1 for hex8
    shape_functions: list[Expr]      # N_a(xi, eta, zeta) symbolic
    shape_gradients: list[list[Expr]]  # dN_a/d(xi_j) symbolic
    is_isoparametric: bool           # True for hex8

@dataclass
class GeometryIR:
    """Reference-to-physical geometry mapping."""
    jacobian: Expr                   # J_iI = sum_a dN_a/d(xi_I) * X_ai
    det_jacobian: Expr               # det(J)
    inv_jacobian: Expr               # J^{-1}
    physical_gradients: Expr         # dN_a/dX_I = dN_a/d(xi_j) * J^{-1}_{jI}
    configuration: str               # "reference" (TL) or "current" (UL)

@dataclass
class MaterialEvalIR:
    """Material evaluation contract at a single quadrature point."""
    model: str                       # "hooke_power_law"
    input_measures: list[str]        # ["F", "C", "E", "J"] for TL
    output_stress: str               # "S" (PK2 for TL) or "sigma" (Cauchy for UL)
    output_tangent: str              # "C_IJKL" (material tangent)
    has_state_update: bool           # True for plasticity
    state_inputs: list[str]          # ["peeq_old", "stress_old"]
    state_outputs: list[str]         # ["peeq_new", "stress_new"]
    update_signature: str            # function signature for generated code

@dataclass
class LocalForceIR:
    """Internal force contribution at one quadrature point."""
    expression: Expr                 # e.g. P_iI * dN_a/dX_I * det_J * w_q
    scatter_pattern: str             # "atomic_add" or "local_accumulate"
    einsum_str: str                  # contraction string for einsum optimiser

@dataclass
class LocalTangentIR:
    """Tangent stiffness contribution at one quadrature point."""
    material_tangent: Expr           # C_IJKL or c_ijkl
    geometric_stiffness: Expr        # sigma_IJ * delta_ij term
    einsum_str: str                  # contraction string
    is_matrix_free: bool             # True → emit matvec, False → emit matrix

@dataclass
class ConvectedIR:
    """Convected coordinate data for TL with convected framework."""
    reference_metric: Expr           # G_IJ
    current_metric: Expr             # g_IJ = C_IJ
    has_christoffel: bool            # False for MVP (Cartesian reference)
    christoffel_symbols: Expr | None # Gamma^K_IJ (None for MVP)
```

---

## 3  Element IR construction

Element IR is built from Mechanics IR by **FE localisation** — the process of mapping global variational forms to element-level operations:

```
Mechanics IR (ProblemIR)
    │
    ▼
FE Localisation:
    1. Select element type and quadrature from ProblemIR.cell_type
    2. Instantiate basis functions and gradients
    3. Build geometry mapping (reference Jacobian for TL)
    4. Map constitutive model to quadrature-point evaluation
    5. Express residual integrand in element-local terms
    6. Express tangent integrand in element-local terms
    7. Extract einsum strings for the optimiser
    │
    ▼
ElementIR (immutable)
```

**Owner:** `compmech.lowering.fe_localise`

```python
def localise(problem: ProblemIR) -> ElementIR:
    """Lower a Mechanics IR problem to an Element IR execution model."""
    ...
```

---

## 4  Supported elements

### MVP

| Cell | Nodes | Quad points | Quad rule | Budget (static lines) |
|------|-------|------------|-----------|----------------------|
| Hex8 | 8 | 8 (2×2×2) | Full Gauss | 123 (physics) + 81 (scatter) = 204 |

### Plan B extensions

| Cell | Nodes | Quad points | Notes |
|------|-------|------------|-------|
| Tet4 | 4 | 1 | Constant strain, simplest 3D |
| Tet10 | 10 | 4 | Quadratic, same physics budget as Hex8 |
| Hex20 | 20 | 27 (3×3×3) | Serendipity quadratic |
| Hex8-R | 8 | 1 | Reduced integration, requires hourglass control |

All elements share the same physics-index budget (123 static lines for 3D). The difference is in runtime loop counts (nodes × quad points), which do not affect JIT compilation.

---

## 5  Data flow: Element IR → Einsum IR → Backend

```
ElementIR
    │
    ├── LocalForceIR.einsum_str ──→ plan_contraction() ──→ ContractionPlan
    │                                                          │
    ├── LocalTangentIR.einsum_str ──→ plan_contraction() ──→ ContractionPlan
    │                                                          │
    ▼                                                          ▼
Einsum IR (normalised contraction layer)            Backend scheduling
    │                                                          │
    ▼                                                          ▼
opt_einsum optimisation                             Tier classification
    │                                                          │
    └──────────────────────┬───────────────────────────────────┘
                           ▼
                    Taichi code emission
```

The Einsum IR is not a separate data structure — it is the set of `einsum_str` fields embedded in Element IR plus the `ContractionPlan` objects returned by the optimiser. This keeps the IR lean while still providing the normalised contraction layer described in the alternatives spec.

---

## 6  Serialisation and artifact capture

Like Mechanics IR, Element IR is serialisable:

```python
element_ir.to_dict()   # → JSON-serialisable nested dict
```

The artifact bundle stores:

- Element IR dump (cell type, basis, quadrature, expressions)
- Einsum strings extracted from local force and tangent
- ContractionPlan for each einsum (steps, tiers, line counts)
- Scheduling decisions (which tier for each step)

This enables golden-file regression: if a code change alters the Element IR or the contraction plan, the diff is visible in the artifact.

---

## 7  Relationship to other specs

| Spec | Relationship |
|------|-------------|
| `04-MECHANICS-IR.md` | Element IR is constructed from Mechanics IR |
| `06-CODEGEN.md` | Backend printers consume Element IR |
| `07-CONVENTIONS.md` | Index conventions and Voigt ordering are embedded in Element IR expressions |
| `09-EINSUM-OPTIMISER.md` | Einsum strings from Element IR are the input to the optimiser |
| `10-BOUNDARIES.md` | BC enforcement is a separate concern; Element IR handles volume integrals only |
