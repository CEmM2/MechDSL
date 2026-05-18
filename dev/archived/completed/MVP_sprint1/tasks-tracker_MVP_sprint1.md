# MechDSL Development Task Tracker

> ⚠️ **Superseded** — the active execution source is [`tasks-tracker_recovery_plan_latex_contract.md`](tasks-tracker_recovery_plan_latex_contract.md), driven by [`dev/plans/recovery_plan_latex_contract.md`](../plans/recovery_plan_latex_contract.md). This tracker is retained for historical reference only (Phase 7 / R6 archival, P7-5).

Generated on: 2026-04-03
This tracker records execution status for the MVP Sprint 1 — Core Runtime Loop task set.

## MVP Sprint 1 Tracker

Plan source: `.claude/plans/serialized-booping-quokka.md`
Task index: `dev/tasks/MVP_sprint1/all-tasks.md`

| Task ID | Title | Status | Owner | Blocked by (open) | Blocks | Plan lines | PR/Commit | Verified by | Completed on |
|---|---|---|---|---|---|---|---|---|---|
| P1-T1 | Implement ConstitutiveModel ABC | done | claude | — | P1-T2, P1-T3 | 17–38 | sprint1_phase-1 | test_smoke.py (10/10), import check | 2026-04-03 |
| P1-T2 | Add SVKModel wrapper class | done | claude | — | P1-T4, P1-T5 | 42–46 | sprint1_phase-1 | test_svk.py (18/18), test_constitutive_abc.py::TestSVKModelWrapper (5/5) | 2026-04-03 |
| P1-T3 | Add J2Model wrapper class | done | claude | — | P1-T4, P1-T5 | 48–53 | sprint1_phase-1 | test_j2.py (28/28), test_constitutive_abc.py::TestJ2ModelWrapper (5/5) | 2026-04-03 |
| P1-T4 | Update fe_localise model validation | done | claude | — | — | 55–59 | sprint1_phase-1 | test_localise.py (28/28), test_localise_model_validation.py (3/3) | 2026-04-03 |
| P1-T5 | Write constitutive ABC tests | done | claude | — | — | 61–68 | sprint1_phase-1 | test_constitutive_abc.py (16/16), test_localise_model_validation.py (3/3) | 2026-04-03 |
| P2-T1 | Implement extract_einsum_specs() | done | claude | — | P2-T2 | 77–89 | sprint1_phase-2 | import check, smoke (10/10) | 2026-04-03 |
| P2-T2 | Refactor fe_localise + update exports | done | claude | — | P2-T3, P4-T1 | 91–101 | sprint1_phase-2 | test_localise (28/28), test_e2e (26/26), test_einsum (26/26), test_einsum_optimizer (16/16) | 2026-04-03 |
| P2-T3 | Write einsum extraction tests | done | claude | — | — | 104–112 | sprint1_phase-2 | test_einsum_extract.py (9/9) | 2026-04-03 |
| P3-T1 | Implement newton_solve() | done | claude | — | P3-T2, P3-T3 | 120–184 | sprint1_phase-3 | import check, smoke (10/10) | 2026-04-03 |
| P3-T2 | Newton driver unit tests | done | claude | — | P6-T1 | 188–191 | sprint1_phase-3 | test_newton.py::TestNewtonSolveUnit (5/5) | 2026-04-03 |
| P3-T3 | Newton + load_stepping integration test | done | claude | — | P6-T1 | 192–193 | sprint1_phase-3 | test_newton.py::TestNewtonLoadSteppingIntegration (2/2), match ref < 1e-10 | 2026-04-03 |
| P4-T1 | Implement compile() and top-level export | done | claude | — | P4-T2 | 201–226 | sprint1_phase-4 | import check, smoke+e2e (24/24) | 2026-04-04 |
| P4-T2 | Write compile pipeline tests | done | claude | — | P5-T1 | 228–234 | sprint1_phase-4 | test_compile_pipeline.py (9/9) | 2026-04-04 |
| P5-T1 | Rename emit stub + add emit_postprocess() | done | claude | — | P5-T2 | 242–264 | sprint1_phase-5 | test_emission_phase5.py::TestEmitPostprocess (2/2), test_taichi_printer.py (25/25) | 2026-04-04 |
| P5-T2 | Add emit_main() function | done | claude | — | P5-T3 | 249–257 | sprint1_phase-5 | test_emission_phase5.py::TestEmitMain (2/2) | 2026-04-04 |
| P5-T3 | Update emit() chain, regen golden files, tests | done | claude | — | P6-T1 | 267–284 | sprint1_phase-5 | test_emission_phase5.py (6/6), test_codegen (53/53), test_emission_verification (80/80) | 2026-04-04 |
| P6-T1 | Create E2E Taichi smoke test | done | claude | — | P6-T2 | 292–313 | sprint1_phase-6 | test_e2e_taichi.py (2/2), 740/740 fast regression | 2026-04-04 |
| P6-T2 | CI integration for slow tests | done | claude | — | — | 315–318 | sprint1_phase-6 | pyproject.toml markers, ci.yml slow-tests job | 2026-04-04 |


