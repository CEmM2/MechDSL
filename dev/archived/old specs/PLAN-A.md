# Implementation Plan A — Setup → MVP

**Goal:** A working 3D finite element code that solves large-deformation hyper-elasto-plastic boundary value problems using Total Lagrangian Hex8 elements, driven by LaTeX input.

**MVP acceptance test:** Solve a necking bar problem (J2 plasticity + neo-Hookean elastic, 3D Hex8 mesh, Newton-Raphson with imported linear solver) and reproduce the load-displacement curve from Simo & Hughes (1998) within 2% of the reference.

**Dependencies from the user:** existing Taichi linear solver library (CG/PCG), to be imported as a module.

---

## Phase A1 — Repository scaffolding

**Duration:** 3–4 days

### A1.1  Create repo and package structure

Set up `compmech/` as a `uv`-managed Python package with `src` layout:

```
compmech/
├── pyproject.toml          # uv, build metadata, dependencies
├── src/
│   └── compmech/
│       ├── __init__.py
│       ├── frontend/
│       ├── symbolic/
│       ├── weakform/
│       ├── codegen/
│       ├── solver/
│       ├── verify/
│       └── lib/             # pre-written Taichi ti.func library
└── tests/
```

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

## Phase A2 — NRPyLaTeX fork and `% mechanics` parser

**Duration:** 1–2 weeks

### A2.1  Fork NRPyLaTeX

- Fork `zachetienne/nrpylatex` into project org
- Add as `uv` git dependency: `nrpylatex = { git = "...", branch = "compmech" }`
- Verify all existing NRPyLaTeX tests pass

### A2.2  Add `% mechanics` directive infrastructure

In `scanner.py`, add tokens:

```python
('MECHANICS_KWD', r'mechanics'),
```

In `parser.py`, extend `_config()`:

```python
elif self.accept('MECHANICS_KWD'):
    self._mechanics_directive()
```

Implement `_mechanics_directive()` as a dispatcher that reads the command keyword and calls sub-handlers: `_mech_dim()`, `_mech_coord()`, `_mech_material()`, `_mech_formulation()`.

### A2.3  Implement core directives

| Directive | Handler | Output |
|-----------|---------|--------|
| `% mechanics dim 3` | `_mech_dim` | Sets `ctx['dim']` |
| `% mechanics coord spatial x y z` | `_mech_coord` | Sets coordinate symbols |
| `% mechanics coord material X Y Z` | `_mech_coord` | Sets material coordinates |
| `% mechanics material neo_hookean --mu mu --kappa kappa` | `_mech_material` | Populates `ctx['params']`, `ctx['material_type']` |
| `% mechanics material j2 --E E --nu nu --sigma_y sigma_y` | `_mech_material` | Same |
| `% mechanics formulation total_lagrangian` | `_mech_formulation` | Sets `ctx['formulation']` |

### A2.4  Two-point tensor index support

Add `manifold` attribute to `IndexedSymbol`:
- `% mechanics index spatial i j k l` → spatial indices
- `% mechanics index material I J K L` → material indices
- Parser validates: contracted indices share the same manifold (or go through a two-point tensor)

### A2.5  Integration test

Parse the following and verify the output context dictionary:

```latex
% mechanics dim 3
% mechanics coord spatial x y z
% mechanics coord material X Y Z
% mechanics material neo_hookean --mu mu --kappa kappa
% mechanics formulation total_lagrangian
```

**Exit criterion A2:** `compmech.frontend.parse(latex_str)` returns correct context dict with params, dims, material type, coordinate symbols. All NRPyLaTeX upstream tests still pass.

---

## Phase A3 — Symbolic engine: kinematics and constitutive

**Duration:** 1–2 weeks

### A3.1  Kinematics module

Implement `compmech.symbolic.kinematics`:

```python
def compute(dim: int, u_symbols, X_symbols) -> KinematicsResult:
    # Build F = I + grad(u) symbolically
    # Compute C = F^T F, J = det(F), E = (C-I)/2
    # Compute Finv, FinvT
    ...
```

