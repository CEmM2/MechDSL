# Development Task Tracker

> ⚠️ **Superseded** — the active execution source is [`tasks-tracker_recovery_plan_latex_contract.md`](tasks-tracker_recovery_plan_latex_contract.md), driven by [`dev/plans/recovery_plan_latex_contract.md`](../plans/recovery_plan_latex_contract.md). This tracker is retained for historical reference only (Phase 7 / R6 archival, P7-5).

Generated on: 2026-04-08
This tracker records execution status for the Sprint 3 task set.

## Sprint 3 Tracker

Plan source: `dev/plans/sprint3.md`
Task index: `dev/tasks/sprint3/all-tasks.md`

| Task ID | Title | Status | Owner | Blocked by (open) | Blocks | Plan lines | PR/Commit | Verified by | Completed on |
|---|---|---|---|---|---|---|---|---|---|
| P1-1 | Upgrade cantilever to 40x8x4 mesh, 5% EB tolerance | done | agent | -- | P4-1 | 33-45 | sprint3_phase-1 | test_benchmarks.py | 2026-04-08 |
| P1-2 | Add 4-level MMS convergence test [2,4,8,16] | done | agent | -- | P4-1 | 47-51 | sprint3_phase-1 | test_convergence.py | 2026-04-08 |
| P1-3 | Add @pytest.mark.e2e to TestTaskP3T5 | done | agent | -- | P4-1 | 36 | sprint3_phase-1 | test_patch_test.py | 2026-04-08 |
| P1-4 | Add 30-degree finite rotation test | done | agent | -- | P4-1 | 37 | sprint3_phase-1 | test_benchmarks.py | 2026-04-08 |
| P2-1 | Implement generate_cook_membrane_mesh() | done | agent | -- | P2-2, P2-3, P5-2 | 77, 81-85 | sprint3_phase-2 | test_mesh_io.py::TestCookMembraneGeometry (6/6) | 2026-04-09 |
| P2-2 | Test trapezoidal mesh geometry | done | agent | -- | P2-3 | 78 | sprint3_phase-2 | test_mesh_io.py::TestCookMembraneGeometry (8/8) | 2026-04-09 |
| P2-3 | Cook's membrane benchmark with J2 and reference | done | agent | -- | P4-1 | 79, 87-95 | sprint3_phase-2 | test_benchmarks.py::TestCooksMembrane (4/4) | 2026-04-09 |
| P3-1 | Implement necking bar mesh generator | done | agent | -- | P3-2, P3-3, P3-4, P5-2 | 121, 126-130 | sprint3_phase-3 (8e95b96) | test_mesh_io.py::TestNeckingBarGeometry (8/8) | 2026-04-09 |
| P3-2 | Test necking bar mesh geometry | done | agent | -- | P3-4 | 122 | sprint3_phase-3 (8e95b96) | test_mesh_io.py::TestNeckingBarGeometry (8/8) | 2026-04-09 |
| P3-3 | Generate self-converged reference data | done | agent | -- | P3-4 | 123, 132-135 | sprint3_phase-3 | test_artifacts.py::TestGoldenNeckingBarMatches (3/3) | 2026-04-10 |
| P3-4 | Necking bar benchmark with 2% comparison | done | agent | -- | P4-1 | 124, 137-145 | sprint3_phase-3 (59893b6) | test_benchmarks.py::TestNeckingBar (4/4) | 2026-04-12 |
| P4-1 | Create test_full_pipeline.py (all 6 layers) | done | agent | -- | P4-2 | 171, 175-186 | SOSOVSKI/sprint3-phase4 (8d0758c) | test_full_pipeline.py (2/2), -m e2e collect-only | 2026-04-12 |
| P4-2 | Add nightly e2e schedule to CI | done | agent | -- | P4-3 | 172, 188-192 | SOSOVSKI/sprint3-phase4 (a1e661c) | test_ci_config.py::TestCIConfig (2/2), ci.yml parse | 2026-04-12 |
| P4-3 | Implement failure protocol | done | agent | -- | -- | 173, 194-196 | SOSOVSKI/sprint3-phase4 (04d613d) | test_ci_config.py::TestCIFailureProtocol (2/2), test_ci_config.py (4/4) | 2026-04-12 |
| P5-1 | Update README | done | agent | -- | -- | 221 | SOSOVSKI/sprint3-phase4 (673c38a) | test_documentation.py::TestTaskP5T1 (3/3) | 2026-04-12 |
| P5-2 | Create 5 example Python scripts | done | agent | -- | -- | 222, 227 | SOSOVSKI/sprint3-phase4 (673c38a) | test_frontend_build_context.py::TestBuildContextBasics (2/2), test_compile_pipeline.py::TestCompilePipeline (6/6), test_documentation.py::TestTaskP5T2 (15/15) | 2026-04-12 |
| P5-3 | Add docstrings to public API | done | agent | -- | -- | 223 | SOSOVSKI/sprint3-phase4 (673c38a) | test_documentation.py::TestTaskP5T3 (5/5) | 2026-04-12 |
| P5-4 | Update CHANGELOG for MVP | done | agent | -- | -- | 224 | SOSOVSKI/sprint3-phase4 (673c38a) | test_documentation.py::TestTaskP5T4 (1/1) | 2026-04-12 |
| P5-5 | Review UnsupportedError messages | done | agent | -- | -- | 225 | SOSOVSKI/sprint3-phase4 (673c38a) | test_frontend_build_context.py::TestBuildContextValidation (5/5), test_mechanics_ir.py::TestInvalidFormulation::test_formulation_guard_message (1/1), test_localise.py::TestIncompatibleFormulation::test_non_tl_rejected (1/1), test_documentation.py::TestTaskP5T5 (1/1) | 2026-04-12 |
| P6-1 | Ruff lint and format pass | done | agent | -- | P6-3 | 247 | SOSOVSKI/phase6-exec | ruff check packages/, ruff format --check packages/, test_phase6_exit.py::TestTaskP6T1 (2/2) | 2026-04-12 |
| P6-2 | Mypy type checking pass | done | agent | -- | P6-3 | 248 | SOSOVSKI/phase6-exec | mypy packages/mechdsl-core/src/mechdsl/, test_phase6_exit.py::TestTaskP6T2 (1/1) | 2026-04-12 |
| P6-3 | Full test suite zero failures | done | agent | -- | P6-6 | 249 | SOSOVSKI/phase6-exec | pytest --tb=short -q (1014/1014), test_phase6_exit.py::TestTaskP6T3 (1/1) | 2026-04-12 |
| P6-4 | JIT budget compliance check | done | agent | -- | P6-6 | 250 | SOSOVSKI/phase6-exec | test_einsum.py -k budget (9/9) | 2026-04-12 |
| P6-5 | Remove dead code and resolved TODOs | done | agent | -- | P6-6 | 251 | SOSOVSKI/phase6-exec | cleanup scan (intentional markers only), test_phase6_exit.py::TestTaskP6T5 (2/2) | 2026-04-12 |
| P6-6 | Verify all Sprint 3 exit criteria | done | agent | -- | P6-7 | 252, 255-265 | SOSOVSKI/phase6-exec | test_patch_test.py::TestTaskP3T5 (2/2), test_benchmarks.py target bundle (19/19), test_convergence.py -k 4level (2/2), test_full_pipeline.py (2/2), test_ci_config.py (4/4), test_documentation.py (25/25), test_phase6_exit.py::TestTaskP6T6 (2/2) | 2026-04-12 |
| P6-7 | Sprint 3 handoff document | done | agent | -- | -- | 253 | SOSOVSKI/phase6-exec | test_phase6_exit.py::TestTaskP6T7 (1/1) | 2026-04-12 |


