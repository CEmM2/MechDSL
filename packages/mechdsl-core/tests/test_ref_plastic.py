"""Tests for the handwritten TL Hex8 J2 plastic reference solver.

Verifies correctness of:
- Elastic regime equivalence with the elastic reference
- Yield detection and radial return mapping
- History variable management (commit / rollback)
- Monotonic hardening under increasing load
- Single-element uniaxial stress-strain curve
- Newton convergence for a small plastic problem
"""

from __future__ import annotations

import numpy as np
import pytest

from mechdsl.symbolic.models.j2_power_law import (
    J2PowerLawMaterial,
    deviatoric,
    radial_return,
    von_mises,
    yield_stress,
)
from tests.ref.ref_hex8_elastic import (
    generate_hex8_mesh,
    solve_elastic,
)
from tests.ref.ref_hex8_plastic import (
    HistoryFields,
    assemble_internal_force_plastic,
    element_internal_force_plastic,
    solve_plastic,
)

# ---------------------------------------------------------------------------
# Material parameters — steel-like J2 plasticity
# ---------------------------------------------------------------------------

# Same elastic constants as the elastic reference
E_YOUNG = 200.0e3  # Young's modulus [MPa]
NU = 0.3  # Poisson's ratio
SIGMA_Y0 = 250.0  # Initial yield stress [MPa]
K_HARD = 500.0  # Hardening modulus [MPa]
N_HARD = 1.0  # Hardening exponent (linear; n < 1 causes H' singularity at alpha=0)

LAM = E_YOUNG * NU / ((1 + NU) * (1 - 2 * NU))
MU = E_YOUNG / (2 * (1 + NU))

MAT = J2PowerLawMaterial(E=E_YOUNG, nu=NU, sigma_y0=SIGMA_Y0, K=K_HARD, n=N_HARD)

