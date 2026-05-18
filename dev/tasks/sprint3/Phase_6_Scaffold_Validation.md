# Phase 6 Scaffold Validation

Scaffold pass for Sprint 3 Phase 6 (Final Cleanup & Sprint Exit).
Generated: 2026-04-12

| Task ID | Title | Missing / Incomplete Fields | Scaffold Action |
|---------|-------|-----------------------------|-----------------|
| P6-1 | Ruff lint and format pass | `test_artifacts=[""]`, `verification_commands=[""]`, `risks=[]` | auto-filled |
| P6-2 | Mypy type checking pass | `test_artifacts=[""]`, `verification_commands=[""]`, `risks=[]` | auto-filled |
| P6-3 | Full test suite zero failures | `test_artifacts=[""]`, `verification_commands=[""]`, `risks=[]` | auto-filled |
| P6-4 | JIT budget compliance check | `test_artifacts=[""]`, `verification_commands=[""]`, `risks=[]` | auto-filled |
| P6-5 | Remove dead code, unused imports, resolved TODOs | `test_artifacts=[""]`, `verification_commands=[""]`, `risks=[]` | auto-filled |
| P6-6 | Verify all Sprint 3 exit criteria | `test_artifacts=[""]`, `verification_commands=[""]`, `risks=[]` | auto-filled |
| P6-7 | Sprint 3 handoff document | `test_artifacts=[""]`, `verification_commands=[""]`, `risks=[]` | auto-filled |

## Scaffold Summary

| Metric | Value |
|--------|-------|
| Tasks scaffolded | 7 |
| Test cases assessed | 10 |
| Cases covered by existing tests | 1 |
| Cases partially covered (stubs generated) | 3 |
| Cases with no existing tests (stubs generated) | 6 |
| New stub files created | 1 |
| Total new stubs generated | 9 |
| Tasks fully covered by existing tests (no stub needed) | 1 |
| Tasks needing human review | 0 |
| Auto-filled fields | `test_artifacts`, `verification_commands`, `risks`, `github_issue.task_issue` |

## Existing Test Coverage Found

| Task ID | Test case | Existing test file | Function | Coverage |
|---------|-----------|-------------------|----------|----------|
| P6-3 | Full suite exercises Sprint 3 deliverables end-to-end | `packages/mechdsl-core/tests/test_benchmarks.py`, `packages/mechdsl-core/tests/test_convergence.py`, `packages/mechdsl-core/tests/test_full_pipeline.py`, `packages/mechdsl-core/tests/test_ci_config.py`, `packages/mechdsl-core/tests/test_documentation.py`, `packages/algo2code/tests/test_end_to_end.py` | `TestCantilever.test_tip_displacement_within_5_percent`, `TestCooksMembrane.test_reference_comparison`, `TestNeckingBar.test_reference_comparison`, `TestTaskP1T2.test_mms_4level_l2_convergence_rate`, `TestTaskP1T2.test_mms_4level_h1_convergence_rate`, `TestFullPipeline.test_elastic_full_pipeline`, `TestFullPipeline.test_plastic_full_pipeline`, `TestCIConfig.test_ci_tier_filters_are_correct`, `TestTaskP5T1..P5T5`, `test_end_to_end_*` | partial -- the constituent tests exist, but there is no explicit Phase 6 orchestration/report test yet |
| P6-4 | JIT budget compliance stays within MVP limits | `packages/mechdsl-core/tests/test_einsum.py` | `TestBudgetRegressionMVP::test_budget_regression_mvp_per_func`, `test_budget_regression_mvp_kernel_total`, `test_budget_regression_mvp_absolute_ceiling`, `test_budget_regression_mvp_tier_assignments`, `test_budget_regression_mvp_all_within_budget_flag` | covered |
| P6-5 | No stale TODO placeholders remain in emitted SVK path | `packages/mechdsl-core/tests/test_emission_verification.py` | `TestEmissionVerification::test_no_placeholder_todos_in_svk` | partial -- covers one emitted-code path only, not repo-wide cleanup |
| P6-6 | Exit criteria already have targeted proof points from prior phases | `packages/mechdsl-core/tests/test_patch_test.py`, `packages/mechdsl-core/tests/test_benchmarks.py`, `packages/mechdsl-core/tests/test_convergence.py`, `packages/mechdsl-core/tests/test_full_pipeline.py`, `packages/mechdsl-core/tests/test_ci_config.py`, `packages/mechdsl-core/tests/test_documentation.py` | `TestTaskP3T5::test_svk_patch_test_irregular_mesh`, `TestTaskP3T5::test_rigid_body_rotation_zero_force`, `TestRigidBodyMotion::test_finite_rotation_30_degrees`, `TestCantilever::test_tip_displacement_within_5_percent`, `TestCooksMembrane::test_reference_comparison`, `TestNeckingBar::test_reference_comparison`, `TestTaskP1T2::test_mms_4level_l2_convergence_rate`, `TestTaskP1T2::test_mms_4level_h1_convergence_rate`, `TestFullPipeline::*`, `TestCIConfig::*`, `TestTaskP5T1..P5T5` | partial -- underlying checks exist, but the final checklist/report artifact still needs its own Phase 6 wrapper |

## Stub Files Generated

| File | New? | Classes | Stubs |
|------|------|---------|-------|
| `packages/mechdsl-core/tests/test_phase6_exit.py` | yes | `TestTaskP6T1`, `TestTaskP6T2`, `TestTaskP6T3`, `TestTaskP6T5`, `TestTaskP6T6`, `TestTaskP6T7` | `test_ruff_check_packages_clean`, `test_ruff_format_check_packages_clean`, `test_mypy_mechdsl_core_clean`, `test_full_workspace_pytest_suite_passes`, `test_no_resolved_todos_or_fixmes_remain`, `test_no_implemented_phase_stubs_remain`, `test_exit_criteria_matrix_records_all_ten_checks`, `test_exit_report_cites_clean_toolchain_and_ci_evidence`, `test_sprint3_handoff_document_covers_mvp_completion_and_plan_b_limits` |

Repo note: `pytest` runs with `--strict-markers`, and this workspace defines only `slow`, `gpu`, `e2e`, `audit`, and `benchmark`. The Phase 6 scaffold stubs are intentionally unmarked so they collect cleanly under the existing marker policy.

All 9 stubs in `packages/mechdsl-core/tests/test_phase6_exit.py` collect cleanly under
`uv run pytest packages/mechdsl-core/tests/test_phase6_exit.py --collect-only -q`
(9 tests collected in 0.01s).

## Tasks Needing Human Review Before Execute

None. All Phase 6 task JSONs already had concrete `objective`, `acceptance_criteria`, `implementation_steps`, and `deliverables`; scaffold only filled verification metadata and generated the Phase 6 stub harness.

## Ready for Execute

Fully scaffolded:
- **P6-1:** Ruff lint/format cleanup — 2 stubs in `test_phase6_exit.py`
- **P6-2:** Mypy cleanup — 1 stub in `test_phase6_exit.py`
- **P6-3:** Full-suite verification — 1 orchestration stub plus existing suite references
- **P6-4:** JIT budget compliance — fully covered by `test_einsum.py`, no new stub needed
- **P6-5:** Dead-code / TODO / skip cleanup — 2 stubs plus partial existing TODO coverage
- **P6-6:** Exit-criteria checklist — partial existing coverage plus 2 report/checklist stubs
- **P6-7:** Sprint 3 handoff — 1 documentation stub in `test_phase6_exit.py`

The phase is ready for `/Aut_Faciam exec 6 dev/plans/sprint3.md`.
