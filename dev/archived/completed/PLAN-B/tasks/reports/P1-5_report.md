# Task P1-5: Objective stress rates — Complete

**Issue:** #67
**Branch:** `claude/modest-johnson_phase-1`
**Implementation commit:** `82f3d4a`
**Bookkeeping commit:** `c5e5bb6`
**Started / Completed:** 2026-04-15

## Implementation Summary

Added a new module `mechdsl.symbolic.objective_rates` with two layers of API
to support Updated Lagrangian rate-form constitutive models:

1. **Direct rate functions** (scope addition — see Gate B m1):
   - `jaumann_rate(sigma_dot, L, sigma)` — `sigma_dot - W @ sigma - sigma @ W.T`
   - `truesdell_rate(sigma_dot, L, sigma)` — `sigma_dot - L @ sigma - sigma @ L.T + sigma * tr(D)`
   - `green_naghdi_rate(sigma_dot, Omega, sigma)` — `sigma_dot - Omega @ sigma - sigma @ Omega.T`

2. **Spatial tangent conversions** (scope API):
   - `truesdell_tangent(C4, sigma)` — identity push-forward at F = I
   - `jaumann_tangent(C4, sigma)` — adds Prandtl-Reuss correction `T(sigma)`
   - `green_naghdi_tangent(C4, sigma, R)` — reduces to Jaumann at R = I, raises
     `NotImplementedError` for R ≠ I (fail-fast seam for future large-rotation work)

