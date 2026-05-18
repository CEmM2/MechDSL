# PR #3 Review Resolution Task Tracker

> ⚠️ **Superseded** — the active execution source is [`tasks-tracker_recovery_plan_latex_contract.md`](tasks-tracker_recovery_plan_latex_contract.md), driven by [`dev/plans/recovery_plan_latex_contract.md`](../plans/recovery_plan_latex_contract.md). This tracker is retained for historical reference only (Phase 7 / R6 archival, P7-5).

Generated on: 2026-04-02
This tracker records execution status for the mvp_pr3_round3 task set.

## mvp_pr3_round3 Tracker

Plan source: `dev/plans/mvp_pr3_round3.md`
Task index: `dev/tasks/mvp_pr3_round3/all-tasks.md`

| Task ID | Title | Status | Owner | Blocked by (open) | Blocks | Plan lines | PR/Commit | Verified by | Completed on |
|---|---|---|---|---|---|---|---|---|---|
| R3.1.1 | Fix J2 Newton ti.static → runtime (C1) | done | Claude | — | R3.6.1 | 15–20 | Phase 1 batch | test_plastic_emission.py:114 | 2026-04-02 |
| R3.1.2 | Fix quadrature loop to ti.static (C2) | done | Claude | — | R3.1.5, R3.6.1 | 22–31 | Phase 1 batch | test_taichi_printer.py:229, test_emission_verification.py:280, test_codegen.py:157 | 2026-04-02 |
| R3.1.3 | Emit raise RuntimeError on Newton non-convergence (C4) | done | Claude | — | R3.6.1 | 33–50 | Phase 1 batch | test_phase1_codegen_fixes.py::TestC4, test_emission_verification.py:650 | 2026-04-02 |
| R3.1.4 | Add NaN/Inf guard in emitted Newton driver (C4b) | done | Claude | — | R3.6.1 | 52–61 | Phase 1 batch | test_phase1_codegen_fixes.py::TestC4b | 2026-04-02 |
| R3.1.5 | Change node loops to runtime (C5) | done | Claude | — | R3.6.1 | 63–73 | Phase 1 batch | test_taichi_printer.py::TestIndexPartitioning, test_emission_verification.py:370, test_codegen.py:175 | 2026-04-02 |
| R3.1.6 | Add material model validation in emit() (H9) | done | Claude | — | R3.6.1 | 75–86 | Phase 1 batch | test_phase1_codegen_fixes.py::TestH9 | 2026-04-02 |
| R3.1.7 | Add emitted J2 convergence check (H1) | done | Claude | — | R3.1.4, R3.6.1 | 88–97 | Phase 1 batch | test_phase1_codegen_fixes.py::TestH1 | 2026-04-02 |
| R3.1.8 | Add emitted J2 negative dl guard (H2) | done | Claude | — | R3.1.4, R3.6.1 | 99–103 | Phase 1 batch | test_phase1_codegen_fixes.py::TestH2 | 2026-04-02 |
| R3.1.9 | Fix comments CM3, CM4, CM5, CM7 | done | Claude | — | R3.6.1 | 105–109 | Phase 1 batch | test_phase1_codegen_fixes.py::TestCM3 | 2026-04-02 |
| R3.1.10 | Update convention docs for C2 carve-out | done | Claude | — | — | 113–116 | Phase 1 batch | manual review | 2026-04-02 |
| R3.2.1 | Add CG/PCG breakdown warning (C3) | done | Claude | — | — | 122–140 | Phase 2 batch | test_solver.py 11/11 | 2026-04-02 |
| R3.2.2 | Fix J2 radial_return stall guard (H3) | done | Claude | — | R3.5.1 | 142–156 | Phase 2 batch | test_j2.py 19/19 | 2026-04-02 |
| R3.2.3 | Add emitted CG failure counter (H4) | done | Claude | — | R3.6.1 | 158–179 | Phase 2 batch | test_emission_verification.py 81/81 | 2026-04-02 |
| R3.2.4 | Fix einsum FLOPS fallback to sentinel (H5) | done | Claude | — | — | 181–193 | Phase 2 batch | test_einsum_optimizer.py 30/30 | 2026-04-02 |
| R3.2.5 | Add Newton non-convergence to ref elastic solver (H6) | done | Claude | — | R3.6.1 | 195–204 | Phase 2 batch | test_ref_elastic.py 24/24 | 2026-04-02 |
| R3.2.6 | Add boundary codegen zero-area and axis guards (H7+H8) | done | Claude | — | R3.5.2 | 206–233 | Phase 2 batch | test_boundary_codegen.py 22/22 | 2026-04-02 |
| R3.3.1 | Add __post_init__ to J2PowerLawMaterial | done | Claude | — | R3.5.3 | 239–254 | Phase 3 batch | test_j2.py 19/19 | 2026-04-02 |
| R3.3.2 | Freeze ReturnMappingResult + fix comments (H11-H13) | done | Claude | — | — | 256–261 | Phase 3 batch | test_j2.py 19/19 | 2026-04-02 |
| R3.3.3 | Add __post_init__ to SVKMaterial + from_E_nu | done | Claude | — | R3.5.3 | 263–277 | Phase 3 batch | test_svk.py 15/15 | 2026-04-02 |
| R3.3.4 | Add __post_init__ to HexMesh | done | Claude | — | R3.5.3 | 279–296 | Phase 3 batch | test_mesh_io.py 28/28 | 2026-04-02 |
| R3.3.5 | Add __post_init__ to QuadratureRule | done | Claude | — | R3.5.3 | 298–311 | Phase 3 batch | test_element_ir.py 19/19 | 2026-04-02 |
| R3.3.6 | Add __post_init__ to DirichletBC/NeumannBC | done | Claude | — | R3.5.3 | 313–330 | Phase 3 batch | test_boundary_codegen.py 22/22 | 2026-04-02 |
| R3.3.7 | Improve HistoryFields error messages | done | Claude | — | — | 332–353 | Phase 3 batch | test_history_fields.py 24/24 | 2026-04-02 |
| R3.4.1 | Fix CI uv sync flags (H10) | done | Claude | — | — | 359–364 | Phase 4 | ci.yml lines 19,38,51 verified | 2026-04-02 |
| R3.5.1 | Add tests T1-T2: radial_return error paths | done | Claude | — | — | 370–409 | Phase 5 | test_j2.py 28/28 (3 new) | 2026-04-02 |
| R3.5.2 | Add tests T3-T4: degenerate element + invalid face | done | Claude | — | — | 411–433 | Phase 5 | test_hex8_tables.py, test_boundary_codegen.py | 2026-04-02 |
| R3.5.3 | Add tests T5: __post_init__ validation tests | done | Claude | — | — | 435–440 | Phase 5 | test_j2/svk/mesh_io/element_ir/boundary_codegen | 2026-04-02 |
| R3.5.4 | Tighten tolerances (G1, G4) + Dirichlet fix (G3) | done | Claude | — | R3.6.1 | 442–454 | Phase 5 | test_ref_elastic.py 24/24, test_j2.py 28/28 | 2026-04-02 |
| R3.6.1 | Regenerate golden files + full verification | done | Claude | — | — | 458–483 | Phase 6 | 677/677 passed, ruff clean, mypy clean | 2026-04-03 |

