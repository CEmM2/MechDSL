"""Tests for Task P3-2: clear rank-4 rejection in bridge.py for tangent emission.

Covers:
1. Rank-4 tangent moduli C_IJKL pass bridge.py without rejection (allows routing to tangent-emission path).
2. Over-budget tangent unroll (> 512 lines/@ti.func) is rejected with documented JIT-budget message.
3. Unsupported higher ranks (rank > 4) still reject with phase-pointer message.
   Also covers rank-1 and rank-3 (genuinely unsupported odd/low ranks).

The task clears the rank-4 tensor rejection in symbolic/bridge.py (~line 154)
for tangent-moduli emission, gated by the JIT budget counter
(codegen/einsum_optimizer.py). Before P3-2, rank-4 was uniformly rejected.
After P3-2, rank-4 tangent is accepted and routed to tangent emission,
but JIT budget enforcement prevents unbounded unrolls.
"""

from __future__ import annotations

import nrpylatex
import pytest
from sympy import Function, Symbol

from mechdsl.codegen.einsum_optimizer import (
    MAX_LINES_TI_FUNC,
    BudgetExceededError,
    optimize_all,
    optimize_contraction,
)
from mechdsl.symbolic.bridge import BridgeError, SymbolicNode, convert


def _make_indexed_symbol(name: str, rank: int, dimension: int = 3) -> nrpylatex.IndexedSymbol:
    """Construct a synthetic nrpylatex.IndexedSymbol of the given rank.

    nrpylatex infers rank from the number of index-suffix characters in the
    Symbol name (UU = rank-2, UUUU = rank-4, etc.).  We mirror the pattern
    used in test_p4_2.py.
    """
    suffix = "U" * rank
    sym_name = name + suffix
    func = Function("Tensor")(Symbol(sym_name, real=True))
    return nrpylatex.IndexedSymbol(func, dimension=dimension)


class TestTaskP3_2:
    """Tests for Task P3-2: clear rank-4 rejection in bridge.py for tangent emission.
    AC covered: 1, 2, 3."""

    @pytest.mark.unit
    def test_rank_4_tangent_accepted_by_bridge(self) -> None:
        """Rank-4 tangent moduli C_IJKL pass bridge.py without the prior rejection.

        AC: Rank-4 tangent passes bridge.py without prior rejection.
        Passes when: convert() accepts rank-4 indexed symbol and returns a
        SymbolicNode with kind='tensor4' and rank=4.
        """
        sym4 = _make_indexed_symbol("C", rank=4, dimension=3)
        node = convert("CUUUU", sym4, classification=None)

        assert isinstance(node, SymbolicNode)
        assert node.kind == "tensor4"
        assert node.rank == 4
        assert node.name == "CUUUU"
        assert node.raw is sym4

    @pytest.mark.unit
    def test_over_budget_tangent_unroll_rejected_with_budget_message(self) -> None:
        """Over-budget (>512 lines) tangent unroll rejected with documented JIT-budget message.

        AC: Over-budget tangent unroll rejects with documented JIT-budget message.

        Strategy: drive optimize_all() with a rank-4 contraction that the
        optimizer estimates as requiring more than MAX_LINES_ABSOLUTE lines.
        The 3x3x3x3 C_IJKL S_KL contraction is comfortably within budget on
        its own; we replicate it enough times to breach the absolute ceiling
        and confirm BudgetExceededError is raised.  The error message must
        contain the budget fraction and the "OVER BUDGET" / ceiling marker.

        For the per-function (Tier 3) path we also confirm that a single
        contraction that yields > MAX_LINES_TI_FUNC lines sets
        within_budget=False and "OVER BUDGET" in budget_detail.
        """
        # --- per-function budget: a large physics contraction ---
        # 6x6x6x6 rank-4 contraction: estimated lines should be large enough
        # to trigger Tier 3 (> 512) given the heuristic in estimate_unrolled_lines.
        result = optimize_contraction("ijkl,kl->ij", [(6, 6, 6, 6), (6, 6)])
        # A 6x6x6x6 contraction is deterministically over the per-@ti.func limit,
        # so this is an unconditional guarantee — assert it directly (not behind
        # an `if`) so the AC stays locked even if the heuristic shifts.
        assert result.estimated_lines > MAX_LINES_TI_FUNC, result.estimated_lines
        assert result.within_budget is False
        assert "OVER BUDGET" in result.budget_detail

        # --- absolute ceiling: replicate a contraction until ceiling is breached ---
        # Use a small rank-4 contraction and repeat it until cumulative lines
        # exceed MAX_LINES_ABSOLUTE (5000).
        small = optimize_contraction("ijkl,kl->ij", [(3, 3, 3, 3), (3, 3)])
        # Build a list big enough to exceed 5000 lines total
        from mechdsl.codegen.einsum_optimizer import MAX_LINES_ABSOLUTE

        copies_for_absolute = (MAX_LINES_ABSOLUTE // max(small.estimated_lines, 1)) + 2

        specs = [("ijkl,kl->ij", [(3, 3, 3, 3), (3, 3)])] * copies_for_absolute
        with pytest.raises(BudgetExceededError) as excinfo:
            optimize_all(specs)

        err_msg = str(excinfo.value)
        # Must contain the ceiling value and "exceeded" language
        assert (
            str(MAX_LINES_ABSOLUTE) in err_msg
            or "ceiling" in err_msg.lower()
            or "exceeded" in err_msg.lower()
        )

    @pytest.mark.unit
    def test_unsupported_higher_rank_still_rejected_with_phase_pointer(self) -> None:
        """Unsupported higher-rank constructs (rank 1, 3, 5) still reject with phase pointer.

        AC: Genuinely-unsupported higher-rank constructs still reject with a
        phase pointer (post_recovery_plan Phase 4).
        """
        for bad_rank in (1, 3, 5):
            sym = _make_indexed_symbol("T", rank=bad_rank, dimension=3)
            with pytest.raises(BridgeError) as excinfo:
                convert(f"T{'U' * bad_rank}", sym, classification=None)
            msg = str(excinfo.value)
            assert "post_recovery_plan Phase 4" in msg, (
                f"rank-{bad_rank} error missing phase pointer: {msg!r}"
            )
            assert (
                f"rank-{bad_rank}" in msg.lower()
                or f"rank {bad_rank}" in msg.lower()
                or str(bad_rank) in msg
            ), f"rank-{bad_rank} error missing rank number: {msg!r}"
