"""Tests for Task P1-5: Objective stress rates (Jaumann, Truesdell, Green-Naghdi).

Plan: dev/design_docs/PLAN-B.md lines 56-65 (B1.4 Objective stress rates table).

Implementation note: the P1-5 scope names three `*_tangent` functions in the
API, and the acceptance criteria call for a rigid-rotation invariance test.
Mathematically those two requirements live on different surfaces -- the
rigid-rotation invariance is a property of the **direct rate formulas**
(sigma_hat = sigma_dot - W @ sigma - sigma @ W.T, etc.), not of tangent
operators (under rigid rotation D = 0 so any tangent c:D is trivially zero).
The module therefore exposes BOTH direct rate functions AND the tangent
conversions that P1-4 will consume for UL emission. These tests cover both
layers.
"""

from __future__ import annotations

import numpy as np
import pytest

from mechdsl.symbolic.objective_rates import (
    green_naghdi_rate,
    jaumann_rate,
    jaumann_tangent,
    truesdell_rate,
    truesdell_tangent,
)


def _rotating_sigma_rate(Omega: np.ndarray, sigma: np.ndarray) -> np.ndarray:
    """Exact sigma_dot for a rigidly-rotating Cauchy stress.

    If sigma(t) = R(t) @ sigma_0 @ R(t).T then
    sigma_dot = Omega @ sigma + sigma @ Omega.T
    where Omega = R_dot @ R.T.
    """
    return Omega @ sigma + sigma @ Omega.T


def _skew_spin(omega: float) -> np.ndarray:
    """Rigid-rotation angular velocity tensor about z with rate omega."""
    return np.array(
        [
            [0.0, -omega, 0.0],
            [omega, 0.0, 0.0],
            [0.0, 0.0, 0.0],
        ]
    )


def _isotropic_material_tangent(lam: float, mu: float) -> np.ndarray:
    """Isotropic 4th-order tangent.

    C_IJKL = lam*delta_IJ*delta_KL + mu*(delta_IK*delta_JL + delta_IL*delta_JK)
    """
    ident = np.eye(3)
    return lam * np.einsum("ij,kl->ijkl", ident, ident) + mu * (
        np.einsum("ik,jl->ijkl", ident, ident) + np.einsum("il,jk->ijkl", ident, ident)
    )


def _contract_4th_order(C4: np.ndarray, D: np.ndarray) -> np.ndarray:
    """Compute c_{ijkl} * D_{kl}."""
    return np.einsum("ijkl,kl->ij", C4, D)


