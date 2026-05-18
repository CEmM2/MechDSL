# Phase 4 Scaffold Validation

| Task ID | Title | Missing / Incomplete Fields | Scaffold Action |
|---------|-------|------------------------------|-----------------|
| P4-1 | Add structured execution-contract fields to `ElementIR` | `verification_commands`, `test_artifacts` | auto-filled |
| P4-2 | Demote `EinsumSpec` / `LocalisationResult` to derived views | `verification_commands`, `test_artifacts` | auto-filled |
| P4-3 | Lowering emits richer `ElementIR` first | `verification_commands`, `test_artifacts` | auto-filled |
| P4-4 | Unsupported stable-path combos fail in lowering with phase pointer | `verification_commands`, `test_artifacts` | auto-filled |
| P4-5 | Artifact bundling reflects enriched IR ownership | `verification_commands`, `test_artifacts` | auto-filled |

## Scaffold Summary

| Metric | Value |
|--------|-------|
| Tasks scaffolded | 5 |
| Test cases assessed | 10 |
| Cases covered by existing tests | 0 |
| Cases partially covered (stubs generated) | 0 |
| Cases with no existing tests (stubs generated) | 10 |
| New stub files created | 5 |
| Total new stubs generated | 10 |
| Tasks fully covered by existing tests (no stub needed) | 0 |
| Tasks needing human review | 0 |
| Auto-filled fields | `verification_commands`, `test_artifacts` |

## Existing Test Coverage Found

None — Phase 4 introduces new IR shapes and lowering boundaries that did not exist before, so every case maps to a fresh stub.

| Task ID | Test case | Existing test file | Function | Coverage |
|---------|-----------|-------------------|----------|----------|
| (none) | | | | |

## Tasks Needing Human Review Before Execute

| Task ID | Title | Field | Issue |
|---------|-------|-------|-------|
| (none) | | | |

## Ready for Execute

Fully scaffolded:
- P4-1: Add structured execution-contract fields to `ElementIR`
- P4-2: Demote `EinsumSpec` / `LocalisationResult` to derived views
- P4-3: Lowering emits richer `ElementIR` first
- P4-4: Unsupported stable-path combos fail in lowering with phase pointer
- P4-5: Artifact bundling reflects enriched IR ownership

Needs human review before execution:
- (none)

## Notes

- All five task JSONs already had populated `objective`, `acceptance_criteria`, `implementation_steps`, `deliverables`, `risks`, `test_plan.tier`, and `test_plan.cases` from Plan-2-Tasks. The only fields that needed filling were the test-artifact and verification-command paths the new stub files satisfy.
- Stubs live at `packages/mechdsl-core/tests/plan_tests/recovery_plan_latex_contract/test_p4_{1..5}.py`.
- Dependency order for execute: **P4-1 → P4-2 → P4-3 → P4-4 → P4-5** (P4-2 blocks on P4-1; P4-3 blocks on P4-1, P4-2; P4-4 blocks on P4-1, P4-3; P4-5 blocks on P4-1).
