"""Tests for Task P4-5: AD oracle + uniaxial acceptance suite.

Two families of checks per hyperelastic model:

- **AD oracle** — the analytic PK2 stress must match the central-difference of
  the strain energy over 100 random deformation states. Central differences on
  double-precision are limited to ~1e-6 relative error by the h^2/roundoff
  tradeoff, so the acceptance threshold is 1e-6 (matches the existing SVK
  verifier). This validates consistency between ``pk2_stress`` and the
  hand-derived strain energy.

- **Uniaxial closed form** -- under uniaxial stretch ``lam`` along e_x with
  lateral stretches ``1/sqrt(lam)`` (so J = 1 exactly and the compressible
  volumetric part drops out), the deviatoric Cauchy stress ``sig_11 - sig_22``
  reduces to the classical incompressible rubber-elasticity closed form. We
  check the model reproduces that formula to 1e-10 -- the computation is
  entirely analytical (PK2 from the model, push-forward to Cauchy by hand,
  subtraction), so FD roundoff doesn't enter.

Closed forms used (F = diag(lam, 1/sqrt(lam), 1/sqrt(lam)), J=1):

    Neo-Hookean:     sig_11 - sig_22 = mu * (lam^2 - 1/lam)
    Mooney-Rivlin:   sig_11 - sig_22 = 2 * (C1 + C2/lam) * (lam^2 - 1/lam)
    Ogden:           sig_11 - sig_22 = sum_p mu_p * (lam^alpha_p - lam^(-alpha_p/2))
    HGO (k_disp=0, a1=e_x, a2=e_y for lam>1 perp-inactive):
                     sig_11 - sig_22 = mu * (lam^2 - 1/lam)
                                       + 2 * k1 * lam^2 * (lam^2 - 1)
                                         * exp(k2 * (lam^2 - 1)^2)

References: Holzapfel "Nonlinear Solid Mechanics" §6 (rubber elasticity,
uniaxial); Holzapfel-Gasser-Ogden 2006 (anisotropic fiber term).

Ogden exclusion: sampler skips deformation states where any pair of C
eigenvalues is within 1e-4 (documented task risk note — spectral PK2 is
continuous there but FD of eigenvalue-dependent energies is ill-conditioned).
"""

from __future__ import annotations

import numpy as np
import pytest

from mechdsl.lib.tensor_ops import green_lagrange
from mechdsl.symbolic.models.hgo import HGOMaterial
from mechdsl.symbolic.models.hgo import pk2_stress as hgo_pk2
from mechdsl.symbolic.models.mooney_rivlin import MooneyRivlinMaterial
from mechdsl.symbolic.models.mooney_rivlin import pk2_stress as mr_pk2
from mechdsl.symbolic.models.neo_hookean import NeoHookeanMaterial
from mechdsl.symbolic.models.neo_hookean import pk2_stress as nh_pk2
from mechdsl.symbolic.models.ogden import OgdenMaterial
from mechdsl.symbolic.models.ogden import pk2_stress as ogden_pk2
from mechdsl.verify.ad_oracle import (
    verify_hgo,
    verify_mooney_rivlin,
    verify_neo_hookean,
    verify_ogden,
)

_STRETCHES = np.array([0.8, 0.9, 1.0, 1.1, 1.3, 1.6, 2.0, 2.5])
_STRETCHES_TENSILE = np.array([1.0001, 1.1, 1.3, 1.6, 2.0])


def _uniaxial_F(stretch: float) -> np.ndarray:
    """Isochoric uniaxial deformation gradient with stretch along e_x (J = 1)."""
    lat = 1.0 / np.sqrt(stretch)
    return np.diag([stretch, lat, lat]).astype(np.float64)


def _cauchy_dev_11_22(S: np.ndarray, F: np.ndarray) -> float:
    """Return sig_11 - sig_22 from PK2 S and deformation F (sig = F S F^T / J)."""
    J = float(np.linalg.det(F))
    sig = F @ S @ F.T / J
    return float(sig[0, 0] - sig[1, 1])


