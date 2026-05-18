# Task P1-3: UL residual emission — Complete

**Issue:** #69 | **Branch:** `claude/modest-johnson_phase-1`
**Impl commit:** `a364b4b` | **Bookkeeping:** `a7c3469`

## Implementation Summary

Extended `emit_internal_force_kernel` in `taichi_printer.py` with an Updated
Lagrangian branch that emits the Cauchy-stress residual integrand over the
current (deformed) configuration:

    f_int[a,i] += w_q * detj * sigma_{ij} * dN_a/dx_j

where sigma = (1/J) F @ S @ F^T (push-forward from PK2).

Key additions:
- `_emit_ul_force_qp_inner(ctx, is_plastic)` — private helper emitting the
  full UL QP body (current Jacobian j, spatial gradients dNdx, reference
  Jacobian J0 for F, constitutive update returning PK2, push-forward to
  Cauchy, scatter with detj).
- Python-time configuration dispatch: `if configuration == "current"` calls
  the UL helper; `else` keeps the TL body inline (unchanged).
- New UL golden `generated_ul_svk.py.golden`.

## Gate History

| Gate | Attempts | Result | Score |
|------|----------|--------|-------|
| A — Spec | 1 | PASS | all 4 criteria |
| B — Domain | 1 | PASS | **10/10** |
| C — Verification | 1 | PASS | 1020/1020, 0 fail |

## Failure Patterns

None. Zero gate failures.

## Files Changed

| File | Status | Purpose |
|------|--------|---------|
| `src/mechdsl/codegen/taichi_printer.py` | modified | UL branch + `_emit_ul_force_qp_inner` helper |
| `tests/test_taichi_printer_ul.py` | rewritten | 4 P1-3 tests (real assertions), 4 P1-4 stubs |
| `tests/golden/generated_ul_svk.py.golden` | new | UL SVK golden snapshot |

## Test Evidence

```
4/4 P1-3 tests PASSED, 3/3 TL golden tests PASSED
Full suite: 1020 passed, 10 skipped, 0 failed (23.52s)
```

## Open Questions

None.
