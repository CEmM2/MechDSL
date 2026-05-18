"""Tests for Task P4-1: Neo-Hookean hyperelastic model.

Classical form: Psi = (mu/2)(I1_bar - 3) + (kappa/2)(J - 1)^2

Three acceptance checks:
- AC-1: at F = I, S = 0 and C matches the linear-elastic tangent.
- AC-2: pure dilation gives hydrostatic S matching hand calc.
- AC-3: simple shear matches the analytical closed form.

Full AD-oracle validation against 100 random states is deferred to P4-5.
"""

from __future__ import annotations

import numpy as np
import pytest
from numpy.testing import assert_allclose

from mechdsl.frontend import build_context
from mechdsl.symbolic.models.neo_hookean import (
    NeoHookeanMaterial,
    material_tangent_4th,
    material_tangent_voigt,
    pk2_stress,
)
from mechdsl.symbolic.voigt import tangent_to_voigt_66

_MU = 80.0
_KAPPA = 160.0


def _green_lagrange_from_F(F: np.ndarray) -> np.ndarray:
    """E = 0.5 * (F^T F - I)."""
    return 0.5 * (F.T @ F - np.eye(3))


class TestTaskP4_1NeoHookean:
    """Acceptance criteria AC-1, AC-2, AC-3 for Neo-Hookean."""

    @pytest.mark.unit
    def test_zero_stress_at_identity(self):
        """At F = I (E = 0), PK2 stress is exactly zero."""
        mat = NeoHookeanMaterial(mu=_MU, kappa=_KAPPA)
        E = np.zeros((3, 3))
        S = pk2_stress(mat, E)
        assert_allclose(S, np.zeros((3, 3)), atol=1e-12)

    @pytest.mark.unit
    def test_tangent_at_identity_matches_linear_elastic(self):
        """At F = I, C_IJKL reduces to the isotropic linear elastic tangent

        with effective Lame constants lam_eff = kappa - (2/3)*mu and mu_eff = mu.
        """
        mat = NeoHookeanMaterial(mu=_MU, kappa=_KAPPA)
        E = np.zeros((3, 3))
        C4 = material_tangent_4th(mat, E)

        lam_eff = _KAPPA - (2.0 / 3.0) * _MU
        mu_eff = _MU
        d = np.eye(3)
        expected = np.zeros((3, 3, 3, 3))
        for i in range(3):
            for j in range(3):
                for k in range(3):
                    for ll in range(3):
                        expected[i, j, k, ll] = lam_eff * d[i, j] * d[k, ll] + mu_eff * (
                            d[i, k] * d[j, ll] + d[i, ll] * d[j, k]
                        )
        assert_allclose(C4, expected, atol=1e-10)

    @pytest.mark.unit
    def test_pure_dilation_hydrostatic_stress(self):
        """F = lambda*I gives S = kappa*lambda*(lambda^3 - 1) * I.

        Under pure dilation the isochoric part vanishes by construction
        (J^(-2/3) * I1 = 3 so the isochoric term is zero), leaving only the
        volumetric response.
        """
        mat = NeoHookeanMaterial(mu=_MU, kappa=_KAPPA)
        for lam in (0.9, 1.0, 1.05, 1.2):
            F = lam * np.eye(3)
            E = _green_lagrange_from_F(F)
            S = pk2_stress(mat, E)

            expected = _KAPPA * lam * (lam**3 - 1.0) * np.eye(3)
            assert_allclose(S, expected, atol=1e-10, rtol=1e-10)

            # Deviatoric part must vanish under pure dilation
            dev = S - (np.trace(S) / 3.0) * np.eye(3)
            assert_allclose(dev, np.zeros((3, 3)), atol=1e-10)

    @pytest.mark.unit
    def test_simple_shear_closed_form(self):
        """Simple shear F = I + gamma * e1 x e2 matches analytical S.

        For Neo-Hookean with J = 1, I1 = 3 + gamma^2,
            S_iso = mu * (I - (I1/3) * Cinv),    S_vol = 0.
        Exact closed form:
            S_00 = -mu * (4*gamma^2/3 + gamma^4/3)
            S_11 = S_22 = -mu * gamma^2 / 3
            S_01 = S_10 = mu * gamma * (1 + gamma^2/3)
        """
        mat = NeoHookeanMaterial(mu=_MU, kappa=_KAPPA)
        gamma = 0.05
        F = np.eye(3)
        F[0, 1] = gamma
        E = _green_lagrange_from_F(F)
        S = pk2_stress(mat, E)

        expected = np.zeros((3, 3))
        expected[0, 0] = -_MU * (4.0 * gamma**2 / 3.0 + gamma**4 / 3.0)
        expected[1, 1] = -_MU * gamma**2 / 3.0
        expected[2, 2] = -_MU * gamma**2 / 3.0
        expected[0, 1] = _MU * gamma * (1.0 + gamma**2 / 3.0)
        expected[1, 0] = expected[0, 1]
        assert_allclose(S, expected, atol=1e-12, rtol=1e-12)

    @pytest.mark.unit
    def test_tangent_fd_against_stress_central_difference(self):
        """Material tangent C_IJKL matches 2*dS_IJ/dC_KL via central difference.

        Robust-but-cheap oracle: picks several F states, perturbs C symmetrically,
        and checks the analytical tangent reproduces central-difference stress
        derivatives to 1e-5. Full 100-state AD oracle is in P4-5.
        """
        mat = NeoHookeanMaterial(mu=_MU, kappa=_KAPPA)
        rng = np.random.default_rng(42)

        # A handful of generic F (each with J > 0)
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

                    # dS_IJ/dE_KL = C_IJKL (contracted on symmetric dE_sym)
                    # With dE_sym = 0.5*(dE + dE^T), dS = C : dE_sym.
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
        """C_IJKL = C_KLIJ within 1e-10 on a random deformation."""
        mat = NeoHookeanMaterial(mu=_MU, kappa=_KAPPA)
        rng = np.random.default_rng(7)
        F = np.eye(3) + 0.1 * rng.standard_normal((3, 3))
        E = _green_lagrange_from_F(F)
        C4 = material_tangent_4th(mat, E)
        assert_allclose(C4, C4.transpose(2, 3, 0, 1), atol=1e-10)

    @pytest.mark.unit
    def test_voigt_tangent_matches_contracted_4th(self):
        """The 6x6 Voigt tangent is the Voigt contraction of the (3,3,3,3) form."""
        mat = NeoHookeanMaterial(mu=_MU, kappa=_KAPPA)
        E = np.zeros((3, 3))
        assert_allclose(
            material_tangent_voigt(mat, E),
            tangent_to_voigt_66(material_tangent_4th(mat, E)),
            atol=1e-12,
        )

    @pytest.mark.unit
    def test_from_E_nu_matches_steel(self):
        """E/nu constructor produces the expected kappa, mu for steel."""
        mat = NeoHookeanMaterial.from_E_nu(E=200_000.0, nu=0.3)
        assert mat.mu == pytest.approx(200_000.0 / (2.0 * 1.3))
        assert mat.kappa == pytest.approx(200_000.0 / (3.0 * 0.4))

    @pytest.mark.unit
    def test_build_context_accepts_neo_hookean(self):
        """build_context must accept material_type='neo_hookean' (scope item 3)."""
        ctx = build_context(
            dim=3,
            cell_type="hex8",
            formulation="total_lagrangian",
            material_type="neo_hookean",
            params={"mu": _MU, "kappa": _KAPPA},
            boundaries={},
            coord_system="cartesian",
        )
        assert ctx["material_type"] == "neo_hookean"
        assert ctx["params"]["mu"] == _MU
        assert ctx["params"]["kappa"] == _KAPPA
