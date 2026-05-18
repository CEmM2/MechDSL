# Implementation Plan A — Setup → MVP

**Goal:** A working 3D finite element code that solves large-deformation elasto-plastic boundary-value problems using Total Lagrangian Hex8 elements with convected coordinates, driven by LaTeX input.

**Constitutive model:**
- Elastic: St. Venant-Kirchhoff (Hooke in reference config): $S_{IJ} = \mathbb{C}_{IJKL}\,E_{KL}$
- Plastic: J2 with power-law isotropic hardening: $\sigma_y(\bar{\varepsilon}_p) = \sigma_{y0} + K\,\bar{\varepsilon}_p^{\,n}$

**MVP acceptance test:** Solve a necking bar problem (3D Hex8 mesh, power-law elasto-plasticity, convected coordinates TL, Newton-Raphson with imported linear solver) and reproduce the load-displacement curve from Simo & Hughes (1998) within 2% of the reference.

**Linear solver strategy:** Initially, the user's existing Taichi CG/PCG library is imported via `LinearSolverInterface` (A1.3). Once `algo2code` is ready, it transpiles `solvers/pcg.tex` → `_pcg_taichi.py` and replaces the external dependency behind the same interface. See `11-ALGO2CODE.md`.

---

## Phase A1 — Repository scaffolding

**Duration:** 3–4 days

### A1.1  Create repo and package structure

Set up the monorepo as a `uv` workspace with two packages:

```
MechDSL/
├── pyproject.toml              # uv workspace definition
├── packages/
│   ├── mechdsl-core/
│   │   ├── pyproject.toml
│   │   ├── src/
│   │   │   └── mechdsl/
│   │   │       ├── __init__.py
│   │   │       ├── frontend/
│   │   │       ├── symbolic/
│   │   │       ├── ir/               # Mechanics IR + Element IR
│   │   │       ├── lowering/         # FE localisation (IR → Element IR)
│   │   │       ├── codegen/
│   │   │       ├── solver/
│   │   │       ├── verify/
│   │   │       └── lib/              # pre-written Taichi ti.func library
│   │   └── tests/
│   │       ├── golden/               # artifact golden files
│   │       ├── ref/                  # handwritten reference kernels
│   │       └── ...
│   └── algo2code/                    # algorithm boxes → solver code (see 11-ALGO2CODE.md)
│       ├── pyproject.toml
│       ├── src/algo2code/
│       └── tests/
├── dev/design_docs/
└── .github/
```

See `01-ARCHITECTURE.md §5` for the full package tree.

Dependencies in `pyproject.toml`: `sympy>=1.12`, `sympde>=0.19`, `nrpylatex>=1.4` (git fork), `opt-einsum>=3.3`, `taichi>=1.7`, `numpy>=1.24`.

Dev dependencies: `pytest`, `ruff`, `mypy`.

### A1.2  CI pipeline

GitHub Actions workflow:
- Lint (ruff)
- Type check (mypy, selective)
- Unit tests (pytest, CPU-only Taichi)
- Budget counter regression (verify all contractions pass JIT budget)

### A1.3  Import existing Taichi linear solver

Create `compmech.solver.import_adapter`:
- Define the abstract interface the generated Newton driver expects:

```python
class LinearSolverInterface:
    def solve(self, matvec_fn, rhs, x0, tol, max_iter) -> tuple[field, int, float]:
        """Solve A x = b where A is given as a matvec function."""
        ...
```

- Write a concrete adapter wrapping the user's existing CG/PCG implementation.
- Verify: solve a known SPD system, check residual < tol.

### A1.4  Taichi library functions (Tier 1 functions)

Create `compmech.lib.tensor_ops`:

```python
@ti.func
def mat_mul_33(A, B): return A @ B

@ti.func
def mat_mul_T_33(A, B): return A.transpose() @ B

@ti.func
def pk1_from_pk2(F, S): return F @ S

@ti.func
def cauchy_from_pk1(P, F, J): return (1.0 / J) * (P @ F.transpose())

@ti.func
def right_cauchy_green(F): return F.transpose() @ F

@ti.func
def det_33(F): return F.determinant()

@ti.func
def inv_33(F): return F.inverse()
```

