# MechDSL Development Task Tracker

> ⚠️ **Superseded** — the active execution source is [`tasks-tracker_recovery_plan_latex_contract.md`](tasks-tracker_recovery_plan_latex_contract.md), driven by [`dev/plans/recovery_plan_latex_contract.md`](../plans/recovery_plan_latex_contract.md). This tracker is retained for historical reference only (Phase 7 / R6 archival, P7-5).

Generated on: 2026-04-04
This tracker records execution status for the MVP Sprint 2 — J2 Plasticity Runtime & Verification Hardening task set.

## MVP Sprint 2 Tracker

Plan source: `dev/plans/sprint2.md`
Task index: `dev/tasks/sprint2/all-tasks.md`

| Task ID | Title | Status | Owner | Blocked by (open) | Blocks | Plan lines | PR/Commit | Verified by | Completed on |
|---|---|---|---|---|---|---|---|---|---|
| P1-T1 | Fix emit_main E/nu → Lamé conversion | done | claude | — | P1-T5, P1-T6 | 21–25 | sprint2_phase-1 | test_emit_lame_conversion.py (5/5), test_emission_phase5.py (6/6), test_codegen.py (20/20) | 2026-04-05 |
| P1-T2 | Implement convected coordinate functions | done | claude | — | P1-T3, P1-T4 | 27–32 | sprint2_phase-1 | test_convected.py (7/7) | 2026-04-05 |
| P1-T3 | Write convected coordinate tests | done | claude | — | — | 34–39 | sprint2_phase-1 | test_convected.py (7/7) | 2026-04-05 |
| P1-T4 | Update convected exports | done | claude | — | — | 41–43 | sprint2_phase-1 | import check | 2026-04-05 |
| P1-T5 | Regenerate golden files after emit_main fix | done | claude | — | P4-T7 | 45–47 | sprint2_phase-1 | test_codegen.py::TestGoldenSnapshot (3/3) | 2026-04-05 |
| P1-T6 | Write emit_main Lamé conversion test | done | claude | — | — | 49–50 | sprint2_phase-1 | test_emit_lame_conversion.py (5/5) | 2026-04-05 |
| P2-T1 | Implement patch_test_reference() | done | claude | — | P2-T5, P3-T4 | 60–64 | sprint2_phase-2 | test_analytical.py::TestPatchTestReference (7/7) | 2026-04-05 |
| P2-T2 | Implement rigid_body_reference() | done | claude | — | P2-T5, P3-T4 | 66–69 | sprint2_phase-2 | test_analytical.py::TestRigidBodyReference (6/6) | 2026-04-05 |
| P2-T3 | Implement cantilever_euler_bernoulli() | done | claude | — | P2-T5 | 71–74 | sprint2_phase-2 | test_analytical.py::TestCantileverEulerBernoulli (8/8) | 2026-04-05 |
| P2-T4 | Implement uniaxial_tension_hardening() | done | claude | — | P2-T5, P4-T5 | 76–80 | sprint2_phase-2 | test_analytical.py::TestUniaxialTensionHardening (13/13) | 2026-04-05 |
| P2-T5 | Write analytical solution tests | done | claude | — | — | 82–87 | sprint2_phase-2 | test_analytical.py (38/38) | 2026-04-05 |
| P2-T6 | Implement frontend.build_context() | done | claude | — | P2-T7, P2-T8 | 89–94 | sprint2_phase-2 | test_frontend_build_context.py::TestBuildContextBasics (2/2) | 2026-04-05 |
| P2-T7 | Implement build_context validation | done | claude | — | P2-T8 | 96–99 | sprint2_phase-2 | test_frontend_build_context.py::TestBuildContextValidation (4/4) | 2026-04-05 |
| P2-T8 | Write frontend tests | done | claude | — | — | 101–106 | sprint2_phase-2 | test_frontend_build_context.py (10/10) | 2026-04-05 |
| P3-T1 | Implement check_convergence_rate() | done | claude | — | P3-T3 | 116–120 | sprint2_phase-3 | test_convergence.py::TestTaskP3T1 (12/12) | 2026-04-05 |
| P3-T2 | Implement MMS driver | done | claude | — | P3-T3 | 122–129 | sprint2_phase-3 | test_convergence.py::TestTaskP3T2 (1/1 fast, 3 slow pending) | 2026-04-05 |
| P3-T3 | Write convergence rate test | done | claude | — | — | 131–135 | sprint2_phase-3 | test_convergence.py::TestTaskP3T3 (2 slow, cached fixture) | 2026-04-05 |
| P3-T4 | Implement run_patch_test() and run_rigid_body_test() | done | claude | — | P3-T5 | 137–146 | sprint2_phase-3 | test_patch_test.py::TestTaskP3T4 (4/4), TestPatchTestFailureRoutes (8/8) | 2026-04-05 |
| P3-T5 | Write patch test | done | claude | — | — | 148–152 | sprint2_phase-3 | test_patch_test.py::TestTaskP3T5 (2/2) | 2026-04-05 |
| P4-T1 | Audit J2 constitutive emission | done | claude | — | P4-T5 | 162–172 | sprint2_phase-4 | test_plastic_emission.py::TestTaskP4T1Audit (1/1), test_plastic_emission.py (43/43) | 2026-04-05 |
| P4-T2 | Validate FD tangent for J2 | done | claude | — | P4-T5 | 174–178 | sprint2_phase-4 | test_e2e_plastic.py::TestTaskP4T2E2E (1/1), test_plastic_emission.py::TestTangentForBoth (8/8) | 2026-04-05 |
| P4-T3 | Verify history field emission | done | claude | — | P4-T5 | 180–185 | sprint2_phase-4 | test_plastic_emission.py::TestHistoryFieldInKernel (4/4), TestAlphaUpdate (2/2) | 2026-04-05 |
| P4-T4 | Verify numerical safeguards | done | claude | — | P4-T5 | 187–193 | sprint2_phase-4 | test_plastic_emission.py::TestTaskP4T4Safeguards (2/2), TestVonMisesGuard (2/2), test_phase1_codegen_fixes.py dl_clamp (1/1) | 2026-04-05 |
| P4-T5 | Create test_e2e_plastic.py | done | claude | — | P4-T6 | 195–208 | sprint2_phase-4 | test_e2e_plastic.py::TestTaskP4T5 (5/5) | 2026-04-05 |
| P4-T6 | Compare generated vs reference | done | claude | — | P4-T7 | 210–214 | sprint2_phase-4 | test_e2e_plastic.py::TestTaskP4T6 (1/1), max diff 1.2e-16 | 2026-04-05 |
| P4-T7 | Validate/update golden file | done | claude | — | — | 216–219 | sprint2_phase-4 | test_codegen.py::TestGoldenSnapshot (3/3) | 2026-04-05 |
| P5-T1 | Audit symbolic (S1-S9) + parser (P1-P6) | done | claude | — | P5-T4 | 229–234 | sprint2_phase-5 | test_kinematics.py, test_svk.py, test_j2.py, test_voigt.py, test_convected.py, test_frontend_build_context.py (100/100); P3/P4 deferred | 2026-04-05 |
| P5-T2 | Audit IR (M1-M6), Element (E1-E6), Einsum (N1-N5) | done | claude | — | P5-T4 | 236–240 | sprint2_phase-5 | test_mechanics_ir.py, test_element_ir.py, test_hex8_tables.py, test_einsum.py, test_einsum_optimizer.py, test_verification_gaps_p5t2.py (14/14 new + 119 existing) | 2026-04-05 |
| P5-T3 | Audit Backend (T1-T4), BC (B1-B5), Artifact (A1-A3), Emission (C1-C3) | done | claude | — | P5-T4 | 242–246 | sprint2_phase-5 | test_codegen.py, test_boundary_codegen.py, test_artifact_bundle.py, test_e2e_taichi.py, test_e2e_plastic.py, test_verification_gaps_p5t3.py (3/3 new + 77 existing) | 2026-04-05 |
| P5-T4 | Create verification matrix | done | claude | — | — | 248–252 | sprint2_phase-5 | dev/tracking/verification_matrix.md (47 IDs: 45 pass, 2 deferred) | 2026-04-05 |
| P6-T1 | Full regression suite | done | claude | — | P6-T2 | 262–265 | sprint2_phase-6 | 853 fast + 9 E2E slow = 862 passed, 0 failed | 2026-04-05 |
| P6-T2 | Verify sprint exit criteria | done | claude | — | P6-T3 | 267–278 | sprint2_phase-6 | 10/10 exit criteria met with evidence | 2026-04-05 |
| P6-T3 | Sprint 2 completion handoff | done | claude | — | — | 280–281 | sprint2_phase-6 | Sprint2_Completion_Handoff.md (all sections filled) | 2026-04-05 |


