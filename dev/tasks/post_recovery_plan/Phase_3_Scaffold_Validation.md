# Phase 3 Scaffold Validation

| Task ID | Title | Missing / Incomplete Fields | Scaffold Action |
|---------|-------|-----------------------------|-----------------|
| P3-1 | Add BC handoff paragraph to compile_latex docstring | `verification_commands=[""]`, `test_artifacts=[""]` (risks already populated) | auto-filled |
| P3-2 | New docstring-presence test (test_compile_latex_docstring.py) | `verification_commands=[""]`, `test_artifacts=[""]`, `risks=[]` | auto-filled |

`objective`, `acceptance_criteria`, `implementation_steps`, `deliverables`, `test_plan.tier`, `test_plan.cases` populated by Plan-2-Tasks for both tasks. No human-review flags raised.

## Existing Test Coverage Found

| Task ID | Test case | Existing test file | Function | Coverage |
|---------|-----------|-------------------|----------|----------|
| P3-1 | docstring covers public contract | `packages/mechdsl-core/tests/plan_tests/recovery_plan_latex_contract/test_p5_1.py` | `test_compile_latex_docstring_documents_taichi_stability` | partial — covers Taichi-backend paragraph; does NOT assert BoundaryCondition / f_ext substrings |

`test_p5_1.py` provides the `inspect.getdoc(compile_latex)` substring-check pattern; new P3-1 stub reuses it but adds BC-specific assertions. Logged as `partial` — both files referenced in `test_artifacts`.

## Scaffold Summary

| Metric | Value |
|--------|-------|
| Tasks scaffolded | 2 |
| Test cases assessed | 6 (P3-1: 3, P3-2: 3) |
| Cases covered by existing tests | 0 (Taichi-stability paragraph adjacent but distinct) |
| Cases partially covered (stubs generated) | 0 |
| Cases with no existing tests (stubs generated) | 6 |
| New stub files created | 2 |
| Total new stubs generated | 6 |
| Tasks fully covered by existing tests (no stub needed) | 0 |
| Tasks needing human review | 0 |
| Auto-filled fields | `verification_commands`, `test_artifacts`, `risks` (P3-2 only) |

## Tasks Needing Human Review Before Execute

| Task ID | Title | Field | Issue |
|---------|-------|-------|-------|
| — | — | — | none |

## Notes

- All P3 stubs marked `@pytest.mark.docs` (the `docs` marker, registered in Phase 2, is now a hard dependency of this phase — Phase 3 must execute on a branch that has Phase 2's commits).
- P3-1 blocker P1-5 is `done` (Phase 1 closed in PR #214 → main). P3-2 blocker P3-1 is in this phase.
- P3-2's deliverable IS a test file (`tests/test_compile_latex_docstring.py`); the stub set is a meta-spec asserting the deliverable file's existence and substring-target shape rather than re-checking the docstring directly (which P3-1's stub already does).

## Ready for Execute

Fully scaffolded:
- P3-1: Add BC handoff paragraph to compile_latex docstring
- P3-2: New docstring-presence test test_compile_latex_docstring.py

Needs human review before execution:
- (none)

Execution order (dependency-driven):
1. P3-1 (blocked by P1-5 — already done) — write the docstring paragraph.
2. P3-2 (blocked by P3-1) — author the deliverable test file.
