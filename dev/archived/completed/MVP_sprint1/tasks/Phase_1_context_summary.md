# Phase 1 Context Summary — Constitutive Base Class

## Conventions

- **Voigt ordering**: `[xx, yy, zz, xy, xz, yz]` with unscaled shears (tensorial Voigt, not engineering Voigt) — per `07-CONVENTIONS.md §2`
- **Tension-positive** stress, compression-positive pressure — per `07-CONVENTIONS.md §4`
- **float64** throughout all numerical computation
- **Index convention**: lowercase `i,j,k,l` = spatial; uppercase `I,J,K,L` = material
- Frozen dataclasses for immutable data structures
- Type hints encouraged (Python 3.12)

## Key Principles

- Per `.claude/rules/symbolic.md`: hyperelastic models (SVK) derive stress via `sympy.diff` of energy Ψ; dissipative models (J2) use algorithmic update (return mapping). **The ABC must accommodate both** — never force a strain-energy formulation onto a dissipative model.
- The ABC uses `**state` kwargs to allow flexible state variable passing without prescribing a specific container. SVK ignores state kwargs; J2 uses `alpha=...`.
- **All existing standalone functions MUST be preserved.** The ABC wrapper classes delegate to them; they do not replace them. The reference solvers (`tests/ref/`) and 687 existing tests call standalone functions directly.
- Per CLAUDE.md: "Don't add features, refactor code, or make 'improvements' beyond what was asked." Add only what the sprint plan specifies.

## Pre-resolved Design Decisions

- `ConstitutiveModel` is an ABC (not a Protocol) with 5 abstract methods: `pk2_stress`, `material_tangent`, `voigt_tangent`, `state_variables` (property), `is_dissipative` (property)
- SVK wrapper: `SVKModel(ConstitutiveModel)` in `svk.py`, wraps `SVKMaterial` + standalone functions
- J2 wrapper: `J2Model(ConstitutiveModel)` in `j2_power_law.py`, wraps `J2PowerLawMaterial` + `radial_return()`
- `fe_localise.py` update is minimal (~5 lines): add validation that model string maps to known subclass

## Downstream Impact

- Phase 4 (`compile()`) can optionally use the ABC for structural validation of material models
- Phase 5 (TaichiPrinter) does NOT need the ABC — it reads `bundle.problem_ir_dict["material"]["model"]` string
- Phase 6 (E2E) does NOT depend on the ABC
- Future models (neo-Hookean, Ogden, etc.) will inherit from `ConstitutiveModel`

## Key Files

| File | Current state | Action |
|------|--------------|--------|
| `src/mechdsl/symbolic/constitutive.py` | 1-line stub | → ~60 line ABC |
| `src/mechdsl/symbolic/models/svk.py` | 115 lines, standalone functions | Append ~30 lines (SVKModel class) |
| `src/mechdsl/symbolic/models/j2_power_law.py` | 335 lines, standalone functions | Append ~40 lines (J2Model class) |
| `src/mechdsl/lowering/fe_localise.py` | 263 lines | ~5 lines changed (model validation) |
| `tests/test_constitutive_abc.py` | Does not exist | New test file |
