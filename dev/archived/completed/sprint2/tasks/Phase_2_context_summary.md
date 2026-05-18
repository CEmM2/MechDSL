# Phase 2 Context Summary — Analytical Solutions & Frontend Stubs

## Conventions
- **Patch test**: constant strain field must be reproduced exactly (relative error < 1e-12) per 08-VERIFICATION.md §4.1
- **Rigid body**: zero internal force for any rigid body motion (force norm < 1e-12)
- **Cantilever**: Euler-Bernoulli tip deflection δ = PL³/(3EI) — small deformation theory
- **Uniaxial hardening**: σ = σ_y0 + K·ε_p^n with total strain decomposition ε_total = σ/E + ε_p
- **Frontend layer** produces a *context dict* (not ProblemIR) — ProblemIR construction is Layer 3's job
- **Supported-subset validation**: per ir.md, every rejection includes (1) unsupported construct, (2) LaTeX source line if available, (3) plan-phase pointer

## Key Principles
- `verify/analytical.py` provides ground truth references — these functions must be independently verifiable against hand calculations
- `frontend.build_context()` is a programmatic entry point that returns the same dict the LaTeX parser would produce
- The uniaxial_tension_hardening function is **critical for Phase 4** — the J2 E2E test compares against it

## Pre-resolved Design Decisions
- **build_context returns dict, not ProblemIR**: Layer separation — frontend (Layer 1) produces raw parsed data, IR (Layer 3) constructs ProblemIR
- **Uniaxial hardening uses implicit solve**: for σ = σ_y0 + K·ε_p^n, ε_p is found by solving f(ε_p) = σ_y0 + K·ε_p^n + E·ε_p - E·ε_total = 0 via Brent's method
- **Supported materials**: only "svk" and "j2_power_law" — matching ProblemIR.__post_init__ validation

## Downstream Impact
- **P2-T1 (patch_test_reference)** → used by Phase 3 run_patch_test() (P3-T4)
- **P2-T2 (rigid_body_reference)** → used by Phase 3 run_rigid_body_test() (P3-T4)
- **P2-T4 (uniaxial_tension_hardening)** → used by Phase 4 test_e2e_plastic.py (P4-T5) for hardening curve validation
- **P2-T8 (frontend tests)** → covers test IDs P1, P2, P5, P6 for Phase 5 audit

## Key Files
- `packages/mechdsl-core/src/mechdsl/verify/analytical.py` — currently a 1-line stub
- `packages/mechdsl-core/src/mechdsl/frontend/__init__.py` — currently a 1-line stub
- `packages/mechdsl-core/src/mechdsl/ir/mechanics_ir.py` — ProblemIR validation (reference for build_context)
- `dev/design_docs/08-VERIFICATION.md` — test ID definitions
