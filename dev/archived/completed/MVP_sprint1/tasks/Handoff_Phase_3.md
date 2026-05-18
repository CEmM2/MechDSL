# Phase 2 Handoff

> **From**: Phase 2 agent  
> **To**: Phase 3 agent  
> **Date**: 2026-04-03  
> **Branch**: `sprint1_phase-2`  
> **Plan**: `.claude/plans/serialized-booping-quokka.md`  

---

## Phase 2 Completion Summary

| Task ID | Title | Commit | Tests (pass/total) | Failing Tests |
|---------|-------|--------|--------------------|---------------|
| P2-T1 | Implement extract_einsum_specs() | sprint1_phase-2 | 10/10 (smoke) | None |
| P2-T2 | Refactor fe_localise + update exports | sprint1_phase-2 | 96/96 (localise+e2e+einsum+optimizer) | None |
| P2-T3 | Write einsum extraction tests | sprint1_phase-2 | 9/9 | None |

**Overall test status**: 9/9 task-dedicated tests passing. 715/715 total tests passing (706 Phase 1 baseline + 9 new).

---

## Architecture and State After Phase 2

- **New files created**:
  - `tests/test_einsum_extract.py` — 9 tests for extract_einsum_specs

- **Modified files**:
  - `src/mechdsl/lowering/einsum_extract.py` — stub → full implementation (~110 lines). Contains `extract_einsum_specs(element_ir: ElementIR) -> dict[str, EinsumSpec]`
  - `src/mechdsl/lowering/fe_localise.py` — removed `_extract_hex8_tl_einsums()` (~100 lines deleted), `localise()` now delegates to `extract_einsum_specs(element_ir)` via inline import
  - `src/mechdsl/lowering/__init__.py` — added `extract_einsum_specs` to exports

- **New Taichi fields/kernels**: None

- **Interfaces added or changed**:
  - `extract_einsum_specs(element_ir: ElementIR) -> dict[str, EinsumSpec]` — new public API, canonical location for einsum extraction per `.claude/rules/ir.md`
  - `mechdsl.lowering` now exports `extract_einsum_specs`
  - `localise()` output is numerically identical — only internal delegation changed

---

## Assumptions Made During Phase 2

| Assumption | Where it applies | Rationale | Risk if wrong |
|------------|-----------------|-----------|---------------|
| `EinsumSpec` dataclass stays in `fe_localise.py`, not moved to `einsum_extract.py` | Both files | Plan says "Import EinsumSpec from fe_localise.py (keep dataclass in its current location)" | Low — could move later if circular import issues arise |
| `extract_einsum_specs` imported inside `localise()` function body (not at module level) | fe_localise.py:98 | Avoids circular import between fe_localise and einsum_extract (einsum_extract imports EinsumSpec from fe_localise) | Low — function-level import is standard pattern for this |

---

## Known Issues and Deferred Concerns

### Failing tests
None.

### Known bugs or behavioral limitations
None.

### Test coverage gaps
- No test for the exact `description` field content of each EinsumSpec (only names, strings, shapes tested). Not critical.

---

## What Phase 3 Must Know Before Starting

- **Critical dependencies**: Phase 3 (Newton driver) does NOT depend on Phase 2 outputs. `newton.py` operates at the numpy level using assembly callbacks — it does not call `extract_einsum_specs()` or interact with the lowering layer.

- **High-risk tasks in Phase 3**: P3-T1 (implement newton_solve) is the most substantial new code (~200 lines). The callback-based design must match `ref_hex8_elastic.py::solve_elastic` patterns exactly, including Dirichlet enforcement (identity row in matvec, zero constrained DOFs in residual and increment).

- **Recommended starting point**: P3-T1 — it has no blockers and is the prerequisite for P3-T2 and P3-T3.

- **Key files to read**: `tests/ref/ref_hex8_elastic.py:364-466` (solve_elastic pattern), `solver/load_stepping.py` (callback contract), `solver/import_adapter.py` (CGSolver interface), `solver/history_fields.py` (commit/rollback API).
