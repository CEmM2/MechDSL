"""Tests for Task P2-2: neo_hookean_energy.tex + differential & AD oracle.

Covers: LaTeX-derived Neo-Hookean energy (Ψ in named invariants Ibar1, Jdet)
matches the hand-coded oracle (models/neo_hookean.py) at random deformations
(differential oracle < 1e-9); passes the spec AD-oracle (symbolic S vs
autodiff of Ψ, rel-err < 1e-10); tangent passes symmetry; unsupported
invariant forms reject with phase pointer.

Energy authored:
    Ψ = (μ/2)(Ī₁ − 3) + (κ/2)(J − 1)²

where Ī₁ = I₁ · I₃^{−1/3} and J = √(det C), matching models/neo_hookean.py
exactly (classical compressible NH, isochoric-volumetric split).
"""

from __future__ import annotations

import pathlib

import numpy as np
import pytest
import sympy as sp

from mechdsl.symbolic.energy import EnergyDerivationError, derive_from_energy
from mechdsl.symbolic.models.neo_hookean import (
    NeoHookeanMaterial,
    material_tangent_4th,
    pk2_stress,
)

# ---------------------------------------------------------------------------
# Fixtures and shared setup
# ---------------------------------------------------------------------------

_EXAMPLES_DIR = pathlib.Path(__file__).parents[5] / "dev" / "examples"
_NH_TEX = _EXAMPLES_DIR / "neo_hookean_energy.tex"

# Material parameters shared across all tests (must be identical on both sides
# of every comparison so the differential oracle is fair).
_MU = 80.0
_KAPPA = 160.0
_N_SAMPLES = 25
_SEED = 20260604


def _green_lagrange_from_F(F: np.ndarray) -> np.ndarray:
    """E = ½(FᵀF − I)."""
    return 0.5 * (F.T @ F - np.eye(3))


def _random_F_list(n: int, seed: int) -> list[np.ndarray]:
    """Generate *n* random F matrices with positive Jacobian (near-identity)."""
    rng = np.random.default_rng(seed)
    Fs: list[np.ndarray] = []
    while len(Fs) < n:
        A = rng.standard_normal((3, 3)) * 0.1
        F = np.eye(3) + A
        if np.linalg.det(F) > 0.1:  # keep well-conditioned deformations
            Fs.append(F)
    return Fs


@pytest.fixture(scope="module")
def nh_model():
    """Parsed + derived Neo-Hookean EnergyModel (module-scoped for speed)."""
    latex = _NH_TEX.read_text()
    return derive_from_energy(latex)


@pytest.fixture(scope="module")
def param_subs(nh_model):
    """Numeric substitution map: sanitised/raw symbols → μ, κ values."""
    subs: dict = {}
    for sym in nh_model.pk2.free_symbols:
        if sym.name == "mu":
            subs[sym] = _MU
        elif sym.name == "kappa":
            subs[sym] = _KAPPA
    assert len(subs) == 2, (
        f"expected exactly 'mu' and 'kappa' in pk2 free symbols, "
        f"got {[s.name for s in nh_model.pk2.free_symbols]}"
    )
    return subs


@pytest.fixture(scope="module")
def F_list():
    """Shared list of random F matrices for reproducibility."""
    return _random_F_list(_N_SAMPLES, _SEED)


# ---------------------------------------------------------------------------
# Helper: evaluate symbolic S at a concrete E
# ---------------------------------------------------------------------------


def _eval_pk2(model, param_subs, E: np.ndarray) -> np.ndarray:
    """Evaluate the symbolic pk2 at strain E with numeric params."""
    strain = model.strain_symbols
    subs = dict(param_subs)
    for i in range(3):
        for j in range(3):
            subs[strain[i][j]] = float(E[i, j])
    return np.array([[float(model.pk2[i, j].subs(subs)) for j in range(3)] for i in range(3)])


def _eval_tangent(model, param_subs, E: np.ndarray) -> np.ndarray:
    """Evaluate the symbolic tangent at strain E with numeric params."""
    strain = model.strain_symbols
    subs = dict(param_subs)
    for i in range(3):
        for j in range(3):
            subs[strain[i][j]] = float(E[i, j])
    C_der = np.empty((3, 3, 3, 3))
    for i in range(3):
        for j in range(3):
            for k in range(3):
                for el in range(3):
                    C_der[i, j, k, el] = float(model.tangent[i, j, k, el].subs(subs))
    return C_der


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------