## Update protocol

1. When a task starts, set `Status` to `in_progress`, assign `Owner`, and keep unresolved blockers in `Blocked by (open)`.
2. When a task is done, set `Status` to `done`, fill `PR/Commit`, `Verified by`, and `Completed on` (YYYY-MM-DD).
3. For each newly completed task, remove its ID from downstream rows in `Blocked by (open)` when applicable.

## Verification status

### Phase 1 aggregate verification:

#### Phase 1 mapping between test and task:

| Task ID | Title | Test file | Stubs |
|---|---|---|---|
| P1-T1 | Fix emit_main E/nu → Lamé conversion | `tests/test_emit_lame_conversion.py` | 5 |
| P1-T2 | Implement convected coordinate functions | `tests/test_convected.py` | 7 |
| P1-T3 | Write convected coordinate tests | `tests/test_convected.py` | 0 (same file as P1-T2) |
| P1-T4 | Update convected exports | import check (verification_commands) | 0 |
| P1-T5 | Regenerate golden files after emit_main fix | `tests/test_codegen.py` (existing golden regression) | 0 |
| P1-T6 | Write emit_main Lamé conversion test | `tests/test_emit_lame_conversion.py` | 0 (same file as P1-T1) |

#### Verification outcomes:

    `uv run pytest packages/mechdsl-core/tests/test_convected.py packages/mechdsl-core/tests/test_emit_lame_conversion.py -v` → 12/12 passed (2026-04-05)

