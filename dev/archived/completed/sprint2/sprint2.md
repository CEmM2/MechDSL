# Sprint 2 Execution Plan — J2 Plasticity Runtime & Verification Hardening

> ⚠️ **Superseded** by [`recovery_plan_latex_contract.md`](recovery_plan_latex_contract.md) (Phase 7 / R6 archival, P7-5). The plasticity / verification runtime work landed in tree; only the implicit LaTeX-input contract carries forward, and that has been moved to the recovery plan. See [`STATUS_LEGEND.md`](../tracking/STATUS_LEGEND.md) and [`frontend_drift_history.md`](../reviews/frontend_drift_history.md).

## Context

Sprint 1 (PR #6, branch `sprint1_phase-6`) delivered the core compile-to-run pipeline: `compile(problem_ir) -> ArtifactBundle` produces a runnable Taichi solver. The elastic E2E test matches the handwritten reference to <1e-10. Three known gaps carry forward: (1) generated `newton_solve()` lacks BC enforcement — the E2E test uses an external `_newton_with_bc()` workaround, (2) `emit_main()` emits `lam_val=0, mu_val=0` when ProblemIR stores E/nu instead of pre-computed Lamé params (taichi_printer.py:810, `params.get('lam', 0.0)` returns 0.0), (3) FD tangent precision floor ~4e-9 from h=1e-7.

The J2 codegen path already emits a full radial return (`_emit_j2_constitutive()`, taichi_printer.py:281-379) with Newton iteration (20 iter, tol=1e-12), but uses FD tangent instead of algorithmic consistent tangent. The `alpha[e,q]` history field is declared and updated in-place, but there is no commit/rollback mechanism — a critical issue for load stepping that Sprint 2 must address in the E2E test via external alpha save/restore.

**Baseline:** 740 fast tests + 2 slow E2E tests green. Branch: `sprint2_phase-1`.

**Goal:** Generated J2 elasto-plastic solver compiles, runs under Taichi JIT, and matches `ref_hex8_plastic.py` to <1e-10. Verification infrastructure (`verify/analytical.py`, `verify/convergence.py`, `verify/patch_test.py`) implemented. Every test ID in `08-VERIFICATION.md §2` has a passing test.

---

## Phase 1: Convected Coordinates & Codegen Bug Fixes (Sprint 2 §3 + Sprint 1 gaps)

**Why:** Two Sprint 1 bugs (`emit_main` lam=0 for E/nu materials, missing BC enforcement in generated Newton driver) must be fixed before J2 E2E testing. The convected coordinate module is trivial for MVP (Cartesian) and unblocks test S9 and E6 in the audit.

### Tasks (6)

**P1-T1: Fix emit_main E/nu → Lamé conversion** (complexity 2, risk 3)
- **File:** `src/mechdsl/codegen/taichi_printer.py` (line 810)
- Bug: `params.get('lam', 0.0)` returns 0.0 when ProblemIR stores E/nu
- Fix: compute `lam = E*nu/((1+nu)*(1-2*nu))`, `mu = E/(2*(1+nu))` when `lam`/`mu` absent
- Test: emit with E/nu MaterialSpec, verify `lam_val` and `mu_val` in output match hand calculation

**P1-T2: Implement convected coordinate functions** (complexity 1, risk 1)
- **File:** `src/mechdsl/symbolic/convected.py` (stub → ~50 lines)
- `compute_reference_metric(coords="cartesian") -> Matrix`: returns δ_IJ (3x3 identity), raises `UnsupportedError` for non-Cartesian
- `compute_convected_metric(F: Matrix) -> Matrix`: returns g_IJ = F^T @ F = C_IJ
- `green_lagrange_convected(g, G) -> Matrix`: returns E = 0.5*(g - G)
- Note: `kinematics.py` already computes `g = C` — these functions formalize the convected interpretation

**P1-T3: Write convected coordinate tests** (complexity 1, risk 1)
- **New file:** `tests/test_convected.py`
- At F=I: g = G = I, E = 0 (matches kinematics.py output)
- At known simple shear: g = C (hand calculation)
- Non-Cartesian raises UnsupportedError with Plan B pointer
- Verifies test ID S9 from 08-VERIFICATION.md

**P1-T4: Update convected exports** (complexity 1, risk 1)
- **File:** `src/mechdsl/symbolic/__init__.py`
- Export `compute_reference_metric`, `compute_convected_metric`, `green_lagrange_convected`

**P1-T5: Regenerate golden files after emit_main fix** (complexity 1, risk 2)
- Run `generate_golden.py`, verify diff is limited to __main__ block (lam/mu values)
- Golden files: `tests/golden/generated_elastic.py.golden`, `tests/golden/generated_plastic.py.golden`

**P1-T6: Write emit_main Lamé conversion test** (complexity 2, risk 1)
- Add test to `tests/test_emission_phase5.py` or new file: emit with E=200e3, nu=0.3, verify emitted lam/mu values match analytical Lamé params

---

## Phase 2: Analytical Solutions & Frontend Stubs (Sprint 2 §2a + §4)

**Why:** The analytical solution library provides ground truth for the J2 E2E test (§1.5 needs uniaxial_tension_hardening) and the patch/rigid-body tests (Phase 3). The frontend `build_context()` is a small independent task that unblocks parser test IDs P1-P6.

### Tasks (8)

**P2-T1: Implement patch_test_reference()** (complexity 2, risk 2)
- **File:** `src/mechdsl/verify/analytical.py`
- Given a constant strain tensor and a Hex8 mesh, compute exact nodal displacement: `u_I = E_IJ * X_J`
- Input: mesh coords (n_nodes, 3), target Green-Lagrange strain E (3,3)
- Output: displacement field (n_nodes, 3)

**P2-T2: Implement rigid_body_reference()** (complexity 2, risk 1)
- **File:** `src/mechdsl/verify/analytical.py`
- Given rotation R (3,3) and translation t (3,), compute `u = R @ X + t - X`
- Verify: internal force should be zero for any rigid body motion (E=0)

**P2-T3: Implement cantilever_euler_bernoulli()** (complexity 1, risk 1)
- **File:** `src/mechdsl/verify/analytical.py`
- `cantilever_euler_bernoulli(L, I, E, P) -> tip_displacement`: δ = PL³/(3EI)
- Classic beam theory reference for coarse-mesh elastic validation

**P2-T4: Implement uniaxial_tension_hardening()** (complexity 3, risk 2)
- **File:** `src/mechdsl/verify/analytical.py`
- `uniaxial_tension_hardening(E, nu, sigma_y0, K, n, eps_total) -> (stress, eps_p)`
- For 1D uniaxial: elastic until σ = σ_y0, then σ = σ_y0 + K * ε_p^n (implicit solve for ε_p)
- **Critical for Phase 4**: J2 E2E test compares hardening response against this

**P2-T5: Write analytical solution tests** (complexity 2, risk 1)
- **New file:** `tests/test_analytical.py`
- patch_test: constant strain → exact displacement, verify with hand calculation
- rigid_body: R=I,t=0 → u=0; simple rotation → correct displacement
- cantilever: known L/I/E/P → known δ
- uniaxial: below yield → σ = E*ε; above yield → matches hardening law

**P2-T6: Implement frontend.build_context()** (complexity 2, risk 2)
- **File:** `src/mechdsl/frontend/__init__.py` (stub → ~80 lines)
- `build_context(dim, cell_type, formulation, material_type, params, boundaries) -> dict`
- Returns same context dict the LaTeX parser would produce
- Validates required fields, rejects unsupported values with `UnsupportedError`
- This is the *programmatic* entry point — does NOT construct ProblemIR directly (that's Layer 3's job)

**P2-T7: Implement build_context validation** (complexity 2, risk 1)
- Same file as P2-T6
- Reject unsupported: dim≠3, cell_type≠hex8, formulation≠total_lagrangian, material∉{svk, j2_power_law}
- Each error includes plan-phase pointer (per `ir.md` rules)

**P2-T8: Write frontend tests** (complexity 2, risk 1)
- **New file:** `tests/test_frontend_build_context.py`
- P1: valid MVP source → correct dict
- P2: unknown material → error with suggestion
- P5: missing dim → error listing required fields
- P6: convected coordinate handling (Cartesian default)

---

## Phase 3: Verification Infrastructure (Sprint 2 §2b + §2c)

**Why:** The convergence rate checker and patch test validator are needed for MVP exit criteria. The MMS driver is the highest-complexity verification task — it requires manufactured body force computation and mesh refinement.

### Tasks (5)

**P3-T1: Implement check_convergence_rate()** (complexity 2, risk 2)
- **File:** `src/mechdsl/verify/convergence.py` (stub → ~80 lines)
- `check_convergence_rate(errors, mesh_sizes, expected_rate, tol) -> ConvergenceResult`
- Fit log-log slope via numpy least squares
- Return: measured_rate, expected_rate, passed (rate ≥ expected - tol)

**P3-T2: Implement MMS driver** (complexity 4, risk 4) — **Opus 4.6 required**
- **File:** `src/mechdsl/verify/convergence.py` (add ~150 lines)
- Given manufactured `u*(x) = A sin(πx/L) cos(πy/L) sin(πz/L)`:
  - Compute F* = I + grad(u*), then E* = 0.5*(C* - I)
  - Compute S* = SVK(E*), then body force b* = -Div(F*·S*)
  - Solve on mesh sequence, measure L2 and H1 errors
- Reuse: `ref_hex8_elastic.py::generate_hex8_mesh()` for mesh generation at multiple levels
- This is the most complex single task — requires symbolic differentiation of the manufactured solution

**P3-T3: Write convergence rate test** (complexity 3, risk 3) — `@pytest.mark.slow`
- **New file:** `tests/test_convergence.py`
- Hex8 (p=1) on 3 mesh levels (2³, 4³, 8³ elements)
- Assert L2 rate ≥ 2.0, H1 rate ≥ 1.0 (within tolerance 0.1)
- Uses MMS driver from P3-T2

**P3-T4: Implement run_patch_test() and run_rigid_body_test()** (complexity 3, risk 3)
- **File:** `src/mechdsl/verify/patch_test.py` (stub → ~120 lines)
- `run_patch_test(solver_source, mesh, strain_field) -> PatchTestResult`
  - Run generated solver with constant-strain BC
  - Compare output against `analytical.patch_test_reference()`
  - Assert relative error < 1e-12
- `run_rigid_body_test(solver_source, mesh, rotation, translation) -> RigidBodyResult`
  - Apply rigid body motion BCs
  - Assert internal force norm < 1e-12
- **Depends on:** P2-T1, P2-T2 (analytical references)

**P3-T5: Write patch test** (complexity 3, risk 3) — `@pytest.mark.slow`
- **New file:** `tests/test_patch_test.py`
- Irregular Hex8 mesh (perturbed nodes) → SVK elastic patch test pass
- Rigid body rotation → zero internal force
- Uses generated solver from `compile()`

---

## Phase 4: J2 Plasticity E2E Integration (Sprint 2 §1)

**Why:** This is the sprint's primary deliverable — proving the generated J2 solver actually works. Highest risk phase.

### Tasks (7) — **All Opus 4.6**

**P4-T1: Audit J2 constitutive emission (§1.1)** (complexity 3, risk 3)
- **File:** `src/mechdsl/codegen/taichi_printer.py` (`_emit_j2_constitutive()`, lines 281-379)
- Verify emitted code matches the radial return algorithm:
  1. Elastic predictor: S_trial = lam*tr(E)*I + 2*mu*E
  2. Deviatoric split + von Mises σ_eq
  3. Yield check: f = σ_eq - σ_y(α_old)
  4. Scalar Newton for Δλ (20 iter, tol=1e-12)
  5. Stress update: S = S_vol + (1 - 3μΔλ/σ_eq)*S_dev
  6. α_new = α_old + Δλ
- Compare against `symbolic/models/j2_power_law.py::radial_return()` algorithm
- Fix any discrepancies; update golden file if emission changes

**P4-T2: Validate FD tangent for J2 (§1.2)** (complexity 3, risk 4)
- Verify that FD tangent (`emit_tangent_matvec_kernel()`, lines 507-607) converges Newton correctly for plastic problems
- Key concern: FD perturbation (h=1e-7) must NOT perturb history variables (α_old must stay fixed during tangent evaluation)
- Verify in emitted code: the tangent matvec calls `compute_internal_force` with perturbed u but same α state
- If FD tangent fails for J2: document limitation, adjust tolerances for E2E test

**P4-T3: Verify history field emission (§1.3)** (complexity 3, risk 3)
- Verify `emit_field_declarations()` declares `alpha` field
- Verify `emit_internal_force_kernel()` reads `alpha[e,q]` and writes `alpha_new` back
- **Critical gap:** no commit/rollback mechanism in emitted code — α is overwritten each Newton iteration
- **Mitigation for E2E test:** external α save/restore via `alpha.to_numpy()`/`alpha.from_numpy()` between Newton iterations (same pattern as elastic `_newton_with_bc()`)
- Document as Sprint 3 TODO: emit dual-buffer `alpha` + `alpha_converged` with copy kernel

**P4-T4: Verify numerical safeguards (§1.4)** (complexity 2, risk 2)
- Check emitted J2 code for:
  - J > 1e-15 guard (deformation gradient Jacobian)
  - σ_eq > tol guard before computing flow direction n = S_dev/σ_eq
  - Δλ ≥ 0 guard
  - Hardening derivative guard: α^(n-1) with 1e-30 floor
- Cross-reference with `07-CONVENTIONS.md §6` safeguard requirements

**P4-T5: Create test_e2e_plastic.py (§1.5)** (complexity 4, risk 5) — **Highest risk task**
- **New file:** `tests/test_e2e_plastic.py` (`@pytest.mark.slow @pytest.mark.e2e`)
- Pattern: follow `test_e2e_taichi.py` elastic test structure with these additions:
  1. Construct J2 ProblemIR (sigma_y0=200, K=100, n=0.3, E=200e3, nu=0.3)
  2. `compile(problem_ir)` → get emitted source
  3. Import generated module, call `ti.init()`, `allocate_fields()`
  4. External Newton loop with BC enforcement (`_newton_with_bc_plastic()`)
  5. **History management:** save α before each Newton iter, restore on non-convergence
  6. Load stepping: apply incremental displacement past yield in N steps
  7. Assertions:
     (a) Below yield: stress matches elastic (within FD tolerance)
     (b) Above yield: stress follows σ = σ_y + K·ε_p^n
     (c) Return mapping: f(σ^{n+1}) = 0 to machine precision
- **Key risk:** alpha save/restore during Newton iterations must be correct

**P4-T6: Compare generated vs reference (§1.6)** (complexity 3, risk 4)
- Run `ref_hex8_plastic.py::solve_plastic()` on same 1-element problem
- Run generated J2 solver on same problem (via test_e2e_plastic.py infrastructure)
- Assert: displacement field max difference < 1e-10
- If FD tangent prevents meeting 1e-10: document and use relaxed tolerance with justification

**P4-T7: Validate/update golden file (§1.7)** (complexity 1, risk 2)
- Compare current `tests/golden/generated_plastic.py.golden` against freshly generated J2 Taichi code
- If Phase 4 required emission changes → regenerate golden file
- Verify diff is limited to intended changes (regression guard)

---

## Phase 5: Test Completeness Audit (Sprint 2 §5)

**Why:** The sprint exit criteria require every test ID in `08-VERIFICATION.md §2` to have a passing test. This phase audits coverage and fills gaps.

### Tasks (4)

**P5-T1: Audit symbolic (S1-S9) + parser (P1-P6)** (complexity 2, risk 1)
- S1-S8: already covered (124 tests across 7 files) — verify each ID maps to a passing test
- S9: convected metric — verify `test_convected.py` from Phase 1 covers this
- P1-P6: `test_frontend_build_context.py` from Phase 2 covers P1, P2, P5, P6
- Gaps: P3 (two-point tensor F_{iI}) and P4 (index manifold clash) — these require the parser which is a stub
- **Decision needed:** mark P3/P4 as "deferred: parser not yet implemented" or implement minimal test stubs

**P5-T2: Audit IR (M1-M6), Element (E1-E6), Einsum (N1-N5)** (complexity 2, risk 1)
- M1-M6: 48 tests across 4 files — verify coverage of each ID
- E1-E6: 87 tests across 5 files — E6 (convected) verified by Phase 1 tests
- N1-N5: 55 tests across 3 files
- Fill any gaps with targeted tests

**P5-T3: Audit Backend (T1-T4), BC (B1-B5), Artifact (A1-A3), Emission (C1-C3)** (complexity 2, risk 1)
- T1-T4: 192+ tests — strong
- B1-B5: 27 tests — verify each ID
- A1-A3: 35 tests — verify each ID
- C1-C3: 68+ tests — C3 (generated vs handwritten) is the Sprint 1 deliverable, now extended by J2 in Phase 4

**P5-T4: Create verification matrix** (complexity 1, risk 1)
- **New file:** `dev/tracking/verification_matrix.md`
- Table: test ID → test file → test function → status (pass/fail/deferred)
- 37 test IDs across 9 categories
- Links to test files for each ID

---

## Phase 6: Sprint Integration & Exit Criteria

**Why:** Final verification pass, full regression, and sprint handoff.

### Tasks (3)

**P6-T1: Full regression suite** (complexity 1, risk 1)
- Run `uv run pytest packages/mechdsl-core/tests/ -m "not slow and not gpu" -x -q`
- Run `uv run pytest packages/mechdsl-core/tests/ -m slow -x -q`
- Verify all pre-existing + new tests pass

**P6-T2: Verify sprint exit criteria** (complexity 2, risk 1)
- Check each exit criterion from `dev/plans/MVP_sprint2.md`:
  - [ ] Generated J2 solver compiles and runs under Taichi JIT
  - [ ] Uniaxial tension past yield reproduces correct hardening curve
  - [ ] Generated plastic solver matches ref_hex8_plastic.py (< 1e-10)
  - [ ] verify/analytical.py provides 4 reference solutions
  - [ ] verify/convergence.py checks convergence rates
  - [ ] verify/patch_test.py runs patch + rigid body tests
  - [ ] symbolic/convected.py computes metrics
  - [ ] frontend.build_context() provides programmatic spec
  - [ ] Every test ID in 08-VERIFICATION.md §2 has a passing test
  - [ ] All pre-existing tests still pass

**P6-T3: Sprint 2 completion handoff** (complexity 1, risk 1)
- Generate `dev/tasks/MVP_sprint2/Sprint2_Completion_Handoff.md` using template

---

## Dependency Graph & Execution Order

```
Phase 1 (convected + emit_main fix)  ──┐
                                        ├──→ Phase 4 (J2 E2E)  ──→ Phase 5 (audit)  ──→ Phase 6 (integration)
Phase 2 (analytical + frontend)  ───────┤
                                        │
Phase 3 (convergence + patch test)  ────┘
         ↑ depends on P2-T1, P2-T2
```

- **Phases 1, 2** can execute in parallel (no mutual dependencies)
- **Phase 3** depends on Phase 2 (patch_test needs analytical.patch_test_reference from P2-T1)
- **Phase 4** depends on Phase 1 (emit_main fix) and Phase 2 (uniaxial_tension_hardening from P2-T4)
- **Phase 5** depends on Phases 1-4 (needs all tests in place to audit)
- **Phase 6** depends on all above (final integration)

**Critical path:** Phase 2 → Phase 4 → Phase 5 → Phase 6

---

## Files Modified/Created Summary

| File | Action | Phase |
|------|--------|-------|
| `src/mechdsl/codegen/taichi_printer.py` | Fix emit_main E/nu→Lamé conversion (line 810) | 1 |
| `src/mechdsl/symbolic/convected.py` | Stub → 3 convected coordinate functions | 1 |
| `src/mechdsl/symbolic/__init__.py` | Add convected exports | 1 |
| `src/mechdsl/verify/analytical.py` | Stub → 4 analytical solution functions | 2 |
| `src/mechdsl/frontend/__init__.py` | Stub → build_context() with validation | 2 |
| `src/mechdsl/verify/convergence.py` | Stub → check_convergence_rate() + MMS driver | 3 |
| `src/mechdsl/verify/patch_test.py` | Stub → run_patch_test() + run_rigid_body_test() | 3 |
| `tests/golden/generated_elastic.py.golden` | Regenerate (emit_main fix) | 1 |
| `tests/golden/generated_plastic.py.golden` | Regenerate (emit_main fix + any J2 fixes) | 1, 4 |
| `tests/test_convected.py` | **New** — convected coordinate tests | 1 |
| `tests/test_analytical.py` | **New** — analytical solution tests | 2 |
| `tests/test_frontend_build_context.py` | **New** — frontend build_context tests | 2 |
| `tests/test_convergence.py` | **New** — MMS convergence rate tests (slow) | 3 |
| `tests/test_patch_test.py` | **New** — patch test + rigid body tests (slow) | 3 |
| `tests/test_e2e_plastic.py` | **New** — J2 E2E Taichi execution tests (slow, e2e) | 4 |
| `dev/tracking/verification_matrix.md` | **New** — test ID coverage map | 5 |

All paths relative to `packages/mechdsl-core/` unless prefixed with `dev/`.

---

## Key Implementation Notes

### History Variable Management in J2 E2E Test (Phase 4)

The generated J2 code overwrites `alpha[e,q]` in-place during each `compute_internal_force()` call. For Newton iteration, α must remain at the beginning-of-step value across iterations, and only "commit" on convergence. The E2E test must implement:

```python
def _newton_with_bc_plastic(mod, coords, bc_mask, f_ext, lam, mu, sigma_y0, K, n, tol=1e-8):
    # Save alpha state before Newton loop
    alpha_snapshot = mod.alpha.to_numpy().copy()
    for it in range(max_iter):
        # Restore alpha to beginning-of-step before each residual eval
        mod.alpha.from_numpy(alpha_snapshot)
        mod.compute_internal_force(lam, mu, sigma_y0, K, n)
        # ... BC enforcement, convergence check, CG solve ...
    # On convergence: alpha is correct (last eval); DON'T restore
    # On failure: restore alpha_snapshot
```

### FD Tangent Concerns for Plastic Problems

The FD tangent perturbation (h=1e-7 in `emit_tangent_matvec_kernel`) calls `compute_internal_force` with perturbed `u`. Since `compute_internal_force` also updates `alpha[e,q]`, the perturbed call will corrupt the alpha field. The E2E test must save/restore alpha around tangent evaluations too. If this proves unworkable, the test may need to accept a looser tolerance or fewer load steps.

### MMS Body Force Computation (Phase 3)

For manufactured u*(x), the body force is b* = -Div(P*) where P* = F*·S* (first Piola-Kirchhoff stress). For SVK: S* = λ tr(E*)I + 2μE* where E* = 0.5*(F*^T F* - I). The divergence Div(P*) requires symbolic differentiation of P* w.r.t. X — use SymPy for this. The mesh refinement sequence uses `generate_hex8_mesh(nx, ny, nz, Lx, Ly, Lz)` from `tests/ref/ref_hex8_elastic.py`.

---

## Complexity/Risk Summary

| Task | Complexity | Risk | Combined | Model |
|------|-----------|------|----------|-------|
| P1-T1 (emit_main fix) | 2 | 3 | 5 | Sonnet |
| P1-T2 (convected impl) | 1 | 1 | 2 | Sonnet |
| P1-T3 (convected tests) | 1 | 1 | 2 | Sonnet |
| P2-T4 (uniaxial hardening) | 3 | 2 | 5 | Sonnet |
| P2-T6 (build_context) | 2 | 2 | 4 | Sonnet |
| P3-T2 (MMS driver) | 4 | 4 | **8** | **Opus** |
| P3-T3 (convergence test) | 3 | 3 | 6 | Sonnet/Opus |
| P3-T4 (patch test impl) | 3 | 3 | 6 | Sonnet/Opus |
| P3-T5 (patch test) | 3 | 3 | 6 | Sonnet/Opus |
| P4-T1 (J2 audit) | 3 | 3 | 6 | Sonnet/Opus |
| P4-T2 (FD tangent) | 3 | 4 | **7** | **Opus** |
| P4-T3 (history emit) | 3 | 3 | 6 | Sonnet/Opus |
| P4-T5 (E2E plastic) | 4 | 5 | **9** | **Opus** |
| P4-T6 (gen vs ref) | 3 | 4 | **7** | **Opus** |

---

## Verification

After each phase, run:
```bash
uv run pytest packages/mechdsl-core/tests/ -m "not slow and not gpu" -x -q
```

After all phases, run the full suite including slow:
```bash
uv run pytest packages/mechdsl-core/tests/ -x -q
```

**Exit criteria from sprint plan:**
- [ ] Generated J2 elasto-plastic solver compiles and runs under Taichi JIT
- [ ] 1-element uniaxial tension past yield reproduces correct hardening curve
- [ ] Generated plastic solver matches `ref_hex8_plastic.py` (displacement error < 1e-10)
- [ ] `verify/analytical.py` provides patch-test, rigid-body, cantilever, and uniaxial references
- [ ] `verify/convergence.py` checks mesh-refinement convergence rates
- [ ] `verify/patch_test.py` runs patch test and rigid-body test on generated solvers
- [ ] `symbolic/convected.py` computes reference and current metrics
- [ ] `frontend.build_context()` provides programmatic problem specification with validation
- [ ] Every test ID in `08-VERIFICATION.md §2` (P1–P6, S1–S9, M1–M6, E1–E6, N1–N5, T1–T4, B1–B5, A1–A3, C1–C3) has a corresponding passing test
- [ ] All pre-existing + Sprint 1 tests still pass
