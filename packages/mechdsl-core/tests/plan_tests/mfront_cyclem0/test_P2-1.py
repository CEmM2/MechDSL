"""Plan tests for Task P2-1: route expression lowering through a real printer.

Plan: dev/plans/mfront_cycleM0.md (lines 76-78) — MFront-mimic Cycle M0, Phase 2.
Deliverable under test (built in P2-1 exec):
  packages/mechdsl-core/src/mechdsl/lawgen/sympy_to_taichi.py

Binding acceptance invariants (P1-3 REUSE.md, Gate-B-verified): the lowerer adds
a dedicated SymPy->Taichi printer (reusing the whitelist idea from
energy_emitter._MATH_TO_TAICHI + a StrPrinter subclass), NOT sp.pycode/regex (R4);
it applies deterministic sp.cse(order='canonical'); and CSE temporaries are
emitted before the return expressions.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import sympy as sp

from mechdsl.lawgen import sympy_to_taichi as _lowerer_module
from mechdsl.lawgen.sympy_to_taichi import lower_expression


class TestTaskP2_1:
    """Tests for Task P2-1: sympy_to_taichi lowerer (deterministic CSE). AC covered: 1-5."""

    @pytest.mark.unit
    def test_lower_simple_quadratic_to_taichi(self) -> None:
        """Verifies: a simple SymPy expr lowers to the expected Taichi string.
        AC3: output for a known expression matches the expected Taichi snippet (golden).
        AC1: no pycode/re.sub is used in the lowerer module source."""
        x = sp.Symbol("x")
        result = lower_expression(x**2 + 2 * x + 1)

        # Golden: no shared sub-expression, so no CSE temp; one return line.
        # Since P2-4 the small-integer ``x**2`` is inlined to ``x*x`` (not ti.pow).
        assert result.temporaries == ()
        assert result.returns == ("x*x + 2*x + 1",)

        # AC1: the R4 anti-pattern (pycode + regex substitution) is absent.
        source = Path(_lowerer_module.__file__).read_text(encoding="utf-8")
        assert "pycode" not in source
        assert not re.search(r"re\.sub", source)

    @pytest.mark.unit
    def test_repeated_subexpression_introduces_cse_temp(self) -> None:
        """Verifies: a repeated sub-expression is factored into a CSE temporary.
        AC1/AC4: sp.cse used (not pycode); CSE temporaries emitted before the return expr.
        Passes when: an expr with a shared sub-term emits a temp assignment ahead of the result."""
        b, p = sp.symbols("b p")
        shared = sp.exp(-b * p)
        result = lower_expression(shared * (1 + shared))

        # The shared exp(-b*p) is lifted to a temporary, printed as a ti.* call.
        assert result.temporaries == ("x0 = ti.exp(-b*p)",)
        assert result.returns == ("x0*(x0 + 1)",)
        # AC4: the temporary assignment precedes and feeds the return expression.
        assert result.temporaries[0].startswith("x0 = ")
        assert "x0" in result.returns[0]

    @pytest.mark.unit
    def test_cse_canonical_order_is_deterministic(self) -> None:
        """Verifies: sp.cse(order='canonical') yields identical output across calls.
        AC2: sp.cse is called with order='canonical' for determinism.
        Passes when: lowering the same expr twice produces byte-identical emitted lines."""
        b, p, sigma0, Q, K, n = sp.symbols("b p sigma0 Q K n")
        shared = sp.exp(-b * p)
        exprs = [sigma0 + Q * (1 - shared) + K * p**n, Q * shared]

        first = lower_expression(exprs)
        second = lower_expression(exprs)

        assert first == second
        assert first.temporaries == second.temporaries
        assert first.returns == second.returns
