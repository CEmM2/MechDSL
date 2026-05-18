"""Task P1-7: TL/UL equivalence + rigid rotation tests.

Phase 1 exit criterion: "UL solver produces identical results to TL on
shared benchmarks. Objective rates verified via rigid rotation test."

Plan: dev/design_docs/PLAN-B.md lines 70-72 (B1 exit criterion).

Depends on: P1-1..P1-6 complete.
"""

from __future__ import annotations

import numpy as np
import pytest

from mechdsl.symbolic.objective_rates import (
    green_naghdi_rate,
    jaumann_rate,
    truesdell_rate,
)
from tests.ref.ref_hex8_elastic import generate_hex8_mesh, solve_elastic
from tests.ref.ref_hex8_ul import solve_elastic_ul

# ---------------------------------------------------------------------------
# Helpers for rigid rotation tests
# ---------------------------------------------------------------------------


def _rotation_matrix_z(theta: float) -> np.ndarray:
    """Rotation matrix about the z-axis by angle theta (radians)."""
    c, s = np.cos(theta), np.sin(theta)
    return np.array(
        [
            [c, -s, 0.0],
            [s, c, 0.0],
            [0.0, 0.0, 1.0],
        ],
        dtype=np.float64,
    )


def _spin_matrix_z(omega: float) -> np.ndarray:
    """Skew-symmetric spin tensor for rotation about z with angular rate omega."""
    return np.array(
        [
            [0.0, -omega, 0.0],
            [omega, 0.0, 0.0],
            [0.0, 0.0, 0.0],
        ],
        dtype=np.float64,
    )


def _rotating_sigma_dot(Omega: np.ndarray, sigma: np.ndarray) -> np.ndarray:
    """Exact material time derivative of sigma under rigid rotation.

    For a rigidly-rotating stress field sigma(t) = R(t) @ sigma_0 @ R(t).T:
        sigma_dot = Omega @ sigma + sigma @ Omega.T
    where Omega = R_dot @ R.T is the spin tensor.
    """
    result: np.ndarray = Omega @ sigma + sigma @ Omega.T
    return result


