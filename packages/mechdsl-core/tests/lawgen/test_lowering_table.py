"""Unit tests for the Taichi-safe lowering table + source hash (Task P2-4).

Part of the MechDSL lawgen test suite.

Covers six lowering cases:

1. ``sp.exp(x)`` → ``ti.exp(x)`` in the lowered output (no bare ``exp(``).
2. A 3-branch ``Piecewise`` → a right-nested ``ti.select`` chain.
3. A 9-branch ``Piecewise`` → :class:`BudgetError` (default limit 8).
4. ``Pow(x, 2)`` → inlined ``x*x`` (never ``ti.pow``).
5. Lowering the same input twice → identical ``source_hash``.
6. ``source_hash`` is a 64-char lowercase hex string.

Plus the surrounding contract: the small-int-Pow threshold boundary, the
Piecewise budget boundary/override, guards landing inside branch expressions,
and the documented hash input (``"\\n".join(temporaries + returns)``).
"""

from __future__ import annotations

import re

import pytest
import sympy as sp

from mechdsl.lawgen.contracts import TiconstitTarget
from mechdsl.lawgen.diagnostics import LawgenError
from mechdsl.lawgen.sympy_to_taichi import (
    SMALL_INT_POW_LIMIT,
    LoweredExpr,
    compute_source_hash,
    lower_expression,
)

_HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _lower_one(expr: sp.Expr, **kwargs: object) -> str:
    """Lower a single expression and return its one return line."""
    result = lower_expression(expr, **kwargs)  # type: ignore[arg-type]
    assert len(result.returns) == 1
    return result.returns[0]


# ---------------------------------------------------------------------------
# Case 1 — exp → ti.exp.
# ---------------------------------------------------------------------------


def test_exp_lowers_to_ti_exp() -> None:
    """``sp.exp(x)`` lowers to ``ti.exp(x)`` — no bare ``exp(`` leaks (AC1)."""
    x = sp.Symbol("x")
    emitted = _lower_one(sp.exp(x))

    assert emitted == "ti.exp(x)"
    assert "ti.exp(x)" in emitted
    # The only ``exp(`` occurrence is the ``ti.exp`` call — no bare ``exp(`` leaks.
    assert emitted.replace("ti.exp(", "") == "x)"


# ---------------------------------------------------------------------------
# Case 2 — Piecewise (within budget) → nested ti.select.
# ---------------------------------------------------------------------------


def test_piecewise_three_branches_nested_select() -> None:
    """A 3-branch ``Piecewise`` → a right-nested ``ti.select`` chain (AC2).

    ``Piecewise((x, x>0), (y, x<0), (0, True))`` →
    ``ti.select(x > 0, x, ti.select(x < 0, y, 0))``: two nested selects, the
    default (``0``) as the innermost else-value, conditions printed as scalar
    comparisons.
    """
    x, y = sp.symbols("x y")
    piece = sp.Piecewise((x, x > 0), (y, x < 0), (0, True))
    emitted = _lower_one(piece)

    assert emitted == "ti.select(x > 0, x, ti.select(x < 0, y, 0))"
    # Right-nesting structure: exactly one nested select for three branches.
    assert emitted.count("ti.select") == 2
    # The default branch value is the innermost argument.
    assert emitted.endswith(", 0))")


def test_piecewise_two_branches_single_select() -> None:
    """A 2-branch ``Piecewise`` collapses to a single ``ti.select`` (AC2)."""
    x = sp.Symbol("x")
    piece = sp.Piecewise((x, x > 0), (0, True))
    emitted = _lower_one(piece)

    assert emitted == "ti.select(x > 0, x, 0)"
    assert emitted.count("ti.select") == 1


def test_piecewise_branch_guards_are_injected() -> None:
    """Guards (P2-3) land *inside* branch expressions of a lowered Piecewise.

    ``log(x)`` in a branch must be domain-floored exactly as it would be outside
    a ``Piecewise`` — the guard pass recurses into branch values.
    """
    x = sp.Symbol("x")
    piece = sp.Piecewise((sp.log(x), x > 0), (0, True))
    emitted = _lower_one(piece)

    assert emitted == "ti.select(x > 0, ti.log(ti.max(x, 1e-12)), 0)"


