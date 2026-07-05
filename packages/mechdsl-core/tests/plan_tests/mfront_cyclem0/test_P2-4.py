"""Plan tests for Task P2-4: Taichi-safe lowering table + deterministic source hash.

Plan: dev/plans/mfront_cycleM0.md (lines 87-90) — MFront-mimic Cycle M0, Phase 2.
Deliverable under test (built in P2-4 exec):
  lowering table + source_hash in packages/mechdsl-core/src/mechdsl/lawgen/sympy_to_taichi.py;
  packages/mechdsl-core/tests/lawgen/test_lowering_table.py

Table: exp->ti.exp, Piecewise->nested ti.select (under branch budget), Pow(x,small_int)->mul.
source_hash = sha256 over the emitted lines in emission order (temporaries then returns).

These plan-level assertions pin the six acceptance criteria; the exhaustive
behaviour (thresholds, boundaries, budget override, guarded branches) lives in
tests/lawgen/test_lowering_table.py.
"""

from __future__ import annotations

import re

import pytest
import sympy as sp

from mechdsl.lawgen.diagnostics import LawgenError
from mechdsl.lawgen.sympy_to_taichi import lower_expression


class TestTaskP2_4:
    """Tests for Task P2-4: Taichi-safe lowering table + source hash. AC covered: 1-6."""

    @pytest.mark.unit
    def test_exp_lowers_to_ti_exp(self) -> None:
        """Verifies: sp.exp(x) lowers to 'ti.exp(x)' (no raw 'exp').
        AC1: exp->ti.exp mapping.
        Passes when: the emitted output contains 'ti.exp(x)' and no bare 'exp('."""
        x = sp.Symbol("x")
        emitted = lower_expression(sp.exp(x)).returns[0]

        assert emitted == "ti.exp(x)"
        # No bare ``exp(`` outside the ``ti.exp`` call.
        assert emitted.replace("ti.exp(", "") == "x)"

    @pytest.mark.unit
    def test_piecewise_within_budget_becomes_nested_select(self) -> None:
        """Verifies: a Piecewise with <= max_piecewise_branches lowers to nested ti.select.
        AC2: Piecewise -> nested ti.select under branch budget.
        Passes when: a 3-branch Piecewise emits a nested ti.select chain."""
        x, y = sp.symbols("x y")
        piece = sp.Piecewise((x, x > 0), (y, x < 0), (0, True))
        emitted = lower_expression(piece).returns[0]

        assert emitted == "ti.select(x > 0, x, ti.select(x < 0, y, 0))"
        # 3 branches → 2 nested selects (right-nested chain).
        assert emitted.count("ti.select") == 2

    @pytest.mark.unit
    def test_piecewise_over_budget_raises(self) -> None:
        """Verifies: a Piecewise exceeding the branch budget fails loud (P2-2 budget, P3-1 aggregate).
        AC3: over-budget Piecewise fails loud.
        Passes when: a 9-branch Piecewise raises a LawgenError whose budget diagnostic
        names the knob + measured (9) + limit (8)."""
        a = sp.Symbol("a")
        pairs = [(sp.Integer(i), a > i) for i in range(8)]
        pairs.append((sp.Integer(99), sp.true))
        piece = sp.Piecewise(*pairs)
        assert len(piece.args) == 9

        with pytest.raises(LawgenError) as exc:
            lower_expression(piece)
        (diag,) = exc.value.diagnostics
        assert diag.node == "max_piecewise_branches"
        assert "max_piecewise_branches budget exceeded: 9 > 8" in diag.reason

    @pytest.mark.unit
    def test_small_int_pow_inlined_as_multiplication(self) -> None:
        """Verifies: Pow(x, 2) inlines to multiplication (x*x), not ti.pow.
        AC4: Pow(x, small_int) -> multiplication (threshold documented).
        Passes when: the emitted output for x**2 is 'x*x' (or inlined), not a ti.pow call."""
        x = sp.Symbol("x")
        emitted = lower_expression(x**2).returns[0]

        assert emitted == "x*x"
        assert "ti.pow" not in emitted
        assert "**" not in emitted

    @pytest.mark.unit
    def test_same_input_yields_same_source_hash(self) -> None:
        """Verifies: lowering the same spec twice produces an identical source_hash.
        AC5: deterministic source hash.
        Passes when: two lower_expression calls on the same input hash-match."""
        sigma0, Q, b, p, K, n, p0 = sp.symbols("sigma0 Q b p K n p0")
        expr = sigma0 + Q * (1 - sp.exp(-b * p)) + K * ((p + p0) ** n - p0**n)

        first = lower_expression(expr)
        second = lower_expression(expr)

        assert first.source_hash == second.source_hash

    @pytest.mark.unit
    def test_source_hash_is_64_hex_chars(self) -> None:
        """Verifies: source_hash is a 64-char hex sha256 string.
        AC6: source_hash format.
        Passes when: the hash matches ^[0-9a-f]{64}$."""
        x = sp.Symbol("x")
        result = lower_expression(sp.exp(x) + x**2)

        assert re.match(r"^[0-9a-f]{64}$", result.source_hash)
        assert len(result.source_hash) == 64
