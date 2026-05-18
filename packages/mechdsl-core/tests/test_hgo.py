"""Tests for Task P4-4: HGO anisotropic hyperelastic model (two fiber families).

Strain energy (compressible, isochoric-volumetric split + two fiber families):

    Psi = Psi_iso_NH + Psi_vol + sum_{i=1,2} (k1 / (2 k2)) (exp(k2 * <E_fi>^2) - 1)

with E_fi = kappa_disp*(I1_bar - 3) + (1 - 3*kappa_disp)*(I4_bar_i - 1).  The
MacCauley bracket gates the fiber term on E_fi > 0 (avoids buckling artefacts
under compression).

Acceptance:
- AC-1: uniaxial along a1 gives higher stress than isotropic NH at same F.
- AC-2: shear parallel to a1 is stiffer than shear perpendicular.
- AC-3: compressive loading with E_fi <= 0 makes HGO == isotropic NH exactly.
"""

from __future__ import annotations

import numpy as np
import pytest
from numpy.testing import assert_allclose

from mechdsl.frontend import UnsupportedError, build_context
from mechdsl.symbolic.models.hgo import (
    HGOMaterial,
    material_tangent_4th,
    material_tangent_voigt,
    pk2_stress,
)
from mechdsl.symbolic.models.neo_hookean import (
    NeoHookeanMaterial,
)
from mechdsl.symbolic.models.neo_hookean import (
    pk2_stress as nh_pk2,
)
from mechdsl.symbolic.voigt import tangent_to_voigt_66


def _E_from_F(F: np.ndarray) -> np.ndarray:
    return 0.5 * (F.T @ F - np.eye(3))


_MAT = HGOMaterial(mu=30.0, k1=1000.0, k2=5.0, kappa=1000.0, fiber_dispersion=0.1)
_A1 = np.array([1.0, 0.0, 0.0])
_A2 = np.array([0.0, 1.0, 0.0])


