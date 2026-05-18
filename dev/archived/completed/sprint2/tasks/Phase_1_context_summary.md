# Phase 1 Context Summary — Convected Coordinates & Codegen Bug Fixes

## Conventions
- **Index convention**: lowercase `i,j,k,l` = spatial; uppercase `I,J,K,L` = material; mixed `F_{iI}` = two-point tensor (07-CONVENTIONS.md)
- **Voigt ordering**: `[xx, yy, zz, xy, xz, yz]` with unscaled shears
- **Lamé parameters**: λ = Eν/((1+ν)(1-2ν)), μ = E/(2(1+ν))
- **Convected metric**: g_IJ = C_IJ = F^T F for Cartesian reference (06-CODEGEN.md §8)
- **Green-Lagrange strain**: E_IJ = 0.5*(g_IJ - G_IJ) where G_IJ = δ_IJ for Cartesian

## Key Principles
- `symbolic/kinematics.py` already computes `g = C` (line 54) — convected.py formalizes the convected interpretation without duplicating computation
- Unsupported constructs must raise `UnsupportedError` with pointer to the Plan B phase that adds support (per `ir.md` rules)
- Golden files must be regenerated after any emission change — diff must be reviewed before committing

## Pre-resolved Design Decisions
- **emit_main bug fix** (P1-T1): The fix adds E/nu → Lamé conversion at line 810 of `taichi_printer.py`. When `params.get('lam')` is None but `params['E']` and `params['nu']` exist, compute and emit the correct Lamé values
- **Convected coordinate scope** (P1-T2): MVP only supports Cartesian reference (G_IJ = δ_IJ). Non-Cartesian raises `UnsupportedError("Curvilinear reference planned for Plan B phase B2")`
- **convected.py uses SymPy matrices** (consistent with kinematics.py)

## Downstream Impact
- **P1-T1 fix** enables correct `__main__` block in generated solvers for E/nu materials — required by Phase 4 J2 E2E test
- **P1-T5 golden regeneration** changes the golden file baseline — all subsequent golden comparisons use the new baseline
- **P1-T2/T3 convected functions** satisfy test ID S9 from 08-VERIFICATION.md — needed by Phase 5 audit
- **P1-T4 exports** enable `from mechdsl.symbolic import compute_reference_metric` in downstream code

## Key Files
- `packages/mechdsl-core/src/mechdsl/codegen/taichi_printer.py` — emit_main() at line 810
- `packages/mechdsl-core/src/mechdsl/symbolic/convected.py` — currently a 1-line stub
- `packages/mechdsl-core/src/mechdsl/symbolic/kinematics.py` — reference for g = C pattern (line 54)
- `packages/mechdsl-core/tests/generate_golden.py` — golden file regeneration script
