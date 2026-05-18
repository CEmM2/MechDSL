# Phase 2 Context Summary: Cook's Membrane -- Trapezoidal Mesh & J2 Benchmark

**Plan:** `dev/plans/sprint3.md`
**Original plan phase name:** Phase 2

## Conventions
- Cook's membrane geometry: trapezoidal, x in [0,48], left height=44, right height=16, thickness=1
- Y-coordinate warping: y_warped = y * (44 - 28*x/48) / 44
- Material: E=240.565 MPa, nu=0.3, sigma_y0=243.0 MPa, K=300.0 MPa, n=0.4
- HexMesh dataclass with boundary_tags dict for face identification

## Key Principles
- nu=0.3 chosen to avoid volumetric locking (literature uses nu=0.4999 which locks with standard Hex8)
- Self-converged fine-mesh reference compensates for material parameter deviation from literature
- 2% tolerance is against our own converged reference, not absolute literature value

## Pre-resolved Design Decisions
- Use coordinate warping of structured mesh (not unstructured meshing)
- Use nu=0.3 (not 0.4999) -- B-bar/F-bar out of MVP scope
- Reference generated from fine mesh (e.g. 16x16x1) using same solver
- J2 solve via solve_plastic from ref_hex8_plastic.py with 10 load steps

## Allowed Deviations
- None explicitly stated

## Downstream Impact
- generate_cook_membrane_mesh is reused by P5-2 (example scripts)
- Cook's benchmark test contributes to Phase 4 e2e collection
