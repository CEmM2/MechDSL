"""Unit tests for numerical-guard injection (Task P2-3).

Part of the MechDSL lawgen test suite. Correctness-critical: the guards
emitted by :func:`mechdsl.lawgen.sympy_to_taichi.lower_expression` must match
the hand-authored guards in the reference ``swift_voce.py`` so the
numerical-equivalence check (``rtol=1e-10``) holds.

Covers the five ``test_plan.cases``:

1. ``pow(x, alpha)`` (symbolic alpha) → base floored ``ti.max(x, 1e-12)``.
2. ``log(x)``  → ``ti.log(ti.max(x, 1e-12))``.
3. ``sqrt(x)`` → ``ti.sqrt(ti.max(x, 1e-12))``.
4. ``1/x``     → denominator guarded (sign-preserving; Gate-B Finding 1).
5. GOLDEN: the SwiftVoce ``R`` expression reproduces ``swift_voce.py``'s
   ``get_R`` guard structure — floored Swift ``pow`` bases via ``ti.pow`` AND an
   **unguarded** ``exp``.

Plus the #1-risk regression test: ``exp`` is NOT guarded.

The golden patterns are encoded as **string literals** here, transcribed from
``NumerixWeave/libs/ticonstit/src/ticonstit/generated/plasticity/swift_voce.py``
(Cycle 0, hand-authored) ``get_R``. The NumerixWeave file is deliberately NOT
read at test time — it lives in a separate repo and MechDSL CI must be
self-contained (plan risk R3). The reference idioms, from that file's
``get_R``::

    base    = ti.max(peeq + self.p0, self._POW_FLOOR)   # _POW_FLOOR = 1e-12
    p0_base = ti.max(self.p0, self._POW_FLOOR)
    return ... self.Qsat * (1.0 - ti.exp(-self.b * peeq))          # exp UNGUARDED
             + self.K * (ti.pow(base, self.n) - ti.pow(p0_base, self.n))
"""

from __future__ import annotations

import sympy as sp

from mechdsl.lawgen.guard_transforms import GUARD_FLOOR, GUARD_FLOOR_LITERAL
from mechdsl.lawgen.sympy_to_taichi import (
    TaichiExprPrinter,
    TaichiGuardedPrinter,
    lower_expression,
)


def _lower_one(expr: sp.Expr) -> str:
    """Lower a single expression (guards on) and return its one return line."""
    result = lower_expression(expr)
    assert len(result.returns) == 1
    return result.returns[0]


# ---------------------------------------------------------------------------
# Case 1 — pow with a symbolic exponent floors the base (the "safe pattern").
# ---------------------------------------------------------------------------


def test_pow_symbolic_exponent_floors_base() -> None:
    """``x**alpha`` (symbolic exp) → ``ti.pow(ti.max(x, 1e-12), alpha)`` (AC1).

    The base is floored with ``ti.max(·, 1e-12)`` — the equivalent safe pattern
    ``swift_voce.py`` ``get_R``/``get_dR`` use (a ``ti.max`` base-floor, not a
    ``ti.select`` gate), and the floored base is emitted through ``ti.pow``.
    """
    x, alpha = sp.symbols("x alpha")
    emitted = _lower_one(x**alpha)

    assert emitted == "ti.pow(ti.max(x, 1e-12), alpha)"
    # The safe pattern: the base is floored inside the ti.pow.
    assert "ti.max(x, 1e-12)" in emitted
    assert emitted.startswith("ti.pow(")


def test_pow_fractional_constant_exponent_floors_base() -> None:
    """A non-integer *constant* exponent (``x**(1/3)``) also floors the base.

    ``1/3`` is not an integer, so the base-floor rule applies exactly as for a
    symbolic exponent (only integer powers are exempt).
    """
    x = sp.Symbol("x")
    emitted = _lower_one(x ** sp.Rational(1, 3))

    assert "ti.pow(ti.max(x, 1e-12)," in emitted


def test_pow_integer_exponent_is_not_floored() -> None:
    """A positive integer power is left un-floored (AC1 boundary).

    Integer powers are exact, so the guard pass adds no ``ti.max`` floor.
    Since P2-4, a *small* integer power is additionally inlined to repeated
    multiplication (``x**3`` → ``x*x*x``); the invariant this test guards is the
    absence of any domain floor, not the ``**`` spelling.
    """
    x = sp.Symbol("x")
    emitted = _lower_one(x**3)

    assert emitted == "x*x*x"
    assert "ti.max" not in emitted
    assert "ti.pow" not in emitted


# ---------------------------------------------------------------------------
# Case 2 — log argument is domain-floored.
# ---------------------------------------------------------------------------


