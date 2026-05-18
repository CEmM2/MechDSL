# Phase 3 Context Summary: Enrich `ProblemIR` into the semantic center again (R2)

**Plan:** `dev/plans/recovery_plan_latex_contract.md`
**Original plan phase name:** Enrich `ProblemIR` into the semantic center again (R2)

## Goal
Move semantics back into the mechanics IR without breaking current consumers.

## Why this phase
Once the front door is canonical again, the next requirement is to make the semantic center real rather than implied.

## Code reality anchor (2026-04-26)
- `ir/mechanics_ir.py:113` is `@dataclass(frozen=True)`; the existing `ProblemIR` field list runs roughly `:210-219`.
- `BoundaryCondition.to_dict/from_dict` exist (`mechanics_ir.py:124-145`) and `MaterialSpec.to_dict/from_dict` exist (`:155-168`); however `ProblemIR` itself has no `to_dict/from_dict`.
- The mismatch this phase corrects: P3-1's "round-trip tests" requires a `ProblemIR.to_dict/from_dict` pair which does not yet exist — that infrastructure must be built as part of P3-1, not assumed.

## Required constraints
- Backward compatibility is mandatory for the initial enrichment pass.
- `ProblemIR` remains an immutable dataclass-based surface.
- Do not push transient optimizer or printer-specific details into `ProblemIR`.

## Cross-phase dependencies
This phase blocks: P4-1, P4-3, P5-4.
This phase is blocked by: P2-1.

## Exit criteria
- `ProblemIR` can carry the semantic minimum promised by the design docs.
- Existing consumers remain functional via adapters.
- More semantics are validated at IR-construction time.

## Tasks in this phase
- **P3-1** (R2.1, tier=integration): Add optional semantic fields to `ProblemIR`: `fields`, `domain`, `mesh_contract`, `residual_contract`.
- **P3-2** (R2.2, tier=unit): Add compatibility constructors/adapters from the current thin representation.
- **P3-3** (R2.3, tier=regression): Move boundary/domain assumptions out of scattered runtime/codegen logic and into IR metadata where possible.
- **P3-4** (R2.4, tier=unit): Define a stable `ProblemIR` minimal subset for the MVP-stable contract.
- **P3-5** (R2.5, tier=integration): Add targeted IR validation for semantics that were previously implicit.
