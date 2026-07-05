"""Unit tests for the pre-emission JIT budget gate (Task P2-2).

MFront-mimic Cycle M0, Phase 2 (``dev/plans/mfront_cycleM0.md`` lines 79-82).

Covers all seven ``test_plan.cases``:

1-6. Each of the six budget knobs is tripped *in isolation* by a targeted
     fixture, and the raised :class:`BudgetError` names the knob, the measured
     value, and the limit.
7.   A compliant SwiftVoce-like expression set passes :meth:`check_all` cleanly.

Plus: the three module-level counters are exercised directly (they are the
independently-testable primitives P2-3/P2-4/P3 reuse), and the defaults are
proven to be wired from :class:`TiconstitTarget` (one test trips a *default*
budget, the rest use tiny overridden knobs to keep fixtures small).
"""

from __future__ import annotations

import pytest
import sympy as sp

from mechdsl.codegen.einsum_optimizer import BudgetExceededError
from mechdsl.lawgen.budgets import (
    BudgetChecker,
    BudgetError,
    count_expr_ops,
    count_piecewise_branches,
    count_pow_symbolic_exponent,
)
from mechdsl.lawgen.contracts import TiconstitTarget
from mechdsl.lawgen.diagnostics import LawgenDiagnostic, LawgenError
from mechdsl.lawgen.sympy_to_taichi import LoweredExpr


def _sole_diagnostic(exc: LawgenError, knob: str) -> LawgenDiagnostic:
    """Return the single collected diagnostic and assert it names ``knob``.

    The P2-2 single-knob fixtures each trip exactly one budget, so the collect-all
    :class:`LawgenError` (P3-1) carries exactly one diagnostic. This helper pins
    that (one diagnostic, the expected knob) and hands it back for the
    measured+limit assertions.
    """
    assert len(exc.diagnostics) == 1, [d.node for d in exc.diagnostics]
    (diag,) = exc.diagnostics
    assert diag.node == knob
    assert diag.fix.strip()  # every diagnostic carries an actionable fix
    return diag


# ---------------------------------------------------------------------------
# Shared symbols / a compliant SwiftVoce-like expression set.
# ---------------------------------------------------------------------------

_x, _n, _b, _p, _p0 = sp.symbols("x n b p p0")
_sigma0, _Q, _K = sp.symbols("sigma0 Q K")


def _swift_voce_expressions() -> dict[str, sp.Expr]:
    """A compliant SwiftVoce-like ``{R, H, Q}`` expression set.

    ``R = sigma0 + Q*(1 - exp(-b*p)) + K*((p + p0)**n - p0**n)``; ``H = 1``;
    ``Q = 1``. Small on every axis: a dozen ops, two symbolic-exponent powers,
    no ``Piecewise`` — comfortably inside every default budget.
    """
    r = _sigma0 + _Q * (1 - sp.exp(-_b * _p)) + _K * ((_p + _p0) ** _n - _p0**_n)
    return {"R": r, "H": sp.Integer(1), "Q": sp.Integer(1)}


def _lowered(n_temps: int = 0, n_returns: int = 1) -> LoweredExpr:
    """Build a ``LoweredExpr`` with the requested temporary/return line counts."""
    return LoweredExpr(
        temporaries=tuple(f"x{i} = 0.0" for i in range(n_temps)),
        returns=tuple(f"r{i}" for i in range(n_returns)),
    )


# ---------------------------------------------------------------------------
# Module-level counters — the reusable primitives (P2-3/P2-4/P3 depend here).
# ---------------------------------------------------------------------------


def test_count_expr_ops_matches_sympy() -> None:
    """``count_expr_ops`` returns an int equal to ``sp.count_ops``."""
    expr = _x**2 + 2 * _x + 1
    value = count_expr_ops(expr)
    assert isinstance(value, int)
    assert value == int(sp.count_ops(expr))


def test_count_piecewise_branches_takes_the_max() -> None:
    """Branch count is ``len(Piecewise.args)``; 0 when there is no Piecewise."""
    three = sp.Piecewise((_x, _x > 0), (2 * _x, _x < -1), (sp.Integer(0), True))
    assert count_piecewise_branches(three) == 3
    assert count_piecewise_branches(_x**2 + 1) == 0


