"""Numerical-guard injection for the SymPy → Taichi lowerer (Task P2-3).

Part of the MechDSL lawgen pipeline (YAML law spec → restricted SymPy →
Taichi carrier). Correctness-critical: the guards emitted here must match the
hand-authored guards in the reference ``swift_voce.py`` so the
numerical-equivalence check (``rtol=1e-10``) holds.

Mechanism — a SymPy-tree rewrite pass with stand-in marker nodes
----------------------------------------------------------------
The context summary (§Allowed Deviations) prefers a rewrite pass over post-hoc
string surgery, and a rewrite pass is genuinely cleaner *here* because SymPy
models a reciprocal as ``Pow(base, negative-integer)`` and ``a / b`` as
``Mul(a, Pow(b, -1))`` — the denominator is a plain sub-tree that ``_print_Mul``
formats itself. Rather than re-implement SymPy's ``_print_Mul`` (brittle, and
close to the R4 anti-pattern), we *wrap the denominator sub-tree* in a marker
node so ``_print_Mul`` prints the guard for free: ``a / _signed_floor(b)``
renders as ``a/ti.select(b >= 0, ti.max(b, 1e-12), ti.min(b, -1e-12))``.

Two marker nodes carry the guard, both trivial :class:`sympy.Function`
subclasses that :class:`~mechdsl.lawgen.sympy_to_taichi.TaichiGuardedPrinter`
knows how to render:

* :class:`GuardFloor` — ``ti.max(arg, 1e-12)``. Positive-domain floor for
  ``log``, ``sqrt`` and ``pow`` with a non-integer exponent (the base of a
  fractional power must be positive, so flooring to ``+1e-12`` is correct).
* :class:`GuardSignedFloor` — ``ti.select(arg >= 0, ti.max(arg, 1e-12),
  ti.min(arg, -1e-12))``. **Sign-preserving** near-zero guard for a division
  denominator that is not a compile-time constant. A plain ``ti.max(ti.abs(b),
  1e-12)`` would return ``|b|`` and flip the sign of ``a/b`` for ``b < 0``
  (Gate-B Finding 1); the signed floor keeps ``b``'s sign and only floors its
  *magnitude* to ``1e-12``. It is a no-op for ``|b| >= 1e-12`` (returns ``b``).

The floor literal is fixed as the *string* ``"1e-12"`` (see
:data:`GUARD_FLOOR_LITERAL`) rather than a ``sympy.Float`` so the emitted text
is exactly ``1e-12`` — a ``Float`` would print ``1.0e-12`` and drift from the
golden. The printer renders the literal, so it never passes through SymPy
numeric formatting.

The exact guard idioms (reproduced, not invented — the golden is the authority)
-------------------------------------------------------------------------------
From ``NumerixWeave/libs/ticonstit/.../generated/plasticity/swift_voce.py``
(Cycle 0, hand-authored), ``get_R``/``get_dR``:

* Swift ``(peeq + p0)**n`` and ``p0**n`` → **floor the base** with
  ``ti.max(base, 1e-12)`` then ``ti.pow`` — *only* when the exponent is
  non-integer. An integer power needs no floor (and P2-4 inlines small-int
  powers to multiplication anyway).
* ``exp(-b*peeq)`` is **UNGUARDED**, matching the Voce idiom (physical domain
  ``peeq >= 0`` ⇒ argument ``<= 0`` ⇒ ``exp in (0, 1]``, no overflow). Guarding
  ``exp`` would *diverge* from the golden — this pass MUST NOT wrap it (the
  ``exp`` node is simply not a rule here).
* ``log`` / ``sqrt`` → positive-domain floor ``ti.max(arg, 1e-12)``.
  ``swift_voce`` has no ``log``/``sqrt``, so these are the generic mechanism
  (covered by the generic tests, not the golden).
* Division by a possibly-zero *variable* denominator (a genuine reciprocal — a
  negative-**integer** exponent) → sign-preserving guard. A denominator that is
  a compile-time constant (a pure number) is left bare — matching
  ``swift_voce``'s ``/edot0`` (division by a nonzero parameter is not
  runtime-guarded there).

Negative NON-integer exponents are fractional powers, not division
------------------------------------------------------------------
``x**(-3/10)`` (a negative *fractional* constant) and ``x**(-alpha)`` (a
negative *symbolic* exponent) are still fractional powers whose base must be
positive — they are base-floored via ``ti.pow(ti.max(base, 1e-12), exp)``, NOT
routed to the division guard (Gate-B Finding 2). Only a negative-**integer**
exponent is a reciprocal (``x**-1 = 1/x``, ``x**-2 = 1/x**2``).
"""