## Update protocol

1. When a task starts, set `Status` to `in_progress`, assign `Owner`, and keep unresolved blockers in `Blocked by (open)`.
2. When a task is done, set `Status` to `done`, fill `PR/Commit`, `Verified by`, and `Completed on` (YYYY-MM-DD).
3. For each newly completed task, remove its ID from downstream rows in `Blocked by (open)` when applicable.

## Verification status

### Phase 1 aggregate verification:

#### Phase 1 mapping between test and task:

| Task ID | Title | Test file | Coverage |
|---|---|---|---|
| R3.1.1 | Fix J2 Newton ti.static (C1) | test_plastic_emission.py:114 | **must update** existing assertion |
| R3.1.2 | Fix quadrature loop ti.static (C2) | test_taichi_printer.py:229,232 | **must update** existing assertions |
| R3.1.3 | Emit RuntimeError on non-convergence (C4) | test_emission_verification.py + **test_phase1_codegen_fixes.py** (new stubs) | partial + 2 new stubs |
| R3.1.4 | NaN guard in Newton driver (C4b) | **test_phase1_codegen_fixes.py** (new stubs) | 2 new stubs |
| R3.1.5 | Node loops to runtime (C5) | test_taichi_printer.py:220, test_emission_verification.py:371 | **must update** existing assertions |
| R3.1.6 | Material model validation (H9) | **test_phase1_codegen_fixes.py** (new stubs) | 3 new stubs |
| R3.1.7 | J2 convergence check (H1) | test_plastic_emission.py:120 + **test_phase1_codegen_fixes.py** (new stubs) | partial + 2 new stubs |
| R3.1.8 | J2 negative dl guard (H2) | test_plastic_emission.py:116 + **test_phase1_codegen_fixes.py** (new stub) | partial + 1 new stub |
| R3.1.9 | Comment fixes (CM3-CM7) | **test_phase1_codegen_fixes.py** (new stubs) | 2 new stubs |
| R3.1.10 | Convention docs update | manual review | N/A |