## Update protocol

1. When a task starts, set `Status` to `in_progress`, assign `Owner`, and keep unresolved blockers in `Blocked by (open)`.
2. When a task is done, set `Status` to `done`, fill `PR/Commit`, `Verified by`, and `Completed on` (YYYY-MM-DD).
3. For each newly completed task, remove its ID from downstream rows in `Blocked by (open)` when applicable.

## Verification status

### Phase 1 aggregate verification:

#### Phase 1 mapping between test and task:

| Task ID | Title | Test file |
|---|---|---|
| P1-1 | Upgrade cantilever | tests/test_benchmarks.py |
| P1-2 | MMS 4-level convergence | tests/test_convergence.py |
| P1-3 | Add e2e marker | tests/test_patch_test.py |
| P1-4 | 30-degree rotation test | tests/test_benchmarks.py |

#### Existing test coverage (from scaffold):

| Task ID | Case | Status | Existing test |
|---|---|---|---|
| P1-1 | test_tip_displacement_within_5_percent on 40x8x4 | missing | -- |
| P1-1 | Existing coarse-mesh tests unbroken | covered | TestCantilever (5 methods) |
| P1-2 | test_mms_4level_convergence [2,4,8,16] | missing | -- (existing uses [2,3,4]) |
| P1-3 | Verify e2e marker via --collect-only | covered | TestTaskP3T5 exists, needs marker |
| P1-4 | test_finite_rotation_30_degrees multi-element | missing | test_patch_test.py has equivalent |

