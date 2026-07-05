"""Unit tests for the collect-all lawgen diagnostics layer (Task P3-1).

MFront-mimic Cycle M0, Phase 3 (``dev/plans/mfront_cycleM0.md`` lines 98-100).

Covers the four ``test_plan.cases``:

1. Two distinct unsupported nodes → both surface in ONE ``LawgenError`` (no
   silent drop) — checked via lowering AND via a raw collector.
2. A budget breach → the diagnostic's ``reason`` names the measured value AND the
   limit.
3. No diagnostics → ``DiagnosticCollector.raise_if_any()`` is a no-op.
4. The ``fix`` field is a non-empty, actionable string for every diagnostic type
   the lawgen pipeline can emit (unsupported node, non-exhaustive Piecewise,
   each of the six budget knobs).

Plus the surrounding contract: the five required non-empty fields, the aggregate
message/args discoverability, the ``NotImplementedError`` hierarchy, and the
context-manager form.
"""

from __future__ import annotations

import pytest
import sympy as sp

from mechdsl.lawgen.budgets import BudgetChecker
from mechdsl.lawgen.contracts import TiconstitTarget
from mechdsl.lawgen.diagnostics import (
    DiagnosticCollector,
    LawgenDiagnostic,
    LawgenError,
)
from mechdsl.lawgen.sympy_to_taichi import LoweredExpr, lower_expression


def _diag(**overrides: str) -> LawgenDiagnostic:
    """Build a complete :class:`LawgenDiagnostic`, overriding any field."""
    fields = {
        "law": "R",
        "expression": "foo(x)",
        "node": "foo",
        "reason": "unsupported function 'foo'",
        "fix": "register foo in MATH_TO_TAICHI",
    }
    fields.update(overrides)
    return LawgenDiagnostic(**fields)


def _lowered(n_temps: int = 0, n_returns: int = 1) -> LoweredExpr:
    """A ``LoweredExpr`` with the requested temporary/return line counts."""
    return LoweredExpr(
        temporaries=tuple(f"x{i} = 0.0" for i in range(n_temps)),
        returns=tuple(f"r{i}" for i in range(n_returns)),
    )


# ---------------------------------------------------------------------------
# LawgenDiagnostic — five required, non-empty fields.
# ---------------------------------------------------------------------------


def test_diagnostic_has_all_five_fields() -> None:
    """A ``LawgenDiagnostic`` exposes law/expression/node/reason/fix (AC1)."""
    diag = _diag()
    assert diag.law == "R"
    assert diag.expression == "foo(x)"
    assert diag.node == "foo"
    assert diag.reason == "unsupported function 'foo'"
    assert diag.fix == "register foo in MATH_TO_TAICHI"


@pytest.mark.parametrize("field", ["law", "expression", "node", "reason", "fix"])
def test_diagnostic_rejects_empty_field(field: str) -> None:
    """Every field must be a non-empty string — a blank one is rejected at construction."""
    with pytest.raises(ValueError, match=field):
        _diag(**{field: ""})
    with pytest.raises(ValueError, match=field):
        _diag(**{field: "   "})  # whitespace-only is also empty


# ---------------------------------------------------------------------------
# Case 1 — two unsupported nodes → both appear in one LawgenError.
# ---------------------------------------------------------------------------


def test_two_unsupported_nodes_both_reported_via_lowering() -> None:
    """Two distinct undefined functions → both in one ``LawgenError`` (AC2, no silent drop)."""
    x = sp.Symbol("x")
    foo = sp.Function("foo")
    bar = sp.Function("bar")

    with pytest.raises(LawgenError) as exc:
        lower_expression(foo(x) + bar(x))

    nodes = sorted(d.node for d in exc.value.diagnostics)
    assert nodes == ["bar", "foo"]
    # Both appear in the message AND in .args (the P3-1 acceptance surface).
    message = str(exc.value)
    assert "foo" in message and "bar" in message
    arg_text = " ".join(str(a) for a in exc.value.args)
    assert "foo" in arg_text and "bar" in arg_text


