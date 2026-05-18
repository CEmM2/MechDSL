# Phase 3 Context Summary — Verification Infrastructure

## Conventions
- **Convergence rate**: for Hex8 (p=1), expected L2 rate ≥ p+1 = 2.0, H1 rate ≥ p = 1.0 (08-VERIFICATION.md §4.2)
- **Rate tolerance**: 0.1 (i.e., L2 rate ≥ 1.9, H1 rate ≥ 0.9 is acceptable)
- **MMS body force**: b* = -Div(P*) where P* = F*·S* (first Piola-Kirchhoff)
- **SVK constitutive**: S = λ·tr(E)·I + 2μ·E where E = 0.5*(C - I), C = F^T·F
- **Patch test tolerance**: relative error < 1e-12
- **Rigid body tolerance**: internal force norm < 1e-12

## Key Principles
- MMS (Method of Manufactured Solutions) uses symbolic differentiation (SymPy) to compute manufactured body force
- The manufactured displacement u*(x) = A·sin(πx/L)·cos(πy/L)·sin(πz/L) is chosen to exercise all displacement gradient components
- Mesh refinement uses `generate_hex8_mesh(nx, ny, nz, Lx, Ly, Lz)` from `tests/ref/ref_hex8_elastic.py`
- Patch test uses irregular meshes (perturbed nodes) — limit perturbation to 10% of element size to avoid degenerate elements

## Pre-resolved Design Decisions
- **MMS uses ref solver, not generated solver**: the MMS test validates the *reference* implementation's convergence properties, not the generated code (generated code convergence is tested by E2E comparison)
- **3 mesh levels**: 2³, 4³, 8³ elements — keeps runtime reasonable for slow tests
- **ConvergenceResult dataclass**: contains measured_rate, expected_rate, passed flag, raw errors and mesh_sizes
- **PatchTestResult and RigidBodyResult dataclasses**: contain error values and pass/fail status
- **Patch test depends on Phase 2**: uses `analytical.patch_test_reference()` (P2-T1) and `analytical.rigid_body_reference()` (P2-T2)

## Downstream Impact
- **P3-T1 (check_convergence_rate)** → used by P3-T3 convergence test; could be reused in future convergence studies
- **P3-T4 (run_patch_test, run_rigid_body_test)** → used by P3-T5 patch test; validates fundamental correctness of solver
- **Phase 3 tests are all @pytest.mark.slow** — they involve solver execution (reference or generated)

## Key Files
- `packages/mechdsl-core/src/mechdsl/verify/convergence.py` — currently a 1-line stub
- `packages/mechdsl-core/src/mechdsl/verify/patch_test.py` — currently a 1-line stub
- `packages/mechdsl-core/tests/ref/ref_hex8_elastic.py` — generate_hex8_mesh() for mesh refinement
- `packages/mechdsl-core/src/mechdsl/verify/analytical.py` — from Phase 2, provides patch_test_reference and rigid_body_reference
