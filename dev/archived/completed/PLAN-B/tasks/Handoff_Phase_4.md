# Handoff: Phase 3 → Phase 4

## Phase 3 Summary

**Phase:** Viscoplasticity (Perzyna + Johnson-Cook)
**Branch:** `plan-b_phase-3`
**Status:** Complete — all 4 tasks done, exit criterion B3 (rate/quasi-static/thermal verification) met
**Final suite:** 1115 passed, 1 skipped, 0 failed (mechdsl-core fast sweep, markers `not slow and not gpu`)

### What was built

The symbolic layer now supports two rate-dependent constitutive models, both with backward-Euler return maps and consistent algorithmic tangents:

| Component | Function | Location |
|-----------|----------|----------|
| Perzyna overstress | `R(dl) = σ_eq_trial − 3μ·dl − σ_y(α+dl) − η·(dl/dt)^(1/m)` | `symbolic/models/perzyna.py` |
| Perzyna return map | Scalar-Newton on `dl`, convergence to `tol=1e-10` | `perzyna.py::radial_return` |
| Perzyna tangent | `denominator = 3μ + H'(α_new) + η_term`, via shared helper | `perzyna.py` |
| JC flow stress | `σ_y = (A + B·α^n)·(1 + C·ln ε̇*)·(1 − T*^m)` | `symbolic/models/johnson_cook.py` |
| JC rate clamp | `ε̇* = max(dl/(dt·ε̇_0), 1)` | `johnson_cook.py` |
| JC 2×2 Newton | Coupled residual on `(dl, dT)` with Taylor-Quinney heating | `johnson_cook.py::radial_return` |
| JC tangent | Schur-complement of converged `J_conv`: `denominator = −det(J_conv)/J_conv[1,1]` | `johnson_cook.py` |
| Shared tangent assembler | `assemble_j2_like_tangent(lam, mu, S_dev_trial, σ_eq_trial, dl, denominator)` | `j2_power_law.py` |
| Acceptance suite | Rate sensitivity (Perzyna + JC), quasi-static limit (both), thermal softening (JC) | `tests/test_viscoplastic_acceptance.py` |

### Key decisions and fixes

1. **Dissipative tangent derivation.** Perzyna and JC tangents come from implicit differentiation of the Newton residual at convergence (Simo & Hughes 1998 Box 3.5), NOT from `sympy.diff` of the free energy. This is the distinguishing pattern for dissipative models — the tangent depends on `dl`, which is itself a function of the strain increment through the return map.

2. **Shared helper factored at module scope.** `assemble_j2_like_tangent` in `j2_power_law.py` takes `denominator` as a parameter, so J2 / Perzyna / JC all route through the same tensor assembly. J2's own `radial_return` was refactored onto the helper byte-identically (existing `test_tangent_fd_plastic` unchanged).

3. **JC Schur-complement reduction.** The 2×2 Newton Jacobian at convergence is captured and reduced to a scalar `denominator`. At `β=0, C=0, T=T_ref`, the tangent reduces byte-for-byte to J2 (unit-tested).

4. **Acceptance tests use `von_mises(deviatoric(stress))`.** The full Cauchy stress includes a volumetric elastic term that dominates the total `von_mises` norm; the plastic signal only lives in the deviatoric part. Forgetting `deviatoric` gave a 0.37% thermal-softening drop instead of >10%.

5. **JC rate-sensitivity test uses `dt ∈ [1e-3, 1e-7]`.** The `max(dl/(dt·ε̇_0), 1)` clamp floors the rate factor at 1 for any `dl/dt ≤ ε̇_0`, so `dt ≥ 1e-2` with `ε̇_0 = 1` gives identical stress at all rates. Keep `dl/dt ≫ ε̇_0` to exercise the rate term.

6. **FD tangent harness.** Central difference requires dividing by `2·eps`, not `eps` — an earlier draft gave exactly 2× the true derivative (50% relative error). The canonical pattern is J2's `_fd_tangent`: perturb with `dE_sym = 0.5·(dE + dE.T)`, divide by `2·eps` at `eps=1e-7`.

### What Phase 4 needs to know

Phase B4 is **advanced hyperelasticity** (Neo-Hookean, Mooney-Rivlin, Ogden, HGO):

- **Different tangent pattern.** Hyperelastic models are non-dissipative — the tangent IS `∂²Ψ/∂E∂E` and should be derived via `sympy.diff` of the free energy (per `.claude/rules/symbolic.md`). Do NOT copy the Perzyna/JC Simo-Hughes pattern.
- **No return map.** No internal state, no Newton iteration at the constitutive level. The 2PK stress is a direct function of the strain invariants.
- **Ogden requires eigendecomposition.** 3×3 symmetric eigendecomposition over `C` — Taichi codegen will need `ti.sym_eig` or a hand-rolled Jacobi iteration (verify in plan before scope).
- **HGO needs per-element fiber directions.** This is a new data-flow pattern — fiber direction is per-element, not per-material. Check the Element IR schema can carry it before P4 starts.

Phase B4 does NOT depend on Phase 3. The viscoplasticity modules sit alongside J2 in `symbolic/models/` and do not interact with hyperelasticity.

### Test baseline (mechdsl-core)

- **1115 passed, 1 skipped, 0 failed** (markers `not slow and not gpu`)
- Viscoplastic acceptance suite: 5/5 pass
- Perzyna: 4/4 FD + symmetry tests pass
- Johnson-Cook: 3/3 FD + symmetry tests pass
- Pre-existing `test_phase6_exit.py::TestTaskP6T5` "stub sentinel" failure resolved automatically by P3-4 (last "stub — implement after Task P3-X" marker removed).

### Gate history

All 4 tasks passed Gate A (spec compliance), Gate B (domain quality), Gate C (verification). See `dev/tasks/PLAN-B/gates/phase_3_gates.md` for per-task entries.

| Task | Commit | Notes |
|------|--------|-------|
| P3-1 Perzyna | 9e0baa6 | Backward Euler return map; tangent stub → filled in P3-3 |
| P3-2 Johnson-Cook | 5e9efc4 | 2×2 Newton (`dl, dT`) with Taylor-Quinney heating |
| P3-3 Consistent tangent | 8101a14 | Shared `assemble_j2_like_tangent` helper; FD + symmetry verified |
| P3-4 Acceptance suite | e659d5d | Rate / quasi-static / thermal monotonicity |
