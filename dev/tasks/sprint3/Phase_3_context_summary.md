# Phase 3 Context Summary: Necking Bar -- MVP Acceptance Test

**Plan:** `dev/plans/sprint3.md`
**Original plan phase name:** Phase 3 (CRITICAL PATH -- MVP acceptance criterion)

## Conventions
- Quarter-model symmetry: [0,L/2]x[0,W/2]x[0,W/2] with symmetry BCs on z0, x0, y0
- Geometric imperfection: smooth taper reducing cross-section at z=L/2 by imperfection*W
- Displacement-controlled loading: prescribed u_z on z1 face, 20 load steps
- Load-displacement curve: reaction force at z=0 vs prescribed displacement at z=L/2

## Key Principles
- Rectangular bar (not cylindrical) is valid for necking and avoids cylindrical mesh complexity
- Self-converged reference avoids copyright issues with Simo & Hughes (1998) figure digitization
- 2% tolerance validates generated solver matches reference solver implementation
- Necking onset requires geometric imperfection to localize deformation

## Pre-resolved Design Decisions
- Rectangular bar mesh, not cylindrical
- Self-converged reference from fine mesh (e.g. 8x8x32) using ref_hex8_plastic.py
- Material parameters chosen to produce clear necking response
- Reference stored in tests/golden/necking_bar_reference.npz

## Allowed Deviations
- Material parameters may be adjusted from Simo & Hughes values if needed for convergence

## Downstream Impact
- This is the MVP acceptance criterion -- Sprint 3 cannot be declared done without this passing
- generate_necking_bar_mesh reused by P5-2 (example scripts)
- Reference data stored as golden file for future regression testing
