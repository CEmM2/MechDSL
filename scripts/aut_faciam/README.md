# `scripts/aut_faciam/` — Plan orchestration helpers

Promoted from session-local `.context/` helpers during the back2latex / recovery PR cleanup pass. These scripts batch the GitHub-API and filesystem operations that the `Aut_Faciam` workflow needs, so a session doesn't have to hand-run `gh issue create` 30+ times.

## Source-of-truth contract

Every script in this folder reads and writes a single canonical file:

```
dev/tasks/<plan_slug>/github_issue_map.json
```

That map is the bridge between local task data and GitHub issues. **Never hand-edit it** — re-run the appropriate orchestrator and let it update both the map and the corresponding task JSONs in lockstep. Each script also stamps `dev/tasks/<plan_slug>/json/<task_id>.json` with the `github_issue.task_issue` and `github_issue.phase_issue` numbers as it creates issues.

## Two plan namespaces, two prefixes

The scripts are prefixed by which plan they operate against. Confusing the namespaces is the most common mistake — task `P1-6` exists in both `back2latex` and `recovery_plan_latex_contract` and means very different things.

| Plan | Tasks folder | GH plan-overview | Scripts here |
|---|---|---|---|
| `back2latex` | `dev/tasks/back2latex/` | #124 | `back2latex_*` |
| `recovery_plan_latex_contract` | `dev/tasks/recovery_plan_latex_contract/` | #140 | `recovery_*` |

## Inventory

### back2latex helpers (the meta-plan)

| Script | What it does |
|---|---|
| `back2latex_scaffold_phase1_issues.py` | Reads the 9 Phase-1 task JSONs, creates one `task-issue` per task on GitHub in dependency order, stamps each task JSON's `github_issue.task_issue`, and updates `github_issue_map.json`. Idempotent only if the issue map is empty for Phase 1 (re-running blindly creates duplicate issues). |
| `back2latex_scaffold_phase2_issues.py` | Same shape as Phase 1 but for the 4 Phase-2 verification tasks. Marks tasks with the `blocked` label when their `blocked_by` references aren't yet `done`. |
| `back2latex_close_phase1_issues.py` | Closes the 9 Phase-1 task issues with `done,gate-b-pass` labels, populates the phase-1 issue body checklist (`- [ ] #N` → `- [x] #N`), closes the phase-1 issue, and checks off Phase 1 in plan-overview #124. |

### recovery_plan_latex_contract helpers

| Script | What it does |
|---|---|
| `recovery_plan_decompose.py` | Walks the seven action-item tables in `dev/plans/recovery_plan_latex_contract.md` (already canonical-shaped after back2latex Phase 1 amendments), emits 38 task JSONs, 7 phase context summaries, the all-tasks index, the recovery-plan tracker, and a skeleton `github_issue_map.json`. **Does not call gh** — that's `recovery_phase_skeleton_issues.py`'s job. |
| `recovery_phase_skeleton_issues.py` | Creates the recovery plan-overview issue (#140) and 7 phase-skeleton issues (#141–#147), populates each phase-skeleton body with its context-summary content, patches the plan-overview body with the real issue numbers, and stamps every task JSON's `github_issue.phase_issue`. |
| `recovery_scaffold_phase1.py` | Scaffolds Phase 1 of the recovery plan: writes 6 pytest stubs, updates the 6 task JSONs with `test_artifacts` + `verification_commands`, writes `Phase_1_Scaffold_Validation.md`, creates 6 task issues (#148–#153), populates phase-1 issue #141 body, swaps `not-scaffolded` → `scaffolded`. |
| `recovery_scaffold_phase2.py` | Same shape as Phase 1 but for the 6 Phase-2 tasks. Issue range #154–#159. |
| `recovery_scaffold_phase3.py` | Same shape but for the 5 Phase-3 tasks. Issue range #160–#164. Phase 3 stubs covering `P3-1..P3-5` (P3-1 was implemented in this PR; the other 4 remain `pytest.skip(...)` stubs). |

## Usage

Run from the repo root with the project's `uv` environment:

```bash
uv run python scripts/aut_faciam/recovery_scaffold_phase3.py
```

Each script is self-contained: imports only `json`, `subprocess`, `tempfile`, and `pathlib` from the stdlib. They all expect:

- The repo to be a git checkout under the user's account.
- `gh` CLI authenticated against the same repo (`gh auth status` should be green before running).
- The corresponding task JSONs to already exist in `dev/tasks/<plan_slug>/json/` (run `recovery_plan_decompose.py` first if the recovery-plan task tree doesn't exist yet).

## Idempotency caveats

These scripts were written for one-shot use during this PR. They do **not** check the issue map for pre-existing entries before calling `gh issue create` — re-running a scaffold script will create duplicate task issues on GitHub. Before re-running:

1. Inspect `dev/tasks/<plan_slug>/github_issue_map.json` — if `phases.<N>.task_issues` already has entries, the scaffold for that phase already ran.
2. If you intentionally want to re-scaffold (e.g., you closed all the issues and want fresh ones), clear the relevant `task_issues` map first.
3. Better: extract the task-issue creation logic to a single parameterised helper that *does* respect the existing map. That refactor is out of scope for this PR.

## Why these are scripts, not Aut_Faciam-skill internals

The Aut_Faciam skill commands (`Plan-2-Tasks.md`, `ScaffoldPhase.md`, etc.) are prompts that the agent reads and follows. They tell the agent *what* to do, not *how to batch the gh calls*. These scripts are the agent's chosen implementation of "batch all the issue creates in one process so we don't ask the user to approve 30 separate `gh issue create` invocations." Future runs of the skill may pick a different batching strategy; these scripts are the historical record of how this PR handled it.

## Future work

1. Unify the per-phase scaffold scripts into one `scaffold_phase.py --phase N --plan <slug>` parameterised entry point.
2. Make every script idempotent by reading `github_issue_map.json` and skipping entries that already have an `issue_number`.
3. Move the issue-body templates inline → external `templates/*.md` files so the script body is just orchestration.

None of those block this PR.