class TestTaskP1_5:
    """
    Tests for Task P1-5: Objective stress rates.

    Acceptance criteria:
      1. All three rates implemented as pure NumPy functions.
      2. Rigid rotation test passes for Jaumann / Truesdell / Green-Naghdi
         (sigma_hat vanishes under pure rotation for each rate).
      3. Simple shear Jaumann tangent matches the Prandtl-Reuss correction
         applied to the Truesdell tangent.
    """

    @pytest.mark.unit
    def test_jaumann_tangent_at_rigid_rotation_gives_zero_cauchy_rate(self) -> None:
        """Jaumann rate sigma_hat_J vanishes under pure rigid rotation.

        Acceptance criterion: "Rigid rotation test passes for all three rates."
        Test semantics: computes the exact sigma_dot produced by rotating a
        pre-stressed state at angular velocity omega, feeds (sigma_dot, L=Omega,
        sigma) into the Jaumann rate formula, and checks that sigma_hat_J = 0
        to machine precision. L = Omega here because for rigid rotation the
        velocity gradient equals the spin tensor (D = 0, W = Omega).
        """
        omega = 0.73  # non-trivial angular velocity
        sigma = np.diag([100.0, 50.0, -20.0])
        Omega = _skew_spin(omega)
        sigma_dot = _rotating_sigma_rate(Omega, sigma)
        sigma_hat = jaumann_rate(sigma_dot=sigma_dot, L=Omega, sigma=sigma)
        assert np.allclose(sigma_hat, np.zeros_like(sigma), atol=1e-12), (
            f"Jaumann rate did not vanish under rigid rotation:\n{sigma_hat}"
        )

    @pytest.mark.unit
    def test_truesdell_tangent_at_rigid_rotation_gives_zero_cauchy_rate(self) -> None:
        """Truesdell rate sigma_hat_T vanishes under pure rigid rotation.

        For rigid rotation L = Omega, D = sym(Omega) = 0, tr(D) = 0, so all
        terms in sigma_hat_T = sigma_dot - L @ sigma - sigma @ L.T + sigma*tr(D)
        reduce to sigma_hat_T = sigma_dot - Omega @ sigma - sigma @ Omega.T = 0.
        """
        omega = 0.42
        sigma = np.array(
            [
                [30.0, 5.0, -2.0],
                [5.0, -10.0, 1.0],
                [-2.0, 1.0, 15.0],
            ]
        )  # symmetric pre-stress
        Omega = _skew_spin(omega)
        sigma_dot = _rotating_sigma_rate(Omega, sigma)
        sigma_hat = truesdell_rate(sigma_dot=sigma_dot, L=Omega, sigma=sigma)
        assert np.allclose(sigma_hat, np.zeros_like(sigma), atol=1e-12), (
            f"Truesdell rate did not vanish under rigid rotation:\n{sigma_hat}"
        )

    @pytest.mark.unit
    def test_green_naghdi_tangent_at_rigid_rotation_gives_zero_cauchy_rate(self) -> None:
        """Green-Naghdi rate sigma_hat_GN vanishes under pure rigid rotation.

        For rigid rotation, the polar-decomposition spin Omega_GN = R_dot @ R.T
        coincides with the continuum spin W (since F = R, U = I). So the
        Green-Naghdi rate reduces to the same cancellation as Jaumann.
        """
        omega = 0.58
        sigma = np.diag([200.0, -40.0, 25.0])
        Omega = _skew_spin(omega)
        sigma_dot = _rotating_sigma_rate(Omega, sigma)
        sigma_hat = green_naghdi_rate(sigma_dot=sigma_dot, Omega=Omega, sigma=sigma)
        assert np.allclose(sigma_hat, np.zeros_like(sigma), atol=1e-12), (
            f"Green-Naghdi rate did not vanish under rigid rotation:\n{sigma_hat}"
        )

    @pytest.mark.unit
    def test_truesdell_tangent_full_f_simple_shear_matches_b_formula(self) -> None:
        """Truesdell tangent at non-identity F equals (1/J) F F F F : C.

        For an isotropic Lagrangian tangent with lam = 0 and
        ``C_IJKL = mu (delta_IK delta_JL + delta_IL delta_JK)``, the
        4-leg Piola push-forward simplifies analytically to

            c_ijkl = mu (B_ik B_jl + B_il B_jk),    B = F @ F.T

        because each pair ``F_iI F_kI = B_ik``. This is an independent
        derivation from the einsum implementation, so matching it
        validates the push-forward end-to-end.

        Test deformation: simple shear F = I + gamma * e1 (x) e2 with
        gamma = 0.5 (so J = det(F) = 1, no volume change). Pre-stress is
        zero -- the Truesdell push-forward does not depend on sigma.
        """
        gamma = 0.5
        F = np.eye(3)
        F[0, 1] = gamma
        assert abs(np.linalg.det(F) - 1.0) < 1e-14, "simple shear must be isochoric"

        # Isotropic shear-only tangent (lam = 0).
        mu = 1.0
        C4 = _isotropic_material_tangent(lam=0.0, mu=mu)

        sigma = np.zeros((3, 3))
        c_tru = truesdell_tangent(C4, sigma, F=F)

        # Closed-form expectation via left Cauchy-Green B.
        B = F @ F.T
        expected = mu * (np.einsum("ik,jl->ijkl", B, B) + np.einsum("il,jk->ijkl", B, B))
        assert np.allclose(c_tru, expected, atol=1e-12), (
            f"Truesdell push-forward did not match closed-form B-tensor expression.\n"
            f"max abs error: {np.max(np.abs(c_tru - expected)):.3e}"
        )

        # Spot check on a few specific components against hand calculation:
        #   B_11 = 1 + gamma^2 = 1.25
        #   B_22 = 1, B_12 = B_21 = gamma = 0.5
        #   c_1212 = mu (B_11 B_22 + B_12 B_21) = 1*(1.25 + 0.25) = 1.50
        #   c_1111 = 2 mu B_11^2 = 2 * 1.5625 = 3.125
        #   c_1122 = 2 mu B_12^2 = 2 * 0.25 = 0.5
        assert abs(c_tru[0, 1, 0, 1] - 1.5) < 1e-12
        assert abs(c_tru[0, 0, 0, 0] - 3.125) < 1e-12
        assert abs(c_tru[0, 0, 1, 1] - 0.5) < 1e-12

    @pytest.mark.unit
    def test_truesdell_tangent_identity_f_back_compat(self) -> None:
        """Passing F=None or F=I is equivalent and recovers C_IJKL.

        Regression guard for the original P1-5 identity-only path.
        """
        C4 = _isotropic_material_tangent(lam=1000.0, mu=400.0)
        sigma = np.diag([10.0, -5.0, 3.0])

        c_default = truesdell_tangent(C4, sigma)
        c_explicit_identity = truesdell_tangent(C4, sigma, F=np.eye(3))
        assert np.allclose(c_default, C4, atol=1e-15)
        assert np.allclose(c_explicit_identity, C4, atol=1e-15)
        assert np.allclose(c_default, c_explicit_identity, atol=1e-15)

    @pytest.mark.unit
    def test_truesdell_tangent_rejects_inverted_f(self) -> None:
        """det(F) <= 0 raises ValueError with element-inversion diagnostic."""
        C4 = _isotropic_material_tangent(lam=0.0, mu=1.0)
        # Reflect across the y axis: det(F) = -1.
        F_inverted = np.diag([-1.0, 1.0, 1.0])
        with pytest.raises(ValueError, match="Non-positive Jacobian"):
            truesdell_tangent(C4, sigma=np.zeros((3, 3)), F=F_inverted)

    @pytest.mark.unit
    def test_jaumann_tangent_on_simple_shear_matches_hand_calculation(self) -> None:
        """Jaumann tangent conversion matches the Prandtl-Reuss correction.

        At F = I the Truesdell tangent coincides with the Lagrangian material
        tangent (identity push-forward, J = 1). The Jaumann tangent adds the
        stress-symmetrisation correction

            T_{ijkl} = 0.5*(delta_ik sigma_jl + delta_il sigma_jk
                          + sigma_ik delta_jl + sigma_il delta_jk)
                       - sigma_ij delta_kl

        which, when contracted with the symmetric rate of deformation D, gives
            T : D = D @ sigma + sigma @ D - sigma * tr(D).

        This test verifies the identity at the rank-4 level (no D needed) and
        then at the rank-2 level via a specific simple-shear rate to match a
        hand calculation.
        """
        lam, mu = 1000.0, 400.0  # Lame parameters
        C4 = _isotropic_material_tangent(lam, mu)

        # Uniaxial pre-stress along x.
        sigma_11 = 75.0
        sigma = np.diag([sigma_11, 0.0, 0.0])

        # (a) Rank-4 identity: c_Jau - c_Tru equals the Prandtl-Reuss correction.
        c_tru = truesdell_tangent(C4, sigma)
        c_jau = jaumann_tangent(C4, sigma)

        ident = np.eye(3)
        T_expected = 0.5 * (
            np.einsum("ik,jl->ijkl", ident, sigma)
            + np.einsum("il,jk->ijkl", ident, sigma)
            + np.einsum("ik,jl->ijkl", sigma, ident)
            + np.einsum("il,jk->ijkl", sigma, ident)
        ) - np.einsum("ij,kl->ijkl", sigma, ident)
        T_actual = c_jau - c_tru
        assert np.allclose(T_actual, T_expected, atol=1e-12), (
            "Jaumann - Truesdell tangent did not match Prandtl-Reuss correction T(sigma)"
        )

        # (b) Rank-2 hand calc on a simple-shear D.
        gamma_dot = 0.1
        D = np.array(
            [
                [0.0, gamma_dot / 2, 0.0],
                [gamma_dot / 2, 0.0, 0.0],
                [0.0, 0.0, 0.0],
            ]
        )
        c_jau_D = _contract_4th_order(c_jau, D)
        # Expected: c_tru : D = 2*mu*D (since lam*tr(D) = 0)
        # plus T : D = D @ sigma + sigma @ D - sigma * tr(D)
        expected = 2 * mu * D + (D @ sigma + sigma @ D - sigma * np.trace(D))
        assert np.allclose(c_jau_D, expected, atol=1e-12), (
            f"Jaumann tangent on simple shear mismatch:\ngot:      {c_jau_D}\nexpected: {expected}"
        )