Test: at F = I, verify C = I, J = 1, E = 0.
Test: at known simple shear F, verify C, E against hand calculation.

### A3.2  Neo-Hookean constitutive model

Implement `compmech.symbolic.models.neo_hookean`:

```python
class NeoHookean(ConstitutiveModel):
    def strain_energy(self, kin):
        Ibar1 = kin.J**(-Rational(2,3)) * trace(kin.C)
        return (self.mu / 2) * (Ibar1 - 3) + (self.kappa / 2) * (kin.J - 1)**2
    
    def pk2_stress(self, kin):
        return 2 * diff(self.strain_energy(kin), kin.C)  # component-wise
    
    def material_tangent(self, kin):
        S = self.pk2_stress(kin)
        return 2 * diff(S, kin.C)  # 4th order
```

Test against known closed-form neo-Hookean PK2 expressions.

### A3.3  Voigt module

Implement `compmech.symbolic.voigt`:
- `tensor_to_voigt_3d(A)` → 6-vector
- `voigt_to_tensor_3d(v)` → 3×3
- `tangent_4to_voigt_3d(C_ijkl)` → 6×6 matrix
- `mandel_from_voigt(C_voigt)` → 6×6 Mandel
- `voigt_from_mandel(C_mandel)` → 6×6 Voigt

Test: round-trips, known isotropic C_voigt, symmetries.

### A3.4  AD oracle for constitutive verification

Implement `compmech.verify.ad_oracle`:
- Lambdify the symbolic Ψ(C) to a PyTorch/Taichi autodiff function
- At N=100 random deformation states: compare symbolic S_IJ against AD-computed 2∂Ψ/∂C_IJ
- Assert relative error < 1e-10

**Exit criterion A3:** Neo-Hookean stress and tangent pass AD oracle. Voigt round-trips exact. Kinematics at F=I gives identity measures.

---

## Phase A4 — opt_einsum integration and JIT budget counter

**Duration:** 3–5 days

### A4.1  Port einsum_optimizer module

Move `compmech/codegen/einsum_optimizer.py` (the PoC from this conversation) into the package proper. Add full test coverage:
- Budget counting for all element types
- Tier classification correctness (Tier 1 for rank-2 GEMM, Tier 2 for rank-4)
- Guardrail triggers on artificially oversized contractions

### A4.2  Integrate with symbolic engine output

Write the bridge that extracts einsum strings from SymPy tensor expressions:
- Given a symbolic expression `S_IJ * F_iJ * dN_aI`, identify the index structure and produce `'IJ,iJ,aI->ai'`
- Pass to `plan_contraction()`, receive `ContractionPlan`

### A4.3  Budget regression test

Add a pytest fixture that runs `plan_contraction()` on every contraction from every constitutive model × every element type and asserts `not plan.over_budget`. This runs in CI on every commit.

**Exit criterion A4:** All contractions pass budget. Speedup factors match expected values (46x for full TL element stiffness, 7.5x for Voigt B^T C B).

---

## Phase A5 — Taichi codegen: Hex8 element kernel

**Duration:** 1–2 weeks

### A5.1  Hex8 reference element

Implement shape functions and gradients for the 8-node hexahedron:
- Trilinear shape functions: $N_a(\xi, \eta, \zeta) = \frac{1}{8}(1 + \xi_a\xi)(1 + \eta_a\eta)(1 + \zeta_a\zeta)$
- Shape function gradient: $\frac{\partial N_a}{\partial \xi_i}$
- 2×2×2 Gauss quadrature (8 points, weights = 1.0)
- Jacobian: $J_{ij} = \sum_a \frac{\partial N_a}{\partial \xi_j} X_{ai}$

Store quadrature points and reference gradients as compile-time constants.

Test: partition of unity, constant field exactness.

### A5.2  Element kinematics kernel