Test: round-trip F → C → F^T F, det(I) = 1, inv(F) @ F = I.

**Exit criterion A1:** `uv run pytest` passes, CI green, solver import works on a test system.

---

## Phase A2 — Handwritten Taichi reference kernels

**Duration:** 1 week

### A2.1  Purpose

Before the compiler generates any element kernels, we write them **by hand** in Taichi and verify correctness. This creates:

- A trusted numerical baseline for comparing generated code
- A smoke test for the imported linear solver integration
- Confidence that the physics is correct independently of the compiler

### A2.2  Handwritten elastic reference (`ref_hex8_elastic.py`)

A complete Taichi solver for 3D TL Hex8 with St. Venant-Kirchhoff elasticity:

- Hex8 shape functions and 2×2×2 Gauss quadrature
- Deformation gradient computation from displacements
- SVK stress: $S_{IJ} = \lambda\,\mathrm{tr}(E)\,\delta_{IJ} + 2\mu\,E_{IJ}$
- Internal force assembly with atomic scatter
- Newton-Raphson with imported linear solver
- Dirichlet/Neumann BC application

Verify on:
- **Patch test:** constant strain field on irregular Hex8 mesh → exact stress (error < 1e-12)
- **Rigid body motion:** rotation + translation → zero internal force
- **Cantilever:** compare tip displacement against Euler-Bernoulli

### A2.3  Handwritten plastic reference (`ref_hex8_plastic.py`)

Extend the elastic reference with:
- J2 return mapping in corotational frame
- Power-law hardening: $\sigma_y = \sigma_{y0} + K\,\bar{\varepsilon}_p^{\,n}$
- Algorithmic tangent (consistent elasto-plastic)
- History variable management (peeq, stress_old)
- Load stepping

Verify on:
- **Uniaxial tension past yield:** check $\sigma = \sigma_y + H\varepsilon_p$
- **Elastic loading (below yield):** matches elastic reference exactly
- **Return mapping:** $f(\sigma^{n+1}) = 0$ to machine precision

### A2.4  Freeze as golden baselines

Store reference outputs (displacement fields, load-disp curves) as golden files in `tests/golden/`. These are the **ground truth** against which generated code is compared in phase A10.

**Exit criterion A2:** Both reference solvers pass all verification tests. Golden files stored.

---

## Phase A3 — NRPyLaTeX fork and `% mechanics` parser

**Duration:** 1–2 weeks

### A3.1  Fork NRPyLaTeX

- Fork `zachetienne/nrpylatex` into project org
- Add as `uv` git dependency: `nrpylatex = { git = "...", branch = "compmech" }`
- Verify all existing NRPyLaTeX tests pass

### A3.2  Add `% mechanics` directive infrastructure

In `scanner.py`, add tokens:

```python
('MECHANICS_KWD', r'mechanics'),
```

In `parser.py`, extend `_config()`:

```python
elif self.accept('MECHANICS_KWD'):
    self._mechanics_directive()
```

### A3.3  Implement core directives

| Directive | Handler | Output |
|-----------|---------|--------|
| `% mechanics dim 3` | `_mech_dim` | Sets `ctx['dim']` |
| `% mechanics coord spatial x y z` | `_mech_coord` | Sets coordinate symbols |
| `% mechanics coord material X Y Z` | `_mech_coord` | Sets material coordinates |
| `% mechanics coord convected theta1 theta2 theta3` | `_mech_coord` | Sets convected coordinates |
| `% mechanics material hooke_power_law --E E --nu nu --sigma_y0 sigma_y0 --K K --n n` | `_mech_material` | Populates material params |
| `% mechanics formulation total_lagrangian` | `_mech_formulation` | Sets formulation |
| `% mechanics cell hex8` | `_mech_cell` | Sets element type |
| `% mechanics boundary Gamma_u --type dirichlet --field u --value 0` | `_mech_boundary` | Adds BC |
| `% mechanics boundary Gamma_t --type neumann --traction t_bar` | `_mech_boundary` | Adds traction |

### A3.4  Two-point tensor index support

Add `manifold` attribute to `IndexedSymbol`:
- `% mechanics index spatial i j k l` → spatial indices
- `% mechanics index material I J K L` → material indices
- Parser validates: contracted indices share the same manifold (or go through a two-point tensor)

