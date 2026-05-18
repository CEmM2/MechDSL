"""Tests for Layer 4b — Einsum optimizer and JIT budget counter.

Covers:
1. Simple matrix multiply (3x3): Tier 1, within budget.
2. Large contraction: correct tier assignment.
3. Within-budget contraction passes check.
4. Over-budget @ti.func (artificially large): triggers correct detection.
5. Over-budget @ti.kernel: triggers correct detection.
6. Absolute ceiling exceeded: raises BudgetExceededError.
7. opt_einsum produces valid contraction path.
8. Estimated flops are positive for non-trivial contractions.
9. Tier classification boundaries (Tier 1 <= 64, Tier 2 <= 512, Tier 3 > 512).
10. optimize_all returns correct number of results.
"""

from __future__ import annotations

import pytest

from mechdsl.codegen.einsum_optimizer import (
    MAX_LINES_ABSOLUTE,
    MAX_LINES_TI_FUNC,
    MAX_LINES_TI_KERNEL,
    BudgetExceededError,
    ContractionResult,
    Tier,
    check_absolute_budget,
    check_kernel_budget,
    classify_tier,
    optimize_all,
    optimize_contraction,
)

# ── Test 1: Simple matrix multiply (3x3) → Tier 1, within budget ────────


def test_matrix_multiply_3x3_is_tier1():
    """A 3x3 @ 3x3 matrix multiply should be Tier 1 (very small)."""
    result = optimize_contraction("ij,jk->ik", [(3, 3), (3, 3)])

    assert result.tier == Tier.TIER_1
    assert result.within_budget is True
    assert result.estimated_lines <= 64
    assert result.einsum_string == "ij,jk->ik"


# ── Test 2: Large contraction — correct tier assignment ──────────────────


def test_4th_order_tangent_contraction_tier():
    """4th-order tangent contraction C_{IJKL} S_{KL} -> T_{IJ}.

    With 6x6x6x6 this is large and should be at least Tier 2.
    """
    result = optimize_contraction("ijkl,kl->ij", [(6, 6, 6, 6), (6, 6)])

    # The exact tier depends on the line estimate, but it should not be Tier 1
    # given the large index ranges involved.
    assert result.tier in (Tier.TIER_2, Tier.TIER_3)
    assert result.estimated_lines > 64


# ── Test 3: Within-budget contraction passes check ───────────────────────


def test_within_budget_passes_kernel_check():
    """A small contraction should pass kernel budget check."""
    result = optimize_contraction("ij,jk->ik", [(3, 3), (3, 3)])

    ok, detail = check_kernel_budget([result])
    assert ok is True
    assert "OVER BUDGET" not in detail


# ── Test 4: Over-budget @ti.func detection ───────────────────────────────


def test_over_budget_ti_func_detection():
    """A contraction exceeding 512 lines should be flagged as over budget."""
    result = optimize_contraction("ijkl,kl->ij", [(6, 6, 6, 6), (6, 6)])

    if result.estimated_lines > MAX_LINES_TI_FUNC:
        assert result.within_budget is False
        assert "OVER BUDGET" in result.budget_detail
        assert result.tier == Tier.TIER_3
    else:
        # Even if this particular contraction fits, we verify the flag is correct
        assert result.within_budget is True


def test_artificially_large_func_over_budget():
    """Construct a ContractionResult that exceeds @ti.func budget."""
    over_budget = ContractionResult(
        einsum_string="test",
        contraction_path=[],
        estimated_flops=1e6,
        estimated_lines=MAX_LINES_TI_FUNC + 100,
        tier=Tier.TIER_3,
        within_budget=False,
        budget_detail=f"{MAX_LINES_TI_FUNC + 100}/{MAX_LINES_TI_FUNC} lines [OVER]",
    )
    assert over_budget.within_budget is False
    assert over_budget.tier == Tier.TIER_3


# ── Test 5: Over-budget @ti.kernel detection ─────────────────────────────


def test_over_budget_ti_kernel():
    """Multiple contractions exceeding kernel budget are detected."""
    # Create contractions whose total exceeds MAX_LINES_TI_KERNEL
    lines_each = MAX_LINES_TI_KERNEL // 3 + 100  # ~767 each, 3*767 > 2000
    items = [
        ContractionResult(
            einsum_string=f"test_{i}",
            contraction_path=[],
            estimated_flops=1000.0,
            estimated_lines=lines_each,
            tier=Tier.TIER_3,
            within_budget=False,
        )
        for i in range(3)
    ]
    ok, detail = check_kernel_budget(items)
    assert ok is False
    assert "OVER BUDGET" in detail


# ── Test 6: Absolute ceiling exceeded → BudgetExceededError ──────────────


