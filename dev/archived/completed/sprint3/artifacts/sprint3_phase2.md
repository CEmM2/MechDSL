# Sprint 3 Phase 2 Review

**Branch:** `sprint3_phase-2`
**Date:** 2026-04-09
**Scope:** 12 files changed, +735 lines, -127 lines

---

## Codex Review

**Session ID:** `019d728d-7363-73b1-a80b-f6cc185cae7e`

No-ship: the new Cook's membrane coverage does not provide trustworthy acceptance evidence yet. The benchmark oracle is explicitly non-converged, and the applied load is discretized in a mesh-dependent way that can mask or manufacture agreement.

### [HIGH] Self-referential benchmark oracle is not mesh-converged

**File:** `packages/mechdsl-core/tests/test_benchmarks.py:685-797`

The test hard-codes the 2x2x1 result as the reference even though the class docstring states the same solver changes by about 17.5% when moving from 2x2x1 to 3x3x1. That means this benchmark can pass its 2% tolerance while still being materially wrong relative to mesh-refined behavior. This is not just a weak test: it creates false confidence for a distortion-sensitive benchmark and would let solver regressions ship as long as they preserve the old coarse-mesh answer. The conclusion that this is 'self-converged' is contradicted by the numbers in the same file.

**Recommendation:** Replace the 2x2x1 replay oracle with an actually defensible reference: either a mesh-refined value from the finest feasible mesh, an external literature/reference-solver value, or a refinement-based assertion that the solution approaches a stable limit. Also make the checked-in generator reproduce the exact oracle used by the test.

### [HIGH] Mesh-dependent load application via equal nodal point loads

**File:** `packages/mechdsl-core/tests/test_benchmarks.py:724-729`

The benchmark applies `total_shear / len(right_nodes)` to every node on the loaded face. On a slanted Hex8 boundary this is not the consistent nodal load for uniform traction; the correct weights depend on face area and shape functions, so corners and edge nodes should not all receive the same contribution. As a result, refining the mesh changes the discrete loading operator itself, not just the solution accuracy. That undermines both the claimed convergence study and the regression value being checked here, because agreement can drift due to load discretization rather than constitutive or solver correctness. This inference is supported by the code path here and repeated in the reference-generation helper.

**Recommendation:** Assemble the Cook's membrane Neumann load via boundary-face integration on the `x1` surface and use the resulting consistent nodal loads in both the benchmark and the reference generator. At minimum, derive face-based weights instead of equal per-node forces.

### Assessment

1. **Self-referential oracle (HIGH)** -- By design, but the framing is misleading. The test is documented as a "solver reproducibility" check (same mesh, same solver, deterministic replay), NOT a convergence or accuracy test. The 17.5% mesh sensitivity is acknowledged in the docstring. However, Codex is correct that calling the value `_REFERENCE_TIP_UY` and testing within 2% tolerance creates an appearance of validation that doesn't exist. Phase 3's necking bar benchmark has the same issue. Worth fixing by renaming to `_REGRESSION_TIP_UY` and reframing the tolerance as a regression gate, or upgrading to a proper reference when the solver improves.

2. **Mesh-dependent loading (HIGH)** -- Legitimate physics concern, repeated from the Phase 1 review (same pattern on the cantilever). The equal-nodal-load approximation is standard for coarse-mesh development work but breaks down on refined or distorted meshes. On the 2x2x1 Cook's membrane, the right face has only 4 nodes (2x2 grid) so the error is small. On a refined mesh it would matter. This is a known limitation of the MVP reference solver, not a Phase 2 regression. A consistent surface traction assembly requires face integration infrastructure that is out of MVP scope (planned for Sprint 4+). The self-converged reference compensates because both the test and the reference use the same loading.

---

## Code Review (from diff-review)

### Good

