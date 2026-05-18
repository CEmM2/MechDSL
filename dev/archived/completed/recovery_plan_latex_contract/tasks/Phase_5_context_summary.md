# Phase 5 Context Summary: Re-anchor Taichi codegen as the stable path (R4)

**Plan:** `dev/plans/recovery_plan_latex_contract.md`
**Original plan phase name:** Re-anchor Taichi codegen as the stable path (R4)

## Goal
Preserve codegen assets while making the stable contract unambiguous.

## Why this phase
The stable path should be recoverable without deleting experimental backend work.

## Code reality anchor (2026-04-26)
- `codegen/__init__.py:10-20` exposes `compile(problem_ir) -> ArtifactBundle`; `taichi_printer.py:20-80` uses an `EmissionContext` class.
- `codegen/mfem_printer.py` and `codegen/moose_printer.py` exist alongside the Taichi printer; nothing in code or docs currently labels them experimental.
- The mismatch this phase corrects: there are no module-level `emit*` functions in `taichi_printer.py` (contrary to the drift report's wording), so a thin façade may be needed; and the experimental backends still sit on the same surface as the stable Taichi path.

## Required constraints
- Keep existing backend code in-tree.
- Do not allow experimental backend status to block stable-path verification.
- Do not widen the stable backend set during recovery.

## Cross-phase dependencies
This phase blocks: P7-2, P7-5.
This phase is blocked by: P2-1, P3-1, P4-1 (only P5-4 needs all three; the rest are independent).

## Exit criteria
- Taichi is clearly the stable path again.
- Experimental backend code is preserved but no longer defines the public contract.
- Codegen tests reflect this distinction.

## Tasks in this phase
- **P5-1** (R4.1, tier=docs): Define Taichi as the only stable backend for the canonical LaTeX compile path.
- **P5-2** (R4.2, tier=docs): Mark MFEM/MOOSE printers as experimental backend surfaces.
- **P5-3** (R4.3, tier=unit): Add a small façade layer if needed to present codegen in the design-doc style while preserving current emitters.
- **P5-4** (R4.4, tier=unit): Ensure the Taichi path consumes enriched IR data where available rather than relying primarily on implicit summaries.
- **P5-5** (R4.5, tier=regression): Split codegen verification into stable vs experimental suites.
