# MVP Sprint 2 — J2 Plasticity Runtime & Verification Hardening

> ⚠️ **Superseded for the frontend contract** by [`recovery_plan_latex_contract.md`](recovery_plan_latex_contract.md) (Phase 2 / R1). The plasticity / verification work here remains in tree; only the implicit LaTeX-input contract has been moved to the recovery plan. See [`STATUS_LEGEND.md`](../tracking/STATUS_LEGEND.md) and [`frontend_drift_history.md`](../reviews/frontend_drift_history.md).

**Goal:** Extend the working elastic solver from Sprint 1 to handle J2 elasto-plasticity end-to-end, and build the verification infrastructure needed to trust the results.

**Duration:** ~2 weeks

**Preconditions:** Sprint 1 complete — Newton driver works, E2E elastic smoke test passes, `compile()` produces runnable Taichi code.

---

## 1. J2 Plasticity End-to-End Integration

The symbolic J2 model (`models/j2_power_law.py`, ~350 lines) and history field management (`solver/history_fields.py`) are already implemented. What's missing is the *code generation path* that emits a working J2 solver and the *runtime verification* that it produces correct results.

| # | Action item | Ref |
|---|-------------|-----|
| 1.1 | Verify `TaichiPrinter.emit_constitutive_kernel()` correctly emits the J2 radial return mapping as a `@ti.func`: elastic predictor → yield check → scalar Newton for Δλ → stress update → PEEQ update. | `06-CODEGEN.md §4.1`, `PLAN-A §A9.1` |
| 1.2 | Verify emission of the algorithmic consistent tangent `C_alg` in 6×6 Voigt: elastic branch returns elastic tangent, plastic branch returns consistent elasto-plastic tangent. Currently the printer uses FD tangent (known TODO) — either implement analytical tangent emission or validate that FD tangent converges Newton correctly. | `06-CODEGEN.md §4.2`, `PLAN-A §A9.2` |
| 1.3 | Verify emission of history variable fields (`peeq`, `stress_old`, `peeq_old`) and the copy kernel (`current → old`) at converged steps. Ensure `emit_data_structures()` declares them and `emit_newton_driver()` calls the copy kernel. | `06-CODEGEN.md §3.2`, `PLAN-A §A9.3` |
| 1.4 | Verify constitutive kernel numerical safeguards are emitted: J > 1e-15, σ_eq > tol before computing flow direction, Δλ ≥ 0. | `06-CODEGEN.md §4.3`, `07-CONVENTIONS.md §6` |
| 1.5 | Create `tests/test_e2e_plastic.py` (`@pytest.mark.slow`): construct J2 ProblemIR → compile → run on 1-element Hex8 → apply uniaxial tension past yield → verify (a) below yield matches elastic exactly, (b) stress follows σ = σ_y + K·ε_p^n, (c) return mapping satisfies f(σ^{n+1}) = 0 to machine precision. | `PLAN-A §A9.5`, `08-VERIFICATION.md §4.1` |
| 1.6 | Compare generated J2 solver against `tests/ref/ref_hex8_plastic.py` on the same 1-element problem: displacement field max difference < 1e-10. | `08-VERIFICATION.md §3.3`, `PLAN-A §A10.2` |
| 1.7 | Validate golden file `tests/golden/generated_plastic.py.golden` against newly generated J2 Taichi code. Update golden file if emission has legitimately changed. | `08-VERIFICATION.md §2.8 (A2)` |

---

## 2. Verification Infrastructure (`verify/`)

The AD oracle is done. Three stubs remain that are needed for MVP acceptance.

### 2a. Analytical Solution Library (`verify/analytical.py`)