### A3.5  Integration test

Parse the MVP example and verify the output context dictionary:

```latex
% mechanics dim 3
% mechanics cell hex8
% mechanics coord spatial x y z
% mechanics coord material X Y Z
% mechanics material hooke_power_law --E E --nu nu --sigma_y0 sigma_y0 --K K --n n
% mechanics formulation total_lagrangian
% mechanics boundary Gamma_u --type dirichlet --field u --components 0 1 2 --value 0
% mechanics boundary Gamma_t --type neumann --traction "t_bar"
```

**Exit criterion A3:** `compmech.frontend.parse(latex_str)` returns correct context dict. All NRPyLaTeX upstream tests still pass.

---

## Phase A4 — Symbolic engine: kinematics and constitutive

**Duration:** 1–2 weeks

### A4.1  Kinematics module

Implement `compmech.symbolic.kinematics`:

```python
def compute(dim: int, u_symbols, X_symbols) -> KinematicsResult:
    # Build F = I + grad(u) symbolically
    # Compute C = F^T F, J = det(F), E = (C-I)/2
    # Compute Finv, FinvT
    # Compute convected metric g_IJ = C_IJ
    ...
```

**Convected coordinate deliverable:** Compute convected metric $g_{IJ} = C_{IJ}$ (for Cartesian reference configuration) as part of `KinematicsResult`. Test S9 from `08-VERIFICATION.md` applies here.

Test: at F = I, verify C = I, J = 1, E = 0, g = G = I.
Test: at known simple shear F, verify C, E against hand calculation.

### A4.2  St. Venant-Kirchhoff constitutive model

Implement `compmech.symbolic.models.svk`:

```python
class StVenantKirchhoff(ConstitutiveModel):
    def pk2_stress(self, kin):
        lam, mu = self.params['lambda'], self.params['mu']
        E = kin.E
        return lam * trace(E) * eye(3) + 2 * mu * E

    def material_tangent(self, kin):
        # C_IJKL = lambda * delta_IJ * delta_KL + mu * (delta_IK delta_JL + delta_IL delta_JK)
        ...
```

### A4.3  Power-law J2 plasticity

Implement `compmech.symbolic.models.j2_power_law`:

- Yield function: $f = \sigma_{eq} - \sigma_y(\bar{\varepsilon}_p)$
- Hardening: $\sigma_y = \sigma_{y0} + K\,\bar{\varepsilon}_p^{\,n}$
- Return mapping: radial return, scalar Newton for $\Delta\lambda$
- Algorithmic tangent: $\mathbb{C}^{alg}$ in Voigt form

The return mapping is implemented symbolically for code generation and numerically for verification.

### A4.4  Voigt module

Implement `compmech.symbolic.voigt`:
- `tensor_to_voigt_3d(A)` → 6-vector
- `voigt_to_tensor_3d(v)` → 3×3
- `tangent_4to_voigt_3d(C_ijkl)` → 6×6 matrix
- `mandel_from_voigt(C_voigt)` → 6×6 Mandel
- Round-trip tests, known isotropic $C$ Voigt, symmetries.

### A4.5  AD oracle for constitutive verification

Implement `compmech.verify.ad_oracle`:
- Lambdify the symbolic $S(E)$ to a PyTorch/Taichi autodiff function
- At N=100 random deformation states: compare symbolic $S_{IJ}$ against AD-computed stress
- Assert relative error < 1e-10

**Exit criterion A4:** SVK stress/tangent and J2 return mapping pass AD oracle. Voigt round-trips exact. Kinematics at F=I gives identity measures.

---

## Phase A5 — Mechanics IR + Element IR

**Duration:** 1 week

### A5.1  Mechanics IR implementation

Implement `compmech.ir.mechanics_ir`:
- `ProblemIR` dataclass and all sub-entities from `04-MECHANICS-IR.md`
- IR construction from parser context dict + symbolic engine output
- All validation checks from `04-MECHANICS-IR.md §5`
- Supported-subset rejection from `00-OVERVIEW.md §8`
- Serialisation (`to_dict()`, `to_yaml()`, `from_dict()`)

### A5.2  Element IR implementation

