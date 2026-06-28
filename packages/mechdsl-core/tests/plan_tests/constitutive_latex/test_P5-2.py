"""Tests for Task P5-2: HGO energy via i4/i5 + diff-test (fiber gating).

A LaTeX-authored HGO energy (``dev/examples/hgo_energy.tex``)

    Psi = (mu/2)(Ibar1 - 3) + (kappa/2)(Jdet - 1)^2
        + (k1/2k2)(exp(k2 (Ibar4 - 1)^2) - 1)

is derived through ``symbolic/anisotropic_energy.derive_from_anisotropic_energy``:
the isotropic+volumetric part is differentiated w.r.t. E (the proven Neo-Hookean
path), and the fiber template binds ``Ibar4 -> I3^{-1/3}(a . C . a)`` with
symbolic fiber components and is differentiated to the active-branch fiber
stress. The model applies the fiber template to each declared fiber direction,
gating each by the Macaulay bracket ``<Ibar4 - 1>`` (active only in tension,
Ibar4 > 1), and differential-tested vs ``models/hgo.py`` (fiber_dispersion=0) to
< 1e-8. The tangent is FD, matching the oracle.

Acceptance criteria:
- AC-1: HGO matches hgo.py < 1e-8 at random strains with fiber directions supplied.
- AC-2: Fiber-gating (Ibar4 > 1) branch correct; gated-off branch returns
  isotropic-only stress.
- AC-3: Tangent within FD tolerance (codegen emission of the fiber gather +
  gated exponential is not in the MVP Taichi backend and is deferred).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from mechdsl.symbolic.anisotropic_energy import (
    AnisotropicEnergyModel,
    derive_from_anisotropic_energy,
)
from mechdsl.symbolic.energy import EnergyDerivationError, derive_from_energy
from mechdsl.symbolic.models.hgo import (
    HGOMaterial,
)
from mechdsl.symbolic.models.hgo import (
    material_tangent_voigt as hgo_tangent_voigt,
)
from mechdsl.symbolic.models.hgo import (
    pk2_stress as hgo_pk2_stress,
)

_EXAMPLES_DIR = Path(__file__).resolve().parents[5] / "dev" / "examples"
_HGO_TEX = _EXAMPLES_DIR / "hgo_energy.tex"

_MU, _K1, _K2, _KAPPA = 30.0, 5.0, 8.0, 200.0
_PARAMS = {"mu": _MU, "k1": _K1, "k2": _K2, "kappa": _KAPPA}
# fiber_dispersion = 0 -> E_fi = Ibar4 - 1, exactly the authored energy.
_MAT = HGOMaterial(mu=_MU, k1=_K1, k2=_K2, kappa=_KAPPA, fiber_dispersion=0.0)
_N_SAMPLES = 20
_FD_TANGENT_TOL = 1e-6


def _unit(v: np.ndarray) -> np.ndarray:
    return v / np.linalg.norm(v)


def _E(F: np.ndarray) -> np.ndarray:
    return 0.5 * (F.T @ F - np.eye(3))


@pytest.fixture(scope="module")
def hgo_energy() -> AnisotropicEnergyModel:
    """Derive the HGO AnisotropicEnergyModel once for the module."""
    return derive_from_anisotropic_energy(_HGO_TEX.read_text())


class TestTaskP5_2:
    """Tests for Task P5-2: HGO energy via i4/i5 + diff-test (fiber gating).
    AC covered: 1, 2, 3."""

    # ------------------------------------------------------------------
    # AC-1: derived HGO stress matches oracle at random F (mixed gating)
    # ------------------------------------------------------------------

    @pytest.mark.integration
    def test_derived_hgo_matches_oracle_two_families(self, hgo_energy: AnisotropicEnergyModel):
        """Verifies: derived HGO stress (two fiber families, per-fiber gating)
        matches the oracle at N random F.
        AC: AC-1 + AC-2 (gating) + two families combine.
        Passes when: derived S agrees with hgo.py (fiber_dispersion=0) to < 1e-8
        across random states that exercise both gated-on and gated-off fibers."""
        model = hgo_energy
        a1, a2 = np.array([1.0, 0.0, 0.0]), _unit(np.array([0.3, 1.0, 0.2]))
        rng = np.random.default_rng(20260604)
        max_rel = 0.0
        for _ in range(_N_SAMPLES):
            F = np.eye(3) + 0.08 * rng.standard_normal((3, 3))
            E = _E(F)
            S_derived = model.pk2_stress(E, (a1, a2), _PARAMS)
            S_oracle = hgo_pk2_stress(_MAT, E, (a1, a2))
            scale = max(1.0, float(np.max(np.abs(S_oracle))))
            max_rel = max(max_rel, float(np.max(np.abs(S_derived - S_oracle)) / scale))
        assert max_rel < 1e-8, f"derived vs hgo.py stress max rel-err {max_rel:.3e} >= 1e-8"

    @pytest.mark.integration
    def test_zero_stress_at_identity(self, hgo_energy: AnisotropicEnergyModel):
        """Verifies: stress vanishes at F = I (Ibar1=3, Jdet=1, Ibar4=1 -> fibers
        gated off, E_fi=0).
        AC: AC-1 (physical consistency)."""
        model = hgo_energy
        S = model.pk2_stress(
            np.zeros((3, 3)), (np.array([1.0, 0, 0]), np.array([0, 1.0, 0])), _PARAMS
        )
        assert np.max(np.abs(S)) < 1e-9

    # ------------------------------------------------------------------
    # AC-2: gated-on vs gated-off branches
    # ------------------------------------------------------------------

    @pytest.mark.integration
    def test_fiber_gated_on_stiffens_along_fiber(self, hgo_energy: AnisotropicEnergyModel):
        """Verifies: stretching ALONG the fiber (Ibar4 > 1) activates the fiber
        term — the derived stress matches the oracle's gated-on branch and is
        strictly stiffer than the isotropic-only stress along the fiber axis.
        AC: AC-2 (gated-on)."""
        model = hgo_energy
        a1 = np.array([1.0, 0.0, 0.0])
        # Isochoric uniaxial stretch along x (fiber a1): lambda = 1.3 in tension.
        F = np.diag([1.3, 1.0 / np.sqrt(1.3), 1.0 / np.sqrt(1.3)])
        E = _E(F)
        flat = [E[i, j] for i in range(3) for j in range(3)]
        assert float(model._ibar4_fn(*flat, *a1)) > 1.0, "fiber should be in tension"

        # Both sides use the same two fiber directions (here both = a1).
        S_derived = model.pk2_stress(E, (a1, a1), _PARAMS)
        S_oracle = hgo_pk2_stress(_MAT, E, (a1, a1))
        scale = max(1.0, float(np.max(np.abs(S_oracle))))
        assert float(np.max(np.abs(S_derived - S_oracle)) / scale) < 1e-8

        # The active fiber adds stress beyond the isotropic-only response along x.
        S_iso_only = model.pk2_stress(E, (), _PARAMS)
        assert S_derived[0, 0] > S_iso_only[0, 0] + 1e-6, "active fiber must stiffen along its axis"

    @pytest.mark.integration
    def test_gated_off_returns_isotropic_only(self, hgo_energy: AnisotropicEnergyModel):
        """Verifies: when every fiber is in compression (Ibar4 <= 1) the fiber
        terms are gated off and the stress equals the isotropic+volumetric
        (Neo-Hookean) part — and matches the oracle (which also returns 0 fiber).
        AC: AC-2 (gated-off)."""
        model = hgo_energy
        # Compress along x so a fiber aligned with x has Ibar4 < 1.
        a1 = np.array([1.0, 0.0, 0.0])
        F = np.diag([0.8, 1.0 / np.sqrt(0.8), 1.0 / np.sqrt(0.8)])
        E = _E(F)
        flat = [E[i, j] for i in range(3) for j in range(3)]
        assert float(model._ibar4_fn(*flat, *a1)) <= 1.0, "fiber should be compressed"

        S_derived = model.pk2_stress(E, (a1, a1), _PARAMS)
        # Isotropic-only: no fibers supplied -> pure iso+vol stress.
        S_iso_only = model.pk2_stress(E, (), _PARAMS)
        assert np.allclose(S_derived, S_iso_only, atol=1e-10), "gated-off must equal iso-only"
        # And matches the oracle (fibers gated off there too).
        S_oracle = hgo_pk2_stress(_MAT, E, (a1, a1))
        scale = max(1.0, float(np.max(np.abs(S_oracle))))
        assert float(np.max(np.abs(S_derived - S_oracle)) / scale) < 1e-8

    # ------------------------------------------------------------------
    # AC-1b: isotropic part equals Neo-Hookean (mu, kappa) when fibers off
    # ------------------------------------------------------------------

    @pytest.mark.integration
    def test_isotropic_part_is_neo_hookean(self, hgo_energy: AnisotropicEnergyModel):
        """Verifies: the derived HGO isotropic+volumetric stress (no active
        fibers) equals the Neo-Hookean oracle with the same (mu, kappa).
        AC: AC-1 (the iso split is the proven NH path)."""
        from mechdsl.symbolic.models.neo_hookean import NeoHookeanMaterial
        from mechdsl.symbolic.models.neo_hookean import pk2_stress as nh_pk2

        model = hgo_energy
        nh = NeoHookeanMaterial(mu=_MU, kappa=_KAPPA)
        rng = np.random.default_rng(7)
        max_rel = 0.0
        for _ in range(10):
            F = np.eye(3) + 0.05 * rng.standard_normal((3, 3))
            E = _E(F)
            S_iso = model.pk2_stress(E, (), _PARAMS)
            S_nh = nh_pk2(nh, E)
            scale = max(1.0, float(np.max(np.abs(S_nh))))
            max_rel = max(max_rel, float(np.max(np.abs(S_iso - S_nh)) / scale))
        assert max_rel < 1e-8, f"HGO iso part vs Neo-Hookean rel-err {max_rel:.3e}"

    # ------------------------------------------------------------------
    # AC-3: FD tangent matches the oracle within tolerance
    # ------------------------------------------------------------------

    @pytest.mark.integration
    def test_derived_tangent_matches_oracle(self, hgo_energy: AnisotropicEnergyModel):
        """Verifies: the derived FD tangent (6x6 Voigt) matches hgo.py's FD
        tangent within tolerance.
        AC: AC-3.
        Passes when: derived tangent agrees with the oracle 6x6 Voigt to within
        the FD tolerance at N random F (both compared via tangent_to_voigt_66)."""
        model = hgo_energy
        a1, a2 = np.array([1.0, 0.0, 0.0]), _unit(np.array([0.3, 1.0, 0.2]))
        rng = np.random.default_rng(20260604)
        max_rel = 0.0
        for _ in range(_N_SAMPLES):
            F = np.eye(3) + 0.08 * rng.standard_normal((3, 3))
            E = _E(F)
            D_derived = model.material_tangent_voigt(E, (a1, a2), _PARAMS)
            D_oracle = hgo_tangent_voigt(_MAT, E, (a1, a2))
            scale = max(1.0, float(np.max(np.abs(D_oracle))))
            max_rel = max(max_rel, float(np.max(np.abs(D_derived - D_oracle)) / scale))
        assert max_rel < _FD_TANGENT_TOL, (
            f"derived vs hgo.py tangent max rel-err {max_rel:.3e} >= {_FD_TANGENT_TOL}"
        )

    # ------------------------------------------------------------------
    # IR discipline: the two derivation paths reject each other's energies
    # ------------------------------------------------------------------

    @pytest.mark.unit
    def test_anisotropic_path_rejects_isotropic_energy(self):
        """Verifies: an isotropic energy (no Ibar4) fed to the anisotropic path
        raises with a pointer to derive_from_energy.
        AC: AC-3 (IR discipline)."""
        nh_tex = (_EXAMPLES_DIR / "neo_hookean_energy.tex").read_text()
        with pytest.raises(EnergyDerivationError, match="derive_from_energy"):
            derive_from_anisotropic_energy(nh_tex)

    @pytest.mark.unit
    def test_isotropic_path_rejects_fiber_invariant(self):
        """Verifies: the HGO energy (with Ibar4) fed to the isotropic path raises
        (Ibar4 is a fiber invariant, unsupported there) rather than silently
        producing a wrong result.
        AC: AC-3 (IR discipline)."""
        with pytest.raises(EnergyDerivationError):
            derive_from_energy(_HGO_TEX.read_text())