def test_non_exhaustive_piecewise_fails_loud() -> None:
    """A ``Piecewise`` with no ``True`` default branch fails loud (R2).

    ``ti.select`` has no undefined result, so a missing default would silently
    emit a wrong fallthrough; the printer rejects it instead.
    """
    x = sp.Symbol("x")
    piece = sp.Piecewise((x, x > 0))
    with pytest.raises(NotImplementedError, match="non-exhaustive Piecewise"):
        lower_expression(piece)


# ---------------------------------------------------------------------------
# Case 3 — Piecewise over budget → BudgetError.
# ---------------------------------------------------------------------------


def _piecewise_with_branches(n: int) -> sp.Piecewise:
    """Build a ``Piecewise`` with exactly ``n`` branches (last one the default)."""
    a = sp.Symbol("a")
    pairs = [(sp.Integer(i), a > i) for i in range(n - 1)]
    pairs.append((sp.Integer(99), sp.true))
    return sp.Piecewise(*pairs)


def test_piecewise_nine_branches_raises_budget_error() -> None:
    """A 9-branch ``Piecewise`` exceeds the default budget (8) → ``LawgenError`` (AC3).

    P3-1 collect-all: the over-budget switch now surfaces as a budget diagnostic
    inside a :class:`LawgenError` (a ``NotImplementedError`` subclass), whose
    ``reason`` names the budget knob, the measured branch count (9), and the
    limit (8), and is raised *before* any ``ti.select`` is emitted.
    """
    piece = _piecewise_with_branches(9)
    assert len(piece.args) == 9

    with pytest.raises(LawgenError) as exc:
        lower_expression(piece)

    (diag,) = exc.value.diagnostics
    assert diag.node == "max_piecewise_branches"
    assert "max_piecewise_branches budget exceeded: 9 > 8" in diag.reason
    assert "9" in diag.reason and "8" in diag.reason
    assert diag.fix.strip()


def test_piecewise_at_budget_limit_lowers() -> None:
    """An 8-branch ``Piecewise`` is exactly at the default budget → lowers (AC2/AC3)."""
    piece = _piecewise_with_branches(8)
    assert len(piece.args) == 8

    emitted = _lower_one(piece)
    # 8 branches → 7 nested selects.
    assert emitted.count("ti.select") == 7


def test_piecewise_budget_override_via_target() -> None:
    """A custom ``TiconstitTarget`` lowers the branch budget (wiring check).

    A 4-branch ``Piecewise`` passes the default (8) but fails a target with
    ``max_piecewise_branches=3`` — proving ``lower_expression`` threads the
    target down to the gate rather than hard-coding the limit.
    """
    piece = _piecewise_with_branches(4)
    strict = TiconstitTarget(max_piecewise_branches=3)

    # Default target: fine.
    assert lower_expression(piece).returns
    # Strict target: over budget → collect-all LawgenError with the budget diagnostic.
    with pytest.raises(LawgenError) as exc:
        lower_expression(piece, target=strict)
    (diag,) = exc.value.diagnostics
    assert diag.node == "max_piecewise_branches"
    assert "max_piecewise_branches budget exceeded: 4 > 3" in diag.reason


# ---------------------------------------------------------------------------
# Case 4 — small-int Pow → multiplication (not ti.pow).
# ---------------------------------------------------------------------------


def test_pow_two_inlines_to_multiplication() -> None:
    """``Pow(x, 2)`` → ``x*x`` in the emitted output, never ``ti.pow`` (AC4)."""
    x = sp.Symbol("x")
    emitted = _lower_one(x**2)

    assert emitted == "x*x"
    assert "ti.pow" not in emitted
    assert "**" not in emitted


def test_pow_three_inlines_to_triple_product() -> None:
    """``Pow(x, 3)`` → ``x*x*x`` (repeated multiplication)."""
    x = sp.Symbol("x")
    assert _lower_one(x**3) == "x*x*x"


def test_pow_one_and_zero_fold_to_identities() -> None:
    """``x**1`` → ``x`` and ``x**0`` → ``1`` (trivial-power folding)."""
    x = sp.Symbol("x")
    assert _lower_one(sp.Pow(x, 1, evaluate=False)) == "x"
    assert _lower_one(sp.Pow(x, 0, evaluate=False)) == "1"


