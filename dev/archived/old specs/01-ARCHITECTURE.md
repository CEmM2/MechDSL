# 01 — System Architecture

---

## 1  Layer diagram

```
┌──────────────────────────────────────────────────────────────┐
│                     LaTeX source file                        │
│  % mechanics dim 3                                           │
│  % mechanics material J2 --E E --nu nu --sigma_y sigma_y     │
│  % mechanics formulation total_lagrangian                    │
│  \sigma_{ij} = C_{ijkl} \varepsilon_{kl}                    │
│  ...                                                         │
└─────────────────────────┬────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────┐
│  Layer 1 — LaTeX Frontend  (NRPyLaTeX fork)                  │
│                                                              │
│  Lexer → Parser → AST                                        │
│  • Mechanics directive processor                             │
│  • Two-point tensor index resolver                           │
│  • Standard NRPyLaTeX: Einstein summation, index gymnastics  │
│                                                              │
│  Output: SymPy IR (IndexedSymbol tensors + metadata dict)    │
└─────────────────────────┬────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────┐
│  Layer 2 — Symbolic Engine                                   │
│                                                              │
│  2a. Kinematics generator                                    │
│      F, C, E, J, b, ε  from deformation gradient             │
│                                                              │
│  2b. Constitutive evaluator                                  │
│      Ψ → S = 2 ∂Ψ/∂C → ℂ = 2 ∂S/∂C   (symbolic diff)      │
│      or: algorithmic tangent for rate models                 │
│                                                              │
│  2c. Voigt contractor                                        │
│      C_ijkl → C_IJ (6×6 or 3×3)                             │
│                                                              │
│  Output: symbolic stress, tangent, strain expressions        │
└─────────────────────────┬────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────┐
│  Layer 3 — Weak Form Builder  (SymPDE)                       │
│                                                              │
│  • Domain, FunctionSpace, TestFunction definitions           │
│  • BilinearForm a(u,v), LinearForm L(v) construction         │
│  • Linearisation: δR[δu] for Newton-Raphson                  │
│  • TerminalExpr expansion to component derivatives           │
│                                                              │
│  Output: component-wise symbolic integrand expressions       │
└─────────────────────────┬────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────┐
│  Layer 3b — Einsum Optimiser  (opt_einsum + budget counter)  │
│                                                              │
│  • Extract einsum strings from TerminalExpr                  │
│  • opt_einsum: find optimal contraction path                 │
│  • Budget counter: count unrolled lines per step             │
│  • Tier classification: T1 native / T2 static / T3 runtime  │
│  • Index partition: physics (static) vs mesh (runtime)       │
│                                                              │
│  Output: ContractionPlan with per-step tier assignments      │
└─────────────────────────┬────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────┐
│  Layer 4 — Code Generation                                   │
│                                                              │
│  Printer walks TerminalExpr tree, emits target code:         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐     │
│  │  Taichi  │  │  MFEM    │  │  MOOSE   │  │  Psydac  │     │
│  │  kernel  │  │  integ.  │  │  material│  │  IGA     │     │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘     │
│                                                              │
│  Also emits: mesh I/O, BC application, solver driver         │
│                                                              │
│  Output: self-contained source files                         │
└─────────────────────────┬────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────┐
│  Layer 5 — Verification Harness                              │
│                                                              │
│  • AD oracle (PyTorch / Taichi autodiff)                     │
│  • Analytical solution library                               │
│  • Convergence rate checker                                  │
│  • Patch test / rigid body motion validators                 │
│                                                              │
│  Output: pass/fail report                                    │
└──────────────────────────────────────────────────────────────┘
```

---

## 2  Layer responsibilities

### Layer 1 — LaTeX Frontend

**Owner:** `compmech.frontend`

**Responsibility:** Parse a LaTeX source string containing both standard mathematics and `% mechanics` directives. Produce a context dictionary and SymPy symbolic objects.

**Interface:**

```python
ctx = compmech.frontend.parse(latex_string: str) -> dict
```

**Output dictionary keys:**

| Key | Type | Description |
|-----|------|-------------|
| `dim` | `int` | Spatial dimension (2 or 3) |
| `formulation` | `str` | `"plane_stress"`, `"plane_strain"`, `"3d"`, `"total_lagrangian"`, `"updated_lagrangian"` |
| `material_type` | `str` | `"isotropic_elastic"`, `"neo_hookean"`, `"j2_plasticity"`, `"damage_lemaitre"`, ... |
| `params` | `dict[str, Symbol]` | Material parameter symbols |
| `tensors` | `dict[str, IndexedSymbol]` | Named tensors from NRPyLaTeX namespace |
| `coord_material` | `list[Symbol]` | Material coordinate symbols (if TL/UL) |
| `coord_spatial` | `list[Symbol]` | Spatial coordinate symbols |
| `user_equations` | `list` | User-defined LaTeX equations parsed to SymPy |