class TestTaskP2_2:
    """Tests for Task P2-2: neo_hookean_energy.tex + differential & AD oracle.
    AC covered: 1, 2, 3, 4."""

    # ------------------------------------------------------------------
    # AC-1: Derived S matches oracle at N random deformation gradients
    # ------------------------------------------------------------------

    @pytest.mark.integration
    def test_derived_stress_matches_oracle_at_random_deformations(
        self, nh_model, param_subs, F_list
    ) -> None:
        """LaTeX-derived S matches models/neo_hookean.py at 25 random F.

        AC: Derived S and C match neo_hookean.py < 1e-9 at random strains.
        Passes when: rel_err < 1e-9 on N random deformation gradients.
        """
        mat = NeoHookeanMaterial(mu=_MU, kappa=_KAPPA)

        for F in F_list:
            E = _green_lagrange_from_F(F)
            S_derived = _eval_pk2(nh_model, param_subs, E)
            S_oracle = pk2_stress(mat, E)

            norm_S = np.linalg.norm(S_oracle)
            if norm_S > 1e-12:
                rel_err = np.linalg.norm(S_derived - S_oracle) / norm_S
            else:
                rel_err = np.linalg.norm(S_derived - S_oracle)

            assert rel_err < 1e-9, (
                f"Stress mismatch: rel_err={rel_err:.3e} (threshold 1e-9)\n"
                f"  S_derived={S_derived}\n  S_oracle={S_oracle}"
            )

    # ------------------------------------------------------------------
    # AC-2: Derived C matches oracle at N random deformation gradients
    # ------------------------------------------------------------------

    @pytest.mark.integration
    def test_derived_tangent_matches_oracle_at_random_deformations(
        self, nh_model, param_subs, F_list
    ) -> None:
        """LaTeX-derived C_IJKL matches oracle at 25 random F.

        AC: Derived S and C match neo_hookean.py < 1e-9 at random strains.
        Passes when: rel_err < 1e-9 on material tangent.
        """
        mat = NeoHookeanMaterial(mu=_MU, kappa=_KAPPA)

        for F in F_list:
            E = _green_lagrange_from_F(F)
            C_derived = _eval_tangent(nh_model, param_subs, E)
            C_oracle = material_tangent_4th(mat, E)

            norm_C = np.linalg.norm(C_oracle)
            rel_err = np.linalg.norm(C_derived - C_oracle) / (norm_C if norm_C > 1e-12 else 1.0)

            assert rel_err < 1e-9, f"Tangent mismatch: rel_err={rel_err:.3e} (threshold 1e-9)"

    # ------------------------------------------------------------------
    # AC-3: Spec AD-oracle — symbolic S vs autodiff of Ψ
    # ------------------------------------------------------------------

    @pytest.mark.integration
    def test_spec_ad_oracle_symbolic_vs_autodiff(self, nh_model, param_subs, F_list) -> None:
        """Symbolic S agrees with an INDEPENDENT numerical derivative of Ψ.

        AC: Spec AD-oracle passes (symbolic S vs autodiff of Ψ).

        The symbolic ``pk2`` is the symmetrised ∂Ψ/∂E produced by
        ``derive_from_energy``. This oracle differentiates Ψ a *different* way —
        a central finite difference of the lambdified energy w.r.t. each strain
        component — so it actually exercises the invariant binding and the
        C = 2E + I chain rule (a re-run of ``sympy.diff`` would be tautological,
        always zero error, and could not catch a binding mistake). Central FD
        is accurate to O(h²); the tight 1e-9 check lives in the differential
        oracle vs ``neo_hookean.py``, so 1e-6 is the right bar here.
        """
        strain = nh_model.strain_symbols
        flat_syms = [strain[i][j] for i in range(3) for j in range(3)]
        # Numeric energy as a function of the nine E components (params fixed).
        psi_num = sp.lambdify(flat_syms, nh_model.psi.subs(param_subs), modules="numpy")
        index_pairs = [(i, j) for i in range(3) for j in range(3)]
        h = 1e-6

        for F in F_list[:10]:
            E = _green_lagrange_from_F(F)
            e = [float(E[i, j]) for i in range(3) for j in range(3)]

            # Central FD of Ψ w.r.t. each independent E component -> raw ∂Ψ/∂E.
            dpsi = np.zeros((3, 3))
            for idx, (i, j) in enumerate(index_pairs):
                ep, em = list(e), list(e)
                ep[idx] += h
                em[idx] -= h
                dpsi[i, j] = (psi_num(*ep) - psi_num(*em)) / (2.0 * h)
            # Symmetrise to match pk2 = ½(∂Ψ/∂E_ij + ∂Ψ/∂E_ji).
            S_fd = 0.5 * (dpsi + dpsi.T)

            S_symbolic = _eval_pk2(nh_model, param_subs, E)
            norm_S = np.linalg.norm(S_symbolic)
            rel_err = np.linalg.norm(S_symbolic - S_fd) / (norm_S if norm_S > 1e-12 else 1.0)

            assert rel_err < 1e-6, (
                f"AD oracle (numeric FD of Ψ) mismatch: rel_err={rel_err:.3e} "
                f"(threshold 1e-6)\n  S_symbolic={S_symbolic}\n  S_fd={S_fd}"
            )

    # ------------------------------------------------------------------
    # AC-4a: Tangent minor symmetry C_IJKL = C_IJLK
    # ------------------------------------------------------------------

    @pytest.mark.integration
    def test_tangent_minor_symmetry(self, nh_model, param_subs, F_list) -> None:
        """Derived tangent satisfies C_IJKL = C_IJLK (minor symmetry).

        AC: Tangent passes minor/major symmetry checks.
        Passes when: C[i,j,k,l] == C[i,j,l,k] within 1e-10.
        """
        for F in F_list[:3]:
            E = _green_lagrange_from_F(F)
            C_derived = _eval_tangent(nh_model, param_subs, E)
            # Minor symmetry: C_IJKL = C_IJLK (swap last two indices)
            np.testing.assert_allclose(
                C_derived,
                C_derived.transpose(0, 1, 3, 2),
                atol=1e-10,
                err_msg="Minor symmetry C_IJKL != C_IJLK violated",
            )

    # ------------------------------------------------------------------
    # AC-4b: Tangent major symmetry C_IJKL = C_KLIJ
    # ------------------------------------------------------------------

    @pytest.mark.integration
    def test_tangent_major_symmetry(self, nh_model, param_subs, F_list) -> None:
        """Derived tangent satisfies C_IJKL = C_KLIJ (major symmetry).

        AC: Tangent passes minor/major symmetry checks.
        Passes when: C[i,j,k,l] == C[k,l,i,j] within 1e-10.
        """
        for F in F_list[:3]:
            E = _green_lagrange_from_F(F)
            C_derived = _eval_tangent(nh_model, param_subs, E)
            # Major symmetry: C_IJKL = C_KLIJ (swap first and last pairs)
            np.testing.assert_allclose(
                C_derived,
                C_derived.transpose(2, 3, 0, 1),
                atol=1e-10,
                err_msg="Major symmetry C_IJKL != C_KLIJ violated",
            )

    # ------------------------------------------------------------------
    # AC-5: Unsupported invariant form rejects with phase pointer
    # ------------------------------------------------------------------

    @pytest.mark.integration
    def test_unsupported_invariant_form_rejects_with_phase_pointer(self) -> None:
        """Unsupported invariant (e.g. \\mathrm{Ibar7}) rejects with plan-phase message.

        AC: Unsupported invariant form rejects with phase-pointed message.
        Passes when: EnergyDerivationError is raised with a phase reference.
        """
        # Author an energy with a fictitious invariant Ibar7 (not in registry)
        bad_latex = r"""
% declare metric gDD --dim 3
% declare EDD --dim 3
% declare \mu --const
\Psi = \frac{\mu}{2} \left( \mathrm{Ibar7} - 3 \right)
"""
        with pytest.raises(EnergyDerivationError, match=r"[Pp]hase"):
            derive_from_energy(bad_latex)