def test_pow_compound_base_is_parenthesised() -> None:
    """``(x + y)**2`` inlines to ``(x + y)*(x + y)`` — the base is grouped."""
    x, y = sp.symbols("x y")
    assert _lower_one((x + y) ** 2, guards=False) == "(x + y)*(x + y)"


def test_pow_at_threshold_inlines_above_threshold_keeps_pow_spelling() -> None:
    """The small-int threshold boundary: ``<= 4`` inlines, ``> 4`` does not.

    ``x**4`` (at the limit) inlines to four factors; ``x**5`` (over the limit)
    is left as an integer power (``x**5`` — an exact power, no ``ti.pow`` guard
    since the exponent is a plain integer).
    """
    x = sp.Symbol("x")
    assert SMALL_INT_POW_LIMIT == 4

    assert _lower_one(x**4, guards=False) == "x*x*x*x"
    assert _lower_one(x**5, guards=False) == "x**5"


def test_standalone_negative_pow_is_not_inlined() -> None:
    """A standalone ``x**-2`` (no numerator) is NOT inlined — stays ``x**(-2)``.

    Negative integer exponents are reciprocals; the printer must not intercept
    them (Gate-B critical fix). With no numerator there is no division to
    mis-group, so SymPy's canonical ``x**(-2)`` is emitted verbatim. The old
    behaviour (inlining to a self-contained ``1/(x*x)``) is exactly what caused
    the Mul-context collapse and is deliberately gone.
    """
    x = sp.Symbol("x")
    assert _lower_one(x**-2, guards=False) == "x**(-2)"

    # Guarded standalone reciprocal: the base is the sign-preserving floor, and
    # the power stays ``**(-2)`` (still no collapse — no numerator).
    guarded = _lower_one(x**-2)
    signed_floor = "ti.select(x >= 0, ti.max(x, 1e-12), ti.min(x, -1e-12))"
    assert guarded == f"{signed_floor}**(-2)"


# ---------------------------------------------------------------------------
# Case 4 (regression) — division-by-power must NOT collapse to ``a/x*x``.
# ---------------------------------------------------------------------------
#
# ``a/x**2`` = ``Mul(a, Pow(x, -2))``. SymPy's ``_print_Mul`` splits the
# reciprocal into the denominator and prints the positive counterpart ``Pow(x, 2)``
# through ``_print_Pow`` — which inlines it to ``x*x``. Without the ``parenthesize``
# override, ``_print_Mul`` would leave that unwrapped (a ``Pow`` node reports
# precedence 60 > ``Mul``'s 50), emitting ``a/x*x``, which under left-to-right
# ``/`` and ``*`` evaluates to ``a`` — silently-wrong math on realistic forms like
# ``mu/J**2``. These tests pin the correct, parenthesised division on BOTH the raw
# and guarded paths.


def test_division_by_square_is_parenthesised_not_collapsed() -> None:
    """``a/x**2`` → ``a/(x*x)`` (raw and guarded) — never the ``a/x*x`` collapse."""
    a, x = sp.symbols("a x")

    raw = _lower_one(a / x**2, guards=False)
    assert raw == "a/(x*x)"
    # The collapse: unparenthesised ``/x*x`` must NOT appear ...
    assert "/x*x" not in raw
    # ... and it must not have degenerated to the bare numerator ``a``.
    assert raw != "a"
    assert raw != "a/x*x"

    guarded = _lower_one(a / x**2)
    signed_floor = "ti.select(x >= 0, ti.max(x, 1e-12), ti.min(x, -1e-12))"
    assert guarded == f"a/({signed_floor}*{signed_floor})"
    assert "/x*x" not in guarded


def test_division_by_square_realistic_material_form() -> None:
    """``k/J**2`` (a realistic ``mu/J**2``-style form) → ``k/(J*J)``, not ``k/J*J``."""
    k, J = sp.symbols("k J")

    raw = _lower_one(k / J**2, guards=False)
    assert raw == "k/(J*J)"
    assert "/J*J" not in raw
    assert raw != "k"


def test_division_by_cube_is_parenthesised() -> None:
    """``a/x**3`` → ``a/(x*x*x)`` — the three-factor denominator is grouped."""
    a, x = sp.symbols("a x")

    raw = _lower_one(a / x**3, guards=False)
    assert raw == "a/(x*x*x)"
    assert "/x*x" not in raw