### Layer 2 — Symbolic Engine

**Owner:** `compmech.symbolic`

**Sub-modules:**

- `compmech.symbolic.kinematics` — deformation measures from F
- `compmech.symbolic.constitutive` — strain energy → stress → tangent via `sympy.diff`
- `compmech.symbolic.voigt` — tensor ↔ Voigt ↔ Mandel conversions

**Interface:**

```python
kin = compmech.symbolic.kinematics.compute(F: Matrix, dim: int) -> KinematicsResult
stress = compmech.symbolic.constitutive.evaluate(model: str, params: dict, kin: KinematicsResult) -> StressResult
C_voigt = compmech.symbolic.voigt.tensor_to_voigt(C_ijkl, dim: int) -> Matrix
```

**`KinematicsResult` fields:** `F`, `C`, `E`, `J`, `b`, `Finv`, `FinvT`

**`StressResult` fields:** `Psi` (energy), `S` (PK2), `P` (PK1), `sigma` (Cauchy), `C_tangent` (material tangent, 4th order), `C_voigt` (Voigt tangent)

### Layer 3 — Weak Form Builder

**Owner:** `compmech.weakform`

**Responsibility:** Construct SymPDE `BilinearForm` and `LinearForm` objects from the symbolic engine output. Perform linearisation for nonlinear problems.

**Interface:**

```python
wf = compmech.weakform.build(
    ctx: dict,
    stress_result: StressResult,
    formulation: str,
) -> WeakFormResult
```

**`WeakFormResult` fields:** `bilinear_form`, `linear_form`, `terminal_expr`, `domain`, `function_space`

### Layer 3b — Einsum Optimiser

**Owner:** `compmech.codegen.einsum_optimizer`

**Responsibility:** Take tensor contractions from the weak form builder, find the optimal pairwise contraction sequence using opt_einsum, estimate the Taichi JIT unrolling cost per step, and classify each step into emission tiers.

**Interface:**

```python
plan = compmech.codegen.einsum_optimizer.plan_contraction(
    einsum_str: str,       # e.g. 'iK,KILJ,jL->iIjJ'
    shapes: list[tuple],   # tensor shapes
    dim: int,              # spatial dimension
    n_nodes: int,          # element node count
    budget: JITBudget,     # threshold configuration
) -> ContractionPlan
```

**`ContractionPlan` fields:** `steps` (list of `StepPlan`), `opt_flops`, `naive_flops`, `speedup`, `total_static_lines`, `over_budget`, `budget_message`

**`StepPlan` fields:** `einsum`, `blas_type`, `input_shapes`, `output_shape`, `tier` (1/2/3), `static_lines`, `emit_strategy`, `physics_indices`, `mesh_indices`

**Tier classification:**

| Tier | Criterion | Emission | JIT cost |
|------|-----------|----------|----------|
| 1 | Rank-2, dims ≤ 6, output ≤ 36, GEMM/DOT | `ti.Matrix @` (library func) | 0 lines |
| 2 | `static_lines ≤ func_budget` (512) | Emitted `ti.static` loop nest | ≤ 512 lines |
| 3 | `static_lines > func_budget` | Runtime loops, static innermost only | reduced |

### Layer 4 — Code Generation

**Owner:** `compmech.codegen`

**Sub-modules:**

- `compmech.codegen.taichi` — Taichi kernel printer
- `compmech.codegen.mfem` — MFEM integrator printer
- `compmech.codegen.moose` — MOOSE material class printer

**Interface:**

```python
source_code = compmech.codegen.taichi.generate(
    wf: WeakFormResult,
    ctx: dict,
    mesh_spec: dict,
) -> str
```

### Layer 5 — Verification

**Owner:** `compmech.verify`

**Interface:**

```python
report = compmech.verify.run_suite(
    generated_solver: str,
    benchmarks: list[str],
) -> VerificationReport
```

---

## 3  Data flow (linear elasticity example)

```
User writes:
  % mechanics dim 2
  % mechanics material isotropic --E E --nu nu
  % mechanics formulation plane_stress

Layer 1 emits:
  ctx = {
    'dim': 2,
    'formulation': 'plane_stress',
    'material_type': 'isotropic_elastic',
    'params': {'E': Symbol('E'), 'nu': Symbol('nu')},
    ...
  }

Layer 2 emits:
  C_voigt = E/(1-nu²) * [[1, nu, 0], [nu, 1, 0], [0, 0, (1-nu)/2]]
  (no kinematics needed — small strain)

Layer 3 emits:
  a(u,v) = ∫ ε(v) : C : ε(u) dΩ
  TerminalExpr → component derivatives dx1(u[0]), dx2(u[1]), ...

Layer 4 emits:
  complete taichi_solver.py with:
    - B-matrix computation kernel
    - element stiffness kernel
    - matrix-free CG solver
    - BC application
    - post-processing

Layer 5 runs:
  - patch test (constant strain) → PASS
  - cantilever convergence study → rate ≈ 1.0 (CST) or 2.0 (Q4)
  - comparison vs Euler-Bernoulli → within expected tolerance
```

