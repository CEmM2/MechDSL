# 08 — Verification and Validation Strategy

---

## 1  Purpose

This document specifies the V&V strategy for the CompMech DSL compiler and generated solvers. Verification is structured in two tiers:

1. **Compiler-pass tests** — verify each stage of the compiler pipeline in isolation.
2. **Physical benchmarks** — verify end-to-end correctness of generated FEM solvers against analytical solutions and published results.

Both tiers run in CI. Compiler-pass tests run on every commit; physical benchmarks run nightly.

---

## 2  Compiler-pass tests

Each compiler stage has its own test suite that validates correctness independently of downstream stages. When a generated solver produces wrong results, these tests isolate the bug to a specific pipeline stage.

### 2.1  Parser tests (Layer 1)

| ID | Test | Input | Expected output |
|----|------|-------|----------------|
| P1 | Valid MVP source | Hex8 TL elasto-plastic LaTeX | Correct context dict with dim=3, cell_type="hex8", kinematics="total_lagrangian", material params |
| P2 | Unknown directive | `% mechanics foo` | `ParseError` with line number and suggestion |
| P3 | Two-point tensor | `F_{iI}` | Spatial index `i`, material index `I`, two-point flag |
| P4 | Index manifold clash | Contract spatial with material without two-point tensor | `IndexError` with guidance |
| P5 | Missing required directive | No `dim` declaration | `ParseError` listing required directives |
| P6 | Convected coordinate declaration | `% mechanics coord convected theta1 theta2 theta3` | Correct convected coordinate symbols |

### 2.2  Symbolic engine tests (Layer 2)

| ID | Test | Validation |
|----|------|-----------|
| S1 | Kinematics at F=I | C=I, J=1, E=0, b=I |
| S2 | Kinematics at known shear | C, E match hand calculation |
| S3 | St. Venant-Kirchhoff stress | S_IJ = C_IJKL * E_KL for known E |
| S4 | Power-law hardening curve | σ_y(ε_p) matches analytical σ_y0 + K * ε_p^n at sample points |
| S5 | Voigt round-trip | tensor → Voigt → tensor = identity |
| S6 | Mandel round-trip | Voigt → Mandel → Voigt = identity |
| S7 | Tangent symmetry | C_IJKL = C_KLIJ (major symmetry) |
| S8 | AD oracle | Symbolic S vs autodiff 2∂Ψ/∂C at 100 random F states, relative error < 1e-10 |
| S9 | Convected metric | g_IJ = C_IJ for Cartesian reference configuration |

### 2.3  Mechanics IR tests

| ID | Test | Validation |
|----|------|-----------|
| M1 | Valid IR construction | ProblemIR from valid context dict — no errors |
| M2 | Unsupported constitutive model | `UnsupportedConstitutiveError` with list of supported models |
| M3 | Dimension mismatch | 2D field in 3D problem → `DimensionError` |
| M4 | Missing BC region | BC references undeclared region → `BoundaryRegionError` |
| M5 | IR serialisation round-trip | `ProblemIR.from_dict(ir.to_dict()) == ir` |
| M6 | Supported-subset rejection | Unsupported cell type → explicit rejection |

### 2.4  Element IR / FE localisation tests

| ID | Test | Validation |
|----|------|-----------|
| E1 | Hex8 shape functions | Partition of unity: $\sum_a N_a(\xi) = 1$ at all quad points |
| E2 | Hex8 constant field | Constant field reproduced exactly through interpolation |
| E3 | Hex8 Jacobian | Known regular hex: det(J) = expected volume / 8 |
| E4 | Physical gradients | $\sum_a dN_a/dX_I = 0$ (gradient of constant) |
| E5 | Einsum string extraction | LocalForceIR.einsum_str matches expected contraction pattern |
| E6 | Convected geometry mapping | For Cartesian reference, convected = standard TL mapping |

### 2.5  Einsum / contraction tests

| ID | Test | Validation |
|----|------|-----------|
| N1 | Budget count | All MVP contractions pass JIT budget (< 2000 lines) |
| N2 | Tier classification | Rank-2 GEMM → Tier 1, rank-4 push-forward → Tier 2 |
| N3 | Forced budget overflow | Artificially large contraction → Tier 3 fallback, not crash |
| N4 | Contraction correctness | opt_einsum result matches naive numpy.einsum on random data |
| N5 | Speedup factor | TL element stiffness: speedup ≥ 10x over naive |

### 2.6  Backend scheduling and template tests

| ID | Test | Validation |
|----|------|-----------|
| T1 | Tier 1 emission | GEMM step emits `ti.Matrix @` call |
| T2 | Tier 2 emission | Rank-4 step emits `ti.static` loop nest |
| T3 | Code-size cutoff | Kernel exceeding `func_budget` → split into sub-functions |
| T4 | Static vs runtime | Physics indices (range ≤ 6) are `ti.static`; node loops are runtime |

### 2.7  Boundary condition tests

| ID | Test | Validation |
|----|------|-----------|
| B1 | Boundary-tag mapping | Named region maps to correct mesh tag set |
| B2 | Dirichlet enforcement | Known system with fixed DOF: modified matvec produces identity on fixed row |
| B3 | Component-wise BC | Fix x only: y and z remain free |
| B4 | Neumann integration | Constant traction on face: integrated force = traction × area |
| B5 | Missing binding | Unbonded region → `BoundaryBindingError` |