class TestTaskP4_4HGO:
    """AC-1 / AC-2 / AC-3 for the HGO anisotropic model."""

    @pytest.mark.unit
    def test_zero_stress_at_identity(self) -> None:
        S = pk2_stress(_MAT, np.zeros((3, 3)), (_A1, _A2))
        assert_allclose(S, np.zeros((3, 3)), atol=1e-12)

    @pytest.mark.unit
    def test_uniaxial_fiber_stiffening(self) -> None:
        """AC-1: stretch along a1 gives strictly higher stress than NH-only."""
        stretch = 1.5
        lat = 1.0 / np.sqrt(stretch)
        F = np.diag([stretch, lat, lat])
        E = _E_from_F(F)

        S_hgo = pk2_stress(_MAT, E, (_A1, _A2))
        nh = NeoHookeanMaterial(mu=_MAT.mu, kappa=_MAT.kappa)
        S_nh = nh_pk2(nh, E)

        # Fiber family a1 is along the stretch axis; fiber contribution is
        # strictly positive and adds to S_00.
        assert S_hgo[0, 0] > S_nh[0, 0] + 1.0, (
            f"HGO fiber stiffening expected; got S_hgo={S_hgo[0, 0]}, S_nh={S_nh[0, 0]}"
        )

    @pytest.mark.unit
    def test_shear_anisotropy_parallel_vs_perpendicular(self) -> None:
        """AC-2: under identical F, a fiber aligned with the shear stretch axis
        gives a stiffer response than a fiber normal to it.

        For simple shear F = I + gamma * e_x ⊗ e_y, C = F^T F has
        C_yy = 1 + gamma^2 and C_xx = 1. A fiber along e_y is stretched
        (I4 > 1 ⇒ E_fi > 0 ⇒ active); a fiber along e_x is not (I4 = 1,
        I1_bar > 3 but by far less contribution ⇒ near-inactive).
        """
        gamma = 0.2
        F = np.eye(3)
        F[0, 1] = gamma
        E = _E_from_F(F)

        a_null = np.array([0.0, 0.0, 1.0])  # out-of-plane, unstretched

        # Parallel: fiber along the stretch axis e_y.
        S_par = pk2_stress(_MAT, E, (np.array([0.0, 1.0, 0.0]), a_null))
        # Perpendicular: fiber normal to stretch, along e_x.
        S_perp = pk2_stress(_MAT, E, (np.array([1.0, 0.0, 0.0]), a_null))

        tau_par = float(np.linalg.norm(S_par))
        tau_perp = float(np.linalg.norm(S_perp))
        assert tau_par > tau_perp, (
            f"Shear with fiber parallel to stretch must exceed perpendicular; "
            f"got tau_par={tau_par}, tau_perp={tau_perp}"
        )

    @pytest.mark.unit
    def test_compression_along_fiber_equals_isotropic_nh(self) -> None:
        """AC-3: compression along a1 zeros both fibers ⇒ HGO == NH exactly.

        With a1 and a2 both compressed (I4_bar_i < 1) and I1_bar slightly > 3
        balanced against (I4_bar - 1), we choose a loading mode where the
        dispersion-weighted E_fi is clearly negative for both families. Here
        we compress along a1 = e_x and stretch laterally: I4_bar_1 < 1,
        I4_bar_2 > 1 potentially. To make both fibers inactive, align both
        along the compression axis.
        """
        a1 = np.array([1.0, 0.0, 0.0])
        a2 = np.array([1.0, 0.0, 0.0])
        # Strong compression along x, modest lateral stretch (incompressible).
        stretch = 0.6
        lat = 1.0 / np.sqrt(stretch)
        F = np.diag([stretch, lat, lat])
        E = _E_from_F(F)

        S_hgo = pk2_stress(_MAT, E, (a1, a2))
        nh = NeoHookeanMaterial(mu=_MAT.mu, kappa=_MAT.kappa)
        S_nh = nh_pk2(nh, E)
        assert_allclose(S_hgo, S_nh, atol=1e-12, rtol=1e-12)

    @pytest.mark.unit
    def test_tangent_major_symmetry(self) -> None:
        F = np.eye(3) + 0.05 * np.array([[0.1, 0.0, 0.0], [0.0, -0.05, 0.0], [0.0, 0.0, 0.02]])
        E = _E_from_F(F)
        C4 = material_tangent_4th(_MAT, E, (_A1, _A2))
        assert_allclose(C4, C4.transpose(2, 3, 0, 1), atol=1e-6)

    @pytest.mark.unit
    def test_tangent_matches_fd_of_stress(self) -> None:
        """Independent FD oracle on S(E) confirms the tangent in the active regime."""
        # Tensile uniaxial so fiber is active.
        stretch = 1.3
        lat = 1.0 / np.sqrt(stretch)
        F = np.diag([stretch, lat, lat])
        E = _E_from_F(F)
        C4 = material_tangent_4th(_MAT, E, (_A1, _A2))

        rng = np.random.default_rng(3)
        dE = rng.standard_normal((3, 3))
        dE = 0.5 * (dE + dE.T)
        eps = 1e-5
        S_plus = pk2_stress(_MAT, E + eps * dE, (_A1, _A2))
        S_minus = pk2_stress(_MAT, E - eps * dE, (_A1, _A2))
        dS_fd = (S_plus - S_minus) / (2.0 * eps)
        dS_from_C = np.einsum("ijkl,kl->ij", C4, dE)
        assert_allclose(dS_from_C, dS_fd, atol=1e-2, rtol=1e-2)

    @pytest.mark.unit
    def test_voigt_tangent_matches_4th_order(self) -> None:
        E = np.diag([0.01, -0.002, 0.001])
        C4 = material_tangent_4th(_MAT, E, (_A1, _A2))
        CV = material_tangent_voigt(_MAT, E, (_A1, _A2))
        assert_allclose(CV, tangent_to_voigt_66(C4), atol=1e-12)

    @pytest.mark.unit
    def test_build_context_accepts_hgo_with_fiber_data(self) -> None:
        """Frontend accepts 'hgo' with a fiber_data kwarg; rejects without."""
        fibers = np.zeros((1, 2, 3))
        fibers[0, 0] = [1.0, 0.0, 0.0]
        fibers[0, 1] = [0.0, 1.0, 0.0]
        ctx = build_context(
            dim=3,
            cell_type="hex8",
            formulation="total_lagrangian",
            material_type="hgo",
            params={"mu": 30.0, "k1": 1e3, "k2": 5.0, "kappa": 1e3, "fiber_dispersion": 0.1},
            boundaries=[
                {"name": "fix", "type": "dirichlet", "value": 0, "components": [0, 1, 2]},
                {"name": "load", "type": "neumann", "traction": "t_bar"},
            ],
            fiber_data=fibers,
        )
        assert ctx["material_type"] == "hgo"
        assert np.array_equal(ctx["fiber_data"], fibers)

    @pytest.mark.unit
    def test_build_context_rejects_hgo_without_fiber_data(self) -> None:
        """HGO without fiber_data is an error: required per-element data."""
        with pytest.raises(UnsupportedError, match="fiber_data"):
            build_context(
                dim=3,
                cell_type="hex8",
                formulation="total_lagrangian",
                material_type="hgo",
                params={"mu": 30.0, "k1": 1e3, "k2": 5.0, "kappa": 1e3, "fiber_dispersion": 0.1},
                boundaries=[
                    {"name": "fix", "type": "dirichlet", "value": 0, "components": [0, 1, 2]},
                ],
            )
