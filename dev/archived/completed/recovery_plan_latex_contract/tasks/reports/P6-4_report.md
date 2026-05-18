# Task P6-4: Defer radial-return replacement until frontend + IR alignment is settled — Complete

**Issue:** SOSOVSKI/MechDSL#184
**Branch:** `SOSOVSKI/scaffold-phase-6`
**Implementer commit:** `5c310a0`
**Started:** 2026-04-29 17:30 UTC
**Completed:** 2026-04-29 18:08 UTC

## Implementation Summary

Docs-only callout added to `dev/plans/recovery_plan_latex_contract.md:323-335` immediately after the Phase-6 action-item table. Callout pins radial-return substitution to "later-stage, deferred" work behind R2 (frontend) + R3 (IR alignment), names the constitutive-contract rationale, scopes the first integration wave to the linear-solver seam (P6-1..P6-3), and tags the work `post-MVP` relative to Phase 6's exit criteria.

Test stubs in `test_p6_4.py` fleshed out with real assertions exercising the callout text. Stale TODO comment removed.

**Zero production-code touches.** `git diff 02055a6..5c310a0 -- packages/mechdsl-core/src/ packages/algo2code/src/` empty.

## Gate History

**Gate A — Spec Compliance:** 1 attempt → PASS (strict, multi-axis evidence)
- Zero production-code drift.
- Recovery-plan callout present with all required tokens (`radial-return`, `later-stage`, `deferred`, `post-MVP`, `Phase 2 / R2`, `Phase 3 / R3`).
- Test assertions match acceptance criteria.
- Targeted P6 + phase6_exit regression: **50/50 pass**.
- Full fast-suite: **1686 pass / 0 fail / 83 skipped**. Phase-6 TODO scanner sentinel (`test_phase6_exit::test_no_resolved_todos_or_fixmes_remain`) now resolved.
- algo2code runtime invariant unchanged.
- Newton default branch unchanged.

**Gate B — Domain Quality:** 1 attempt → APPROVED, score 10/10 (operator-direct review)
- Placement at `recovery_plan_latex_contract.md:323-335` — natural break after Phase-6 table, before "Required constraints".
- Voice consistent with plan's existing callout style; legacy-ID format `R2`/`R3` matches the action-item table column.
- Accuracy: Phase 2 = R2 (frontend), Phase 3 = R3 (IR) verified. Constitutive-contract rationale correct.
- Consistency: amplifies the existing line-340 constraint without contradiction.
- Completeness: rationale + scope + reactivation condition + tier marker.
- Zero issues (no critical, no high, no medium, no minor).

**Gate C — Verification:** 1 attempt → PASS
- `test_p6_4.py` 2/2 pass.
- Wider fast-suite confirmed clean in Gate A (1686/0).
- Aggregate: **2/2 (100%)**. Iron Law satisfied.

## Failure Patterns

None. Strict-Gate-A protocol caught zero defects. Gate B 10/10 with no issues at any severity.

## Files Changed

- `dev/plans/recovery_plan_latex_contract.md` — blockquote callout inserted at lines 323-335.
- `packages/mechdsl-core/tests/plan_tests/recovery_plan_latex_contract/test_p6_4.py` — both stubs fleshed out; stale TODO comment removed.

## Test Evidence

```
$ uv run pytest packages/mechdsl-core/tests/plan_tests/recovery_plan_latex_contract/test_p6_4.py -v
============================== 2 passed in 0.03s ===============================

Phase-6 TODO scanner sentinel:
$ uv run pytest packages/mechdsl-core/tests/test_phase6_exit.py::TestTaskP6T5::test_no_resolved_todos_or_fixmes_remain -v
============================== 1 passed in 0.06s ===============================

Full fast-suite (Gate A evidence):
1686 passed, 83 skipped, 113 deselected, 2 warnings in 53.24s
(zero failures — first time in Phase 6 the fast-suite is fully green)
```

## TODO Marker Fall-Through Arc

Tracking `test_phase6_exit::test_no_resolved_todos_or_fixmes_remain` across Phase 6:

| Commit | Phase event | Marker count |
|---|---|---|
| `d4f261e` | Scaffold (P6-{1..5} stubs landed with TODO comments) | 4 |
| `199dedc` | P6-1 implementation (test_p6_1.py TODO removed) | 3 |
| `4b15191` | P6-2 implementation (test_p6_2.py TODO removed) | 2 |
| `f498880` | P6-3 implementation (test_p6_3.py TODO removed) | 1 |
| **`5c310a0`** | **P6-4 implementation (test_p6_4.py TODO removed)** | **0 ✓** |

## Open Questions / Deferred Items

1. **Optional design-doc cross-link** in `dev/design_docs/11-ALGO2CODE.md` (after the Plan-A Phase-A9 J2 radial-return paragraph at line 37) was blocked by the `.claude/hooks/protect-spec.sh` hook. Operator decision required: either (a) add the cross-link via direct human edit, or (b) accept that the recovery-plan callout is the single canonical surface. Either is consistent with P6-4's acceptance criteria; the recovery plan is the mandatory surface and is in place.
2. **P6-5 still owes** the design-doc sync on §2.5 (canonical PCG LaTeX). That is a P6-1 Gate-B carry-forward, not introduced by P6-4.

## Lessons Reused / Added

- **Reused:** strict Gate A multi-axis evidence pattern. For docs-tier the protected-symbols proof is trivial (zero src touches) but the wider-regression sweep still adds real value (caught the phase6_exit sentinel resolution as a bonus).
- **Added:** the TODO-fall-through tracking pattern — recording marker count across each Phase-6 commit makes visible the way scaffold-introduced obligations get retired one task at a time. Useful sentinel for future phases.
