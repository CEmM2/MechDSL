# MVP Sprint 1 — Core Runtime Loop

> ⚠️ **Superseded for the frontend contract** by [`recovery_plan_latex_contract.md`](recovery_plan_latex_contract.md) (Phase 2 / R1). The runtime / codegen / solver work in this sprint stayed correct and remains in tree; the LaTeX-input contract it implicitly assumed has been moved to the recovery plan. See [`STATUS_LEGEND.md`](../tracking/STATUS_LEGEND.md) and [`frontend_drift_history.md`](../reviews/frontend_drift_history.md).

**Goal:** Close the "can it actually run?" gap. After this sprint the compiler pipeline can produce a Taichi solver that compiles, runs a Newton solve, and converges on a single-element elastic test.

**Duration:** ~2 weeks

**Preconditions:** All 687 existing tests remain green. No regressions.

---

## 1. Newton-Raphson Driver (`solver/newton.py`)

The Newton driver is the single biggest functional gap — every supporting piece (mesh I/O, load stepping, history fields, linear solver adapter) is already implemented, but the driver that orchestrates them is a one-line stub.

| # | Action item | Ref |
|---|-------------|-----|
| 1.1 | Implement `newton_solve()` following the pseudocode in `06-CODEGEN.md §9.1`: residual assembly → linear solve (via `LinearSolverInterface`) → convergence check → increment update. | `06-CODEGEN.md §9` |
| 1.2 | Wire Newton driver to `load_stepping.py`: adaptive step-size control (increase ×1.5 if converged in <5 iters, halve and retry on failure). | `06-CODEGEN.md §9.2`, `PLAN-A §A8.4` |
| 1.3 | Wire Newton driver to `history_fields.py`: copy `stress → stress_old`, `peeq → peeq_old` only at converged load steps. | `06-CODEGEN.md §3.2`, `PLAN-A §A9.3` |
| 1.4 | Integrate Dirichlet enforcement: modify residual (zero fixed DOFs) and increment (zero fixed DOF corrections) each Newton iteration, per `10-BOUNDARIES.md §4`. | `10-BOUNDARIES.md §4–5` |
| 1.5 | Integrate Neumann loading: add traction contribution to `f_ext` at each load step. | `10-BOUNDARIES.md §6` |
| 1.6 | Emit convergence diagnostics: per-step and per-iteration log of load parameter λ, residual norm, Newton iter count, linear solver iter count and residual. | `06-CODEGEN.md §10.2` |
| 1.7 | Write unit tests for Newton driver: (a) converge a 1-element linear elastic system in 1 iteration, (b) divergence detection triggers step halving, (c) Dirichlet DOFs remain zero throughout solve. | `08-VERIFICATION.md §2.6 (T4)` |

---

## 2. Einsum String Extraction (`lowering/einsum_extract.py`)

Currently a one-line stub. This module bridges the Element IR to the einsum optimizer — without it the codegen pipeline cannot be driven programmatically from a ProblemIR.

| # | Action item | Ref |
|---|-------------|-----|
| 2.1 | Implement `extract_einsum_specs(element_ir: ElementIR) -> dict[str, EinsumSpec]` that returns the local-force and local-tangent einsum strings plus tensor shapes for Hex8 TL. | `05-ELEMENT-IR.md`, `09-EINSUM-OPTIMISER.md §2` |
| 2.2 | Local force einsum: `'iI,aI->ai'` (PK1 · dN scatter), shapes `(3,3), (8,3) -> (8,3)`. | `01-ARCHITECTURE.md §3` |
| 2.3 | Local tangent einsum: two-step push-forward `'iK,KILJ->iILJ'` then `'iILJ,jL->iIjJ'`, shapes `(3,3), (3,3,3,3) -> (3,3,3,3)`. | `06-CODEGEN.md §6.2`, `09-EINSUM-OPTIMISER.md §3` |
| 2.4 | Validate that extracted specs match the existing hardcoded specs used by `einsum_optimizer.py` (regression guard). | `08-VERIFICATION.md §2.4 (E5)` |
| 2.5 | Write tests: (a) extraction from a valid Hex8 ElementIR produces expected strings, (b) extraction from unsupported element type raises `LocalisationError`. | `08-VERIFICATION.md §2.4 (E5, E6)` |

---

## 3. Programmatic Pipeline Wiring

Connect the layers so that a ProblemIR can flow through to generated Taichi source without manual intervention.

| # | Action item | Ref |
|---|-------------|-----|
| 3.1 | Create a `compile(problem_ir: ProblemIR) -> ArtifactBundle` top-level function that chains: `fe_localise()` → `extract_einsum_specs()` → `plan_contraction()` → `TaichiPrinter.generate()` → bundle. | `01-ARCHITECTURE.md §8.2` |
| 3.2 | Store all intermediate products (Mechanics IR, Element IR, contraction plans, generated source) in the `ArtifactBundle`. | `01-ARCHITECTURE.md §8.1` |
| 3.3 | Add golden-file regression: serialize the artifact bundle for the MVP SVK Hex8 problem and compare against `tests/golden/generated_elastic.py.golden`. | `08-VERIFICATION.md §2.8 (A1–A3)` |
| 3.4 | Write a pipeline integration test: construct a ProblemIR for SVK elastic Hex8 → `compile()` → assert generated source is valid Python (AST parse, import check). | `08-VERIFICATION.md §2.9 (C1, C2)` |