**Interpretive decision (logged in Gate B):** the P1-5 scope names three
`*_tangent` functions AND asks for a rigid-rotation invariance test.
Mathematically those live on different surfaces — rigid rotation gives `D = 0`
which makes any `c : D` trivially zero. The module therefore exposes **both**
a direct-rate layer (for the invariance test) and the tangent layer (for
P1-4's UL emission). The scaffold test names `test_*_tangent_at_rigid_rotation_*`
were preserved; the bodies call the rate functions with docstrings explaining
what is actually verified.

## Gate History

**Gate A (Spec Compliance):** 1 attempt → PASS
  - All 3 acceptance criteria met: NumPy-only pure functions, rigid-rotation
    invariance for all three rates, simple-shear Jaumann matches Prandtl-Reuss
    hand calc at both rank-4 and rank-2 levels.

**Gate B (Domain Quality):** 1 attempt → PASS — 8/10
  - 2 minor issues flagged:
    - **m1 (scope drift):** Direct rate functions added beyond stated scope
      to make the rigid-rotation test meaningful. Tiny, well-documented,
      likely consumed by P1-7 verification. Cost of removal ≈ 10 min.
    - **m2 (deferred):** `truesdell_tangent` assumes F = I. Full-F
      push-forward `c_ijkl = (1/J) F_iI F_jJ F_kK F_lL C_IJKL` is the
      documented seam if a later phase needs it. Not required for P1-4's
      first-pass UL necking bar (quasi-static).
  - 0 medium / high / critical issues.
  - Physics checks: Jaumann/Truesdell/Green-Naghdi rigid-rotation
    cancellation verified by the derivation in the module docstring and
    exercised at 1e-12 in the tests. Prandtl-Reuss correction derived at
    both rank-4 and rank-2 levels and cross-checked.
  - Code quality: follows `j2_power_law.py` ASCII-math convention (sigma,
    Omega, delta, lam, mu) to pass ruff RUF002 repo-wide. `Mat33` /
    `Tensor4` type aliases match `lib/tensor_ops.py`.

**Gate C (Verification):** 1 attempt → PASS
  - Full fast suite: **1013 passed, 13 skipped, 0 failed** (24.02s, fresh run).
  - Task-scoped: **4/4** on `test_objective_rates.py`.
  - Ruff check: clean on both files.
  - Ruff format --check: "2 files already formatted".
  - Mypy: "Success: no issues found in 1 source file".

## Failure Patterns

None. No gate failures during this task.

One Gate B iteration was triggered by a **lint issue** (not a gate failure):
my first pass of `objective_rates.py` used Greek letters (σ, Ω, δ) in
docstrings, which ruff's RUF002 confusables rule flagged (122 errors). I
rewrote both files to ASCII math notation matching the existing
`j2_power_law.py` convention and re-ran — ruff, mypy, and tests all clean.
This is a **style-violation** category event, caught before Gate A was
officially scored, so it does not appear in the gates file as a fail cycle.

**Future signal:** the project's ruff config has `RUF002` enabled. Any new
math-heavy module should use ASCII math notation (`sigma`, `omega`, `alpha`,
`delta`, `mu`, `lam`) in docstrings and comments. The existing convention is
in `mechdsl/symbolic/models/j2_power_law.py` — read that first when adding
a new symbolic module.

## Files Changed

| File | Status | Purpose |
|------|--------|---------|
| `packages/mechdsl-core/src/mechdsl/symbolic/objective_rates.py` | new | Two-layer API (rate functions + tangent conversions) |
| `packages/mechdsl-core/tests/test_objective_rates.py` | rewritten | 4 asserting tests replace the pytest.skip stubs from scaffold |
| `dev/tasks/PLAN-B/json/P1-5.json` | status update | `done`, review_score 8, completion_date |
| `dev/tasks/PLAN-B/gates/phase_1_gates.md` | append | P1-5 gate entries |
| `dev/tracking/tasks-tracker_PLAN-B.md` | row update | P1-5 → done |

## Test Evidence

```
$ uv run pytest packages/mechdsl-core/tests/test_objective_rates.py -v
test_jaumann_tangent_at_rigid_rotation_gives_zero_cauchy_rate    PASSED [ 25%]
test_truesdell_tangent_at_rigid_rotation_gives_zero_cauchy_rate  PASSED [ 50%]
test_green_naghdi_tangent_at_rigid_rotation_gives_zero_cauchy_rate PASSED [ 75%]
test_jaumann_tangent_on_simple_shear_matches_hand_calculation    PASSED [100%]
4 passed in 0.24s

$ uv run pytest packages/mechdsl-core/tests/ -m 'not slow and not gpu'
1013 passed, 13 skipped, 51 deselected, 29 warnings in 24.02s
```

## Open Questions

1. **P1-4 consumption path:** my `truesdell_tangent(C4, sigma)` assumes
   `F = I`. P1-4 emits into `taichi_printer.py` at a quadrature point where
   `F` is typically ≠ I. The simplest path is for P1-4 to call
   `jaumann_tangent` at each QP treating the local `sigma` and `C` as
   already-pushed-forward. This works correctly because the rate-form
   material term `c^Jau : D` at that QP uses the local F to define L and
   hence D, not to re-push the tangent. **Action:** P1-4 implementer to
   verify this interpretation is correct before starting. If full-F
   push-forward is needed, extend `truesdell_tangent` per the Gate B m2 note.

2. **Green-Naghdi activation:** `green_naghdi_tangent` currently raises for
   `R ≠ I`. P1-7's rigid-rotation test passes R = I (no deformation, pure
   rotation) so the restriction is not a blocker for Phase 1. **Action:**
   flag for the first phase that introduces large-rotation + rate-form
   constitutive update (probably B3 Perzyna or B4 HGO).

3. **Direct rate functions, fate of:** the three `*_rate` functions live
   outside the stated scope. If a future reviewer wants strict adherence,
   they can be removed (≈ 10 min) and the rigid-rotation test rewritten to
   hand-compute the rate formula inline. I think the current split is
   cleaner and future-proof, but noting this for the record.

---

**Ready to proceed to the next task?** The natural continuation is P1-3 (UL
residual emission), which is the direct blocker for both P1-4 and P1-6. It
will touch `taichi_printer.py` so running `npx gitnexus analyze --embeddings`
first would be valuable — impact analysis on the code generator is much
more useful with a fresh graph.
