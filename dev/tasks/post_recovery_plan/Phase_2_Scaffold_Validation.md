# Phase 2 Scaffold Validation

| Task ID | Title | Missing / Incomplete Fields | Scaffold Action |
|---------|-------|-----------------------------|-----------------|
| P2-1 | Register `docs` pytest marker in pyproject.toml and tests.md | `verification_commands=[""]`, `test_artifacts=[""]`, `risks=[]` | auto-filled |
| P2-2 | Swap @pytest.mark.integration → @pytest.mark.docs in test_p7_3..6.py | `verification_commands=[""]`, `test_artifacts=[""]`, `risks=[]` | auto-filled |
| P2-3 | Audit and update CI workflow tier:docs selector | `verification_commands=[""]`, `test_artifacts=[""]` (risks already populated) | auto-filled |

All three tasks had blank `verification_commands` and `test_artifacts` arrays at scaffold start; these were auto-filled from the test stubs generated in Step 3 plus the file lists implied by `scope` / `deliverables`. P2-1 and P2-2 had empty `risks` arrays, inferred from `implementation_steps` (TOML edits under `--strict-markers`; cross-job CI selector race condition).

`objective`, `acceptance_criteria`, `implementation_steps`, and `deliverables` were already fully populated by Plan-2-Tasks for all three tasks — no human-review flags raised.

## Scaffold Summary

| Metric | Value |
|--------|-------|
| Tasks scaffolded | 3 |
| Test cases assessed | 8 (P2-1: 3, P2-2: 3, P2-3: 2) |
| Cases covered by existing tests | 0 |
| Cases partially covered (stubs generated) | 0 |
| Cases with no existing tests (stubs generated) | 8 |
| New stub files created | 3 |
| Total new stubs generated | 7 (P2-1: 3, P2-2: 2, P2-3: 2) |
| Tasks fully covered by existing tests (no stub needed) | 0 |
| Tasks needing human review | 0 |
| Auto-filled fields | `verification_commands`, `test_artifacts`, `risks` (P2-1, P2-2 only) |

## Existing Test Coverage Found

| Task ID | Test case | Existing test file | Function | Coverage |
|---------|-----------|-------------------|----------|----------|
| P2-1 | docs marker registered in pyproject | `packages/mechdsl-core/tests/plan_tests/recovery_plan_latex_contract/test_p7_1.py` | `_read_registered_markers` (helper, not direct test) | partial — helper exists but no doc-tier marker assertion |

P2-1's stub reuses the `_read_registered_markers` parsing pattern from `test_p7_1.py` but adds `docs`-specific assertions. Logged as `partial` so both files are referenced in `test_artifacts`-style follow-ups during exec, but only the new stub is required for verification.

## Tasks Needing Human Review Before Execute

| Task ID | Title | Field | Issue |
|---------|-------|-------|-------|
| — | — | — | none |

## Notes

- P2-2 stub uses `@pytest.mark.unit` (not `@pytest.mark.docs`) because the meta-stub verifies *source-file state* and must run in the fast suite **before** `docs` is registered. The task JSON's `test_plan.tier = docs` still describes the swap target; the stub itself is unit-tier.
- P2-3 stubs use `@pytest.mark.integration` (parses YAML files crossing tooling layer) — appropriate per existing tier conventions.
- No existing tests need re-tagging; the stubs are additive.

## Ready for Execute

Fully scaffolded:
- P2-1: Register `docs` pytest marker in pyproject.toml and tests.md
- P2-2: Swap @pytest.mark.integration → @pytest.mark.docs in test_p7_3..6.py
- P2-3: Audit and update CI workflow tier:docs selector

Needs human review before execution:
- (none)

Execution order (dependency-driven):
1. P2-1 (no blockers) — register marker.
2. P2-2 (blocked by P2-1) — swap decorators.
3. P2-3 (blocked by P2-1, parallelizable with P2-2) — CI audit.
