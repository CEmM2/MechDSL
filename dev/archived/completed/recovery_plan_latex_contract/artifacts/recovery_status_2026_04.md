# Recovery Status Note — LaTeX Compiler Contract

**Date authored:** 2026-04-29
**Authored by:** recovery_plan_latex_contract Phase 7 task P7-4
**Companion documents:**
[`drift_20_04.md`](drift_20_04.md) (the diagnosis),
[`../plans/recovery_plan_latex_contract.md`](../plans/recovery_plan_latex_contract.md) (the prescription),
[`frontend_drift_history.md`](frontend_drift_history.md) (the historical drift record).

## One-line summary

The MechDSL repo drifted away from its **LaTeX-driven semantic compiler
contract** during MVP execution; the recovery plan restores LaTeX as the
canonical entry point while preserving the symbolic, solver, codegen,
verification, and `algo2code` work that already landed.

## Why this note exists

This file is a single short pointer that future readers can hit before
diving into the audit or the plan. It links the diagnosis (what drifted,
why it matters) to the prescription (what is being done, in what order)
so that "why is there a recovery branch?" is a one-page answer rather
than an archaeology project.

## Cross-links (prescription and diagnosis)

| Document | Role |
|---|---|
| [`dev/reviews/drift_20_04.md`](drift_20_04.md) | Architectural-drift audit (2026-04-26). Identifies the LaTeX-first contract as the highest-leverage deferral and rates module-by-module severity. |
| [`dev/plans/recovery_plan_latex_contract.md`](../plans/recovery_plan_latex_contract.md) | Active recovery plan. Phases R0–R6 with per-task action items, files-touched lists, blockers, and acceptance criteria. |
| [`dev/reviews/frontend_drift_history.md`](frontend_drift_history.md) | Companion classification: planned-but-deferred vs never-planned vs implemented-via-substitute. |

## Recovery phase status (R0 → R6)

| Phase | Title | Status |
|-------|-------|--------|
| R0 (Phase 1) | Freeze stable vs experimental contract surface | done |
| R1 (Phase 2) | Restore the LaTeX frontend as the canonical entry point | done |
| R2 (Phase 3) | Enrich `ProblemIR` compatibly | done |
| R3 (Phase 4) | Enrich `ElementIR` and normalize lowering | done |
| R4 (Phase 5) | Re-anchor Taichi as the stable codegen path | done |
| R5 (Phase 6) | Integrate `algo2code` at the PCG seam | done |
| R6 (Phase 7) | Verification, governance, closure | **in progress** |

Phase status reflects the merged state of branch `SOSOVSKI/recovery-phase7`
at the time of authoring. The authoritative per-task state lives in
`dev/tracking/tasks-tracker_recovery_plan_latex_contract.md`.

## How to read this

- For the **task list** and per-phase action items, go to
  [`dev/plans/recovery_plan_latex_contract.md`](../plans/recovery_plan_latex_contract.md).
- For the **diagnosis** (what drifted and why it matters), go to
  [`dev/reviews/drift_20_04.md`](drift_20_04.md).
- For the **historical classification** of what was planned, deferred, or
  substituted, go to [`frontend_drift_history.md`](frontend_drift_history.md).
- This note itself is intentionally short — its job is cross-linking, not
  re-stating the audit or the plan.

## Scope (non-goals)

This note does **not** modify the design docs under `dev/design_docs/`,
duplicate the audit, or change the recovery plan's task list. It exists
only to make the recovery story discoverable from a single index entry
in `dev/reviews/`.
