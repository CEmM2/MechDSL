# Sprint 3 Implementation Plan — Physical Benchmarks, Integration & Acceptance

> ⚠️ **Superseded** by [`recovery_plan_latex_contract.md`](recovery_plan_latex_contract.md) (Phase 7 / R6 archival, P7-5). This is the earlier draft of the Sprint 3 plan; it is retained for historical reference only. The active execution source is the recovery plan. See [`STATUS_LEGEND.md`](../tracking/STATUS_LEGEND.md) and [`frontend_drift_history.md`](../reviews/frontend_drift_history.md).

## Context

**Problem:** Sprint 2 delivered the complete compiler pipeline (ProblemIR → Taichi solver) and verification infrastructure, but the physical benchmark tests in `test_benchmarks.py` are placeholder-quality: coarse meshes, loose tolerances, skipped reference comparisons. The MVP cannot be declared done without passing the 5 physical benchmarks at spec-required tolerances, a full pipeline test exercising all 6 compiler layers, CI nightly scheduling, and documentation.

**What already works:**
- Patch test on irregular mesh (`test_patch_test.py:341` — 3x3x3 irregular, error < 1e-12) ✓
- Rigid body 30° rotation (`test_patch_test.py:374` — irregular mesh, force_norm < 1e-12) ✓
- MMS convergence on 3 levels [2,3,4] with L2 ≥ 2.0, H1 ≥ 1.0 (`test_convergence.py:340,356`) ✓
- Reference solvers: `tests/ref/ref_hex8_elastic.py`, `tests/ref/ref_hex8_plastic.py` ✓
- Solver infrastructure: newton.py, load_stepping.py, mesh_io.py, history_fields.py ✓
- Verify harness: convergence.py (`run_mms_convergence`, `check_convergence_rate`), patch_test.py (`run_patch_test`, `run_rigid_body_test`, `generate_irregular_mesh`), analytical.py, ad_oracle.py ✓

**What's incomplete (the gaps this sprint fills):**
- Cantilever: 4x2x1 mesh with 0.25-2.0x tolerance → needs 40x8x4 with 5%
- Cook's membrane: rectangular approximation, `test_reference_comparison` is `pytest.skip()` → needs trapezoidal mesh + 2% reference comparison
- Necking bar: 2x1x1 uniform bar, `test_reference_comparison` is `pytest.skip()` → needs refined mesh with imperfection + 2% reference comparison (MVP acceptance criterion)
- MMS: 3 levels [2,3,4] → needs 4 levels with proper 2x refinement [2,4,8,16]
- No `test_full_pipeline.py` exercising all 6 layers
- CI missing nightly e2e tier
- Documentation incomplete (README basic, no example .py scripts, no CHANGELOG MVP entry)

---

## Phase 1: Cantilever Upgrade + MMS Extension + Marker Cleanup

**Branch:** `sprint3_phase-1`

### Tasks

| # | Task | File(s) | Size |
|---|------|---------|------|
| P1-T1 | Upgrade cantilever to 40x8x4 mesh, 5% EB tolerance | `tests/test_benchmarks.py` (`TestCantilever`) | M |
| P1-T2 | Add 4-level MMS convergence test [2,4,8,16] | `tests/test_convergence.py` | S |
| P1-T3 | Add `@pytest.mark.e2e` to `TestTaskP3T5` in test_patch_test.py (currently only `@pytest.mark.slow`) | `tests/test_patch_test.py` | S |
| P1-T4 | Add 30deg finite rotation test to `TestRigidBodyMotion` in test_benchmarks.py (using reference solver directly) | `tests/test_benchmarks.py` | S |

**P1-T1 details:**
- Keep existing coarse-mesh tests (they run fast, catch regressions)
- Add new fixture `cantilever_problem_refined` with `generate_hex8_mesh(40, 8, 4, 10.0, 2.0, 1.0)` -- generates mesh on-the-fly (no .npz file)
- Material: E=1000, nu=0.3 (same as existing)
- New test `test_tip_displacement_within_5_percent`: assert `abs(1 - tip_uz/delta_eb) < 0.05`
- Mark `@pytest.mark.e2e @pytest.mark.slow`
- Risk: 40x8x4 = 12,285 nodes, CG solve will be slow in pure numpy. Set `cg_max_iter=5000`. Acceptable for `@pytest.mark.slow`.

**P1-T2 details:**
- Add `test_mms_4level_convergence` using `run_mms_convergence(lam=1.0, mu=1.0, mesh_levels=[2, 4, 8, 16])`
- 16^3 mesh = 4913 nodes -- slow but acceptable for `@pytest.mark.e2e @pytest.mark.slow`
- Assert L2 rate >= 2.0, H1 rate >= 1.0 (tol=0.1)
- Fallback: if 16^3 is prohibitively slow, use [2, 4, 8] (still proper 2x ratios)