`@ti.func` that computes at one quadrature point:
- Deformation gradient: $F_{iI} = \delta_{iI} + \sum_a u_{ai}\,\frac{\partial N_a}{\partial X_I}$
- Where $\frac{\partial N_a}{\partial X_I} = \left(\frac{\partial N_a}{\partial \xi_j}\right) J^{-1}_{jI}$
- $J = \det(F)$, $C = F^T F$

Use Tier 1 functions from `compmech.lib.tensor_ops`.

### A5.3  Constitutive kernel

`@ti.func` that evaluates PK2 stress and material tangent from neo-Hookean model at one quadrature point.

This function is **generated** from the symbolic neo-Hookean expressions via SymPy `lambdify` → Taichi code printer. The einsum optimiser determines the contraction order for the tangent push-forward.

### A5.4  Internal force kernel

`@ti.kernel` over all elements:

```python
for e in range(n_elems):
    for q in ti.static(range(8)):  # 2×2×2 quad
        F = compute_F(e, q)
        S = compute_pk2(F)
        P = pk1_from_pk2(F, S)
        # scatter P · dN to nodal forces (Tier 3 pattern: runtime node loop)
        for a in range(8):
            f_int[conn[e,a]] += P @ dN_ref[a,q] * detJ[e,q] * w_q
```

Budget check before emission: should be ~123 static lines for the physics + 81 for scatter = 204.

### A5.5  Element stiffness (matrix-free)

`@ti.func` for tangent operator application $\mathbf{y} = \mathbf{K}(\mathbf{u})\,\mathbf{x}$:
- Compute virtual gradient $\delta F_{iI} = \sum_a x_{ai}\,\frac{\partial N_a}{\partial X_I}$
- Apply pushed tangent: $\delta P_{iI} = \mathcal{A}_{iIjJ}\,\delta F_{jJ}$
- Use Tier 2 emission for the push-forward contraction (243 + 243 = 486 lines)
- Scatter $\delta P \cdot dN$ to output vector

**Exit criterion A5:** Single-element patch test passes (constant strain → exact stress). Rigid body motion produces zero internal force. Matrix-free operator matches assembled stiffness (compare against NumPy for one element).

---

## Phase A6 — Newton-Raphson driver, BCs, mesh I/O

**Duration:** 1 week

### A6.1  Newton-Raphson driver

```python
def newton_solve(u, f_ext, tol=1e-8, max_iter=20):
    for iteration in range(max_iter):
        f_int = compute_internal_forces(u)
        R = f_int - f_ext
        apply_dirichlet_to_residual(R)
        r_norm = norm(R)
        if r_norm < tol * r_norm_0:
            return u, iteration
        
        # Linear solve: K du = -R using imported solver
        matvec = lambda x: apply_tangent_operator(u, x)
        du = linear_solver.solve(matvec, -R)
        apply_dirichlet_to_increment(du)
        u += du
```

The linear solver is the user's imported CG/PCG. The Newton driver only calls its `solve(matvec, rhs)` interface.

### A6.2  Boundary condition application

- Dirichlet: zero rows/columns in matvec (identity on fixed DOFs), zero residual on fixed DOFs
- Neumann: add traction contributions to `f_ext`
- Displacement-controlled: incremental loading with load steps

### A6.3  Mesh I/O

Minimal mesh reader for structured Hex8 meshes (generated in Python). Support for VTK/XDMF output using `meshio` for paraview visualisation.

### A6.4  Load stepping

Incremental loading with adaptive step size:
- If Newton converges in < 5 iterations, increase step size (×1.5)
- If Newton fails to converge, halve step size and retry

**Exit criterion A6:** Cantilever beam (large-deformation neo-Hookean) converges with Newton-Raphson. Tip displacement matches reference within 2%.

---

## Phase A7 — J2 plasticity

**Duration:** 1–2 weeks

### A7.1  Return mapping (radial return)

Implement `compmech.lib.j2_return`:
- Elastic predictor: $\sigma^{tr} = \sigma^n + C_e : \Delta\varepsilon$
- Yield check: $f^{tr} = \sigma_{eq}^{tr} - \sigma_y(\bar{\varepsilon}_p^n)$
- Scalar Newton for $\Delta\lambda$
- Stress update: $s^{n+1} = s^{tr} - 2\mu\Delta\lambda\,\mathbf{n}$
- PEEQ update: $\bar{\varepsilon}_p^{n+1} = \bar{\varepsilon}_p^n + \Delta\lambda$

