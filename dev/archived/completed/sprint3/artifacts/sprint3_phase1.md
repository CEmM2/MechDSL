# Sprint 3 Phase 1 Review

**Branch:** `sprint3_phase-1`
**Date:** 2026-04-08
**Scope:** 3 files changed, +196 lines, 0 deletions

---

## Codex Review

**Session ID:** `019d6d41-a17c-7a03-a54a-e99a263de203`

The added benchmarks introduce one invalid quantitative load setup and two very expensive CPU-only solves into the slow test path. As written, they risk false signal from the cantilever benchmark and substantially degrade the practicality of the slow suite.

### [P2] Apply a consistent end load in the 5% cantilever benchmark

**File:** `packages/mechdsl-core/tests/test_benchmarks.py:587-590`

On the refined 40x8x4 end face, corner, edge, and interior nodes do not represent equal surface areas, so `total_force / len(right_nodes)` is not a consistent discretization of a uniform end traction. That matters here because this test immediately compares the loaded-face displacement to Euler-Bernoulli within 5%; the measured deflection becomes mesh-topology dependent instead of reflecting solver accuracy. Using area-weighted nodal loads (or a proper surface integral) would keep the benchmark aligned with the continuum problem.

### [P2] Keep the 40x8x4 cantilever solve out of the slow test job

**File:** `packages/mechdsl-core/tests/test_benchmarks.py:568-570`

This adds a 40x8x4 reference cantilever solve to the `slow` suite, but `tests.ref.ref_hex8_elastic.solve_elastic()` is a pure-NumPy matrix-free Newton/CG driver whose tangent matvec finite-differences two full internal-force assemblies. Relative to the existing 4x2x1 cantilever case, that is 1280 vs 8 elements per matvec (about 160x more assembly work) before accounting for higher CG iteration counts, so PRs that trigger the slow CI job are likely to spend most of their time here or time out.

### [P2] Keep the 16^3 MMS convergence study out of the slow test job

**File:** `packages/mechdsl-core/tests/test_convergence.py:463`

This fixture makes `run_mms_convergence()` solve on `[2, 4, 8, 16]`. Because each level goes through the same matrix-free Python assembly and unpreconditioned CG path, the total element work jumps from `2^3+3^3+4^3 = 99` in the existing 3-level fixture to `2^3+4^3+8^3+16^3 = 4680` here, and the 16^3 system also needs more CG iterations. Any PR that touches `solver/` or `codegen/` will therefore make the slow CI job much heavier and may push it into timeout territory.

### Assessment

1. **Nodal load consistency (P2)** -- Legitimate physics concern. The existing coarse cantilever fixture uses the same `total_force / len(right_nodes)` pattern, which works for a coarse mesh where all face nodes are roughly equivalent. On a 40x8x4 mesh, corner/edge/interior nodes carry different tributary areas. Worth fixing before first real run.

2. **Slow job timeout (P2 x2)** -- By design. Both tests are marked `@pytest.mark.e2e` specifically to exclude them from the PR-triggered `slow` job. Phase 4 (P4-T2) will configure CI to run `slow` and `e2e` as separate tiers: `-m "slow and not e2e"` for PRs, `-m e2e` for nightly only. The Codex reviewer didn't see the Phase 4 plan context.

---

## Code Review (from diff-review)

### Good

- **Purely additive, zero-regression design.** All 196 lines are insertions. Existing tests are untouched. Old coarse-mesh cantilever tests remain as fast regression gates. Textbook benchmark hardening -- tighten tolerances without breaking the safety net.

- **Class-scoped fixture for MMS avoids redundant FEM solves.** `mms_convergence_results_4level` uses `scope="class"` so the expensive 4-level convergence study (including a 16^3 mesh) runs exactly once, shared by both L2 and H1 tests. Matches the existing `TestTaskP3T3` pattern.

- **Physics documentation in docstrings.** The 30-degree rotation test at `test_benchmarks.py:326` clearly explains the derivation chain: F=R -> C=R^T R=I -> E=0 -> S=0 -> f_int=0. The tolerance relaxation rationale is documented inline, not hidden in a comment.

### Bad

- **No CHANGELOG entry for Sprint 3 Phase 1.** 196 lines of benchmark hardening with no CHANGELOG record. While test-only, the benchmark status is a user-facing quality signal. The plan defers CHANGELOG to Phase 5 (P5-4), so this is by design.

### Ugly

- **Tolerance divergence between reference solver and verify harness.** `test_finite_rotation_30_degrees` uses `<1e-9` while the equivalent test in `test_patch_test.py` uses `<1e-12`. The 3-order gap is documented but may confuse future developers. The root cause (different integration paths in `ref_hex8_elastic.py` vs `verify/patch_test.py`) deserves a shared comment or constant.