def test_log_argument_wrapped_with_ti_max() -> None:
    """``log(x)`` → ``ti.log(ti.max(x, 1e-12))`` (AC2)."""
    x = sp.Symbol("x")
    emitted = _lower_one(sp.log(x))

    assert emitted == "ti.log(ti.max(x, 1e-12))"
    assert "ti.max(x, 1e-12)" in emitted


# ---------------------------------------------------------------------------
# Case 3 — sqrt argument is domain-floored.
# ---------------------------------------------------------------------------


def test_sqrt_argument_wrapped_with_ti_max() -> None:
    """``sqrt(x)`` → ``ti.sqrt(ti.max(x, 1e-12))`` (AC2)."""
    x = sp.Symbol("x")
    emitted = _lower_one(sp.sqrt(x))

    assert emitted == "ti.sqrt(ti.max(x, 1e-12))"
    assert "ti.max(x, 1e-12)" in emitted


# ---------------------------------------------------------------------------
# Case 4 — division denominators are guarded (SIGN-PRESERVING).
# ---------------------------------------------------------------------------
#
# The denominator guard must PRESERVE the denominator's sign. A plain
# ``ti.max(ti.abs(b), 1e-12)`` returns ``|b|`` and flips the sign of ``a/b`` for
# a runtime-negative ``b`` (``a/|b|`` != ``a/b``) — silently wrong. The
# sign-preserving form keeps ``b``'s sign and floors only its magnitude to
# 1e-12; it is a no-op for ``|b| >= 1e-12`` (returns ``b``), and returns
# ``+1e-12`` / ``-1e-12`` for a near-zero positive / negative ``b``.
_SIGNED_FLOOR_X = "ti.select(x >= 0, ti.max(x, 1e-12), ti.min(x, -1e-12))"
_SIGNED_FLOOR_B = "ti.select(b >= 0, ti.max(b, 1e-12), ti.min(b, -1e-12))"


def test_reciprocal_denominator_sign_preserving_guard() -> None:
    """``1/x`` guards the denominator with the sign-preserving floor (AC3).

    ``1/ti.select(x >= 0, ti.max(x, 1e-12), ti.min(x, -1e-12))`` — a no-op for
    ``|x| >= 1e-12``, so ``1/x`` is unchanged in the normal range; only a
    denominator within 1e-12 of zero is clamped, keeping its sign.
    """
    x = sp.Symbol("x")
    emitted = _lower_one(1 / x)

    assert emitted == f"1/{_SIGNED_FLOOR_X}"
    # The naive abs-floor (sign-losing) form must NOT be emitted.
    assert "ti.abs(x)" not in emitted


def test_division_denominator_sign_preserving_guard() -> None:
    """``a/b`` guards the denominator (sign-preserving), not the numerator (AC3)."""
    a, b = sp.symbols("a b")
    emitted = _lower_one(a / b)

    assert emitted == f"a/{_SIGNED_FLOOR_B}"
    # The numerator ``a`` is not wrapped; only the denominator is guarded.
    assert "ti.select(a" not in emitted
    # No sign-losing abs floor anywhere.
    assert "ti.abs(b)" not in emitted


def test_division_by_constant_is_not_guarded() -> None:
    """Division by a compile-time constant is left bare (matches ``/edot0``).

    ``swift_voce.py``'s ``get_dH`` divides by the nonzero *parameter* ``edot0``
    with no runtime guard; only a possibly-zero variable denominator is guarded.
    A pure numeric denominator (here ``2``) needs no floor.
    """
    x = sp.Symbol("x")
    emitted = _lower_one(x / 2)

    assert "ti.max" not in emitted
    assert "ti.select" not in emitted
    assert "ti.abs" not in emitted


def test_negative_integer_exponent_is_reciprocal_guard() -> None:
    """``x**-2`` is a genuine reciprocal → sign-preserving denominator guard.

    ``x**-2 = 1/x**2``: a negative *integer* exponent is division, so its base is
    wrapped in the sign-preserving floor (then raised to the positive power).
    Distinct from a negative *fractional* exponent (see the base-floor test).
    """
    x = sp.Symbol("x")
    emitted = _lower_one(x**-2)

    assert _SIGNED_FLOOR_X in emitted
    # It is a power of the guarded base, not a ti.pow base-floor.
    assert "ti.pow(ti.max(x" not in emitted


def test_negative_fractional_exponent_floors_base_not_denominator() -> None:
    """``x**(-3/10)`` is a fractional power → base-floor via ``ti.pow`` (Finding 2).

    A negative *non-integer* exponent is still a fractional power whose base must
    be positive; it must NOT be treated as a division (no sign-preserving
    denominator guard). It base-floors like any other non-integer power:
    ``ti.pow(ti.max(x, 1e-12), -3/10)``.
    """
    x = sp.Symbol("x")
    emitted = _lower_one(x ** sp.Rational(-3, 10))

    assert emitted == "ti.pow(ti.max(x, 1e-12), -3/10)"
    # Not routed to the reciprocal / sign-preserving denominator guard.
    assert "ti.select" not in emitted


