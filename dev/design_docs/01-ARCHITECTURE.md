# 01 — System Architecture

---

## 1  Layer diagram

```
┌──────────────────────────────────────────────────────────────┐
│                     LaTeX source file                        │
│  % mechanics dim 3                                           │
│  % mechanics cell hex8                                       │
│  % mechanics material hooke_power_law --E E --nu nu ...      │
│  % mechanics formulation total_lagrangian                    │
│  F_{iI} = \delta_{iI} + u_{i,I}                             │
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
│  Output: SymPy IR (IndexedSymbol tensors + context dict)     │
└─────────────────────────┬────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────┐
│  Layer 2 — Symbolic Engine                                   │
│                                                              │
│  2a. Kinematics generator                                    │
│      F, C, E, J, g_IJ (convected metric) from deformation   │
│                                                              │
│  2b. Constitutive evaluator                                  │
│      SVK: S = C:E  /  J2: return mapping + C_alg             │
│      Symbolic diff for tangent derivation                    │
│                                                              │
│  2c. Voigt contractor                                        │
│      C_ijkl → C_IJ (6×6)                                    │
│                                                              │
│  Output: symbolic stress, tangent, strain expressions        │
└─────────────────────────┬────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────┐
│  Layer 3 — Mechanics IR  (semantic center)                   │
│                                                              │
│  • ProblemIR: fields, material, BCs, residual, domain        │
│  • Supported-subset validation and rejection                 │
│  • Serialisation for artifact capture                        │
│  • See 04-MECHANICS-IR.md                                    │
│                                                              │
│  Output: validated, immutable ProblemIR                      │
└─────────────────────────┬────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────┐
│  Layer 4 — Element IR  (FE localisation)                     │
│                                                              │
│  • Cell type, basis functions, quadrature rule               │
│  • Geometry mapping (reference Jacobian for TL)              │
│  • Material evaluation contract                              │
│  • Local force / tangent expressions with einsum strings     │
│  • Convected coordinate data                                 │
│  • See 05-ELEMENT-IR.md                                      │
│                                                              │
│  Output: ElementIR with einsum strings                       │
└─────────────────────────┬────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────┐
│  Layer 4b — Einsum Optimiser  (opt_einsum + budget counter)  │
│                                                              │
│  • Extract einsum strings from ElementIR                     │
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
│  Layer 5 — Taichi Code Generation                            │
│                                                              │
│  TaichiPrinter consumes ElementIR + ContractionPlans:        │
│  ┌──────────────────────────────────────────────────┐        │
│  │  Taichi backend (sole target until v1.0)         │        │
│  │  Kernels, driver, BCs, mesh I/O, postprocessing  │        │
│  └──────────────────────────────────────────────────┘        │
│                                                              │
│  Output: self-contained .py file + artifact bundle           │
└─────────────────────────┬────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────┐
│  Layer 6 — Verification Harness                              │
│                                                              │
│  • Handwritten reference comparison                          │
│  • AD oracle (PyTorch / Taichi autodiff)                     │
│  • Analytical solution library                               │
│  • Convergence rate checker                                  │
│  • Patch test / rigid body motion validators                 │
│  • See 08-VERIFICATION.md                                    │
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
| `kinematics` | `str` | `"total_lagrangian"`, `"updated_lagrangian"`, `"small_strain"` |
| `formulation` | `str` | `"convected"`, `"cartesian"` |
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

### Layer 3 — Mechanics IR

**Owner:** `compmech.ir.mechanics_ir`

**Responsibility:** Construct and validate the `ProblemIR` — the semantic center of the compiler. Consumes the parser context dict and symbolic engine output. Runs supported-subset validation and rejects unsupported constructs.

**Interface:**

```python
problem_ir = compmech.ir.mechanics_ir.build(
    ctx: dict,
    stress_result: StressResult,
    kinematics_result: KinematicsResult,
) -> ProblemIR
```

See `04-MECHANICS-IR.md` for the full schema.

### Layer 4 — Element IR (FE Localisation)

**Owner:** `compmech.lowering.fe_localise`

**Responsibility:** Lower `ProblemIR` to `ElementIR` by selecting element type, instantiating basis functions and quadrature, mapping constitutive evaluation to quadrature-point operations, and extracting einsum strings for the optimiser.

**Interface:**

```python
element_ir = compmech.lowering.fe_localise.localise(
    problem: ProblemIR,
) -> ElementIR
```

See `05-ELEMENT-IR.md` for the full schema.

### Layer 4b — Einsum Optimiser

**Owner:** `compmech.codegen.einsum_optimizer`

**Responsibility:** Take einsum strings from Element IR, find the optimal pairwise contraction sequence using opt_einsum, estimate the Taichi JIT unrolling cost per step, and classify each step into emission tiers.

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

### Layer 5 — Taichi Code Generation

**Owner:** `compmech.codegen.taichi_printer`

**Responsibility:** Consume ElementIR and ContractionPlans, emit a self-contained Taichi `.py` file. Sole backend until v1.0.

**Interface:**

```python
source_code = compmech.codegen.taichi_printer.TaichiPrinter().generate(
    element_ir: ElementIR,
    problem_ir: ProblemIR,
) -> str
```

See `06-CODEGEN.md` for Taichi-specific emission details.

### Layer 6 — Verification

**Owner:** `compmech.verify`

**Interface:**

```python
report = compmech.verify.run_suite(
    generated_solver: str,
    reference_solver: str,
    benchmarks: list[str],
) -> VerificationReport
```

See `08-VERIFICATION.md` for the full test strategy.

---

## 3  Data flow (MVP: SVK elastic, TL with convected coordinates)

```
User writes:
  % mechanics dim 3
  % mechanics cell hex8
  % mechanics material hooke_power_law --E E --nu nu --sigma_y0 sigma_y0 --K K --n n
  % mechanics formulation total_lagrangian

