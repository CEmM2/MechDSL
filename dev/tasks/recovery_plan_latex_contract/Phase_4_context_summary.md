# Phase 4 Context Summary: Enrich `ElementIR` and normalize lowering boundaries (R3)

**Plan:** `dev/plans/recovery_plan_latex_contract.md`
**Original plan phase name:** Enrich `ElementIR` and normalize lowering boundaries (R3)

## Goal
Make the IR discipline true in practice, not just in naming.

## Why this phase
The current lowering/codegen contract works, but too much execution meaning is hidden in helper structures and printer knowledge.

## Code reality anchor (2026-04-26)
- `ir/element_ir.py:35-89` already carries basis/quadrature/integration metadata; the dataclass is frozen.
- `lowering/fe_localise.py:35-66` defines `EinsumSpec` and `LocalisationResult`, both frozen dataclasses, currently treated as primary semantic carriers downstream.
- The mismatch this phase corrects: `ElementIR` does not yet carry an explicit execution-contract block (geometry summary, material-eval contract, force/tangent descriptors), so `EinsumSpec` ends up doing semantic work it should not own.

## Required constraints
- Do not break existing optimizer work.
- Do not delete proven helper structures unless a richer replacement is already in place.
- Avoid backend-specific leakage into IR types.

## Cross-phase dependencies
This phase blocks: P5-4, P7-2.
This phase is blocked by: P3-1.

## Exit criteria
- `ElementIR` carries explicit execution semantics.
- Lowering produces semantically rich IR before optimizer views.
- Artifact bundling reflects the intended IR hierarchy more faithfully.

## Tasks in this phase
- **P4-1** (R3.1, tier=integration): Add structured execution-contract fields to `ElementIR` (geometry summary, material-eval contract, local force/tangent descriptors).
- **P4-2** (R3.2, tier=unit): Keep `EinsumSpec` and `LocalisationResult`, but demote them to derived/optimization views rather than the primary semantic carrier.
- **P4-3** (R3.3, tier=regression): Rework lowering so it emits richer `ElementIR` first, then derives contraction/optimizer artifacts from it.
- **P4-4** (R3.4, tier=integration): Make unsupported stable-path combinations fail in lowering with clear phase-scoped guidance.
- **P4-5** (R3.5, tier=unit): Update artifact bundling to reflect enriched IR ownership cleanly.