#### Verification outcomes:

    `uv run pytest packages/mechdsl-core/tests/test_benchmarks.py::TestCantilever -v` -> 6 collected (fast tests pass, e2e test collects)
    `uv run pytest packages/mechdsl-core/tests/test_convergence.py -k 4level --collect-only -q` -> 2 tests collected
    `uv run pytest packages/mechdsl-core/tests/test_patch_test.py::TestTaskP3T5 -m e2e --collect-only -q` -> 2/14 collected
    `uv run pytest packages/mechdsl-core/tests/test_benchmarks.py::TestRigidBodyMotion -v` -> 5/5 passed
    `uv run pytest packages/mechdsl-core/tests/ -m "not slow and not gpu and not e2e" -q` -> 803/803 passed

### Phase 2 aggregate verification:

#### Phase 2 mapping between test and task:

| Task ID | Title | Test file |
|---|---|---|
| P2-1 | Cook's membrane mesh | tests/test_mesh_io.py::TestCookMembraneGeometry |
| P2-2 | Mesh geometry tests | tests/test_mesh_io.py::TestCookMembraneGeometry |
| P2-3 | Cook's benchmark | tests/test_benchmarks.py::TestCooksMembrane |

#### Existing test coverage (from scaffold):

| Task ID | Case | Status | Existing test |
|---|---|---|---|
| P2-1 | Corner coordinates match trapezoid | missing | -- (stub: TestCookMembraneGeometry::test_corner_coordinates_match_trapezoid) |
| P2-1 | Boundary tags present | missing | -- (stub: TestCookMembraneGeometry::test_boundary_tags_present_and_nonempty) |
| P2-1 | Node and element counts | missing | -- (stub: TestCookMembraneGeometry::test_node_and_element_counts) |
| P2-2 | Cook membrane mesh geometry | missing | -- (covered by P2-1 stubs above) |
| P2-3 | Reference comparison 2% | partial | TestCooksMembrane::test_reference_comparison (skipped) |
| P2-3 | Newton convergence all steps | covered | TestCooksMembrane::test_newton_converges (elastic, needs plastic) |
| P2-3 | Tip displacement direction | covered | TestCooksMembrane::test_displacement_direction (elastic, needs plastic) |

#### Verification outcomes:

    `uv run pytest packages/mechdsl-core/tests/test_mesh_io.py::TestCookMembraneGeometry -v` -> pending (stubs skip)
    `uv run pytest packages/mechdsl-core/tests/test_benchmarks.py -k "cook" -v` -> pending

### Phase 3 aggregate verification:

#### Phase 3 mapping between test and task:

| Task ID | Title | Test file |
|---|---|---|
| P3-1 | Necking bar mesh generator | tests/test_mesh_io.py::TestNeckingBarGeometry |
| P3-2 | Mesh geometry tests | tests/test_mesh_io.py::TestNeckingBarGeometry |
| P3-3 | Reference data generation | tests/test_artifacts.py::TestGoldenFilesExist, TestGoldenNeckingBarMatches |
| P3-4 | Necking bar benchmark | tests/test_benchmarks.py::TestNeckingBar |

#### Existing test coverage (from scaffold):

