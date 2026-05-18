# Phase 5 Context Summary: Additional elements and integration rules

**Plan:** `dev/design_docs/PLAN-B.md`
**Original plan phase name:** B5 Additional elements and integration rules

## Conventions

- New `ElementType` values: `TET4`, `TET10`, `HEX20` (in addition to the existing `HEX8`).
- New `IntegrationRule` enum: `FULL` (default) and `REDUCED`. Hourglass schemes: `None` or `FLANAGAN_BELYTSCHKO`.
- Tet elements use barycentric / volume-coordinate shape functions; hex elements use (ξ, η, ζ) natural coordinates. Do not mix the two in a single module.
- Quadrature-point arrays (`SHAPE_AT_QUAD`, `GRAD_AT_QUAD`, `QUAD_WEIGHTS`) are emitted per-element-type in dedicated `*_tables.py` files in `codegen/`.

## Key Principles

- **Patch test is the universal acceptance bar.** Every new element must reproduce a constant-strain state exactly (< 1e-12) on an irregular mesh of that element type. No exceptions.
- **Reduced integration is unstable without hourglass control.** Reduced Hex8 alone is a broken element; always pair with Flanagan-Belytschko. The ElementFactory raises a warning if you skip hourglass control on reduced Hex8.
- **Hourglass force is zero on constant-strain states.** The control must suppress zero-energy modes, not add energy to legitimate deformations. Verify on a constant strain test.
- **JIT budget matters more for high-order elements.** Hex20 with 27 quadrature points can easily exceed 512 unrolled lines per `@ti.func`; restructure into sub-functions when it does.
- **Tet4 is an incompressibility trap.** Linear tets lock volumetrically as ν → 0.5. Document this in the module docstring; defer F-bar / B-bar mitigation to a post-MVP task.

## Pre-resolved Design Decisions

- The ElementFactory API is fixed for the lifetime of Plan B: `ElementFactory.create(topology, integration='full', hourglass=None)`. Downstream tasks depend on this signature; breaking changes cascade.
- Tet10 uses a standard symmetric 4-point Gauss quadrature. The specific barycentric coordinates come from Zienkiewicz §5.
- Hex20 uses 3×3×3 = 27-point Gauss. 2×2×2 (8-point) is NOT adequate for quadratic serendipity — the quadrature must integrate the full stiffness exactly.
- Flanagan-Belytschko uses the classical 1981 formulation. Hourglass coefficient `lambda_h` defaults to 0.05 and is user-tunable via `hourglass_coef`.
- LaTeX directive extension: `% mechanics cell hex8 --integration reduced --hourglass flanagan_belytschko` — the `--integration` and `--hourglass` flags are added in P5-6.

## Allowed Deviations

- Tet4 on an incompressible material (ν > 0.48) may fail the patch test. This is expected behaviour from volumetric locking and is documented, not a bug.

## Downstream Impact

- **Phase 9 (template tuning)** consumes the full matrix of elements plus the backends from Phase 8. Phase 9 blocks until Phase 5 AND Phase 8 are complete.
- **P10-7 Taylor impact** needs reduced Hex8 + hourglass control — the full Phase 5 output.
- **P10-2 cantilever matrix** and **P10-3 Cook's membrane matrix** parametrise over Tet10 / Hex20; Phase 5 must expose them through build_context.
