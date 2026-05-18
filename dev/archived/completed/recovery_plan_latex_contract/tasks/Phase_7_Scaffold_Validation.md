# Phase 7 Scaffold Validation

Plan: `dev/plans/recovery_plan_latex_contract.md`
Phase: 7 — Verification, governance, and closure (R6)
Scaffolded: 2026-04-29

| Task ID | Title | Missing / Incomplete Fields | Scaffold Action |
|---------|-------|-----------------------------|-----------------|
| P7-1 | Split end-to-end tests into `from_latex` and `from_problem_ir` families. | `verification_commands`, `test_artifacts` (placeholder `[""]`) | auto-filled (pytest path inferred from new stub) |
| P7-2 | Add at least one canonical LaTeX-to-solution acceptance test on the MVP-stable path. | `verification_commands`, `test_artifacts` (placeholder `[""]`) | auto-filled (pytest path inferred from new stub) |
| P7-3 | Update examples so the stable story begins from LaTeX input; keep programmatic examples as advanced/testing aids. | `verification_commands`, `test_artifacts` (placeholder `[""]`) | auto-filled (pytest path inferred from new stub) |
| P7-4 | Add a short architecture decision or recovery-status note cross-linking this plan and the drift report. | `verification_commands`, `test_artifacts` (placeholder `[""]`) | auto-filled (pytest path inferred from new stub) |
| P7-5 | Archive or annotate superseded sprint/task documents so they are obviously historical. | `verification_commands`, `test_artifacts` (placeholder `[""]`) | auto-filled (pytest path inferred from new stub) |
| P7-6 | Close the loop with an updated drift/alignment review after Phases R1–R4 land. | `verification_commands`, `test_artifacts` (placeholder `[""]`) | auto-filled (pytest path inferred from new stub) |

All six tasks already carried non-placeholder `objective`, `acceptance_criteria`, `implementation_steps`, `deliverables`, `risks`, `test_plan.tier`, and `test_plan.cases`. Only `verification_commands` and `test_artifacts` were placeholder-empty and have been auto-filled.

## Existing Test Coverage Search

| Task ID | Search terms | Hits in `packages/mechdsl-core/tests/` | Coverage classification |
|---------|--------------|----------------------------------------|--------------------------|
| P7-1 | `from_latex`, `from_problem_ir` (as marker / family selector) | 0 (no e2e family split exists) | both cases `missing` |
| P7-2 | `compile_latex(` invoked end-to-end + Newton solve | 6 files import `compile_latex` (P2/P3/P5 plan_tests, all API-shape level) | both cases `missing` (no LaTeX→solution acceptance test exists) |
| P7-3 | README first-run example + `dev/examples/*.tex` | `dev/examples/*.tex` exists (cantilever, necking) but README first-run path not yet validated programmatically | both cases `missing` |
| P7-4 | ADR / cross-link note tying recovery plan ↔ drift report | `dev/reviews/drift_20_04.md` exists; no follow-up cross-link note | both cases `missing` |
| P7-5 | `superseded` banners in non-recovery plan/task/tracking docs | P1-6 added banners to `MVP_plan.md` + `MVP_sprint{1,2,3}.md`; broader sweep across `dev/tasks/` and `dev/tracking/` not yet validated | both cases `missing` |
| P7-6 | post-R1–R4 drift/alignment review | `dev/reviews/drift_20_04.md` is the original; no follow-up confirming contract restoration | both cases `missing` |

12 cases total / 0 covered / 0 partial / 12 missing → 12 stubs generated across 6 new files.

## Stubs Generated

| File | Tests | Tier marker |
|------|-------|-------------|
| `packages/mechdsl-core/tests/plan_tests/recovery_plan_latex_contract/test_p7_1.py` | `TestP7_1::test_ci_test_selection_exposes_from_latex_family`, `TestP7_1::test_deliverables_present_at_surfaces` | `@pytest.mark.integration` |
| `packages/mechdsl-core/tests/plan_tests/recovery_plan_latex_contract/test_p7_2.py` | `TestP7_2::test_acceptance_passes_starting_from_latex_input`, `TestP7_2::test_deliverables_present_at_surfaces` | `@pytest.mark.integration` |
| `packages/mechdsl-core/tests/plan_tests/recovery_plan_latex_contract/test_p7_3.py` | `TestP7_3::test_first_run_example_in_readme_uses_canonical_path`, `TestP7_3::test_deliverables_present_at_surfaces` | `@pytest.mark.integration` |
| `packages/mechdsl-core/tests/plan_tests/recovery_plan_latex_contract/test_p7_4.py` | `TestP7_4::test_cross_link_note_exists_and_references_plan_and_drift`, `TestP7_4::test_deliverables_present_at_surfaces` | `@pytest.mark.integration` |
| `packages/mechdsl-core/tests/plan_tests/recovery_plan_latex_contract/test_p7_5.py` | `TestP7_5::test_no_historical_plan_appears_active_by_accident`, `TestP7_5::test_deliverables_present_at_surfaces` | `@pytest.mark.integration` |
| `packages/mechdsl-core/tests/plan_tests/recovery_plan_latex_contract/test_p7_6.py` | `TestP7_6::test_follow_up_review_confirms_contract_status`, `TestP7_6::test_deliverables_present_at_surfaces` | `@pytest.mark.integration` |

(`docs`-tier tasks P7-3..P7-6 are stubbed under the `integration` pytest marker because the existing pytest config has no `docs` marker; the `docs` semantic tier is preserved in each task JSON's `test_plan.tier`. Same convention applied by prior phases — see `test_p5_1.py` Tier docstring.)

## Smoke

```
uv run pytest packages/mechdsl-core/tests/plan_tests/recovery_plan_latex_contract/test_p7_*.py --collect-only -q
```

→ `12 tests collected in 0.04s` (all stubs are discovered; bodies are `pytest.skip("stub — implement after Task P7-N is complete")`).

## Scaffold Summary

| Metric | Value |
|--------|-------|
| Tasks scaffolded | 6 |
| Test cases assessed | 12 |
| Cases covered by existing tests | 0 |
| Cases partially covered (stubs generated) | 0 |
| Cases with no existing tests (stubs generated) | 12 |
| New stub files created | 6 |
| Total new stubs generated | 12 |
| Tasks fully covered by existing tests (no stub needed) | 0 |
| Tasks needing human review | 0 |
| Auto-filled fields | `verification_commands`, `test_artifacts` (six tasks each) |

## Tasks Needing Human Review Before Execute

(none — every P7 task carries a complete `objective`, `acceptance_criteria`, `implementation_steps`, and `deliverables` set from the prior `Plan-2-Tasks` run.)

## Ready for Execute

Fully scaffolded:
- P7-1: Split end-to-end tests into `from_latex` and `from_problem_ir` families. (blocked on P5-1 → done)
- P7-2: Canonical LaTeX-to-solution acceptance test on the MVP-stable path. (blocked on P2-1 → done, P4-1 → done, P5-1 → done)
- P7-3: Examples LaTeX-first; programmatic examples demoted to advanced/testing aids. (blocked on P2-1 → done)
- P7-4: ADR / recovery-status note cross-linking plan and drift report. (no upstream blockers)
- P7-5: Archive or annotate superseded sprint/task documents. (blocked on P5-1 → done)
- P7-6: Closing drift/alignment review after Phases R1–R4 land. (blocked on P2-1, P3-1, P4-1, P5-1 → all done)

All upstream blockers for Phase 7 are already `done` per the tracker. P7 is fully unblocked and ready for `ExecPhase`.

Needs human review before execution:
- (none)
