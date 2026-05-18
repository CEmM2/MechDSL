# Development Task Tracker — back2latex

> ⚠️ **Superseded** — the active execution source is [`tasks-tracker_recovery_plan_latex_contract.md`](tasks-tracker_recovery_plan_latex_contract.md), driven by [`dev/plans/recovery_plan_latex_contract.md`](../plans/recovery_plan_latex_contract.md). This tracker is retained for historical reference only (Phase 7 / R6 archival, P7-5).

Generated on: 2026-04-26
This tracker records execution status for the back2latex task set.

## back2latex Tracker

Plan source: `dev/plans/back2latex.md`
Task index: `dev/tasks/back2latex/all-tasks.md`

| Task ID | Title | Status | Owner | Blocked by (open) | Blocks | Plan lines | PR/Commit | Verified by | Completed on |
|---|---|---|---|---|---|---|---|---|---|
| P1-1 | Insert Phase ID mapping table | done | claude-opus-4.7 | — | P1-2, P1-3, P1-5, P1-6, P1-7, P1-9 | 51–75 | (pending commit) | test_p1_1.py 3/3 | 2026-04-26 |
| P1-2 | Renumber phase headings to integer + (RX) form | done | claude-opus-4.7 | — | P1-3, P1-5 | 77–87 | (pending commit) | test_p1_2.py 3/3 | 2026-04-26 |
| P1-3 | Rewrite action-item tables with new columns | done | claude-opus-4.7 | — | P1-5, P1-6, P1-7 | 89–107 | (pending commit) | test_p1_3.py 4/4 | 2026-04-26 |
| P1-4 | Insert Code reality anchor blocks per phase | done | claude-opus-4.7 | — | P2-1 | 109–131 | (pending commit) | test_p1_4.py 3/3 | 2026-04-26 |
| P1-5 | Add Cross-phase dependencies blocks per phase | done | claude-opus-4.7 | — | P2-1 | 133–151 | (pending commit) | test_p1_5.py 3/3 | 2026-04-26 |
| P1-6 | Add Affects task(s) column to risks table | done | claude-opus-4.7 | — | P2-1 | 153–164 | (pending commit) | test_p1_6.py 3/3 | 2026-04-26 |
| P1-7 | Add P1-6 supersession task in recovery plan | done | claude-opus-4.7 | — | P2-1 | 166–174 | (pending commit) | test_p1_7.py 3/3 | 2026-04-26 |
| P1-8 | Drop or fold Suggested PR slices section | done | claude-opus-4.7 | — | P2-1 | 176–178 | (pending commit) | test_p1_8.py 2/2 | 2026-04-26 |
| P1-9 | Update success criteria checklist with canonical IDs | done | claude-opus-4.7 | — | P2-1 | 180–184 | (pending commit) | test_p1_9.py 3/3 | 2026-04-26 |
| P2-1 | Skim verification of amended recovery plan | done | claude-opus-4.7 | — | P2-2 | 211–219 | (pending commit) | test_p2_1.py 2/2 + 7 grep checks | 2026-04-26 |
| P2-2 | Run /Aut_Faciam tasks on amended recovery plan | done | claude-opus-4.7 | — | P2-3 | 220–230 | (pending commit) | test_p2_2.py 5/5 | 2026-04-26 |
| P2-3 | Spot-check three generated task JSONs | done | claude-opus-4.7 | — | P2-4 | 232–235 | (pending commit) | test_p2_3.py 3/3 | 2026-04-26 |
| P2-4 | Run /Aut_Faciam scaffold 1 on recovery plan and stop | done | claude-opus-4.7 | — | — | 237–243 | (pending commit) | test_p2_4.py 3/3 (incl. hard-stop) | 2026-04-26 |


## Update protocol

1. When a task starts, set `Status` to `in_progress`, assign `Owner`, and keep unresolved blockers in `Blocked by (open)`.
2. When a task is done, set `Status` to `done`, fill `PR/Commit`, `Verified by`, and `Completed on` (YYYY-MM-DD).
3. For each newly completed task, remove its ID from downstream rows in `Blocked by (open)` when applicable.

## Verification status

### Phase 1 aggregate verification:

#### Phase 1 mapping between test and task:

| Task ID | Title | Test file |
|---|---|---|
| P1-1 | Insert Phase ID mapping table | manual / grep `## Phase ID mapping` in `dev/plans/recovery_plan_latex_contract.md` |
| P1-2 | Renumber phase headings | manual / grep `^## Phase [0-9]` count = 7 |
| P1-3 | Rewrite action-item tables | manual / column-header check on each table |
| P1-4 | Insert Code reality anchors | manual / grep `### Code reality anchor (2026-04-26)` count = 7 |
| P1-5 | Add Cross-phase dependencies | manual / grep `### Cross-phase dependencies` count = 7 |
| P1-6 | Add Affects task(s) column to risks | manual / risks-table column inspection |
| P1-7 | Add P1-6 supersession task | manual / Phase 1 action table row count = 6 |
| P1-8 | Drop/fold Suggested PR slices | manual / grep absence of legacy slice patterns |
| P1-9 | Update success criteria checklist | manual / new bullet appended |

#### Verification outcomes:

Phase 1 is doc-only; verification is per-task grep + regex assertions via pytest at `audit` tier.

`uv run pytest packages/mechdsl-core/tests/plan_tests/ -v -m audit` → 27/27 passed (100%).

### Phase 2 aggregate verification:

#### Phase 2 mapping between test and task:

| Task ID | Title | Test file |
|---|---|---|
| P2-1 | Skim verification of amended recovery plan | manual / structural checklist |
| P2-2 | Run /Aut_Faciam tasks on amended recovery plan | integration / artifact existence check under `dev/tasks/recovery_plan_latex_contract/` |
| P2-3 | Spot-check three task JSONs | manual / inspection of P1-4 / P2-1 / P3-1 in recovery namespace |
| P2-4 | Run /Aut_Faciam scaffold 1 on recovery plan and stop | integration / `phase_1_gates.md` + GitHub label transitions |

#### Verification outcomes:

Phase 2 is integration-tier; outcomes are file-existence and GitHub-label assertions captured in `dev/tasks/back2latex/gates/phase_2_gates.md`.

`uv run pytest packages/mechdsl-core/tests/plan_tests/test_p2_*.py` → 13/13 passed (5 audit + 8 integration). Hard-stop invariant (no `/Aut_Faciam exec 1` against the recovery plan) verified by `test_p2_4::test_no_exec_artifacts_present`.

## Plan complete

All 13 tasks across both phases are `done`. The back2latex plan is finished. Recovery plan (`dev/plans/recovery_plan_latex_contract.md`) is now Plan-2-Tasks-shaped, decomposed into 38 task JSONs at `dev/tasks/recovery_plan_latex_contract/`, with Phase 1 fully scaffolded (6 task issues live on GitHub: #148–#153). The user owns the next move: review the scaffolded artifacts and start a fresh engagement to run `/Aut_Faciam exec 1 dev/plans/recovery_plan_latex_contract.md` when ready.