def test_count_pow_symbolic_exponent_rule() -> None:
    """Only non-``Integer`` exponents count (symbolic, rational, float)."""
    assert count_pow_symbolic_exponent(_x**_n) == 1  # symbolic
    assert count_pow_symbolic_exponent(_x**2) == 0  # integer literal
    assert count_pow_symbolic_exponent(_x**-3) == 0  # negative integer
    # ±1/2 exponents lower to ti.sqrt / 1/ti.sqrt (P2-1 printer), NOT ti.pow,
    # so they are exempt from this runtime-ti.pow budget.
    assert count_pow_symbolic_exponent(sp.sqrt(_x)) == 0  # Pow(x, S.Half)
    assert count_pow_symbolic_exponent(1 / sp.sqrt(_x)) == 0  # Pow(x, -S.Half)
    assert count_pow_symbolic_exponent(_x ** sp.Rational(3, 2)) == 1  # non-half rational
    assert count_pow_symbolic_exponent(_x**2.0) == 1  # Float
    assert count_pow_symbolic_exponent(_x**_n + _p**_n) == 2  # two distinct symbolic


# ---------------------------------------------------------------------------
# Case 1 — max_expr_ops.
# ---------------------------------------------------------------------------


def test_max_expr_ops_exceeded_raises_named_error() -> None:
    """Exceeding ``max_expr_ops`` raises collect-all ``LawgenError`` naming knob/value/limit."""
    expr = _x**2 + 2 * _x + 1  # count_ops == 4
    target = TiconstitTarget(max_expr_ops=2)
    checker = BudgetChecker(target)

    with pytest.raises(LawgenError) as exc:
        checker.check_all({"R": expr}, {"R": _lowered()})

    diag = _sole_diagnostic(exc.value, "max_expr_ops")
    assert "4" in diag.reason  # measured
    assert "2" in diag.reason  # limit
    assert "budget exceeded" in diag.reason
    # The aggregate message surfaces the same knob + numbers.
    message = str(exc.value)
    assert "max_expr_ops" in message and "4" in message and "2" in message


# ---------------------------------------------------------------------------
# Case 2 — max_cse_temps_per_func.
# ---------------------------------------------------------------------------


def test_max_cse_temps_per_func_exceeded_raises() -> None:
    """Too many CSE temporaries in one function trips ``max_cse_temps_per_func``."""
    target = TiconstitTarget(max_cse_temps_per_func=2)
    checker = BudgetChecker(target)
    lowered = _lowered(n_temps=3, n_returns=1)  # 3 temporaries > 2

    with pytest.raises(LawgenError) as exc:
        checker.check_all({"R": sp.Integer(1)}, {"R": lowered})

    diag = _sole_diagnostic(exc.value, "max_cse_temps_per_func")
    assert "3" in diag.reason  # measured
    assert "2" in diag.reason  # limit


# ---------------------------------------------------------------------------
# Case 3 — max_func_lines.
# ---------------------------------------------------------------------------


def test_max_func_lines_exceeded_raises() -> None:
    """An over-length function (temps + returns) trips ``max_func_lines``."""
    target = TiconstitTarget(max_func_lines=3)
    checker = BudgetChecker(target)
    lowered = _lowered(n_temps=2, n_returns=2)  # 4 lines > 3

    with pytest.raises(LawgenError) as exc:
        checker.check_all({"R": sp.Integer(1)}, {"R": lowered})

    diag = _sole_diagnostic(exc.value, "max_func_lines")
    assert "4" in diag.reason  # measured
    assert "3" in diag.reason  # limit


# ---------------------------------------------------------------------------
# Case 4 — max_total_generated_lines_per_class.
# ---------------------------------------------------------------------------


def test_max_total_generated_lines_per_class_exceeded_raises() -> None:
    """The summed line count across functions trips the per-class budget.

    Each function stays under ``max_func_lines`` (5), but their *sum* (3 + 3 = 6)
    exceeds ``max_total_generated_lines_per_class`` (5), so only the class-level
    budget fires.
    """
    target = TiconstitTarget(max_func_lines=5, max_total_generated_lines_per_class=5)
    checker = BudgetChecker(target)
    lowered = {
        "R": _lowered(n_temps=2, n_returns=1),  # 3 lines
        "H": _lowered(n_temps=2, n_returns=1),  # 3 lines -> total 6
    }
    exprs = {"R": sp.Integer(1), "H": sp.Integer(1)}

    with pytest.raises(LawgenError) as exc:
        checker.check_all(exprs, lowered)

    diag = _sole_diagnostic(exc.value, "max_total_generated_lines_per_class")
    assert "6" in diag.reason  # measured total
    assert "5" in diag.reason  # limit


# ---------------------------------------------------------------------------
# Case 5 — max_piecewise_branches.
# ---------------------------------------------------------------------------