def test_negative_symbolic_exponent_floors_base() -> None:
    """``x**(-alpha)`` (negative symbolic exp) also base-floors via ``ti.pow``.

    A symbolic exponent is non-integer as far as the rewrite can tell, so it
    floors the base regardless of any leading minus sign — never a division.
    """
    x, alpha = sp.symbols("x alpha")
    emitted = _lower_one(x ** (-alpha))

    assert emitted == "ti.pow(ti.max(x, 1e-12), -alpha)"
    assert "ti.select" not in emitted


# ---------------------------------------------------------------------------
# The #1 risk — exp must NOT be guarded (regression test).
# ---------------------------------------------------------------------------


def test_exp_is_not_guarded() -> None:
    """``exp(-b*peeq)`` emits a bare ``ti.exp`` — NO ``ti.max`` around its arg.

    This is the phase's #1 failure mode: over-guarding ``exp`` would diverge
    from ``swift_voce.py`` (whose ``get_R`` uses a bare ``ti.exp(-self.b*peeq)``,
    matching the Voce idiom on the physical domain ``peeq >= 0``) and break the
    P4-2 equivalence gate.
    """
    b, peeq = sp.symbols("b peeq")
    emitted = _lower_one(sp.exp(-b * peeq))

    assert emitted == "ti.exp(-b*peeq)"
    # No domain floor anywhere around the exp argument.
    assert "ti.max" not in emitted


def test_exp_inside_larger_expression_stays_unguarded() -> None:
    """``exp`` stays unguarded even when floored ``pow`` terms sit beside it.

    Guarding one construct must not accidentally wrap a neighbouring ``exp``.
    """
    b, peeq, K, p0, n = sp.symbols("b peeq K p0 n")
    emitted = _lower_one(sp.exp(-b * peeq) + K * (peeq + p0) ** n)

    assert "ti.exp(-b*peeq)" in emitted
    # The exp argument is not floored ...
    assert "ti.max(-b*peeq" not in emitted
    assert "ti.max(peeq" not in emitted  # exp's arg is -b*peeq, not peeq
    # ... but the Swift pow base beside it IS floored.
    assert "ti.pow(ti.max(p0 + peeq, 1e-12), n)" in emitted


# ---------------------------------------------------------------------------
# Case 5 — GOLDEN: SwiftVoce R reproduces swift_voce.py get_R guard structure.
# ---------------------------------------------------------------------------


def test_golden_swift_voce_R_guard_structure() -> None:
    """Lowering SwiftVoce ``R`` reproduces ``swift_voce.py`` ``get_R`` guards (AC4).

    ``R = sigma0 + Qsat*(1 - exp(-b*peeq)) + K*((peeq+p0)**n - p0**n)``.

    The expected guard structure is transcribed as string literals from Cycle 0
    ``swift_voce.py`` ``get_R`` (see the module docstring) — the NumerixWeave
    file is NOT read here (R3). Asserted structure:

    * Swift base ``(peeq+p0)**n``  → ``ti.pow(ti.max(p0 + peeq, 1e-12), n)``.
    * Swift base ``p0**n``         → ``ti.pow(ti.max(p0, 1e-12), n)``.
    * ``exp(-b*peeq)``             → bare ``ti.exp(-b*peeq)`` (UNGUARDED).
    """
    sigma0, Qsat, b, peeq, K, p0, n = sp.symbols("sigma0 Qsat b peeq K p0 n")
    R = sigma0 + Qsat * (1 - sp.exp(-b * peeq)) + K * ((peeq + p0) ** n - p0**n)

    result = lower_expression(R)
    assert len(result.returns) == 1
    emitted = result.returns[0]

    # --- Swift pow bases: floored with ti.max(·, 1e-12) then ti.pow ----------
    # Golden get_R: base = ti.max(peeq + self.p0, 1e-12); ti.pow(base, self.n).
    assert "ti.pow(ti.max(p0 + peeq, 1e-12), n)" in emitted
    # Golden get_R: p0_base = ti.max(self.p0, 1e-12); ti.pow(p0_base, self.n).
    assert "ti.pow(ti.max(p0, 1e-12), n)" in emitted

    # --- exp is UNGUARDED (the #1 risk) --------------------------------------
    # Golden get_R: self.Qsat * (1.0 - ti.exp(-self.b * peeq)) — bare ti.exp.
    assert "ti.exp(-b*peeq)" in emitted
    # There must be NO ti.max wrapping the exp argument anywhere.
    assert "ti.max(-b*peeq, 1e-12)" not in emitted

    # --- No un-guarded pow/sqrt/log leaked into the output -------------------
    # Every ``**`` with a symbolic exponent must have gone through ti.pow; the
    # only ``**`` that could remain would be an integer power (none here).
    assert "peeq)**n" not in emitted
    assert "p0**n" not in emitted


