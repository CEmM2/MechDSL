"""Strain-energy auto-differentiation engine (design doc 03-SYMBOLIC-ENGINE §3.1).

Derives the second Piola-Kirchhoff stress and the fourth-order material
tangent from a hyperelastic strain-energy density Psi authored in LaTeX::

    Psi(C)  --d/dE-->  S_IJ = dPsi/dE_IJ  --d/dE-->  C_IJKL = d2Psi/dE_IJ dE_KL

This is the compiler link the LaTeX-to-code pipeline was always meant to
have (and that Plan B bypassed by hand-coding models). The LaTeX energy is
parsed by ``nrpylatex`` into a SymPy scalar; differentiation is performed
with respect to the nine independent Green-Lagrange strain components,
which reproduces the textbook ``S = lambda*tr(E)*I + 2*mu*E`` for SVK
including the unscaled-shear factor (07-CONVENTIONS).

Two frontend realities are handled here:

* **Symbol sanitisation.** ``nrpylatex`` emits the bare symbol name into
  generated Python (``\\lambda`` -> ``lambda``, a keyword; ``\\Lambda`` ->
  SymPy's ``Lambda``). Colliding parameter names are rewritten to the
  Hebrew-letter family (``\\aleph \\beth \\gimel \\daleth``) before parsing
  and kept that way: the placeholder is disjoint from every mechanical
  symbol, so it is unambiguous in any intermediate dump and never
  reintroduces the collision at codegen. The original LaTeX name is kept
  only for display via :attr:`EnergyModel.parameters`.
* **Reference metric.** ``nrpylatex`` requires Einstein contractions to
  pair one upper with one lower index, so a scalar energy needs a declared
  ``% declare metric gDD --dim 3`` to raise indices (physically the
  curvilinear reference metric). For the Cartesian MVP the metric is pinned
  to the identity, collapsing ``nrpylatex``'s symbolic ``gUU = inverse(gDD)``
  to delta with no determinant denominators.

Named-invariant authoring (P2-1)
--------------------------------
A strain energy may instead be authored in *named invariants* of the right
Cauchy-Green tensor ``C = 2E + I`` — ``\\bar I_1``, ``\\bar I_2``, ``J``, … —
so that ``nrpylatex`` never has to parse ``\\det`` / ``\\log`` (a frontend
*parsing*-only obstacle; SymPy handles det/sqrt/log fine). The invariant
symbols are authored with the existing ``\\mathrm{..}`` escape, which
``nrpylatex`` emits as a bare scalar symbol needing no index contraction::

    \\Psi = \\frac{\\mu}{2} (\\mathrm{Ibar1} - 3) + \\frac{\\kappa}{2} (\\mathrm{Jdet} - 1)^2

After parsing and metric-pinning, each recognised invariant symbol is
``subs``-ed with its definition *evaluated on the EDD strain grid via
C = 2E + I*, and the existing ``d/dE`` differentiation core runs unchanged.
Because ``C = 2E + I`` ⇒ ``d/dE = 2 d/dC``, the existing
``S = dPsi/dE`` is exactly the spec's ``S = 2 dPsi/dC`` and
``C_tangent = 4 d²Psi/dC dC``, with the same minor-symmetrisation — so the
symmetric-diff double-count trap (the 2μ/4μ bug) is sidestepped entirely
without a separate component-wise diff path.

The symbol -> definition table is :data:`_INVARIANT_REGISTRY`
(symbol-name -> callable(C) -> SymPy scalar):

==============  ==========================================  ============================
authored as     symbol                                      definition on C = 2E + I
==============  ==========================================  ============================
``\\mathrm{I1}``     ``I1``     ``tr C``
``\\mathrm{I2}``     ``I2``     ``1/2[(tr C)^2 - tr(C^2)]``
``\\mathrm{I3}``     ``I3``     ``det C``
``\\mathrm{Jdet}``   ``Jdet``   ``sqrt(det C)``
``\\mathrm{Ibar1}``  ``Ibar1``  ``I1 * I3^{-1/3}``
``\\mathrm{Ibar2}``  ``Ibar2``  ``I2 * I3^{-2/3}``
``\\mathrm{I4f}``    ``I4f``    ``a·C·a``      (fiber a — Phase 5 / P5-1)
``\\mathrm{I5f}``    ``I5f``    ``a·C²·a``     (fiber a — Phase 5 / P5-1)
==============  ==========================================  ============================
"""

from __future__ import annotations

import builtins
import keyword
import re
from collections.abc import Callable
from dataclasses import dataclass

import nrpylatex
import sympy as sp

from mechdsl.symbolic import invariants

