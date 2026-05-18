# MVP Sprint 3 — Physical Benchmarks, Integration & Acceptance

> ⚠️ **Superseded for the frontend contract** by [`recovery_plan_latex_contract.md`](recovery_plan_latex_contract.md) (Phase 2 / R1). The benchmarks and acceptance work here remain in tree; the implicit LaTeX-input acceptance test is being moved to recovery-plan Phase 7 (R6). See [`STATUS_LEGEND.md`](../tracking/STATUS_LEGEND.md) and [`frontend_drift_history.md`](../reviews/frontend_drift_history.md).

**Goal:** Run the five physical benchmarks from PLAN-A §A10.3, pass the MVP acceptance test (necking bar within 2% of Simo & Hughes 1998), polish documentation, and declare the MVP done.

**Duration:** ~2 weeks

**Preconditions:** Sprint 2 complete — both elastic and plastic E2E solvers run, verification infrastructure in place, all compiler-pass tests passing.

---

## 1. Physical Benchmark Suite

These are the five acceptance-level benchmarks defined in `PLAN-A §A10.3` and `08-VERIFICATION.md §4.1`. Each requires a mesh, BCs, material parameters, a reference value, and an acceptance tolerance.

### 1a. Patch Test (Constant Strain)

| # | Action item | Ref |
|---|-------------|-----|
| 1.1 | Generate an irregular (non-affine) Hex8 mesh using `mesh_io.py` or a helper script. Store in `tests/meshes/patch_irregular_hex8.npz`. | `PLAN-A §A2.2` |
| 1.2 | Run the generated SVK elastic solver with constant-strain Dirichlet BCs on the irregular mesh. | `08-VERIFICATION.md §4.1` |
| 1.3 | Assert: stress field is exactly constant (relative error < 1e-12 at every quadrature point). | `PLAN-A §A10.3` |
| 1.4 | Mark test `@pytest.mark.e2e`. | `08-VERIFICATION.md §5.1` |

### 1b. Rigid Body Motion

| # | Action item | Ref |
|---|-------------|-----|
| 1.5 | Apply a finite rotation (e.g., 30° about z-axis) + translation to all nodes of a regular Hex8 mesh. | `PLAN-A §A2.2` |
| 1.6 | Run the generated SVK elastic solver and collect internal forces after one "solve" step. | `08-VERIFICATION.md §4.1` |
| 1.7 | Assert: internal force norm < 1e-12 (no spurious stiffness). | `PLAN-A §A10.3` |
| 1.8 | Mark test `@pytest.mark.e2e`. | `08-VERIFICATION.md §5.1` |

### 1c. Cantilever (Large-Deformation Elastic)

| # | Action item | Ref |
|---|-------------|-----|
| 1.9 | Generate a 40×8×4 structured Hex8 mesh for a cantilever beam. Store in `tests/meshes/cantilever_40x8x4.npz`. | `PLAN-A §A10.3` |
| 1.10 | Apply fixed BC on one face, tip traction on the opposite face. SVK elastic material with E=200 GPa, ν=0.3. | `PLAN-A §A8` |
| 1.11 | Run generated solver with Newton-Raphson + load stepping. | `PLAN-A §A8.1` |
| 1.12 | Compare tip displacement against Euler-Bernoulli reference from `verify/analytical.py`. | `08-VERIFICATION.md §4.1` |
| 1.13 | Assert: within 5% (coarse-mesh tolerance for 8-node hex). | `PLAN-A §A10.3` |
| 1.14 | Mark test `@pytest.mark.e2e`. | `08-VERIFICATION.md §5.1` |

### 1d. Cook's Membrane (Elasto-Plastic)

| # | Action item | Ref |
|---|-------------|-----|
| 1.15 | Generate a graded Hex8 mesh for the Cook's membrane geometry (trapezoidal cross-section, 3D extrusion). Store in `tests/meshes/cook_membrane_hex8.npz`. | `PLAN-A §A10.3` |
| 1.16 | Apply fixed BC on left face, uniform shear traction on right face. Hooke + power-law J2 material (σ_y0=243.0 MPa, K=300 MPa, n=0.4). | `PLAN-A §A9`, `08-VERIFICATION.md §4.1` |
| 1.17 | Run generated J2 solver with load stepping. | `PLAN-A §A9.4` |
| 1.18 | Compare tip (upper-right corner) vertical displacement against de Souza Neto et al. reference. | `08-VERIFICATION.md §4.1` |
| 1.19 | Assert: within 2% of published reference. | `PLAN-A §A10.3` |
| 1.20 | Mark test `@pytest.mark.e2e`. | `08-VERIFICATION.md §5.1` |

### 1e. Necking Bar (MVP Acceptance Test)