from __future__ import annotations

import sympy as sp
from sympy.core.function import Function

__all__ = [
    "GUARD_FLOOR",
    "GUARD_FLOOR_LITERAL",
    "GUARD_FLOOR_NEG_LITERAL",
    "GuardFloor",
    "GuardSignedFloor",
    "inject_guards",
]

# The domain-floor / near-zero epsilon, emitted verbatim as this string so the
# generated text is exactly ``1e-12`` (a ``sympy.Float`` would print
# ``1.0e-12`` and drift from Cycle 0's ``swift_voce.py``). ``GUARD_FLOOR`` keeps
# the numeric value available for callers/tests that reason about the value;
# ``GUARD_FLOOR_NEG_LITERAL`` is the negative-side floor for the sign-preserving
# denominator guard.
GUARD_FLOOR_LITERAL: str = "1e-12"
GUARD_FLOOR_NEG_LITERAL: str = "-1e-12"
GUARD_FLOOR: float = 1e-12


class GuardFloor(Function):  # type: ignore[misc]  # SymPy Function is untyped
    """Marker node rendered as ``ti.max(arg, 1e-12)`` — the positive-domain floor.

    A single-argument stand-in that the guarded printer renders; it never
    reaches Taichi as a real function. Used for ``log``/``sqrt`` arguments and
    for the base of a ``pow`` with a non-integer exponent — all cases where the
    argument is required to be positive, so flooring to ``+1e-12`` is correct.
    """

    nargs = 1


class GuardSignedFloor(Function):  # type: ignore[misc]  # SymPy Function is untyped
    """Sign-preserving near-zero guard for a division denominator.

    Rendered as ``ti.select(arg >= 0, ti.max(arg, 1e-12), ti.min(arg, -1e-12))``:
    it keeps ``arg``'s sign and floors only its *magnitude* to ``1e-12``. This is
    a no-op for ``|arg| >= 1e-12`` (returns ``arg``); for ``|arg| < 1e-12`` it
    returns ``+1e-12`` (``arg >= 0``) or ``-1e-12`` (``arg < 0``).

    Why not ``ti.max(ti.abs(arg), 1e-12)`` (Gate-B Finding 1): an ``abs`` floor
    returns ``|arg|``, so ``a / arg`` would evaluate to ``a / |arg|`` and FLIP
    SIGN for a runtime-negative ``arg``. Wrong result whenever the denominator
    can be negative — silently emitting wrong code (R2). The signed floor is the
    correct near-zero clamp for a denominator of unknown sign.
    """

    nargs = 1


# Private aliases: the marker classes are an implementation detail of this pass,
# but the printer needs to dispatch on their names.
_GuardFloor = GuardFloor
_GuardSignedFloor = GuardSignedFloor


def inject_guards(expr: sp.Expr) -> sp.Expr:
    """Return ``expr`` with numerical guards injected as marker nodes.

    A pure, bottom-up SymPy rewrite (no mutation, no string surgery, no
    print-to-Python-source): each node is rebuilt from already-guarded children,
    then the guard rules apply to the current node. Running it *before* CSE means the
    common-subexpression pass sees a normal SymPy tree (the markers are ordinary
    ``Function`` nodes) and factors it deterministically.

    Rules (see the module docstring for the golden anchoring):

    * ``Pow(base, 1/2)`` (``sqrt``)              → positive-floor the base.
    * ``Pow(base, non-negative integer)``        → **no** guard (P2-4 inlines).
    * ``Pow(base, non-integer: fractional or symbolic, any sign)`` → positive
      base-floor via ``ti.pow`` (a fractional power's base must be positive).
    * ``Pow(base, negative integer)`` (``1/x``, ``1/x**2``) → sign-preserving
      denominator guard, unless ``base`` is a pure number (a nonzero constant).
    * ``log(x)``                                 → positive-floor the argument.
    * ``exp(x)``                                 → **untouched** (the Voce idiom;
      the #1 failure mode is over-guarding this).

    Already-injected markers are returned as-is so the pass is idempotent.
    """
    # Atoms (symbols, numbers) and markers already in place: nothing to rewrite.
    if expr.is_Atom or isinstance(expr, (_GuardFloor, _GuardSignedFloor)):
        return expr

    guarded_args = [inject_guards(arg) for arg in expr.args]

    if expr.is_Pow:
        return _guard_pow(guarded_args[0], guarded_args[1])

    # ``log`` is the one whitelisted function with a domain guard; ``exp`` (and
    # every other function) is rebuilt from guarded children but NOT wrapped.
    if expr.func is sp.log:
        return sp.log(_floor(guarded_args[0]))

    # Any other node (Add, Mul, exp, trig, Abs, Max/Min, sign, ...): rebuild
    # from guarded children, unchanged. ``exp`` flows through here unguarded.
    return expr.func(*guarded_args)