__all__ = [
    "EnergyDerivationError",
    "EnergyModel",
    "declared_const_params",
    "derive_from_energy",
    "parse_energy_scalar_sympy",
]

# Safe, distinctive placeholders for parameter names that collide with a
# Python keyword or a SymPy/builtins name. The Hebrew-letter NAMES are used
# as plain ASCII symbols: nrpylatex rejects \aleph (not in its command
# vocabulary) but accepts a multi-letter identifier in a declaration and the
# matching \mathrm{aleph} in an expression. They never name a mechanical
# quantity, so they stand out in any intermediate dump.
_PLACEHOLDERS: tuple[str, ...] = ("aleph", "beth", "gimel", "daleth")

# nrpylatex names tensor components with the declared U/D suffix (EDD00),
# so only bare *constant* names collide. The strain tensor is EDD by
# convention here (material Green-Lagrange strain, both indices lower).
_STRAIN_SYMBOL = "EDD"
_ENERGY_KEY = "Psi"
_METRIC_PREFIXES = ("gDD", "gUU")


def _c_from_strain(strain: tuple[tuple[sp.Symbol, ...], ...]) -> sp.Matrix:
    """Build the right Cauchy-Green tensor ``C = 2E + I`` from the EDD grid.

    The nine EDD strain components are treated as independent symbols (the
    same basis the ``d/dE`` core differentiates against), so substituting an
    invariant's ``C(E)`` definition and then differentiating w.r.t. ``E``
    yields ``S = dPsi/dE = 2 dPsi/dC`` once the minor-symmetrisation runs.
    """
    e = sp.Matrix(3, 3, lambda i, j: strain[i][j])
    return 2 * e + sp.eye(3)


# Named-invariant authoring contract. Each entry maps an authored
# scalar symbol name (emitted by nrpylatex from ``\mathrm{<name>}``) to a
# callable that builds the invariant as a SymPy scalar on C = 2E + I, drawing
# every definition from symbolic/invariants.py so this module never re-derives
# an invariant. See the module docstring for the full table.
_InvariantBinder = Callable[[sp.Matrix], sp.Expr]


def _ibar1(c: sp.Matrix) -> sp.Expr:
    """Isochoric first invariant Ibar1 = I1 * I3^{-1/3}."""
    return invariants.i1(c) * invariants.i3(c) ** sp.Rational(-1, 3)


def _ibar2(c: sp.Matrix) -> sp.Expr:
    """Isochoric second invariant Ibar2 = I2 * I3^{-2/3}."""
    return invariants.i2(c) * invariants.i3(c) ** sp.Rational(-2, 3)


def _jdet(c: sp.Matrix) -> sp.Expr:
    """Jacobian J = sqrt(det C) (= det F)."""
    return sp.sqrt(invariants.i3(c))


_INVARIANT_REGISTRY: dict[str, _InvariantBinder] = {
    "I1": invariants.i1,
    "I2": invariants.i2,
    "I3": invariants.i3,
    "Jdet": _jdet,
    "Ibar1": _ibar1,
    "Ibar2": _ibar2,
}

# Invariant symbols that are recognised but require a fiber direction, which
# is not plumbed in this path. Authoring one is rejected with a clear error
# rather than silently treated as a free parameter.
_FIBER_INVARIANTS: dict[str, str] = {
    "I4f": "I4 = a·C·a",
    "I5f": "I5 = a·C²·a",
}

# Any authored symbol matching this shape is treated as an *intended* invariant
# (so an unknown one is rejected instead of being mistaken for a free material
# parameter). Bare Greek/Latin parameter names (mu, kappa, aleph, …) do not match.
_INVARIANT_NAME_RE = re.compile(r"^(?:I\d+\w*|Ibar\d+|J(?:det)?)$")


class EnergyDerivationError(RuntimeError):
    """Raised when a strain-energy block cannot be parsed or differentiated."""


@dataclass(frozen=True)
class EnergyModel:
    """Symbolic result of differentiating a strain-energy density.

    All expressions are SymPy in the nine strain-component symbols
    (``EDD00 .. EDD22``) and the (sanitised) parameter symbols.
    """

    psi: sp.Expr
    strain_symbols: tuple[tuple[sp.Symbol, ...], ...]  # 3x3 grid, EDD_ij
    pk2: sp.ImmutableDenseMatrix  # 3x3, S_IJ
    tangent: sp.ImmutableDenseNDimArray  # 3x3x3x3, C_IJKL
    parameters: dict[sp.Symbol, str]  # sanitised symbol -> original LaTeX name


