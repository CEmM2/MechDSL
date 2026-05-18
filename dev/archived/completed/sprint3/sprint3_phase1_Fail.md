# Sprint 3 Phase 1 — Failing & Skipped Tests

> ⚠️ **Superseded** by [`recovery_plan_latex_contract.md`](recovery_plan_latex_contract.md) (Phase 7 / R6 archival, P7-5). This document is a point-in-time triage record for Sprint 3 Phase 1 failures and is retained for historical reference only. The active execution source is the recovery plan. See [`STATUS_LEGEND.md`](../tracking/STATUS_LEGEND.md) and [`frontend_drift_history.md`](../reviews/frontend_drift_history.md).

**Branch:** `sprint3_phase-1`
**Date:** 2026-04-09
**Suite:** `uv run pytest -m "not slow and not gpu and not e2e" packages/mechdsl-core/`
**Result:** 835 passed, 6 skipped, 6 failed (62 deselected)

---

## Failures (6)

All 6 failures are **pre-existing** — present on `main` before any Sprint 3 work.

### Missing `scipy` dependency

| # | Test | File |
|---|------|------|
| 1 | `TestUniaxialTensionHardening::test_uniaxial_above_yield_hardening_law` | `tests/test_analytical.py` |
| 2 | `TestUniaxialTensionHardening::test_uniaxial_continuity_at_yield_point` | `tests/test_analytical.py` |
| 3 | `TestUniaxialTensionHardening::test_uniaxial_large_strain_monotonic` | `tests/test_analytical.py` |
| 4 | `TestUniaxialTensionHardening::test_uniaxial_power_law_hardening` | `tests/test_analytical.py` |
| 5 | `TestUniaxialTensionHardening::test_uniaxial_zero_hardening` | `tests/test_analytical.py` |
| 6 | `TestAnalyticalSolutionsCombined::test_hardening_above_yield_consistent_decomposition` | `tests/test_analytical.py` |

**Error:** `ModuleNotFoundError: No module named 'scipy'`

**Cause:** `mechdsl.verify.analytical.uniaxial_tension_hardening` calls `from scipy.optimize import brentq` at line 258, but `scipy` is not declared as a dependency in `pyproject.toml`.

**Why not fixed yet:** These tests are isolated to the analytical verification module and do not affect any Sprint 3 work. The fix is either adding `scipy` as a dependency or replacing `brentq` with a stdlib bisection. This is tracked as a Phase 6 cleanup item (P6-3: full test suite zero failures).

---

## Skips (6)

### P2-1 test stubs (new — scaffolded this session)

| # | Test | File |
|---|------|------|
| 1 | `TestCookMembraneGeometry::test_corner_coordinates_match_trapezoid` | `tests/test_mesh_io.py` |
| 2 | `TestCookMembraneGeometry::test_boundary_tags_present_and_nonempty` | `tests/test_mesh_io.py` |
| 3 | `TestCookMembraneGeometry::test_node_and_element_counts` | `tests/test_mesh_io.py` |
| 4 | `TestCookMembraneGeometry::test_positive_jacobians` | `tests/test_mesh_io.py` |
| 5 | `TestCookMembraneGeometry::test_fixed_face_x0_nodes` | `tests/test_mesh_io.py` |
| 6 | `TestCookMembraneGeometry::test_loaded_face_x1_nodes` | `tests/test_mesh_io.py` |

**Reason:** Scaffold stubs for Phase 2 Task P2-1 (`generate_cook_membrane_mesh`). These skip with message "stub -- implement after Task P2-1 is complete". They will be implemented during Phase 2 execution.

---

## Deselected (62)

Tests marked `@pytest.mark.slow`, `@pytest.mark.e2e`, or `@pytest.mark.gpu` — excluded by the fast suite filter `-m "not slow and not gpu and not e2e"`. Among these, 3 are additionally skipped at runtime:

| Test | File | Reason |
|------|------|--------|
| `TestCantilever::test_tip_displacement_within_5_percent` | `tests/test_benchmarks.py` | 40x8x4 mesh infeasible with unpreconditioned CG (>12h). Tracked in #28. |
| `TestMMS4LevelConvergence::test_mms_4level_l2_convergence_rate` | `tests/test_convergence.py` | [2,4,8,16] MMS infeasible with unpreconditioned CG. Tracked in #28. |
| `TestMMS4LevelConvergence::test_mms_4level_h1_convergence_rate` | `tests/test_convergence.py` | [2,4,8,16] MMS infeasible with unpreconditioned CG. Tracked in #28. |