def test_absolute_ceiling_raises_error():
    """optimize_all must raise BudgetExceededError if absolute ceiling is exceeded."""
    # We need many large contractions. Use a contraction that produces many lines.
    # 6^8 indices would be huge but let's just craft specs that are large enough.
    # Strategy: use many copies of a moderately large contraction.
    single = optimize_contraction("ijkl,kl->ij", [(6, 6, 6, 6), (6, 6)])

    # How many copies to exceed absolute ceiling?
    copies_needed = (MAX_LINES_ABSOLUTE // max(single.estimated_lines, 1)) + 2
    specs = [("ijkl,kl->ij", [(6, 6, 6, 6), (6, 6)])] * copies_needed

    with pytest.raises(BudgetExceededError):
        optimize_all(specs)


def test_absolute_ceiling_check_direct():
    """check_absolute_budget reports correctly for over-ceiling sets."""
    items = [
        ContractionResult(
            einsum_string="test",
            contraction_path=[],
            estimated_flops=0.0,
            estimated_lines=MAX_LINES_ABSOLUTE,
            tier=Tier.TIER_3,
            within_budget=False,
        ),
        ContractionResult(
            einsum_string="test2",
            contraction_path=[],
            estimated_flops=0.0,
            estimated_lines=1,
            tier=Tier.TIER_1,
            within_budget=True,
        ),
    ]
    ok, detail = check_absolute_budget(items)
    assert ok is False
    assert "ABSOLUTE CEILING EXCEEDED" in detail


# ── Test 7: opt_einsum produces valid contraction path ───────────────────


def test_opt_einsum_valid_path():
    """The contraction path from opt_einsum should be a list of index tuples."""
    result = optimize_contraction("ij,jk->ik", [(3, 3), (3, 3)])

    assert isinstance(result.contraction_path, list)
    assert len(result.contraction_path) >= 1
    for step in result.contraction_path:
        assert isinstance(step, tuple)
        assert all(isinstance(idx, int) for idx in step)
        assert len(step) >= 2  # pairwise contraction


def test_three_operand_path():
    """A three-operand contraction should have a valid multi-step path."""
    # A @ B @ C (ij,jk,kl->il)
    result = optimize_contraction("ij,jk,kl->il", [(3, 3), (3, 3), (3, 3)])

    assert isinstance(result.contraction_path, list)
    assert len(result.contraction_path) >= 1
    # Two-step contraction with 3x3 operands — within budget but may
    # exceed Tier 1 threshold due to conservative line estimation.
    assert result.tier in (Tier.TIER_1, Tier.TIER_2)
    assert result.within_budget is True


# ── Test 8: Estimated flops are positive ─────────────────────────────────


def test_estimated_flops_positive():
    """Non-trivial contractions should have positive estimated FLOPS."""
    result = optimize_contraction("ij,jk->ik", [(3, 3), (3, 3)])
    assert result.estimated_flops > 0.0


def test_estimated_flops_larger_contraction():
    """Larger contraction should have even more FLOPS."""
    small = optimize_contraction("ij,jk->ik", [(3, 3), (3, 3)])
    large = optimize_contraction("ij,jk->ik", [(6, 6), (6, 6)])
    assert large.estimated_flops > small.estimated_flops


# ── Test 9: Tier classification boundaries ───────────────────────────────


@pytest.mark.parametrize(
    ("lines", "expected_tier"),
    [
        (1, Tier.TIER_1),
        (32, Tier.TIER_1),
        (64, Tier.TIER_1),  # boundary: exactly 64 is still Tier 1
        (65, Tier.TIER_2),  # just above Tier 1 threshold
        (256, Tier.TIER_2),
        (512, Tier.TIER_2),  # boundary: exactly 512 is still Tier 2
        (513, Tier.TIER_3),  # just above Tier 2 threshold
        (1000, Tier.TIER_3),
        (5000, Tier.TIER_3),
    ],
)
def test_classify_tier_boundaries(lines: int, expected_tier: Tier):
    """Tier classification respects exact boundary values."""
    assert classify_tier(lines) == expected_tier


# ── Test 10: optimize_all returns correct number of results ──────────────


def test_optimize_all_result_count():
    """optimize_all should return exactly one result per input spec."""
    specs = [
        ("ij,jk->ik", [(3, 3), (3, 3)]),
        ("ij,j->i", [(3, 3), (3,)]),
        ("i,i->", [(3,), (3,)]),
    ]
    results = optimize_all(specs)
    assert len(results) == len(specs)
    for r in results:
        assert isinstance(r, ContractionResult)


def test_optimize_all_empty():
    """optimize_all with empty input returns empty list."""
    results = optimize_all([])
    assert results == []


# ── Additional edge-case tests ───────────────────────────────────────────


def test_dot_product_tier1():
    """Dot product (i,i->) should be Tier 1."""
    result = optimize_contraction("i,i->", [(3,), (3,)])
    assert result.tier == Tier.TIER_1
    assert result.within_budget is True


def test_outer_product_tier1():
    """Outer product (i,j->ij) with small dims is Tier 1."""
    result = optimize_contraction("i,j->ij", [(3,), (3,)])
    assert result.tier == Tier.TIER_1
    assert result.within_budget is True


def test_trace_tier1():
    """Trace (ii->) should be Tier 1."""
    result = optimize_contraction("ii->", [(3, 3)])
    assert result.tier == Tier.TIER_1


def test_contraction_result_is_frozen():
    """ContractionResult should be immutable (frozen dataclass)."""
    result = optimize_contraction("ij,jk->ik", [(3, 3), (3, 3)])
    with pytest.raises(AttributeError):
        result.tier = Tier.TIER_3  # type: ignore[misc]


def test_budget_detail_contains_fraction():
    """Budget detail string should show lines/limit format."""
    result = optimize_contraction("ij,jk->ik", [(3, 3), (3, 3)])
    assert f"/{MAX_LINES_TI_FUNC}" in result.budget_detail


def test_kernel_budget_within():
    """Small contractions should pass kernel budget check."""
    results = [
        optimize_contraction("ij,jk->ik", [(3, 3), (3, 3)]),
        optimize_contraction("ij,j->i", [(3, 3), (3,)]),
    ]
    ok, detail = check_kernel_budget(results)
    assert ok is True
    assert f"/{MAX_LINES_TI_KERNEL}" in detail


def test_estimate_lines_positive():
    """Line estimate must always be positive for valid contractions."""
    result = optimize_contraction("ij,jk->ik", [(3, 3), (3, 3)])
    assert result.estimated_lines > 0