- **Cantilever fixture defined as instance method inside test class.** `cantilever_problem_refined` at line 553 is a `self` fixture inside `TestCantilever`, while the MMS fixture is module-level with `scope="class"`. The inconsistency is inherited from the existing `cantilever_problem` fixture. Not a bug, but a pattern that will accumulate if Cook's and necking bar follow the same style.

### Questions

- **Has the 40x8x4 cantilever been run to completion?** The test is marked `@slow` and was NOT executed during this phase (only collection was verified). With 12,285 nodes and `cg_max_iter=5000` in pure NumPy, the first actual run in CI may reveal convergence issues or timeout. Consider a one-time local validation run before merging.

- **Will the 16^3 MMS mesh complete within nightly budget?** 4,913 nodes x 4 mesh levels. The plan allows fallback to `[2, 4, 8]` if too slow. The test exists but hasn't been timed. Phase 4 CI nightly has a 60-minute budget.

---

## Decision Log (from diff-review)

### Keep coarse-mesh cantilever tests alongside refined mesh
**Confidence:** HIGH (sourced from plan + conversation)
**Rationale:** The 4x2x1 tests run in milliseconds and catch regressions immediately. The 40x8x4 test takes minutes and runs nightly. Both are needed: fast feedback loop + production accuracy.
**Alternatives:** Replace coarse tests entirely (rejected: loses fast feedback). Parameterize over mesh sizes (rejected: different tolerances make parameterization awkward).

### Use [2,4,8,16] mesh levels instead of [2,3,4]
**Confidence:** HIGH (sourced from plan)
**Rationale:** Proper 2x refinement ratios produce unbiased log-log slope estimates for convergence rate measurement. Non-uniform ratios ([2,3,4] = 1.5x then 1.33x) bias the fit and can mask superconvergence or degradation.
**Alternatives:** Keep [2,3,4] (rejected: biased rates). Use [4,8,16,32] for finer meshes (rejected: 32^3 = 35K nodes is prohibitive in pure NumPy).

### Relax 30-degree rotation tolerance from 1e-12 to 1e-9
**Confidence:** MEDIUM (inferred from code)
**Rationale:** The reference solver (`ref_hex8_elastic.py`) accumulates O(1e-10) floating-point roundoff during multi-element Gauss quadrature assembly with steel-like material parameters (MU~77,000). The verify harness achieves 1e-12 via a different integration path. Tolerance of 1e-9 provides 2 orders of headroom.
**Alternatives:** Use unit material parameters (rejected: breaks consistency with TestRigidBodyMotion class which uses steel parameters throughout). Switch to verify harness API (rejected: task spec requires reference solver API).

### Add @e2e marker at class level on TestTaskP3T5
**Confidence:** HIGH (sourced from plan)
**Rationale:** Phase 4 introduces a nightly CI tier collecting `-m e2e`. Patch test and rigid body tests on irregular mesh must be in that tier. Class-level marker is inherited by all methods, matching the existing `@slow` pattern.
**Alternatives:** Method-level markers (rejected: redundant, class already has @slow per-method). No marker, let Phase 4 add it (rejected: Phase 4 expects it done).

---

## Re-entry Context (from diff-review)

### Key Invariants
- The 40x8x4 cantilever test assumes `solve_elastic` accepts `cg_max_iter` as a keyword argument. If the solver API changes, this test breaks silently (it would just use the default).
- `TestMMS4LevelConvergence` fixture is `scope="class"` -- moving a test method to a different class will re-trigger the expensive solve.
- The 30-degree rotation test tolerance (1e-9) is coupled to the **reference solver implementation**, not the physics. If ref_hex8_elastic.py is improved, the tolerance can be tightened.

### Non-obvious Coupling
- `test_benchmarks.py` has two independent test scopes on cantilever: the original `cantilever_problem` fixture (4x2x1) and the new `cantilever_problem_refined` (40x8x4). They use the same material constants but different meshes. Changing `E_YOUNG` or `NU` at module level affects both.
- Phase 4's CI nightly tier (`-m e2e`) now collects tests from 3 files. Adding `@e2e` to more tests increases nightly runtime -- budget is 60 minutes.

### Gotchas
- The `@e2e @slow` tests have NOT been run to completion -- only collection was verified. First real execution will be Phase 4's nightly CI or a manual `-m slow` run.
- Pre-existing failure: `test_analytical.py::test_uniaxial_above_yield_hardening_law` fails due to missing `scipy` dependency. Excluded from fast suite but will appear in full `pytest` runs.

### Don't Forget
- These changes are **uncommitted** on branch `sprint3_phase-1`. Commit before starting Phase 2.
- CHANGELOG update is deferred to Phase 5 (P5-4).
- Phase 2 (Cook's membrane) needs `generate_cook_membrane_mesh()` in `mesh_io.py` -- that's the first blocker.