def test_golden_swift_voce_dR_guard_structure() -> None:
    """SwiftVoce ``dR`` reproduces ``get_dR``: floored ``(peeq+p0)**(n-1)``, bare exp.

    ``dR = Qsat*b*exp(-b*peeq) + K*n*(peeq+p0)**(n-1)``.
    Golden get_dR: ``base = ti.max(peeq + self.p0, 1e-12)``;
    ``K * self.n * ti.pow(base, self.n - 1.0)`` with the exp term unguarded.
    """
    Qsat, b, peeq, K, p0, n = sp.symbols("Qsat b peeq K p0 n")
    dR = Qsat * b * sp.exp(-b * peeq) + K * n * (peeq + p0) ** (n - 1)

    emitted = lower_expression(dR).returns[0]

    assert "ti.pow(ti.max(p0 + peeq, 1e-12), n - 1)" in emitted
    assert "ti.exp(-b*peeq)" in emitted
    assert "peeq)**(n - 1)" not in emitted


# ---------------------------------------------------------------------------
# Flag / determinism / raw-path contract.
# ---------------------------------------------------------------------------


def test_guards_off_leaves_expression_raw() -> None:
    """``guards=False`` bypasses injection — the raw P2-1 output is unchanged.

    The raw path emits ``**`` for a symbolic power and never introduces a
    ``ti.max`` floor; this is the escape hatch P2-1 tests and downstream
    guard-elsewhere callers rely on.
    """
    x, alpha = sp.symbols("x alpha")
    raw = lower_expression(x**alpha, guards=False).returns[0]

    assert raw == "x**alpha"
    assert "ti.max" not in raw


def test_guards_default_is_on() -> None:
    """The default is guards-on: a symbolic power is floored without the flag."""
    x, alpha = sp.symbols("x alpha")

    assert lower_expression(x**alpha).returns[0] == "ti.pow(ti.max(x, 1e-12), alpha)"


def test_guarded_lowering_is_deterministic() -> None:
    """Guard injection preserves byte-for-byte determinism across repeat calls."""
    sigma0, Qsat, b, peeq, K, p0, n = sp.symbols("sigma0 Qsat b peeq K p0 n")
    R = sigma0 + Qsat * (1 - sp.exp(-b * peeq)) + K * ((peeq + p0) ** n - p0**n)

    first = lower_expression(R)
    second = lower_expression(R)

    assert first == second


def test_guard_floor_literal_and_value_agree() -> None:
    """The emitted literal string and the numeric floor constant match ``1e-12``.

    ``GUARD_FLOOR_LITERAL`` is emitted verbatim (so the text is exactly
    ``1e-12``, not the ``1.0e-12`` a ``sympy.Float`` would print); ``GUARD_FLOOR``
    is the numeric value for callers/tests reasoning about magnitude.
    """
    assert GUARD_FLOOR_LITERAL == "1e-12"
    assert GUARD_FLOOR == 1e-12
    assert float(GUARD_FLOOR_LITERAL) == GUARD_FLOOR


def test_guarded_printer_renders_markers_directly() -> None:
    """The guarded printer renders the marker nodes; the raw printer rejects them.

    Confirms the two printers are a matched pair: guarded expressions must be
    printed with :class:`TaichiGuardedPrinter`, and the raw
    :class:`TaichiExprPrinter` fails loud (R2) rather than silently mis-emitting
    an injected marker.
    """
    from mechdsl.lawgen.guard_transforms import GuardFloor, GuardSignedFloor

    x = sp.Symbol("x")
    guarded = TaichiGuardedPrinter()

    assert guarded.doprint(GuardFloor(x)) == "ti.max(x, 1e-12)"
    assert (
        guarded.doprint(GuardSignedFloor(x))
        == "ti.select(x >= 0, ti.max(x, 1e-12), ti.min(x, -1e-12))"
    )

    # The raw printer has no marker rendering and must fail loud on either.
    import pytest

    with pytest.raises(NotImplementedError, match="GuardFloor"):
        TaichiExprPrinter().doprint(GuardFloor(x))
    with pytest.raises(NotImplementedError, match="GuardSignedFloor"):
        TaichiExprPrinter().doprint(GuardSignedFloor(x))
