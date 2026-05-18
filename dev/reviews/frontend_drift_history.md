# Frontend Deferral as Historical Execution Drift

**Date authored:** 2026-04-26
**Authored by:** recovery_plan_latex_contract Phase 1 task P1-5
**Companion documents:** [`drift_20_04.md`](drift_20_04.md), [`../plans/recovery_plan_latex_contract.md`](../plans/recovery_plan_latex_contract.md)

## What this note records

The original MechDSL design (`dev/design_docs/00-OVERVIEW.md` through
`11-ALGO2CODE.md`) specified a **LaTeX-driven semantic compiler** whose
canonical entry point would accept LaTeX source describing a continuum-mechanics
problem and produce solver code. The MVP plan (`dev/plans/MVP_plan.md`) and
its sprint plans (`MVP_sprint{1,2,3}.md`) carried frontend tasks
`P2.1..P2.5` that were intended to deliver this entry point.

In practice the frontend tasks were repeatedly deferred while runtime,
codegen, and verification work proceeded. By the time of `drift_20_04.md`
(see that file for the audit), the bypass — building a `ProblemIR`
programmatically via `build_context()` and skipping the LaTeX layer — had
hardened into the actual public surface, and `P2.1..P2.5` were still
showing `not_started` in the trackers.

This note exists so future readers can clearly distinguish:

| Pattern | Meaning |
|---------|---------|
| Planned but never implemented | Intent existed; work was deferred. The intent **is** in the design docs. |
| Never planned | Out of scope from the start; absent from the design docs. |
| Implemented via substitute | The original intent is satisfied by alternate work that landed under a different surface (e.g. `build_context()` covered the construct-a-`ProblemIR` use case that `P2.1..P2.5` would have covered for non-LaTeX inputs). |

The frontend deferral falls into the **planned but never implemented**
column for the LaTeX-input portion, and **implemented via substitute** for
the programmatic-construction portion. Both are recovered to canonical
status by the recovery plan.

## Where the drift was first surfaced

`dev/reviews/drift_20_04.md` documents the architectural-drift audit and
identifies the bypassed frontend as the highest-leverage deferral. That
file contains the technical detail; this note exists as a short pointer
in the planning trail for readers who land here first.

## How recovery handles it

[`dev/plans/recovery_plan_latex_contract.md`](../plans/recovery_plan_latex_contract.md)
Phase 2 (R1) introduces a canonical `compile_latex(...)` façade and
preserves `build_context()` as a documented secondary API. The recovery
plan's Phase 1 (R0) — including this note — establishes the vocabulary
and tracker hygiene to record the deferral honestly. Phase 1 task P1-6
adds the supersession banners to the affected MVP plan files.

## Status convention used after this note lands

Per [`../tracking/STATUS_LEGEND.md`](../tracking/STATUS_LEGEND.md), the
old `P2.1..P2.5` rows in `tasks-tracker_MVP_plan.md` should now be
classified as `implemented-via-substitute` for the programmatic case and
`deferred` for the LaTeX-source case, both citing the recovery plan.
This replaces the misleading `not_started` they currently carry.

## Why this is a `drift`, not a `bug`

No code is broken. The runtime, codegen, IRs, and solver work, and the
verification suite passes. What slipped is the **front door**. Treating
this as historical execution drift (rather than a defect) keeps the
recovery plan focused on restoring the contract additively, without
implying the intervening work was wasted. It was not — it just defined
the actual public surface, which is now being re-aligned with the
design docs.