| Task ID | Case | Status | Existing test |
|---|---|---|---|
| P3-1 | Verify geometry dimensions | missing | -- (stub: TestNeckingBarGeometry::test_geometry_dimensions) |
| P3-1 | Verify imperfection at z=L/2 | missing | -- (stub: TestNeckingBarGeometry::test_imperfection_reduces_cross_section) |
| P3-1 | Verify boundary tags | missing | -- (stub: TestNeckingBarGeometry::test_boundary_tags_symmetry_faces) |
| P3-2 | Geometry and imperfection | missing | -- (merged with P3-1 stubs above) |
| P3-3 | Golden file exists | missing | -- (stub: TestGoldenFilesExist::test_golden_necking_bar_exists) |
| P3-3 | Golden file keys | missing | -- (stub: TestGoldenNeckingBarMatches::test_golden_necking_bar_keys) |
| P3-3 | Convergence at all steps | missing | -- (stub: TestGoldenNeckingBarMatches::test_golden_necking_bar_convergence) |
| P3-4 | Reference comparison 2% | partial | TestNeckingBar::test_reference_comparison (skipped) |
| P3-4 | Newton convergence all steps | partial | TestNeckingBar::test_newton_converges_all_steps (5 steps, needs 20) |
| P3-4 | Plastic deformation occurs | covered | TestNeckingBar::test_plastic_deformation_occurs |
| P3-4 | Load-displacement monotonic | covered | TestNeckingBar::test_load_displacement_monotonic |

#### Verification outcomes:

    `uv run pytest packages/mechdsl-core/tests/test_mesh_io.py::TestNeckingBarGeometry -v` -> 8/8 passed (P3-1, P3-2)
    `uv run pytest packages/mechdsl-core/tests/test_artifacts.py::TestGoldenNeckingBarMatches tests/test_artifacts.py::TestGoldenFilesExist::test_golden_necking_bar_exists -v` -> 3/3 passed (P3-3)
    `uv run pytest packages/mechdsl-core/tests/test_benchmarks.py::TestNeckingBar -v` -> pending (P3-4)
    `uv run pytest -m "not slow and not gpu and not e2e" -q` -> 867 passed, 62 deselected, 0 failed

### Phase 4 aggregate verification:

#### Phase 4 mapping between test and task:

| Task ID | Title | Test file | Stub file | Coverage from scaffold |
|---|---|---|---|---|
| P4-1 | Create test_full_pipeline.py (all 6 layers) | packages/mechdsl-core/tests/test_full_pipeline.py | packages/mechdsl-core/tests/test_full_pipeline.py (new, 2 stubs) | missing (test_e2e.py starts from ProblemIR, skips frontend.build_context) |
| P4-2 | Add nightly e2e schedule to CI | packages/mechdsl-core/tests/test_ci_config.py | packages/mechdsl-core/tests/test_ci_config.py::TestCIConfig (new, 2 stubs) | missing (no test parsed .github/workflows/ci.yml) |
| P4-3 | Implement failure protocol | packages/mechdsl-core/tests/test_ci_config.py | packages/mechdsl-core/tests/test_ci_config.py::TestCIFailureProtocol (new, 2 stubs) | missing (no test covered continue-on-error / actions/github-script) |

#### Existing test coverage (from scaffold):

| Task ID | Test case | Existing test file | Function | Coverage |
|---|---|---|---|---|
| P4-1 | test_elastic_full_pipeline | packages/mechdsl-core/tests/test_e2e.py:105 | TestArtifactBundle.test_elastic_pipeline | partial (starts from ProblemIR, no frontend.build_context, no golden comparison) |
| P4-1 | test_plastic_full_pipeline | packages/mechdsl-core/tests/test_e2e.py:153 | TestArtifactBundle.test_plastic_pipeline | partial (starts from ProblemIR, no frontend.build_context, no golden comparison) |
| P4-2 | Verify YAML syntax is valid | -- | -- | missing |
| P4-2 | Verify job filters are correct | -- | -- | missing |
| P4-3 | Verify YAML configuration is correct | -- | -- | missing |

#### Verification outcomes:

    `uv run pytest packages/mechdsl-core/tests/test_full_pipeline.py -v` -> pending
    `uv run pytest packages/mechdsl-core/tests/test_full_pipeline.py::TestFullPipeline::test_elastic_full_pipeline -v` -> pending
    `uv run pytest packages/mechdsl-core/tests/test_full_pipeline.py::TestFullPipeline::test_plastic_full_pipeline -v` -> pending
    `uv run pytest packages/mechdsl-core/tests/test_ci_config.py::TestCIConfig -v` -> pending
    `uv run pytest packages/mechdsl-core/tests/test_ci_config.py::TestCIFailureProtocol -v` -> pending
    `uv run pytest packages/mechdsl-core/tests/ -m e2e --collect-only -q` -> pending