Implement `compmech.ir.element_ir`:
- `ElementIR` dataclass from `05-ELEMENT-IR.md`
- Hex8 basis functions, gradients, 2×2×2 Gauss quadrature
- Geometry mapping (reference Jacobian)
- **Convected coordinate data:** metric tensors $G_{IJ}$, $g_{IJ} = C_{IJ}$, stored in Element IR for use by the code generator. Test P6 from `08-VERIFICATION.md` applies here.

### A5.3  FE localisation

Implement `compmech.lowering.fe_localise`:
- Takes `ProblemIR`, produces `ElementIR`
- Extracts einsum strings for local force and tangent
- Validates element compatibility with problem dimension

### A5.4  Artifact bundle

Implement `compmech.codegen.artifact`:
- `ArtifactBundle` class that collects Mechanics IR, Element IR, contraction plans, generated source
- Serialisation for golden-file comparison

**Exit criterion A5:** `ProblemIR` → `ElementIR` pipeline works for MVP inputs. IR serialisation round-trips. Unsupported inputs are rejected with actionable errors.

---

## Phase A6 — opt_einsum integration and JIT budget counter

**Duration:** 3–5 days

### A6.1  Port einsum_optimizer module

Implement `compmech/codegen/einsum_optimizer.py` with full test coverage:
- Budget counting for Hex8
- Tier classification (Tier 1 for rank-2 GEMM, Tier 2 for rank-4)
- Guardrail triggers on artificially oversized contractions

### A6.2  Integrate with Element IR

Extract einsum strings from `ElementIR.local_force.einsum_str` and `ElementIR.local_tangent.einsum_str`, pass to `plan_contraction()`, store `ContractionPlan` in artifact bundle.

### A6.3  Budget regression test

pytest fixture that runs `plan_contraction()` on all MVP contractions and asserts `not plan.over_budget`. Runs in CI on every commit.

**Exit criterion A6:** All contractions pass budget. Speedup factors match expected values.

---

## Phase A7 — Taichi codegen: Hex8 element kernel

**Duration:** 1–2 weeks

### A7.1  Hex8 reference element data

Compile-time constants: trilinear shape functions, gradients, 2×2×2 Gauss points and weights.
Test: partition of unity, constant field exactness.

### A7.2  TaichiPrinter implementation

Implement `compmech.codegen.taichi_printer.TaichiPrinter`:
- Consumes `ElementIR` and `ProblemIR`
- Emits complete `.py` file per `06-CODEGEN.md`
- Uses tier assignments from contraction plans
- Includes convected coordinate infrastructure

### A7.3  Constitutive kernel emission

Generate the `constitutive_update` `@ti.func` from symbolic SVK stress + J2 return mapping.
- CSE on tangent expressions
- Numerical safeguards (J > 0, σ_eq > tol)

### A7.4  Element kernel emission

Generate `compute_internal_forces` `@ti.kernel`:
- Deformation gradient computation
- Constitutive call
- PK1 → nodal force scatter
- Budget validation before emission

### A7.5  Matrix-free tangent

Generate `tangent_matvec` `@ti.kernel`:
- Push-forward contraction (Tier 2, 486 static lines)
- Geometric stiffness term
- Dirichlet enforcement on matvec

**Exit criterion A7:** Generated Taichi file compiles without errors. Single-element patch test passes. Matrix-free matvec matches assembled stiffness (NumPy comparison for one element).

---

## Phase A8 — Newton-Raphson driver, BCs, mesh I/O

**Duration:** 1 week

### A8.1  Newton-Raphson driver

Generate the Newton loop per `06-CODEGEN.md §9`. Calls imported linear solver.

### A8.2  Boundary condition generation

Generate BC routines per `10-BOUNDARIES.md`:
- `bc_mask` field and Dirichlet enforcement functions
- Traction force computation for Neumann BCs
- Component-wise BC support

### A8.3  Mesh I/O

Minimal mesh reader for structured Hex8 meshes (generated in Python). VTK/XDMF output via `meshio`.

### A8.4  Load stepping

Incremental loading with adaptive step size.

**Exit criterion A8:** Cantilever beam (large-deformation SVK elastic) converges with Newton-Raphson. Tip displacement matches reference within 2%.

---

## Phase A9 — J2 plasticity integration

