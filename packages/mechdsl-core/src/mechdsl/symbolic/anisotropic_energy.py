"""Anisotropic (fiber-reinforced) strain-energy derivation engine.

The named-invariant path
(:func:`mechdsl.symbolic.energy.derive_from_energy`) derives an *isotropic*
energy by differentiating a single ``Psi(C)`` w.r.t. the strain components. The
Holzapfel-Gasser-Ogden (HGO) family adds **fiber** terms that (a) depend on a
per-element fiber direction ``a`` (P5-1 field data, not authored in LaTeX) and
(b) are gated to tension only by the Macaulay bracket ``<Ibar4 - 1>`` — a
per-fiber, non-smooth branch that does not map onto one differentiable ``Psi``.
This module provides the fiber-aware derivation that handles both.

Authoring contract
------------------
The energy is authored once for a SINGLE (generic) fiber family in named
invariants (see ``examples/hgo_energy.tex``)::

    Psi = (mu/2)(Ibar1 - 3) + (kappa/2)(Jdet - 1)^2
        + (k1/2k2)(exp(k2 (Ibar4 - 1)^2) - 1)

``Ibar1`` / ``Jdet`` bind as usual (isotropic + volumetric); the fiber
pseudo-invariant ``\\mathrm{Ibar4}`` binds to ``I3^{-1/3} (a . C . a)`` with the
fiber direction ``a = (a0, a1, a2)`` introduced as symbolic components.

Derivation
----------
``Psi`` is split by whether a term contains ``Ibar4``:

* The **isotropic + volumetric** part is bound (``Ibar1``, ``Jdet`` -> their
  ``C = 2E + I`` definitions) and differentiated w.r.t. the nine strain
  components, giving the always-on ``S_iso(E)`` and its tangent — identical to
  the proven Neo-Hookean derivation.
* The **fiber template** part binds ``Ibar4`` and is differentiated to the
  *active-branch* fiber stress ``S_fib(E, a, k1, k2)``.

Because ``C = 2E + I`` => ``d/dE = 2 d/dC``, ``S = dPsi/dE`` is the spec's
``S = 2 dPsi/dC`` with the same minor-symmetrisation as the isotropic engine.

Numerical evaluation
---------------------
``S(E)`` is assembled per evaluation: ``S_iso`` plus, for each declared fiber
direction, the fiber template gated by the Macaulay bracket — the fiber term is
added only when ``Ibar4(E, a) > 1`` (tension), matching
``models/hgo.py``'s ``if E_fi <= 0: return 0``. The material tangent uses
central-difference FD of that gated stress, matching the HGO oracle's own
method (robust across the gating boundary).

This is the ``fiber_dispersion = 0`` (perfectly-aligned) HGO case. Taichi
emission of the per-element fiber gather + gated exponential is not in the MVP
backend and is deferred; verification is at the symbolic-derivation +
numerical-assembly level against the oracle.

Conventions (07-CONVENTIONS.md): tension-positive stress; Voigt ordering
[xx, yy, zz, xy, xz, yz] with unscaled shears; float64.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
import sympy as sp

from mechdsl.symbolic import invariants
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
    "AnisotropicEnergyModel",
    "derive_from_anisotropic_energy",
]

_STRAIN_SYMBOL = "EDD"
_FIBER_INVARIANT = "Ibar4"
# Isotropic invariants the fiber path reuses (bound to C = 2E + I definitions).
_ISO_BINDERS = {
    "I1": invariants.i1,
    "I2": invariants.i2,
    "I3": invariants.i3,
    "Jdet": lambda c: sp.sqrt(invariants.i3(c)),
    "Ibar1": lambda c: invariants.i1(c) * invariants.i3(c) ** sp.Rational(-1, 3),
    "Ibar2": lambda c: invariants.i2(c) * invariants.i3(c) ** sp.Rational(-2, 3),
}
# Anything matching the invariant shape but unbound is a typo -> reject (IR
# discipline), rather than silently surviving as a phantom parameter.
_INVARIANT_NAME_RE = re.compile(r"^(?:I\d+\w*|Ibar\d+|J(?:det)?)$")

_FD_EPS = 1e-6


def _strain_grid(psi: sp.Expr) -> tuple[tuple[sp.Symbol, ...], ...]:
    """Resolve the 3x3 grid of EDD strain-component symbols (creating any that
    simplification dropped), mirroring symbolic.energy."""
    by_name = {s.name: s for s in psi.free_symbols}
    grid: list[tuple[sp.Symbol, ...]] = []
    for i in range(3):
        row = [
            by_name.get(f"{_STRAIN_SYMBOL}{i}{j}", sp.Symbol(f"{_STRAIN_SYMBOL}{i}{j}", real=True))
            for j in range(3)
        ]
        grid.append(tuple(row))
    return tuple(grid)


def _c_from_strain(strain: tuple[tuple[sp.Symbol, ...], ...]) -> sp.Matrix:
    e = sp.Matrix(3, 3, lambda i, j: strain[i][j])
    return 2 * e + sp.eye(3)


def _minor_sym_pk2(
    psi: sp.Expr, strain: tuple[tuple[sp.Symbol, ...], ...]
) -> sp.ImmutableDenseMatrix:
    """S_IJ = sym( dPsi/dE_IJ ) — the minor-symmetric first derivative."""
    raw = [[sp.diff(psi, strain[i][j]) for j in range(3)] for i in range(3)]
    half = sp.Rational(1, 2)
    return sp.ImmutableDenseMatrix(
        [[half * (raw[i][j] + raw[j][i]) for j in range(3)] for i in range(3)]
    )


@dataclass(frozen=True)
class AnisotropicEnergyModel:
    """Symbolic + numerically-evaluable fiber-reinforced (HGO) energy.

    Carries the always-on isotropic+volumetric PK2 stress ``S_iso(E)`` and the
    *active-branch* fiber-template stress ``S_fib(E, a)``; the evaluator gates
    each declared fiber family by ``Ibar4(E, a) > 1`` and sums. The tangent is
    central-difference FD of the gated stress (matches models/hgo.py).
    """

    psi: sp.Expr
    strain_symbols: tuple[tuple[sp.Symbol, ...], ...]
    iso_pk2: sp.ImmutableDenseMatrix  # S_iso+vol(E, *iso_params)
    fiber_pk2: sp.ImmutableDenseMatrix  # S_fib(E, a0,a1,a2, *fiber_params) — active branch
    fiber_ibar4: sp.Expr  # Ibar4(E, a0,a1,a2) for the Macaulay gate
    fiber_symbols: tuple[sp.Symbol, sp.Symbol, sp.Symbol]
    iso_param_symbols: tuple[sp.Symbol, ...]
    fiber_param_symbols: tuple[sp.Symbol, ...]
    parameters: dict[sp.Symbol, str]  # sanitised -> original LaTeX name
    _iso_fn: Callable[..., NDArray]
    _fiber_fn: Callable[..., NDArray]
    _ibar4_fn: Callable[..., float]

    def _iso_args(self, e_strain: NDArray, params: dict[str, float]) -> list[float]:
        flat = [e_strain[i, j] for i in range(3) for j in range(3)]
        return [*flat, *(float(params[s.name]) for s in self.iso_param_symbols)]

    def _fiber_args(self, e_strain: NDArray, a: NDArray, params: dict[str, float]) -> list[float]:
        flat = [e_strain[i, j] for i in range(3) for j in range(3)]
        return [*flat, a[0], a[1], a[2], *(float(params[s.name]) for s in self.fiber_param_symbols)]

    def pk2_stress(
        self,
        e_strain: NDArray,
        fiber_dirs: tuple[NDArray, ...],
        param_values: dict[str, float],
    ) -> NDArray:
        """Assemble PK2 stress: S_iso + sum over tension-active fibers.

        Each fiber direction is normalised (as the HGO oracle does) and its
        active-branch contribution is added only when Ibar4(E, a) > 1.
        """
        if e_strain.shape != (3, 3):
            raise ValueError(f"Expected (3,3) strain tensor, got {e_strain.shape}")
        s = np.array(self._iso_fn(*self._iso_args(e_strain, param_values)), dtype=np.float64)
        for raw_a in fiber_dirs:
            a = np.asarray(raw_a, dtype=np.float64)
            norm = float(np.linalg.norm(a))
            if norm <= 0.0:
                raise ValueError("Fiber direction must be non-zero")
            a = a / norm
            ibar4 = float(self._ibar4_fn(*self._fiber_args(e_strain, a, param_values)[:12]))
            if ibar4 > 1.0:  # Macaulay gate <Ibar4 - 1>: active in tension only
                s = s + np.array(
                    self._fiber_fn(*self._fiber_args(e_strain, a, param_values)), dtype=np.float64
                )
        return 0.5 * (s + s.T)

    def material_tangent_4th(
        self,
        e_strain: NDArray,
        fiber_dirs: tuple[NDArray, ...],
        param_values: dict[str, float],
    ) -> NDArray:
        """4th-order tangent via central-difference FD of the gated PK2 stress,
        mirroring models/hgo.py (robust across the fiber-gating boundary)."""
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
                s_plus = self.pk2_stress(e_strain + _FD_EPS * de, fiber_dirs, param_values)
                s_minus = self.pk2_stress(e_strain - _FD_EPS * de, fiber_dirs, param_values)
                ds = (s_plus - s_minus) / (2.0 * _FD_EPS)
                c4[:, :, k, ll] = ds
                if k != ll:
                    c4[:, :, ll, k] = ds
        return 0.5 * (c4 + c4.transpose(2, 3, 0, 1))

    def material_tangent_voigt(
        self,
        e_strain: NDArray,
        fiber_dirs: tuple[NDArray, ...],
        param_values: dict[str, float],
    ) -> NDArray:
        return tangent_to_voigt_66(self.material_tangent_4th(e_strain, fiber_dirs, param_values))


def _bind_iso(psi_iso: sp.Expr, c: sp.Matrix, source: str) -> sp.Expr:
    """Substitute isotropic invariant symbols (Ibar1/Jdet/...) with their
    C = 2E + I definitions; reject a misspelled invariant rather than letting it
    survive as a phantom parameter (IR discipline)."""
    subs: dict[sp.Symbol, sp.Expr] = {}
    for sym in psi_iso.free_symbols:
        name = sym.name
        if name.startswith(_STRAIN_SYMBOL) or name == _FIBER_INVARIANT:
            continue
        if name in _ISO_BINDERS:
            subs[sym] = _ISO_BINDERS[name](c)
        elif _INVARIANT_NAME_RE.match(name):
            raise EnergyDerivationError(
                f"invariant {name!r} in the isotropic part is not a supported "
                f"named invariant; supported: {sorted(_ISO_BINDERS)} (and the "
                f"fiber invariant {_FIBER_INVARIANT!r})."
            )
    return psi_iso.subs(subs)


def derive_from_anisotropic_energy(latex: str, *, dim: int = 3) -> AnisotropicEnergyModel:
    """Parse a fiber-reinforced LaTeX strain energy (HGO) and derive the
    isotropic stress + the active-branch fiber-template stress.

    Raises
    ------
    EnergyDerivationError
        If no fiber invariant (``Ibar4``) is present (an isotropic energy
        belongs to :func:`mechdsl.symbolic.energy.derive_from_energy`), or an
        unresolved/misspelled symbol survives.
    """
    if dim != 3:
        raise EnergyDerivationError(
            f"dim={dim} is outside the MVP-stable subset; 2D / non-3D anisotropic "
            "energy derivation is planned for Plan B phase B2."
        )

    psi, backmap = parse_energy_scalar_sympy(latex)
    by_name = {s.name: s for s in psi.free_symbols}
    ibar4 = by_name.get(_FIBER_INVARIANT)
    if ibar4 is None:
        raise EnergyDerivationError(
            f"no fiber invariant ({_FIBER_INVARIANT}) found in the strain energy; "
            "an isotropic energy is derived by symbolic.energy.derive_from_energy, "
            "not the anisotropic (fiber) path."
        )

    strain = _strain_grid(psi)
    c = _c_from_strain(strain)

    # Split Psi by Ibar4 presence: fiber template vs isotropic + volumetric.
    fiber_part = sum((t for t in psi.as_ordered_terms() if ibar4 in t.free_symbols), sp.S.Zero)
    iso_part = sp.expand(psi - fiber_part)

    # --- isotropic + volumetric stress ---
    psi_iso = _bind_iso(iso_part, c, latex)
    iso_pk2 = _minor_sym_pk2(psi_iso, strain)

    # --- fiber template: bind Ibar4 -> I3^{-1/3} (a . C . a) with symbolic a ---
    a = sp.symbols("a0 a1 a2", real=True)
    a_vec = sp.Matrix(a)
    ibar4_expr = invariants.i3(c) ** sp.Rational(-1, 3) * invariants.i4(c, a_vec)
    psi_fiber = fiber_part.subs({ibar4: ibar4_expr})
    fiber_pk2 = _minor_sym_pk2(psi_fiber, strain)

    # Parameters = free symbols that are neither strain nor fiber components.
    fiber_set = set(a)
    strain_set = {strain[i][j] for i in range(3) for j in range(3)}

    def _params_of(expr: sp.Expr) -> tuple[sp.Symbol, ...]:
        return tuple(
            sorted(
                (s for s in expr.free_symbols if s not in strain_set and s not in fiber_set),
                key=lambda s: s.name,
            )
        )

    iso_param_symbols = _params_of(iso_pk2)
    fiber_param_symbols = _params_of(fiber_pk2)

    # IR discipline: every parameter must be a declared --const (else a typo'd
    # symbol would masquerade as a free parameter contributing nothing).
    placeholder_for = {original: ph for ph, original in backmap.items()}
    allowed = {placeholder_for.get(n, n) for n in declared_const_params(latex)}
    # k1/k2 are authored as \mathrm{..} bare symbols (not --const-declarable in
    # nrpylatex); accept the canonical HGO fiber params explicitly.
    allowed |= {"k1", "k2"}
    unresolved = sorted(
        s.name for s in (*iso_param_symbols, *fiber_param_symbols) if s.name not in allowed
    )
    if unresolved:
        raise EnergyDerivationError(
            f"unresolved symbol(s) {unresolved} in the anisotropic strain energy: "
            "each is neither a declared --const parameter, a recognised invariant "
            "(Ibar1/Ibar2/Jdet/Ibar4), nor a fiber component. Declare material "
            "parameters with '% declare \\name --const'."
        )

    flat = [strain[i][j] for i in range(3) for j in range(3)]
    iso_fn = sp.lambdify((*flat, *iso_param_symbols), iso_pk2, "numpy")
    fiber_fn = sp.lambdify((*flat, *a, *fiber_param_symbols), fiber_pk2, "numpy")
    ibar4_fn = sp.lambdify((*flat, *a), ibar4_expr, "numpy")

    all_params = {*iso_param_symbols, *fiber_param_symbols}
    parameters = {s: backmap[s.name] for s in all_params if s.name in backmap}

    return AnisotropicEnergyModel(
        psi=psi,
        strain_symbols=strain,
        iso_pk2=iso_pk2,
        fiber_pk2=fiber_pk2,
        fiber_ibar4=ibar4_expr,
        fiber_symbols=(a[0], a[1], a[2]),
        iso_param_symbols=iso_param_symbols,
        fiber_param_symbols=fiber_param_symbols,
        parameters=parameters,
        _iso_fn=iso_fn,
        _fiber_fn=fiber_fn,
        _ibar4_fn=ibar4_fn,
    )