### Exit Criteria
- `test_tip_displacement_within_5_percent` passes on 40x8x4 mesh
- MMS 4-level convergence passes with L2 >= 2.0, H1 >= 1.0
- `TestTaskP3T5` has `@pytest.mark.e2e` marker
- All pre-existing tests still pass

### Verification
```bash
uv run pytest packages/mechdsl-core/tests/ -m "not slow and not gpu" -x -q
uv run pytest packages/mechdsl-core/tests/test_benchmarks.py -k "cantilever and 5_percent" -x -v
uv run pytest packages/mechdsl-core/tests/test_convergence.py -k "4level" -x -v
```

---

## Phase 2: Cook's Membrane -- Trapezoidal Mesh & J2 Benchmark

**Branch:** `sprint3_phase-2`
**Depends on:** Phase 1

### Tasks

| # | Task | File(s) | Size |
|---|------|---------|------|
| P2-T1 | Implement `generate_cook_membrane_mesh(nx, ny, nz) -> HexMesh` | `src/mechdsl/solver/mesh_io.py` | M |
| P2-T2 | Test trapezoidal mesh geometry | `tests/test_mesh_io.py` | S |
| P2-T3 | Implement Cook's membrane benchmark with J2 plasticity and reference comparison | `tests/test_benchmarks.py` (`TestCooksMembrane`) | L |

**P2-T1 details -- trapezoidal mesh generator:**
- Cook's geometry: left face x=0 height=44mm, right face x=48mm height=16mm, thickness=1mm
- Implementation: generate structured mesh on [0,48]x[0,44]x[0,1], then warp y-coordinates:
  `y_warped = y * (44 - 28*x/48) / 44`
- Boundary tags: `x0` (fixed), `x1` (loaded), `y0`, `y1`, `z0`, `z1`

**P2-T3 details -- benchmark implementation:**
- Material decision: use **nu=0.3** (not 0.4999) to avoid Hex8 volumetric locking. Generate a self-converged reference from a fine mesh run.
- Material: E=240.565 MPa, nu=0.3, sigma_y0=243.0 MPa, K=300.0 MPa, n=0.4
- Mesh: `generate_cook_membrane_mesh(8, 8, 1)` for production test
- BCs: fix left face (x=0) all DOFs, uniform shear traction on right face (y-direction)
- Solve with `solve_plastic` + load stepping (10 steps)
- Extract: average y-displacement of upper-right corner nodes (x=48, y~16)
- Compare against self-converged fine-mesh reference (2% tolerance)
- Un-skip `test_reference_comparison`

### Exit Criteria
- `generate_cook_membrane_mesh` produces correct trapezoidal geometry (verified by corner coordinates)
- Cook's membrane converges with J2 plasticity
- Tip displacement within 2% of self-converged reference
- `test_reference_comparison` no longer skipped

### Verification
```bash
uv run pytest packages/mechdsl-core/tests/test_mesh_io.py -k "cook" -x -v
uv run pytest packages/mechdsl-core/tests/test_benchmarks.py -k "cook" -x -v
```

---

## Phase 3: Necking Bar -- MVP Acceptance Test

**Branch:** `sprint3_phase-3`
**Depends on:** Phase 2
**Critical path -- this is the MVP acceptance criterion**

### Tasks

| # | Task | File(s) | Size |
|---|------|---------|------|
| P3-T1 | Implement necking bar mesh generator with geometric imperfection | `src/mechdsl/solver/mesh_io.py` | M |
| P3-T2 | Test necking bar mesh geometry and imperfection | `tests/test_mesh_io.py` | S |
| P3-T3 | Generate self-converged reference data (fine mesh) | `tests/generate_golden.py`, `tests/golden/necking_bar_reference.npz` | M |
| P3-T4 | Implement necking bar benchmark with load-displacement curve extraction and 2% comparison | `tests/test_benchmarks.py` (`TestNeckingBar`) | L |

**P3-T1 details -- mesh generator:**
- Use rectangular bar (simpler than cylindrical, mechanically valid for necking). Quarter-model with symmetry BCs.
- `generate_necking_bar_mesh(nx, ny, nz, L, W, imperfection=0.005) -> HexMesh`
- Geometry: bar [0,L/2]x[0,W/2]x[0,W/2], imperfection: reduce cross-section width at z=L/2 by `imperfection * W` with smooth taper over ~2 elements
- Boundary tags: `z0` (symmetry, u_z=0), `z1` (prescribed displacement), `x0` (symmetry, u_x=0), `y0` (symmetry, u_y=0)

**P3-T3 details -- self-converged reference:**
- Run `ref_hex8_plastic.py::solve_plastic` on a fine mesh (e.g. 8x8x32)
- Store `displacement[]`, `force[]`, `mesh_params`, `material_params` in `tests/golden/necking_bar_reference.npz`
- This avoids needing to digitize Simo & Hughes (1998) figures. The 2% tolerance validates generated solver matches reference solver.

