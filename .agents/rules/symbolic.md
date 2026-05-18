---
paths:
  - "packages/mechdsl-core/src/mechdsl/symbolic/**"
---

# Symbolic Engine Rules

## Constitutive model classes

Not all constitutive models are hyperelastic, so the derivation strategy depends on the model class.

### Hyperelastic models

For SVK, neo-Hookean, Mooney-Rivlin, Ogden, HGO, and similar models:

- Derive PK2 stress and the material tangent through `sympy.diff` of the strain energy.
- Use `S_IJ = dPsi / dE_IJ`.
- Use `C_IJKL = d2Psi / dE_IJ dE_KL`.

### Dissipative models

For J2 plasticity, viscoplasticity, damage, and similar models:

- Stress and tangent come from the algorithmic update, not from a scalar energy.
- The tangent is the algorithmic consistent tangent from the return mapping.
- Symbolic differentiation may help with subexpressions, but never force a strain-energy formulation on a dissipative model.

## General rules

- Every model must produce PK2 stress and a material tangent.
- Use tensorial Voigt ordering `[xx, yy, zz, xy, xz, yz]` with unscaled shears.
- Kinematics must produce `F`, `C`, `E`, `J`, and the convected metric `g_IJ = C_IJ`.
- Keep symbolic expressions in SymPy symbols; do not substitute numbers during symbolic construction.

