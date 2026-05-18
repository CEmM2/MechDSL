# CompMech DSL — Specification Suite

**Version:** 0.2
**Status:** Draft
**Date:** March 2026

---

## 1  Project statement

CompMech DSL is a domain-specific language for computational mechanics that lets researchers write constitutive models and boundary-value problems in LaTeX notation and obtain working finite element solvers as output. The compiler pipeline is:

```
LaTeX source  →  SymPy symbolic tensors  →  Mechanics IR  →  Element IR  →  Einsum IR  →  Taichi solver code
```

The user writes a `.tex` file containing both their equations (rendered normally by pdflatex) and embedded `% mechanics` directives (ignored by LaTeX, consumed by the DSL). The DSL produces a correct, tested FEM implementation — no hand-coding of element routines.

**Until version 1.0, the sole code-generation target is Taichi.** Additional backends (MFEM, MOOSE) are planned for post-1.0.

---

## 2  Scope

### In scope

- 3D continuum mechanics (large deformation, Total Lagrangian)
- Constitutive models: Hooke elasticity (St. Venant-Kirchhoff), J2 plasticity with power-law hardening
- Convected coordinate framework
- Nonlinear FEM with Newton-Raphson
- Code generation targeting Taichi (GPU-accelerated)
- Verification against analytical solutions and method of manufactured solutions

### Long-range scope (post-MVP)

- 2D plane stress / plane strain
- Anisotropic hyperelasticity (Mooney-Rivlin, Ogden, HGO)
- Rate-dependent viscoplasticity (Perzyna, Johnson-Cook)
- Continuum damage (Lemaitre CDM)
- Updated Lagrangian formulation
- Explicit dynamics (central difference)
- Additional elements (Tet4, Tet10, Hex20, reduced integration)
- Additional backends (MFEM, MOOSE)

### Out of scope (for now)

- Beam, shell, and plate elements
- Multi-physics coupling (thermal, fluid)
- Contact mechanics
- Mesh generation (external tool)
- Adaptive mesh refinement

---

## 3  MVP definition

**Target:** A working 3D finite element code that solves large-deformation elasto-plastic boundary-value problems using Total Lagrangian Hex8 elements with convected coordinates, driven by LaTeX input.

