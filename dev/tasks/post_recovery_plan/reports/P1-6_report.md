# Task P1-6: Replace numeric f_ext injection in test_p7_2 — Complete

## Implementation Summary

`test_p7_2` no longer constructs `f_ext` by hand. Neumann directive is the sole source:
- `CANONICAL_LATEX_SOURCE` updated to `--traction "1 0 0" --surface x1`.
- Bundle source spliced (`bundle.emitted_source + bundle.f_ext_kernel`) so imported module exposes both `newton_solve` and `init_f_ext_from_neumann_load`.
- `mod.f_ext.from_numpy(f_ext)` replaced with `mod.init_f_ext_from_neumann_load(right, f_factor)`.
- Reference solver `f_ext` uses identical per-node value (`traction[0] * f_factor = 0.25`), preserving < 1e-10 tolerance comparison.
- Placeholder traction-string-gap comment removed (closes follow-up item 9).

P1-6 dedicated audit tests (`test_p1_6.py`, 5 cases) scan target for obsolete patterns. Marked `unit` for now; switch to `docs` tier in P2-1.

## Gate History

- **Gate A:** 1 attempt → Pass.
- **Gate B:** 1 attempt → Pass. End-to-end LaTeX → JIT → reference comparison preserved.
- **Gate C:** 2 attempts. First failed `test_gap` — audit asserter matched a comment that mentioned the removed `mod.f_ext.from_numpy` pattern while documenting its removal. Resolved by rewording comment.

## Failure Patterns

`test_gap` recurrence — same category as P1-4 Gate C failure. Both involved test assertions matching too literally on artifacts the implementation produced or referenced.

## Files Changed

- `tests/plan_tests/recovery_plan_latex_contract/test_p7_2.py` — directive-driven rewrite of acceptance test
- `tests/plan_tests/post_recovery_plan/test_p1_6.py` — 5 audit tests
- task JSON, gates, tracker

## Test Evidence

```
test_p1_6.py:           5/5 (0.04s)
test_p7_2.py (slow+e2e): 2/2 (2.39s, JIT cached)
fast suite:             1709/1709 (+5 vs P1-5)
ruff check:             clean
```

## Commit

`e23de63` — test(p7_2): drive Neumann load via directive-only path (P1-6)

## Open Questions

- The splice pattern (`emitted_source + f_ext_kernel`) is a test-only convenience. A future task could integrate the Neumann kernel into the main emission flow at the codegen layer, dropping the manual splice. Not blocking for Phase 1.

## Downstream Impact

- Phase 1 chain progress: P1-1..P1-6 done. Only P1-7 (golden test) remains.
- P7-3 (Phase 7) item 9 / forward-pointer comment: superseded — placeholder comment is gone, P7-3's fallback path no longer needed.