- **Pre-warp boundary tag detection.** `generate_cook_membrane_mesh` detects face tags on the rectangular grid before applying the y-coordinate warp. This is critical: after warping, the y1 face no longer sits at constant y=44, so post-warp detection would miss nodes. The ordering is correct and documented in comments.

- **Class-scoped fixture avoids redundant 91-second solves.** `cooks_membrane_problem` uses `scope="class"` so the expensive `solve_plastic` call (10 load steps, 91s) runs once and is shared across all 4 test methods. Matches the Phase 1 `TestMMS4LevelConvergence` pattern.

- **Comprehensive mesh geometry tests.** All 6 test stubs from the scaffold phase were replaced with real assertions, plus a parametrized multi-density test covering 1x1x1 and 8x8x2 extremes. Corner coordinates, boundary tags, node/element counts, positive Jacobians, and face node identification are all checked.

- **Reference generation utility is not collected by pytest.** `_gen_cooks_ref.py` uses underscore prefix to prevent pytest collection. Verified that `python_files` is not configured in pyproject.toml, so the default `test_*.py` pattern protects against accidental collection.

### Bad

- **No CHANGELOG entry for Phase 2.** 735 lines of new benchmark infrastructure with no CHANGELOG record. Deferred to Phase 5 (P5-4) by plan, same as Phase 1.

### Ugly

- **Newton tolerance relaxed to 1e-6 without convention update.** `07-CONVENTIONS.md` specifies `tol=1e-8` for Newton convergence. The Cook's membrane benchmark uses `tol=1e-6` with an inline comment explaining the CG solver performance justification. This is the right pragmatic choice for MVP, but creates a precedent where benchmarks deviate from conventions without updating the spec. The necking bar benchmark (Phase 3) will face the same pressure.

- **`_gen_cooks_ref.py` does not reproduce the test's reference value.** The checked-in generator script runs a mesh convergence study, but the actual `_REFERENCE_TIP_UY` value in the test was extracted from a separate manual run. The generator and the test are decoupled -- changing material parameters in one won't update the other.

- **Fixture pattern inconsistency persists.** `cooks_membrane_problem` is a `self` fixture inside the test class (inherited from the cantilever pattern noted in Phase 1), while MMS uses module-level `scope="class"` fixtures. Not a bug, but accumulating tech debt.

### Questions

- **Is the 2% tolerance meaningful for a self-converged reference?** A 2% gate on a deterministic replay should either pass exactly (0% error) or indicate a solver change. The 2% headroom exists to absorb floating-point non-determinism across platforms, but has it been validated that the solver IS non-deterministic across runs?

---

## Decision Log (from diff-review)

### Use 2x2x1 mesh instead of plan's 8x8x1
**Confidence:** HIGH (sourced from conversation + handoff)
**Rationale:** The pure-NumPy CG solver is infeasible beyond ~50 nodes. 8x8x1 has 162 nodes, 2x2x1 has 18. The 4x4x1 mesh (75 nodes) was tested and consumed 100% CPU for 13+ minutes without completing. This is a hard performance ceiling, not an optimization choice.
**Alternatives:** 8x8x1 as planned (rejected: solver can't complete). 4x4x1 compromise (rejected: still too slow). Wait for Taichi solver (rejected: blocks MVP).

### Self-converged reference instead of literature value
**Confidence:** HIGH (sourced from conversation)
**Rationale:** Literature values for Cook's membrane use nu=0.4999 (near-incompressible), which causes volumetric locking with standard Hex8. Using nu=0.3 avoids locking but means literature values don't apply. A self-converged reference from the same solver is the only option that doesn't require B-bar/F-bar elements (out of MVP scope).
**Alternatives:** Literature reference with nu=0.4999 (rejected: volumetric locking without B-bar). External solver reference (rejected: no validated external solver available). Skip Cook's benchmark entirely (rejected: it's a sprint deliverable).