**P3-T4 details -- benchmark:**
- Replace `necking_bar_problem` fixture with production setup:
  - Mesh: `generate_necking_bar_mesh(4, 4, 16, L=20.0, W=2.0, imperfection=0.005)`
  - Material: J2 power-law (E=206.9e3, nu=0.29, sigma_y0=450.0, K=129.24, n=0.1) -- or simpler parameters that produce necking
  - Displacement-controlled: 20 load steps up to ~20% nominal strain
- Extract load-displacement curve at each converged step
- Interpolate onto reference displacement points
- Assert: relative error < 2% at all load levels
- Un-skip `test_reference_comparison`

### Exit Criteria
- Necking bar mesh has correct geometry with visible imperfection at midplane
- Newton converges through full load history (pre-necking + necking onset)
- Load-displacement curve within 2% of self-converged reference
- Reference data stored in `tests/golden/necking_bar_reference.npz`
- **MVP acceptance criterion met**

### Verification
```bash
uv run pytest packages/mechdsl-core/tests/test_mesh_io.py -k "necking" -x -v
uv run pytest packages/mechdsl-core/tests/test_benchmarks.py -k "necking" -x -v
```

---

## Phase 4: Full Pipeline Test & CI Nightly

**Branch:** `sprint3_phase-4`
**Depends on:** Phase 3

### Tasks

| # | Task | File(s) | Size |
|---|------|---------|------|
| P4-T1 | Create `test_full_pipeline.py` exercising all 6 compiler layers | `tests/test_full_pipeline.py` (new) | M |
| P4-T2 | Add nightly e2e schedule to CI | `.github/workflows/ci.yml` | M |
| P4-T3 | Implement failure protocol (benchmark regressions create issues, compiler failures block merge) | `.github/workflows/ci.yml` | S |

**P4-T1 details -- full pipeline test:**
- Two test methods: elastic (SVK cantilever) and plastic (J2 uniaxial)
- Each exercises all 6 layers:
  1. `frontend.build_context()` -> context dict
  2. Construct `ProblemIR` from context -> validates supported subset
  3. `localise()` -> `LocalisationResult` with `ElementIR` and einsum specs
  4. `localise_and_optimize()` -> `ContractionPlan`s, verify JIT budget
  5. `emit()` -> Taichi source, `ast.parse()` validates syntax
  6. Compare against golden files (`elastic_cantilever.npz`, `plastic_uniaxial.npz`)
- Assert artifact bundle completeness: `problem_ir_dict`, `element_ir_summary`, `contraction_plans` (3 entries), `emitted_source` all non-empty
- Mark `@pytest.mark.e2e`
- Reuse `_make_elastic_problem_ir()` / `_make_plastic_problem_ir()` patterns from `test_e2e.py`

**P4-T2 details -- CI nightly:**
- Add `schedule: cron: '0 3 * * *'` trigger
- New job `e2e-benchmarks`: runs `pytest -m e2e --tb=short -q` (< 60 min budget)
- Update existing `test` job filter to: `-m "not slow and not gpu and not e2e"`
- Update existing `slow-tests` job filter to: `-m "slow and not e2e"`

**P4-T3 details -- failure protocol:**
- `e2e-benchmarks` job: benchmark test step has `continue-on-error: true`
- On failure, create GitHub issue via `actions/github-script@v7` with label `benchmark-regression`

### Exit Criteria
- `test_full_pipeline.py` exercises all 6 layers for both elastic and plastic
- Artifact bundle completeness passes
- CI has 3 tiers: fast (every commit), medium/slow (every PR), nightly (e2e)
- Nightly benchmark failures create issues instead of blocking

### Verification
```bash
uv run pytest packages/mechdsl-core/tests/test_full_pipeline.py -x -v
uv run pytest packages/mechdsl-core/tests/ -m e2e --collect-only -q  # verify collection
```

---

## Phase 5: Documentation & Examples

**Branch:** `sprint3_phase-5`
**Depends on:** Phase 4

### Tasks

| # | Task | File(s) | Size |
|---|------|---------|------|
| P5-T1 | Update README with installation, quickstart, architecture | `README.md` | M |
| P5-T2 | Create 5 example Python scripts | `dev/examples/{elastic_cantilever,plastic_uniaxial,cook_membrane,necking_bar,patch_test}.py` (new) | M |
| P5-T3 | Add docstrings to public API functions | `codegen/__init__.py`, `frontend/__init__.py`, `ir/mechanics_ir.py`, `ir/element_ir.py`, `codegen/taichi_printer.py`, `solver/newton.py` | M |
| P5-T4 | Update CHANGELOG for MVP release | `CHANGELOG.md` | S |
| P5-T5 | Review UnsupportedError messages reference correct Plan B phases | `frontend/__init__.py`, `ir/mechanics_ir.py`, `lowering/fe_localise.py` | S |

