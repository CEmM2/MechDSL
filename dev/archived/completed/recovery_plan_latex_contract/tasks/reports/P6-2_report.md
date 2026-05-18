# Task P6-2: Keep the current imported solver path as the default fallback until generated PCG is stable — Complete

**Issue:** SOSOVSKI/MechDSL#186
**Branch:** `SOSOVSKI/scaffold-phase-6`
**Implementer commit:** `4b15191`
**Started:** 2026-04-29 13:10 UTC
**Completed:** 2026-04-29 13:58 UTC

## Implementation Summary

Added `get_default_solver()` + `build_solver(mode)` factories to `packages/mechdsl-core/src/mechdsl/solver/import_adapter.py` (purely additive, lines 392-457), created new `packages/mechdsl-core/src/mechdsl/solver/integration.py` with `select_linear_solver(mode)`, and re-exported all three through `mechdsl.solver.__all__`.

**Default behaviour:** `get_default_solver()` and `build_solver()` (no args) and `select_linear_solver()` (no args) all return `ScipyCGSolver()` — the imported fallback. `build_solver("generated")` returns `Algo2CodePCGSolver`. Bad mode raises `ValueError` naming the offending value and the valid set.

**Newton driver call site is unchanged.** `linear_solver is None -> ScipyCGSolver()` at `newton.py:111-112` preserved. P6-2 adds the factory + selector API but does NOT rewire Newton to consume it — callers continue to pass `linear_solver=` explicitly when opting into the generated path. The flip-default decision is reserved for a future task once P6-3's integration test proves the generated path stable.

## Gate History

**Gate A — Spec Compliance:** 1 attempt → PASS (strict multi-axis evidence from start; lessons from P6-1 attempt-1 applied)
- Byte-diff `git diff 817853b..4b15191 -- import_adapter.py` = pure append `391a392,457` (+66 lines).
- AST hashes for 6 protected/legacy symbols (`LinearSolverInterface`, `CGSolver`, `PCGSolver`, `ScipyCGSolver`, `_identity`, `Algo2CodePCGSolver`) all match pre→post.
- Module-level side-effects added: 1 type alias `_SolverMode = Literal["fallback","generated"]` (no runtime mutation).
- Re-export identity preserved (`mechdsl.solver.X is mechdsl.solver.import_adapter.X` for all 7 ✓).
- Factory semantics verified live: defaults resolve to `ScipyCGSolver`; `"generated"` returns `Algo2CodePCGSolver`.
- Newton default branch unchanged (empty diff on `newton.py`).
- algo2code runtime invariant: zero `mechdsl` imports.
- Targeted regression: **210/210** across 14 importer modules.
- Full fast-suite: **1681 pass / 1 fail / 87 skipped**. Single fail = pre-existing scaffold TODO scanner; marker count fell 3→2 (P6-2 stub TODO removed).

**Gate B — Domain Quality:** 1 attempt → APPROVED, score 9/10 (0 critical, 0 high, 0 medium, 1 minor — fixed in batch)
- Naming aligned with recovery-plan vocabulary; docstrings cite line 318; mode-validation error helpful (`ValueError(f"Unknown solver mode {mode!r}; ...")`).
- `integration.py` thin (61 lines, pure delegation); `select_linear_solver` purity confirmed.
- Tests: SPD tridiagonal genuinely SPD; tolerances appropriate; cross-mode solution comparison non-trivial; AST audit of Newton default robust.
- 1 minor — comment at `import_adapter.py:404-407` claimed `Literal` couldn't live in `TYPE_CHECKING` due to `typing.get_type_hints`. Both halves wrong: `from __future__ import annotations` (line 15) makes annotations lazy; `get_type_hints` already fails because `Callable` is `TYPE_CHECKING`-only. Real reason: byte-identity protection of P6-1's lines 1-391. Comment replaced with correct rationale; AST-hash re-check confirms zero behavioural drift.

**Gate C — Verification:** 1 attempt → PASS
- `test_p6_2.py` 2/2 pass.
- `test_solver.py` 18/18 pass (regression sentinel green).
- Aggregate: **20/20 (100%)**. Iron Law satisfied.

## Failure Patterns

None. Gate A passed first attempt with strict evidence (the lesson encoded after P6-1 attempt-1). Gate B's minor was caught and fixed in the same close commit.

## Files Changed

- `packages/mechdsl-core/src/mechdsl/solver/import_adapter.py` (+66 lines appended at 392-457: `_Literal` import, `_SolverMode` alias, `get_default_solver`, `build_solver`). Comment corrected during Gate B. Lines 1-391 byte-identical.
- `packages/mechdsl-core/src/mechdsl/solver/integration.py` (new, 61 lines, `select_linear_solver`).
- `packages/mechdsl-core/src/mechdsl/solver/__init__.py` (added imports + `__all__` entries `build_solver`, `get_default_solver`, `select_linear_solver`).
- `packages/mechdsl-core/tests/plan_tests/recovery_plan_latex_contract/test_p6_2.py` (both stubs fleshed out: factory + dual-mode regression, AST audit of Newton default, surface-presence + algo2code-runtime-free + default-is-fallback).

## Test Evidence

```
$ uv run pytest packages/mechdsl-core/tests/plan_tests/recovery_plan_latex_contract/test_p6_2.py -v
============================== 2 passed in 0.38s ===============================

$ uv run pytest packages/mechdsl-core/tests/test_solver.py -v
============================== 18 passed in 0.33s ==============================
```

Targeted regression (Gate A evidence): `210 passed, 46 deselected in 14.32s` across 14 importer modules.
Full fast-suite (Gate A evidence): `1681 passed, 1 failed, 87 skipped, 113 deselected, 2 warnings in 55.65s` — single fail pre-existing.

## Open Questions / Deferred Items

1. **Default flip** — once P6-3's integration test proves the generated path stable, a future task may switch the default. Out of P6-2 scope.
2. **Design-doc sync** — `dev/design_docs/11-ALGO2CODE.md` does not yet mention `build_solver` / `select_linear_solver` factory vocabulary. P6-5 owns docs sweep; the gap is a known carry-forward, unchanged by P6-2.
3. **Newton end-to-end through factory** — `newton_solve(linear_solver=select_linear_solver("generated"))` is the documented opt-in pattern. P6-3 will exercise the full chain.

## Lessons Reused / Added

- **Reused:** strict Gate A multi-axis evidence pattern from P6-1 (byte-diff + AST hashes + side-effect audit + identity check + Protocol semantics + targeted regression + full fast-suite). Made Gate A pass first attempt rather than failing on insufficient evidence.
- **Added:** when adding module-level imports below a byte-identity-protected block, document the protection rationale in the comment, not a fabricated technical reason — future readers will misread fabricated rationales and potentially "fix" them at the cost of breaking byte-identity.
