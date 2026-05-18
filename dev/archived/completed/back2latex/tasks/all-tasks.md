# All Tasks — back2latex

Plan source: `dev/plans/back2latex.md`
Tracker: `dev/tracking/tasks-tracker_back2latex.md`

The plan is a single-pass meta-edit on `dev/plans/recovery_plan_latex_contract.md` to make it ingestible by Plan-2-Tasks, followed by a verification round-trip through Aut_Faciam. Two phases: amendment authoring, then validation.

| Task ID | Phase | Title | Blocked by (immediate) | Blocks (immediate) | Derived from plan lines |
|---|---|---|---|---|---|
| P1-1 | 1 | Insert Phase ID mapping (R↔integer) table | — | P1-2, P1-3, P1-5, P1-6, P1-7, P1-9 | 51–75 |
| P1-2 | 1 | Renumber phase headings to integer + (RX) form | P1-1 | P1-3, P1-5 | 77–87 |
| P1-3 | 1 | Rewrite action-item tables with new columns | P1-2 | P1-5, P1-6, P1-7 | 89–107 |
| P1-4 | 1 | Insert Code reality anchor blocks per phase | — | P2-1 | 109–131 |
| P1-5 | 1 | Add Cross-phase dependencies blocks per phase | P1-3 | P2-1 | 133–151 |
| P1-6 | 1 | Add Affects task(s) column to risks table | P1-3 | P2-1 | 153–164 |
| P1-7 | 1 | Add P1-6 supersession task in recovery plan | P1-3 | P2-1 | 166–174 |
| P1-8 | 1 | Drop or fold Suggested PR slices section | — | P2-1 | 176–178 |
| P1-9 | 1 | Update success criteria checklist with canonical IDs | P1-1 | P2-1 | 180–184 |
| P2-1 | 2 | Skim verification of amended recovery plan | P1-1, P1-2, P1-3, P1-4, P1-5, P1-6, P1-7, P1-8, P1-9 | P2-2 | 211–219 |
| P2-2 | 2 | Run /Aut_Faciam tasks on amended recovery plan | P2-1 | P2-3 | 220–230 |
| P2-3 | 2 | Spot-check three generated task JSONs | P2-2 | P2-4 | 232–235 |
| P2-4 | 2 | Run /Aut_Faciam scaffold 1 on recovery plan and stop | P2-3 | — | 237–243 |

## Dependency notes

- **Phase 1 (amendments)** — most amendments are independent edits to `recovery_plan_latex_contract.md`. Only the structural-ID amendments (P1-1 → P1-2 → P1-3) form a strict chain because each later step references canonical task IDs introduced upstream. The remaining tasks (P1-4 anchors, P1-8 PR-slices, P1-9 checklist) can land in any order.
- **Phase 2 (verification)** — strictly serial: skim → decompose → spot-check → scaffold-and-stop.
- **No circular dependencies.** Verified by inspection of the table above.
- **No cross-phase dependencies** beyond Phase-1-blocks-Phase-2; the rule is encoded by listing every Phase-1 task in P2-1's `blocked_by`.
