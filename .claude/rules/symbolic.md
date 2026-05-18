---
paths:
  - "packages/mechdsl-core/src/mechdsl/symbolic/**"
---

# Symbolic Engine Rules

## Constitutive model classes

Not all constitutive models are hyperelastic. The derivation strategy depends on the model class:

### Hyperelastic models (SVK, neo-Hookean, Mooney-Rivlin, Ogden, HGO)

- Derive PK2 stress S and the material tangent C via `sympy.diff` of the strain energy Ψ.
- S_IJ = ∂Ψ/∂E_IJ, C_IJKL = ∂²Ψ/∂E_IJ∂E_KL.
- This is the correct and preferred approach for models possessing a stored energy function.

### Dissipative models (J2 plasticity, viscoplasticity, damage)

- Stress and tangent come from the **algorithmic update** (return mapping, consistency condition), not from differentiating a scalar energy.
- The tangent is the **algorithmic consistent tangent** (linearization of the return map), not ∂²Ψ/∂E².
- Symbolic differentiation may be used for *parts* of the derivation (yield function gradient, elastic predictor, normal to the yield surface) but not as the top-level "differentiate Ψ" pattern.
- Never force a strain-energy formulation onto a dissipative model.

## General rules

- Every model must produce both PK2 stress (S_IJ) and the material tangent (C_IJKL or C_alg).
- Voigt contraction uses the tensorial Voigt ordering from 07-CONVENTIONS.md — unscaled shears, [xx, yy, zz, xy, xz, yz].
- Kinematics must always produce: F, C, E, J, and the convected metric g_IJ = C_IJ.
- All symbolic expressions should be kept in terms of SymPy Symbols — do not substitute numerical values during symbolic construction.
