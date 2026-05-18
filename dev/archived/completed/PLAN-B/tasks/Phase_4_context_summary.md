# Phase 4 Context Summary: Advanced hyperelasticity

**Plan:** `dev/design_docs/PLAN-B.md`
**Original plan phase name:** B4 Advanced hyperelasticity

## Conventions

- All models use the isochoric-volumetric split: `Ψ = Ψ_iso(C_bar) + Ψ_vol(J)` where `C_bar = J^(-2/3) C` is the modified right Cauchy-Green and `J = det(F)` is the Jacobian.
- PK2 stress from `S = 2 ∂Ψ/∂C` analytically via SymPy-derived closed forms; the generated code does NOT rely on AD at runtime.
- Material tangent via `C = 4 ∂²Ψ/∂C∂C`, also derived analytically.

## Key Principles

- **Every hyperelastic model must have both a symbolic PK2 and an AD oracle check.** Per the symbolic engine rules (`.claude/rules/symbolic.md`), hyperelastic models derive stress and tangent from Ψ via SymPy differentiation. AD oracle verifies the hand-derived closed form against PyTorch/Taichi autodiff on 100 random states.
- **Uniaxial closed-form reduction is a regression guard.** For each model there is a 1D stretch-stress curve (from rubber-elasticity textbooks) that the 3D implementation must reproduce when constrained to λ_2 = λ_3 = λ^(-1/2).
- **Ogden must handle repeated eigenvalues.** When two principal stretches are within 1e-6, apply the L'Hôpital limit formulas from Holzapfel §6.5. Silent divide-by-zero here is a HIGH-risk bug.
- **HGO fibers are per-element data**, not material constants. The `fiber_data` kwarg on `build_context` takes an (n_elem, 2, 3) array — two unit fiber directions per element.
- **Compressive fibers don't contribute.** HGO fiber terms are gated on I_4 > 1 (stretched) to prevent buckling artefacts in compression.

## Pre-resolved Design Decisions

- Neo-Hookean uses the classical form `Ψ = (μ/2)(I1_bar − 3) + (κ/2)(J − 1)²` — not the Simo-Taylor form. Document the form in the module docstring.
- Mooney-Rivlin with `C2 = 0` must reduce exactly to Neo-Hookean with `μ = 2 C1`. Regression test.
- Ogden eigendecomposition uses `numpy.linalg.eigh` (symmetric) — NOT `numpy.linalg.eig` (general). Symmetric eigh is stable and fast for 3x3.
- Fiber directions are unit vectors. The material dataclass validates `||a|| == 1` to 1e-8 at construction.

## Allowed Deviations

- Uniaxial closed-form tolerance is 1e-6, not 1e-10. The closed forms themselves are derived with finite algebraic simplification and carry ~1e-10 round-off; the 1e-6 margin absorbs that plus discretisation noise from the 3D solve.

## Downstream Impact

- **P10-2 cantilever matrix** uses Neo-Hookean as one of the two elastic models (alongside SVK).
- **P10-9 fiber strip benchmark** is HGO-specific.
- Phase 8 MFEM/MOOSE printers need to emit each of the four new hyperelastic models — the analytical stress/tangent closed forms must be portable to C++.
- Phase 6 damage does NOT extend to hyperelastic models in this plan; Lemaitre damage is coupled to plastic dissipation only.
