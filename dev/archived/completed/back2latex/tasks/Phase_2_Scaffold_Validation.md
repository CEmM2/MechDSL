# Phase 2 Scaffold Validation

| Task ID | Title | Missing / Incomplete Fields | Scaffold Action |
|---------|-------|-----------------------------|-----------------|
| P2-1 | Skim verification of amended recovery plan | none | passthrough |
| P2-2 | Run /Aut_Faciam tasks on amended recovery plan | none | passthrough |
| P2-3 | Spot-check three generated task JSONs | none | passthrough |
| P2-4 | Run /Aut_Faciam scaffold 1 on recovery plan and stop | none | passthrough |

All Phase 2 task JSONs have non-empty `objective`, `acceptance_criteria` (≥3 entries), `implementation_steps` (≥4 each), `deliverables`, `risks`, `test_plan.tier`, and `test_plan.cases`.

## Existing Test Coverage Search

The verification artifacts Phase 2 produces (recovery-plan task tree, GitHub issues for the recovery plan) live entirely under namespaces created *during* Phase 2 itself. There is no pre-existing pytest coverage of these artifacts; every test case is `missing` and a stub was generated.

## Scaffold Summary

| Metric | Value |
|--------|-------|
| Tasks scaffolded | 4 |
| Test cases assessed | 14 |
| Cases covered by existing tests | 0 |
| Cases partially covered (stubs generated) | 0 |
| Cases with no existing tests (stubs generated) | 14 |
| New stub files created | 4 |
| Total new stubs generated | 14 |
| Tasks fully covered by existing tests (no stub needed) | 0 |
| Tasks needing human review | 0 |
| Auto-filled fields | none (all fields hand-authored during Plan-2-Tasks) |

## Existing Test Coverage Found

| Task ID | Test case | Existing test file | Function | Coverage |
|---------|-----------|-------------------|----------|----------|
| (none) | | | | |

## Tasks Needing Human Review Before Execute

| Task ID | Title | Field | Issue |
|---------|-------|-------|-------|
| (none) | | | |

## Ready for Execute

Fully scaffolded:
- P2-1: Skim verification of amended recovery plan (audit-tier, runs immediately)
- P2-2: Run /Aut_Faciam tasks on amended recovery plan (integration-tier; tests `pytest.skip` until artifacts exist)
- P2-3: Spot-check three generated task JSONs (audit-tier; skips until JSONs exist)
- P2-4: Run /Aut_Faciam scaffold 1 on recovery plan and stop (integration-tier; skips until phase_1_gates.md and 6 task issues exist; includes hard-stop invariant test)

## Notes for ExecPhase

- P2-1 is the only task whose tests pass before exec begins (it just confirms the amended plan is shape-correct).
- P2-2, P2-3, P2-4 use `pytest.skip(...)` until their respective artifacts exist on disk. After exec, they all flip to live assertions.
- Phase 2 is strictly serial (P2-1 → P2-2 → P2-3 → P2-4); parallelism is not legal here because each task's output is the next task's input.
- P2-4's `test_no_exec_artifacts_present` is the hard-stop invariant: if anyone runs `/Aut_Faciam exec 1` against the recovery plan in this engagement, that test will fail.