---

## 4  Data flow (nonlinear: neo-Hookean, total Lagrangian)

```
User writes:
  % mechanics dim 3
  % mechanics material neo_hookean --mu mu --kappa kappa
  % mechanics formulation total_lagrangian

Layer 1 emits:
  ctx with coord_material = [X1, X2, X3], coord_spatial = [x1, x2, x3]

Layer 2 emits:
  F_iI = ∂x_i/∂X_I = δ_iI + ∂u_i/∂X_I
  C_IJ = F_kI F_kJ
  J = det(F)
  Ψ = (μ/2)(tr(C) - 3) - μ ln(J) + (κ/2)(ln J)²
  S_IJ = 2 ∂Ψ/∂C_IJ   (symbolic differentiation)
  ℂ_IJKL = 2 ∂S_IJ/∂C_KL

Layer 3 emits:
  Residual: R_i = ∫ P_iJ ∂δu_i/∂X_J dΩ₀ - ∫ b_i δu_i dΩ₀
  Tangent:  K_ij = ∫ ∂δu_i/∂X_I ℂ_IJKL ∂Δu_j/∂X_L dΩ₀ + geometric stiffness

Layer 4 emits:
  Newton-Raphson driver:
    while ||R|| > tol:
      K δu = -R
      u += δu
      recompute F, S, P, R, K
```

---

## 5  Package structure

```
compmech/
├── __init__.py
├── frontend/
│   ├── __init__.py
│   ├── parser.py          # NRPyLaTeX fork entry point
│   ├── directives.py      # % mechanics directive handler
│   └── two_point.py       # dual-index tensor support
├── symbolic/
│   ├── __init__.py
│   ├── kinematics.py      # F → C, E, J, b
│   ├── constitutive.py    # Ψ → S → ℂ
│   ├── voigt.py           # tensor ↔ Voigt ↔ Mandel
│   └── models/
│       ├── __init__.py
│       ├── linear_elastic.py
│       ├── neo_hookean.py
│       ├── mooney_rivlin.py
│       ├── j2_plasticity.py
│       └── lemaitre_damage.py
├── weakform/
│   ├── __init__.py
│   ├── builder.py         # SymPDE form construction
│   ├── linearise.py       # Gâteaux derivative for Newton
│   └── adapters.py        # NRPyLaTeX IR → SymPDE operators
├── codegen/
│   ├── __init__.py
│   ├── einsum_optimizer.py  # opt_einsum + JIT budget counter
│   ├── taichi_printer.py
│   ├── mfem_printer.py
│   ├── moose_printer.py
│   └── common.py          # shared codegen utilities
├── solver/
│   ├── __init__.py
│   ├── import_adapter.py   # adapter for user's existing Taichi linear solvers
│   └── newton.py           # Newton-Raphson driver (calls imported solver)
├── verify/
│   ├── __init__.py
│   ├── analytical.py      # analytical solution library
│   ├── ad_oracle.py       # AD-based verification
│   ├── patch_test.py
│   └── convergence.py
└── tests/
    ├── test_frontend.py
    ├── test_symbolic.py
    ├── test_weakform.py
    ├── test_codegen.py
    └── test_e2e.py
```

---

## 6  Error handling strategy

Errors are classified by layer and severity:

| Layer | Error class | Example | Action |
|-------|-------------|---------|--------|
| 1 | `ParseError` | Unknown directive `% mechanics foo` | Raise with line number and suggestion |
| 1 | `IndexError` | Two-point tensor with ambiguous index manifold | Raise with index annotation guidance |
| 2 | `ConstitutiveError` | Unsupported material model | Raise with list of supported models |
| 2 | `DimensionError` | 2D formulation with 3D tensor | Raise with dimension mismatch details |
| 3 | `FormError` | Non-symmetric bilinear form where symmetry expected | Warn (may be intentional for non-self-adjoint) |
| 4 | `CodegenError` | Target backend cannot express required operation | Raise with fallback suggestion |
| 5 | `VerificationError` | Convergence rate below expected | Report with actual vs expected rate |

All errors include the LaTeX source line that triggered them when possible.

---

## 7  Threading and parallelism model

- Layers 1–3 are **single-threaded, symbolic**. They run once at "compile time" and produce source code. Performance is not critical (seconds, not microseconds).
- Layer 4 output is **GPU-parallel** (Taichi) or **MPI-parallel** (MFEM/MOOSE). The generated code is the performance-critical path.
- Layer 5 verification runs are **embarrassingly parallel** across test cases.

The DSL is a *compiler*, not a *runtime*. Symbolic overhead is acceptable; generated code performance is paramount.
