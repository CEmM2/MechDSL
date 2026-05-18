"""Tests for Task P4-2: Mooney-Rivlin hyperelastic model.

Strain energy: Psi = C1 (I1_bar - 3) + C2 (I2_bar - 3) + (kappa/2)(J - 1)^2

Acceptance criteria:
- AC-1: zero stress at F = I.
- AC-2: C2 = 0 reduces exactly to Neo-Hookean with mu = 2*C1 (tol 1e-12).
- AC-3: simple shear matches a closed-form rubber benchmark to 1e-6.
"""

from __future__ import annotations

import numpy as np
import pytest
from numpy.testing import assert_allclose

from mechdsl.frontend import build_context
from mechdsl.symbolic.models.mooney_rivlin import (
    MooneyRivlinMaterial,
    material_tangent_4th,
    material_tangent_voigt,
    pk2_stress,
)
from mechdsl.symbolic.models.neo_hookean import (
    NeoHookeanMaterial,
)
from mechdsl.symbolic.models.neo_hookean import (
    material_tangent_4th as nh_tangent_4th,
)
from mechdsl.symbolic.models.neo_hookean import (
    pk2_stress as nh_pk2_stress,
)
from mechdsl.symbolic.voigt import tangent_to_voigt_66


def _green_lagrange_from_F(F: np.ndarray) -> np.ndarray:
    return 0.5 * (F.T @ F - np.eye(3))


