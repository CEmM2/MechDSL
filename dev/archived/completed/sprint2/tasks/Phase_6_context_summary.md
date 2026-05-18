# Phase 6 Context Summary — Sprint Integration & Exit Criteria

## Conventions
- **Fast CI test command**: `uv run pytest packages/mechdsl-core/tests/ -m "not slow and not gpu" -x -q`
- **Slow test command**: `uv run pytest packages/mechdsl-core/tests/ -m slow -x -q`
- **Handoff template**: `.claude/skills/Aut_Faciam/templates/Handoff_template.md`

## Key Principles
- All 10 exit criteria from `dev/plans/MVP_sprint2.md` must be verified with concrete evidence (test pass counts, file existence, etc.)
- The handoff document must capture known issues, lessons learned, and what Sprint 3 should know
- Full regression includes both fast and slow suites

## Pre-resolved Design Decisions
- **Sprint 2 baseline**: 740 fast + 2 slow E2E from Sprint 1 — Sprint 2 adds new tests but must not break existing ones
- **Exit criteria evidence**: each criterion needs specific test evidence, not "should pass" claims

## Downstream Impact
- **Sprint 2 completion** unblocks Sprint 3 work
- **Known gaps to carry forward**: generated Newton driver still lacks BC enforcement, alpha history needs dual-buffer pattern
- **The handoff document** is the primary communication to the Sprint 3 agent

## Key Files
- `dev/plans/MVP_sprint2.md` — exit criteria list
- `.claude/skills/Aut_Faciam/templates/Handoff_template.md` — handoff document template
- `dev/tasks/sprint2/Sprint2_Completion_Handoff.md` — to be created
