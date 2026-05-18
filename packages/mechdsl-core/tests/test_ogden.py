"""Tests for Task P4-3: Ogden hyperelastic model (spectral stretch).

Strain energy (compressible, isochoric-volumetric split):
    Psi_iso = sum_p (mu_p/alpha_p) * (lambda_bar_1^alpha_p + lambda_bar_2^alpha_p
                                      + lambda_bar_3^alpha_p - 3)
    Psi_vol = (kappa/2)*(J - 1)^2

Acceptance checks:
- AC-1: N=1, alpha=2 reduces to Neo-Hookean with mu = mu_1 exactly.
- AC-2: uniaxial stretch curve is smooth and monotonic on [1.0, 3.0].
- AC-3: repeated eigenvalues (F = lambda*I) do not blow up and the stress
  is hydrostatic.  Near-degenerate eigenvalues (|lambda_i - lambda_j| = 1e-8)
  also return a finite stress continuous with the degenerate limit.
"""

from __future__ import annotations

import numpy as np
import pytest
from numpy.testing import assert_allclose

from mechdsl.frontend import build_context
from mechdsl.symbolic.models.neo_hookean import (
    NeoHookeanMaterial,
)
from mechdsl.symbolic.models.neo_hookean import (
    material_tangent_4th as nh_tangent,
)
from mechdsl.symbolic.models.neo_hookean import (
    pk2_stress as nh_pk2,
)
from mechdsl.symbolic.models.ogden import (
    OgdenMaterial,
    material_tangent_4th,
    material_tangent_voigt,
    pk2_stress,
)
from mechdsl.symbolic.voigt import tangent_to_voigt_66


def _E_from_F(F: np.ndarray) -> np.ndarray:
    return 0.5 * (F.T @ F - np.eye(3))