### Phase 5 aggregate verification:

#### Phase 5 mapping between test and task:

| Task ID | Title | Test file |
|---|---|---|
| P5-1 | Update README | packages/mechdsl-core/tests/test_documentation.py::TestTaskP5T1 |
| P5-2 | Create 5 example Python scripts | packages/mechdsl-core/tests/test_documentation.py::TestTaskP5T2 |
| P5-3 | Add docstrings to public API | packages/mechdsl-core/tests/test_documentation.py::TestTaskP5T3 |
| P5-4 | Update CHANGELOG for MVP | packages/mechdsl-core/tests/test_documentation.py::TestTaskP5T4 |
| P5-5 | Review UnsupportedError messages | packages/mechdsl-core/tests/test_documentation.py::TestTaskP5T5 |

#### Existing test coverage (from scaffold):

| Task ID | Case | Status | Existing test |
|---|---|---|---|
| P5-1 | README installation section | missing | -- |
| P5-1 | README quickstart section | missing | -- |
| P5-1 | README architecture overview + design doc links | missing | -- |
| P5-2 | Example scripts exist | missing | -- |
| P5-2 | Example scripts use build_context() + compile() | partial | test_frontend_build_context.py::TestBuildContextBasics, test_compile_pipeline.py::TestCompilePipeline |
| P5-2 | Example scripts run under uv | missing | -- |
| P5-3 | Public API docstrings are complete and numpy-style | missing | -- |
| P5-4 | CHANGELOG has MVP release entry | missing | -- |
| P5-5 | Plan B phase references are correct across targeted files | partial | test_frontend_build_context.py::TestBuildContextValidation, test_mechanics_ir.py::TestInvalidFormulation::test_formulation_guard_message, test_localise.py::TestIncompatibleFormulation::test_non_tl_rejected |

#### Verification outcomes:

    `uv run pytest packages/mechdsl-core/tests/test_documentation.py --collect-only -q` -> 25 tests collected
    `uv run pytest packages/mechdsl-core/tests/test_frontend_build_context.py::TestBuildContextBasics -v` -> 2/2 passed
    `uv run pytest packages/mechdsl-core/tests/test_compile_pipeline.py::TestCompilePipeline -v` -> 6/6 passed
    `uv run pytest packages/mechdsl-core/tests/test_frontend_build_context.py::TestBuildContextValidation -v` -> 5/5 passed
    `uv run pytest packages/mechdsl-core/tests/test_mechanics_ir.py::TestInvalidFormulation::test_formulation_guard_message -v` -> 1/1 passed
    `uv run pytest packages/mechdsl-core/tests/test_localise.py::TestIncompatibleFormulation::test_non_tl_rejected -v` -> 1/1 passed
    `uv run pytest packages/mechdsl-core/tests/test_documentation.py::TestTaskP5T1 -v` -> 3/3 passed
    `uv run pytest packages/mechdsl-core/tests/test_documentation.py::TestTaskP5T2 -v` -> 15/15 passed
    `uv run pytest packages/mechdsl-core/tests/test_documentation.py::TestTaskP5T3 -v` -> 5/5 passed
    `uv run pytest packages/mechdsl-core/tests/test_documentation.py::TestTaskP5T4 -v` -> 1/1 passed
    `uv run pytest packages/mechdsl-core/tests/test_documentation.py::TestTaskP5T5 -v` -> 1/1 passed
    `uv run pytest packages/mechdsl-core/tests/test_documentation.py -v` -> 25/25 passed
    `uv run ruff check dev/examples ... test_documentation.py ...` -> passed

### Phase 6 aggregate verification:

#### Phase 6 mapping between test and task:

| Task ID | Title | Test file | Stub file | Coverage from scaffold |
|---|---|---|---|---|
| P6-1 | Ruff lint and format pass | -- (tooling commands only) | packages/mechdsl-core/tests/test_phase6_exit.py::TestTaskP6T1 | missing (no dedicated pytest wrapper existed for lint/format cleanliness) |
| P6-2 | Mypy type checking pass | -- (tooling commands only) | packages/mechdsl-core/tests/test_phase6_exit.py::TestTaskP6T2 | missing |
| P6-3 | Full test suite zero failures | packages/mechdsl-core/tests/test_benchmarks.py, test_convergence.py, test_full_pipeline.py, test_ci_config.py, test_documentation.py, packages/algo2code/tests/test_end_to_end.py | packages/mechdsl-core/tests/test_phase6_exit.py::TestTaskP6T3 | partial (constituent suites exist; no Phase 6 orchestration/report test yet) |
| P6-4 | JIT budget compliance check | packages/mechdsl-core/tests/test_einsum.py::TestBudgetRegressionMVP | -- | covered |
| P6-5 | Remove dead code and resolved TODOs | packages/mechdsl-core/tests/test_emission_verification.py | packages/mechdsl-core/tests/test_phase6_exit.py::TestTaskP6T5 | partial (one emitted-code TODO check exists; repo-wide cleanup proof missing) |
| P6-6 | Verify all Sprint 3 exit criteria | packages/mechdsl-core/tests/test_patch_test.py, test_benchmarks.py, test_convergence.py, test_full_pipeline.py, test_ci_config.py, test_documentation.py | packages/mechdsl-core/tests/test_phase6_exit.py::TestTaskP6T6 | partial (underlying checks exist; final checklist/report wrapper missing) |
| P6-7 | Sprint 3 handoff document | -- | packages/mechdsl-core/tests/test_phase6_exit.py::TestTaskP6T7 | missing |

#### Existing test coverage (from scaffold):

| Task ID | Case | Status | Existing test |
|---|---|---|---|
| P6-3 | Full workspace suite exercises Sprint 3 functionality | partial | test_benchmarks.py, test_convergence.py, test_full_pipeline.py, test_ci_config.py, test_documentation.py, packages/algo2code/tests/test_end_to_end.py |
| P6-4 | Budget regression suite stays within JIT limits | covered | test_einsum.py::TestBudgetRegressionMVP |
| P6-5 | No placeholder TODOs remain in emitted SVK constitutive path | partial | test_emission_verification.py::TestEmissionVerification::test_no_placeholder_todos_in_svk |
| P6-6 | Patch and rigid-body evidence exists | covered | test_patch_test.py::TestTaskP3T5 |
| P6-6 | Cantilever / Cook's / necking benchmark evidence exists | covered | test_benchmarks.py::TestCantilever, TestCooksMembrane, TestNeckingBar |
| P6-6 | MMS convergence evidence exists | covered | test_convergence.py::TestTaskP1T2 |
| P6-6 | Full pipeline evidence exists | covered | test_full_pipeline.py::TestFullPipeline |
| P6-6 | CI tier evidence exists | covered | test_ci_config.py::TestCIConfig, TestCIFailureProtocol |
| P6-6 | Documentation/example/docstring evidence exists | covered | test_documentation.py::TestTaskP5T1..P5T5 |

#### Verification outcomes:

    `uv run pytest packages/mechdsl-core/tests/test_phase6_exit.py --collect-only -q` -> 9 tests collected in 0.01s
    `uv run ruff check packages/` -> pending
    `uv run ruff format --check packages/` -> pending
    `uv run mypy packages/mechdsl-core/src/mechdsl/` -> pending
    `uv run pytest --tb=short -q` -> pending
    `uv run pytest packages/mechdsl-core/tests/test_einsum.py -k budget -v` -> pending
    `rg -n "TODO|FIXME|pytest\.skip\(" packages/mechdsl-core README.md CHANGELOG.md dev/examples .github/workflows/ci.yml` -> pending
    `uv run pytest packages/mechdsl-core/tests/test_patch_test.py::TestTaskP3T5 -v` -> pending
    `uv run pytest packages/mechdsl-core/tests/test_benchmarks.py::TestRigidBodyMotion packages/mechdsl-core/tests/test_benchmarks.py::TestCantilever packages/mechdsl-core/tests/test_benchmarks.py::TestCooksMembrane packages/mechdsl-core/tests/test_benchmarks.py::TestNeckingBar -v` -> pending
    `uv run pytest packages/mechdsl-core/tests/test_convergence.py -k 4level -v` -> pending
    `uv run pytest packages/mechdsl-core/tests/test_full_pipeline.py -v` -> pending
    `uv run pytest packages/mechdsl-core/tests/test_ci_config.py -v` -> pending
    `uv run pytest packages/mechdsl-core/tests/test_documentation.py -v` -> pending