#### Verification outcomes:

    `uv run pytest packages/mechdsl-core/tests/test_phase1_codegen_fixes.py -v` → 12/12 passed
    `uv run pytest packages/mechdsl-core/tests/test_taichi_printer.py packages/mechdsl-core/tests/test_plastic_emission.py packages/mechdsl-core/tests/test_emission_verification.py -v --tb=short` → 179/179 passed
    `uv run pytest packages/mechdsl-core/tests/ -m "not slow and not gpu" --ignore=packages/mechdsl-core/tests/test_codegen.py -q` → 633/633 passed
    `uv run pytest packages/mechdsl-core/tests/test_codegen.py -v` → 18/20 passed, 2 golden snapshot failures (expected — Phase 6)

### Phase 2 aggregate verification:

#### Phase 2 mapping between test and task:

| Task ID | Title | Test file | Coverage |
|---|---|---|---|
| R3.2.1 | CG/PCG breakdown warning (C3) | test_solver.py + **test_phase2_error_handling.py** | 3 new stubs |
| R3.2.2 | J2 stall guard fix (H3) | test_j2.py + **test_phase2_error_handling.py** | 3 new stubs |
| R3.2.3 | Emitted CG failure counter (H4) | test_emission_verification.py:613 + **test_phase2_error_handling.py** | partial + 3 new stubs |
| R3.2.4 | Einsum FLOPS sentinel (H5) | test_einsum_optimizer.py:206 (**must update**) + **test_phase2_error_handling.py** | 1 must update + 2 new stubs |
| R3.2.5 | Ref elastic non-convergence (H6) | test_ref_elastic.py | covered (converge) + missing (raise path) |
| R3.2.6 | Boundary codegen guards (H7+H8) | test_boundary_codegen.py + **test_phase2_error_handling.py** | 4 new stubs |

#### Verification outcomes:

    `uv run pytest packages/mechdsl-core/tests/test_phase2_error_handling.py -v` → 15 stubs skipped (to be filled in Phase 5)
    `uv run pytest packages/mechdsl-core/tests/ -m "not slow and not gpu" -q` → 652 passed, 15 skipped, 0 failed

### Phase 3 aggregate verification:

| Task ID | Title | Test file | Coverage |
|---|---|---|---|
| R3.3.1 | J2 __post_init__ | test_j2.py | regression (validation tests in Phase 5 R3.5.3) |
| R3.3.2 | Freeze ReturnMappingResult | test_j2.py | regression + manual (comment check) |
| R3.3.3 | SVK __post_init__ | test_svk.py | regression (validation tests in Phase 5 R3.5.3) |
| R3.3.4 | HexMesh __post_init__ | test_mesh_io.py | regression (validation tests in Phase 5 R3.5.3) |
| R3.3.5 | QuadratureRule __post_init__ | test_element_ir.py | regression (validation tests in Phase 5 R3.5.3) |
| R3.3.6 | DirichletBC/NeumannBC __post_init__ | test_boundary_codegen.py | regression (validation tests in Phase 5 R3.5.3) |
| R3.3.7 | HistoryFields errors | test_history_fields.py | regression |

#### Verification outcomes:

    Phase 3 uses existing tests for regression — no new stub files needed.
    Validation-specific tests deferred to Phase 5 (R3.5.3).

### Phase 5 aggregate verification:

| Task ID | Title | Test file |
|---|---|---|
| R3.5.1 | T1-T2 radial_return error paths | test_j2.py (new tests) |
| R3.5.2 | T3-T4 degenerate element + face | test_hex8_tables.py, test_boundary_codegen.py (new tests) |
| R3.5.3 | T5 __post_init__ validation | test_j2.py, test_svk.py, test_mesh_io.py, test_element_ir.py, test_boundary_codegen.py (new tests) |
| R3.5.4 | Tolerance tightening + Dirichlet fix | test_ref_elastic.py, test_j2.py |

### Phase 6 aggregate verification:

    `uv run pytest packages/mechdsl-core/tests/ -m "not slow and not gpu" --tb=short -q` -> TBD
    `uv run ruff check packages/` -> TBD
    `uv run mypy packages/mechdsl-core/src/mechdsl/` -> TBD