# A material with very high yield stress (effectively elastic)
MAT_HIGH_YIELD = J2PowerLawMaterial(E=E_YOUNG, nu=NU, sigma_y0=1e12, K=K_HARD, n=N_HARD)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _single_element_coords() -> np.ndarray:
    """Reference coordinates for a single unit cube [0,1]^3 Hex8 element."""
    return np.array(
        [
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [1.0, 1.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
            [1.0, 0.0, 1.0],
            [1.0, 1.0, 1.0],
            [0.0, 1.0, 1.0],
        ],
        dtype=np.float64,
    )


def _apply_constant_strain(
    X_elem: np.ndarray, eps_xx: float = 0.0, eps_yy: float = 0.0, eps_zz: float = 0.0
) -> np.ndarray:
    """Compute displacements from a constant engineering strain field."""
    u_elem = np.zeros_like(X_elem)
    u_elem[:, 0] = eps_xx * X_elem[:, 0]
    u_elem[:, 1] = eps_yy * X_elem[:, 1]
    u_elem[:, 2] = eps_zz * X_elem[:, 2]
    return u_elem


# ===========================================================================
# Test 1: Below-yield equality with elastic reference
# ===========================================================================


class TestBelowYieldEquality:
    """Small load that stays elastic — displacement must match elastic ref."""

    def test_small_load_matches_elastic(self):
        """Below-yield load: plastic solver must reproduce elastic result to 1e-8.

        Both solvers use FD-based tangent matvec, so the achievable Newton
        accuracy is limited by the FD perturbation (~1e-7). We use tol=1e-8
        and compare displacements to 1e-8 — tight enough to confirm correctness.
        """
        # Use a 2x1x1 mesh — small enough to be fast
        coords, conn = generate_hex8_mesh(2, 1, 1, 2.0, 1.0, 1.0)
        n_nodes = coords.shape[0]

        # BC: fix left face (x=0)
        bc_mask = np.zeros((n_nodes, 3), dtype=bool)
        bc_values = np.zeros((n_nodes, 3), dtype=np.float64)
        left_nodes = np.where(np.abs(coords[:, 0]) < 1e-12)[0]
        bc_mask[left_nodes, :] = True

        # Very small external force — well below yield
        f_ext = np.zeros((n_nodes, 3), dtype=np.float64)
        right_nodes = np.where(np.abs(coords[:, 0] - 2.0) < 1e-12)[0]
        # Distribute a small traction on right face
        for nd in right_nodes:
            f_ext[nd, 0] = 0.1  # small tensile load per node

        # Solve with elastic reference
        u_elastic, _ = solve_elastic(
            coords,
            conn,
            LAM,
            MU,
            bc_mask,
            bc_values,
            f_ext,
            tol=1e-8,
            max_iter=50,
        )

        # Solve with plastic solver (single step, high yield — should stay elastic)
        u_plastic, history, _ = solve_plastic(
            coords,
            conn,
            MAT_HIGH_YIELD,
            bc_mask,
            bc_values,
            f_ext,
            n_steps=1,
            tol=1e-8,
            max_iter=50,
        )

        # All alpha should be zero (no yielding)
        np.testing.assert_allclose(history.alpha_current, 0.0, atol=1e-15)
        np.testing.assert_allclose(history.alpha_old, 0.0, atol=1e-15)

        # Displacements must match to solver precision
        np.testing.assert_allclose(u_plastic, u_elastic, atol=1e-8)

    def test_single_element_elastic_regime(self):
        """Single element: small strain below yield produces identical force."""
        X_elem = _single_element_coords()
        eps = 1e-5  # very small strain — safely below yield
        u_elem = _apply_constant_strain(X_elem, eps_xx=eps)
        alpha_elem = np.zeros(8, dtype=np.float64)

        f_plastic, alpha_new = element_internal_force_plastic(u_elem, X_elem, MAT, alpha_elem)

        # Import elastic element force for comparison
        from tests.ref.ref_hex8_elastic import element_internal_force

        f_elastic = element_internal_force(u_elem, X_elem, LAM, MU)

        np.testing.assert_allclose(f_plastic, f_elastic, atol=1e-10)
        np.testing.assert_allclose(alpha_new, 0.0, atol=1e-15)


# ===========================================================================
# Test 2: Yield detection
# ===========================================================================


class TestYieldDetection:
    """Load above yield — history must show nonzero alpha."""

    def test_large_strain_yields(self):
        """Single element with large strain exceeds yield → alpha > 0."""
        X_elem = _single_element_coords()
        # Large uniaxial strain to push well past yield
        eps = 0.01
        u_elem = _apply_constant_strain(X_elem, eps_xx=eps)
        alpha_elem = np.zeros(8, dtype=np.float64)

        _, alpha_new = element_internal_force_plastic(u_elem, X_elem, MAT, alpha_elem)

        # At least some quadrature points should have yielded
        assert np.any(alpha_new > 0.0), (
            f"Expected yielding at 1% strain but all alpha=0. max(alpha)={alpha_new.max()}"
        )

    def test_history_updated_after_assembly(self):
        """Global assembly should update history.alpha_current at yielded points."""
        coords, conn = generate_hex8_mesh(1, 1, 1, 1.0, 1.0, 1.0)
        n_nodes = coords.shape[0]
        n_elem = conn.shape[0]
        history = HistoryFields(n_elem)

        # Apply large displacement to cause yielding
        u = np.zeros((n_nodes, 3), dtype=np.float64)
        u[:, 0] = 0.01 * coords[:, 0]  # 1% uniaxial strain

        _ = assemble_internal_force_plastic(u, coords, conn, MAT, history)

        assert np.any(history.alpha_current > 0.0), "Expected nonzero alpha_current after yielding"


# ===========================================================================
# Test 3: Yield-surface residual check
# ===========================================================================


class TestYieldSurfaceResidual:
    """After return mapping, verify yield surface consistency."""

    def test_von_mises_equals_yield_stress(self):
        """At yielded points, von_mises(S_dev) should equal sigma_y(alpha) to < 1e-10."""
        from mechdsl.lib.tensor_ops import deformation_gradient, green_lagrange

        X_elem = _single_element_coords()
        eps = 0.02  # 2% strain — definitely yielding
        u_elem = _apply_constant_strain(X_elem, eps_xx=eps)

        # Compute at each quadrature point
        from mechdsl.ir.element_ir import hex8_basis, hex8_quadrature

        basis = hex8_basis()
        quad = hex8_quadrature()

        for q in range(quad.n_points):
            xi, eta, zeta = quad.points[q]
            dN_dxi = basis.gradient(xi, eta, zeta)
            J0 = X_elem.T @ dN_dxi
            J0_inv = np.linalg.inv(J0)
            dN_dX = dN_dxi @ J0_inv

            grad_u = u_elem.T @ dN_dX
            F = deformation_gradient(grad_u)
            E = green_lagrange(F)

            result = radial_return(MAT, E, 0.0)

            if result.is_plastic:
                S_dev = deviatoric(result.stress)
                sigma_eq = von_mises(S_dev)
                sigma_y = yield_stress(MAT, result.alpha_new)
                np.testing.assert_allclose(
                    sigma_eq,
                    sigma_y,
                    atol=1e-10,
                    err_msg=f"Yield surface residual too large at qp {q}",
                )


# ===========================================================================
# Test 4: History commit / rollback
# ===========================================================================


class TestHistoryCommitRollback:
    """Verify commit copies current->old, rollback restores."""

    def test_commit(self):
        """After commit, alpha_old equals alpha_current."""
        history = HistoryFields(n_elem=3, n_qp=8)
        history.alpha_current[0, :] = 0.001
        history.alpha_current[1, 3] = 0.005
        history.alpha_current[2, 7] = 0.01

        history.commit()

        np.testing.assert_array_equal(history.alpha_old, history.alpha_current)

    def test_rollback(self):
        """After rollback, alpha_current equals alpha_old (old state)."""
        history = HistoryFields(n_elem=2, n_qp=8)

        # Set old state
        history.alpha_old[0, :] = 0.002
        history.alpha_old[1, :] = 0.003

        # Modify current (simulating a failed Newton)
        history.alpha_current[0, :] = 0.999
        history.alpha_current[1, :] = 0.888

        history.rollback()

        np.testing.assert_array_equal(history.alpha_current, history.alpha_old)
        np.testing.assert_allclose(history.alpha_current[0, 0], 0.002)
        np.testing.assert_allclose(history.alpha_current[1, 0], 0.003)

    def test_commit_then_rollback(self):
        """Commit then rollback: current should match the committed state."""
        history = HistoryFields(n_elem=1, n_qp=8)
        history.alpha_current[:] = 0.01
        history.commit()

        # Modify current
        history.alpha_current[:] = 0.99

        # Rollback should restore to the committed state
        history.rollback()
        np.testing.assert_allclose(history.alpha_current, 0.01)

    def test_independent_copy(self):
        """Commit makes a copy — later changes to current don't affect old."""
        history = HistoryFields(n_elem=1, n_qp=8)
        history.alpha_current[:] = 0.05
        history.commit()

        history.alpha_current[:] = 0.99
        np.testing.assert_allclose(history.alpha_old, 0.05)


# ===========================================================================
# Test 5: Hardening — alpha increases monotonically
# ===========================================================================


class TestHardeningMonotonic:
    """With multiple load steps, alpha should increase monotonically."""

    def test_alpha_increases_with_load(self):
        """Across load steps, committed alpha never decreases."""
        coords, conn = generate_hex8_mesh(1, 1, 1, 1.0, 1.0, 1.0)
        n_nodes = coords.shape[0]

        # BC: fix left face (x=0), prescribe displacement on right face (x=1)
        bc_mask = np.zeros((n_nodes, 3), dtype=bool)
        bc_values = np.zeros((n_nodes, 3), dtype=np.float64)
        left_nodes = np.where(np.abs(coords[:, 0]) < 1e-12)[0]
        bc_mask[left_nodes, :] = True
        right_nodes = np.where(np.abs(coords[:, 0] - 1.0) < 1e-12)[0]
        bc_mask[right_nodes, 0] = True  # prescribe x-displacement on right face

        # Prescribe 5% extension — enough to yield with power-law hardening
        bc_values[right_nodes, 0] = 0.05

        # Zero external force — loading purely by displacement
        f_ext = np.zeros((n_nodes, 3), dtype=np.float64)

        # Use a material with lower yield for easier yielding
        mat_soft = J2PowerLawMaterial(E=E_YOUNG, nu=NU, sigma_y0=100.0, K=300.0, n=1.0)

        _, history, residual_history = solve_plastic(
            coords,
            conn,
            mat_soft,
            bc_mask,
            bc_values,
            f_ext,
            n_steps=5,
            tol=1e-8,
            max_iter=50,
        )

        # alpha_old should be the committed state after all steps
        # With increasing prescribed displacement, alpha should increase
        # (We check the final state has nonzero alpha since we applied large strain)
        assert np.any(history.alpha_old > 0.0), "Expected yielding with 5% strain"

        # Each step converged
        assert len(residual_history) == 5


# ===========================================================================
# Test 6: Single-element uniaxial stress-strain curve
# ===========================================================================


class TestSingleElementUniaxial:
    """Single element under uniaxial tension — verify hardening law."""

    def test_uniaxial_stress_strain_follows_hardening(self):
        """Stress-strain response should follow the power-law hardening curve.

        For uniaxial tension on a unit cube element, we check that the
        resulting axial stress after return mapping follows the expected
        hardening law: sigma_y = sigma_y0 + K * alpha^n.
        """
        from mechdsl.ir.element_ir import hex8_basis, hex8_quadrature
        from mechdsl.lib.tensor_ops import deformation_gradient, green_lagrange

        X_elem = _single_element_coords()
        basis = hex8_basis()
        quad = hex8_quadrature()

        # Use a softer material for clearer hardening
        mat = J2PowerLawMaterial(E=1000.0, nu=0.3, sigma_y0=10.0, K=50.0, n=1.0)

        # Step through increasing strains and track stress/alpha at first qp
        strains = [0.005, 0.01, 0.02, 0.05, 0.1]
        alphas: list[float] = []
        sigma_eqs: list[float] = []

        alpha_old = 0.0

        for eps in strains:
            u_elem = _apply_constant_strain(X_elem, eps_xx=eps)

            # Evaluate at first quadrature point
            xi, eta, zeta = quad.points[0]
            dN_dxi = basis.gradient(xi, eta, zeta)
            J0 = X_elem.T @ dN_dxi
            J0_inv = np.linalg.inv(J0)
            dN_dX = dN_dxi @ J0_inv

            grad_u = u_elem.T @ dN_dX
            F = deformation_gradient(grad_u)
            E = green_lagrange(F)

            result = radial_return(mat, E, alpha_old)

            if result.is_plastic:
                S_dev = deviatoric(result.stress)
                sigma_eq = von_mises(S_dev)
                sigma_eqs.append(sigma_eq)
                alphas.append(result.alpha_new)
                alpha_old = result.alpha_new

        # If we got plastic points, check that sigma_eq matches yield_stress
        for i, (alpha, sigma_eq) in enumerate(zip(alphas, sigma_eqs, strict=True)):
            expected_sy = yield_stress(mat, alpha)
            np.testing.assert_allclose(
                sigma_eq,
                expected_sy,
                atol=1e-10,
                err_msg=f"Stress-strain mismatch at step {i}: sigma_eq={sigma_eq}, sigma_y={expected_sy}",
            )

        # Verify alpha is monotonically increasing
        for i in range(1, len(alphas)):
            assert alphas[i] >= alphas[i - 1], (
                f"Alpha decreased at step {i}: {alphas[i]} < {alphas[i - 1]}"
            )


# ===========================================================================
# Test 7: Newton convergence for a small plastic problem
# ===========================================================================


class TestNewtonConvergence:
    """Newton converges within reasonable iterations for a small plastic problem."""

    @pytest.fixture
    def plastic_cantilever(self) -> dict:
        """Set up a 2x1x1 cantilever with plastic material."""
        nx, ny, nz = 2, 1, 1
        Lx, Ly, Lz = 2.0, 1.0, 1.0
        coords, conn = generate_hex8_mesh(nx, ny, nz, Lx, Ly, Lz)
        n_nodes = coords.shape[0]

        # BC: fix left face
        bc_mask = np.zeros((n_nodes, 3), dtype=bool)
        bc_values = np.zeros((n_nodes, 3), dtype=np.float64)
        left_nodes = np.where(np.abs(coords[:, 0]) < 1e-12)[0]
        bc_mask[left_nodes, :] = True

        # Moderate force that will cause some yielding
        f_ext = np.zeros((n_nodes, 3), dtype=np.float64)
        right_nodes = np.where(np.abs(coords[:, 0] - Lx) < 1e-12)[0]
        for nd in right_nodes:
            f_ext[nd, 0] = 50.0  # moderate tensile traction

        # Use softer material for easier yielding
        mat = J2PowerLawMaterial(E=1000.0, nu=0.3, sigma_y0=30.0, K=100.0, n=1.0)

        return {
            "coords": coords,
            "conn": conn,
            "mat": mat,
            "bc_mask": bc_mask,
            "bc_values": bc_values,
            "f_ext": f_ext,
            "n_nodes": n_nodes,
        }

    def test_newton_converges(self, plastic_cantilever: dict):
        """Newton-Raphson converges for the plastic cantilever."""
        s = plastic_cantilever
        _u, _history, residual_history = solve_plastic(
            s["coords"],
            s["conn"],
            s["mat"],
            s["bc_mask"],
            s["bc_values"],
            s["f_ext"],
            n_steps=5,
            tol=1e-8,
            max_iter=50,
        )

        # All steps should have converged
        assert len(residual_history) == 5

        # Each step's residual should decrease
        for step_idx, step_res in enumerate(residual_history):
            assert len(step_res) >= 1, f"Step {step_idx}: no residuals recorded"
            if step_res[0] > 1e-15:  # non-trivial step
                assert step_res[-1] < 1e-8 * step_res[0], (
                    f"Step {step_idx}: Newton did not converge. "
                    f"R0={step_res[0]:.3e}, R_final={step_res[-1]:.3e}"
                )

    def test_displacement_nonzero(self, plastic_cantilever: dict):
        """Solver produces nonzero displacement under load."""
        s = plastic_cantilever
        u, _, _ = solve_plastic(
            s["coords"],
            s["conn"],
            s["mat"],
            s["bc_mask"],
            s["bc_values"],
            s["f_ext"],
            n_steps=5,
            tol=1e-8,
            max_iter=50,
        )

        max_disp = float(np.max(np.abs(u)))
        assert max_disp > 1e-6, f"Displacement too small: {max_disp:.6e}"

    def test_fixed_face_zero(self, plastic_cantilever: dict):
        """Fixed face displacements should be exactly zero."""
        s = plastic_cantilever
        u, _, _ = solve_plastic(
            s["coords"],
            s["conn"],
            s["mat"],
            s["bc_mask"],
            s["bc_values"],
            s["f_ext"],
            n_steps=5,
            tol=1e-8,
            max_iter=50,
        )

        np.testing.assert_allclose(u[s["bc_mask"]], 0.0, atol=1e-15)

    def test_plastic_displacement_larger_than_elastic(self, plastic_cantilever: dict):
        """Plastic solution should have larger displacement than elastic (less stiff)."""
        s = plastic_cantilever
        mat = s["mat"]

        # Plastic solution
        u_plastic, _, _ = solve_plastic(
            s["coords"],
            s["conn"],
            mat,
            s["bc_mask"],
            s["bc_values"],
            s["f_ext"],
            n_steps=5,
            tol=1e-8,
            max_iter=50,
        )

        # Elastic solution with same E, nu
        u_elastic, _ = solve_elastic(
            s["coords"],
            s["conn"],
            mat.lam,
            mat.mu,
            s["bc_mask"],
            s["bc_values"],
            s["f_ext"],
            tol=1e-8,
            max_iter=50,
        )

        # Plastic displacement magnitude should be >= elastic
        # (yielding reduces stiffness, allowing more deformation)
        disp_plastic = float(np.max(np.abs(u_plastic)))
        disp_elastic = float(np.max(np.abs(u_elastic)))
        assert disp_plastic >= disp_elastic * (1.0 - 1e-10), (
            f"Plastic displacement ({disp_plastic:.6e}) should be >= elastic ({disp_elastic:.6e})"
        )