def _is_unsafe(name: str) -> bool:
    """A stripped symbol name is unsafe if nrpylatex would emit it as a
    Python keyword, a builtin, or a name shadowing the SymPy namespace it
    execs against."""
    return keyword.iskeyword(name) or hasattr(builtins, name) or hasattr(sp, name)


def _strip_prose_comments(latex: str) -> str:
    """Drop prose ``%`` comment lines so a full ``.tex`` block parses; keep
    ``% declare`` directives (which nrpylatex consumes) and the equations."""
    kept: list[str] = []
    for line in latex.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("%") and not stripped.startswith("% declare"):
            continue
        kept.append(line)
    return "\n".join(kept)


def _const_param_names(latex: str) -> set[str]:
    """Names declared as ``--const`` scalar parameters (the only bare-name
    symbols that can collide; tensors carry a safe U/D suffix)."""
    names: set[str] = set()
    for line in latex.splitlines():
        stripped = line.strip()
        if stripped.startswith("% declare") and "--const" in stripped:
            head = stripped.split("--const", 1)[0]
            names.update(re.findall(r"\\([A-Za-z]+)", head))
    return names


def _sanitise_source(latex: str) -> tuple[str, dict[str, str]]:
    """Rewrite colliding ``--const`` parameter names to the placeholder pool.

    nrpylatex needs a plain identifier in the declaration but ``\\mathrm{..}``
    in expressions, so replacement is context-aware. Returns the rewritten
    source and a ``{placeholder_name: original_name}`` map. Only declared
    constants are touched — structural commands like ``\\frac`` are left alone
    even though their bare name (``frac``) shadows a SymPy attribute."""
    colliding = sorted(p for p in _const_param_names(latex) if _is_unsafe(p))
    if not colliding:
        return latex, {}
    if len(colliding) > len(_PLACEHOLDERS):
        raise EnergyDerivationError(
            f"{len(colliding)} colliding parameter names {colliding} exceed the "
            f"{len(_PLACEHOLDERS)}-slot placeholder pool; extend _PLACEHOLDERS "
            "in symbolic/energy.py."
        )
    assignments = list(zip(colliding, _PLACEHOLDERS, strict=False))
    out_lines: list[str] = []
    for line in latex.splitlines():
        is_declare = line.lstrip().startswith("% declare")
        new = line
        for original, placeholder in assignments:
            repl = placeholder if is_declare else rf"\mathrm{{{placeholder}}}"
            # Whole-token match only (\lambda must not match inside \lambdabar);
            # backslashes are doubled so re treats the repl literally rather
            # than processing escapes (\a -> BEL, \m -> bad-escape error).
            new = re.sub(rf"\\{original}(?![A-Za-z])", repl.replace("\\", "\\\\"), new)
        out_lines.append(new)
    backmap = {placeholder: original for original, placeholder in assignments}
    return "\n".join(out_lines), backmap


def _parse_energy_scalar(latex: str) -> sp.Expr:
    """Run sanitised LaTeX through nrpylatex and return the evaluated Psi scalar."""
    try:
        nrpylatex.parse_latex(latex, reset=True)
    except Exception as exc:  # nrpylatex raises a family of parser errors
        raise EnergyDerivationError(
            f"nrpylatex could not parse the strain-energy block: {type(exc).__name__}: {exc}"
        ) from exc
    namespace = nrpylatex.Parser._namespace
    if _ENERGY_KEY not in namespace:
        raise EnergyDerivationError(
            f"no scalar energy {_ENERGY_KEY!r} found after parsing; the block must "
            r"assign \Psi = ... as a fully-contracted (scalar) expression."
        )
    psi_obj = namespace[_ENERGY_KEY]
    return sp.sympify(getattr(psi_obj, "structure", psi_obj))


def _pin_identity_metric(psi: sp.Expr) -> sp.Expr:
    """Substitute the reference-metric symbols (gDD/gUU) with the identity,
    collapsing nrpylatex's symbolic inverse to delta with no denominators."""
    subs: dict[sp.Symbol, sp.Integer] = {}
    for symbol in psi.free_symbols:
        name = symbol.name
        if name.startswith(_METRIC_PREFIXES) and len(name) == 5 and name[3:].isdigit():
            i, j = int(name[3]), int(name[4])
            subs[symbol] = sp.Integer(1 if i == j else 0)
    return sp.simplify(psi.subs(subs)) if subs else psi