### 2.8  Artifact inspection tests

| ID | Test | Validation |
|----|------|-----------|
| A1 | Artifact bundle completeness | Bundle contains: Mechanics IR, Element IR, einsum plans, scheduling decisions, generated source |
| A2 | Golden-file diff | Artifact matches stored golden file (no unintended changes) |
| A3 | Artifact round-trip | Serialise → deserialise → re-serialise produces identical bytes |

### 2.9  Code emission tests

| ID | Test | Validation |
|----|------|-----------|
| C1 | Generated code syntax | Generated Taichi file parses without Python syntax errors |
| C2 | Import correctness | Generated file imports run without `ImportError` |
| C3 | Generated vs handwritten | Generated element stiffness matches handwritten reference for one element (see §3.1) |

---

## 3  Handwritten reference baselines

### 3.1  Purpose

Before the compiler generates element kernels, a **handwritten Taichi reference implementation** is created and verified. This serves as:

- Ground truth for generated code comparison
- Smoke test for the imported linear solver
- Validation that the physics is correct independently of the compiler

### 3.2  Reference implementations

| Reference | Element | Material | What it validates |
|-----------|---------|----------|-------------------|
| `ref_hex8_elastic.py` | Hex8 | St. Venant-Kirchhoff | TL assembly, Newton-Raphson, patch test |
| `ref_hex8_plastic.py` | Hex8 | Hooke + power-law J2 | Return mapping, history variables, load stepping |

### 3.3  Verification of generated code against reference

For each reference implementation, a test:

1. Runs the handwritten reference on a small mesh
2. Runs the compiler-generated code on the same mesh
3. Compares: displacement field max difference < 1e-10

This test is the **strongest correctness guarantee** in the system.

---

## 4  Physical benchmarks

### 4.1  MVP benchmark suite

| Test | Model | Mesh | Reference | Acceptance |
|------|-------|------|-----------|------------|
| Patch test (constant strain) | SVK elastic | Irregular Hex8 | Exact constant strain | Relative error < 1e-12 |
| Rigid body motion | SVK elastic | Any Hex8 | Zero internal force | Force norm < 1e-12 |
| Cantilever (large deformation) | SVK elastic | 40×8×4 Hex8 | Euler-Bernoulli theory | Tip displacement within 5% (coarse mesh) |
| Cook's membrane | Hooke + power-law J2 | Graded Hex8 | de Souza Neto et al. | Tip displacement within 2% |
| Necking bar | Hooke + power-law J2 | Hex8 (axial symmetry) | Simo & Hughes (1998) | Load-displacement curve within 2% |

### 4.2  Convergence studies

For each element type, run MMS (Method of Manufactured Solutions):

- Manufacture a smooth displacement field: $u^*(x) = A \sin(\pi x/L) \cos(\pi y/L) \sin(\pi z/L)$
- Compute the corresponding manufactured body force
- Solve on 4+ mesh refinements
- Verify convergence rate: $L^2$ rate ≥ $p+1$, $H^1$ rate ≥ $p$ where $p$ is the polynomial order

### 4.3  AD oracle suite

For each constitutive model:

- At $N=100$ random deformation states (uniformly in a neighbourhood of $F = I$):
- Compare symbolic stress $S_{IJ}$ against autodiff $2\partial\Psi/\partial C_{IJ}$
- Compare symbolic tangent $\mathbb{C}_{IJKL}$ against autodiff $2\partial S/\partial C$
- Assert relative error < 1e-10

---

## 5  Regression test integration

### 5.1  CI tiers

| Tier | When | What | Time budget |
|------|------|------|-------------|
| Fast | Every commit | Parser, symbolic, IR, einsum, emission tests (§2) | < 2 min |
| Medium | Every PR | Handwritten reference comparison (§3) | < 10 min |
| Nightly | Scheduled | Full physical benchmarks (§4) | < 60 min |

### 5.2  Golden-file management

Artifact golden files are checked into `tests/golden/`. Any change to the golden files requires explicit approval in the PR. The golden-file diff is the primary tool for reviewing compiler changes: if the generated code changed, the diff shows exactly how.

### 5.3  Failure protocol

- Compiler-pass test failure → blocks merge
- Reference comparison failure → blocks merge
- Physical benchmark regression → creates issue, does not block merge (may be mesh/tolerance related)

---

## 6  Plan B extensions

| Phase | Additional tests |
|-------|-----------------|
| B1 (UL) | TL vs UL equivalence test: same problem, both formulations, matching displacement |
| B2 (Convected) | Curvilinear patch test, Cartesian equivalence test |
| B3 (Viscoplasticity) | Rate sensitivity test, quasi-static limit test |
| B4 (Hyperelasticity) | Each model: AD oracle + uniaxial against closed-form |
| B5 (Elements) | Patch test per element type, hourglass mode test for reduced integration |
| B6 (Damage) | D=0 regression, monotonic damage increase |
| B7 (Explicit) | Free vibration period, explicit-implicit cross-check |
| B8 (MFEM/MOOSE) | Cross-backend comparison: 3 backends, same problem, matching results |