| # | Action item | Ref |
|---|-------------|-----|
| 2.1 | Implement `patch_test_reference(mesh, strain_field) -> displacement_field`: given a constant strain tensor and an irregular Hex8 mesh, compute the exact nodal displacement field. | `08-VERIFICATION.md §4.1 (patch test)` |
| 2.2 | Implement `rigid_body_reference(mesh, rotation, translation) -> displacement_field`: apply a rigid body motion and return the expected zero-internal-force state. | `08-VERIFICATION.md §4.1 (rigid body)` |
| 2.3 | Implement `cantilever_euler_bernoulli(L, I, E, P) -> tip_displacement`: Euler-Bernoulli tip deflection for validating coarse-mesh elastic cantilever. | `08-VERIFICATION.md §4.1 (cantilever)` |
| 2.4 | Implement `uniaxial_tension_hardening(E, nu, sigma_y0, K, n, eps_total) -> (stress, eps_p)`: analytical uniaxial stress–strain curve for power-law J2 hardening. | `PLAN-A §A9.5` |
| 2.5 | Write tests for each analytical solution: known inputs → known outputs, compare against hand calculations. | `08-VERIFICATION.md §2.2` |

### 2b. Convergence Rate Checker (`verify/convergence.py`)

| # | Action item | Ref |
|---|-------------|-----|
| 2.6 | Implement `check_convergence_rate(errors: list[float], mesh_sizes: list[float], expected_rate: float, tol: float) -> ConvergenceResult`: fit log-log slope of error vs h, assert rate ≥ expected − tol. | `08-VERIFICATION.md §4.2` |
| 2.7 | Implement MMS (Method of Manufactured Solutions) driver: given a manufactured displacement field u*(x), compute the corresponding body force, solve on a sequence of meshes, measure L2 and H1 errors. | `08-VERIFICATION.md §4.2` |
| 2.8 | Write test: Hex8 (p=1) on 3 mesh levels, assert L2 rate ≥ 2.0, H1 rate ≥ 1.0 (within tolerance 0.1). Mark `@pytest.mark.slow`. | `08-VERIFICATION.md §4.2` |

### 2c. Patch Test Validator (`verify/patch_test.py`)

| # | Action item | Ref |
|---|-------------|-----|
| 2.9 | Implement `run_patch_test(solver_source: str, mesh, strain_field) -> PatchTestResult`: run the generated solver with a constant-strain BC, compare output against `analytical.patch_test_reference()`, assert relative error < 1e-12. | `08-VERIFICATION.md §4.1 (patch test)`, `PLAN-A §A10.3` |
| 2.10 | Implement `run_rigid_body_test(solver_source: str, mesh, rotation, translation) -> RigidBodyResult`: apply rigid body motion, assert internal force norm < 1e-12. | `08-VERIFICATION.md §4.1 (rigid body)` |
| 2.11 | Write test: irregular Hex8 mesh → patch test pass for SVK elastic. Mark `@pytest.mark.slow`. | `PLAN-A §A2.2` |

---

## 3. Convected Coordinate Module (`symbolic/convected.py`)

Architecturally present but numerically trivial for MVP (Cartesian reference → G_IJ = δ_IJ). Still needs explicit implementation so the infrastructure is in place.

| # | Action item | Ref |
|---|-------------|-----|
| 3.1 | Implement `compute_reference_metric(coords: str) -> Matrix`: returns δ_IJ for Cartesian, raises `UnsupportedError("Curvilinear reference planned for Plan B phase B2")` otherwise. | `06-CODEGEN.md §8.1–8.2` |
| 3.2 | Implement `compute_convected_metric(F: Matrix) -> Matrix`: returns g_IJ = F^T F = C_IJ. | `06-CODEGEN.md §8.2` |
| 3.3 | Implement `green_lagrange_convected(g: Matrix, G: Matrix) -> Matrix`: returns E_IJ = 0.5 * (g_IJ − G_IJ). | `06-CODEGEN.md §8.2` |
| 3.4 | Write test: at F = I, assert g = G = I, E = 0. At known simple shear F, assert g = C (hand calc). Verify S9 from `08-VERIFICATION.md`. | `08-VERIFICATION.md §2.2 (S9)` |

---

## 4. Frontend Stubs with Validation (`frontend/`)

The full NRPyLaTeX fork is out of scope for MVP (the pipeline entry point is "construct ProblemIR in Python"). However, the frontend stubs should be upgraded to provide a *programmatic* constructor that validates the same contract as the LaTeX parser would.