def _strain_grid(psi: sp.Expr) -> tuple[tuple[sp.Symbol, ...], ...]:
    """Resolve the 3x3 grid of EDD strain-component symbols actually present."""
    by_name = {s.name: s for s in psi.free_symbols}
    grid: list[tuple[sp.Symbol, ...]] = []
    for i in range(3):
        row: list[sp.Symbol] = []
        for j in range(3):
            name = f"{_STRAIN_SYMBOL}{i}{j}"
            # A component absent from Psi (e.g. dropped by simplification)
            # still needs a symbol for differentiation; create it.
            row.append(by_name.get(name, sp.Symbol(name, real=True)))
        grid.append(tuple(row))
    return tuple(grid)


def _invariant_location(source: str, name: str) -> str:
    """A `` (line N)`` suffix locating where invariant ``name`` is authored in
    the original LaTeX, or ``""`` if it cannot be found.

    The binding runs on the parsed expression (post-nrpylatex), so the source
    line is recovered by scanning the original text for the ``\\mathrm{name}``
    token (the authoring form) and falling back to the bare name."""
    targets = (rf"\mathrm{{{name}}}", name)
    for lineno, line in enumerate(source.splitlines(), start=1):
        if any(token in line for token in targets):
            return f" (line {lineno})"
    return ""


def _bind_invariants(
    psi: sp.Expr,
    strain: tuple[tuple[sp.Symbol, ...], ...],
    source: str,
) -> sp.Expr:
    """Replace named-invariant symbols in ``psi`` with their ``C = 2E + I``
    definitions so the existing ``d/dE`` core can differentiate them.

    Only symbols recognised by :data:`_INVARIANT_REGISTRY` are substituted.
    A symbol that *looks* like an invariant (matches :data:`_INVARIANT_NAME_RE`)
    but is unsupported is rejected with a plan-phase pointer rather than left to
    masquerade as a free material parameter — IR discipline. Bare parameter
    symbols (mu, kappa, the Hebrew placeholders) are left untouched.

    Because ``C = 2E + I`` ⇒ ``d/dE = 2 d/dC``, no separate chain-rule path is
    needed: the existing ``S = dPsi/dE`` becomes the spec's ``S = 2 dPsi/dC``
    and the minor-symmetrisation already in :func:`derive_from_energy` handles
    the symmetric projection (avoiding the 2μ/4μ symmetric-diff double-count).
    """
    invariant_syms = [s for s in psi.free_symbols if _INVARIANT_NAME_RE.match(s.name)]
    if not invariant_syms:
        return psi

    c: sp.Matrix | None = None
    subs: dict[sp.Symbol, sp.Expr] = {}
    for sym in invariant_syms:
        name = sym.name
        loc = _invariant_location(source, name)
        if name in _FIBER_INVARIANTS:
            raise EnergyDerivationError(
                f"invariant {name!r}{loc} ({_FIBER_INVARIANTS[name]}) requires a "
                "fiber direction; anisotropic I4/I5 fiber plumbing is planned for "
                "Phase 5 (P5-1)."
            )
        binder = _INVARIANT_REGISTRY.get(name)
        if binder is None:
            raise EnergyDerivationError(
                f"invariant {name!r}{loc} is not a supported named invariant; the "
                f"authoring contract covers {sorted(_INVARIANT_REGISTRY)} "
                "(isotropic) and I4/I5 fiber invariants are planned for "
                "Phase 5 (P5-1)."
            )
        if c is None:
            c = _c_from_strain(strain)
        subs[sym] = binder(c)
    return psi.subs(subs)


def _assert_symbols_resolved(
    psi: sp.Expr,
    strain: tuple[tuple[sp.Symbol, ...], ...],
    allowed_params: set[str],
) -> None:
    """Reject any free symbol in ``psi`` that is neither a strain component nor a
    declared material parameter.

    After invariant binding, the only legitimate free symbols are the nine
    ``EDD`` strain components and the declared ``--const`` parameters. A symbol
    that *looks* like an invariant but is misspelled (``Jdet2``, ``Ibar1x``,
    ``Jbar`` — none match :data:`_INVARIANT_NAME_RE`) would otherwise survive as
    a bare constant, silently contributing zero stress with no error. IR
    discipline: an unrecognised construct must raise, not be guessed."""
    strain_names = {strain[i][j].name for i in range(3) for j in range(3)}
    allowed = allowed_params | strain_names
    leftover = sorted({s.name for s in psi.free_symbols if s.name not in allowed})
    if leftover:
        raise EnergyDerivationError(
            f"unresolved symbol(s) {leftover} in the strain energy: each is neither "
            "a declared --const parameter nor a strain component, and none is a "
            f"supported named invariant {sorted(_INVARIANT_REGISTRY)}. If it is a "
            "material parameter, declare it with '% declare \\name --const'; if it "
            "is a mistyped invariant, use one of the supported names."
        )