Layer 1 (Parser) emits:
  ctx = {
    'dim': 3,
    'cell_type': 'hex8',
    'formulation': 'total_lagrangian',
    'material_type': 'hooke_power_law',
    'params': {'E': Symbol('E'), 'nu': Symbol('nu'), ...},
    'coord_material': [X1, X2, X3],
    'coord_spatial': [x1, x2, x3],
    ...
  }

Layer 2 (Symbolic Engine) emits:
  F_iI = δ_iI + ∂u_i/∂X_I
  C_IJ = F_kI F_kJ         (convected metric g_IJ = C_IJ)
  E_IJ = (C_IJ - δ_IJ)/2   (Green-Lagrange strain)
  J = det(F)
  S_IJ = λ tr(E) δ_IJ + 2μ E_IJ   (SVK stress)
  ℂ_IJKL = λ δ_IJ δ_KL + μ (δ_IK δ_JL + δ_IL δ_JK)
  J2 return mapping: S_IJ, C_alg (algorithmic tangent)

Layer 3 (Mechanics IR) produces:
  ProblemIR with dim=3, cell_type='hex8', material='hooke_power_law',
  fields, BCs, residual form, convected metric data
  → supported-subset validated, serialised to artifact bundle

Layer 4 (Element IR) produces:
  ElementIR with hex8 basis, 2×2×2 Gauss quadrature,
  reference Jacobian, material eval contract,
  local force einsum: 'iI,aI->ai' (PK1 · dN scatter)
  local tangent einsum: 'iK,KILJ,jL->iIjJ' (push-forward)

Layer 4b (Einsum Optimiser) produces:
  ContractionPlan: push-forward = 486 static lines (Tier 2),
  scatter = 81 lines (Tier 2), total 567 lines ✓

Layer 5 (Taichi Code Gen) emits:
  complete taichi_solver.py with:
    - constitutive_update @ti.func (SVK + J2 return mapping)
    - compute_internal_forces @ti.kernel
    - tangent_matvec @ti.kernel (matrix-free)
    - BC application (Dirichlet mask + Neumann traction)
    - Newton-Raphson driver with imported linear solver
    - mesh I/O, VTK export

Layer 6 (Verification) runs:
  - generated vs handwritten reference: max displacement diff < 1e-10
  - patch test (constant strain) → PASS
  - Cook's membrane → within 2% of literature
  - necking bar → load-disp curve within 2% of Simo & Hughes
