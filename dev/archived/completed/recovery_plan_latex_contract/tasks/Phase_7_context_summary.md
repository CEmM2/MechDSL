# Phase 7 Context Summary: Verification, governance, and closure (R6)

**Plan:** `dev/plans/recovery_plan_latex_contract.md`
**Original plan phase name:** Verification, governance, and closure (R6)

## Goal
Make the recovered contract testable, documented, and traceable.

## Why this phase
Governance should describe the stabilized recovery state, not speculate ahead of it.

## Code reality anchor (2026-04-26)
- `tests/test_e2e.py:1-80` constructs `ProblemIR` directly via a `_make_elastic_problem_ir()` helper.
- No test currently starts from a LaTeX string anywhere in the suite.
- The mismatch this phase corrects: end-to-end coverage cannot demonstrate the LaTeX-driven contract because every e2e test bypasses the frontend entirely; recovery is incomplete until at least one acceptance test runs from a LaTeX source.

## Required constraints
(none documented separately)

## Cross-phase dependencies
This phase blocks: — (terminal phase).
This phase is blocked by: P2-1, P3-1, P4-1, P5-1 (the four pillars whose acceptance test, governance closure, and split test families this phase verifies).

## Exit criteria
- Stable verification clearly begins from LaTeX input.
- Planning and tracking artifacts reflect reality.
- Recovery progress can be audited without re-reading the whole repo history.

## Tasks in this phase
- **P7-1** (R6.1, tier=integration): Split end-to-end tests into `from_latex` and `from_problem_ir` families.
- **P7-2** (R6.2, tier=integration): Add at least one canonical LaTeX-to-solution acceptance test on the MVP-stable path.
- **P7-3** (R6.3, tier=docs): Update examples so the stable story begins from LaTeX input; keep programmatic examples as advanced/testing aids.
- **P7-4** (R6.4, tier=docs): Add a short architecture decision or recovery-status note cross-linking this plan and the drift report.
- **P7-5** (R6.5, tier=docs): Archive or annotate superseded sprint/task documents so they are obviously historical.
- **P7-6** (R6.6, tier=docs): Close the loop with an updated drift/alignment review after Phases R1–R4 land.