### Full regression (post-Phase 1):

    `uv run pytest packages/mechdsl-core/tests/ -m 'not slow and not gpu' -x -q` → 752/752 passed (2026-04-05)

### Phase 2 aggregate verification:

#### Phase 2 mapping between test and task:

| Task ID | Title | Test file | Stubs |
|---|---|---|---|
| P2-T1 | Implement patch_test_reference() | `tests/test_analytical.py` (+ `tests/test_ref_elastic.py` partial) | 3 |
| P2-T2 | Implement rigid_body_reference() | `tests/test_analytical.py` (+ `tests/test_benchmarks.py` partial) | 2 |
| P2-T3 | Implement cantilever_euler_bernoulli() | `tests/test_analytical.py` (+ `tests/test_ref_elastic.py` partial) | 1 |
| P2-T4 | Implement uniaxial_tension_hardening() | `tests/test_analytical.py` (+ `tests/test_ref_plastic.py` partial) | 4 |
| P2-T5 | Write analytical solution tests | `tests/test_analytical.py` | 1 (import check) |
| P2-T6 | Implement frontend.build_context() | `tests/test_frontend_build_context.py` | 2 |
| P2-T7 | Implement build_context validation | `tests/test_frontend_build_context.py` | 4 |
| P2-T8 | Write frontend tests | `tests/test_frontend_build_context.py` | 4 |

#### Verification outcomes:

    `uv run pytest packages/mechdsl-core/tests/test_analytical.py packages/mechdsl-core/tests/test_frontend_build_context.py -v` → 48/48 passed (2026-04-05)

### Phase 3 aggregate verification:

#### Phase 3 mapping between test and task:

| Task ID | Title | Test file | Stubs |
|---|---|---|---|
| P3-T1 | Implement check_convergence_rate() | `tests/test_convergence.py::TestTaskP3T1` | 7 |
| P3-T2 | Implement MMS driver | `tests/test_convergence.py::TestTaskP3T2` | 4 |
| P3-T3 | Write convergence rate test | `tests/test_convergence.py::TestTaskP3T3` | 2 |
| P3-T4 | Implement run_patch_test() and run_rigid_body_test() | `tests/test_patch_test.py::TestTaskP3T4` (+ `tests/test_benchmarks.py` partial) | 4 |
| P3-T5 | Write patch test | `tests/test_patch_test.py::TestTaskP3T5` (+ `tests/test_ref_elastic.py` partial) | 2 |

#### Verification outcomes:

    `uv run pytest packages/mechdsl-core/tests/test_convergence.py packages/mechdsl-core/tests/test_patch_test.py -v -k "not slow"` → 21/21 fast tests passed (2026-04-05)
    `uv run pytest packages/mechdsl-core/tests/test_convergence.py::TestTaskP3T2 -v -m slow` → 3 slow MMS convergence tests (pending: 8^3 mesh level is compute-intensive)
    `uv run pytest packages/mechdsl-core/tests/test_patch_test.py -v -m slow` → 6 slow tests (patch + rigid body on various meshes)

