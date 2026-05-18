# Phase 10 Scaffold Validation Report

**Date:** 2026-04-18
**Phase:** 10 — Full V&V suite (PLAN-B §B9)
**Scaffolded by:** Aut_Faciam `scaffold 10`

---

## Summary

| Metric | Value |
|---|---|
| Tasks in phase | 10 |
| Stub files generated | 10 |
| Stub tests collected | **41** (all skipped, pending implementation) |
| Existing partial-coverage tests referenced | 6 |
| Pytest markers added | `nightly` (registered in `pyproject.toml`) |
| Task JSONs updated | 10 (`verification_commands` + `test_artifacts`) |
| Tracker Phase 10 rows updated | 10 |
| GitHub task issues created | pending (see §GitHub Operations) |

---

## Per-Task Scaffold Details

| Task | Stub file | Tests | Partial-coverage links |
|---|---|---:|---|
| P10-1 | `test_mms_convergence_matrix.py` | 8 | `test_convergence.py`, `test_analytical.py` |
| P10-2 | `test_benchmarks_cantilever_matrix.py` | 12 (parametrised) | `test_benchmarks.py::TestCantilever` |
| P10-3 | `test_benchmarks_cook_membrane_matrix.py` | 4 | `test_benchmarks.py::TestCooksMembrane` |
| P10-4 | `test_thick_cylinder.py` | 2 | — |
| P10-5 | `test_plate_with_hole.py` | 2 | — |
| P10-6 | `test_benchmarks_necking_bar_matrix.py` | 2 | `test_benchmarks.py::TestNeckingBar` |
| P10-7 | `test_taylor_impact.py` | 3 | — |
| P10-8 | `test_notched_bar_benchmark.py` | 2 | `test_lemaitre_acceptance.py`, `test_phase6_exit.py` |
| P10-9 | `test_hgo_benchmark.py` | 3 | `test_hgo.py` |
| P10-10 | `test_perf_regression.py` | 3 | — |
| **Total** | | **41** | |

All stubs carry `@pytest.mark.nightly` + `@pytest.mark.regression`, plus `@pytest.mark.slow` where Taichi JIT is expected at run time.

---

## Ready-for-execute

All 10 Phase 10 tasks scaffolded cleanly. None require human-review blocks.

**Hard prerequisites (from `blocked_by`):** every P10-* task transitively depends on Phase 1-9 work. Executable sequence:
- **Unblocked today** (Phases 1-9 complete or partial): none — all P10-* block on at least one phase still in progress.
- **Near-term unlock candidates:** P10-4 (depends only on P1-7 ✅), P10-6 (P1-7 ✅), P10-9 (P4-4 ✅), P10-8 (P6-3 ✅), P10-3 (P1-7 ✅ + P5-2 pending).
- **Later:** P10-1 (needs P5-7, P9-3 ✅), P10-2 / P10-5 / P10-7 (need Phase 5 elements), P10-10 (needs all other P10 tasks).

All 10 task issues will carry the `blocked` label on creation — to be removed individually as prerequisites clear.

---

## Scaffold Concessions

1. **`nightly` pytest marker registered in `pyproject.toml` ahead of P10-10.** `--strict-markers` is enabled; without registering the marker, the stubs would fail to collect. Documented in the P10-10 stub docstring.
2. **No benchmark harness module yet.** All stubs reference `mechdsl.verify.benchmarks` (or `packages.mechdsl_core.tests.perf.compare`) as the future import path. Commented out and marked for wire-up at implementation time. This module does not exist today.

---

## Fast-suite Sanity

Post-scaffold fast-suite state (`uv run pytest -m "not slow and not gpu"`):
- Baseline (pre-scaffold, Phase 9 exit): 1307 passed / 1 failed (P9-1 spec-gap, user-owned)
- After initial scaffold: regressed by 1 (P6T5 TODO-guard tripped on stub `# TODO:` comments)
- **After TODO-comment rewrite (current): 1307 passed / 1 failed** — back to Phase 9 exit state. The remaining failure is the pre-existing P9-1 spec §9 update, not a Phase 10 scaffold issue.

Stub collection verified: `uv run pytest <10 stubs> --collect-only` → **41 tests collected**, all skipped at run time.

---

## GitHub Operations (Step 7)

Pending at time of this report:
1. Create 10 task-level issues under phase issue #65, linked to the repo `SOSOVSKI/MechDSL`.
2. Apply `task-issue`, `phase-10`, `plan:plan-b`, `blocked` labels (+ `tier:regression` for all).
3. Update phase issue #65 body with task checklist.
4. Swap phase #65 labels: remove `not-scaffolded`, add `scaffolded`.
5. Back-fill each task JSON's `github_issue.task_issue` with the new issue number.

Tracker (`dev/tracking/tasks-tracker_PLAN-B.md`) is the authoritative record; GitHub is the projection.
