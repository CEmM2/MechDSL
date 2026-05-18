# Phase 2 Context Summary: Verify and validate via Aut_Faciam round-trip

**Plan:** `dev/plans/back2latex.md`
**Original plan phase name:** Verification (steps 1–5)

## Conventions

- Phase 2 is strictly serial: P2-1 → P2-2 → P2-3 → P2-4. No parallelism. Each step's output is the next step's input.
- Two distinct task namespaces are involved:
  - **back2latex namespace** — this plan's tasks at `dev/tasks/back2latex/json/`.
  - **recovery_plan_latex_contract namespace** — created by P2-2 at `dev/tasks/recovery_plan_latex_contract/json/`.
  When P2-3 says "spot-check P1-4, P2-1, P3-1," those IDs live in the recovery-plan namespace, not this one.
- Hard stop after P2-4. Do **not** invoke `/Aut_Faciam exec 1` in the same engagement. Execution is a separate user-initiated action.

## Key Principles

- **Trust the structural checks before invoking decomposition.** P2-1's grep checklist is what catches the "Plan-2-Tasks-shape errors" that would otherwise propagate into ~30 malformed task JSONs.
- **GitHub artifacts are a projection, not the source of truth.** If GitHub is unauthenticated, P2-2 must still emit local artifacts; the tracker remains authoritative.
- **One round-trip is enough.** If P2-3 spot-checks fail, the right move is to fix the corresponding Phase 1 amendment and re-run P2-2 — not to patch the generated JSON by hand.

## Pre-resolved Design Decisions

- **The expected task count for the recovery plan is ~30**, derived from Phase 1 having 6 tasks and Phases 2–7 having ~3–5 each. Plan-2-Tasks producing ≥40 or ≤20 tasks is a signal the amendments under-specified or over-specified the dependency graph.
- **Spot-check by content, not just by ID.** The recovery-plan task that adds `to_dict/from_dict` to `ProblemIR` is conceptually `P3-1`, but if Plan-2-Tasks splits or merges Phase 3 differently, identify it by deliverable (`mechanics_ir.py` in `deliverables`) and validate that one instead.
- **Scaffold Phase 1 only.** Phases 2–7 of the recovery plan stay un-scaffolded after this engagement, because their downstream effects (six → seven branches, dozens of task issues) outstrip a single review session.

## Allowed Deviations

- If `gh auth status` fails inside P2-2, the local artifacts still must be produced; mark the GitHub portion as deferred and note in the gates file. This is documented behavior in `Plan-2-Tasks.md:77`.
- If Plan-2-Tasks generates 25–35 tasks instead of exactly 30, that is acceptable. The structural amendments fix the action-item rows but Plan-2-Tasks may decompose further inside individual rows.

## Downstream Impact

- After P2-4, the user holds a fully scaffolded `recovery_plan_latex_contract` Phase 1 that they can `exec` when ready. This back2latex plan exits at that point.
- If anything in Phase 2 fails, the failure feeds back into Phase 1 of this plan: either the amendments are incomplete (re-open the relevant P1-* task) or the recovery plan has a deeper structural issue this plan didn't anticipate (escalate, do not paper over).
- Gates history for Phase 2 lives at `dev/tasks/back2latex/gates/phase_2_gates.md` and records the artifact-existence assertions plus any GitHub label transitions.