## Update protocol

1. When a task starts, set `Status` to `in_progress`, assign `Owner`, and keep unresolved blockers in `Blocked by (open)`.
2. When a task is done, set `Status` to `done`, fill `PR/Commit`, `Verified by`, and `Completed on` (YYYY-MM-DD).
3. For each newly completed task, remove its ID from downstream rows in `Blocked by (open)` when applicable.

## Verification status

### Phase 1 aggregate verification:

#### Phase 1 mapping between test and task:

| Task ID | Title | Test file | Stubs |
|---|---|---|---|
| P1-T1 | Implement ConstitutiveModel ABC | `tests/test_constitutive_abc.py::TestConstitutiveModelABC` | 3 |
| P1-T2 | Add SVKModel wrapper class | `tests/test_constitutive_abc.py::TestSVKModelWrapper` | 5 |
| P1-T3 | Add J2Model wrapper class | `tests/test_constitutive_abc.py::TestJ2ModelWrapper` | 5 |
| P1-T4 | Update fe_localise model validation | `tests/test_localise_model_validation.py::TestModelStringValidation` | 3 |
| P1-T5 | Write constitutive ABC tests | `tests/test_constitutive_abc.py::TestConstitutiveABCIntegration` | 3 |

#### Verification outcomes:

    `uv run pytest packages/mechdsl-core/tests/test_constitutive_abc.py packages/mechdsl-core/tests/test_localise_model_validation.py -v` -> 19/19 passed (2026-04-03)

### Phase 2 aggregate verification:

#### Phase 2 mapping between test and task:

| Task ID | Title | Test file | Stubs |
|---|---|---|---|
| P2-T1 | Implement extract_einsum_specs() | `tests/test_einsum_extract.py::TestExtractEinsumSpecs` | 6 |
| P2-T2 | Refactor fe_localise + update exports | `tests/test_localise.py`, `tests/test_e2e.py`, `tests/test_einsum.py` (regression) | 0 |
| P2-T3 | Write einsum extraction tests | `tests/test_einsum_extract.py::TestEinsumExtractionRegression` | 3 |

#### Verification outcomes:

    `uv run pytest packages/mechdsl-core/tests/test_einsum_extract.py -v` -> 9/9 passed (2026-04-03)

### Phase 3 aggregate verification:

#### Phase 3 mapping between test and task:

| Task ID | Title | Test file | Stubs |
|---|---|---|---|
| P3-T1 | Implement newton_solve() | `tests/test_newton.py::TestNewtonSolveImport` | 3 |
| P3-T2 | Newton driver unit tests | `tests/test_newton.py::TestNewtonSolveUnit` | 5 |
| P3-T3 | Newton + load_stepping integration test | `tests/test_newton.py::TestNewtonLoadSteppingIntegration` | 2 |

#### Verification outcomes:

    `uv run pytest packages/mechdsl-core/tests/test_newton.py -v` -> 10/10 passed (2026-04-03)

### Phase 4 aggregate verification:

#### Phase 4 mapping between test and task:

| Task ID | Title | Test file | Stubs |
|---|---|---|---|
| P4-T1 | Implement compile() | `tests/test_compile_pipeline.py::TestCompileImport` | 2 |
| P4-T2 | Write compile pipeline tests | `tests/test_compile_pipeline.py::TestCompilePipeline` | 6 |

#### Verification outcomes:

    `uv run pytest packages/mechdsl-core/tests/test_compile_pipeline.py -v` -> 9/9 passed (2026-04-04)

### Phase 5 aggregate verification:

#### Phase 5 mapping between test and task:

| Task ID | Title | Test file | Stubs |
|---|---|---|---|
| P5-T1 | Rename emit stub + postprocess | `tests/test_emission_phase5.py::TestEmitPostprocess` | 2 |
| P5-T2 | Add emit_main() | `tests/test_emission_phase5.py::TestEmitMain` | 2 |
| P5-T3 | Wire emit chain + golden files | `tests/test_emission_phase5.py::TestEmitChainWiring` + `tests/test_taichi_printer.py` | 4 |

#### Verification outcomes:

    `uv run pytest packages/mechdsl-core/tests/test_emission_phase5.py -v` -> 6/6 passed (2026-04-04)

### Phase 6 aggregate verification:

#### Phase 6 mapping between test and task:

| Task ID | Title | Test file | Stubs |
|---|---|---|---|
| P6-T1 | E2E Taichi smoke test | `tests/test_e2e_taichi.py::TestE2ETaichiExecution` | 2 |
| P6-T2 | CI integration for slow tests | N/A (CI config task) | 0 |

#### Verification outcomes:

    `uv run pytest packages/mechdsl-core/tests/test_e2e_taichi.py -v -m slow` -> 2/2 passed (2026-04-04)

### Full regression (post-Phase 6):

    `uv run pytest packages/mechdsl-core/tests/ -m 'not slow and not gpu' -x -q` -> 740/740 passed (2026-04-04)

### Full regression:

    `uv run pytest packages/mechdsl-core/tests/ -m 'not slow and not gpu' -x -q` -> 687/687 passed (baseline)