---

## 4. TaichiPrinter: Newton Driver Emission

The printer already emits constitutive kernels, element kernels, and BCs, but `emit_newton_driver()` and `emit_main()` need to produce working solver scaffolding.

| # | Action item | Ref |
|---|-------------|-----|
| 4.1 | Implement `emit_newton_driver()`: generate the Newton loop that calls `compute_internal_forces`, `tangent_matvec`, BC enforcement, and the linear solver interface. | `06-CODEGEN.md §9.1` |
| 4.2 | Implement `emit_main()`: generate the `if __name__ == '__main__'` block with mesh loading, BC binding, `newton_raphson()` call, and result export. | `06-CODEGEN.md §2` |
| 4.3 | Implement `emit_postprocess()`: VTK/XDMF export via meshio (nodal displacement, extrapolated stress, PEEQ). | `06-CODEGEN.md §10.1` |
| 4.4 | Verify emitted code against golden file `tests/golden/generated_elastic.py.golden`. | `08-VERIFICATION.md §2.9 (C1–C3)` |

---

## 5. End-to-End Taichi Smoke Test

The highest-value validation gate: prove the generated code actually compiles and runs under Taichi JIT.

| # | Action item | Ref |
|---|-------------|-----|
| 5.1 | Create `tests/test_e2e_taichi.py` (mark `@pytest.mark.slow`): construct SVK elastic ProblemIR → compile → write generated `.py` → `ti.init(arch=ti.cpu)` → load a 1-element Hex8 mesh → apply simple tension BCs → run 1 load step → assert Newton converges. | `PLAN-A §A10.1` |
| 5.2 | Compare generated-code displacement against `tests/ref/ref_hex8_elastic.py` on the same 1-element problem: max field difference < 1e-10. | `08-VERIFICATION.md §3.3`, `PLAN-A §A10.2` |
| 5.3 | Add a CI job (or extend existing) that runs `pytest -m slow` on PRs touching `codegen/` or `solver/`. | `08-VERIFICATION.md §5.1` |

---

## 6. Constitutive Base Class (`symbolic/constitutive.py`)

Thin but important — currently SVK and J2 are standalone modules with no shared interface. A base class makes the lowering and codegen layers model-agnostic.

| # | Action item | Ref |
|---|-------------|-----|
| 6.1 | Implement `ConstitutiveModel` ABC with methods: `pk2_stress(kin) -> Matrix`, `material_tangent(kin) -> Array`, `voigt_tangent(kin) -> Matrix`, `state_variables() -> list[str]`, `is_dissipative() -> bool`. | `01-ARCHITECTURE.md §2 (Layer 2)`, `.claude/rules/symbolic.md` |
| 6.2 | Refactor `models/svk.py` and `models/j2_power_law.py` to inherit from `ConstitutiveModel`. All existing tests must pass unchanged. | `PLAN-A §A4.2, A4.3` |
| 6.3 | Update `fe_localise.py` to use the `ConstitutiveModel` interface instead of model-specific branching. | `05-ELEMENT-IR.md` |
| 6.4 | Write test: instantiate each model via the ABC, call `pk2_stress` and `material_tangent`, assert output shapes and types. | `08-VERIFICATION.md §2.2 (S3, S7)` |

---

## Sprint 1 Exit Criteria

- [ ] `solver/newton.py` implements a working Newton-Raphson loop with load stepping and history management.
- [ ] `lowering/einsum_extract.py` extracts correct einsum specs from Hex8 ElementIR.
- [ ] `compile()` top-level function produces an `ArtifactBundle` from a `ProblemIR`.
- [ ] `TaichiPrinter` emits a complete, self-contained solver `.py` file.
- [ ] At least one `@pytest.mark.slow` E2E test compiles and runs the generated Taichi code.
- [ ] Generated solver matches handwritten reference on a 1-element problem (displacement error < 1e-10).
- [ ] `ConstitutiveModel` ABC exists; SVK and J2 inherit from it.
- [ ] All pre-existing 687 tests still pass. New tests added for every item above.

---

## PLAN-A Phase Coverage

| PLAN-A Phase | Items covered in this sprint |
|--------------|------------------------------|
| A5.3 (FE localisation) | §2 — einsum extraction completes the lowering step |
| A6.2 (Einsum ↔ Element IR integration) | §2.1–2.4 |
| A7.2 (TaichiPrinter) | §4 — Newton driver + main emission |
| A8.1 (Newton-Raphson driver) | §1.1–1.6 |
| A8.2 (BC generation) | §1.4–1.5 (integration into Newton loop) |
| A8.4 (Load stepping) | §1.2 |
| A9.3 (History variable management) | §1.3 |
| A10.1 (E2E pipeline test) | §5.1 |
| A10.2 (Generated vs handwritten) | §5.2 |
