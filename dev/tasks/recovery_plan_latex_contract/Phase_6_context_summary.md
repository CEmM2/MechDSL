# Phase 6 Context Summary: Integrate `algo2code` at the least risky seam (R5)

**Plan:** `dev/plans/recovery_plan_latex_contract.md`
**Original plan phase name:** Integrate `algo2code` at the least risky seam (R5)

## Goal
Recover the intended monorepo relationship incrementally.

## Why this phase
`algo2code` is already useful; the right move is to connect it at the safest planned seam, not to force deep replacement immediately.

## Code reality anchor (2026-04-26)
- `solver/import_adapter.py:26-57` defines `LinearSolverInterface` (Protocol) plus `CGSolver` and `PCGSolver` concrete adapters.
- `algo2code` is a sibling package with its own pipeline (`algo_parser → expr_parser → type_inference → backends/taichi_codegen`).
- The mismatch this phase corrects: there are zero `algo2code` imports anywhere under `packages/mechdsl-core/src/`, so the monorepo relationship is design-doc only — no actual integration seam exists yet.

## Required constraints
- Do not merge package boundaries.
- Do not replace the current J2 implementation in the first integration wave.
- Keep `algo2code` runtime-independence intact.

## Cross-phase dependencies
This phase blocks: — (no later phase depends on `algo2code` integration on the stable path).
This phase is blocked by: P4-1 (P6-1 needs the enriched ElementIR before wiring the PCG seam).

## Exit criteria
- One real, low-risk integration point exists.
- The monorepo relationship is architectural reality, not only design-doc intent.
- The generated PCG path remains optional until proven stable.

## Tasks in this phase
- **P6-1** (R5.1, tier=integration): Add an optional `algo2code`-generated PCG path behind `LinearSolverInterface`.
- **P6-2** (R5.2, tier=unit): Keep the current imported solver path as the default fallback until generated PCG is stable.
- **P6-3** (R5.3, tier=integration): Add a single stable integration test for `algo2code` → PCG → Newton solve plumbing.
- **P6-4** (R5.4, tier=docs): Defer radial-return replacement until frontend + IR alignment is settled.
- **P6-5** (R5.5, tier=docs): Document `algo2code`’s role in the recovered architecture to prevent renewed drift.
