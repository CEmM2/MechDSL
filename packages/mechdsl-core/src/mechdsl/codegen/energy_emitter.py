"""Emit a Taichi constitutive ``@ti.func`` from a LaTeX-derived energy model.

This closes the LaTeX-to-code constitutive loop: :mod:`mechdsl.symbolic.energy`
derives the symbolic PK2 stress from a strain-energy density, and this module
prints that stress as a self-contained Taichi function. It is the
derived-expression counterpart to the hand-written ``_emit_svk_constitutive``
branch in :mod:`mechdsl.codegen.taichi_printer`; wiring it into the main
printer's dispatch is a follow-up once the path is proven end-to-end.

Parameter arguments keep their sanitised names (e.g. ``aleph`` for a strain
energy that used ``\\lambda``) — the names are already valid identifiers and
stay disjoint from any mechanical symbol, so the generated signature is
unambiguous. :attr:`EnergyModel.parameters` records the original LaTeX name.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from sympy import Symbol, pycode

from mechdsl.symbolic.voigt import VOIGT_MAP_3D

if TYPE_CHECKING:
    from mechdsl.symbolic.energy import EnergyModel

__all__ = [
    "derived_param_names",
    "emit_constitutive_func",
    "emit_derived_tangent_matvec_body",
    "emit_tangent_func",
]

_STRAIN = "EDD"

# SymPy's ``pycode`` prints transcendental calls against the ``math`` module
# (``math.sqrt``, ``math.log``, …). Those are host-Python calls that Taichi
# rejects inside a ``@ti.func`` ("must be real number, not Taichi Expression").
# Rewrite the supported elementary functions to their Taichi equivalents so the
# emitted source JIT-compiles. SVK (linear, no transcendental) is unaffected —
# its emitted body contains no ``math.`` call, so this map is a no-op there.
# Keyed by the bare function name (``math.sqrt`` -> key ``sqrt``).
_MATH_TO_TAICHI: dict[str, str] = {
    "sqrt": "ti.sqrt",
    "exp": "ti.exp",
    "log": "ti.log",
    "sin": "ti.sin",
    "cos": "ti.cos",
    "tan": "ti.tan",
    "asin": "ti.asin",
    "acos": "ti.acos",
    "atan": "ti.atan",
    "tanh": "ti.tanh",
    "floor": "ti.floor",
    "ceil": "ti.ceil",
    # Constants pycode prints as math.pi / math.e (ti.pi does NOT exist; the
    # constants live under ti.math). Harmless for the current hyperelastics,
    # registered so a model that does use them compiles instead of raising.
    "pi": "ti.math.pi",
    "e": "ti.math.e",
}

_MATH_CALL_RE = re.compile(r"\bmath\.([A-Za-z_]\w*)")

# Host-NumPy counterpart of :data:`_MATH_TO_TAICHI`, used by the derived
# ``tangent_matvec`` body — a plain Python/NumPy routine (not a ``@ti.func``),
# so ``math.*`` is rewritten to the already-imported ``np.*`` rather than to
# ``ti.*``. Names differ from the Taichi/host spellings where NumPy diverges
# (``math.asin`` -> ``np.arcsin``); an explicit table makes those correct.
_MATH_TO_NUMPY: dict[str, str] = {
    "sqrt": "np.sqrt",
    "exp": "np.exp",
    "log": "np.log",
    "sin": "np.sin",
    "cos": "np.cos",
    "tan": "np.tan",
    "asin": "np.arcsin",
    "acos": "np.arccos",
    "atan": "np.arctan",
    "tanh": "np.tanh",
    "floor": "np.floor",
    "ceil": "np.ceil",
    "pi": "np.pi",
    "e": "np.e",
}


def _to_numpy_math(expr_src: str) -> str:
    """Rewrite ``pycode``'s ``math.*`` calls to their NumPy counterparts for the
    host-side derived ``tangent_matvec`` body. Fails loud on an unregistered
    ``math.*`` (mirrors :func:`_to_taichi_math`)."""

    def _sub(match: re.Match[str]) -> str:
        fn = match.group(1)
        numpy = _MATH_TO_NUMPY.get(fn)
        if numpy is None:
            raise NotImplementedError(
                f"emitted tangent expression uses math.{fn}, which has no registered "
                f"NumPy equivalent; add it to _MATH_TO_NUMPY in codegen/energy_emitter.py "
                f"(supported: {sorted(_MATH_TO_NUMPY)})."
            )
        return numpy

    return _MATH_CALL_RE.sub(_sub, expr_src)


def _to_taichi_math(expr_src: str) -> str:
    """Rewrite ``pycode``'s ``math.*`` calls to their Taichi counterparts so the
    emitted expression runs inside a ``@ti.func``.

    Uses a token-boundary regex (not chained ``str.replace``) so overlapping
    names like ``math.tan`` / ``math.tanh`` can never collide, and raises on an
    unregistered ``math.*`` rather than emitting source Taichi cannot compile —
    so a future energy (e.g. Ogden) that needs a new function fails with a clear,
    actionable message instead of a cryptic JIT error."""

    def _sub(match: re.Match[str]) -> str:
        fn = match.group(1)
        taichi = _MATH_TO_TAICHI.get(fn)
        if taichi is None:
            raise NotImplementedError(
                f"emitted expression uses math.{fn}, which has no registered Taichi "
                f"equivalent; add it to _MATH_TO_TAICHI in codegen/energy_emitter.py "
                f"(supported: {sorted(_MATH_TO_TAICHI)})."
            )
        return taichi

    return _MATH_CALL_RE.sub(_sub, expr_src)


def _parameter_symbols(model: EnergyModel) -> list[Symbol]:
    """Sorted parameter symbols (everything in the stress that is not a strain
    component), so the emitted signature is deterministic."""
    params = {s for s in model.pk2.free_symbols if not s.name.startswith(_STRAIN)}
    return sorted(params, key=lambda s: s.name)


def derived_param_names(model: EnergyModel) -> list[str]:
    """Sorted union of material-parameter names appearing in the derived PK2
    stress or the derived rank-4 tangent.

    This is the single vocabulary the generated solver is parameterised on for a
    LaTeX-derived model: the ``constitutive_update`` / ``tangent_matvec`` /
    ``newton_solve`` signatures and the ``__main__`` parameter setup all use it,
    so a derived bundle produces a runnable solver instead of one hard-coded to
    the SVK/J2 ``(lam, mu)`` names. The union (not just the stress params)
    guarantees a parameter that survives only into the tangent is still plumbed.
    """
    names = {s.name for s in _parameter_symbols(model)}
    names |= {s.name for s in _tangent_parameter_symbols(model)}
    return sorted(names)


def emit_constitutive_func(
    model: EnergyModel,
    *,
    func_name: str = "constitutive_update",
    param_names: list[str] | None = None,
) -> str:
    """Return a Taichi ``@ti.func`` computing PK2 stress ``S(F)`` from the
    derived energy model.

    The function takes the deformation gradient ``F`` and one ``ti.f64``
    argument per material parameter, computes the Green-Lagrange strain
    ``E = 0.5 (F^T F - I)``, and assigns each ``S[i, j]`` from the
    differentiated energy expression.

    ``param_names`` overrides the argument list (default: the parameters the
    stress actually uses). Pass :func:`derived_param_names` so the signature
    matches the unified vocabulary the generated solver forwards — a parameter
    that appears only in the tangent then rides along as an unused (harmless)
    argument, keeping the ``constitutive_update(F, ...)`` call site consistent.
    """
    # Rename strain symbols EDDij -> Eij to match the per-component locals the
    # body declares from the strain matrix.
    strain_subs = {
        model.strain_symbols[i][j]: Symbol(f"E{i}{j}") for i in range(3) for j in range(3)
    }

    args = param_names if param_names is not None else [s.name for s in _parameter_symbols(model)]
    # @ti.func arguments are untyped: Taichi infers their types from the call
    # site (ti.types.matrix annotations are only valid on @ti.kernel args).
    arglist = ", ".join(["F", *args])
    head = [
        "@ti.func",
        f"def {func_name}({arglist}):",
    ]
    body = [
        '"""PK2 stress derived from a LaTeX strain-energy density."""',
        "C = F.transpose() @ F",
        "I3 = ti.Matrix.identity(ti.f64, 3)",
        "E = 0.5 * (C - I3)",
    ]
    for i in range(3):
        for j in range(3):
            body.append(f"E{i}{j} = E[{i}, {j}]")
    body.append("S = ti.Matrix.zero(ti.f64, 3, 3)")
    for i in range(3):
        for j in range(3):
            expr = model.pk2[i, j].xreplace(strain_subs)
            body.append(f"S[{i}, {j}] = {_to_taichi_math(pycode(expr))}")
    body.append("return S")

    indent = "    "
    return "\n".join(head + [indent + line for line in body]) + "\n"


def _tangent_parameter_symbols(model: EnergyModel) -> list[Symbol]:
    """Sorted parameter symbols appearing in the rank-4 tangent (everything that
    is not a strain component), so the emitted signature is deterministic.

    Differs from :func:`_parameter_symbols` (which scans the PK2 stress): a
    parameter that survives differentiation only into the tangent — never the
    stress — must still appear in the tangent signature."""
    params: set[Symbol] = set()
    for i in range(3):
        for j in range(3):
            for k in range(3):
                for el in range(3):
                    params.update(
                        s
                        for s in model.tangent[i, j, k, el].free_symbols
                        if not s.name.startswith(_STRAIN)
                    )
    return sorted(params, key=lambda s: s.name)


def emit_tangent_func(model: EnergyModel, *, func_name: str = "tangent_update") -> str:
    """Return a Taichi ``@ti.func`` computing the 6x6 Voigt material tangent
    ``D_VW(F)`` from the derived energy model.

    The emitted form is the tensorial Voigt 6x6 (``ti.Matrix(6, 6)``), the
    natural Taichi shape: row/column ``a`` map to tensor index pair
    ``VOIGT_MAP_3D[a]`` with unscaled shears (07-CONVENTIONS §2). Each entry is
    taken from the derived rank-4 ``C_IJKL`` at ``(i,j,k,l) = (VOIGT_MAP_3D[a],
    VOIGT_MAP_3D[b])`` — identical to :func:`voigt.tangent_to_voigt_66`, so the
    derived emission and the oracle compare in the *same* representation.

    Like :func:`emit_constitutive_func`, the function takes ``F`` and one
    ``ti.f64`` argument per material parameter, builds the Green-Lagrange strain
    ``E = 0.5 (F^T F - I)``, and assigns each ``D[a, b]`` from the differentiated
    tangent expression (``math.*`` rewritten to ``ti.*`` so it JIT-compiles).
    """
    params = _tangent_parameter_symbols(model)
    strain_subs = {
        model.strain_symbols[i][j]: Symbol(f"E{i}{j}") for i in range(3) for j in range(3)
    }

    arglist = ", ".join(["F"] + [s.name for s in params])
    head = [
        "@ti.func",
        f"def {func_name}({arglist}):",
    ]
    body = [
        '"""6x6 Voigt material tangent derived from a LaTeX strain-energy density."""',
        "C = F.transpose() @ F",
        "I3 = ti.Matrix.identity(ti.f64, 3)",
        "E = 0.5 * (C - I3)",
    ]
    for i in range(3):
        for j in range(3):
            body.append(f"E{i}{j} = E[{i}, {j}]")
    body.append("D = ti.Matrix.zero(ti.f64, 6, 6)")
    for a, (i, j) in enumerate(VOIGT_MAP_3D):
        for b, (k, el) in enumerate(VOIGT_MAP_3D):
            expr = model.tangent[i, j, k, el].xreplace(strain_subs)
            body.append(f"D[{a}, {b}] = {_to_taichi_math(pycode(expr))}")
    body.append("return D")

    indent = "    "
    return "\n".join(head + [indent + line for line in body]) + "\n"


def emit_derived_tangent_matvec_body(model: EnergyModel) -> list[str]:
    """Host-NumPy lines for the derived material term inside ``tangent_matvec``.

    Returns the statements (no leading indent) that, given the Green-Lagrange
    strain ``E`` and the linearised strain ``dE`` (both ``(3, 3)`` ``np.ndarray``)
    and the derived material parameters already in scope, assign:

    - ``S``  — the derived PK2 stress ``(3, 3)`` (needed for the geometric term
      ``dP = grad_v @ S + F @ dS``), and
    - ``dS`` — the linearised PK2 stress ``C_IJKL : dE`` ``(3, 3)`` (material term).

    The full rank-4 ``C_IJKL`` is built and contracted with ``dE`` via
    ``np.einsum('ijkl,kl->ij', ...)`` so the result equals the oracle's
    ``C : dE`` exactly (no Voigt round-trip). ``tangent_matvec`` is a plain
    Python/NumPy routine, so ``pycode``'s ``math.*`` is rewritten to ``np.*``
    (fail-loud on an unregistered function) rather than to ``ti.*``.
    """
    strain_subs = {
        model.strain_symbols[i][j]: Symbol(f"E{i}{j}") for i in range(3) for j in range(3)
    }
    lines: list[str] = ["# Derived constitutive law (from LaTeX strain energy)."]
    for i in range(3):
        for j in range(3):
            lines.append(f"E{i}{j} = E[{i}, {j}]")
    lines.append("S = np.zeros((3, 3), dtype=np.float64)")
    for i in range(3):
        for j in range(3):
            expr = model.pk2[i, j].xreplace(strain_subs)
            if expr == 0:
                continue
            lines.append(f"S[{i}, {j}] = {_to_numpy_math(pycode(expr))}")
    lines.append("C4 = np.zeros((3, 3, 3, 3), dtype=np.float64)")
    for i in range(3):
        for j in range(3):
            for k in range(3):
                for el in range(3):
                    expr = model.tangent[i, j, k, el].xreplace(strain_subs)
                    if expr == 0:
                        continue
                    lines.append(f"C4[{i}, {j}, {k}, {el}] = {_to_numpy_math(pycode(expr))}")
    lines.append("dS = np.einsum('ijkl,kl->ij', C4, dE)")
    return lines
