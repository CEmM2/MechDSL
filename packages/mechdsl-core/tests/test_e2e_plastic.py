"""J2 plasticity end-to-end Taichi execution tests.

Covers tasks P4-T5 (E2E plastic solver), P4-T6 (generated vs reference),
and P4-T2 (FD tangent alpha-corruption verification at emission level).
Pattern follows test_e2e_taichi.py elastic structure with history management.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import pytest

if TYPE_CHECKING:
    from pathlib import Path

from mechdsl.codegen import compile as mechdsl_compile
from mechdsl.ir.mechanics_ir import (
    BCType,
    BoundaryCondition,
    ElementType,
    Formulation,
    MaterialSpec,
    ProblemIR,
)
from mechdsl.solver.import_adapter import CGSolver
from tests._e2e_helpers import _import_generated_module
from tests.ref.ref_hex8_elastic import generate_hex8_mesh

pytestmark = pytest.mark.from_problem_ir

# ---------------------------------------------------------------------------
# Material parameters
# ---------------------------------------------------------------------------

E_YOUNG = 200.0e3
NU = 0.3
SIGMA_Y0 = 200.0
K_HARD = 100.0
N_HARD = 0.3
LAM = E_YOUNG * NU / ((1 + NU) * (1 - 2 * NU))
MU = E_YOUNG / (2 * (1 + NU))

# ---------------------------------------------------------------------------
# Helpers (following test_e2e_taichi.py pattern)
# ---------------------------------------------------------------------------


def _make_j2_problem_ir() -> ProblemIR:
    """Create J2 power-law plasticity ProblemIR for E2E test."""
    return ProblemIR(
        dim=3,
        formulation=Formulation.TOTAL_LAGRANGIAN,
        element_type=ElementType.HEX8,
        material=MaterialSpec(
            model="j2_power_law",
            params={
                "E": E_YOUNG,
                "nu": NU,
                "sigma_y0": SIGMA_Y0,
                "K": K_HARD,
                "n": N_HARD,
            },
        ),
        boundaries=(
            BoundaryCondition(name="fix", bc_type=BCType.DIRICHLET),
            BoundaryCondition(name="load", bc_type=BCType.NEUMANN, traction="t_bar"),
        ),
    )


def _load_mesh_into_module(mod, coords: np.ndarray, conn: np.ndarray) -> None:
    """Allocate Taichi fields and load mesh data into the generated module."""
    n_nodes = coords.shape[0]
    n_elem = conn.shape[0]

    mod.allocate_fields(n_nodes, n_elem)
    mod.x_ref.from_numpy(coords)

    # Load connectivity element-by-element (elem_nodes is a 2D ti.field)
    for e in range(n_elem):
        for a in range(8):
            mod.elem_nodes[e, a] = int(conn[e, a])


def _newton_with_bc_plastic(
    mod,
    coords: np.ndarray,
    bc_mask: np.ndarray,
    f_ext: np.ndarray,
    lam: float,
    mu: float,
    sigma_y0: float,
    K_hard: float,
    n_hard: float,
    tol: float = 1e-8,
    max_iter: int = 50,
) -> tuple[np.ndarray, list[float]]:
    """Run Newton-Raphson with alpha save/restore for J2 plasticity.

    The generated code overwrites alpha[e,q] in-place during every
    compute_internal_force call. We must save alpha at step start and
    restore before every residual evaluation to keep the history consistent.
    """
    n_nodes = coords.shape[0]
    n_dof = n_nodes * 3
    bc_flat = bc_mask.ravel()

    u = mod.u.to_numpy()
    alpha_snapshot = mod.alpha.to_numpy().copy()  # save alpha at step start
    cg = CGSolver()
    residual_history: list[float] = []
    R0_norm: float | None = None

    for newton_iter in range(max_iter):
        # Restore alpha before EVERY residual evaluation
        mod.alpha.from_numpy(alpha_snapshot)
        mod.u.from_numpy(u)
        mod.compute_internal_force(lam, mu, sigma_y0, K_hard, n_hard)
        f_int = mod.f_int.to_numpy()

        R = f_ext - f_int
        R[bc_mask] = 0.0
        R_flat = R.ravel()
        R_norm = float(np.linalg.norm(R_flat))
        residual_history.append(R_norm)

        if newton_iter == 0:
            R0_norm = R_norm
            if R0_norm < 1e-15:
                break

        assert R0_norm is not None
        if R_norm < tol * R0_norm:
            break

        # tangent_matvec handles its own alpha save/restore internally
        def matvec(v_flat: np.ndarray, _u: np.ndarray = u) -> np.ndarray:
            v = v_flat.copy()
            v[bc_flat] = 0.0
            mod.u.from_numpy(_u)
            Kv = mod.tangent_matvec(v, lam, mu, sigma_y0, K_hard, n_hard)
            Kv[bc_flat] = v_flat[bc_flat]
            return Kv

        du_flat, _, _ = cg.solve(matvec, R_flat, np.zeros(n_dof, dtype=np.float64), 1e-10, 2000)
        du = du_flat.reshape((n_nodes, 3))
        du[bc_mask] = 0.0
        u = u + du
    else:
        # Restore alpha on failure
        mod.alpha.from_numpy(alpha_snapshot)
        raise RuntimeError(
            f"Newton did not converge after {max_iter} iters. Final |R|={residual_history[-1]:.3e}"
        )

    # On convergence: run one final compute_internal_force to get correct alpha
    mod.alpha.from_numpy(alpha_snapshot)
    mod.u.from_numpy(u)
    mod.compute_internal_force(lam, mu, sigma_y0, K_hard, n_hard)

    mod.u.from_numpy(u)
    return u, residual_history


def _setup_unit_cube_mesh():
    """Create 1-element unit cube mesh with BCs."""
    coords, conn = generate_hex8_mesh(1, 1, 1, 1.0, 1.0, 1.0)
    n_nodes = coords.shape[0]

    # Identify boundary nodes
    left_nodes = np.where(np.abs(coords[:, 0]) < 1e-12)[0]
    right_nodes = np.where(np.abs(coords[:, 0] - 1.0) < 1e-12)[0]

    # BC mask: fix left face (all DOFs)
    bc_mask = np.zeros((n_nodes, 3), dtype=bool)
    bc_mask[left_nodes, :] = True

    return coords, conn, n_nodes, left_nodes, right_nodes, bc_mask


def _run_load_stepping(
    mod,
    coords: np.ndarray,
    bc_mask: np.ndarray,
    right_nodes: np.ndarray,
    total_disp: float,
    n_steps: int,
) -> tuple[np.ndarray, list[list[float]], list[np.ndarray]]:
    """Run displacement-controlled load stepping through the J2 module.

    For displacement-controlled loading, the right face x-DOFs are prescribed
    (not free). The BC mask must include both fixed DOFs (left face, all
    components) and prescribed DOFs (right face, x-component only).

    Returns
    -------
    u : final displacement field
    all_residuals : residual history for each load step
    alpha_history : alpha snapshots after each converged step
    """
    n_nodes = coords.shape[0]

    # Build augmented BC mask: fixed left face + prescribed right face x-DOF
    bc_mask_disp = bc_mask.copy()
    bc_mask_disp[right_nodes, 0] = True  # prescribed x-displacement on right face

    # Initialise displacement to zero
    u = np.zeros((n_nodes, 3), dtype=np.float64)
    mod.u.from_numpy(u)

    all_residuals: list[list[float]] = []
    alpha_history: list[np.ndarray] = []

    for step in range(1, n_steps + 1):
        fraction = step / n_steps

        # Set prescribed displacement on right face (x-direction)
        u[right_nodes, 0] = fraction * total_disp
        # Ensure left face stays fixed
        left_nodes = np.where(np.abs(coords[:, 0]) < 1e-12)[0]
        u[left_nodes, :] = 0.0

        mod.u.from_numpy(u)

        # External force = 0 for displacement-controlled loading
        f_ext = np.zeros((n_nodes, 3), dtype=np.float64)

        # Solve this load step
        u, residuals = _newton_with_bc_plastic(
            mod,
            coords,
            bc_mask_disp,
            f_ext,
            LAM,
            MU,
            SIGMA_Y0,
            K_HARD,
            N_HARD,
        )

        all_residuals.append(residuals)
        alpha_history.append(mod.alpha.to_numpy().copy())

    return u, all_residuals, alpha_history


class TestTaskP4T5:
    """E2E J2 plasticity Taichi execution tests.

    Tests for Task P4-T5: Create test_e2e_plastic.py
    Acceptance criteria covered: AC1-AC5
    Material params: sigma_y0=200, K=100, n=0.3, E=200e3, nu=0.3
    """

    @pytest.mark.slow
    @pytest.mark.e2e
    def test_j2_compiles_under_taichi_jit(self, tmp_path: Path):
        """Verifies: Generated J2 code compiles and executes under Taichi JIT.

        Acceptance criterion: Generated J2 code compiles under Taichi JIT without error
        Passes when: ti.init() + field allocation + one kernel call succeeds
        """
        # 1. Compile ProblemIR -> emitted source
        bundle = mechdsl_compile(_make_j2_problem_ir())
        assert bundle.emitted_source, "compile() returned empty source"

        # 2. Import generated module (triggers Taichi JIT)
        mod = _import_generated_module(bundle.emitted_source, tmp_path, "gen_j2_e2e")

        # 3. Verify key attributes exist
        assert hasattr(mod, "compute_internal_force")
        assert hasattr(mod, "tangent_matvec")
        assert hasattr(mod, "alpha")
        assert hasattr(mod, "allocate_fields")

        # 4. Allocate fields and do one forward call
        coords, conn = generate_hex8_mesh(1, 1, 1, 1.0, 1.0, 1.0)
        _load_mesh_into_module(mod, coords, conn)

        u_zero = np.zeros((coords.shape[0], 3), dtype=np.float64)
        mod.u.from_numpy(u_zero)

        # One forward call should not raise
        mod.compute_internal_force(LAM, MU, SIGMA_Y0, K_HARD, N_HARD)

        # Internal force at zero displacement should be zero
        f_int = mod.f_int.to_numpy()
        assert float(np.max(np.abs(f_int))) < 1e-12, (
            f"f_int at zero displacement should be zero, got max|f_int|={np.max(np.abs(f_int)):.3e}"
        )

        # Alpha should remain zero at zero deformation
        alpha_val = mod.alpha.to_numpy()
        assert float(np.max(np.abs(alpha_val))) < 1e-15, "alpha should be zero at zero deformation"

    @pytest.mark.slow
    @pytest.mark.e2e
    def test_below_yield_elastic_stress(self, tmp_path: Path):
        """Verifies: Below yield point, stress matches elastic reference.

        Acceptance criterion: Below yield stress matches elastic (within FD tolerance)
        Passes when: max |f_int_j2 - f_int_elastic_ref| < 1e-8 (relative)
        """
        from tests.ref.ref_hex8_elastic import assemble_internal_force as ref_assemble

        # Compile J2 module
        bundle = mechdsl_compile(_make_j2_problem_ir())
        mod = _import_generated_module(bundle.emitted_source, tmp_path, "gen_j2_below")

        # Setup mesh
        coords, conn, _n_nodes, _left_nodes, right_nodes, _bc_mask = _setup_unit_cube_mesh()
        n_nodes = coords.shape[0]

        _load_mesh_into_module(mod, coords, conn)

        # Apply a very small displacement that keeps stress well below yield
        # For SVK uniaxial tension: sigma_xx ~ E * eps (small strain)
        # sigma_y0 = 200 => eps_yield ~ 200/200e3 = 0.001
        # Use eps = 1e-5 (factor 100 below yield)
        small_disp = 1e-5
        u = np.zeros((n_nodes, 3), dtype=np.float64)
        u[right_nodes, 0] = small_disp

        # J2 module (generated Taichi): set displacement and compute internal force
        mod.u.from_numpy(u)
        mod.compute_internal_force(LAM, MU, SIGMA_Y0, K_HARD, N_HARD)
        f_int_j2 = mod.f_int.to_numpy()

        # Reference elastic internal force (pure numpy, no Taichi)
        f_int_el = ref_assemble(u, coords, conn, LAM, MU)

        # Below yield, J2 should match elastic exactly
        max_diff = float(np.max(np.abs(f_int_j2 - f_int_el)))
        f_norm = float(np.max(np.abs(f_int_el)))
        rel_diff = max_diff / f_norm if f_norm > 1e-15 else max_diff

        assert rel_diff < 1e-8, (
            f"Below yield, J2 should match elastic. "
            f"Relative diff = {rel_diff:.3e}, abs diff = {max_diff:.3e}"
        )

        # Alpha should remain zero (no plasticity triggered)
        alpha_val = mod.alpha.to_numpy()
        assert float(np.max(np.abs(alpha_val))) < 1e-15, "alpha should be zero below yield"

    @pytest.mark.slow
    @pytest.mark.e2e
    def test_above_yield_hardening_response(self, tmp_path: Path):
        """Verifies: Above yield, stress follows hardening law.

        Acceptance criterion: Above yield stress follows hardening law
        Passes when: alpha > 0 and stress < pure elastic prediction
        """
        bundle = mechdsl_compile(_make_j2_problem_ir())
        mod = _import_generated_module(bundle.emitted_source, tmp_path, "gen_j2_above")

        coords, conn, _n_nodes, _left_nodes, right_nodes, bc_mask = _setup_unit_cube_mesh()
        _load_mesh_into_module(mod, coords, conn)

        # Use displacement large enough to exceed yield
        # eps_yield ~ sigma_y0 / E = 200/200e3 = 0.001
        # Use total_disp = 0.01 (10x yield strain) over 5 steps
        total_disp = 0.01
        n_steps = 5

        u, _all_residuals, alpha_history = _run_load_stepping(
            mod,
            coords,
            bc_mask,
            right_nodes,
            total_disp,
            n_steps,
        )

        # Verify plastic deformation occurred: alpha > 0
        max_alpha = float(np.max(alpha_history[-1]))
        assert max_alpha > 1e-6, (
            f"Expected plastic deformation (alpha > 0) after loading past yield. "
            f"Got max alpha = {max_alpha:.3e}"
        )

        # Compare against pure elastic prediction using reference solver:
        # For elastic: f_int at the same displacement would be larger
        # because plasticity reduces the effective stiffness
        from tests.ref.ref_hex8_elastic import assemble_internal_force as ref_assemble

        f_int_elastic = ref_assemble(u, coords, conn, LAM, MU)

        # J2 internal force at converged state
        f_int_j2 = mod.f_int.to_numpy()

        # Reaction force magnitude on right face (x-direction)
        rx_j2 = float(np.sum(np.abs(f_int_j2[right_nodes, 0])))
        rx_el = float(np.sum(np.abs(f_int_elastic[right_nodes, 0])))

        assert rx_j2 < rx_el, (
            f"Plastic reaction ({rx_j2:.3e}) should be less than elastic ({rx_el:.3e}) "
            f"because plasticity reduces effective stiffness"
        )

        # Solution should be non-trivial
        assert float(np.max(np.abs(u))) > 1e-6, "Solution is trivially zero"

    @pytest.mark.slow
    @pytest.mark.e2e
    def test_return_mapping_residual(self, tmp_path: Path):
        """Verifies: Return mapping yields f(sigma^{n+1}) approx 0 to machine precision.

        Acceptance criterion: Return mapping residual approx 0
        Passes when: |f_yield| < 1e-6 after each converged load step
        """
        from mechdsl.lib.tensor_ops import deformation_gradient, green_lagrange
        from mechdsl.symbolic.models.j2_power_law import J2PowerLawMaterial, radial_return

        bundle = mechdsl_compile(_make_j2_problem_ir())
        mod = _import_generated_module(bundle.emitted_source, tmp_path, "gen_j2_rm")

        coords, conn, _n_nodes, _left_nodes, right_nodes, bc_mask = _setup_unit_cube_mesh()
        _load_mesh_into_module(mod, coords, conn)

        total_disp = 0.01
        n_steps = 5

        u, _all_residuals, alpha_history = _run_load_stepping(
            mod,
            coords,
            bc_mask,
            right_nodes,
            total_disp,
            n_steps,
        )

        # Now verify the return mapping residual using the reference material
        mat = J2PowerLawMaterial(
            E=E_YOUNG,
            nu=NU,
            sigma_y0=SIGMA_Y0,
            K=K_HARD,
            n=N_HARD,
        )

        # For the converged state, compute stress at each quad point
        # and check the yield function residual
        from mechdsl.ir.element_ir import hex8_basis, hex8_quadrature

        basis = hex8_basis()
        quad = hex8_quadrature()

        for e in range(conn.shape[0]):
            nodes = conn[e]
            u_elem = u[nodes]
            X_elem = coords[nodes]

            for q in range(quad.n_points):
                xi, eta, zeta = quad.points[q]
                dN_dxi = basis.gradient(xi, eta, zeta)
                J0 = X_elem.T @ dN_dxi
                J0_inv = np.linalg.inv(J0)
                dN_dX = dN_dxi @ J0_inv

                grad_u = u_elem.T @ dN_dX
                F = deformation_gradient(grad_u)
                E_strain = green_lagrange(F)

                # Use alpha from the PREVIOUS step as input to return mapping
                # For the last step, alpha_old = alpha from step n_steps-1
                alpha_old = float(alpha_history[-2][e, q]) if n_steps > 1 else 0.0

                result = radial_return(mat, E_strain, alpha_old)

                # If plastic (alpha increased), check yield function residual
                if result.alpha_new > alpha_old + 1e-15:
                    S = result.stress
                    # Compute deviatoric PK2 and von Mises equivalent
                    tr_S = float(np.trace(S))
                    S_dev = S - (tr_S / 3.0) * np.eye(3)
                    sigma_eq = float(np.sqrt(1.5 * np.sum(S_dev * S_dev)))
                    sigma_y = SIGMA_Y0 + K_HARD * result.alpha_new**N_HARD
                    f_yield = sigma_eq - sigma_y

                    assert abs(f_yield) < 1e-6, (
                        f"Yield function residual too large at e={e}, q={q}: "
                        f"f={f_yield:.3e}, sigma_eq={sigma_eq:.3e}, "
                        f"sigma_y={sigma_y:.3e}"
                    )

    @pytest.mark.slow
    @pytest.mark.e2e
    def test_load_stepping_no_divergence(self, tmp_path: Path):
        """Verifies: Load stepping past yield completes without divergence.

        Acceptance criterion: Load stepping completes without divergence
        Passes when: all N load steps converge within max_iter Newton iterations
        """
        bundle = mechdsl_compile(_make_j2_problem_ir())
        mod = _import_generated_module(bundle.emitted_source, tmp_path, "gen_j2_ls")

        coords, conn, _n_nodes, _left_nodes, right_nodes, bc_mask = _setup_unit_cube_mesh()
        _load_mesh_into_module(mod, coords, conn)

        total_disp = 0.01
        n_steps = 5

        # This should not raise RuntimeError (no divergence)
        u, all_residuals, alpha_history = _run_load_stepping(
            mod,
            coords,
            bc_mask,
            right_nodes,
            total_disp,
            n_steps,
        )

        # Verify all steps converged
        assert len(all_residuals) == n_steps, (
            f"Expected {n_steps} load steps, got {len(all_residuals)}"
        )

        # Verify each step actually converged (final residual < tol * initial)
        for step_idx, step_res in enumerate(all_residuals):
            if len(step_res) > 1 and step_res[0] > 1e-15:
                ratio = step_res[-1] / step_res[0]
                assert ratio < 1e-6, (
                    f"Step {step_idx + 1} did not converge well: "
                    f"R_final/R_0 = {ratio:.3e}, "
                    f"residuals = {[f'{r:.3e}' for r in step_res]}"
                )

        # Verify monotonic alpha increase across load steps
        for step_idx in range(1, len(alpha_history)):
            alpha_prev = alpha_history[step_idx - 1]
            alpha_curr = alpha_history[step_idx]
            # Alpha should be non-decreasing (monotonic loading)
            assert float(np.min(alpha_curr - alpha_prev)) >= -1e-12, (
                f"Alpha decreased between steps {step_idx} and {step_idx + 1}: "
                f"min(delta_alpha) = {float(np.min(alpha_curr - alpha_prev)):.3e}"
            )

        # Verify solution is non-trivial
        assert float(np.max(np.abs(u))) > 1e-6, "Solution is trivially zero"

        # Verify final alpha > 0 (plastic deformation occurred)
        assert float(np.max(alpha_history[-1])) > 1e-6, (
            "Expected plastic deformation after loading past yield"
        )


class TestTaskP4T6:
    """Generated vs reference J2 solver comparison.

    Tests for Task P4-T6: Compare generated vs reference
    Acceptance criteria covered: displacement error < 1e-10, same problem setup
    """

    @pytest.mark.slow
    @pytest.mark.e2e
    def test_generated_vs_reference_displacement(self, tmp_path: Path):
        """Verifies: Generated J2 solver matches ref_hex8_plastic on same problem.

        Acceptance criterion: Displacement error < 1e-10 (or documented relaxed tolerance)
        Passes when: max |u_generated - u_reference| < tolerance

        Tolerance rationale: Both solvers use displacement-controlled loading on
        the same 1-element mesh with identical material parameters. The generated
        solver uses an FD tangent (h=1e-7 central difference) while the reference
        uses a consistent algorithmic tangent, but both converge to the same
        equilibrium state within Newton tolerance. Observed max displacement
        difference is ~1e-16 (machine epsilon), so the strict 1e-10 tolerance
        from 07-CONVENTIONS.md is easily met.
        """
        from mechdsl.symbolic.models.j2_power_law import J2PowerLawMaterial
        from tests.ref.ref_hex8_plastic import solve_plastic

        # --- Problem setup (identical for both solvers) ---
        total_disp = 0.01  # 10x yield strain => well into plastic regime
        n_steps = 5

        # Material
        mat = J2PowerLawMaterial(
            E=E_YOUNG,
            nu=NU,
            sigma_y0=SIGMA_Y0,
            K=K_HARD,
            n=N_HARD,
        )

        # Mesh: single unit cube element
        coords, conn, n_nodes, _left_nodes, right_nodes, bc_mask = _setup_unit_cube_mesh()

        # --- Run generated solver ---
        bundle = mechdsl_compile(_make_j2_problem_ir())
        mod = _import_generated_module(bundle.emitted_source, tmp_path, "gen_j2_vs_ref")
        _load_mesh_into_module(mod, coords, conn)

        u_gen, _gen_residuals, _gen_alpha = _run_load_stepping(
            mod,
            coords,
            bc_mask,
            right_nodes,
            total_disp,
            n_steps,
        )

        # --- Run reference solver ---
        # Build bc_mask for reference: fixed left face + prescribed right face x-DOF
        bc_mask_ref = bc_mask.copy()
        bc_mask_ref[right_nodes, 0] = True

        # bc_values: full-load prescribed displacements (reference scales internally)
        bc_values_ref = np.zeros((n_nodes, 3), dtype=np.float64)
        bc_values_ref[right_nodes, 0] = total_disp

        # External force = 0 for displacement-controlled loading
        f_ext_ref = np.zeros((n_nodes, 3), dtype=np.float64)

        u_ref, _ref_history, _ref_residuals = solve_plastic(
            coords,
            conn,
            mat,
            bc_mask_ref,
            bc_values_ref,
            f_ext_ref,
            n_steps=n_steps,
            tol=1e-8,
            max_iter=50,
        )

        # --- Compare ---
        max_diff = float(np.max(np.abs(u_gen - u_ref)))

        # Strict tolerance per 07-CONVENTIONS.md (generated vs reference < 1e-10).
        # Observed difference is ~1e-16 (machine epsilon).
        tolerance = 1e-10

        assert max_diff < tolerance, (
            f"Generated vs reference displacement mismatch: "
            f"max |u_gen - u_ref| = {max_diff:.3e}, tolerance = {tolerance:.3e}."
        )


class TestTaskP4T2E2E:
    """Analytical J2 tangent alpha-preservation verification at emission level.

    History: the original P4-T2 task verified that the finite-difference
    tangent saved and restored ``alpha`` around each FD perturbation.
    PLAN-A §A9.2 replaced the FD tangent with the analytical consistent
    algorithmic tangent (via a per-quadrature-point ``radial_return`` call),
    so alpha preservation is now achieved by construction: the matvec only
    *reads* the alpha field and never writes it back.  This test was
    rewritten to enforce that non-mutation invariant directly.
    """

    def test_analytical_tangent_preserves_alpha_e2e(self):
        """Emitted J2 tangent_matvec reads alpha once and never mutates it.

        Acceptance criterion: alpha corruption impossible by construction.
        Passes when: (1) the matvec snapshots the alpha field via
        ``alpha.to_numpy()``, (2) it never writes to the field via
        ``alpha.from_numpy(...)``, and (3) it does not invoke the residual
        kernel ``compute_internal_force`` at all — the analytical path is a
        single-shot linearisation.
        """
        from mechdsl.codegen import compile as mechdsl_compile
        from mechdsl.ir.mechanics_ir import (
            BCType,
            BoundaryCondition,
            ElementType,
            Formulation,
            MaterialSpec,
            ProblemIR,
        )

        problem_ir = ProblemIR(
            dim=3,
            formulation=Formulation.TOTAL_LAGRANGIAN,
            element_type=ElementType.HEX8,
            material=MaterialSpec(
                model="j2_power_law",
                params={
                    "E": 200e3,
                    "nu": 0.3,
                    "sigma_y0": 200.0,
                    "K": 100.0,
                    "n": 0.3,
                },
            ),
            boundaries=(
                BoundaryCondition(name="fix", bc_type=BCType.DIRICHLET),
                BoundaryCondition(name="load", bc_type=BCType.NEUMANN, traction="t_bar"),
            ),
        )
        bundle = mechdsl_compile(problem_ir)
        source = bundle.emitted_source

        # Isolate the tangent_matvec function body for targeted assertions.
        assert "def tangent_matvec(" in source, (
            "tangent_matvec function not found in emitted J2 source"
        )
        start = source.index("def tangent_matvec(")
        rest = source[start:]
        next_boundary = len(rest)
        for marker in ("\ndef ", "\nclass ", "\n@ti.kernel"):
            idx = rest.find(marker, 1)
            if idx != -1 and idx < next_boundary:
                next_boundary = idx
        matvec_body = rest[:next_boundary]

        # 1. Alpha is read once via a NumPy snapshot.
        assert "alpha_np = alpha.to_numpy()" in matvec_body, (
            "Analytical J2 tangent must snapshot the alpha field."
        )

        # 2. Alpha is never written back — the analytical path is non-mutating.
        assert "alpha.from_numpy" not in matvec_body, (
            "Analytical J2 tangent must not write alpha back to the Taichi field."
        )
        assert "alpha_save" not in matvec_body, (
            "FD save/restore pattern should be absent from the analytical tangent."
        )

        # 3. The analytical tangent does not invoke the residual kernel at all.
        assert "compute_internal_force(" not in matvec_body, (
            "Analytical tangent_matvec must not call compute_internal_force."
        )
        assert "FD_EPS" not in matvec_body, "FD_EPS must not appear in the analytical tangent body."

        # 4. The consistent algorithmic tangent is obtained via radial_return.
        assert "from mechdsl.symbolic.models.j2_power_law import" in matvec_body, (
            "Analytical J2 tangent must import radial_return from the symbolic model."
        )
        assert "radial_return(_j2_mat, E, float(alpha_np[e, q]))" in matvec_body, (
            "Analytical J2 tangent must call radial_return per quadrature point "
            "to obtain the consistent algorithmic tangent."
        )
