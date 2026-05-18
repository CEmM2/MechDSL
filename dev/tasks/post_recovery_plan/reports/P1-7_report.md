# Task P1-7: Golden test test_boundary_neumann.py — Complete

## Implementation Summary

New golden snapshot test for the Neumann `f_ext` kernel emitter. Mirrors the existing `TestGoldenSnapshot` pattern in `test_codegen.py`:
- `_UPDATE_GOLDEN` flag for intentional regen.
- First run auto-generates `tests/golden/boundary_neumann.ti.txt` and skips.
- Subsequent runs assert strict `source == golden` equality.
- Side-by-side syntactic-validity check parses the golden with a stub preamble.

Canonical fixture: traction `(0.0, 0.0, -1000.0)` on surface tag `z1`.

P1-7 dedicated audit (3 cases) verifies the test file, golden artifact, and strict-equality assertion exist.

## Gate History

- **Gate A:** 1 attempt → Pass.
- **Gate B:** 1 attempt → Pass.
- **Gate C:** 1 attempt → Pass. 3/3 P1-7 audit, 3/3 golden test (after auto-generate cycle), 1715/1715 full fast suite.

## Failure Patterns

None this task. Clean across all gates.

## Files Changed

- `packages/mechdsl-core/tests/test_boundary_neumann.py` — new (110 LOC)
- `packages/mechdsl-core/tests/golden/boundary_neumann.ti.txt` — new (24 lines)
- `packages/mechdsl-core/tests/plan_tests/post_recovery_plan/test_p1_7.py` — 3 audit tests
- task JSON, gates, tracker

## Test Evidence

```
test_p1_7.py:               3/3 (0.04s)
test_boundary_neumann.py:   3/3 (0.06s)
fast suite:                 1715/1715 (+6 vs P1-6)
ruff:                       clean
```

## Commit

`(P1-7 commit, see git log)` — test(boundary): golden snapshot for emitted Neumann f_ext kernel (P1-7)

## Open Questions

None.

## Downstream Impact

**Phase 1 complete.** All 7 tasks (P1-1 through P1-7) done with all gates passing. Ready for `/Aut_Faciam exec 2` (Phase 2: docs marker registration) or any future task.