def test_defined_and_undefined_unsupported_both_reported() -> None:
    """A defined-but-unmapped func (``erf``) AND an undefined one (``foo``) both surface."""
    x = sp.Symbol("x")
    foo = sp.Function("foo")

    with pytest.raises(LawgenError) as exc:
        lower_expression(sp.erf(x) + foo(x))

    assert sorted(d.node for d in exc.value.diagnostics) == ["erf", "foo"]


def test_collector_accumulates_two_diagnostics() -> None:
    """A raw ``DiagnosticCollector`` surfaces every added diagnostic in one error."""
    collector = DiagnosticCollector()
    collector.add(_diag(node="foo"))
    collector.add(_diag(node="bar", expression="bar(x)", reason="unsupported 'bar'"))

    with pytest.raises(LawgenError) as exc:
        collector.raise_if_any()

    assert sorted(d.node for d in exc.value.diagnostics) == ["bar", "foo"]
    assert len(exc.value.diagnostics) == 2


# ---------------------------------------------------------------------------
# Case 2 — budget breach reason contains measured value AND limit.
# ---------------------------------------------------------------------------


def test_budget_breach_reason_has_measured_and_limit() -> None:
    """A budget-breach diagnostic's ``reason`` names both the measured value and the limit (AC3)."""
    x = sp.Symbol("x")
    checker = BudgetChecker(TiconstitTarget(max_expr_ops=2))

    with pytest.raises(LawgenError) as exc:
        checker.check_all({"R": x**2 + 2 * x + 1}, {"R": _lowered()})  # 4 ops > 2

    (diag,) = exc.value.diagnostics
    assert diag.node == "max_expr_ops"
    assert "4" in diag.reason  # measured
    assert "2" in diag.reason  # limit


def test_multiple_budget_breaches_collect_all() -> None:
    """Two knobs over budget → two diagnostics in one ``LawgenError`` (collect-all, not fail-first)."""
    x, n = sp.symbols("x n")
    # Trips max_expr_ops (many ops) AND max_pow_with_symbolic_exponent (2 sym-pows > 1).
    checker = BudgetChecker(TiconstitTarget(max_expr_ops=2, max_pow_with_symbolic_exponent=1))

    with pytest.raises(LawgenError) as exc:
        checker.check_all({"R": x**n + (x + 1) ** n + 2 * x + 1}, {"R": _lowered()})

    knobs = sorted(d.node for d in exc.value.diagnostics)
    assert "max_expr_ops" in knobs
    assert "max_pow_with_symbolic_exponent" in knobs


# ---------------------------------------------------------------------------
# Case 3 — no diagnostics → raise_if_any() is a no-op.
# ---------------------------------------------------------------------------


def test_empty_collector_raise_if_any_is_noop() -> None:
    """An empty collector's ``raise_if_any()`` returns cleanly (AC: no-op) — the only silent path."""
    collector = DiagnosticCollector()
    assert collector.raise_if_any() is None
    assert not collector  # __bool__ is False when empty
    assert len(collector) == 0


def test_compliant_law_lowers_without_error() -> None:
    """A clean expression lowers with no ``LawgenError`` (no false-positive diagnostics)."""
    sigma0, Q, b, p = sp.symbols("sigma0 Q b p")
    result = lower_expression(sigma0 + Q * (1 - sp.exp(-b * p)))
    assert result.returns  # emitted cleanly


def test_lawgen_error_requires_at_least_one_diagnostic() -> None:
    """Constructing a ``LawgenError`` with no diagnostics is itself an error (never raise nothing)."""
    with pytest.raises(ValueError, match="at least one diagnostic"):
        LawgenError([])


# ---------------------------------------------------------------------------
# Case 4 — fix is non-empty for every diagnostic type the pipeline emits.
# ---------------------------------------------------------------------------


def test_fix_non_empty_for_unsupported_node() -> None:
    """The unsupported-node diagnostic carries an actionable, non-empty ``fix`` (AC1/AC4)."""
    x = sp.Symbol("x")
    with pytest.raises(LawgenError) as exc:
        lower_expression(sp.Function("foo")(x))
    (diag,) = exc.value.diagnostics
    assert diag.fix.strip()
    assert "foo" in diag.fix  # actionable: names the offending node