def test_division_by_power_above_threshold_keeps_pow() -> None:
    """``a/x**5`` (over the inline threshold) stays ``a/x**5`` — correct and safe.

    An above-threshold power is not inlined, so it prints as ``x**5``; ``**``
    binds tighter than ``/`` so no extra parentheses are needed (``a/x**5`` is
    unambiguous).
    """
    a, x = sp.symbols("a x")
    assert _lower_one(a / x**5, guards=False) == "a/x**5"


def test_multi_factor_denominator_stays_correct() -> None:
    """``a/(x**2 * J)`` keeps a correct, mathematically-sound grouping.

    A two-factor denominator is wrapped by SymPy; the inlined square inside must
    not break that grouping. Whatever the exact spelling, it must not collapse a
    factor out of the denominator (no bare ``/x*x`` fragment).
    """
    a, x, J = sp.symbols("a x J")
    raw = _lower_one(a / (x**2 * J), guards=False)

    assert "/x*x" not in raw
    # A correct grouping: the whole denominator is parenthesised.
    assert raw in {"a/(J*(x*x))", "a/(J*x*x)"}


# ---------------------------------------------------------------------------
# Cases 5 & 6 — deterministic source_hash.
# ---------------------------------------------------------------------------


def test_same_input_yields_same_source_hash() -> None:
    """Lowering the same input twice → identical ``source_hash`` (AC5)."""
    sigma0, Q, b, p, K, n, p0 = sp.symbols("sigma0 Q b p K n p0")
    expr = sigma0 + Q * (1 - sp.exp(-b * p)) + K * ((p + p0) ** n - p0**n)

    first = lower_expression(expr)
    second = lower_expression(expr)

    assert first.source_hash == second.source_hash
    # And the whole lowered result is equal too (lines are byte-identical).
    assert first == second


def test_source_hash_is_64_hex_chars() -> None:
    """``source_hash`` matches ``^[0-9a-f]{64}$`` (AC6)."""
    x = sp.Symbol("x")
    result = lower_expression(sp.exp(x) + x**2)

    assert _HEX64.match(result.source_hash)
    assert len(result.source_hash) == 64


def test_source_hash_input_is_emitted_lines_in_order() -> None:
    """The hash is SHA-256 of ``"\\n".join(temporaries + returns)`` (documented input).

    Recomputing the digest from the emitted lines must reproduce the stored
    ``source_hash`` — pinning the exact hash input (emission order: temporaries
    first, then returns) that P4-1/P4-2 read.
    """
    b, p, sigma0, Q = sp.symbols("b p sigma0 Q")
    shared = sp.exp(-b * p)
    result = lower_expression([sigma0 + shared, Q * shared])

    assert result.temporaries == ("x0 = ti.exp(-b*p)",)
    assert result.returns == ("sigma0 + x0", "Q*x0")

    expected = compute_source_hash(result.temporaries, result.returns)
    assert result.source_hash == expected


def test_direct_lowered_expr_construction_carries_hash() -> None:
    """A directly-constructed ``LoweredExpr`` (P2-2's pattern) still gets a hash.

    P2-2's budget tests build ``LoweredExpr(temporaries=…, returns=…)`` without
    passing a hash; ``__post_init__`` computes it, so every instance carries a
    consistent 64-hex digest and the ``source_hash`` field is not part of
    ``__init__``.
    """
    lowered = LoweredExpr(temporaries=("x0 = ti.exp(-b*p)",), returns=("sigma0 + x0",))

    assert _HEX64.match(lowered.source_hash)
    assert lowered.source_hash == compute_source_hash(lowered.temporaries, lowered.returns)


def test_source_hash_changes_with_different_lines() -> None:
    """Different emitted lines → a different ``source_hash`` (the digest is content-bound)."""
    x, y = sp.symbols("x y")

    assert lower_expression(sp.exp(x)).source_hash != lower_expression(sp.exp(y)).source_hash


def test_source_hash_excluded_from_equality() -> None:
    """Equality is driven by the lines, and the derived hash follows them.

    Two lowered results with identical lines are equal AND share a hash; the
    ``source_hash`` field carries no independent identity (``compare=False``).
    """
    a = LoweredExpr(temporaries=(), returns=("x*x",))
    b = LoweredExpr(temporaries=(), returns=("x*x",))

    assert a == b
    assert a.source_hash == b.source_hash
