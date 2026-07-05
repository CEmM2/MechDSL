"""Plan-anchor tests for Task P2-2: budget checks that fail emission before Taichi sees over-budget source.

Plan: dev/plans/mfront_cycleM0.md (lines 79-82) — MFront-mimic Cycle M0, Phase 2.
Deliverable under test:
  packages/mechdsl-core/src/mechdsl/lawgen/budgets.py

The six limits are frozen and must match TiconstitTarget (P1-1) field names/defaults:
max_expr_ops=400, max_cse_temps_per_func=96, max_func_lines=220,
max_total_generated_lines_per_class=900, max_piecewise_branches=8,
max_pow_with_symbolic_exponent=12.

P3-1 update (collect-all): ``check_all`` now accumulates EVERY budget violation
and raises one ``diagnostics.LawgenError`` carrying them all (each diagnostic's
``reason`` names the knob, the measured value, and the limit). The single-knob
fixtures below trip exactly one budget, so the aggregate carries one diagnostic.

These are the seven test_plan.cases (one per budget knob + the compliant pass);
the exhaustive counter/hierarchy coverage lives in tests/lawgen/test_budgets.py.
"""

from __future__ import annotations

import pytest
import sympy as sp

from mechdsl.lawgen.budgets import BudgetChecker
from mechdsl.lawgen.contracts import TiconstitTarget
from mechdsl.lawgen.diagnostics import LawgenError
from mechdsl.lawgen.sympy_to_taichi import LoweredExpr


def _lowered(n_temps: int = 0, n_returns: int = 1) -> LoweredExpr:
    """A ``LoweredExpr`` with the requested temporary/return line counts."""
    return LoweredExpr(
        temporaries=tuple(f"x{i} = 0.0" for i in range(n_temps)),
        returns=tuple(f"r{i}" for i in range(n_returns)),
    )