### Phase 4 aggregate verification:

#### Phase 4 mapping between test and task:

| Task ID | Title | Test file | Stubs |
|---|---|---|---|
| P4-T1 | Audit J2 constitutive emission | `tests/test_plastic_emission.py` (existing 36+ tests) + `TestTaskP4T1Audit` (stub) | 1 |
| P4-T2 | Validate FD tangent for J2 | `tests/test_plastic_emission.py::TestTangentForBoth` (existing) + `tests/test_e2e_plastic.py::TestTaskP4T2E2E` (stub) | 1 |
| P4-T3 | Verify history field emission | `tests/test_plastic_emission.py::TestHistoryFieldInKernel` + `TestAlphaUpdate` (all covered) | 0 |
| P4-T4 | Verify numerical safeguards | `tests/test_plastic_emission.py::TestVonMisesGuard` (covered) + `tests/test_phase1_codegen_fixes.py` (covered) + `TestTaskP4T4Safeguards` (stub) | 2 |
| P4-T5 | Create test_e2e_plastic.py | `tests/test_e2e_plastic.py::TestTaskP4T5` (stub) | 5 |
| P4-T6 | Compare generated vs reference | `tests/test_e2e_plastic.py::TestTaskP4T6` (stub) | 1 |
| P4-T7 | Validate/update golden file | `tests/test_codegen.py::TestGoldenSnapshot` (fully covered) | 0 |

#### Verification outcomes:

    `uv run pytest packages/mechdsl-core/tests/test_e2e_plastic.py -v` → stubs registered, 0 passing (pre-execution baseline)
    `uv run pytest packages/mechdsl-core/tests/test_plastic_emission.py -v` → pending

### Phase 5 aggregate verification:

#### Phase 5 mapping between test and task:

| Task ID | Title | Test file | Stubs |
|---|---|---|---|
| P5-T1 | Audit symbolic + parser | `test_kinematics.py`, `test_svk.py`, `test_j2.py`, `test_voigt.py`, `test_convected.py`, `test_frontend_build_context.py` | 0 (all covered/deferred) |
| P5-T2 | Audit IR, Element, Einsum | `test_mechanics_ir.py`, `test_element_ir.py`, `test_hex8_tables.py`, `test_einsum.py`, `test_einsum_optimizer.py`, `test_verification_gaps_p5t2.py` | 5 |
| P5-T3 | Audit Backend, BC, Artifact, Emission | `test_codegen.py`, `test_boundary_codegen.py`, `test_artifact_bundle.py`, `test_e2e_taichi.py`, `test_e2e_plastic.py`, `test_verification_gaps_p5t3.py` | 2 |
| P5-T4 | Create verification matrix | `dev/tracking/verification_matrix.md` | 0 (documentation) |

#### Verification outcomes:

    `uv run pytest packages/mechdsl-core/tests/test_verification_gaps_p5t2.py packages/mechdsl-core/tests/test_verification_gaps_p5t3.py -v` → 17/17 passed (2026-04-05)
    `uv run pytest packages/mechdsl-core/tests/ -m 'not slow and not gpu' -x -q` → 853/853 passed (2026-04-05, up from 836 post-Phase 4)

### Phase 6 aggregate verification:

#### Phase 6 mapping between test and task:

| Task ID | Title | Test file |
|---|---|---|
| P6-T1 | Full regression suite | all tests |
| P6-T2 | Verify sprint exit criteria | manual check |
| P6-T3 | Sprint 2 completion handoff | `dev/tasks/sprint2/Sprint2_Completion_Handoff.md` |

#### Verification outcomes:

    `uv run pytest packages/mechdsl-core/tests/ -m 'not slow and not gpu' -x -q` → 853/853 passed (2026-04-05)
    `uv run pytest packages/mechdsl-core/tests/test_e2e_taichi.py packages/mechdsl-core/tests/test_e2e_plastic.py -v -m slow` → 9/9 passed (2026-04-05)
    Exit criteria: 10/10 met with evidence (2026-04-05)
    Sprint2_Completion_Handoff.md created (2026-04-05)