| # | Action item | Ref |
|---|-------------|-----|
| 1.21 | Generate a Hex8 mesh for a cylindrical bar with slight geometric imperfection (necking trigger). Exploit axial symmetry — quarter model with symmetry BCs. Store in `tests/meshes/necking_bar_hex8.npz`. | `PLAN-A §A10.3` |
| 1.22 | Apply displacement-controlled axial tension on the top face. Hooke + power-law J2 material matching Simo & Hughes (1998) parameters. | `PLAN-A §A10.3` |
| 1.23 | Run generated solver through full load history (pre-necking + necking onset). | `PLAN-A §A9` |
| 1.24 | Extract load-displacement curve from convergence history. | `06-CODEGEN.md §10.2` |
| 1.25 | Compare load-displacement curve against Simo & Hughes (1998) reference data. | `PLAN-A §A10.3` |
| 1.26 | **Assert: within 2% at all reported load levels.** This is the MVP acceptance criterion. | `PLAN-A §A10.3` |
| 1.27 | Store reference load-displacement data in `tests/golden/necking_bar_reference.npz`. | `08-VERIFICATION.md §5.2` |
| 1.28 | Mark test `@pytest.mark.e2e`. | `08-VERIFICATION.md §5.1` |

---

## 2. Convergence Study (MMS)

Validates the theoretical convergence rate of the Hex8 element.

| # | Action item | Ref |
|---|-------------|-----|
| 2.1 | Implement the MMS driver from Sprint 2 §2.7 on at least 4 mesh refinements (e.g., 2×2×2, 4×4×4, 8×8×8, 16×16×16 Hex8). | `08-VERIFICATION.md §4.2` |
| 2.2 | Manufacture displacement field: u*(x) = A sin(πx/L) cos(πy/L) sin(πz/L). Compute corresponding body force. | `08-VERIFICATION.md §4.2` |
| 2.3 | Run generated SVK elastic solver on each mesh level. Collect L2 and H1 errors. | `08-VERIFICATION.md §4.2` |
| 2.4 | Assert: L2 convergence rate ≥ 2.0 (p+1 for p=1), H1 rate ≥ 1.0 (p for p=1), within tolerance 0.1. | `08-VERIFICATION.md §4.2` |
| 2.5 | Mark test `@pytest.mark.slow`. | `08-VERIFICATION.md §5.1` |

---

## 3. Full End-to-End Pipeline Test

The "crown jewel" test from PLAN-A §A10.1 — exercises every layer.

| # | Action item | Ref |
|---|-------------|-----|
| 3.1 | Write `tests/test_full_pipeline.py` (`@pytest.mark.e2e`) that: (1) builds context via `frontend.build_context()`, (2) constructs ProblemIR, validates, checks supported subset, (3) lowers to ElementIR, extracts einsum strings, (4) runs einsum optimizer, verifies budget, (5) generates Taichi code via TaichiPrinter, (6) runs generated solver, (7) compares against handwritten reference, (8) compares against physical benchmark. | `PLAN-A §A10.1` |
| 3.2 | Run the full pipeline for SVK elastic (cantilever) and J2 plastic (uniaxial tension). Both must pass. | `PLAN-A §A10.1` |
| 3.3 | Assert artifact bundle completeness: Mechanics IR, Element IR, einsum plans, scheduling, generated source all present. | `08-VERIFICATION.md §2.8 (A1)` |

---

## 4. CI Configuration for Benchmark Tiers

| # | Action item | Ref |
|---|-------------|-----|
| 4.1 | Configure CI to run `pytest -m "not slow and not gpu and not e2e"` on every commit (< 2 min). | `08-VERIFICATION.md §5.1` |
| 4.2 | Configure CI to run `pytest -m "slow and not e2e"` on every PR (< 10 min): includes Taichi JIT compilation tests. | `08-VERIFICATION.md §5.1` |
| 4.3 | Configure CI to run `pytest -m e2e` on nightly schedule (< 60 min): includes all physical benchmarks. | `08-VERIFICATION.md §5.1` |
| 4.4 | Implement failure protocol: compiler-pass and reference-comparison failures block merge; physical-benchmark regressions create issues but don't block. | `08-VERIFICATION.md §5.3` |

---

## 5. Documentation

| # | Action item | Ref |
|---|-------------|-----|
| 5.1 | Update `README.md` with installation instructions, quickstart (uv sync → run example), and link to design docs. | `PLAN-A §A10.5` |
| 5.2 | Create example LaTeX-equivalent input files for each benchmark problem. Place in `dev/examples/`: `elastic_cantilever.py`, `plastic_uniaxial.py`, `cook_membrane.py`, `necking_bar.py`, `patch_test.py`. Each constructs a ProblemIR and calls `compile()` + `solve()`. | `PLAN-A §A10.5` |
| 5.3 | Add inline docstrings to all public API functions: `compile()`, `build_context()`, `ProblemIR`, `ElementIR`, `TaichiPrinter.generate()`, `newton_solve()`. | `PLAN-A §A10.5` |
| 5.4 | Create `CHANGELOG.md` entry for MVP release: summarise what's supported (3D Hex8, TL, SVK + J2, Taichi backend, matrix-free Newton). | `PLAN-A §A10.5` |

