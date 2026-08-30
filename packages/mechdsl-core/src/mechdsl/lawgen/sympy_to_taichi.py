"""Deterministic SymPy → Taichi scalar-expression lowerer (Task P2-1).

Part of the MechDSL lawgen pipeline (YAML law spec → restricted SymPy →
Taichi carrier).

This module is the foundation the rest of Phase 2 builds on: a *dedicated*,
idiomatic SymPy printer that turns a scalar ``sympy.Expr`` into a Taichi source
string, plus a public :func:`lower_expression` entry point that applies
deterministic common-subexpression elimination (CSE) before printing.

Why a bespoke printer (the R4 correction)
-----------------------------------------
The P1-3 reuse audit (``lawgen/REUSE.md``, Gate-B-verified) established that
``codegen/taichi_printer.py`` has **no** reusable scalar SymPy→Taichi printer —
its surface is FEM ``ArtifactBundle`` emission with hard-coded literal Taichi.
The only existing SymPy→Taichi code lives in ``codegen/energy_emitter.py`` and
converts the expression to Python source (SymPy's ``py``-``code`` printer) then
rewrites ``math.*`` to ``ti.*`` with a regex substitution over that string. That
is the **R4 anti-pattern** the plan forbids: brittle string surgery, no CSE, no
whitelist enforcement at the printer boundary.

So P2-1 adds a proper printer instead. It subclasses SymPy's
:class:`~sympy.printing.str.StrPrinter` and overrides the relevant ``_print_*``
methods, so function/operator lowering happens *inside* SymPy's own dispatch —
no Python-source printing, no regex. Unmapped nodes fail loud (R2): a clear
``NotImplementedError`` naming the node and the phase that adds it, never silent
wrong code.

Scope of this task
------------------
Printer + deterministic CSE **only**. Deliberately out of scope (separate
tasks — clean seams are noted inline where each attaches):

* **P2-2** — scalar-expression budget counting over the six ``TiconstitTarget``
  knobs.
* **P2-3** — numerical-guard injection (``ti.max(x, 1e-12)`` for log/sqrt,
  ``ti.select`` for pow with symbolic exponent, guarded division). This printer
  emits ``ti.pow``/``ti.log``/``ti.sqrt`` *unguarded*; P2-3 attaches a rewrite
  pass upstream of :func:`lower_expression` (or wraps the mapped names).
* **P2-4** — ``Piecewise`` → nested ``ti.select`` lowering, small-integer ``Pow``
  inlining, and a ``source_hash`` provenance field on :class:`LoweredExpr`
  (see the extension note on the dataclass).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import sympy as sp
from sympy.printing.precedence import PRECEDENCE, precedence
from sympy.printing.str import StrPrinter

from mechdsl.lawgen.budgets import _budget_diagnostic, count_piecewise_branches
from mechdsl.lawgen.contracts import TiconstitTarget
from mechdsl.lawgen.diagnostics import DiagnosticCollector, LawgenDiagnostic
from mechdsl.lawgen.guard_transforms import (
    GUARD_FLOOR_LITERAL,
    GUARD_FLOOR_NEG_LITERAL,
    GuardFloor,
    GuardSignedFloor,
    inject_guards,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

# Small-integer ``Pow`` inlining threshold.
#
# ``Pow(x, n)`` with ``n`` a **non-negative** integer and ``n <=
# SMALL_INT_POW_LIMIT`` is inlined to repeated multiplication (``x**2`` →
# ``x*x``); a larger magnitude, a negative exponent, or a symbolic/fractional
# exponent keeps ``ti.pow`` / ``**`` (guarded by the guard-injection pass).
# ``4`` is chosen so the worst inlined case unrolls to at most four factors
# (``x*x*x*x``) — comfortably inside the JIT line budget (a ``ti.pow`` call is
# one line, so inlining trades one call for up to three extra ``*`` ops, never
# a whole line) while covering the common material-model powers (square/cube).
# It is a deliberately conservative bound: raising it risks a large unrolled
# multiplication.
SMALL_INT_POW_LIMIT: int = 4


def _inlines_to_product(item: sp.Basic) -> bool:
    """True if ``item`` is a ``Pow`` this printer inlines to a multi-factor product.

    A ``Pow(base, n)`` with ``n`` an integer and ``2 <= n <= SMALL_INT_POW_LIMIT``
    prints as ``base*base*...`` — a value at ``Mul`` precedence, not ``Pow``
    precedence. :meth:`TaichiExprPrinter.parenthesize` uses this to wrap such a
    node when it sits at ``Mul`` level (notably as a division denominator), so
    ``a/x**2`` renders as ``a/(x*x)`` and never the mis-grouped ``a/x*x`` (which
    would evaluate to ``a`` — the Gate-B silently-wrong-math bug). ``n`` of 0/1
    fold to ``"1"``/``base`` (already atomic), so only ``n >= 2`` needs wrapping.
    """
    return (
        isinstance(item, sp.Pow)
        and isinstance(item.exp, sp.Integer)
        and 2 <= int(item.exp) <= SMALL_INT_POW_LIMIT
    )


__all__ = [
    "MATH_TO_TAICHI",
    "SMALL_INT_POW_LIMIT",
    "LoweredExpr",
    "TaichiExprPrinter",
    "TaichiGuardedPrinter",
    "compute_source_hash",
    "lower_expression",
]

# ---------------------------------------------------------------------------
# The canonical SymPy-function → Taichi-name map.
#
# This is the single source of truth for which scalar functions this printer
# can lower and what they lower to. It is kept in deliberate alignment with:
#   * ``codegen/energy_emitter._MATH_TO_TAICHI`` — the existing (regex-based)
#     math→ti name table; we reuse the *mapping idea*, not its
#     print-to-source-plus-regex mechanism.
#   * ``lawgen/cli._ALLOWED_FUNCTIONS`` — the front-end parser allow-list
#     (``exp, log, sqrt, sin, cos, tan, sinh, cosh, tanh, Abs, Max, Min,
#     sign``). Every function the CLI accepts into an R/H/Q expression MUST be
#     lowerable here, or a legal law would parse but fail to emit.
#
# Keyed by the SymPy function class name (``type(node).__name__`` /
# ``node.func.__name__``); valued by the Taichi call name. ``sqrt`` is handled
# specially in ``_print_Pow`` (SymPy models it as ``Pow(x, 1/2)``, not a
# ``Function``), but is listed here so the allowed-set is one table.
#
# Today this map and ``cli._ALLOWED_FUNCTIONS`` are two aligned literals; the
# alignment is asserted in the tests.
# ---------------------------------------------------------------------------
MATH_TO_TAICHI: dict[str, str] = {
    "exp": "ti.exp",
    "log": "ti.log",
    "sqrt": "ti.sqrt",
    "sin": "ti.sin",
    "cos": "ti.cos",
    "tan": "ti.tan",
    "sinh": "ti.sinh",
    "cosh": "ti.cosh",
    "tanh": "ti.tanh",
    "Abs": "ti.abs",
    "Max": "ti.max",
    "Min": "ti.min",
    "sign": "ti.sign",
    # ``pow`` is emitted via ``_print_Pow`` for a symbolic/general exponent;
    # registered here so the name is part of the one allowed-function table.
    "pow": "ti.pow",
}

# SymPy ``Function`` *subclasses* that this lowerer supports via a dedicated
# ``_print_*`` method rather than a :data:`MATH_TO_TAICHI` name mapping. These
# must be excluded from the unsupported-function sweep
# (:func:`_unsupported_function_names`), which walks ``expr.atoms(sp.Function)``:
# ``sp.Piecewise`` is a ``sp.Function`` subclass but is fully supported
# (``_print_Piecewise`` → nested ``ti.select``), so without this exclusion it
# would be mis-reported as an unmapped node. (``sp.Max``/``sp.Min`` are
# ``MinMaxBase``, not ``sp.Function``, so they never appear in that sweep and do
# not need listing here.)
_SUPPORTED_FUNCTION_NODES: frozenset[str] = frozenset({"Piecewise"})


class TaichiExprPrinter(StrPrinter):
    """A :class:`~sympy.printing.str.StrPrinter` that emits Taichi source.

    Deterministic and regex-free: lowering happens through SymPy's own
    ``_print_*`` dispatch, so the same expression always prints to the same
    string (given a fixed SymPy version) and no print-to-Python-source plus
    string-substitution step is involved.

    Behaviour
    ---------
    * Symbols print as their name; ``Integer``/``Float``/``Rational`` print as
      numeric literals; ``Add``/``Mul`` and integer/general ``Pow`` print via
      the base :class:`StrPrinter` (``x**n`` stays ``x**n`` for P2-1).
    * Whitelisted functions (:data:`MATH_TO_TAICHI`) print as their ``ti.*``
      call, e.g. ``exp(-b*p)`` → ``ti.exp(-b*p)``.
    * ``sqrt(x)`` — SymPy's ``Pow(x, 1/2)`` — prints as ``ti.sqrt(x)`` rather
      than the base printer's literal ``sqrt(x)``.
    * **Fail loud (R2):** any function/node this printer does not map raises
      :class:`NotImplementedError` naming the node and the phase that adds it.
      Nothing is emitted silently.
    """

    printmethod = "_taichi"

    def parenthesize(self, item: sp.Basic, level: int, strict: bool = False) -> str:
        """Parenthesise ``item`` at ``level``, treating inlined powers as products.

        Identical to :meth:`StrPrinter.parenthesize` except that a small
        positive-integer ``Pow`` — which :meth:`_print_Pow` inlines to a
        multi-factor product (``x**2`` → ``x*x``) — is judged at ``Mul``
        precedence instead of ``Pow`` precedence for the wrap decision.

        Why (Gate-B critical): SymPy's :meth:`StrPrinter._print_Mul` places a
        reciprocal power in the denominator by calling ``parenthesize`` on the
        *positive* ``Pow`` (e.g. ``Pow(x, 2)`` for ``a/x**2``). The stock method
        wraps only when ``precedence(item) <= level``; a ``Pow`` node reports
        precedence 60 > ``Mul``'s 50, so it is left unwrapped — but our inlined
        print is the product ``x*x`` (precedence 50), yielding the mis-grouped
        ``a/x*x`` which evaluates to ``a`` (silently-wrong math). Reporting the
        inlined power at ``Mul`` precedence makes the denominator wrap correctly
        (``a/(x*x)``) while a standalone ``x**2`` still prints as the bare
        ``x*x``. This also covers the guarded reciprocal
        (``a/x**2`` with guards → ``a/(<signed-floor>*<signed-floor>)``).
        """
        eff = PRECEDENCE["Mul"] if _inlines_to_product(item) else precedence(item)
        if (eff < level) or ((not strict) and eff <= level):
            return f"({self._print(item)})"
        return str(self._print(item))

    def _print_Function(self, expr: sp.Function) -> str:
        """Print a whitelisted SymPy function as its ``ti.*`` call.

        Any function not in :data:`MATH_TO_TAICHI` (an unregistered SymPy
        function such as ``erf`` or ``gamma``) fails loud rather than emitting
        a call Taichi cannot compile.
        """
        name = expr.func.__name__
        taichi = MATH_TO_TAICHI.get(name)
        if taichi is None:
            raise NotImplementedError(
                f"TaichiExprPrinter cannot lower SymPy function {name!r}: it is "
                f"not in the Taichi allow-list {sorted(MATH_TO_TAICHI)}. Register "
                "it in MATH_TO_TAICHI (lawgen/sympy_to_taichi.py) if Taichi "
                "supports it."
            )
        args = ", ".join(self._print(arg) for arg in expr.args)
        return f"{taichi}({args})"

    def _print_Max(self, expr: sp.Max) -> str:
        """Print ``Max(a, b, ...)`` as a ``ti.max`` call.

        SymPy models ``Max``/``Min`` as ``MinMaxBase`` (a lattice op), *not* a
        ``Function``, so ``_print_Function`` never sees them and the base
        printer would emit a bare ``Max(...)``. Route them through the allowed
        table explicitly. Taichi's ``ti.max``/``ti.min`` are variadic, so an
        n-ary ``Max`` maps one-to-one.
        """
        args = ", ".join(self._print(arg) for arg in expr.args)
        return f"{MATH_TO_TAICHI['Max']}({args})"

    def _print_Min(self, expr: sp.Min) -> str:
        """Print ``Min(a, b, ...)`` as a ``ti.min`` call (see ``_print_Max``)."""
        args = ", ".join(self._print(arg) for arg in expr.args)
        return f"{MATH_TO_TAICHI['Min']}({args})"

    def _print_Pow(self, expr: sp.Pow, rational: bool = False) -> str:
        """Print a ``Pow`` node: ``sqrt`` → ``ti.sqrt``, small-int → multiplication.

        SymPy canonicalises ``sqrt(x)`` as ``Pow(x, S.Half)``; the base
        :class:`StrPrinter` would emit literal ``sqrt(x)`` (not a ``ti.*``
        call). We intercept the ``S.Half`` exponent and emit ``ti.sqrt(base)``
        so the allowed-function table stays the single source of truth.

        Small-integer inlining (P2-4)
        -----------------------------
        A ``Pow(base, n)`` with ``n`` a **non-negative** integer and ``n <=
        SMALL_INT_POW_LIMIT`` is inlined to repeated multiplication instead of a
        ``ti.pow`` call: ``x**2`` → ``x*x``, ``x**3`` → ``x*x*x``. Trivial powers
        fold to their identities: ``x**1`` → ``x``, ``x**0`` → ``1``.

        **Negative** integer exponents are deliberately NOT inlined here (Gate-B
        critical fix). A ``Pow(base, -k)`` is a reciprocal; SymPy's
        :meth:`StrPrinter._print_Mul` owns its placement in the denominator — for
        ``a/x**2`` (= ``Mul(a, Pow(x, -2))``) it moves the reciprocal into the
        denominator and prints the *positive* counterpart ``Pow(x, 2)`` through
        this method. If this method instead returned a self-contained ``1/(x*x)``
        for the negative node, it would collide with that split and emit
        ``a/x*x`` — which under left-to-right ``/``/``*`` evaluates to ``a``
        (silently-wrong math, e.g. ``mu/J**2`` → ``mu/J*J``). So the positive
        denominator power that ``_print_Mul`` hands back *is* inlined to ``x*x``,
        and the collapse is prevented by :meth:`parenthesize` (overridden above),
        which reports an inlined power at ``Mul`` precedence so ``_print_Mul``
        wraps the denominator → ``a/(x*x)``. This holds on the guarded path too
        (``a/x**2`` → ``a/(<signed-floor>*<signed-floor>)``). This runs on the
        already-guarded tree, so ``base`` carries any P2-3 guard injected.
        """
        # Mirror SymPy's own idiom (``-expr.exp is S.Half``): negate then
        # identity-check, so an exact ``Rational(-1, 2)`` matches while a
        # ``-0.5`` float does not accidentally route to sqrt.
        if expr.exp is sp.S.Half:
            return f"{MATH_TO_TAICHI['sqrt']}({self._print(expr.base)})"
        if -expr.exp is sp.S.Half:
            return f"1/{MATH_TO_TAICHI['sqrt']}({self._print(expr.base)})"
        if isinstance(expr.exp, sp.Integer):
            inlined = self._inline_small_int_pow(expr.base, int(expr.exp))
            if inlined is not None:
                return inlined
        # ``str(...)``: SymPy is untyped, so the base ``_print_Pow`` is inferred
        # as ``Any``; coerce to satisfy the declared ``-> str`` (it already
        # returns a str at runtime).
        return str(super()._print_Pow(expr, rational=True))

    def _inline_small_int_pow(self, base: sp.Expr, n: int) -> str | None:
        """Inline ``base**n`` to multiplication for a small **non-negative** ``n``.

        Returns the inlined Taichi source, or ``None`` to signal "not inlinable —
        let the caller fall back to the base printer" when ``n`` is negative or
        exceeds :data:`SMALL_INT_POW_LIMIT`.

        Forms (``b`` is the printed, already-guarded base):

        * ``n == 0`` → ``"1"`` (``x**0``).
        * ``n == 1`` → ``b`` (``x**1``).
        * ``n >= 2`` → ``b*b*...`` (``n`` factors), e.g. ``x**2`` → ``x*x``.

        Negative ``n`` returns ``None`` on purpose: a ``Pow`` with a negative
        exponent is a reciprocal, and SymPy's :meth:`StrPrinter._print_Mul` must
        own its placement in the denominator (with correct parenthesisation) —
        inlining it here to a standalone ``1/(...)`` collides with that split and
        produces mathematically wrong, mis-parenthesised division (Gate-B
        critical). The *positive* denominator power that ``_print_Mul`` derives is
        what gets inlined instead.

        The base is parenthesised at ``Mul`` precedence, so a compound base
        (``(a + b)**2`` → ``(a + b)*(a + b)``) is grouped correctly and a bare
        symbol (``x**2`` → ``x*x``) is not over-parenthesised.
        """
        if n < 0 or n > SMALL_INT_POW_LIMIT:
            return None
        if n == 0:
            return "1"
        printed = self.parenthesize(base, PRECEDENCE["Mul"])
        return "*".join([printed] * n)

    def _print_Piecewise(self, expr: sp.Piecewise) -> str:
        """Lower a ``Piecewise`` to a right-nested ``ti.select`` chain (P2-4).

        ``Piecewise((e1, c1), (e2, c2), ..., (en, True))`` →
        ``ti.select(c1, e1, ti.select(c2, e2, ... en))``. Each branch value and
        each condition is lowered recursively through this printer, so guards
        injected inside a branch expression (P2-3) render normally and a nested
        ``Piecewise`` becomes a nested ``ti.select``. Relational conditions
        (``x > 0``) print via the base :class:`StrPrinter` as Taichi-valid scalar
        comparisons.

        The final branch must be the exhaustive default (``cond is True``); its
        value becomes the innermost ``ti.select`` else-argument. A non-exhaustive
        ``Piecewise`` (no ``True`` tail) fails loud (R2) — Taichi ``ti.select``
        has no "undefined" result, so a missing default would silently emit a
        wrong fallthrough. The branch-count *budget* gate is enforced upstream in
        :func:`lower_expression` (pre-emission), not here.
        """
        branches = expr.args
        if branches[-1].cond is not sp.true:
            raise NotImplementedError(
                "TaichiExprPrinter cannot lower a non-exhaustive Piecewise "
                f"{expr!r}: the final branch must be the default ``(value, True)`` "
                "so the nested ti.select has a defined else-value (no silent "
                "fallthrough — R2)."
            )
        # Build the chain from the innermost (default value) outward, so the
        # right-nesting matches the branch order left-to-right. ``str(...)``:
        # ``self._print`` is ``Any`` (SymPy is untyped), coerce to the declared
        # ``-> str`` (it already returns a str at runtime).
        result = str(self._print(branches[-1].expr))
        for pair in reversed(branches[:-1]):
            cond = self._print(pair.cond)
            value = self._print(pair.expr)
            result = f"ti.select({cond}, {value}, {result})"
        return result


class TaichiGuardedPrinter(TaichiExprPrinter):
    """A :class:`TaichiExprPrinter` that renders the P2-3 guard marker nodes.

    Pairs with :func:`mechdsl.lawgen.guard_transforms.inject_guards`: that pass
    wraps guardable sub-trees in :class:`~mechdsl.lawgen.guard_transforms.\
GuardFloor` / :class:`~mechdsl.lawgen.guard_transforms.GuardSignedFloor`
    markers, and this printer turns those markers into concrete Taichi. The two
    are always used together (the base :class:`TaichiExprPrinter` is the raw,
    unguarded path).

    Guard rendering
    ---------------
    * ``GuardFloor(arg)``       → ``ti.max(<arg>, 1e-12)`` (positive-domain floor).
    * ``GuardSignedFloor(arg)`` → ``ti.select(<arg> >= 0, ti.max(<arg>, 1e-12),
      ti.min(<arg>, -1e-12))`` (sign-preserving denominator guard).
    * ``Pow`` whose base is a floored marker and whose exponent is not the
      ``sqrt`` half → ``ti.pow(ti.max(base, 1e-12), exp)`` (matching Cycle 0's
      ``swift_voce.py`` ``get_R``: a floored base is emitted through ``ti.pow``,
      not the base printer's ``**``). This holds for a *negative* fractional
      exponent too — the rewrite pass only floors a base when the power is
      genuinely fractional, never for a negative-integer reciprocal.

    The ``1e-12`` epsilon is emitted verbatim from
    :data:`~mechdsl.lawgen.guard_transforms.GUARD_FLOOR_LITERAL`, so it never
    passes through SymPy ``Float`` formatting (which would print ``1.0e-12``).
    """

    def _print_GuardFloor(self, expr: GuardFloor) -> str:
        """Render the positive-domain floor marker as ``ti.max(arg, 1e-12)``."""
        return f"{MATH_TO_TAICHI['Max']}({self._print(expr.args[0])}, {GUARD_FLOOR_LITERAL})"

    def _print_GuardSignedFloor(self, expr: GuardSignedFloor) -> str:
        """Render the sign-preserving denominator guard.

        ``ti.select(arg >= 0, ti.max(arg, 1e-12), ti.min(arg, -1e-12))`` — floors
        the magnitude to ``1e-12`` while keeping ``arg``'s sign (a no-op for
        ``|arg| >= 1e-12``). ``ti.select``/``ti.max``/``ti.min`` are all valid
        Taichi scalar ops.
        """
        arg = self._print(expr.args[0])
        pos = f"{MATH_TO_TAICHI['Max']}({arg}, {GUARD_FLOOR_LITERAL})"
        neg = f"{MATH_TO_TAICHI['Min']}({arg}, {GUARD_FLOOR_NEG_LITERAL})"
        return f"ti.select({arg} >= 0, {pos}, {neg})"

    def _print_Pow(self, expr: sp.Pow, rational: bool = False) -> str:
        """Route a floored-base power to ``ti.pow``; otherwise defer to the base.

        When the base is a :class:`~mechdsl.lawgen.guard_transforms.GuardFloor`
        marker and the exponent is not the ``sqrt`` half, emit
        ``ti.pow(ti.max(base, 1e-12), exp)`` — the exact ``swift_voce.py`` idiom
        — for any (fractional / symbolic, positive or negative) exponent. The
        ``sqrt`` half-exponent case falls through to the base printer, which
        produces ``ti.sqrt(...)`` with the floored marker rendered inside. A
        :class:`~mechdsl.lawgen.guard_transforms.GuardSignedFloor` base (a
        reciprocal denominator) is likewise handled by the base printer, which
        formats the division and renders the marker via ``_print_GuardSignedFloor``.
        """
        base = expr.base
        if isinstance(base, GuardFloor) and expr.exp is not sp.S.Half:
            return f"{MATH_TO_TAICHI['pow']}({self._print(base)}, {self._print(expr.exp)})"
        return super()._print_Pow(expr, rational=rational)


def _unsupported_function_names(expr: sp.Basic) -> list[str]:
    """Return every function name in ``expr`` this lowerer cannot map, sorted.

    Catches BOTH failure modes in one pre-pass over ``expr.atoms(sp.Function)``:

    * an ``AppliedUndef`` — a call to a function outside the allow-list (a typo
      like ``foo`` or ``expp``), and
    * a *defined-but-unmapped* SymPy function (``erf``, ``gamma``) whose name is
      not a key of :data:`MATH_TO_TAICHI`.

    Two families of *supported* nodes are deliberately not swept up here:

    * ``sp.Max``/``sp.Min`` are ``MinMaxBase`` (not ``sp.Function``), so
      ``atoms(sp.Function)`` never returns them — they have dedicated
      ``_print_Max``/``_print_Min`` methods.
    * ``sp.Piecewise`` *is* a ``sp.Function`` subclass, so it would otherwise be
      mis-flagged as unmapped; it is excluded via
      :data:`_SUPPORTED_FUNCTION_NODES` because it has a dedicated
      ``_print_Piecewise`` lowering (its branch-count budget and exhaustiveness
      are checked separately in the pre-pass).

    Collecting all unmapped names up front (rather than raising on the first one
    deep in the recursive printer) is what lets the caller report *every*
    unsupported node in a single
    :class:`~mechdsl.lawgen.diagnostics.LawgenError` (P3-1 collect-all).
    """
    names = {
        type(fn).__name__
        for fn in expr.atoms(sp.Function)
        if type(fn).__name__ not in MATH_TO_TAICHI
        and type(fn).__name__ not in _SUPPORTED_FUNCTION_NODES
    }
    return sorted(names)


def _collect_unsupported(expr: sp.Basic, *, law: str, collector: DiagnosticCollector) -> None:
    """Add a diagnostic for each unsupported function node in ``expr`` (R2, collect-all).

    One diagnostic per distinct unmapped function name, so two unsupported nodes
    in the same law surface as two diagnostics in the one
    :class:`~mechdsl.lawgen.diagnostics.LawgenError`. Nothing is raised here — the
    caller (:func:`lower_expression`) raises the whole batch after every
    expression has been scanned (no silent fallback: an unmapped node always
    yields a diagnostic).
    """
    for name in _unsupported_function_names(expr):
        collector.add(
            LawgenDiagnostic(
                law=law,
                expression=str(expr),
                node=name,
                reason=(
                    f"function {name!r} is not in the Taichi allow-list "
                    f"{sorted(MATH_TO_TAICHI)}; it is an unknown/unsupported node "
                    "(no silent fallback — R2)."
                ),
                fix=(
                    f"remove or rewrite {name!r} using only allowed functions, or register "
                    f"{name!r} in MATH_TO_TAICHI (lawgen/sympy_to_taichi.py) if Taichi supports it."
                ),
            )
        )


def _collect_non_exhaustive_piecewise(
    expr: sp.Basic, *, law: str, collector: DiagnosticCollector
) -> None:
    """Add a diagnostic for each non-exhaustive ``Piecewise`` in ``expr`` (R2, collect-all).

    A ``Piecewise`` whose final branch condition is not ``True`` has no defined
    else-value; lowering it to nested ``ti.select`` would silently emit a wrong
    fallthrough (``ti.select`` has no "undefined" result). Detected in the same
    pre-pass so it collects alongside unsupported-function and budget diagnostics
    rather than raising mid-recursion.
    """
    for piece in expr.atoms(sp.Piecewise):
        if piece.args[-1].cond is not sp.true:
            collector.add(
                LawgenDiagnostic(
                    law=law,
                    expression=str(expr),
                    node="Piecewise",
                    reason=(
                        f"non-exhaustive Piecewise {piece!r}: the final branch is not the "
                        "default ``(value, True)``, so the nested ti.select would have no "
                        "defined else-value (silent fallthrough — R2)."
                    ),
                    fix=(
                        "add a terminal default branch ``(value, True)`` so the switch is "
                        "exhaustive and the nested ti.select has a defined else-value."
                    ),
                )
            )


def _collect_piecewise_budget(
    expr: sp.Basic, target: TiconstitTarget, *, law: str, collector: DiagnosticCollector
) -> None:
    """Add a budget diagnostic if ``expr``'s largest ``Piecewise`` exceeds the branch budget.

    Reuses P2-2's :func:`~mechdsl.lawgen.budgets.count_piecewise_branches` and the
    shared budget-diagnostic builder, so the ``reason`` carries the measured
    branch count AND the ``max_piecewise_branches`` limit. Runs in the same
    pre-pass, so an over-budget switch never reaches the printer and its
    diagnostic collects alongside the others. ``count_piecewise_branches``
    returns ``0`` when there is no ``Piecewise``, so this is a no-op for ordinary
    expressions.
    """
    branches = count_piecewise_branches(expr)
    if branches > target.max_piecewise_branches:
        collector.add(
            _budget_diagnostic(
                "max_piecewise_branches", branches, target.max_piecewise_branches, law=law
            )
        )


@dataclass(frozen=True)
class LoweredExpr:
    """The deterministic result of lowering one or more scalar expressions.

    Immutable so a lowered result can be cached / hashed / compared safely.

    Attributes
    ----------
    temporaries:
        CSE temporary assignment lines, in emission order, e.g.
        ``("x0 = ti.exp(-b*p)",)``. Empty when CSE finds no shared
        sub-expression. These MUST be emitted before :attr:`returns` — the
        returns reference the ``x0``/``x1`` temporaries by name.
    returns:
        The reduced return-expression source lines, one per input expression,
        in the same order the inputs were supplied, e.g. ``("sigma0 + x0",)``.

    source_hash:
        A deterministic SHA-256 provenance digest over the emitted lines
        (:func:`compute_source_hash`), computed automatically in
        ``__post_init__``. 64 lowercase hex chars. Every ``LoweredExpr`` carries
        one — including instances constructed directly (P2-2's budget tests build
        ``LoweredExpr(temporaries=…, returns=…)`` without passing a hash). It is
        excluded from ``__init__`` (callers never supply it) and from equality
        (it is derived from ``temporaries``/``returns``, so two lowered results
        are equal iff their lines are — the hash carries no independent identity).
    """

    temporaries: tuple[str, ...]
    returns: tuple[str, ...]
    source_hash: str = field(default="", init=False, compare=False)

    def __post_init__(self) -> None:
        # Frozen dataclass: assign the derived hash via ``object.__setattr__``.
        object.__setattr__(self, "source_hash", compute_source_hash(self.temporaries, self.returns))


def compute_source_hash(temporaries: Sequence[str], returns: Sequence[str]) -> str:
    """Return the deterministic SHA-256 provenance hash of emitted lines.

    Hash input: the emitted lines joined with ``"\\n"`` in **emission order** —
    all :attr:`LoweredExpr.temporaries` first, then all :attr:`LoweredExpr.returns`
    (``temporaries + returns``), UTF-8 encoded. Emission order *is* the sort key:
    the CSE temporaries are emitted in canonical-CSE order (``order='canonical'``
    in :func:`lower_expression`) and the returns follow in input order, so the
    line sequence — and therefore the hash — is fully deterministic for a given
    input and SymPy version. Returns 64 lowercase hex chars.

    # NOTE (P4-2): this hashes the *emitted output lines*. Cycle 0's
    # ``swift_voce.py`` header + ``_manifest.json`` instead define ``source_hash``
    # as the SHA-256 of the canonical *input formula string* (the generator
    # INPUT, e.g. ``"R = sigma0 + Q*(1-exp(-b*p)) + K*((p+p0)**n - p0**n)"`` →
    # ``7b5af3a8…``), NOT the emitted output. This P2-4 hash satisfies the task's
    # determinism + 64-hex acceptance criteria but will NOT equal Cycle 0's hash.
    # This function is kept small and separately named so P4-1/P4-2 can add or
    # switch to an input-formula hash for manifest-matching without touching the
    # lowerer. Do NOT reconcile the two definitions here — that is P4's call.
    """
    payload = "\n".join([*temporaries, *returns])
    return hashlib.sha256(payload.encode()).hexdigest()


def lower_expression(
    exprs: sp.Expr | Sequence[sp.Expr],
    *,
    printer: TaichiExprPrinter | None = None,
    guards: bool = True,
    target: TiconstitTarget | None = None,
) -> LoweredExpr:
    """Lower scalar SymPy expression(s) to deterministic Taichi source lines.

    Pipeline
    --------
    1. Normalise ``exprs`` to a list (a single ``Expr`` is wrapped).
    2. Collect-all pre-pass (R2): scan every expression for unsupported nodes
       (unmapped/undefined functions), non-exhaustive ``Piecewise``, and each
       expression's largest ``Piecewise`` against the ``max_piecewise_branches``
       budget — accumulating a diagnostic per problem and raising them together
       as one :class:`~mechdsl.lawgen.diagnostics.LawgenError` *before* any code
       is produced (never fail-first, never a silent drop).
    3. **P2-3 guard injection** (when ``guards`` is true): rewrite each
       expression with :func:`~mechdsl.lawgen.guard_transforms.inject_guards`,
       floring ``log``/``sqrt``/symbolic-``pow`` bases with ``ti.max(·, 1e-12)``
       and guarding division denominators — reproducing Cycle 0's hand-authored
       ``swift_voce.py`` guards. ``exp`` is deliberately left **unguarded**.
       Injection runs *before* CSE so the marker nodes factor deterministically.
    4. Run ``sympy.cse(exprs, order='canonical')``. The ``order='canonical'``
       keyword is **mandatory**: SymPy's default CSE order is not deterministic
       across versions, whereas the canonical order gives a stable sort of the
       common sub-expressions — the guarantee the whole determinism story rests
       on.
    5. Emit the CSE temporaries first (``"x0 = <ti-source>"`` lines), then the
       reduced return expressions — with a :class:`TaichiGuardedPrinter` when
       ``guards`` is true (it renders the injected markers), else the raw
       :class:`TaichiExprPrinter`.

    Parameters
    ----------
    exprs:
        A single scalar ``sympy.Expr`` or an ordered sequence of them. Order is
        preserved: ``returns[i]`` corresponds to ``exprs[i]``.
    printer:
        Optional pre-built printer. Defaults to a :class:`TaichiGuardedPrinter`
        when ``guards`` is true, else a :class:`TaichiExprPrinter`. An explicit
        printer is used verbatim (the caller owns marker rendering then).
    guards:
        When ``True`` (default), inject the P2-3 numerical guards and render them
        with a guarded printer. Set ``False`` for the raw, unguarded lowering
        (the P2-1 path — used by tests and by callers that guard elsewhere).
        P2-4 / P4 depend on this flag: the guarded path is the one the P4-2
        equivalence gate measures.
    target:
        The :class:`~mechdsl.lawgen.contracts.TiconstitTarget` whose
        ``max_piecewise_branches`` knob gates ``Piecewise`` lowering. Defaults to
        a plain :class:`TiconstitTarget` (the plan-frozen default of 8 branches).
        A ``Piecewise`` with more branches yields a budget diagnostic in the
        collect-all :class:`~mechdsl.lawgen.diagnostics.LawgenError` before any
        ``ti.select`` is emitted (pre-emission fail-loud, reusing P2-2's counter
        and error).

    Returns
    -------
    LoweredExpr
        Immutable ``(temporaries, returns, source_hash)``. Deterministic: the
        same input yields byte-identical tuples and hash on repeat calls.

    Raises
    ------
    LawgenError
        Collect-all (P3-1): if any expression contains unsupported nodes, a
        non-exhaustive ``Piecewise``, or an over-budget ``Piecewise``, *every*
        such problem across *all* expressions is collected and raised together as
        one :class:`~mechdsl.lawgen.diagnostics.LawgenError` (a
        ``NotImplementedError`` subclass, preserving the Phase-2 fail-loud
        contract). Each diagnostic carries the offending node, a reason, and an
        actionable fix. No node is ever silently dropped (R2).
    TypeError
        If an element of ``exprs`` is not a ``sympy.Expr``.
    """
    active_target = target if target is not None else TiconstitTarget()
    expr_list = _as_expr_list(exprs)

    # Pre-pass (collect-all): scan every expression for unsupported nodes and
    # budget breaches BEFORE any code is produced, accumulating a diagnostic for
    # each so multiple problems surface in one LawgenError (never fail-first, never
    # a silent drop). Emission below only runs on a fully clean law.
    collector = DiagnosticCollector()
    for index, expr in enumerate(expr_list):
        law = f"expression #{index}"
        _collect_unsupported(expr, law=law, collector=collector)
        _collect_non_exhaustive_piecewise(expr, law=law, collector=collector)
        _collect_piecewise_budget(expr, active_target, law=law, collector=collector)
    collector.raise_if_any()

    if guards:
        expr_list = [inject_guards(expr) for expr in expr_list]

    if printer is not None:
        active_printer: TaichiExprPrinter = printer
    elif guards:
        active_printer = TaichiGuardedPrinter()
    else:
        active_printer = TaichiExprPrinter()

    # order='canonical' is mandatory — see the docstring. This is the single
    # CSE call in lawgen.
    replacements, reduced = sp.cse(expr_list, order="canonical")

    temporaries = tuple(
        f"{active_printer.doprint(sym)} = {active_printer.doprint(sub)}"
        for sym, sub in replacements
    )
    returns = tuple(active_printer.doprint(expr) for expr in reduced)
    return LoweredExpr(temporaries=temporaries, returns=returns)


def _as_expr_list(exprs: sp.Expr | Sequence[sp.Expr]) -> list[sp.Expr]:
    """Normalise the input to a list of validated ``sympy.Expr``.

    A single ``Expr`` (which is itself iterable via ``.args``) is wrapped, not
    iterated — otherwise ``sigma0 + x0`` would be mistaken for a sequence of its
    terms. Every element must be a genuine ``sympy.Expr`` (fail loud, no silent
    coercion).
    """
    items: Iterable[sp.Expr]
    items = [exprs] if isinstance(exprs, sp.Expr) else list(exprs)
    for index, item in enumerate(items):
        if not isinstance(item, sp.Expr):
            raise TypeError(
                f"lower_expression expected sympy.Expr, got "
                f"{type(item).__name__} {item!r} at index {index}."
            )
    return list(items)
