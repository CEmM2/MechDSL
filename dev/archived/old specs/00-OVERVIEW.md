# CompMech DSL — Specification Suite

**Version:** 0.1 (Proof-of-Concept)  
**Status:** Draft  
**Date:** March 2026

---

## 1  Project statement

CompMech DSL is a domain-specific language for computational mechanics that lets researchers write constitutive models and boundary-value problems in LaTeX notation and obtain working finite element solvers as output. The pipeline is:

```
LaTeX source  →  symbolic tensors (SymPy)  →  variational forms (SymPDE)  →  solver code (Taichi / MFEM / MOOSE)
```

The user writes a `.tex` file containing both their equations (rendered normally by pdflatex) and embedded `% mechanics` directives (ignored by LaTeX, consumed by the DSL). The DSL produces a correct, tested FEM implementation — no hand-coding of element routines.

---

## 2  Scope

### In scope

- 2D and 3D continuum mechanics (small and large deformation)
- Constitutive models: isotropic/anisotropic hyperelasticity, J2 plasticity with hardening, continuum damage
- Linear and nonlinear FEM with Newton-Raphson
- Explicit and implicit time integration
- Code generation targeting Taichi, MFEM, and MOOSE
- Verification against analytical solutions and method of manufactured solutions

### Out of scope (for now)

- Beam, shell, and plate elements
- Multi-physics coupling (thermal, fluid)
- Contact mechanics (future phase)
- Mesh generation (external tool)
- Adaptive mesh refinement

---

## 3  Design decisions

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
| D8 | **Linear solver imported** from existing Taichi implementation | The project does not reimplement CG/PCG/GMRES. The user's existing Taichi linear solver library is imported and called by generated Newton-Raphson drivers. |

---

## 4  Document index

| Document | Contents |
|----------|----------|
| `01-ARCHITECTURE.md` | System architecture, layer responsibilities, data flow, dependency map |
| `02-LATEX-DSL.md` | LaTeX frontend grammar, all `% mechanics` directives, NRPyLaTeX fork specification |
| `03-SYMBOLIC-ENGINE.md` | SymPy tensor IR, SymPDE integration, constitutive auto-differentiation |
| `04-CONSTITUTIVE.md` | Material model library: hyperelastic, plastic, damage. Mathematical definitions, algorithmic tangents |
| `05-WEAK-FORMS.md` | Variational formulations (TL, UL, Eulerian), linearisation for Newton, SymPDE mapping |
| `06-CODEGEN.md` | Code generation backends: Taichi, MFEM, MOOSE. Element kernels, solver scaffolding |
| `07-CONVENTIONS.md` | All tensor conventions, Voigt/Mandel maps, index rules, sign conventions. Single source of truth. |
| `08-VERIFICATION.md` | V&V strategy: analytical benchmarks, MMS, patch tests, convergence studies |
| `09-EINSUM-OPTIMISER.md` | opt_einsum integration, JIT budget counter, tier classification, index partitioning |

---

## 5  Terminology

| Term | Meaning |
|------|---------|
| **Directive** | A `% mechanics ...` line in the LaTeX source, consumed by the DSL, invisible to pdflatex |
| **IR** | Intermediate representation — the SymPy `Indexed` / `IndexedSymbol` tensors emitted by the parser |
| **TerminalExpr** | SymPDE's expansion of an abstract variational form into component-wise spatial derivatives |
| **Printer** | A SymPy-style code emitter that walks a symbolic expression tree and outputs target-language source |
| **CST** | Constant Strain Triangle — the simplest 2D element, used in the PoC |
| **TL / UL** | Total Lagrangian / Updated Lagrangian formulation |
| **CPP** | Closest-Point Projection — the radial return algorithm for J2 plasticity |

---

## 6  Dependencies

| Package | Version | Role | License |
|---------|---------|------|---------|
| `nrpylatex` | 1.4+ (forked) | LaTeX parser | BSD-2-Clause |
| `sympde` | 0.19+ | Variational forms | MIT |
| `sympy` | 1.12+ | Symbolic math | BSD-3-Clause |
| `opt_einsum` | 3.3+ | Contraction path optimisation | BSD-3-Clause |
| `taichi` | 1.7+ | GPU compute backend | Apache-2.0 |
| `numpy` | 1.24+ | Numerical arrays | BSD-3-Clause |

Optional (verification only):
| `torch` | 2.0+ | AD verification backend | BSD-3-Clause |

---

## 7  Project phases

### Plan A — Setup → MVP

| Phase | Deliverable | Status |
|-------|-------------|--------|
| **P0** | PoC: LaTeX → SymPy → SymPDE → NumPy/Taichi linear elasticity solver | **Done** |
| **A1** | Repository scaffolding, uv packaging, CI, Taichi solver import | Planned |
| **A2** | NRPyLaTeX fork: two-point tensors, `% mechanics` directive parser | Planned |
| **A3** | Symbolic engine: kinematics (F→C→E→J), neo-Hookean (Ψ→S→ℂ), Voigt | Planned |
| **A4** | opt_einsum integration + JIT budget counter | Planned |
| **A5** | Taichi codegen: Hex8 element kernel, B-matrix, internal forces | Planned |
| **A6** | Newton-Raphson driver (TL), BC application, mesh I/O | Planned |
| **A7** | J2 plasticity: radial return, algorithmic tangent, history variables | Planned |
| **A8** | MVP integration + verification (patch test, Cook's membrane, necking bar) | Planned |

### Plan B — MVP → Full hyperelastic-viscoplastic TL+UL

| Phase | Deliverable | Status |
|-------|-------------|--------|
| **B1** | Updated Lagrangian formulation, Eulerian tangent, objective rates | Planned |
| **B2** | Convected coordinate framework, metric tensors, Christoffel symbols | Planned |
| **B3** | Viscoplasticity: Perzyna, Johnson-Cook, consistent tangent | Planned |
| **B4** | Advanced hyperelasticity: Mooney-Rivlin, Ogden, HGO (anisotropic) | Planned |
| **B5** | Additional elements: Tet10, Hex20, reduced integration + hourglass | Planned |
| **B6** | Damage: Lemaitre CDM, phase-field degradation coupling | Planned |
| **B7** | Explicit dynamics driver (central difference, lumped mass) | Planned |
| **B8** | MFEM and MOOSE backend printers | Planned |
| **B9** | Full V&V suite: MMS convergence, cross-backend comparison | Planned |