class TestTaskP2_2:
    """Tests for Task P2-2: budget checks. AC covered: fail-loud per knob + compliant pass.

    Under P3-1 the raised aggregate is ``LawgenError`` (collect-all); each
    single-knob fixture trips exactly one budget, so the aggregate carries one
    diagnostic whose ``reason`` names the knob + measured + limit.
    """

    @staticmethod
    def _sole_reason(exc: LawgenError, knob: str) -> str:
        """Assert the aggregate carries one diagnostic for ``knob`` and return its reason."""
        assert len(exc.diagnostics) == 1, [d.node for d in exc.diagnostics]
        (diag,) = exc.diagnostics
        assert diag.node == knob
        assert diag.fix.strip()  # actionable fix present
        return diag.reason

    @pytest.mark.unit
    def test_max_expr_ops_exceeded_raises_named_error(self) -> None:
        """Verifies: exceeding max_expr_ops raises a LawgenError naming the knob + value + limit.
        Passes when: an over-ops expr set raises with 'max_expr_ops' + measured + limit in the reason."""
        x = sp.Symbol("x")
        checker = BudgetChecker(TiconstitTarget(max_expr_ops=2))
        with pytest.raises(LawgenError) as exc:
            checker.check_all({"R": x**2 + 2 * x + 1}, {"R": _lowered()})
        reason = self._sole_reason(exc.value, "max_expr_ops")
        assert "4" in reason and "2" in reason  # measured > limit

    @pytest.mark.unit
    def test_max_cse_temps_per_func_exceeded_raises(self) -> None:
        """Verifies: exceeding max_cse_temps_per_func raises a LawgenError.
        Passes when: too many CSE temporaries trip the named budget (measured + limit in reason)."""
        checker = BudgetChecker(TiconstitTarget(max_cse_temps_per_func=2))
        with pytest.raises(LawgenError) as exc:
            checker.check_all({"R": sp.Integer(1)}, {"R": _lowered(n_temps=3)})
        reason = self._sole_reason(exc.value, "max_cse_temps_per_func")
        assert "3" in reason and "2" in reason

    @pytest.mark.unit
    def test_max_func_lines_exceeded_raises(self) -> None:
        """Verifies: exceeding max_func_lines raises a LawgenError.
        Passes when: an over-length function trips the named budget (measured + limit in reason)."""
        checker = BudgetChecker(TiconstitTarget(max_func_lines=3))
        with pytest.raises(LawgenError) as exc:
            checker.check_all({"R": sp.Integer(1)}, {"R": _lowered(n_temps=2, n_returns=2)})
        reason = self._sole_reason(exc.value, "max_func_lines")
        assert "4" in reason and "3" in reason

    @pytest.mark.unit
    def test_max_total_generated_lines_per_class_exceeded_raises(self) -> None:
        """Verifies: exceeding max_total_generated_lines_per_class raises a LawgenError.
        Passes when: an over-length class trips the named budget (measured + limit in reason)."""
        checker = BudgetChecker(
            TiconstitTarget(max_func_lines=5, max_total_generated_lines_per_class=5)
        )
        lowered = {
            "R": _lowered(n_temps=2, n_returns=1),  # 3 lines
            "H": _lowered(n_temps=2, n_returns=1),  # 3 lines -> total 6 > 5
        }
        with pytest.raises(LawgenError) as exc:
            checker.check_all({"R": sp.Integer(1), "H": sp.Integer(1)}, lowered)
        reason = self._sole_reason(exc.value, "max_total_generated_lines_per_class")
        assert "6" in reason and "5" in reason

    @pytest.mark.unit
    def test_max_piecewise_branches_exceeded_raises(self) -> None:
        """Verifies: exceeding max_piecewise_branches raises a LawgenError.
        Passes when: a Piecewise with too many branches trips the named budget (measured + limit)."""
        x = sp.Symbol("x")
        piece = sp.Piecewise(
            (x, x > 2), (2 * x, x > 1), (3 * x, x > 0), (sp.Integer(0), True)
        )  # 4 branches
        checker = BudgetChecker(TiconstitTarget(max_piecewise_branches=2))
        with pytest.raises(LawgenError) as exc:
            checker.check_all({"R": piece}, {"R": _lowered()})
        reason = self._sole_reason(exc.value, "max_piecewise_branches")
        assert "4" in reason and "2" in reason

    @pytest.mark.unit
    def test_max_pow_with_symbolic_exponent_exceeded_raises(self) -> None:
        """Verifies: exceeding max_pow_with_symbolic_exponent raises a LawgenError.
        Passes when: too many symbolic-exponent powers trip the named budget (measured + limit)."""
        n = sp.Symbol("n")
        bases = sp.symbols("a0:13")  # 13 distinct symbols
        expr = sp.Add(*[base**n for base in bases])  # 13 symbolic-exponent Pow nodes
        checker = BudgetChecker(TiconstitTarget())  # default limit == 12
        with pytest.raises(LawgenError) as exc:
            checker.check_all({"R": expr}, {"R": _lowered()})
        reason = self._sole_reason(exc.value, "max_pow_with_symbolic_exponent")
        assert "13" in reason and "12" in reason

    @pytest.mark.unit
    def test_compliant_swift_voce_passes_check_all(self) -> None:
        """Verifies: a compliant SwiftVoce expression set passes check_all with no error.
        AC: budget knobs from TiconstitTarget (P1-1) override module defaults.
        Passes when: check_all on in-budget expressions returns cleanly."""
        sigma0, Q, K, b, p, p0, n = sp.symbols("sigma0 Q K b p p0 n")
        r = sigma0 + Q * (1 - sp.exp(-b * p)) + K * ((p + p0) ** n - p0**n)
        exprs = {"R": r, "H": sp.Integer(1), "Q": sp.Integer(1)}
        lowered = {role: _lowered(n_temps=1, n_returns=1) for role in exprs}
        checker = BudgetChecker(TiconstitTarget())
        assert checker.check_all(exprs, lowered) is None