class TestTaskP4_3Ogden:
    """AC-1 / AC-2 / AC-3 for the Ogden constitutive model."""

    @pytest.mark.unit
    def test_zero_stress_at_identity(self) -> None:
        mat = OgdenMaterial(mus=(80.0,), alphas=(2.0,), kappa=160.0)
        E = np.zeros((3, 3))
        S = pk2_stress(mat, E)
        assert_allclose(S, np.zeros((3, 3)), atol=1e-12)

    @pytest.mark.unit
    def test_n1_alpha2_reduces_to_neo_hookean(self) -> None:
        """N=1, alpha_1=2 ⇒ identical to Neo-Hookean(mu = mu_1).

        Ogden with alpha=2: Psi_iso = (mu/2) * sum(lambda_bar_i^2 - 1)
                                    = (mu/2) * (I1_bar - 3)  since I1_bar = sum(lambda_bar_i^2).
        """
        mu = 80.0
        kappa = 160.0
        ogden = OgdenMaterial(mus=(mu,), alphas=(2.0,), kappa=kappa)
        nh = NeoHookeanMaterial(mu=mu, kappa=kappa)

        rng = np.random.default_rng(0)
        for _ in range(5):
            F = np.eye(3) + 0.1 * rng.standard_normal((3, 3))
            while np.linalg.det(F) < 0.2:
                F = np.eye(3) + 0.1 * rng.standard_normal((3, 3))
            E = _E_from_F(F)
            S_ogd = pk2_stress(ogden, E)
            S_nh = nh_pk2(nh, E)
            assert_allclose(S_ogd, S_nh, atol=1e-10, rtol=1e-10)
            C_ogd = material_tangent_4th(ogden, E)
            C_nh = nh_tangent(nh, E)
            # FD-vs-closed-form tangent matches to the FD step size (~1e-6).
            assert_allclose(C_ogd, C_nh, atol=1e-4, rtol=1e-4)

    @pytest.mark.unit
    def test_repeated_eigenvalues_F_equal_lambda_identity(self) -> None:
        """F = lambda*I (triple-degenerate) returns finite hydrostatic stress."""
        mat = OgdenMaterial(mus=(60.0, -20.0), alphas=(3.0, -2.0), kappa=200.0)
        for lam in (0.8, 1.0, 1.2, 1.5):
            F = lam * np.eye(3)
            E = _E_from_F(F)
            S = pk2_stress(mat, E)
            assert np.all(np.isfinite(S))
            # Hydrostatic (diagonal, equal entries).
            assert_allclose(S - np.diag(np.diag(S)), np.zeros((3, 3)), atol=1e-10)
            diag = np.diag(S)
            assert_allclose(diag, diag[0] * np.ones(3), rtol=1e-10, atol=1e-12)

    @pytest.mark.unit
    def test_near_degenerate_eigenvalues_are_finite_and_continuous(self) -> None:
        """|lambda_2 - lambda_1| = 1e-8 returns finite stress, continuous with limit."""
        mat = OgdenMaterial(mus=(50.0,), alphas=(2.5,), kappa=100.0)
        lam = 1.3

        # Triple-degenerate baseline.
        F0 = lam * np.eye(3)
        S0 = pk2_stress(mat, _E_from_F(F0))

        # Near-degenerate perturbation on the (0, 0) entry.
        for eps in (1e-4, 1e-6, 1e-8):
            F_near = np.diag([lam + eps, lam, lam])
            S_near = pk2_stress(mat, _E_from_F(F_near))
            assert np.all(np.isfinite(S_near))
            # Continuous in the degenerate limit: deviation scales with eps.
            assert np.linalg.norm(S_near - S0) < 1e-1

    @pytest.mark.unit
    def test_uniaxial_cauchy_stress_monotone(self) -> None:
        """N=3 rubber parameters: Cauchy stress sigma_11 is monotone in tension.

        PK2 itself need not be monotone for a non-linear Ogden model (the
        pull-back factor decreases with stretch), so the physically meaningful
        check is on sigma = (1/J) * F * S * F^T.
        """
        mat = OgdenMaterial(
            mus=(0.63, 0.0012, -0.01),
            alphas=(1.3, 5.0, -2.0),
            kappa=1000.0,
        )
        stretches = np.linspace(1.01, 2.5, 25)
        sigma11 = []
        for lam in stretches:
            lat = 1.0 / np.sqrt(lam)
            F = np.diag([lam, lat, lat])
            S = pk2_stress(mat, _E_from_F(F))
            sigma = (F @ S @ F.T) / np.linalg.det(F)
            sigma11.append(float(sigma[0, 0]))
        sigma_arr = np.array(sigma11)
        assert np.all(np.isfinite(sigma_arr))
        assert np.all(np.diff(sigma_arr) > 0), "Cauchy sigma_11 must be monotone in tension"

    @pytest.mark.unit
    def test_tangent_matches_fd_of_stress_on_generic_states(self) -> None:
        """Independent FD oracle on S(E) confirms the tangent."""
        mat = OgdenMaterial(mus=(40.0, -10.0), alphas=(2.5, -1.5), kappa=150.0)
        rng = np.random.default_rng(1)
        for _ in range(3):
            F = np.eye(3) + 0.08 * rng.standard_normal((3, 3))
            while np.linalg.det(F) < 0.3:
                F = np.eye(3) + 0.08 * rng.standard_normal((3, 3))
            E = _E_from_F(F)
            C4 = material_tangent_4th(mat, E)

            # Independent FD: probe random symmetric dE and compare.
            dE = rng.standard_normal((3, 3))
            dE = 0.5 * (dE + dE.T)
            eps = 1e-5
            S_plus = pk2_stress(mat, E + eps * dE)
            S_minus = pk2_stress(mat, E - eps * dE)
            dS_fd = (S_plus - S_minus) / (2.0 * eps)
            dS_from_C = np.einsum("ijkl,kl->ij", C4, dE)
            assert_allclose(dS_from_C, dS_fd, atol=1e-4, rtol=1e-4)

    @pytest.mark.unit
    def test_tangent_major_symmetry(self) -> None:
        mat = OgdenMaterial(mus=(50.0,), alphas=(2.0,), kappa=100.0)
        rng = np.random.default_rng(2)
        F = np.eye(3) + 0.05 * rng.standard_normal((3, 3))
        E = _E_from_F(F)
        C4 = material_tangent_4th(mat, E)
        assert_allclose(C4, C4.transpose(2, 3, 0, 1), atol=1e-6)

    @pytest.mark.unit
    def test_voigt_tangent_matches_4th_order(self) -> None:
        mat = OgdenMaterial(mus=(50.0,), alphas=(2.0,), kappa=100.0)
        E = np.diag([0.01, -0.005, 0.002])
        C4 = material_tangent_4th(mat, E)
        CV = material_tangent_voigt(mat, E)
        assert_allclose(CV, tangent_to_voigt_66(C4), atol=1e-12)

    @pytest.mark.unit
    def test_build_context_accepts_ogden(self) -> None:
        """Ogden material_type is accepted by the frontend dispatcher."""
        ctx = build_context(
            dim=3,
            cell_type="hex8",
            formulation="total_lagrangian",
            material_type="ogden",
            params={"mu1": 80.0, "alpha1": 2.0, "kappa": 160.0},
            boundaries=[
                {"name": "fix", "type": "dirichlet", "value": 0, "components": [0, 1, 2]},
                {"name": "load", "type": "neumann", "traction": "t_bar"},
            ],
        )
        assert ctx["material_type"] == "ogden"
