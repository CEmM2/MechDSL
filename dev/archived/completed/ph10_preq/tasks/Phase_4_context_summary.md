# Phase 4 Context Summary: Elastic Benchmark Solver Layer

**Plan:** `dev/plans/ph10_preq.md`
**Original plan phase name:** E2 Elastic Benchmark Solver Layer

## Must Know

- This phase creates the internal elastic solve surface for cantilever work only.
- Do not expose the public cantilever runner in this phase.
- Support TL/UL, SVK/Neo-Hookean, and Hex8/Tet10/Hex20.
- Do not change frontend, codegen, or constitutive model semantics.

## Should Know

- Validate TL/UL small-displacement agreement before broader matrix work.
- Capture candidate runtime data so the public cantilever phase can set smoke and nightly budgets honestly.

## Allowed Deviations

- None. If a matrix cell is too expensive, record runtime evidence and keep the public test split for the next phase.

## Downstream Impact

- Completion unlocks the public cantilever benchmark API and matrix tests.

