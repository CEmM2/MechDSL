# Phase 6 Scaffold Validation

| Task ID | Title | Missing / Incomplete Fields | Scaffold Action |
|---------|-------|-----------------------------|-----------------|
| P6-T1 | Full regression suite | `risks` empty | auto-filled |
| P6-T2 | Verify sprint exit criteria | `risks` empty | auto-filled |
| P6-T3 | Sprint 2 completion handoff | `risks` empty | auto-filled |

## Auto-filled Fields

- **P6-T1 risks**: "Risk: Slow tests (Taichi JIT) may timeout in CI. Mitigation: run with generous timeout; report partial results if timeout occurs."
- **P6-T2 risks**: "Risk: Exit criteria may have shifted since plan was written. Mitigation: check verification matrix for any deferred items."
- **P6-T3 risks**: "Risk: Handoff may miss lessons from earlier phases. Mitigation: read all phase handoff docs before writing."

---

## Scaffold Summary

| Metric | Value |
|--------|-------|
| Tasks scaffolded | 3 |
| Test cases assessed | 4 |
| Cases covered by existing tests | 4 |
| Cases partially covered (stubs generated) | 0 |
| Cases with no existing tests (stubs generated) | 0 |
| New stub files created | 0 |
| Total new stubs generated | 0 |
| Tasks fully covered by existing tests (no stub needed) | 1 (P6-T1) |
| Tasks that are documentation only (no stub applicable) | 2 (P6-T2, P6-T3) |
| Tasks needing human review | 0 |
| Auto-filled fields | risks (all 3 tasks) |

## Existing Test Coverage Found

| Task ID | Test case | Existing test file | Function | Coverage |
|---------|-----------|-------------------|----------|----------|
| P6-T1 | Fast suite green | all test_*.py files | all fast tests | covered |
| P6-T1 | Slow suite green | test_e2e_taichi.py, test_e2e_plastic.py, test_convergence.py, test_patch_test.py | slow-marked tests | covered |
| P6-T2 | All exit criteria verified | verification_matrix.md + existing test evidence | N/A (manual checklist) | covered |
| P6-T3 | Handoff document completeness | N/A | N/A (documentation) | N/A |

## Tasks Needing Human Review Before execute-phase

| Task ID | Title | Field | Issue |
|---------|-------|-------|-------|
| (none) | | | |

## Ready for execute-phase

Fully scaffolded:
- P6-T1: Full regression suite
- P6-T2: Verify sprint exit criteria
- P6-T3: Sprint 2 completion handoff
