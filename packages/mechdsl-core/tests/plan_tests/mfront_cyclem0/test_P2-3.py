"""Plan tests for Task P2-3: numerical-guard injection (the key correctness task, plan risk R2).

Plan: dev/plans/mfront_cycleM0.md (lines 83-86) — MFront-mimic Cycle M0, Phase 2.
Deliverable under test (built in P2-3 exec):
  guard-injection logic in packages/mechdsl-core/src/mechdsl/lawgen/guard_transforms.py
  + TaichiGuardedPrinter / lower_expression(guards=...) in sympy_to_taichi.py;
  unit tests in packages/mechdsl-core/tests/lawgen/test_guard_injection.py.

Guards reproduce Cycle 0 swift_voce.py hand-written guards:
  pow(base, non-integer exp) -> ti.pow(ti.max(base, 1e-12), exp)   (base floor, safe pattern)
  log(x)/sqrt(x)             -> ti.log/ti.sqrt(ti.max(x, 1e-12))
  division (variable denom)  -> sign-preserving guard
                                ti.select(d >= 0, ti.max(d, 1e-12), ti.min(d, -1e-12))
  exp(...)                   -> UNGUARDED (matches the Voce idiom; the #1 risk)

GOLDEN gate: the SwiftVoce R guard structure is asserted against string literals
transcribed from NumerixWeave libs/ticonstit/.../generated/plasticity/swift_voce.py
get_R (separate repo — NOT read at test time, R3).
"""

from __future__ import annotations

import pytest
import sympy as sp

from mechdsl.lawgen.sympy_to_taichi import lower_expression


class TestTaskP2_3:
    """Tests for Task P2-3: numerical-guard injection. AC covered: 1-5."""

    @pytest.mark.unit
    def test_pow_symbolic_exponent_gets_select_guard(self) -> None:
        """Verifies: pow(x, alpha) with symbolic alpha emits a safe base-floor guard.
        AC1: symbolic-exponent pow is wrapped in a safe pattern (base floored, not left bare).
        Passes when: the emitted string floors the base ti.max(x, 1e-12) inside a ti.pow.

        (The plan title says "ti.select"; the AC allows "ti.select-wrapped form OR
        equivalent safe pattern". swift_voce.py get_R/get_dR use the ti.max base-floor
        — an equivalent safe pattern — so that is what is reproduced.)"""
        x, alpha = sp.symbols("x alpha")
        emitted = lower_expression(x**alpha).returns[0]
        assert emitted == "ti.pow(ti.max(x, 1e-12), alpha)"

    @pytest.mark.unit
    def test_log_argument_wrapped_with_ti_max(self) -> None:
        """Verifies: log(x) emits ti.log(ti.max(x, 1e-12)).
        AC2: log arguments domain-guarded.
        Passes when: the emitted string contains ti.max(x, 1e-12) inside the log."""
        x = sp.Symbol("x")
        emitted = lower_expression(sp.log(x)).returns[0]
        assert emitted == "ti.log(ti.max(x, 1e-12))"

    @pytest.mark.unit
    def test_sqrt_argument_wrapped_with_ti_max(self) -> None:
        """Verifies: sqrt(x) emits ti.sqrt(ti.max(x, 1e-12)).
        AC2: sqrt arguments domain-guarded.
        Passes when: the emitted string contains ti.max(x, 1e-12) inside the sqrt."""
        x = sp.Symbol("x")
        emitted = lower_expression(sp.sqrt(x)).returns[0]
        assert emitted == "ti.sqrt(ti.max(x, 1e-12))"

    @pytest.mark.unit
    def test_division_denominator_guarded(self) -> None:
        """Verifies: 1/x guards the denominator with a SIGN-PRESERVING near-zero floor.
        AC3: division denominators guarded (Gate-B Finding 1 — a sign-losing abs
        floor would flip the sign of a/b for a runtime-negative denominator).
        Passes when: the denominator is clamped to +/-1e-12 keeping its sign
        (a no-op for |x| >= 1e-12)."""
        x = sp.Symbol("x")
        emitted = lower_expression(1 / x).returns[0]
        assert emitted == "1/ti.select(x >= 0, ti.max(x, 1e-12), ti.min(x, -1e-12))"
        # The naive sign-losing abs-floor form must NOT be used.
        assert "ti.abs(x)" not in emitted

    @pytest.mark.unit
    def test_golden_swift_voce_guard_structure(self) -> None:
        """Verifies: lowering the SwiftVoce R expression reproduces Cycle 0's guard structure.
        AC4: golden test against hand-written swift_voce.py get_R (string-pattern match).
        AC5: the deliberately-unguardable exp stays bare; the Swift pow bases get floored.
        Passes when: the generated guards match the hand-authored ones in swift_voce.py.

        Reference patterns transcribed from swift_voce.py get_R (NumerixWeave, NOT read
        at test time — R3): base = ti.max(peeq + self.p0, 1e-12); p0_base = ti.max(self.p0,
        1e-12); ti.pow(base, self.n); ti.pow(p0_base, self.n); ti.exp(-self.b*peeq) bare."""
        sigma0, Qsat, b, peeq, K, p0, n = sp.symbols("sigma0 Qsat b peeq K p0 n")
        R = sigma0 + Qsat * (1 - sp.exp(-b * peeq)) + K * ((peeq + p0) ** n - p0**n)

        emitted = lower_expression(R).returns[0]

        # Swift pow bases floored via ti.pow (the safe pattern).
        assert "ti.pow(ti.max(p0 + peeq, 1e-12), n)" in emitted
        assert "ti.pow(ti.max(p0, 1e-12), n)" in emitted
        # exp is UNGUARDED (the #1 risk) — bare ti.exp, no ti.max on its arg.
        assert "ti.exp(-b*peeq)" in emitted
        assert "ti.max(-b*peeq, 1e-12)" not in emitted
        # No un-guarded symbolic pow leaked through.
        assert "peeq)**n" not in emitted
        assert "p0**n" not in emitted