**P5-T2 details:** Each script constructs a `ProblemIR` programmatically via `build_context()`, calls `compile()`, prints a summary. Self-contained and runnable with `uv run python dev/examples/X.py`.

### Exit Criteria
- README has installation, quickstart, architecture overview
- 5 example scripts runnable
- All public API functions have numpy-style docstrings
- CHANGELOG has MVP release entry
- All UnsupportedError messages point to correct Plan B phases

---

## Phase 6: Final Cleanup & Sprint Exit

**Branch:** `sprint3_phase-6`
**Depends on:** Phase 5

### Tasks

| # | Task | File(s) | Size |
|---|------|---------|------|
| P6-T1 | `uv run ruff check --fix` + `uv run ruff format` | All `packages/` | S |
| P6-T2 | `uv run mypy` -- fix new type errors | `src/mechdsl/` | M |
| P6-T3 | Full test suite (`pytest` all markers) -- zero failures | All tests | S |
| P6-T4 | JIT budget compliance (`test_einsum.py -k budget`) | `tests/test_einsum.py` | S |
| P6-T5 | Remove dead code, unused imports, resolved TODOs, remove remaining `pytest.skip()` stubs | Various | S |
| P6-T6 | Verify all Sprint 3 exit criteria (checklist) | -- | M |
| P6-T7 | Sprint 3 handoff document | -- | S |

### Sprint 3 Exit Criteria (= MVP DONE)
- [ ] Patch test: constant strain on irregular Hex8, relative error < 1e-12
- [ ] Rigid body: zero internal force after 30deg rotation + translation, norm < 1e-12
- [ ] Cantilever: tip displacement within 5% of Euler-Bernoulli (40x8x4 mesh)
- [ ] Cook's membrane: tip displacement within 2% of reference
- [ ] Necking bar: load-displacement curve within 2% of reference **(MVP acceptance)**
- [ ] MMS convergence: L2 rate >= 2.0, H1 rate >= 1.0 on 4 mesh levels
- [ ] Full pipeline test exercises all 6 compiler layers
- [ ] CI runs 3 tiers: fast (commit), slow (PR), nightly (e2e benchmarks)
- [ ] README, examples, CHANGELOG, docstrings complete
- [ ] `ruff`, `mypy`, full `pytest` all pass cleanly

### Verification
```bash
uv run ruff check packages/ && uv run ruff format --check packages/
uv run mypy packages/mechdsl-core/src/mechdsl/
uv run pytest packages/mechdsl-core/tests/ -x -q
uv run pytest packages/mechdsl-core/tests/ -m e2e -x -q
```

---

## Key Technical Decisions

1. **Cook's membrane nu=0.3** (not 0.4999): Standard Hex8 has severe volumetric locking at nu->0.5. Using nu=0.3 with a self-converged fine-mesh reference avoids this. B-bar/F-bar is out of MVP scope.

2. **Necking bar rectangular** (not cylindrical): A rectangular bar with imperfection is mechanically valid for necking and avoids cylindrical mesh complexity. Self-converged reference data instead of digitizing Simo & Hughes (1998).

3. **MMS mesh levels [2,4,8,16]**: Proper 2x refinement ratios for clean convergence rate measurement. 16^3 is slow but acceptable for nightly e2e.

4. **SVK + finite rotation**: Already verified working -- SVK in Total Lagrangian gives E=0 for pure rotation, so f_int=0 exactly regardless of angle. Tests in `test_patch_test.py:374` pass with 30deg rotation.

---

## Files Summary

| File | Action | Phase |
|------|--------|-------|
| `tests/test_benchmarks.py` | Upgrade cantilever, Cook's, necking bar | 1,2,3 |
| `tests/test_convergence.py` | Add 4-level MMS test | 1 |
| `tests/test_patch_test.py` | Add e2e marker | 1 |
| `src/mechdsl/solver/mesh_io.py` | Add Cook's + necking bar mesh generators | 2,3 |
| `tests/test_mesh_io.py` | Tests for new mesh generators | 2,3 |
| `tests/generate_golden.py` | Necking bar reference generation | 3 |
| `tests/golden/necking_bar_reference.npz` | New reference data | 3 |
| `tests/test_full_pipeline.py` | New full pipeline test | 4 |
| `.github/workflows/ci.yml` | Nightly e2e, failure protocol | 4 |
| `README.md` | Installation, quickstart, architecture | 5 |
| `dev/examples/*.py` | 5 new example scripts | 5 |
| `CHANGELOG.md` | MVP release entry | 5 |
| Various `src/` | Docstrings, UnsupportedError review | 5 |

All paths relative to `packages/mechdsl-core/` unless otherwise noted.
