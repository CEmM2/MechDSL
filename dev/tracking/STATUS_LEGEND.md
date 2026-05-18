# Tracker Status Vocabulary

This file is the canonical reference for `Status` column values in every
`dev/tracking/tasks-tracker_*.md` file. It exists to satisfy
[`dev/plans/recovery_plan_latex_contract.md`](../plans/recovery_plan_latex_contract.md)
Phase 1 task `P1-4`, which normalises the per-tracker vocabulary so future
recovery reporting can distinguish "we never started this" from "we shipped a
substitute that does the job differently."

## Permitted values

| Value | Meaning |
|-------|---------|
| `not_started` | Work has not begun. No commits, no branches, no scaffolding for this task. |
| `in_progress` | A branch / draft PR exists; work is actively underway. (Used by `Aut_Faciam` execution gates; not always present in older trackers.) |
| `done` | Implementation complete, all gates passed, evidence recorded in the tracker row (`PR/Commit`, `Verified by`, `Completed on`). |
| `deferred` | Explicitly postponed by a planning decision. The reason and target re-entry phase **must** be cited in the row's `Verified by` or `PR/Commit` cell, e.g. `deferred to recovery R2 — see PR-4`. |
| `implemented-via-substitute` | The original task's intent is satisfied by alternate work that landed under a different task ID. The substitute task ID **must** be cited (e.g. `substituted by P5-4 in recovery_plan_latex_contract`). Used for historical drift cases where the canonical task was bypassed but its problem was solved another way. |

## Why these five (vs the legacy two)

Historical trackers used only `not_started` and `done`, which conflated three
genuinely different states:

1. Work never started → still `not_started`.
2. Work consciously postponed → now `deferred`, with the postponement reason
   recorded so future readers do not waste cycles deciding whether to start it.
3. Work superseded by a substitute → now `implemented-via-substitute`, so the
   plan-of-record reflects the real architecture rather than implying a gap
   that does not exist.

`in_progress` is included for completeness because `Aut_Faciam` flips that
value automatically during execution; older trackers may not show it.

## Update protocol

When changing a tracker row's `Status`:

1. If moving to `done`, fill `PR/Commit`, `Verified by`, and `Completed on`.
2. If moving to `deferred`, cite the deferral phase or planning artifact in
   `Verified by`.
3. If moving to `implemented-via-substitute`, cite the substitute task ID in
   `Verified by`.
4. If a downstream row's `Blocked by (open)` contained the just-completed
   task, remove it.

## See also

- [`dev/plans/recovery_plan_latex_contract.md`](../plans/recovery_plan_latex_contract.md) — Phase 1 (R0) introduces the four-value vocabulary.
- Each `dev/tracking/tasks-tracker_*.md` should reference this legend in its preamble.
