"""Plan-anchor tests for Task P3-1: structured diagnostics for unsupported nodes + budget breaches.

Plan: dev/plans/mfront_cycleM0.md (lines 98-100) — MFront-mimic Cycle M0, Phase 3.
Deliverable under test:
  packages/mechdsl-core/src/mechdsl/lawgen/diagnostics.py

LawgenDiagnostic(law, expression, node, reason, fix) — all 5 required strings.
DiagnosticCollector.add + raise_if_any() -> LawgenError (collect-all, no silent drop, R2).
P3-1 wires the collector into P2-2 (budget) + P2-4 (lowering unsupported-node path).

The four test_plan.cases (exhaustive API/branch coverage lives in
tests/lawgen/test_diagnostics.py):
1. two unsupported nodes → both appear in one LawgenError.args
2. budget breach → diagnostic reason contains measured value + limit
3. no diagnostics → raise_if_any() is a no-op
4. fix field is non-empty for every diagnostic type
"""

from __future__ import annotations

import pytest
import sympy as sp

from mechdsl.lawgen.budgets import BudgetChecker
from mechdsl.lawgen.contracts import TiconstitTarget
from mechdsl.lawgen.diagnostics import DiagnosticCollector, LawgenError
from mechdsl.lawgen.sympy_to_taichi import LoweredExpr, lower_expression


def _lowered(n_temps: int = 0, n_returns: int = 1) -> LoweredExpr:
    """A ``LoweredExpr`` with the requested temporary/return line counts."""
    return LoweredExpr(
        temporaries=tuple(f"x{i} = 0.0" for i in range(n_temps)),
        returns=tuple(f"r{i}" for i in range(n_returns)),
    )


class TestTaskP3_1:
    """Tests for Task P3-1: structured diagnostics. AC covered: 1-4."""

    @pytest.mark.unit
    def test_two_unsupported_nodes_both_reported(self) -> None:
        """Verifies: two distinct unsupported-node diagnostics both surface in one LawgenError.
        AC2: collect-all — no silent drop.
        Passes when: LawgenError.args (and .diagnostics) contains both diagnostics."""
        x = sp.Symbol("x")
        foo = sp.Function("foo")
        bar = sp.Function("bar")

        with pytest.raises(LawgenError) as exc:
            lower_expression(foo(x) + bar(x))

        nodes = sorted(d.node for d in exc.value.diagnostics)
        assert nodes == ["bar", "foo"]  # both collected, neither dropped
        # Both also discoverable off .args (the acceptance surface).
        arg_text = " ".join(str(a) for a in exc.value.args)
        assert "foo" in arg_text and "bar" in arg_text

    @pytest.mark.unit
    def test_budget_breach_reason_has_measured_and_limit(self) -> None:
        """Verifies: a budget-breach diagnostic's `reason` names the measured value and the limit.
        AC3: budget diagnostic reason includes limit + measured.
        Passes when: the diagnostic reason string contains both numbers."""
        x = sp.Symbol("x")
        checker = BudgetChecker(TiconstitTarget(max_expr_ops=2))

        with pytest.raises(LawgenError) as exc:
            checker.check_all({"R": x**2 + 2 * x + 1}, {"R": _lowered()})  # 4 ops > 2

        (diag,) = exc.value.diagnostics
        assert diag.node == "max_expr_ops"
        assert "4" in diag.reason  # measured
        assert "2" in diag.reason  # limit

    @pytest.mark.unit
    def test_no_diagnostics_raise_if_any_is_noop(self) -> None:
        """Verifies: raise_if_any() is a no-op when no diagnostics were collected.
        Passes when: an empty collector's raise_if_any() returns without raising."""
        collector = DiagnosticCollector()
        assert collector.raise_if_any() is None
        assert not collector

    @pytest.mark.unit
    def test_fix_field_non_empty_for_every_diagnostic_type(self) -> None:
        """Verifies: the `fix` field is a non-empty, actionable string for every supported diagnostic.
        AC1: LawgenDiagnostic has all five fields incl. a meaningful `fix`.
        Passes when: every emitted diagnostic type (unsupported node, non-exhaustive Piecewise,
        each budget knob) has a non-empty fix."""
        x, y, n = sp.symbols("x y n")

        # (a) unsupported node.
        with pytest.raises(LawgenError) as exc_node:
            lower_expression(sp.Function("foo")(x))
        assert all(d.fix.strip() for d in exc_node.value.diagnostics)

        # (b) non-exhaustive Piecewise.
        with pytest.raises(LawgenError) as exc_pw:
            lower_expression(sp.Piecewise((x, x > 0)))
        assert all(d.fix.strip() for d in exc_pw.value.diagnostics)

        # (c) all six budget knobs at once.
        target = TiconstitTarget(
            max_expr_ops=1,
            max_cse_temps_per_func=1,
            max_func_lines=1,
            max_total_generated_lines_per_class=1,
            max_piecewise_branches=1,
            max_pow_with_symbolic_exponent=1,
        )
        piece = sp.Piecewise((x**n, x > 0), (y**n, x < 0), (sp.Integer(0), True))
        with pytest.raises(LawgenError) as exc_budget:
            BudgetChecker(target).check_all({"R": piece}, {"R": _lowered(n_temps=3, n_returns=2)})
        emitted_knobs = {d.node for d in exc_budget.value.diagnostics}
        assert len(emitted_knobs) == 6  # all six knob types emitted
        assert all(d.fix.strip() for d in exc_budget.value.diagnostics)
