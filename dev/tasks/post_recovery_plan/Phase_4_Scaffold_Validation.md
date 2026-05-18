# Phase 4 Scaffold Validation

| Task ID | Title | Missing / Incomplete Fields | Scaffold Action |
|---------|-------|-----------------------------|-----------------|
| P4-1 | New frontend/math_parser.py wrapping nrpylatex | `verification_commands=[""]`, `test_artifacts=[""]` (risks already populated) | auto-filled |
| P4-2 | symbolic/bridge.py adapter | `verification_commands=[""]`, `test_artifacts=[""]` | auto-filled |
| P4-3 | Wire math parser into frontend pipeline | `verification_commands=[""]`, `test_artifacts=[""]` | auto-filled |
| P4-4 | New test_nrpylatex_round_trip.py | `verification_commands=[""]`, `test_artifacts=[""]` | auto-filled |
| P4-5 | Add svk_latex_math.tex example + README inventory | `verification_commands=[""]`, `test_artifacts=[""]`, `risks=[]` | auto-filled |

`objective`, `acceptance_criteria`, `implementation_steps`, `deliverables`, `test_plan.tier`, `test_plan.cases` populated by Plan-2-Tasks for all five tasks. No human-review flags raised.

## Existing Test Coverage Found

| Task ID | Test case | Existing test file | Function | Coverage |
|---------|-----------|-------------------|----------|----------|
| (all) | nrpylatex / math_parser / symbolic.bridge | — | — | none — Phase 4 is purely additive (no `nrpylatex`, `math_parser.py`, or `bridge.py` exists in src/) |

`grep -rln "nrpylatex\|math_parser\|symbolic/bridge" packages/mechdsl-core/ --include="*.py"` returns zero matches. All P4 cases are new.

## Scaffold Summary

| Metric | Value |
|--------|-------|
| Tasks scaffolded | 5 |
| Test cases assessed | 16 (P4-1: 3, P4-2: 4, P4-3: 3, P4-4: 4 incl. file-existence, P4-5: 3 incl. file-existence) |
| Cases covered by existing tests | 0 |
| Cases partially covered (stubs generated) | 0 |
| Cases with no existing tests (stubs generated) | 16 |
| New stub files created | 5 |
| Total new stubs generated | 16 |
| Tasks fully covered by existing tests (no stub needed) | 0 |
| Tasks needing human review | 0 |
| Auto-filled fields | `verification_commands`, `test_artifacts`, `risks` (P4-5 only) |

## Tasks Needing Human Review Before Execute

| Task ID | Title | Field | Issue |
|---------|-------|-------|-------|
| — | — | — | none |

## Notes

- P4-1 / P4-2 / P4-3 are higher-complexity than Phase 3 work. Per the Aut_Faciam model assignment rule, complexity ≥ 3 should dispatch Sonnet/Opus subagents during exec; combined-score > 6 mandates Opus 4.6. Complexity scoring lives in `Phase_4_Tasks_analysis.md` (written at exec time).
- P4-4's deliverable is the production round-trip test file (`tests/test_nrpylatex_round_trip.py`); the stub set is a meta-spec asserting its existence and case coverage.
- P4-5's deliverable is the example file + README entry; stub set asserts file-presence and end-to-end compile via `compile_latex`.
- All P4 stubs use tiers per task JSON (`unit` for P4-1/P4-2, `integration` for P4-3/P4-4/P4-5). None marked `docs`; P4 produces machinery, not docs.

## Ready for Execute

Fully scaffolded:
- P4-1: New frontend/math_parser.py wrapping nrpylatex
- P4-2: symbolic/bridge.py adapter — nrpylatex AST → mechdsl symbolic
- P4-3: Wire math parser into frontend/__init__.py pipeline
- P4-4: New test_nrpylatex_round_trip.py covering SVK PK1, J2 yield, two-point tensor
- P4-5: Add dev/examples/svk_latex_math.tex + README inventory entry

Needs human review before execution:
- (none)

Execution order (dependency-driven):
1. P4-1 and P4-2 (parallel — no blockers).
2. P4-3 (blocked by P4-1 + P4-2).
3. P4-4 and P4-5 (parallel — both blocked by P4-3 only).
