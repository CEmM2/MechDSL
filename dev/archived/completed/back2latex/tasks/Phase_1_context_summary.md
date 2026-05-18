# Phase 1 Context Summary: Apply structural amendments to recovery_plan_latex_contract.md

**Plan:** `dev/plans/back2latex.md`
**Original plan phase name:** Amendments 1–9 (single-pass edit pass)

## Conventions

- Edits target a single file: `dev/plans/recovery_plan_latex_contract.md`. No code edits in `packages/`.
- Canonical task IDs follow `P<phase>-<seq>` (Aut_Faciam mandate, `Plan-2-Tasks.md:26`). Legacy IDs (`R0.1`, `R1.1`, …) are preserved alongside in a Legacy ID column for traceability with `dev/reviews/drift_20_04.md`.
- Phase headings follow `## Phase <integer> — <title> (R<digit>)` so both labels are searchable.
- Tier vocabulary is restricted to: `unit | integration | regression | docs | manual`. No other values are valid in the action-item Tier columns.
- All cross-phase dependency edges use canonical IDs only — never legacy IDs — even in prose.

## Key Principles

- **Plan-2-Tasks-shape, no rewrite.** Preserve the careful prose; only add structure. The recovery plan's content is correct; what's missing is the dependency/IDs/tier metadata Plan-2-Tasks needs to author useful task JSONs.
- **Fail loudly if shape drifts.** The verification grep checks (count of `### Code reality anchor`, `### Cross-phase dependencies`, etc.) double as success criteria — if a number is wrong, the amendment is incomplete.
- **Code reality over plan prose.** Where the recovery plan's prose disagrees with current code (e.g., `taichi_printer.py` uses `EmissionContext`, not module-level `emit*` functions), the Code reality anchor records the actual state with file:line citations. Plan-2-Tasks reads anchors to avoid authoring acceptance criteria against a stale mental model.

## Pre-resolved Design Decisions

- **Phase mapping is fixed**: `R0..R6` ↔ `Phase 1..7` exactly, in order. Task P1-1 introduces this mapping table and the rest of Phase 1 cascades from it.
- **Risk attribution uses task IDs only**, not phase IDs. A risk that affects "Phase 2 in general" must still cite specific tasks (P2-1, P2-3, etc.) so the per-task `risks` field in the eventual task JSONs has somewhere concrete to point.
- **PR slicing is not authored upstream.** Amendment 8 explicitly drops or one-sentences the legacy `PR-2 = R1.1-R1.3` style slicing; PR boundaries are downstream of task decomposition (one task = one PR is the default).
- **The recovery plan's own P1-6 task (introduced by Amendment 7) is in the recovery-plan namespace** — distinct from this back2latex plan's `P1-7` task. Naming collision is conceptual only because each plan's tasks live in their own folder (`dev/tasks/<plan>/json/`).

## Allowed Deviations

- Amendment 8 permits either deletion or replacement of the "Suggested PR slices" section. Either is acceptable per back2latex.md; the recommendation is replacement with the one-sentence note.
- Code reality anchor citations may need minor file:line tweaks if the live code has shifted since 2026-04-26. Update the citation to the current line, do not move the anchor.

## Downstream Impact

- Phase 2 (this plan) consumes the amended recovery plan as input to a recursive `/Aut_Faciam tasks` invocation. Every Phase 1 task gap that escapes manifests as either a missing artifact or a malformed task JSON in `dev/tasks/recovery_plan_latex_contract/`.
- The verification grep set (Code reality anchor count = 7, Cross-phase dependencies count = 7, action-item-tables seven-column header on every phase) becomes Phase 2's pre-flight check (P2-1).
- Once Phase 2 lands, the recovery plan's own ~30-task decomposition becomes the actual unit of work. This back2latex plan's job ends at "Phase 1 of recovery plan scaffolded; user reviews; pause."