```

---

## 5  Package structure (monorepo)

```
MechDSL/                              # monorepo root (uv workspace)
├── pyproject.toml                    # workspace definition
├── packages/
│   ├── mechdsl-core/                 # tensor expressions, constitutive laws, element kernels
│   │   ├── pyproject.toml
│   │   ├── src/
│   │   │   └── mechdsl/
│   │   │       ├── __init__.py
│   │   │       ├── frontend/
│   │   │       │   ├── __init__.py
│   │   │       │   ├── parser.py          # NRPyLaTeX fork entry point
│   │   │       │   ├── directives.py      # % mechanics directive handler
│   │   │       │   └── two_point.py       # dual-index tensor support
│   │   │       ├── symbolic/
│   │   │       │   ├── __init__.py
│   │   │       │   ├── kinematics.py      # F → C, E, J, g_IJ (convected metric)
│   │   │       │   ├── constitutive.py    # S, C_alg from constitutive model
│   │   │       │   ├── voigt.py           # tensor ↔ Voigt ↔ Mandel
│   │   │       │   ├── convected.py       # convected coordinate operations
│   │   │       │   └── models/
│   │   │       │       ├── __init__.py
│   │   │       │       ├── svk.py              # St. Venant-Kirchhoff (MVP)
│   │   │       │       ├── j2_power_law.py     # J2 + power-law hardening (MVP)
│   │   │       │       ├── neo_hookean.py      # Plan B
│   │   │       │       ├── mooney_rivlin.py    # Plan B
│   │   │       │       └── lemaitre_damage.py  # Plan B
│   │   │       ├── ir/
│   │   │       │   ├── __init__.py
│   │   │       │   ├── mechanics_ir.py    # ProblemIR construction and validation
│   │   │       │   └── element_ir.py      # ElementIR schema
│   │   │       ├── lowering/
│   │   │       │   ├── __init__.py
│   │   │       │   ├── fe_localise.py     # ProblemIR → ElementIR
│   │   │       │   └── einsum_extract.py  # extract einsum strings from Element IR
│   │   │       ├── codegen/
│   │   │       │   ├── __init__.py
│   │   │       │   ├── einsum_optimizer.py  # opt_einsum + JIT budget counter
│   │   │       │   ├── taichi_printer.py    # Taichi backend (sole target until v1.0)
│   │   │       │   ├── artifact.py          # artifact bundle management
│   │   │       │   └── common.py            # shared codegen utilities (CSE, safeguards)
│   │   │       ├── solver/
│   │   │       │   ├── __init__.py
│   │   │       │   ├── import_adapter.py   # adapter for imported linear solvers
│   │   │       │   └── newton.py           # Newton-Raphson driver
│   │   │       ├── lib/
│   │   │       │   ├── __init__.py
│   │   │       │   └── tensor_ops.py      # Tier 1 @ti.func library
│   │   │       └── verify/
│   │   │           ├── __init__.py
│   │   │           ├── analytical.py      # analytical solution library
│   │   │           ├── ad_oracle.py       # AD-based verification
│   │   │           ├── patch_test.py
│   │   │           └── convergence.py
│   │   └── tests/
│   │       ├── golden/             # artifact golden files for regression
│   │       ├── ref/                # handwritten reference kernels
│   │       │   ├── ref_hex8_elastic.py
│   │       │   └── ref_hex8_plastic.py
│   │       ├── test_frontend.py
│   │       ├── test_symbolic.py
│   │       ├── test_mechanics_ir.py
│   │       ├── test_element_ir.py
│   │       ├── test_einsum.py
│   │       ├── test_codegen.py
│   │       ├── test_boundaries.py
│   │       ├── test_artifacts.py
│   │       └── test_e2e.py
│   └── algo2code/                    # algorithm boxes → solver code (see 11-ALGO2CODE.md)
│       ├── pyproject.toml
│       ├── src/
│       │   └── algo2code/
│       │       ├── algo_parser.py
│       │       ├── expr_parser.py
│       │       ├── type_inference.py
│       │       └── backends/
│       │           └── taichi_codegen.py
│       └── tests/
├── dev/
│   └── design_docs/
└── .github/
```

Import paths remain `mechdsl.*` (e.g. `mechdsl.frontend`, `mechdsl.codegen.taichi_printer`) and `algo2code.*`. The monorepo is managed as a `uv` workspace.

---

## 6  Error handling strategy

Errors are classified by layer and severity:

| Layer | Error class | Example | Action |
|-------|-------------|---------|--------|
| 1 | `ParseError` | Unknown directive `% mechanics foo` | Raise with line number and suggestion |
| 1 | `IndexError` | Two-point tensor with ambiguous index manifold | Raise with index annotation guidance |
| 2 | `ConstitutiveError` | Unsupported material model | Raise with list of supported models |
| 2 | `DimensionError` | 2D formulation with 3D tensor | Raise with dimension mismatch details |
| 3 | `UnsupportedError` | Construct outside supported subset | Raise with plan phase that adds support |
| 3 | `BoundaryRegionError` | BC references undeclared region | Raise listing declared regions |
| 4 | `LocalisationError` | Element type incompatible with problem dimension | Raise with compatible elements |
| 5 | `CodegenError` | Budget exceeded, cannot restructure | Raise with budget usage details |
| 6 | `VerificationError` | Convergence rate below expected | Report with actual vs expected rate |

All errors include the LaTeX source line that triggered them when possible.

---

## 7  Threading and parallelism model

- Layers 1–4b are **single-threaded, symbolic**. They run once at "compile time" and produce source code. Performance is not critical (seconds, not microseconds).
- Layer 5 output is **GPU-parallel** (Taichi). The generated code is the performance-critical path.
- Layer 6 verification runs are **embarrassingly parallel** across test cases.

The DSL is a *compiler*, not a *runtime*. Symbolic overhead is acceptable; generated code performance is paramount.

---

## 8  Compiler artifact bundle

Every compilation produces an **inspectable artifact bundle** — a structured collection of intermediate outputs from each pipeline stage. Artifacts exist to support debugging, regression testing, performance tuning, user inspection, and golden-file comparison.

### 8.1  Bundle contents

| Stage | Artifact | Format |
|-------|----------|--------|
| Layer 1 (Parser) | Parsed context dictionary | JSON |
| Layer 2 (Symbolic) | Normalised symbolic expressions (stress, tangent, kinematics) | SymPy srepr / JSON |
| Mechanics IR | Full `ProblemIR` dump | YAML / JSON |
| Element IR | `ElementIR` dump (cell, basis, quad, expressions) | YAML / JSON |
| Einsum IR | Contraction plans (steps, tiers, line counts, speedups) | JSON |
| Scheduling | Tier assignments, unrolling decisions, budget usage | JSON |
| Code emission | Generated Taichi source file(s) | `.py` |
| Validation | Metadata: budget pass/fail, supported-subset check | JSON |

### 8.2  Artifact API

```python
compiler = MechCompiler(config=...)
artifact = compiler.compile(source_text)

# Inspect intermediate representations
artifact.mechanics_ir       # → ProblemIR
artifact.element_ir         # → ElementIR
artifact.contraction_plans  # → dict[str, ContractionPlan]
artifact.scheduling         # → dict of tier/budget decisions
artifact.generated_source   # → str (Taichi code)

# Bind runtime data and solve
sim = artifact.bind_mesh(mesh).bind_bcs(bc_map).bind_materials(params)
result = sim.solve()
```

### 8.3  Golden-file regression

Artifact bundles are serialised and stored in `tests/golden/`. On every CI run:

1. Compile each test case.
2. Compare the artifact bundle against the stored golden file.
3. If the bundle differs, the diff is displayed in the test output.
4. Golden-file updates require explicit approval in the PR.

This catches unintended changes in any compiler stage — not just the final generated code.

---

## 9  Runtime responsibilities

The runtime layer is responsible for:

- Mesh ingestion and validation
- Boundary-condition binding (named regions → mesh tags)
- Material parameter binding
- Calling generated Taichi kernels
- Interfacing with the imported linear solver
- Exposing result fields (displacement, stress, state variables)
- Exposing diagnostic data (Newton residual history, solver iteration counts)
