"""Spectral (principal-stretch) strain-energy derivation engine.

The named-invariant path (:func:`mechdsl.symbolic.energy.derive_from_energy`)
differentiates ``Psi`` symbolically w.r.t. the nine Green-Lagrange strain
components, which works when ``Psi`` is a closed-form function of polynomial
invariants of ``C = 2E + I``. Ogden-type energies are instead authored in the
*principal stretches* ``lambda_i = sqrt(eig_i(C))``; the eigenvalues of a
symbolic ``C`` are Cardano radicals, so a direct ``d/dE`` of ``Psi`` is
intractable (and would blow the JIT budget). This module provides the spectral
derivation that handles that case.

Authoring contract
------------------
The barred (isochoric) principal stretches are authored as bare scalar symbols
``\\mathrm{lbar1}``, ``\\mathrm{lbar2}``, ``\\mathrm{lbar3}`` and the Jacobian as
``\\mathrm{Jdet}`` — the same ``\\mathrm{..}`` escape the named-invariant path
uses (nrpylatex emits them as scalar symbols with no index contraction). See
``examples/ogden_energy.tex``.

================  ============================================================
authored as       meaning (substituted before differentiation)
================  ============================================================
``\\mathrm{lbar1}``  ``lambda_bar_1 = J^{-1/3} * lambda_1``  (isochoric stretch)
``\\mathrm{lbar2}``  ``lambda_bar_2 = J^{-1/3} * lambda_2``
``\\mathrm{lbar3}``  ``lambda_bar_3 = J^{-1/3} * lambda_3``
``\\mathrm{Jdet}``   ``J = lambda_1 * lambda_2 * lambda_3 = det F``
================  ============================================================

Derivation
----------
With ``lambda_i`` three independent stretch symbols, ``Psi`` is re-expressed in
the ``lambda_i`` (substituting the bars and ``Jdet``) and differentiated. The
principal PK2 stresses are

    S_i = (1 / lambda_i) * dPsi/dlambda_i

because the principal Kirchhoff stress is ``tau_i = lambda_i dPsi/dlambda_i``
and ``S_i = tau_i / lambda_i^2`` (pull-back). The isochoric coupling
``-(1/3) sum_k (...)`` falls out automatically from the chain rule through
``J = lambda_1 lambda_2 lambda_3`` — no hand-coded split. This reproduces
``models/ogden.py``'s ``tau_iso_i`` / ``tau_vol`` exactly.

Numerical evaluation
---------------------
``Psi`` is not a closed-form function of the strain components, so the model
evaluates ``S(E)`` numerically: eigendecomposition of ``C = 2E + I`` gives the
stretches and eigenvectors, the symbolic ``S_i`` are evaluated at the numeric
stretches, and ``S = sum_i S_i N_i (x) N_i`` is reassembled. This spectral form
has no ``1/(e_a - e_b)`` denominators, so it is robust at repeated eigenvalues
(when ``e_i = e_j``, ``S_i = S_j`` and the eigenvector ambiguity cancels in the
sum of projectors). The material tangent uses central-difference FD of that
stress, matching ``models/ogden.py``'s own method (the closed-form spectral
tangent is singular at repeated stretches).

Taichi emission of the spectral path (eigendecomposition inside a ``@ti.func``)
is not in the MVP backend and is deferred — verification here is at the
symbolic-derivation + numerical-assembly level against the oracle.

Conventions (07-CONVENTIONS.md): tension-positive stress; Voigt ordering
[xx, yy, zz, xy, xz, yz] with unscaled shears; float64.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
import sympy as sp

from mechdsl.symbolic.energy import (
    EnergyDerivationError,
    declared_const_params,
    parse_energy_scalar_sympy,
)
from mechdsl.symbolic.voigt import tangent_to_voigt_66

if TYPE_CHECKING:
    from collections.abc import Callable

    from numpy.typing import NDArray

__all__ = [
    "SpectralEnergyModel",
    "derive_from_spectral_energy",
]

# Barred principal-stretch symbols (lbar1/lbar2/lbar3) authored via \mathrm{..}.
_STRETCH_NAME_RE = re.compile(r"^lbar([123])$")
# Jacobian symbol shared with the named-invariant registry.
_VOL_SYMBOL = "Jdet"

# Numerical guards mirror models/ogden.py.
_EIG_FLOOR = 1e-300
_FD_EPS = 1e-6


@dataclass(frozen=True)
class SpectralEnergyModel:
    """Symbolic + numerically-evaluable result of a spectral strain energy.

    Unlike :class:`mechdsl.symbolic.energy.EnergyModel`, the PK2 stress of a
    spectral energy is not a closed-form polynomial in the strain components, so
    this model carries the symbolic *principal* PK2 stresses ``S_i(lambda)`` and
    evaluates the full ``S(E)`` by eigendecomposition at call time. The tangent
    is central-difference FD of that stress (see module docstring).
    """

    psi: sp.Expr
    stretch_symbols: tuple[sp.Symbol, sp.Symbol, sp.Symbol]
    principal_pk2: tuple[sp.Expr, sp.Expr, sp.Expr]  # S_i(lambda_1, _2, _3, *params)
    parameters: dict[sp.Symbol, str]  # sanitised symbol -> original LaTeX name
    param_symbols: tuple[sp.Symbol, ...]  # sorted parameter symbols (eval order)
    _stress_fns: tuple[Callable[..., float], ...]  # lambdified S_i

    # ------------------------------------------------------------------
    # Numerical evaluation
    # ------------------------------------------------------------------

    def _param_args(self, param_values: dict[str, float]) -> list[float]:
        """Resolve parameter values into the lambdified-argument order, keyed by
        sanitised symbol name (the symbol's ``.name``)."""
        missing = [s.name for s in self.param_symbols if s.name not in param_values]
        if missing:
            raise ValueError(
                f"missing parameter value(s) {missing}; expected keys "
                f"{[s.name for s in self.param_symbols]}"
            )
        return [float(param_values[s.name]) for s in self.param_symbols]

    def _principal_stresses(self, e_vals: NDArray, pargs: list[float]) -> NDArray:
        """Principal PK2 stresses S_i at C-eigenvalues ``e_i = lambda_i^2``."""
        e_safe = np.maximum(e_vals, _EIG_FLOOR)
        lam = np.sqrt(e_safe)
        return np.array(
            [float(self._stress_fns[i](lam[0], lam[1], lam[2], *pargs)) for i in range(3)],
            dtype=np.float64,
        )

    def pk2_stress(self, e_strain: NDArray, param_values: dict[str, float]) -> NDArray:
        """PK2 stress ``S(E)`` via spectral reassembly.

        ``C = 2E + I`` is eigendecomposed (``numpy.linalg.eigh``); the symbolic
        principal stresses are evaluated at the numeric stretches and
        ``S = sum_i S_i N_i (x) N_i`` is reassembled and symmetrised.
        """
        if e_strain.shape != (3, 3):
            raise ValueError(f"Expected (3,3) strain tensor, got {e_strain.shape}")
        pargs = self._param_args(param_values)
        c = 2.0 * e_strain + np.eye(3, dtype=np.float64)
        c_sym = 0.5 * (c + c.T)
        e_vals, n_vecs = np.linalg.eigh(c_sym)
        if float(e_vals.min()) <= 0.0:
            raise ValueError(
                f"C must be positive-definite for a valid deformation, "
                f"got min(e)={e_vals.min():.3e}"
            )
        s_prin = self._principal_stresses(e_vals, pargs)
        s = np.zeros((3, 3), dtype=np.float64)
        for i in range(3):
            ni = n_vecs[:, i]
            s += s_prin[i] * np.outer(ni, ni)
        return 0.5 * (s + s.T)

    def material_tangent_4th(self, e_strain: NDArray, param_values: dict[str, float]) -> NDArray:
        """4th-order material tangent ``C_IJKL = dS_IJ/dE_KL`` via central-
        difference FD of :meth:`pk2_stress`, mirroring ``models/ogden.py``.

        Six independent symmetric ``dE`` directions (K <= L) are probed; minor
        symmetry folds ``C_IJKL = C_IJLK`` and major symmetry is enforced by
        averaging (cosmetic for FD noise).
        """
        if e_strain.shape != (3, 3):
            raise ValueError(f"Expected (3,3) strain tensor, got {e_strain.shape}")
        c4 = np.zeros((3, 3, 3, 3), dtype=np.float64)
        for k in range(3):
            for ll in range(k, 3):
                de = np.zeros((3, 3), dtype=np.float64)
                if k == ll:
                    de[k, k] = 1.0
                else:
                    de[k, ll] = 0.5
                    de[ll, k] = 0.5
                s_plus = self.pk2_stress(e_strain + _FD_EPS * de, param_values)
                s_minus = self.pk2_stress(e_strain - _FD_EPS * de, param_values)
                ds = (s_plus - s_minus) / (2.0 * _FD_EPS)
                c4[:, :, k, ll] = ds
                if k != ll:
                    c4[:, :, ll, k] = ds
        return 0.5 * (c4 + c4.transpose(2, 3, 0, 1))

    def material_tangent_voigt(self, e_strain: NDArray, param_values: dict[str, float]) -> NDArray:
        return tangent_to_voigt_66(self.material_tangent_4th(e_strain, param_values))


def derive_from_spectral_energy(latex: str, *, dim: int = 3) -> SpectralEnergyModel:
    """Parse a principal-stretch LaTeX strain-energy block and derive the
    symbolic principal PK2 stresses + a numerically-evaluable model.

    Parameters
    ----------
    latex:
        A LaTeX block with ``% declare`` lines and a scalar ``\\Psi = ...``
        authored in barred principal stretches (``\\mathrm{lbar1..3}``) and,
        optionally, ``\\mathrm{Jdet}`` for the volumetric term.
    dim:
        Spatial dimension. Only ``dim == 3`` is supported in the MVP.

    Raises
    ------
    EnergyDerivationError
        If no principal-stretch symbol is present (an invariant/component
        energy belongs to :func:`mechdsl.symbolic.energy.derive_from_energy`),
        or an unresolved symbol survives.
    """
    if dim != 3:
        raise EnergyDerivationError(
            f"dim={dim} is outside the MVP-stable subset; 2D / non-3D spectral "
            "energy derivation is planned for Plan B phase B2."
        )

    psi, backmap = parse_energy_scalar_sympy(latex)
    by_name = {s.name: s for s in psi.free_symbols}

    stretch_syms = {name: sym for name, sym in by_name.items() if _STRETCH_NAME_RE.match(name)}
    if not stretch_syms:
        raise EnergyDerivationError(
            "no principal-stretch symbol (lbar1/lbar2/lbar3) found in the strain "
            "energy; an invariant- or component-authored energy is derived by "
            "symbolic.energy.derive_from_energy, not the spectral path."
        )

    # IR discipline: every authored free symbol must be a recognised spectral
    # quantity (lbar1/lbar2/lbar3, Jdet) or a declared --const parameter. A
    # misspelled stretch (e.g. ``lbar4``, ``lambar1``) matches neither and would
    # otherwise be silently absorbed as a phantom parameter contributing nothing
    # to the stress — the spectral analogue of the invariant path's
    # _assert_symbols_resolved guard. Validate on the parsed psi (pre-subs).
    placeholder_for = {original: placeholder for placeholder, original in backmap.items()}
    allowed_param_names = {placeholder_for.get(n, n) for n in declared_const_params(latex)}
    recognised = set(stretch_syms) | {_VOL_SYMBOL} | allowed_param_names
    unresolved = sorted(s.name for s in psi.free_symbols if s.name not in recognised)
    if unresolved:
        raise EnergyDerivationError(
            f"unresolved symbol(s) {unresolved} in the spectral strain energy: each "
            "is neither a declared --const parameter nor a recognised spectral "
            "quantity (lbar1/lbar2/lbar3, Jdet). If it is a material parameter, "
            "declare it with '% declare \\name --const'; if it is a mistyped "
            "stretch, use lbar1/lbar2/lbar3."
        )

    # Three independent stretch symbols; bars and Jdet expressed in them.
    lam = sp.symbols("lambda_1 lambda_2 lambda_3", positive=True)
    jdet = lam[0] * lam[1] * lam[2]
    j_m13 = jdet ** sp.Rational(-1, 3)
    subs: dict[sp.Symbol, sp.Expr] = {}
    for name, sym in stretch_syms.items():
        idx = int(_STRETCH_NAME_RE.match(name).group(1)) - 1  # type: ignore[union-attr]
        subs[sym] = j_m13 * lam[idx]
    if _VOL_SYMBOL in by_name:
        subs[by_name[_VOL_SYMBOL]] = jdet

    psi_lambda = psi.subs(subs)

    # Parameters: free symbols that are neither the lambda_i we introduced nor
    # the authored bar/Jdet symbols (which were substituted away). Authoring was
    # already validated above, so every remaining symbol is a declared parameter.
    reserved = set(lam) | set(stretch_syms.values()) | {by_name.get(_VOL_SYMBOL)}
    param_symbols = tuple(
        sorted((s for s in psi_lambda.free_symbols if s not in reserved), key=lambda s: s.name)
    )

    # Principal PK2: S_i = (1/lambda_i) dPsi/dlambda_i.
    principal = tuple(sp.diff(psi_lambda, lam[i]) / lam[i] for i in range(3))
    stress_fns = tuple(
        sp.lambdify((lam[0], lam[1], lam[2], *param_symbols), principal[i], "numpy")
        for i in range(3)
    )

    placeholder_syms = {s for s in param_symbols if s.name in backmap}
    parameters = {s: backmap[s.name] for s in placeholder_syms}

    return SpectralEnergyModel(
        psi=psi,
        stretch_symbols=(lam[0], lam[1], lam[2]),
        principal_pk2=principal,  # type: ignore[arg-type]
        parameters=parameters,
        param_symbols=param_symbols,
        _stress_fns=stress_fns,
    )
