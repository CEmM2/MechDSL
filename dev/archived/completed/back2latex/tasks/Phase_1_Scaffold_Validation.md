# Phase 1 Scaffold Validation

| Task ID | Title | Missing / Incomplete Fields | Scaffold Action |
|---------|-------|-----------------------------|-----------------|
| P1-1 | Insert Phase ID mapping (R-label ↔ Aut_Faciam integer) table | none | passthrough |
| P1-2 | Renumber phase headings to integer + (RX) form | none | passthrough |
| P1-3 | Rewrite action-item tables with new columns | none | passthrough |
| P1-4 | Insert Code reality anchor blocks per phase | none | passthrough |
| P1-5 | Add Cross-phase dependencies blocks per phase | none | passthrough |
| P1-6 | Add 'Affects task(s)' column to risks table | none | passthrough |
| P1-7 | Add P1-6 supersession task in recovery plan | none | passthrough |
| P1-8 | Drop or fold the 'Suggested PR slices' section | none | passthrough |
| P1-9 | Update success criteria checklist with canonical-IDs row | none | passthrough |

All Phase 1 task JSONs were authored with non-empty `objective`, `acceptance_criteria` (≥3 entries each), `implementation_steps` (≥4 each), `deliverables`, `risks`, `test_plan.tier=docs`, and `test_plan.cases`. No auto-fill or human-review flags were needed.

## Existing Test Coverage Search

The recovery plan file `dev/plans/recovery_plan_latex_contract.md` is a markdown document — there are no pre-existing pytest tests that cover its structural amendments. Per scaffold protocol, every test case is classified as `missing` and a stub was generated.

## Scaffold Summary

| Metric | Value |
|--------|-------|
| Tasks scaffolded | 9 |
| Test cases assessed | 28 |
| Cases covered by existing tests | 0 |
| Cases partially covered (stubs generated) | 0 |
| Cases with no existing tests (stubs generated) | 28 |
| New stub files created | 9 |
| Total new stubs generated | 28 |
| Tasks fully covered by existing tests (no stub needed) | 0 |
| Tasks needing human review | 0 |
| Auto-filled fields | none (all fields hand-authored during Plan-2-Tasks) |

## Existing Test Coverage Found

| Task ID | Test case | Existing test file | Function | Coverage |
|---------|-----------|-------------------|----------|----------|
| (none — fresh plan) | | | | |

## Tasks Needing Human Review Before Execute

| Task ID | Title | Field | Issue |
|---------|-------|-------|-------|
| (none) | | | |

## Ready for Execute

Fully scaffolded:
- P1-1: Insert Phase ID mapping (R-label ↔ Aut_Faciam integer) table
- P1-2: Renumber phase headings to integer + (RX) form
- P1-3: Rewrite action-item tables with new columns
- P1-4: Insert Code reality anchor blocks per phase
- P1-5: Add Cross-phase dependencies blocks per phase
- P1-6: Add 'Affects task(s)' column to risks table
- P1-7: Add P1-6 supersession task in recovery plan
- P1-8: Drop or fold the 'Suggested PR slices' section
- P1-9: Update success criteria checklist with canonical-IDs row

Needs human review before execution:
- (none)

## Notes for ExecPhase

- All nine tasks are tier `docs`. Verification is grep / regex against `dev/plans/recovery_plan_latex_contract.md`. No production code changes.
- Each stub uses `@pytest.mark.audit` (the closest registered marker — there is no `docs` marker in `pyproject.toml`).
- All stubs currently `pytest.skip(...)` and must be implemented before Gate C can pass.
- Several tasks share the same target file, so parallel execution must be sequential to avoid edit collisions. The dependency graph (P1-1 → P1-2 → P1-3 → {P1-5, P1-6, P1-7}) already enforces ordering for the structural chain; P1-4, P1-8, P1-9 can interleave.
