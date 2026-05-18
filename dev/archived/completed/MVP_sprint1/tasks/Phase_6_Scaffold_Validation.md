# Phase 6 Scaffold Validation

| Task ID | Title | Missing / Incomplete Fields | Scaffold Action |
|---------|-------|-----------------------------|-----------------|
| P6-T1 | Create E2E Taichi smoke test | — | All fields populated |
| P6-T2 | CI integration for slow tests | risks: empty | auto-filled (CI config risk is low) |

## Scaffold Summary

| Metric | Value |
|--------|-------|
| Tasks scaffolded | 2 |
| Test cases assessed | 6 |
| Cases covered by existing tests | 1 (marker registration) |
| Cases partially covered (stubs generated) | 1 (elastic compile+execute — test_codegen has import-only) |
| Cases with no existing tests (stubs generated) | 1 (Newton 1-iteration convergence) |
| New stub files created | 1 |
| Total new stubs generated | 2 |
| Tasks fully covered by existing tests (no stub needed) | 0 |
| Tasks needing human review | 0 |
| Auto-filled fields | P6-T2.risks (low-risk CI config) |

## Existing Test Coverage Found

| Task ID | Test case | Existing test file | Function | Coverage |
|---------|-----------|-------------------|----------|----------|
| P6-T1 | Elastic Hex8 compile+execute | `tests/test_codegen.py` | `TestBehavioralEquivalence::test_elastic_generated_vs_reference` | partial (imports module, checks for newton_solve callable, but does NOT execute solver or compare displacement) |
| P6-T1 | Elastic Hex8 compile+execute | `tests/test_e2e.py` | `TestGeneratedCodeImport::test_elastic_module_imports` | partial (imports module, verifies callable attributes, but does NOT run solver) |
| P6-T1 | 1-iteration convergence | — | — | missing |
| P6-T2 | Marker warnings suppressed | `pyproject.toml` | markers config (lines 44-48) | covered |
| P6-T2 | CI triggers on codegen/ | — | — | missing (no slow CI job) |
| P6-T2 | CI triggers on solver/ | — | — | missing (no slow CI job) |
| P6-T2 | CI skips unrelated | — | — | missing (no slow CI job) |

## Tasks Needing Human Review Before execute-phase

None.

## Ready for execute-phase

Fully scaffolded:
- P6-T1: Create E2E Taichi smoke test (2 stubs in `tests/test_e2e_taichi.py`)
- P6-T2: CI integration for slow tests (CI config task, no stubs needed; 1 of 4 criteria already met)
