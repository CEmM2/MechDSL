"""Unit tests for the deterministic SymPy → Taichi lowerer (Task P2-1).

MFront-mimic Cycle M0, Phase 2 (``dev/plans/mfront_cycleM0.md`` lines 76-78).

Covers the three ``test_plan.cases`` plus the fail-loud route:

1. A simple quadratic lowers to the expected (golden) Taichi string.
2. A repeated sub-expression is factored into a CSE temporary emitted before
   the return line.
3. Lowering the same expression twice is byte-identical (determinism).
4. An unsupported node (``Piecewise`` / an undefined function) raises
   ``NotImplementedError`` rather than silently emitting wrong code (R2).

Plus the R4 guard: the lowerer module must contain no ``pycode`` / ``re.sub``.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import sympy as sp

from mechdsl.lawgen import sympy_to_taichi as _lowerer_module
from mechdsl.lawgen.cli import _ALLOWED_FUNCTIONS
from mechdsl.lawgen.sympy_to_taichi import (
    MATH_TO_TAICHI,
    LoweredExpr,
    TaichiExprPrinter,
    lower_expression,
)

# Resolve the module source from the imported module (not a CWD-relative path)
# so the R4 guard test is robust to where pytest is invoked from.
_MODULE_SOURCE = Path(_lowerer_module.__file__)


# ---------------------------------------------------------------------------
# Case 1 — simple quadratic → golden Taichi string.
# ---------------------------------------------------------------------------


def test_lower_simple_quadratic_golden() -> None:
    """``x**2 + 2*x + 1`` lowers to the expected Taichi string (AC3).

    No shared sub-expression, so CSE introduces no temporary; the single return
    line is the deterministic golden string the downstream tasks may rely on.
    Since P2-4, the small-integer ``x**2`` is inlined to ``x*x`` (never
    ``ti.pow``).
    """
    x = sp.Symbol("x")
    result = lower_expression(x**2 + 2 * x + 1)

    assert isinstance(result, LoweredExpr)
    assert result.temporaries == ()
    assert result.returns == ("x*x + 2*x + 1",)


def test_lower_function_maps_to_taichi() -> None:
    """A whitelisted function lowers to its ``ti.*`` call, not a bare name."""
    x, b, p = sp.symbols("x b p")
    printer = TaichiExprPrinter()

    assert printer.doprint(sp.exp(-b * p)) == "ti.exp(-b*p)"
    assert printer.doprint(sp.log(x)) == "ti.log(x)"
    assert printer.doprint(sp.sqrt(x)) == "ti.sqrt(x)"
    assert printer.doprint(sp.Abs(x)) == "ti.abs(x)"
    assert printer.doprint(sp.Max(x, 1)) == "ti.max(1, x)"
    assert printer.doprint(sp.Min(x, 1)) == "ti.min(1, x)"
    assert printer.doprint(sp.sign(x)) == "ti.sign(x)"
    assert printer.doprint(sp.tanh(x)) == "ti.tanh(x)"


# ---------------------------------------------------------------------------
# Case 2 — repeated sub-expression introduces a CSE temporary.
# ---------------------------------------------------------------------------


def test_repeated_subexpression_introduces_cse_temp() -> None:
    """A shared sub-term is factored into a temporary emitted before the return.

    ``exp(-b*p)`` appears twice; canonical CSE lifts it to ``x0`` and the
    reduced return references ``x0``. The temporary line must precede the
    return line (AC4) and be a real assignment.
    """
    b, p = sp.symbols("b p")
    shared = sp.exp(-b * p)
    result = lower_expression(shared * (1 + shared))

    assert result.temporaries == ("x0 = ti.exp(-b*p)",)
    assert result.returns == ("x0*(x0 + 1)",)
    # The temporary is an assignment to the symbol the return references.
    assert result.temporaries[0].startswith("x0 = ")
    assert "x0" in result.returns[0]


def test_repeated_subexpression_across_multiple_returns() -> None:
    """CSE factors a sub-term shared across a *sequence* of expressions.

    The two returns keep input order and both reference the lifted temporary.
    """
    b, p, sigma0, Q = sp.symbols("b p sigma0 Q")
    shared = sp.exp(-b * p)
    result = lower_expression([sigma0 + shared, Q * shared])

    assert result.temporaries == ("x0 = ti.exp(-b*p)",)
    assert result.returns == ("sigma0 + x0", "Q*x0")


# ---------------------------------------------------------------------------
# Case 3 — determinism (order='canonical').
# ---------------------------------------------------------------------------


def test_cse_canonical_order_is_deterministic() -> None:
    """Lowering the same expression twice is byte-identical (AC2)."""
    b, p, sigma0, Q, K, n = sp.symbols("b p sigma0 Q K n")
    shared = sp.exp(-b * p)
    exprs = [sigma0 + Q * (1 - shared) + K * p**n, Q * shared, shared + p]

    first = lower_expression(exprs)
    second = lower_expression(exprs)

    assert first == second
    assert first.temporaries == second.temporaries
    assert first.returns == second.returns


def test_lower_expression_result_is_immutable() -> None:
    """``LoweredExpr`` is frozen — the tuples cannot be reassigned."""
    result = lower_expression(sp.Symbol("x") ** 2)
    with pytest.raises((AttributeError, TypeError)):
        result.returns = ("mutated",)  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Case 4 — fail loud (R2), no silent fallback.
# ---------------------------------------------------------------------------


def test_piecewise_lowers_to_ti_select() -> None:
    """A ``Piecewise`` now lowers to ``ti.select`` (P2-4 replaced the P2-1 reject).

    P2-1 fail-loud-rejected ``Piecewise`` and pointed at the P2-4 phase; P2-4
    delivered that lowering, so an exhaustive two-branch switch emits a single
    ``ti.select`` rather than raising. (The full nesting / budget behaviour lives
    in ``test_lowering_table.py``.)
    """
    x = sp.Symbol("x")
    piece = sp.Piecewise((x, x > 0), (0, True))
    assert lower_expression(piece).returns == ("ti.select(x > 0, x, 0)",)


def test_unknown_applied_function_raises() -> None:
    """A bogus undefined function fails loud rather than emitting garbage."""
    x = sp.Symbol("x")
    foo = sp.Function("foo")
    with pytest.raises(NotImplementedError, match="foo"):
        lower_expression(foo(x))


def test_unregistered_defined_function_raises() -> None:
    """A defined-but-unmapped SymPy function (``erf``) fails loud in the printer."""
    x = sp.Symbol("x")
    with pytest.raises(NotImplementedError, match="erf"):
        TaichiExprPrinter().doprint(sp.erf(x))


def test_non_expr_input_raises_type_error() -> None:
    """A non-``Expr`` element is rejected — no silent coercion."""
    with pytest.raises(TypeError):
        lower_expression(["not an expr"])  # type: ignore[list-item]


# ---------------------------------------------------------------------------
# R4 guard + allow-list alignment.
# ---------------------------------------------------------------------------


def test_module_uses_no_pycode_or_regex_substitution() -> None:
    """AC1: the lowerer never uses ``pycode`` or ``re.sub`` (the R4 anti-pattern).

    Asserted against the module source directly so the guard cannot regress.
    """
    source = _MODULE_SOURCE.read_text(encoding="utf-8")
    assert "pycode" not in source
    assert not re.search(r"re\.sub", source)


def test_taichi_map_aligns_with_cli_allowed_functions() -> None:
    """The printer's allow-list matches P1-2's parser allow-list.

    Every function the CLI accepts into an R/H/Q expression must be lowerable,
    or a legal law would parse but fail to emit. ``pow`` is a printer-only entry
    (``Pow`` is not a parseable function name), so it is excluded from the
    comparison.
    """
    printer_functions = set(MATH_TO_TAICHI) - {"pow"}
    assert printer_functions == set(_ALLOWED_FUNCTIONS)
    for taichi_name in MATH_TO_TAICHI.values():
        assert taichi_name.startswith("ti.")
