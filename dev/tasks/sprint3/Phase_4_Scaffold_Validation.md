# Phase 4 Scaffold Validation

Scaffold pass for Sprint 3 Phase 4 (Full Pipeline Test & CI Nightly).
Generated: 2026-04-10

| Task ID | Title | Missing / Incomplete Fields | Scaffold Action |
|---------|-------|-----------------------------|-----------------|
| P4-1 | Create test_full_pipeline.py exercising all 6 compiler layers | `test_artifacts=[""]`, `verification_commands=[""]`, `risks=[]` | auto-filled |
| P4-2 | Add nightly e2e schedule to CI | `test_artifacts=[""]`, `verification_commands=[""]`, `risks=[]` | auto-filled |
| P4-3 | Implement failure protocol (benchmark regressions create issues) | `test_artifacts=[""]`, `verification_commands=[""]`, `risks=[]`, `plan_assets=[]` | auto-filled (plan_assets left empty -- plan lines 194-196 are prose-only, no code/equation/table/diagram to cite) |

## Scaffold Summary

| Metric | Value |
|--------|-------|
| Tasks scaffolded | 3 |
| Test cases assessed | 5 (2 for P4-1, 2 for P4-2, 1 for P4-3) |
| Cases covered by existing tests | 0 |
| Cases partially covered (stubs generated) | 2 (both P4-1 cases — test_e2e.py exercises the post-frontend pipeline only) |
| Cases with no existing tests (stubs generated) | 3 (both P4-2 cases and the P4-3 case) |
| New stub files created | 2 (test_full_pipeline.py, test_ci_config.py) |
| Total new stubs generated | 6 |
| Tasks fully covered by existing tests (no stub needed) | 0 |
| Tasks needing human review | 0 |
| Auto-filled fields | `test_plan.tier`, `test_plan.cases`, `test_artifacts`, `verification_commands`, `risks` |

## Existing Test Coverage Found

| Task ID | Test case | Existing test file | Function | Coverage |
|---------|-----------|-------------------|----------|----------|
| P4-1 | test_elastic_full_pipeline | packages/mechdsl-core/tests/test_e2e.py:105 | TestArtifactBundle.test_elastic_pipeline | partial -- starts from ProblemIR (skips Layer 1 `frontend.build_context`), no golden file comparison, not marked e2e |
| P4-1 | test_plastic_full_pipeline | packages/mechdsl-core/tests/test_e2e.py:153 | TestArtifactBundle.test_plastic_pipeline | partial -- starts from ProblemIR, no golden file comparison, not marked e2e |
| P4-2 | test_ci_yaml_is_valid | -- | -- | missing -- no existing test parses `.github/workflows/ci.yml` |
| P4-2 | test_ci_tier_filters_are_correct | -- | -- | missing |
| P4-3 | Verify YAML configuration is correct | -- | -- | missing |

Both P4-1 stubs generate a new `test_full_pipeline.py` because the plan explicitly requires a new test file that exercises all 6 layers end-to-end (including `frontend.build_context()` and golden comparison). `test_e2e.py::TestArtifactBundle` can be reused as a pattern source (the `_make_elastic_problem_ir` / `_make_plastic_problem_ir` helpers) but does not replace the new test.

## Stub Files Generated

| File | New? | Classes | Stubs |
|------|------|---------|-------|
| `packages/mechdsl-core/tests/test_full_pipeline.py` | yes | `TestFullPipeline` | `test_elastic_full_pipeline`, `test_plastic_full_pipeline` (both `@pytest.mark.e2e`) |
| `packages/mechdsl-core/tests/test_ci_config.py` | yes | `TestCIConfig`, `TestCIFailureProtocol` | `test_ci_yaml_is_valid`, `test_ci_tier_filters_are_correct`, `test_benchmark_step_has_continue_on_error`, `test_github_script_issue_creation_step_present` |

All 6 stubs call `pytest.skip("stub -- implement after Task P4-X is complete")` and collect cleanly under pytest (verified via `--collect-only`, 6 tests collected in 0.01s).

## Tasks Needing Human Review Before Execute

None. All three tasks have populated `objective`, `acceptance_criteria`, `implementation_steps`, and `deliverables`; scaffold only auto-filled testing-related fields.

## Ready for Execute

Fully scaffolded:
- **P4-1:** Create `test_full_pipeline.py` (all 6 layers, elastic + plastic) — integration tier, 2 stubs in new file
- **P4-2:** Add nightly e2e schedule to CI — unit tier, 2 stubs in new `test_ci_config.py::TestCIConfig`
- **P4-3:** Implement failure protocol — unit tier, 2 stubs appended as `test_ci_config.py::TestCIFailureProtocol`

All stubs collect under pytest; the phase is ready for `/Aut_Faciam exec 4 dev/plans/sprint3.md` once blockers (P3-4 tracker sync) are cleared.

## Notes and Caveats

1. **P3-4 tracker lag:** The tracker still shows `P3-4: pending` though the necking bar benchmark landed in commit `59893b6`. ScaffoldPhase does not touch blocker state — this will resolve when Phase 3 ExecPhase finalizes (or manually in the tracker) before Phase 4 execution starts.
2. **P4-1 is heavy:** The 6-layer test will take longer than current `test_e2e.py` cases (golden comparison + `frontend.build_context` overhead) — marked `@pytest.mark.e2e` by design.
3. **P4-2 / P4-3 test harness choice:** CI-config tests live inside `packages/mechdsl-core/tests/test_ci_config.py` rather than a new root-level `tests/` directory, so they run under the existing uv workspace harness without extra plumbing.