All in a single `@ti.func` operating in tensorial Voigt (6 components).

### A7.2  Algorithmic tangent

Implement consistent tangent $\mathbb{C}^{alg}$ as a 6×6 Voigt matrix:
- Elastic: return $C_e$
- Plastic: $C^{alg} = \kappa\,\delta\otimes\delta + 2\mu\theta\,I^{dev} - 2\mu(\theta - \bar{\theta})\,n\otimes n$

### A7.3  History variable management

Per-element, per-quadrature-point Taichi fields:
- `peeq[n_elem, n_quad]` — equivalent plastic strain
- `stress_old[n_elem, n_quad, 6]` — stress at previous step (Voigt)
- `backstress[n_elem, n_quad, 6]` — kinematic hardening backstress (if used)

Copy current → old at end of each converged load step.

### A7.4  Stress update integration into element kernel

Replace the hyperelastic constitutive call with:
1. Compute $F$, build strain increment $\Delta\varepsilon$ from $F^n, F^{n+1}$
2. Call radial return in corotational frame (using Hughes-Winget rotation)
3. Return Cauchy stress → convert to PK2 for TL assembly

### A7.5  Verification

- Pure elastic loading (below yield): J2 reduces to linear elastic — verify stress matches
- Uniaxial tension past yield: check $\sigma = \sigma_y + H\varepsilon_p$
- Radial return: verify $f(\sigma^{n+1}) = 0$ to machine precision
- Algorithmic tangent: verify symmetry, compare against numerical tangent (finite difference on stress)

**Exit criterion A7:** Single-element uniaxial tension reproduces exact hardening curve. Multi-element Cook's membrane matches reference.

---

## Phase A8 — MVP integration and verification

**Duration:** 1 week

### A8.1  End-to-end pipeline test

Write a single test that:
1. Parses a LaTeX input file with `% mechanics` directives
2. Builds symbolic kinematics and constitutive model
3. Runs einsum optimizer, verifies budget
4. Generates Taichi element kernels
5. Runs Newton-Raphson with load stepping
6. Compares results against reference

### A8.2  Verification suite

| Test | Model | Mesh | Reference | Acceptance |
|------|-------|------|-----------|------------|
| Patch test | Neo-Hookean | Irregular Hex8 | Constant strain exact | Relative error < 1e-12 |
| Rigid body | Neo-Hookean | Any Hex8 | Zero force | Force norm < 1e-12 |
| Cantilever (elastic) | Neo-Hookean | 40×8×4 Hex8 | EB beam theory | Within 5% (coarse mesh) |
| Cook's membrane | J2 | Graded Hex8 | Literature (de Souza Neto) | Tip displacement within 2% |
| Necking bar | J2 + neo-Hookean | Hex8, axial symmetry | Simo & Hughes (1998) | Load-disp curve within 2% |

### A8.3  Documentation

- README with installation and quickstart
- Example LaTeX input file for each verification problem
- Rendered output comparison (FEM vs reference)

**Exit criterion A8 (MVP DONE):** All 5 verification tests pass. Full pipeline runs from LaTeX to converged solution.

---

## Total estimated duration: 8–12 weeks

| Phase | Duration | Cumulative |
|-------|----------|------------|
| A1 Scaffolding | 3–4 days | 1 week |
| A2 Parser | 1–2 weeks | 3 weeks |
| A3 Symbolic engine | 1–2 weeks | 5 weeks |
| A4 Einsum optimizer | 3–5 days | 6 weeks |
| A5 Hex8 codegen | 1–2 weeks | 8 weeks |
| A6 Newton + BCs | 1 week | 9 weeks |
| A7 J2 plasticity | 1–2 weeks | 11 weeks |
| A8 Integration + V&V | 1 week | 12 weeks |