---

## 6. Final Cleanup & Polish

| # | Action item | Ref |
|---|-------------|-----|
| 6.1 | Run `uv run ruff check --fix` and `uv run ruff format` across the entire repo. | CLAUDE.md (code style) |
| 6.2 | Run `uv run mypy packages/mechdsl-core/src/mechdsl/` — fix any new type errors from Sprint 1–2 code. | CLAUDE.md (code style) |
| 6.3 | Run full test suite: `uv run pytest` (all markers). Verify zero failures. | CLAUDE.md (testing) |
| 6.4 | Review all `UnsupportedError` messages: ensure each names the correct Plan B phase and provides actionable guidance. | `.claude/rules/ir.md` |
| 6.5 | Verify JIT budget compliance: run `plan_contraction()` on all MVP einsum specs, assert none over budget. | `09-EINSUM-OPTIMISER.md`, `08-VERIFICATION.md §2.5 (N1)` |
| 6.6 | Remove any dead code, unused imports, or orphaned test fixtures introduced during sprints. | — |

---

## Sprint 3 Exit Criteria (= MVP DONE)

- [ ] **Patch test:** constant strain on irregular Hex8, relative error < 1e-12.
- [ ] **Rigid body:** zero internal force after rotation + translation, norm < 1e-12.
- [ ] **Cantilever:** tip displacement within 5% of Euler-Bernoulli.
- [ ] **Cook's membrane:** tip displacement within 2% of de Souza Neto et al.
- [ ] **Necking bar:** load-displacement curve within 2% of Simo & Hughes (1998). **(MVP acceptance criterion)**
- [ ] MMS convergence study: L2 rate ≥ 2.0, H1 rate ≥ 1.0 for Hex8.
- [ ] Full pipeline test exercises all 6 compiler layers.
- [ ] CI runs three tiers: fast (every commit), medium (every PR), nightly (benchmarks).
- [ ] README, examples, CHANGELOG, and docstrings are complete.
- [ ] `ruff`, `mypy`, and full `pytest` all pass cleanly.
- [ ] All compiler-pass test IDs from `08-VERIFICATION.md §2` have passing tests.

---

## PLAN-A Phase Coverage

| PLAN-A Phase | Items covered in this sprint |
|--------------|------------------------------|
| A2.2 (Elastic reference verification) | §1a, §1b (patch test, rigid body against reference) |
| A2.4 (Golden baselines) | §1.27 (necking bar reference data) |
| A10.1 (E2E pipeline test) | §3.1–3.3 |
| A10.2 (Generated vs handwritten) | Inherited from Sprint 1–2; re-verified in §3 |
| A10.3 (Physical benchmark suite) | §1.1–1.28 (all 5 benchmarks) |
| A10.4 (Compiler-pass coverage) | Inherited from Sprint 2 §5; re-verified in §6.3 |
| A10.5 (Documentation) | §5.1–5.4 |

---

## Cumulative PLAN-A Coverage (all 3 sprints)

| PLAN-A Phase | Status after Sprint 3 |
|--------------|----------------------|
| A1 (Scaffolding) | Complete (pre-existing) |
| A2 (Reference kernels) | Complete (pre-existing ref files + benchmark validation) |
| A3 (Parser / NRPyLaTeX) | Deferred — `build_context()` replaces parser for MVP |
| A4 (Symbolic engine) | Complete (pre-existing + Sprint 2 convected module) |
| A5 (IR construction) | Complete (pre-existing + Sprint 1 einsum extraction) |
| A6 (Einsum optimizer) | Complete (pre-existing + Sprint 1 integration) |
| A7 (Taichi codegen) | Complete (pre-existing + Sprint 1 Newton/main emission) |
| A8 (Newton + BCs + mesh) | Complete (Sprint 1 Newton driver + BC integration) |
| A9 (J2 plasticity) | Complete (Sprint 2 J2 E2E + verification) |
| A10 (Integration + V&V) | Complete (Sprint 3 benchmarks + documentation) |

**Note on A3 (Parser):** The LaTeX frontend requires the NRPyLaTeX fork, which is a separate dependency decision. The MVP is fully functional without it — users construct `ProblemIR` programmatically via `build_context()`. The parser is a UX improvement, not a correctness requirement. It can be implemented as a follow-up or as the first item in Plan B.