def test_fix_non_empty_for_non_exhaustive_piecewise() -> None:
    """The non-exhaustive-Piecewise diagnostic carries a non-empty ``fix``."""
    x = sp.Symbol("x")
    with pytest.raises(LawgenError) as exc:
        lower_expression(sp.Piecewise((x, x > 0)))  # no True default branch
    piecewise_diags = [d for d in exc.value.diagnostics if d.node == "Piecewise"]
    assert piecewise_diags
    for diag in piecewise_diags:
        assert diag.fix.strip()
        assert "True" in diag.fix  # actionable: add a (value, True) default


def test_fix_non_empty_for_every_budget_knob() -> None:
    """Every one of the six budget knobs yields a diagnostic with a non-empty ``fix`` (AC4)."""
    x, y, n = sp.symbols("x y n")
    # A single target with every knob lowered so ALL six trip at once, proving the
    # collect-all path emits a fix for each knob type.
    target = TiconstitTarget(
        max_expr_ops=1,
        max_cse_temps_per_func=1,
        max_func_lines=1,
        max_total_generated_lines_per_class=1,
        max_piecewise_branches=1,
        max_pow_with_symbolic_exponent=1,
    )
    checker = BudgetChecker(target)
    # Expression trips: expr_ops, piecewise_branches, pow_symbolic_exponent.
    piece = sp.Piecewise((x**n, x > 0), (y**n, x < 0), (sp.Integer(0), True))
    # Lowered trips: cse_temps, func_lines, total_generated_lines.
    lowered = _lowered(n_temps=3, n_returns=2)

    with pytest.raises(LawgenError) as exc:
        checker.check_all({"R": piece}, {"R": lowered})

    knobs = {d.node for d in exc.value.diagnostics}
    assert knobs == {
        "max_expr_ops",
        "max_cse_temps_per_func",
        "max_func_lines",
        "max_total_generated_lines_per_class",
        "max_piecewise_branches",
        "max_pow_with_symbolic_exponent",
    }
    for diag in exc.value.diagnostics:
        assert diag.fix.strip(), f"empty fix for {diag.node}"
        assert diag.node in diag.reason  # reason names the knob
        # Reason carries measured + limit (both integers appear).
        assert any(ch.isdigit() for ch in diag.reason)


# ---------------------------------------------------------------------------
# LawgenError hierarchy + DiagnosticCollector context-manager form.
# ---------------------------------------------------------------------------


def test_lawgen_error_is_a_not_implemented_error() -> None:
    """``LawgenError`` IS-A ``NotImplementedError`` — Phase-2 fail-loud catchers still work."""
    assert issubclass(LawgenError, NotImplementedError)
    x = sp.Symbol("x")
    with pytest.raises(NotImplementedError):  # the Phase-2 contract
        lower_expression(sp.Function("foo")(x))


def test_collector_context_manager_raises_on_clean_exit() -> None:
    """The context-manager form raises collected diagnostics on a clean block exit."""
    with pytest.raises(LawgenError) as exc, DiagnosticCollector() as collector:
        collector.add(_diag(node="foo"))
    assert exc.value.diagnostics[0].node == "foo"


def test_collector_context_manager_noop_when_empty() -> None:
    """The context-manager form is a no-op when nothing was collected."""
    with DiagnosticCollector() as collector:
        assert not collector  # nothing added


def test_collector_context_manager_does_not_swallow_body_exception() -> None:
    """A real exception in the ``with`` body propagates untouched (no swallow to raise an aggregate)."""
    with pytest.raises(RuntimeError, match="boom"), DiagnosticCollector() as collector:
        collector.add(_diag())  # even with a pending diagnostic ...
        raise RuntimeError("boom")  # ... the real error wins


def test_extend_collects_multiple() -> None:
    """``extend`` records several diagnostics in order."""
    collector = DiagnosticCollector()
    collector.extend([_diag(node="foo"), _diag(node="bar")])
    assert [d.node for d in collector] == ["foo", "bar"]
