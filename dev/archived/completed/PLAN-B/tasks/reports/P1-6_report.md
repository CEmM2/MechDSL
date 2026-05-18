# Task P1-6: Formulation switching (directive + codegen dispatch) — Complete

## Implementation Summary

Wired the `% mechanics formulation updated_lagrangian` directive end-to-end through the FEM compiler pipeline. The key change: `ProblemIR.__post_init__` now auto-infers `Configuration` from `Formulation` when not explicitly provided (`configuration: Configuration | None = None`). This means callers only need to set `formulation='updated_lagrangian'` — the IR handles the rest.

Most of P1-6's originally scoped work (removing the UL rejection in `build_context`, inverting rejection tests) was pre-empted by P1-1. The remaining gap was the formulation→configuration auto-inference that makes the end-to-end pipeline seamless.

## Gate History

**Gate A:** 1 attempt -> Pass
**Gate B:** 1 attempt -> Pass (10/10)
**Gate C:** Tests 1027/1031 (99.6%)

No failures across any gate.

## Files Changed

| File | Change |
|------|--------|
| `packages/mechdsl-core/src/mechdsl/ir/mechanics_ir.py` | Auto-infer Configuration from Formulation in `__post_init__`; update `from_dict` to pass None for missing config |
| `packages/mechdsl-core/tests/test_formulation_switching.py` | 4 integration tests: UL directive parse, TL/UL distinct output, rejection unchanged, programmatic round-trip |

## Test Evidence

- Full fast suite: **1027 passed**, 4 skipped, 51 deselected, 0 failed (18.16s)
- Task-scoped: `test_formulation_switching.py` -> 4/4 PASSED
- Verification commands: 58/58 PASSED (build_context + parser + FormulationGuard)
- Ruff: clean. Mypy: clean.

## Open Questions

None. P1-7 (TL/UL equivalence + rigid rotation tests) is now unblocked — it was the last task waiting on P1-6.