def _floor(arg: sp.Expr) -> sp.Expr:
    """Wrap ``arg`` in a :class:`_GuardFloor`, idempotently.

    An ``arg`` that is *already* a guard marker is returned unchanged so a second
    pass never nests ``_GuardFloor(_GuardFloor(x))`` (double-flooring is
    harmless numerically but would emit a redundant ``ti.max`` and drift from the
    golden). Keeps :func:`inject_guards` a proper idempotent rewrite.
    """
    if isinstance(arg, (_GuardFloor, _GuardSignedFloor)):
        return arg
    return _GuardFloor(arg)


def _signed_floor(arg: sp.Expr) -> sp.Expr:
    """Wrap a denominator ``arg`` in a :class:`_GuardSignedFloor`, idempotently."""
    if isinstance(arg, (_GuardFloor, _GuardSignedFloor)):
        return arg
    return _GuardSignedFloor(arg)


def _guard_pow(base: sp.Expr, exp: sp.Expr) -> sp.Expr:
    """Apply the ``Pow`` guard rules to an already-child-guarded ``base``/``exp``.

    Kept ``evaluate=False`` throughout so the injected marker survives (an
    evaluating rebuild could fold ``_GuardFloor(x)**2`` and lose the wrapper).

    Routing (order matters — integer-ness before sign):

    1. ``exp == 1/2`` (``sqrt``)          → positive base-floor.
    2. ``exp`` a non-integer (fractional or symbolic, ANY sign) → positive
       base-floor via ``ti.pow``. A fractional power's base must be positive, so
       even ``x**(-3/10)`` floors the base — it is NOT a reciprocal/division
       (Gate-B Finding 2).
    3. ``exp`` a negative integer (``x**-1``, ``x**-2``) → genuine reciprocal:
       sign-preserving denominator guard (unless ``base`` is a nonzero constant).
    4. ``exp`` a non-negative integer → no guard (exact; P2-4 inlines small ints).
    """
    # 1. sqrt: SymPy's ``Pow(x, 1/2)``. Floor the radicand; the printer routes
    # the half-exponent to ``ti.sqrt`` → ``ti.sqrt(ti.max(x, 1e-12))``.
    if exp is sp.S.Half:
        return sp.Pow(_floor(base), exp, evaluate=False)

    # 2. Non-integer exponent (fractional constant or symbolic), regardless of
    # sign: a fractional power whose base must be positive → positive base-floor.
    # ``exp.is_Integer`` is False for a symbolic exponent too, so this must come
    # BEFORE the negative-integer reciprocal check. The printer emits
    # ``ti.pow(ti.max(base, 1e-12), exp)``.
    if not exp.is_Integer:
        return sp.Pow(_floor(base), exp, evaluate=False)

    # 3. Negative *integer* exponent: a genuine reciprocal (``x**-1`` = ``1/x``,
    # ``x**-2`` = ``1/x**2``). Sign-preserving denominator guard, unless the base
    # is a pure number (a nonzero compile-time constant needs no runtime guard —
    # matches ``swift_voce``'s bare ``/edot0``).
    if exp.is_negative:
        if base.is_number:
            return sp.Pow(base, exp, evaluate=False)
        return sp.Pow(_signed_floor(base), exp, evaluate=False)

    # 4. Non-negative integer power: no floor. Exact, and the printer inlines
    # small ones to repeated multiplication.
    return sp.Pow(base, exp, evaluate=False)