def declared_const_params(latex: str) -> set[str]:
    """Names declared as ``--const`` scalar parameters in a strain-energy block
    (the only bare-name symbols that can collide; tensors carry a safe U/D
    suffix). Shared by the invariant path and the spectral path so both validate
    authored symbols against the same declaration source."""
    return _const_param_names(latex)


def parse_energy_scalar_sympy(latex: str) -> tuple[sp.Expr, dict[str, str]]:
    """Run a strain-energy LaTeX block through the shared nrpylatex frontend and
    return ``(psi, backmap)``: the metric-pinned SymPy scalar energy and the
    ``{placeholder_name: original_name}`` parameter-sanitisation map.

    This is the frontend the invariant path (:func:`derive_from_energy`) and the
    spectral path (``spectral_energy.derive_from_spectral_energy``) share —
    prose-comment stripping, ``--const`` collision sanitisation, nrpylatex
    parsing, and reference-metric pinning — *before* either path performs its
    own (invariant-substitution vs spectral-substitution) differentiation. It
    does not bind invariants or assert symbol resolution; callers do that
    against their own contract.
    """
    clean, backmap = _sanitise_source(_strip_prose_comments(latex))
    psi = _pin_identity_metric(_parse_energy_scalar(clean))
    return psi, backmap


def derive_from_energy(latex: str, *, dim: int = 3) -> EnergyModel:
    """Parse a LaTeX strain-energy block and derive symbolic PK2 stress and
    material tangent.

    Parameters
    ----------
    latex:
        A LaTeX block containing ``% declare`` lines (including a metric and
        the strain tensor ``EDD``) and a scalar assignment ``\\Psi = ...``.
    dim:
        Spatial dimension. Only ``dim == 3`` is supported in the MVP.

    Returns
    -------
    EnergyModel
        Symbolic ``psi``, the 3x3 strain symbols, ``pk2`` (3x3 ``S_IJ``),
        ``tangent`` (3x3x3x3 ``C_IJKL``), and the sanitised parameter map.
    """
    if dim != 3:
        raise EnergyDerivationError(
            f"dim={dim} is outside the MVP-stable subset; 2D / non-3D energy "
            "derivation is planned for Plan B phase B2."
        )

    psi_parsed, backmap = parse_energy_scalar_sympy(latex)
    strain = _strain_grid(psi_parsed)
    # If the energy was authored in named invariants, substitute their
    # C = 2E + I definitions before differentiation. Component-authored
    # energies (e.g. SVK in EDD) pass through unchanged.
    psi = _bind_invariants(psi_parsed, strain, latex)

    # Guard against misspelled invariants / undeclared parameters silently
    # surviving as bare constants (zero stress, no error).
    original_to_placeholder = {original: placeholder for placeholder, original in backmap.items()}
    allowed_params = {original_to_placeholder.get(n, n) for n in _const_param_names(latex)}
    _assert_symbols_resolved(psi, strain, allowed_params)

    # Differentiate w.r.t. the nine independent strain components, then
    # enforce the physical index symmetries: PK2 is symmetric (minor symmetry
    # of S), and the material tangent is minor-symmetric in (I,J) and (K,L).
    # Major symmetry C_IJKL = C_KLIJ is automatic for a hyperelastic energy.
    raw_s = [[sp.diff(psi, strain[i][j]) for j in range(3)] for i in range(3)]
    raw_c = [
        [
            [[sp.diff(raw_s[i][j], strain[k][el]) for el in range(3)] for k in range(3)]
            for j in range(3)
        ]
        for i in range(3)
    ]
    half = sp.Rational(1, 2)
    quarter = sp.Rational(1, 4)
    pk2 = sp.ImmutableDenseMatrix(
        [[half * (raw_s[i][j] + raw_s[j][i]) for j in range(3)] for i in range(3)]
    )
    tangent = sp.ImmutableDenseNDimArray(
        [
            [
                [
                    [
                        quarter
                        * (
                            raw_c[i][j][k][el]
                            + raw_c[j][i][k][el]
                            + raw_c[i][j][el][k]
                            + raw_c[j][i][el][k]
                        )
                        for el in range(3)
                    ]
                    for k in range(3)
                ]
                for j in range(3)
            ]
            for i in range(3)
        ]
    )

    placeholder_syms = {s for s in psi.free_symbols if s.name in backmap}
    parameters = {s: backmap[s.name] for s in placeholder_syms}

    return EnergyModel(
        psi=psi,
        strain_symbols=strain,
        pk2=pk2,
        tangent=tangent,
        parameters=parameters,
    )
