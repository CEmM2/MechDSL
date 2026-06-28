"""Validate the LaTeX strain-energy auto-diff engine against the hand-coded
SVK oracle (symbolic/models/svk.py).

This is the front-half proof of the LaTeX-to-code constitutive slice: an SVK
energy authored in LaTeX, parsed and differentiated by symbolic.energy, must
reproduce the hand-written closed-form PK2 stress and material tangent at
arbitrary deformation states. Per the validation plan, the hand-coded model
is the differential-test oracle; because the energy is the only input, the
spec's AD oracle (S vs autodiff of Psi) coincides with this comparison.
"""

from __future__ import annotations

import numpy as np
import pytest
import sympy as sp

from mechdsl.symbolic.energy import derive_from_energy
from mechdsl.symbolic.models.svk import (
    SVKMaterial,
    material_tangent_4th,
    pk2_stress,
)

# SVK energy: lambda collides with the Python keyword -> exercises the
# \aleph sanitisation path; mu is already safe.
_SVK_ENERGY = r"""
% declare metric gDD --dim 3
% declare EDD --dim 3
% declare \lambda \mu --const
\Psi = \frac{\lambda}{2} E^{I}_{I} E^{J}_{J} + \mu E^{I J} E_{I J}
"""

_LAM = 115384.6153846154  # E=200e3, nu=0.3
_MU = 76923.07692307692


@pytest.fixture(scope="module")
def svk_model():
    return derive_from_energy(_SVK_ENERGY)


def _param_subs(model) -> dict:
    """Map the engine's (sanitised) parameter symbols to numeric Lame values."""
    subs: dict = {}
    for sym, original in model.parameters.items():
        if original == "lambda":
            subs[sym] = _LAM
    # mu is unsanitised -> a bare symbol named "mu".
    mu_syms = [s for s in model.pk2.free_symbols if s.name == "mu"]
    assert mu_syms, "expected a 'mu' parameter symbol in the derived stress"
    subs[mu_syms[0]] = _MU
    return subs


def test_lambda_is_sanitised_to_aleph(svk_model):
    """The colliding name lambda must be carried as the Hebrew placeholder."""
    originals = set(svk_model.parameters.values())
    assert "lambda" in originals
    placeholder_names = {s.name for s in svk_model.parameters}
    assert placeholder_names == {"aleph"}


def test_derived_stress_matches_svk_oracle(svk_model):
    """Derived S(E) matches svk.py at N random Green-Lagrange strains."""
    mat = SVKMaterial(lam=_LAM, mu=_MU)
    param_subs = _param_subs(svk_model)
    strain = svk_model.strain_symbols
    rng = np.random.default_rng(20260603)

    for _ in range(25):
        A = rng.standard_normal((3, 3)) * 0.1
        E = 0.5 * (A + A.T)  # symmetric strain
        subs = dict(param_subs)
        for i in range(3):
            for j in range(3):
                subs[strain[i][j]] = float(E[i, j])
        S_derived = np.array(
            [[float(svk_model.pk2[i, j].subs(subs)) for j in range(3)] for i in range(3)]
        )
        S_oracle = pk2_stress(mat, E)
        assert np.allclose(S_derived, S_oracle, atol=1e-9, rtol=0.0)


def test_derived_tangent_matches_svk_oracle(svk_model):
    """Derived C_IJKL = d2Psi/dE dE matches svk.py's constant tangent."""
    mat = SVKMaterial(lam=_LAM, mu=_MU)
    param_subs = _param_subs(svk_model)
    C_oracle = material_tangent_4th(mat)

    C_derived = np.empty((3, 3, 3, 3))
    for i in range(3):
        for j in range(3):
            for k in range(3):
                for el in range(3):
                    C_derived[i, j, k, el] = float(svk_model.tangent[i, j, k, el].subs(param_subs))
    assert np.allclose(C_derived, C_oracle, atol=1e-9, rtol=0.0)


def test_energy_is_scalar(svk_model):
    """Psi must be a scalar (no free tensor indices survive)."""
    assert svk_model.psi.free_symbols  # has params + strain
    assert not isinstance(svk_model.psi, sp.MatrixBase)