def test_max_piecewise_branches_exceeded_raises() -> None:
    """A ``Piecewise`` with too many branches trips ``max_piecewise_branches``."""
    piece = sp.Piecewise(
        (_x, _x > 2), (2 * _x, _x > 1), (3 * _x, _x > 0), (sp.Integer(0), True)
    )  # 4 branches
    target = TiconstitTarget(max_piecewise_branches=2)
    checker = BudgetChecker(target)

    with pytest.raises(LawgenError) as exc:
        checker.check_all({"R": piece}, {"R": _lowered()})

    diag = _sole_diagnostic(exc.value, "max_piecewise_branches")
    assert "4" in diag.reason  # measured
    assert "2" in diag.reason  # limit


# ---------------------------------------------------------------------------
# Case 6 — max_pow_with_symbolic_exponent.
# ---------------------------------------------------------------------------


def test_max_pow_with_symbolic_exponent_exceeded_raises() -> None:
    """Too many symbolic-exponent powers trip ``max_pow_with_symbolic_exponent``.

    Uses a *default* ``TiconstitTarget`` (limit 12) to prove the defaults are
    wired from P1-1: 13 distinct symbolic-exponent powers > 12.
    """
    bases = sp.symbols("a0:13")  # 13 distinct symbols
    expr = sp.Add(*[base**_n for base in bases])  # 13 symbolic-exponent Pow nodes
    checker = BudgetChecker(TiconstitTarget())  # default limit == 12

    with pytest.raises(LawgenError) as exc:
        checker.check_all({"R": expr}, {"R": _lowered()})

    diag = _sole_diagnostic(exc.value, "max_pow_with_symbolic_exponent")
    assert "13" in diag.reason  # measured
    assert "12" in diag.reason  # default limit


# ---------------------------------------------------------------------------
# Case 7 — compliant SwiftVoce passes.
# ---------------------------------------------------------------------------


def test_compliant_swift_voce_passes_check_all() -> None:
    """A compliant SwiftVoce set passes ``check_all`` under the default target."""
    exprs = _swift_voce_expressions()
    lowered = {role: _lowered(n_temps=1, n_returns=1) for role in exprs}
    checker = BudgetChecker(TiconstitTarget())

    # No exception == pass; check_all returns None.
    assert checker.check_all(exprs, lowered) is None


def test_check_all_accepts_bare_iterables() -> None:
    """``check_all`` also accepts bare iterables (no role keys), still checking."""
    exprs = list(_swift_voce_expressions().values())
    lowered = [_lowered(n_temps=1, n_returns=1) for _ in exprs]
    checker = BudgetChecker(TiconstitTarget())
    assert checker.check_all(exprs, lowered) is None


# ---------------------------------------------------------------------------
# Error hierarchy + knob-override wiring.
# ---------------------------------------------------------------------------


def test_budget_error_is_a_budget_exceeded_error() -> None:
    """``BudgetError`` keeps its REUSE.md hierarchy; ``check_all`` raises the P3-1 aggregate.

    P3-1 changes the raised *aggregate* to :class:`LawgenError` (a
    ``NotImplementedError`` subclass carrying every violation). :class:`BudgetError`
    is retained as the per-diagnostic ``reason`` formatter and still IS-A the
    shared :class:`BudgetExceededError` (REUSE.md), so callers building a
    :class:`BudgetError` directly keep the old hierarchy.
    """
    assert issubclass(BudgetError, BudgetExceededError)
    # A directly-built BudgetError still is-a BudgetExceededError (formatter role).
    assert isinstance(BudgetError.for_budget("max_expr_ops", 4, 1), BudgetExceededError)
    # check_all now raises the collect-all LawgenError aggregate.
    with pytest.raises(LawgenError):
        BudgetChecker(TiconstitTarget(max_expr_ops=1)).check_all(
            {"R": _x**2 + 2 * _x + 1}, {"R": _lowered()}
        )


def test_default_checker_uses_frozen_plan_defaults() -> None:
    """A ``BudgetChecker()`` with no target binds the plan-frozen defaults."""
    checker = BudgetChecker()
    assert checker.target.max_expr_ops == 400
    assert checker.target.max_cse_temps_per_func == 96
    assert checker.target.max_func_lines == 220
    assert checker.target.max_total_generated_lines_per_class == 900
    assert checker.target.max_piecewise_branches == 8
    assert checker.target.max_pow_with_symbolic_exponent == 12


def test_knob_override_changes_the_verdict() -> None:
    """The same input passes under defaults but fails under a lowered knob."""
    expr = _x**2 + 2 * _x + 1  # 4 ops
    lowered = {"R": _lowered()}
    # Default: 4 <= 400, passes.
    assert BudgetChecker(TiconstitTarget()).check_all({"R": expr}, lowered) is None
    # Overridden knob: 4 > 3, fails with the collect-all LawgenError.
    with pytest.raises(LawgenError):
        BudgetChecker(TiconstitTarget(max_expr_ops=3)).check_all({"R": expr}, lowered)