| # | Action item | Ref |
|---|-------------|-----|
| 4.1 | Implement `frontend.build_context(dim, cell_type, formulation, material_type, params, boundaries) -> dict`: programmatic constructor that produces the same context dict the parser would. Validates required fields (dim, cell_type, formulation, material_type). | `01-ARCHITECTURE.md §2 (Layer 1)` |
| 4.2 | Implement supported-subset validation in `build_context()`: reject unsupported dims (only 3), cell types (only hex8), formulations (only total_lagrangian), materials (only svk, j2_power_law). Raise `UnsupportedError` with plan-phase pointer. | `04-MECHANICS-IR.md §5`, `00-OVERVIEW.md §8` |
| 4.3 | Write tests covering P1 (valid MVP source → correct dict), P2-analogue (unknown material → error), P5-analogue (missing dim → error), P6 (convected coords). | `08-VERIFICATION.md §2.1 (P1, P2, P5, P6)` |

---

## 5. Compiler-Pass Test Completeness Audit

Ensure every test ID from `08-VERIFICATION.md §2` either already passes or is added in this sprint.

| # | Action item | Ref |
|---|-------------|-----|
| 5.1 | Audit S1–S9: verify all symbolic engine tests exist and pass. Fill any gaps (S9 covered by §3.4 above). | `08-VERIFICATION.md §2.2` |
| 5.2 | Audit M1–M6: verify all Mechanics IR tests exist and pass. | `08-VERIFICATION.md §2.3` |
| 5.3 | Audit E1–E6: verify all Element IR tests exist and pass. E5 covered by Sprint 1 §2.5, E6 covered by §3.4 above. | `08-VERIFICATION.md §2.4` |
| 5.4 | Audit N1–N5: verify all einsum tests exist and pass. | `08-VERIFICATION.md §2.5` |
| 5.5 | Audit T1–T4: verify all backend scheduling tests exist and pass. | `08-VERIFICATION.md §2.6` |
| 5.6 | Audit B1–B5: verify all boundary condition tests exist and pass. | `08-VERIFICATION.md §2.7` |
| 5.7 | Audit A1–A3: verify all artifact inspection tests exist and pass. | `08-VERIFICATION.md §2.8` |
| 5.8 | Audit C1–C3: verify all code emission tests exist and pass. C3 (generated vs handwritten for one element) is the key Sprint 1 deliverable. | `08-VERIFICATION.md §2.9` |
| 5.9 | Create a test-coverage map file `dev/tracking/verification_matrix.md` listing every test ID → test file → status (pass/fail/missing). | `08-VERIFICATION.md` |

---

## Sprint 2 Exit Criteria

- [ ] Generated J2 elasto-plastic solver compiles and runs under Taichi JIT.
- [ ] 1-element uniaxial tension past yield reproduces correct hardening curve.
- [ ] Generated plastic solver matches `ref_hex8_plastic.py` (displacement error < 1e-10).
- [ ] `verify/analytical.py` provides patch-test, rigid-body, cantilever, and uniaxial references.
- [ ] `verify/convergence.py` checks mesh-refinement convergence rates.
- [ ] `verify/patch_test.py` runs patch test and rigid-body test on generated solvers.
- [ ] `symbolic/convected.py` computes reference and current metrics (trivial for Cartesian).
- [ ] `frontend.build_context()` provides programmatic problem specification with validation.
- [ ] Every test ID in `08-VERIFICATION.md §2` (P1–P6, S1–S9, M1–M6, E1–E6, N1–N5, T1–T4, B1–B5, A1–A3, C1–C3) has a corresponding passing test.
- [ ] All pre-existing + Sprint 1 tests still pass.

---

## PLAN-A Phase Coverage

| PLAN-A Phase | Items covered in this sprint |
|--------------|------------------------------|
| A4.5 (AD oracle) | Already complete; §5.1 audits S8 |
| A8.2 (BC generation) | §5.6 audits B1–B5 completeness |
| A9.1 (Return mapping codegen) | §1.1 |
| A9.2 (Algorithmic tangent) | §1.2 |
| A9.3 (History variable mgmt) | §1.3 |
| A9.4 (Integration into element kernel) | §1.1–1.4 |
| A9.5 (J2 verification) | §1.5–1.6 |
| A10.2 (Generated vs handwritten) | §1.6 |
| A10.4 (Compiler-pass coverage) | §5.1–5.9 |