**Constitutive model:**
- **Elastic:** St. Venant-Kirchhoff (Hooke's law in the reference configuration): $S_{IJ} = \mathbb{C}_{IJKL}\,E_{KL}$
- **Plastic:** J2 plasticity with power-law isotropic hardening: $\sigma_y(\bar{\varepsilon}_p) = \sigma_{y0} + K\,\bar{\varepsilon}_p^{\,n}$
- **Return mapping:** Radial return in the corotational frame, consistent algorithmic tangent

**Acceptance test:** Solve a necking bar problem (3D Hex8 mesh, power-law elasto-plasticity, Newton-Raphson with imported linear solver) and reproduce the load-displacement curve from Simo & Hughes (1998) within 2% of the reference.

---

## 4  Design decisions

These decisions are settled and not open for revisitation without strong cause.

| # | Decision | Rationale |
|---|----------|-----------|
| D1 | Use **SymPDE** (not UFL) for variational forms | SymPDE is pure SymPy, MIT-licensed, and framework-agnostic. UFL is tightly coupled to FEniCS. SymPDE's custom-printer architecture matches our multi-backend requirement. |
| D2 | **Fork** NRPyLaTeX (not wrap) | Two-point tensors (indices on different manifolds) require parser-level support. The codebase is small (~90 commits, hand-rolled recursive descent) and forkable. |
| D3 | Primary target is **plasticity and damage** | Hyperelasticity is included for large-deformation kinematics, but the constitutive library prioritises J2 plasticity, hardening laws, and damage models. |
| D4 | Use **AutoFD-style functional differentiation** as a verification tool, not a runtime dependency | AutoFD is JAX-only. We use the same concept (differentiate energy functionals numerically) as a test oracle for symbolic stress/tangent derivations. Implement for PyTorch and Taichi autodiff, not JAX. |
| D5 | **Tensorial Voigt** ordering: `[xx, yy, zz, xy, xz, yz]` with unscaled shears | Matches the existing Taichi codebase conventions. All generated code must use this ordering. |
| D6 | **Tension-positive** mean stress, **compression-positive** pressure | `m = (1/3) tr(σ)`, `p = -m`. Matches existing conventions. |
| D7 | Use **opt_einsum** for compile-time contraction path optimisation with a **JIT budget counter** as guardrail | opt_einsum finds optimal pairwise contraction order (up to 46x FLOP reduction). Budget counter classifies each step into Tier 1 (native `ti.Matrix @`), Tier 2 (emitted `ti.static` loops), or Tier 3 (runtime fallback). Physics indices (≤6) are unrolled; mesh indices (nodes, quads, elements) are always runtime loops. Max 512 unrolled lines per `@ti.func`, 2000 per `@ti.kernel`. |
| D8 | **Linear solver imported** (initially from existing Taichi implementation, later from `algo2code`-generated code) | The project does not hand-implement CG/PCG/GMRES. Initially, the user's existing Taichi linear solver library is imported via an adapter (Plan A, A1.3). Once `algo2code` is ready, the solver is transpiled from LaTeX algorithm boxes (`solvers/pcg.tex` → `_pcg_taichi.py`) and replaces the external dependency. In both cases the Newton-Raphson driver consumes the solver through the same `LinearSolverInterface`. See `11-ALGO2CODE.md §1.1`. |
| D9 | **Taichi is the sole backend until v1.0** | All compiler development focuses on Taichi. Backend-neutral IR ensures MFEM/MOOSE can be added later, but no C++ code generation is built until MVP is solid. |
| D10 | **Explicit intermediate representations** (Mechanics IR, Element IR, Einsum IR) | Symbolic weak forms do not emit backend code directly. All information flows through three named IRs to enable inspection, regression testing, and clean separation of concerns. |

---

## 5  Document index

| Document | Contents |
|----------|----------|
| `01-ARCHITECTURE.md` | System architecture, layer responsibilities, data flow, artifact bundle, runtime API |
| `02-LATEX-DSL.md` | LaTeX frontend grammar, all `% mechanics` directives, NRPyLaTeX fork specification |
| `03-SYMBOLIC-ENGINE.md` | SymPy tensor IR, SymPDE integration, constitutive auto-differentiation |
| `04-MECHANICS-IR.md` | Mechanics IR: semantic center of the compiler, ProblemIR schema, validation |
| `05-ELEMENT-IR.md` | Element IR: FE execution model, basis/quadrature/geometry, FE localisation |
| `06-CODEGEN.md` | Taichi backend: code generation, kernel emission, scheduling, performance |
| `07-CONVENTIONS.md` | All tensor conventions, Voigt/Mandel maps, index rules, sign conventions. Single source of truth. |
| `08-VERIFICATION.md` | V&V strategy: compiler-pass tests, handwritten baselines, physical benchmarks |
| `09-EINSUM-OPTIMISER.md` | opt_einsum integration, JIT budget counter, tier classification, template evolution |
| `10-BOUNDARIES.md` | Boundary mapping, Dirichlet/Neumann enforcement, region model, runtime binding |
| `11-ALGO2CODE.md` | `algo2code` transpiler: LaTeX algorithm boxes (algpseudocode) → executable solver code |
| `PLAN-A.md` | Implementation Plan A: Setup → MVP (10 phases, 10–14 weeks) |
| `PLAN-B.md` | Implementation Plan B: MVP → Full hyperelastic-viscoplastic TL+UL (9 phases, 12–18 weeks) |

---

## 6  Terminology

| Term | Meaning |
|------|---------|
| **Directive** | A `% mechanics ...` line in the LaTeX source, consumed by the DSL, invisible to pdflatex |
| **Mechanics IR** | The semantic intermediate representation: `ProblemIR` with fields, material, BCs, residual |
| **Element IR** | The FE execution model: cell type, basis, quadrature, local force/tangent expressions |
| **Einsum IR** | The normalised contraction layer: einsum strings + `ContractionPlan` from opt_einsum |
| **TerminalExpr** | SymPDE's expansion of an abstract variational form into component-wise spatial derivatives |
| **Printer** | A SymPy-style code emitter that walks expression trees and outputs target-language source |
| **TL** | Total Lagrangian formulation (reference configuration) |
| **UL** | Updated Lagrangian formulation (current configuration) |
| **SVK** | St. Venant-Kirchhoff — the TL equivalent of Hooke's law |
| **CPP** | Closest-Point Projection — the radial return algorithm for J2 plasticity |

---

## 7  Dependencies

| Package | Version | Role | License |
|---------|---------|------|---------|
| `nrpylatex` | 1.4+ (forked) | LaTeX parser | BSD-2-Clause |
| `sympde` | 0.19+ | Variational forms | MIT |
| `sympy` | 1.12+ | Symbolic math | BSD-3-Clause |
| `opt_einsum` | 3.3+ | Contraction path optimisation | BSD-3-Clause |
| `taichi` | 1.7+ | GPU compute backend | Apache-2.0 |
| `numpy` | 1.24+ | Numerical arrays | BSD-3-Clause |

Optional (verification only):

| Package | Version | Role | License |
|---------|---------|------|---------|
| `torch` | 2.0+ | AD verification backend | BSD-3-Clause |

---

## 8  Supported-subset contract

The compiler **explicitly rejects** unsupported constructs rather than silently approximating them. This is a safety-critical design choice: a wrong FEM result with no error message is far worse than a clear rejection.

### 8.1  Supported in MVP

- 3D problems (`dim 3`)
- Hex8 elements (`cell hex8`)
- Total Lagrangian kinematics (`kinematics total_lagrangian`)
- Convected coordinates (Cartesian reference configuration for MVP)
- St. Venant-Kirchhoff elasticity
- J2 plasticity with power-law isotropic hardening
- H1 vector displacement field
- Dirichlet and Neumann boundary conditions
- Static and quasi-static loading (Newton-Raphson)
- Imported linear solver interface

### 8.2  Explicitly unsupported in MVP (rejected with error)

| Construct | Error message |
|-----------|--------------|
| `dim 2` | "2D problems are not yet supported. MVP requires dim=3." |
| `cell tri3`, `cell tet4`, etc. | "Only hex8 elements are supported in MVP. Got: {cell_type}" |
| `kinematics small_strain` | "Small-strain kinematics not yet supported. Use total_lagrangian." |
| `kinematics updated_lagrangian` | "Updated Lagrangian formulation is planned for Plan B phase B1." |
| `constitutive neo_hookean`, `constitutive mooney_rivlin`, etc. | "Constitutive model '{model}' not yet supported. MVP supports: hooke_power_law" |
| Mixed function spaces | "Mixed spaces are not supported." |
| Higher-order elements | "Higher-order elements (Tet10, Hex20) are planned for Plan B phase B5." |
| Explicit dynamics | "Explicit dynamics is planned for Plan B phase B7." |
| MFEM/MOOSE backend targets | "Only Taichi backend is supported until v1.0." |

### 8.3  Implementation

Rejection checks run during Mechanics IR construction (see `04-MECHANICS-IR.md §5`). The error includes: the unsupported construct, the line in the LaTeX source, and a pointer to which plan phase adds support.

---

## 9  Project phases

### Plan A — Setup → MVP (Hex8 TL elasto-plastic with convected coordinates)

| Phase | Deliverable | Status |
|-------|-------------|--------|
| **A1** | Repository scaffolding, uv packaging, CI, Taichi solver import | Planned |
| **A2** | Handwritten Taichi Hex8 reference kernels (elastic + plastic baselines) | Planned |
| **A3** | NRPyLaTeX fork: two-point tensors, `% mechanics` directive parser | Planned |
| **A4** | Symbolic engine: kinematics (F→C→E→J), SVK + power-law J2, Voigt | Planned |
| **A5** | Mechanics IR + Element IR: FE localisation, IR validation | Planned |
| **A6** | opt_einsum integration + JIT budget counter | Planned |
| **A7** | Taichi codegen: Hex8 element kernel, B-matrix, internal forces, convected coords | Planned |
| **A8** | Newton-Raphson driver (TL), BC application, mesh I/O | Planned |
| **A9** | J2 plasticity: radial return, algorithmic tangent, history variables | Planned |
| **A10** | MVP integration + verification (patch test, Cook's membrane, necking bar) | Planned |

### Plan B — MVP → Full hyperelastic-viscoplastic TL+UL

| Phase | Deliverable | Status |
|-------|-------------|--------|
| **B1** | Updated Lagrangian formulation, Eulerian tangent, objective rates | Planned |
| **B2** | Full convected coordinate framework (Christoffel, covariant derivatives) | Planned |
| **B3** | Viscoplasticity: Perzyna, Johnson-Cook, consistent tangent | Planned |
| **B4** | Advanced hyperelasticity: Mooney-Rivlin, Ogden, HGO (anisotropic) | Planned |
| **B5** | Additional elements: Tet10, Hex20, reduced integration + hourglass | Planned |
| **B6** | Damage: Lemaitre CDM, phase-field degradation coupling | Planned |
| **B7** | Explicit dynamics driver (central difference, lumped mass) | Planned |
| **B8** | MFEM and MOOSE backend printers | Planned |
| **B8b** | Contraction template tuning (tier → named template families) | Planned |
| **B9** | Full V&V suite: MMS convergence, cross-backend comparison | Planned |