**Duration:** 1–2 weeks

### A9.1  Return mapping code generation

Generate the radial return `@ti.func` from symbolic J2 model:
- Elastic predictor
- Yield check
- Scalar Newton for $\Delta\lambda$ with power-law hardening
- Stress update, PEEQ update

### A9.2  Algorithmic tangent generation

Generate consistent tangent $\mathbb{C}^{alg}$ as 6×6 Voigt:
- Elastic: return elastic tangent
- Plastic: consistent elasto-plastic tangent

### A9.3  History variable management

Generate Taichi fields for `peeq`, `stress_old`, `peeq_old`. Generate copy kernel (`current → old`) at converged steps.

### A9.4  Integration into element kernel

Replace elastic-only constitutive call with full elasto-plastic `constitutive_update`.

### A9.5  Verification

- Below yield: matches elastic reference exactly
- Uniaxial tension past yield: $\sigma = \sigma_y + H\varepsilon_p$
- Return mapping: $f(\sigma^{n+1}) = 0$ to machine precision
- Algorithmic tangent: symmetric, matches numerical tangent (FD)

**Exit criterion A9:** Single-element uniaxial tension reproduces exact hardening curve. Cook's membrane matches reference.

---

## Phase A10 — MVP integration and verification

**Duration:** 1 week

### A10.1  End-to-end pipeline test

Write a single test that:
1. Parses a LaTeX input file with `% mechanics` directives
2. Builds Mechanics IR, validates, checks supported subset
3. Lowers to Element IR, extracts einsum strings
4. Runs einsum optimiser, verifies budget
5. Generates Taichi code via TaichiPrinter
6. Runs generated solver
7. Compares against handwritten reference (from phase A2)
8. Compares against physical benchmarks

### A10.2  Generated vs handwritten comparison

For each reference solver from A2:
- Run both on identical mesh and BCs
- Displacement field max difference < 1e-10

### A10.3  Physical benchmark suite

| Test | Model | Mesh | Reference | Acceptance |
|------|-------|------|-----------|------------|
| Patch test | SVK elastic | Irregular Hex8 | Constant strain exact | Relative error < 1e-12 |
| Rigid body | SVK elastic | Any Hex8 | Zero force | Force norm < 1e-12 |
| Cantilever (elastic) | SVK elastic | 40×8×4 Hex8 | EB beam theory | Within 5% (coarse mesh) |
| Cook's membrane | Hooke + power-law J2 | Graded Hex8 | de Souza Neto | Tip displacement within 2% |
| Necking bar | Hooke + power-law J2 | Hex8, axial symmetry | Simo & Hughes (1998) | Load-disp curve within 2% |

### A10.4  Compiler-pass test coverage

Verify all tests from `08-VERIFICATION.md §2` pass:
- Parser tests (P1–P6)
- Symbolic tests (S1–S9)
- IR tests (M1–M6)
- Element IR tests (E1–E6)
- Einsum tests (N1–N5)
- Backend tests (T1–T4)
- Boundary tests (B1–B5)
- Artifact tests (A1–A3)
- Code emission tests (C1–C3)

### A10.5  Documentation

- README with installation and quickstart
- Example LaTeX input file for each verification problem
- Rendered output comparison (FEM vs reference)

**Exit criterion A10 (MVP DONE):** All 5 physical benchmarks pass. All compiler-pass tests pass. Generated code matches handwritten reference. Full pipeline runs from LaTeX to converged solution.

---

## Total estimated duration: 10–14 weeks

| Phase | Duration | Cumulative |
|-------|----------|------------|
| A1 Scaffolding | 3–4 days | 1 week |
| A2 Handwritten reference kernels | 1 week | 2 weeks |
| A3 Parser | 1–2 weeks | 4 weeks |
| A4 Symbolic engine | 1–2 weeks | 6 weeks |
| A5 IR construction | 1 week | 7 weeks |
| A6 Einsum optimiser | 3–5 days | 8 weeks |
| A7 Taichi codegen | 1–2 weeks | 10 weeks |
| A8 Newton + BCs + mesh | 1 week | 11 weeks |
| A9 J2 plasticity | 1–2 weeks | 13 weeks |
| A10 Integration + V&V | 1 week | 14 weeks |
