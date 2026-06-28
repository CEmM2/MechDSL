"""Tests for Task P4-2: Ogden via the spectral / principal-stretch path.

A LaTeX-authored two-term Ogden strain energy (``dev/examples/ogden_energy.tex``)

    Psi = (mu1/a1)(lbar1^a1 + lbar2^a1 + lbar3^a1 - 3)
        + (mu2/a2)(lbar1^a2 + lbar2^a2 + lbar3^a2 - 3)
        + (kappa/2)(Jdet - 1)^2

is parsed and derived through the new spectral path
``symbolic/spectral_energy.derive_from_spectral_energy``: the bars and Jdet are
substituted in terms of three independent stretch symbols, Psi is differentiated
w.r.t. the stretches to give the principal PK2 stresses S_i = (1/l_i) dPsi/dl_i,
and S(E) is assembled numerically by eigendecomposition. The tangent is
central-difference FD of that stress, matching ``models/ogden.py``.

Acceptance criteria:
- AC-1: Ogden matches ogden.py < 1e-8 (stress).
- AC-2: Tangent within ogden.py's documented FD-method tolerance.
- AC-3: Spectral path handled (eigenvalue derivatives, repeated/near-degenerate
  stretches) without breaking the invariant path.

The eigenvalue derivatives are singular at repeated stretches only in the
closed-form tangent; the spectral *stress* reassembly used here has no
eigenvalue-difference denominators, so it is robust at equal stretches (S_i = S_j
in the degenerate subspace; the eigenvector ambiguity cancels in the projector
sum). Taichi JIT emission of the spectral path (eigendecomposition in @ti.func)
is not in the MVP backend and is intentionally not exercised here.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from mechdsl.symbolic.energy import (
    EnergyDerivationError,
    derive_from_energy,
)
from mechdsl.symbolic.models.neo_hookean import (
    NeoHookeanMaterial,
)
from mechdsl.symbolic.models.neo_hookean import (
    pk2_stress as nh_pk2_stress,
)
from mechdsl.symbolic.models.ogden import (
    OgdenMaterial,
)
from mechdsl.symbolic.models.ogden import (
    material_tangent_voigt as ogden_tangent_voigt,
)
from mechdsl.symbolic.models.ogden import (
    pk2_stress as ogden_pk2_stress,
)
from mechdsl.symbolic.spectral_energy import (
    SpectralEnergyModel,
    derive_from_spectral_energy,
)

_EXAMPLES_DIR = Path(__file__).resolve().parents[5] / "dev" / "examples"
_OGDEN_TEX = _EXAMPLES_DIR / "ogden_energy.tex"

# Two-term compressible Ogden parameters. Authored greek -> oracle slot:
#   mu == mu1, alpha == alpha1, nu == mu2, eta == alpha2, kappa == bulk.
_MUS = (1.3, -0.2)
_ALPHAS = (1.8, -2.0)
_KAPPA = 50.0

# original LaTeX parameter name -> numeric value
_BY_ORIGINAL = {
    "mu": _MUS[0],
    "alpha": _ALPHAS[0],
    "nu": _MUS[1],
    "eta": _ALPHAS[1],
    "kappa": _KAPPA,
}

_N_SAMPLES = 15
# ogden.py computes its tangent by central-difference FD (eps=1e-6); the derived
# tangent uses the identical scheme on a mathematically-identical stress, so the
# two FD tangents agree well within the method's documented tolerance.
_FD_TANGENT_TOL = 1e-6


@pytest.fixture(scope="module")
def ogden_energy() -> SpectralEnergyModel:
    """Derive the two-term Ogden SpectralEnergyModel once for the module."""
    return derive_from_spectral_energy(_OGDEN_TEX.read_text())


def _param_values(model: SpectralEnergyModel) -> dict[str, float]:
    """Map each sanitised parameter symbol name to its numeric value via the
    sanitised->original-LaTeX rename (no sanitisation expected here, all clean)."""
    out: dict[str, float] = {}
    for sym in model.param_symbols:
        original = model.parameters.get(sym, sym.name)
        out[sym.name] = _BY_ORIGINAL[original]
    return out


def _E_from_F(F: np.ndarray) -> np.ndarray:
    return 0.5 * (F.T @ F - np.eye(3))


class TestTaskP4_2:
    """Tests for Task P4-2: Ogden spectral derive/emit/diff (FD tangent).
    AC covered: 1, 2, 3."""

    # ------------------------------------------------------------------
    # AC-1: derived spectral stress matches ogden.py at random F
    # ------------------------------------------------------------------

    @pytest.mark.integration
    def test_derived_ogden_matches_oracle_stress(self, ogden_energy: SpectralEnergyModel):
        """Verifies: PK2 stress derived from the LaTeX Ogden energy via the
        spectral path matches the hand-coded oracle.
        AC: AC-1 (< 1e-8 stress).
        Passes when: spectral S(E) agrees with ogden.py ``pk2_stress`` at N random
        well-conditioned F to < 1e-8."""
        model = ogden_energy
        pvals = _param_values(model)
        mat = OgdenMaterial(mus=_MUS, alphas=_ALPHAS, kappa=_KAPPA)
        rng = np.random.default_rng(20260604)
        max_rel = 0.0
        for _ in range(_N_SAMPLES):
            F = np.eye(3) + 0.05 * rng.standard_normal((3, 3))
            E = _E_from_F(F)
            S_derived = model.pk2_stress(E, pvals)
            S_oracle = ogden_pk2_stress(mat, E)
            scale = max(1.0, float(np.max(np.abs(S_oracle))))
            max_rel = max(max_rel, float(np.max(np.abs(S_derived - S_oracle)) / scale))
        assert max_rel < 1e-8, f"derived vs ogden.py stress max rel-err {max_rel:.3e} >= 1e-8"

    @pytest.mark.integration
    def test_zero_stress_at_identity(self, ogden_energy: SpectralEnergyModel):
        """Verifies: the spectral stress vanishes at F = I (lambda_i = 1, J = 1).
        AC: AC-1 (physical consistency).
        Passes when: S(E=0) is numerically zero."""
        model = ogden_energy
        S = model.pk2_stress(np.zeros((3, 3)), _param_values(model))
        assert np.max(np.abs(S)) < 1e-9, f"stress at identity not zero: {np.max(np.abs(S)):.3e}"

    # ------------------------------------------------------------------
    # AC-2: FD tangent matches ogden.py's FD tangent within tolerance
    # ------------------------------------------------------------------

    @pytest.mark.integration
    def test_ogden_fd_tangent_within_tolerance(self, ogden_energy: SpectralEnergyModel):
        """Verifies: the derived FD material tangent (6x6 Voigt) matches
        ``ogden.py`` ``material_tangent_voigt``.
        AC: AC-2 (within documented FD-method tolerance).
        Passes when: derived tangent agrees with the oracle 6x6 Voigt to within
        the FD tolerance at N random F (compared the SAME way, unscaled shears)."""
        model = ogden_energy
        pvals = _param_values(model)
        mat = OgdenMaterial(mus=_MUS, alphas=_ALPHAS, kappa=_KAPPA)
        rng = np.random.default_rng(20260604)
        max_rel = 0.0
        for _ in range(_N_SAMPLES):
            F = np.eye(3) + 0.05 * rng.standard_normal((3, 3))
            E = _E_from_F(F)
            D_derived = model.material_tangent_voigt(E, pvals)
            D_oracle = ogden_tangent_voigt(mat, E)
            scale = max(1.0, float(np.max(np.abs(D_oracle))))
            max_rel = max(max_rel, float(np.max(np.abs(D_derived - D_oracle)) / scale))
        assert max_rel < _FD_TANGENT_TOL, (
            f"derived vs ogden.py tangent max rel-err {max_rel:.3e} >= {_FD_TANGENT_TOL}"
        )

    # ------------------------------------------------------------------
    # AC-3a: robust at repeated / near-degenerate principal stretches
    # ------------------------------------------------------------------

    @pytest.mark.integration
    def test_repeated_eigenvalue_robustness(self, ogden_energy: SpectralEnergyModel):
        """Verifies: the spectral stress is finite and matches the oracle at
        repeated and near-degenerate stretches (where a closed-form spectral
        tangent would be singular).
        AC: AC-3 (eigenvalue path handled).
        Passes when: hydrostatic (all stretches equal), two-equal, and
        near-degenerate diagonal F all match ogden.py < 1e-8 and the hydrostatic
        stress is isotropic."""
        model = ogden_energy
        pvals = _param_values(model)
        mat = OgdenMaterial(mus=_MUS, alphas=_ALPHAS, kappa=_KAPPA)

        cases = {
            "hydrostatic": np.diag([1.1, 1.1, 1.1]),
            "two-equal": np.diag([1.2, 1.05, 1.05]),
            "near-degenerate": np.diag([1.1, 1.1 + 1e-7, 1.05]),
        }
        for name, F in cases.items():
            E = _E_from_F(F)
            S_derived = model.pk2_stress(E, pvals)
            S_oracle = ogden_pk2_stress(mat, E)
            assert np.all(np.isfinite(S_derived)), f"{name}: non-finite stress"
            scale = max(1.0, float(np.max(np.abs(S_oracle))))
            rel = float(np.max(np.abs(S_derived - S_oracle)) / scale)
            assert rel < 1e-8, f"{name}: derived vs oracle {rel:.3e} >= 1e-8"

        # Hydrostatic stretch -> isotropic stress (S = s * I).
        E_hydro = _E_from_F(cases["hydrostatic"])
        S_hydro = model.pk2_stress(E_hydro, pvals)
        off_diag = S_hydro - np.diag(np.diag(S_hydro))
        assert np.max(np.abs(off_diag)) < 1e-9, "hydrostatic stress not diagonal"
        assert np.allclose(np.diag(S_hydro), S_hydro[0, 0], atol=1e-9), (
            "hydrostatic stress not isotropic"
        )

    # ------------------------------------------------------------------
    # AC-3b: the invariant / component path is unbroken by the spectral addition
    # ------------------------------------------------------------------

    @pytest.mark.integration
    def test_invariant_path_unbroken(self):
        """Verifies: adding the spectral path did not break the named-invariant
        derivation (Neo-Hookean still derives + matches its oracle).
        AC: AC-3 (without breaking the invariant path).
        Passes when: a Neo-Hookean energy authored in named invariants still
        derives through ``derive_from_energy`` and matches neo_hookean.py < 1e-8."""
        import sympy as sp

        nh_tex = (_EXAMPLES_DIR / "neo_hookean_energy.tex").read_text()
        model = derive_from_energy(nh_tex)
        params = sorted(
            (s for s in model.pk2.free_symbols if not s.name.startswith("EDD")),
            key=lambda s: s.name,
        )
        strain = model.strain_symbols
        flat = [strain[i][j] for i in range(3) for j in range(3)]
        pk2_fn = sp.lambdify((*flat, *params), model.pk2, "numpy")

        mu, kappa = 80.0, 160.0
        by_name = {"mu": mu, "kappa": kappa}
        pvals = [by_name[p.name] for p in params]
        mat = NeoHookeanMaterial(mu=mu, kappa=kappa)
        rng = np.random.default_rng(20260604)
        max_rel = 0.0
        for _ in range(10):
            F = np.eye(3) + 0.05 * rng.standard_normal((3, 3))
            E = _E_from_F(F)
            args = [E[i, j] for i in range(3) for j in range(3)]
            S_derived = np.array(pk2_fn(*args, *pvals), dtype=np.float64)
            S_oracle = nh_pk2_stress(mat, E)
            scale = max(1.0, float(np.max(np.abs(S_oracle))))
            max_rel = max(max_rel, float(np.max(np.abs(S_derived - S_oracle)) / scale))
        assert max_rel < 1e-8, f"invariant path regressed: NH rel-err {max_rel:.3e} >= 1e-8"

    # ------------------------------------------------------------------
    # IR discipline: the two derivation paths reject each other's energies
    # ------------------------------------------------------------------

    @pytest.mark.unit
    def test_spectral_path_rejects_non_spectral_energy(self):
        """Verifies: feeding an invariant-authored energy (no principal-stretch
        symbol) to the spectral path raises with a pointer to derive_from_energy.
        AC: AC-3 (IR discipline — unsupported construct raises, not guesses)."""
        nh_tex = (_EXAMPLES_DIR / "neo_hookean_energy.tex").read_text()
        with pytest.raises(EnergyDerivationError, match="derive_from_energy"):
            derive_from_spectral_energy(nh_tex)

    @pytest.mark.unit
    def test_invariant_path_rejects_spectral_symbols(self):
        """Verifies: feeding a principal-stretch energy to the invariant path
        raises (lbar symbols are unresolved there) rather than silently
        producing a wrong (zero-contribution) result.
        AC: AC-3 (IR discipline)."""
        ogden_tex = _OGDEN_TEX.read_text()
        with pytest.raises(EnergyDerivationError):
            derive_from_energy(ogden_tex)

    @pytest.mark.unit
    def test_mistyped_stretch_symbol_is_rejected(self):
        """Verifies: a mistyped principal stretch (``lbar4`` — not 1/2/3, and not
        a declared --const) raises instead of being silently absorbed as a
        phantom parameter that contributes nothing to the stress.
        AC: AC-3 (IR discipline — unsupported construct must raise)."""
        bad_tex = (
            "% declare metric gDD --dim 3\n"
            "% declare EDD --dim 3\n"
            "% declare \\mu \\alpha \\kappa --const\n"
            r"\Psi = \frac{\mu}{\alpha}\left(\mathrm{lbar1}^{\alpha} + "
            r"\mathrm{lbar2}^{\alpha} + \mathrm{lbar4}^{\alpha} - 3\right) + "
            r"\frac{\kappa}{2}\left(\mathrm{Jdet} - 1\right)^{2}"
        )
        with pytest.raises(EnergyDerivationError, match="lbar4"):
            derive_from_spectral_energy(bad_tex)