class TestTaskP1_7:
    """
    Tests for Task P1-7: TL/UL equivalence + rigid rotation tests

    Acceptance criteria covered:
      1. TL and UL converged displacements agree within 1e-8 on cantilever (slow)
      2. Rigid rotation Cauchy-rate test passes for all three objective rates
      3. Both tests correctly marked and collected by pytest
    """

    @pytest.mark.integration
    @pytest.mark.slow
    def test_tl_vs_ul_cantilever_equivalence(self) -> None:
        """TL and UL solvers produce identical cantilever displacements.

        Verifies: solving a Hex8 cantilever beam under both TL and UL
        formulations yields converged displacements that agree within
        1e-8 (quasi-static elastic problem is mathematically identical).

        Setup: 4x2x1 mesh, E=1000, nu=0.3, fixed left face, -10.0 point
        load in z at the right-top corner.

        Acceptance criterion: "TL and UL converged displacements agree
        within 1e-8 on the cantilever test."
        Passes when: numpy.allclose(u_tl, u_ul, atol=1e-8).
        """
        # --- Problem setup (shared between TL and UL) ---
        nx, ny, nz = 4, 2, 1
        Lx, Ly, Lz = 4.0, 2.0, 1.0
        coords, conn = generate_hex8_mesh(nx, ny, nz, Lx, Ly, Lz)
        n_nodes = coords.shape[0]

        # Material: softer for larger displacements on coarse mesh
        E_mod = 1000.0
        nu = 0.3
        lam = E_mod * nu / ((1 + nu) * (1 - 2 * nu))
        mu = E_mod / (2 * (1 + nu))

        # BC: fix all DOFs on left face (x=0)
        bc_mask = np.zeros((n_nodes, 3), dtype=bool)
        bc_values = np.zeros((n_nodes, 3), dtype=np.float64)
        left_nodes = np.where(np.abs(coords[:, 0]) < 1e-12)[0]
        bc_mask[left_nodes, :] = True

        # Load: downward point force on the right-top-back corner
        f_ext = np.zeros((n_nodes, 3), dtype=np.float64)
        right_top = np.where(
            (np.abs(coords[:, 0] - Lx) < 1e-12)
            & (np.abs(coords[:, 1] - Ly) < 1e-12)
            & (np.abs(coords[:, 2] - Lz) < 1e-12)
        )[0]
        assert len(right_top) == 1
        f_ext[right_top[0], 2] = -10.0

        tol = 1e-10
        max_iter = 50
        cg_tol = 1e-12
        cg_max_iter = 3000

        # --- Solve TL ---
        u_tl, res_tl = solve_elastic(
            coords,
            conn,
            lam,
            mu,
            bc_mask,
            bc_values,
            f_ext,
            tol=tol,
            max_iter=max_iter,
            cg_tol=cg_tol,
            cg_max_iter=cg_max_iter,
        )
        assert res_tl[-1] < tol * res_tl[0], (
            f"TL Newton did not converge: {res_tl[-1]:.3e} / {res_tl[0]:.3e}"
        )

        # --- Solve UL ---
        u_ul, res_ul = solve_elastic_ul(
            coords,
            conn,
            lam,
            mu,
            bc_mask,
            bc_values,
            f_ext,
            tol=tol,
            max_iter=max_iter,
            cg_tol=cg_tol,
            cg_max_iter=cg_max_iter,
        )
        assert res_ul[-1] < tol * res_ul[0], (
            f"UL Newton did not converge: {res_ul[-1]:.3e} / {res_ul[0]:.3e}"
        )

        # --- Compare ---
        max_diff = float(np.max(np.abs(u_tl - u_ul)))
        np.testing.assert_allclose(
            u_tl,
            u_ul,
            atol=1e-8,
            err_msg=(
                f"TL vs UL displacement mismatch: max |u_tl - u_ul| = {max_diff:.3e}. "
                f"TL converged in {len(res_tl)} iters, UL in {len(res_ul)} iters."
            ),
        )

    @pytest.mark.integration
    def test_rigid_rotation_jaumann_cauchy_rate_vanishes(self) -> None:
        """Jaumann rate vanishes under 30-degree rigid rotation.

        Under rigid rotation F = R, the velocity gradient L = Omega is
        purely skew-symmetric (D = 0, W = Omega). The exact sigma_dot
        is Omega @ sigma + sigma @ Omega.T. The Jaumann rate subtracts
        W @ sigma + sigma @ W.T, which exactly cancels sigma_dot.

        Acceptance criterion: max |sigma_hat_J| < 1e-12.
        """
        theta = np.radians(30.0)
        omega = 1.0  # angular rate (arbitrary)
        Omega = _spin_matrix_z(omega)

        # Pre-stressed state (general symmetric, non-trivial)
        sigma_0 = np.array(
            [
                [100.0, 15.0, -5.0],
                [15.0, -30.0, 8.0],
                [-5.0, 8.0, 50.0],
            ],
            dtype=np.float64,
        )

        # Rotate the stress to the 30-degree configuration
        R = _rotation_matrix_z(theta)
        sigma = R @ sigma_0 @ R.T

        # Material time derivative of sigma under rigid rotation
        sigma_dot = _rotating_sigma_dot(Omega, sigma)

        # For rigid rotation L = Omega (velocity gradient = spin)
        sigma_hat = jaumann_rate(sigma_dot=sigma_dot, L=Omega, sigma=sigma)

        max_rate = float(np.max(np.abs(sigma_hat)))
        assert max_rate < 1e-12, (
            f"Jaumann rate did not vanish under rigid rotation: "
            f"max |sigma_hat| = {max_rate:.3e}\n{sigma_hat}"
        )

    @pytest.mark.integration
    def test_rigid_rotation_truesdell_cauchy_rate_vanishes(self) -> None:
        """Truesdell rate vanishes under 30-degree rigid rotation.

        Under rigid rotation L = Omega (skew), D = sym(L) = 0, tr(D) = 0.
        The Truesdell formula sigma_hat = sigma_dot - L @ sigma - sigma @ L.T
        + sigma * tr(D) reduces to the same cancellation as Jaumann.

        Acceptance criterion: max |sigma_hat_T| < 1e-10.
        """
        theta = np.radians(30.0)
        omega = 1.0
        Omega = _spin_matrix_z(omega)

        sigma_0 = np.array(
            [
                [100.0, 15.0, -5.0],
                [15.0, -30.0, 8.0],
                [-5.0, 8.0, 50.0],
            ],
            dtype=np.float64,
        )

        R = _rotation_matrix_z(theta)
        sigma = R @ sigma_0 @ R.T

        sigma_dot = _rotating_sigma_dot(Omega, sigma)

        # For rigid rotation L = Omega
        sigma_hat = truesdell_rate(sigma_dot=sigma_dot, L=Omega, sigma=sigma)

        max_rate = float(np.max(np.abs(sigma_hat)))
        assert max_rate < 1e-10, (
            f"Truesdell rate did not vanish under rigid rotation: "
            f"max |sigma_hat| = {max_rate:.3e}\n{sigma_hat}"
        )

    @pytest.mark.integration
    def test_rigid_rotation_green_naghdi_cauchy_rate_vanishes(self) -> None:
        """Green-Naghdi rate vanishes under 30-degree rigid rotation.

        For rigid rotation F = R, U = I. The polar-decomposition spin
        Omega_GN = R_dot @ R.T coincides with the continuum spin Omega.
        The Green-Naghdi formula sigma_hat = sigma_dot - Omega_GN @ sigma
        - sigma @ Omega_GN.T produces the same cancellation.

        Acceptance criterion: max |sigma_hat_GN| < 1e-10.
        """
        theta = np.radians(30.0)
        omega = 1.0
        Omega = _spin_matrix_z(omega)

        sigma_0 = np.array(
            [
                [100.0, 15.0, -5.0],
                [15.0, -30.0, 8.0],
                [-5.0, 8.0, 50.0],
            ],
            dtype=np.float64,
        )

        R = _rotation_matrix_z(theta)
        sigma = R @ sigma_0 @ R.T

        sigma_dot = _rotating_sigma_dot(Omega, sigma)

        # For rigid rotation, Omega_GN = R_dot @ R.T = Omega
        sigma_hat = green_naghdi_rate(sigma_dot=sigma_dot, Omega=Omega, sigma=sigma)

        max_rate = float(np.max(np.abs(sigma_hat)))
        assert max_rate < 1e-10, (
            f"Green-Naghdi rate did not vanish under rigid rotation: "
            f"max |sigma_hat| = {max_rate:.3e}\n{sigma_hat}"
        )