class TestTaskP4_5HyperelasticAcceptance:
    """AC-1 AD oracle (1e-6) + AC-2 uniaxial closed-form (1e-10)."""

    # ------------------------------------------------------------------
    # AC-1: AD oracle — 100 random states per model
    # ------------------------------------------------------------------

    @pytest.mark.unit
    def test_ad_oracle_neo_hookean_100_states(self) -> None:
        result = verify_neo_hookean({"mu": 1.0, "kappa": 2.0}, n_samples=100)
        assert result["all_passed"], f"NH AD oracle failed: {result}"
        assert result["max_stress_error"] < 1e-6

    @pytest.mark.unit
    def test_ad_oracle_mooney_rivlin_100_states(self) -> None:
        result = verify_mooney_rivlin({"C1": 0.5, "C2": 0.2, "kappa": 2.0}, n_samples=100)
        assert result["all_passed"], f"MR AD oracle failed: {result}"
        assert result["max_stress_error"] < 1e-6

    @pytest.mark.unit
    def test_ad_oracle_ogden_100_states(self) -> None:
        result = verify_ogden(
            {"mus": (1.2, -0.1), "alphas": (2.0, -2.0), "kappa": 10.0},
            n_samples=100,
            eig_sep_cutoff=1e-4,
        )
        assert result["all_passed"], f"Ogden AD oracle failed: {result}"
        assert result["max_stress_error"] < 1e-6
        # Document the exclusion count — typically ~0 for random F, but the
        # sampler remains robust if the user chooses pathological params.
        assert "n_skipped_near_degenerate" in result

    @pytest.mark.unit
    def test_ad_oracle_hgo_100_states(self) -> None:
        result = verify_hgo(
            {
                "mu": 30.0,
                "k1": 100.0,
                "k2": 1.0,
                "kappa": 1000.0,
                "fiber_dispersion": 0.1,
            },
            n_samples=100,
        )
        assert result["all_passed"], f"HGO AD oracle failed: {result}"
        assert result["max_stress_error"] < 1e-6

    # ------------------------------------------------------------------
    # AC-2: uniaxial closed form
    # ------------------------------------------------------------------

    @pytest.mark.unit
    def test_uniaxial_closed_form_neo_hookean(self) -> None:
        mat = NeoHookeanMaterial(mu=1.0, kappa=1.0e6)  # near-incompressible
        for lam in _STRETCHES:
            F = _uniaxial_F(float(lam))
            E = green_lagrange(F)
            S = nh_pk2(mat, E)
            dev = _cauchy_dev_11_22(S, F)
            closed = mat.mu * (lam**2 - 1.0 / lam)
            assert abs(dev - closed) < 1e-10, (
                f"NH uniaxial mismatch at λ={lam}: dev={dev}, closed={closed}"
            )

    @pytest.mark.unit
    def test_uniaxial_closed_form_mooney_rivlin(self) -> None:
        mat = MooneyRivlinMaterial(C1=0.5, C2=0.2, kappa=1.0e6)
        for lam in _STRETCHES:
            F = _uniaxial_F(float(lam))
            E = green_lagrange(F)
            S = mr_pk2(mat, E)
            dev = _cauchy_dev_11_22(S, F)
            closed = 2.0 * (mat.C1 + mat.C2 / lam) * (lam**2 - 1.0 / lam)
            assert abs(dev - closed) < 1e-10, (
                f"MR uniaxial mismatch at λ={lam}: dev={dev}, closed={closed}"
            )

    @pytest.mark.unit
    def test_uniaxial_closed_form_ogden(self) -> None:
        # Treloar-class N=3 params; avoid λ=1 exactly (triple-degenerate,
        # eigenvector ambiguity flips bracketed deviator to zero either way).
        mus = (0.69, 0.01, -0.0122)
        alphas = (1.3, 5.0, -2.0)
        mat = OgdenMaterial(mus=mus, alphas=alphas, kappa=1.0e6)
        for lam in _STRETCHES:
            if abs(lam - 1.0) < 1e-6:
                continue
            F = _uniaxial_F(float(lam))
            E = green_lagrange(F)
            S = ogden_pk2(mat, E)
            dev = _cauchy_dev_11_22(S, F)
            closed = sum(
                mu_p * (lam**alpha_p - lam ** (-alpha_p / 2.0))
                for mu_p, alpha_p in zip(mus, alphas, strict=True)
            )
            assert abs(dev - closed) < 1e-10, (
                f"Ogden uniaxial mismatch at λ={lam}: dev={dev}, closed={closed}"
            )

    @pytest.mark.unit
    def test_uniaxial_closed_form_hgo(self) -> None:
        # Aligned fibers (κ_disp=0): a1 along stretch, a2 perpendicular and
        # inactive for λ>1 (E_f2 = 1/λ - 1 < 0). Tensile range only.
        mat = HGOMaterial(mu=30.0, k1=100.0, k2=1.0, kappa=1.0e6, fiber_dispersion=0.0)
        a1 = np.array([1.0, 0.0, 0.0])
        a2 = np.array([0.0, 1.0, 0.0])
        for lam in _STRETCHES_TENSILE:
            F = _uniaxial_F(float(lam))
            E = green_lagrange(F)
            S = hgo_pk2(mat, E, (a1, a2))
            dev = _cauchy_dev_11_22(S, F)
            E_f1 = lam**2 - 1.0
            fiber = 2.0 * mat.k1 * lam**2 * E_f1 * np.exp(mat.k2 * E_f1 * E_f1)
            closed = mat.mu * (lam**2 - 1.0 / lam) + fiber
            # Relative tolerance: fiber exponential stiffening drives abs
            # magnitude to O(1e7) at λ=2, so abs tol would be dominated by
            # floating-point roundoff (~1e-8 relative) rather than modelling
            # error. Rel tol 1e-10 is equivalent to abs tol 1e-10 in the
            # low-stress regime and loosens proportionally as stress grows.
            ref = max(abs(closed), 1.0)
            assert abs(dev - closed) / ref < 1e-10, (
                f"HGO uniaxial mismatch at λ={lam}: dev={dev}, closed={closed}"
            )