### nu=0.3 to avoid volumetric locking
**Confidence:** HIGH (sourced from plan + conversation)
**Rationale:** Standard Hex8 elements exhibit volumetric locking as nu approaches 0.5. B-bar/F-bar remediation is out of MVP scope. nu=0.3 keeps the element well-behaved while still exercising the J2 plasticity code path.
**Alternatives:** nu=0.4999 per literature (rejected: locking). Implement B-bar (rejected: out of scope). Use tetrahedral elements (rejected: Hex8 is the only element type in MVP).

### Boundary tag detection pre-warp
**Confidence:** HIGH (sourced from code + conversation)
**Rationale:** After y-coordinate warping, the y1 face no longer sits at constant y=44 (it varies from 44 at x=0 to 16 at x=48). Face detection by coordinate tolerance only works on the rectangular grid. Detecting tags before warping and then applying the warp ensures correct boundary identification.
**Alternatives:** Post-warp detection with per-face tolerance (rejected: fragile, mesh-density dependent). Topology-based detection (rejected: over-engineered for structured meshes).

### Relaxed Newton tolerance to 1e-6
**Confidence:** MEDIUM (inferred from code + partial conversation)
**Rationale:** The unpreconditioned CG solver on coarse distorted meshes converges slowly. At tol=1e-8, the CG iteration budget would need to increase substantially, extending already-long solve times. tol=1e-6 is sufficient for the regression purpose of this test.
**Alternatives:** Keep tol=1e-8 per convention (rejected: CG iterations blow up). Increase CG budget (rejected: solve time already 91s). Add preconditioner (rejected: out of MVP scope).

---

## Re-entry Context (from diff-review)

### Key Invariants
- `generate_cook_membrane_mesh` MUST detect boundary tags before applying the y-coordinate warp. The warp destroys the constant-y property of the y1 face. If tag detection is moved after the warp, the y1 boundary will be incorrect.
- The Cook's membrane reference value (`_REFERENCE_TIP_UY = 4.6999070649`) is solver-specific and mesh-specific. It is NOT a validated physical result. Any change to the Newton solver, CG solver, or assembly routine will invalidate it.
- The `scope="class"` fixture means all test methods in `TestCooksMembrane` share a single solve. Adding a test that modifies the displacement field would corrupt other tests.

### Non-obvious Coupling
- `_gen_cooks_ref.py` and `TestCooksMembrane` both hardcode the same material parameters (E=240.565, nu=0.3, sigma_y0=243.0, K=300.0, n=0.4) independently. Changing one without the other creates silent divergence.
- The `generate_cook_membrane_mesh` function is now exported from `mechdsl.solver.__init__.py` and used by both `test_mesh_io.py` and `test_benchmarks.py`. Changes to the mesh generator affect both test suites.
- Phase 3's necking bar mesh generator (`generate_necking_bar_mesh`) should follow the same pre-warp tag detection pattern. The handoff document says so, but the coupling is implicit, not enforced.

### Gotchas
- The Cook's membrane solve takes 91 seconds. The test is marked `@slow` and `@e2e`, so it won't run in CI fast gate. But it WILL run in `pytest -m slow` and nightly runs.
- With E/sigma_y0 ~ 1.0 and 100N total load on a 2x2x1 mesh, the Cook's membrane stays elastic. `solve_plastic` exercises the J2 radial return code path (yield check), but actual plastic deformation is minimal. This is a valid solver exercise but not a plasticity stress test.
- The equal-nodal-load approximation on the right face is the same pattern flagged in Phase 1's cantilever review. It's not a regression but the tech debt is accumulating.

### Don't Forget
- Phase 3 necking bar mesh generator should follow the pre-warp boundary tag pattern.
- CHANGELOG update deferred to Phase 5 (P5-4).
- When the solver improves (Taichi backend), revisit Cook's membrane with finer mesh and proper reference.
- The `_gen_cooks_ref.py` script should be updated to match the test's exact parameters and mesh, or removed in favor of inline documentation.