class TestTaskP4_2MooneyRivlin:
    """Acceptance criteria AC-1, AC-2, AC-3 for Mooney-Rivlin."""

    @pytest.mark.unit
    def test_zero_stress_at_identity(self):
        """At F = I (E = 0), PK2 stress is exactly zero."""
        mat = MooneyRivlinMaterial(C1=40.0, C2=10.0, kappa=160.0)
        E = np.zeros((3, 3))
        S = pk2_stress(mat, E)
        assert_allclose(S, np.zeros((3, 3)), atol=1e-12)

    @pytest.mark.unit
    def test_c2_zero_reduces_to_neo_hookean(self):
        """C2 = 0 → MR stress and tangent match Neo-Hookean with mu = 2*C1."""
        C1, kappa = 40.0, 160.0
        mr = MooneyRivlinMaterial(C1=C1, C2=0.0, kappa=kappa)
        nh = NeoHookeanMaterial(mu=2.0 * C1, kappa=kappa)

        rng = np.random.default_rng(0)
        for _ in range(10):
            F = np.eye(3) + 0.1 * rng.standard_normal((3, 3))
            if np.linalg.det(F) <= 0:
                continue
            E = _green_lagrange_from_F(F)

            assert_allclose(pk2_stress(mr, E), nh_pk2_stress(nh, E), atol=1e-12, rtol=1e-12)
            assert_allclose(
                material_tangent_4th(mr, E),
                nh_tangent_4th(nh, E),
                atol=1e-10,
                rtol=1e-10,
            )

    @pytest.mark.unit
    def test_simple_shear_closed_form(self):
        """Simple shear F = I + gamma e1 x e2. J = 1, I1 = I2 = 3 + gamma^2.

        Closed form (hand-derived), with S_iso1 = 2*C1*(I - (I1/3)*Cinv) and
        S_iso2 = 2*C2*(I1*I - C - (2/3)*I2*Cinv):

            S_00 = -(2/3) * gamma^2 * (C1*(4 + gamma^2) + C2*(5 + 2*gamma^2))
            S_11 = -(2/3) * gamma^2 * (C1 + 2*C2)
            S_22 = -(2/3) * gamma^2 * (C1 - C2)
            S_01 =  2 * gamma * (C1*(1 + gamma^2/3) + C2*(1 + 2*gamma^2/3))
        """
        C1, C2, kappa = 0.4, 0.1, 100.0
        mat = MooneyRivlinMaterial(C1=C1, C2=C2, kappa=kappa)
        gamma = 0.05
        F = np.eye(3)
        F[0, 1] = gamma
        E = _green_lagrange_from_F(F)
        S = pk2_stress(mat, E)

        g2, g4 = gamma**2, gamma**4
        expected = np.zeros((3, 3))
        expected[0, 0] = -(2.0 / 3.0) * (C1 * (4.0 * g2 + g4) + C2 * (5.0 * g2 + 2.0 * g4))
        expected[1, 1] = -(2.0 / 3.0) * g2 * (C1 + 2.0 * C2)
        expected[2, 2] = -(2.0 / 3.0) * g2 * (C1 - C2)
        expected[0, 1] = 2.0 * gamma * (C1 * (1.0 + g2 / 3.0) + C2 * (1.0 + 2.0 * g2 / 3.0))
        expected[1, 0] = expected[0, 1]
        assert_allclose(S, expected, atol=1e-10, rtol=1e-10)

    @pytest.mark.unit
    def test_pure_dilation_hydrostatic_stress(self):
        """F = lambda*I: isochoric parts vanish, S = kappa*lam*(lam^3-1)*I."""
        mat = MooneyRivlinMaterial(C1=40.0, C2=10.0, kappa=160.0)
        for lam in (0.95, 1.0, 1.1):
            F = lam * np.eye(3)
            E = _green_lagrange_from_F(F)
            S = pk2_stress(mat, E)
            expected = mat.kappa * lam * (lam**3 - 1.0) * np.eye(3)
            assert_allclose(S, expected, atol=1e-10, rtol=1e-10)

    @pytest.mark.unit
    def test_tangent_at_identity_matches_linear_elastic(self):
        """At F = I, C_IJKL reduces to isotropic linear-elastic with
        mu_eff = 2*(C1 + C2) and lam_eff = kappa - (2/3)*mu_eff.
        """
        C1, C2, kappa = 40.0, 10.0, 160.0
        mat = MooneyRivlinMaterial(C1=C1, C2=C2, kappa=kappa)
        E = np.zeros((3, 3))
        C4 = material_tangent_4th(mat, E)

        mu_eff = 2.0 * (C1 + C2)
        lam_eff = kappa - (2.0 / 3.0) * mu_eff
        d = np.eye(3)
        expected = np.zeros((3, 3, 3, 3))
        for i in range(3):
            for j in range(3):
                for k in range(3):
                    for ll in range(3):
                        expected[i, j, k, ll] = lam_eff * d[i, j] * d[k, ll] + mu_eff * (
                            d[i, k] * d[j, ll] + d[i, ll] * d[j, k]
                        )
        assert_allclose(C4, expected, atol=1e-9)

    @pytest.mark.unit
    def test_tangent_fd_against_stress_central_difference(self):
        """Tangent C_IJKL matches dS/dE_KL via central difference on 3 F states.

        Cheap oracle; full 100-state AD oracle deferred to P4-5.
        """
        mat = MooneyRivlinMaterial(C1=40.0, C2=10.0, kappa=160.0)
        rng = np.random.default_rng(42)
        F_list = [
            np.eye(3) + 0.05 * rng.standard_normal((3, 3)),
            np.diag([1.1, 0.95, 1.03]) + 0.02 * rng.standard_normal((3, 3)),
            np.eye(3) + 0.1 * np.array([[0, 1, 0], [0, 0, 0], [0, 0, 0]]),
        ]
        eps = 1e-6

        for F in F_list:
            E0 = _green_lagrange_from_F(F)
            C4 = material_tangent_4th(mat, E0)

            for k in range(3):
                for ll in range(3):
                    dE = np.zeros((3, 3))
                    dE[k, ll] = 1.0
                    dE_sym = 0.5 * (dE + dE.T)
                    S_plus = pk2_stress(mat, E0 + eps * dE_sym)
                    S_minus = pk2_stress(mat, E0 - eps * dE_sym)
                    dS_numeric = (S_plus - S_minus) / (2.0 * eps)
                    dS_analytic = np.einsum("ijkl,kl->ij", C4, dE_sym)
                    assert_allclose(
                        dS_numeric,
                        dS_analytic,
                        atol=1e-5,
                        rtol=1e-5,
                        err_msg=f"FD tangent mismatch at (k,l)=({k},{ll})",
                    )

    @pytest.mark.unit
    def test_tangent_major_symmetry(self):
        """C_IJKL = C_KLIJ on a random deformation."""
        mat = MooneyRivlinMaterial(C1=40.0, C2=10.0, kappa=160.0)
        rng = np.random.default_rng(7)
        F = np.eye(3) + 0.1 * rng.standard_normal((3, 3))
        E = _green_lagrange_from_F(F)
        C4 = material_tangent_4th(mat, E)
        assert_allclose(C4, C4.transpose(2, 3, 0, 1), atol=1e-10)

    @pytest.mark.unit
    def test_voigt_tangent_matches_contracted_4th(self):
        """6x6 Voigt form equals the contracted (3,3,3,3) form."""
        mat = MooneyRivlinMaterial(C1=40.0, C2=10.0, kappa=160.0)
        E = np.zeros((3, 3))
        assert_allclose(
            material_tangent_voigt(mat, E),
            tangent_to_voigt_66(material_tangent_4th(mat, E)),
            atol=1e-12,
        )

    @pytest.mark.unit
    def test_build_context_accepts_mooney_rivlin(self):
        """build_context must accept material_type='mooney_rivlin' (scope item 3)."""
        ctx = build_context(
            dim=3,
            cell_type="hex8",
            formulation="total_lagrangian",
            material_type="mooney_rivlin",
            params={"C1": 40.0, "C2": 10.0, "kappa": 160.0},
            boundaries={},
            coord_system="cartesian",
        )
        assert ctx["material_type"] == "mooney_rivlin"
