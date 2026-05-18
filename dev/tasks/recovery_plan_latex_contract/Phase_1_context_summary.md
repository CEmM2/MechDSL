# Phase 1 Context Summary: Freeze the contract surface (R0)

**Plan:** `dev/plans/recovery_plan_latex_contract.md`
**Original plan phase name:** Freeze the contract surface (R0)

## Goal
Stop further architectural drift and establish a stable vs experimental boundary.

## Why this phase
Without a declared contract surface, every subsequent refactor remains ambiguous.

## Code reality anchor (2026-04-26)
- `dev/tracking/tasks-tracker_MVP_plan.md` rows are all `not_started`; only two status values exist in practice across the live trackers.
- `dev/plans/` already holds 13 plan files and `dev/tracking/` holds 8 trackers, with no explicit "active vs archived" marker on any of them.
- The mismatch this phase corrects: there is no published stable/experimental boundary, and the four-value status vocabulary (`done`, `deferred`, `implemented-via-substitute`, `not_started`) is not yet legal in any tracker.

## Required constraints
(none documented separately)

## Cross-phase dependencies
This phase blocks: — (Phase 1 outputs are docs/tracker; downstream phases depend on them only weakly).
This phase is blocked by: — (no upstream dependencies).

## Exit criteria
- Stable/experimental scope is documented.
- Tracker status language supports truthful recovery reporting.
- No new work begins without being classified into one of the two support tiers.

## Tasks in this phase
- **P1-1** (R0.1, tier=docs): Define two support tiers for the repo: `MVP-stable` and `experimental`.
- **P1-2** (R0.2, tier=docs): Mark MFEM/MOOSE codegen, explicit dynamics, non-MVP materials, and non-canonical elements as experimental for the canonical compile path.
- **P1-3** (R0.3, tier=docs): Add a lightweight “stability policy” note to developer-facing docs.
- **P1-4** (R0.4, tier=docs): Normalize tracker vocabulary to distinguish `done`, `deferred`, `implemented-via-substitute`, and `not_started`.
- **P1-5** (R0.5, tier=docs): Record the frontend deferral explicitly as historical execution drift, not missing design intent.
- **P1-6** (R0.6 (new), tier=docs): Mark `dev/plans/MVP_plan.md` and `dev/plans/MVP_sprint{1,2,3}.md` as superseded by this recovery plan for the frontend contract; add a banner pointing here and an explicit `superseded` tag.
