"""Layer 4b — Einsum optimizer and JIT budget counter.

Uses *opt_einsum* to find optimal contraction paths for einsum expressions,
then classifies each contraction into a tier and checks compliance with the
JIT budget limits defined in ``dev/design_docs/07-CONVENTIONS.md`` section 9.

Budget hard limits
------------------
- 512 unrolled lines per ``@ti.func``
- 2000 total unrolled lines per ``@ti.kernel``
- 5000 absolute ceiling (never exceeded)

Tier classification
-------------------
- **Tier 1** (library ``@ti.func``): <= 64 estimated unrolled lines.
  Simple operations (matrix multiply, dot product) handled by pre-written
  routines in ``mechdsl.lib.tensor_ops``.
- **Tier 2** (generated ``@ti.func``): <= 512 estimated unrolled lines.
  Code-generated ``ti.static`` loops that fit within the per-function budget.
- **Tier 3** (fallback): > 512 estimated unrolled lines.
  Must be restructured (split sub-functions or runtime-loop outer indices).
"""

from __future__ import annotations

import os
import warnings
from dataclasses import dataclass
from enum import IntEnum

import opt_einsum

# Family classification is a realisation decision orthogonal to the
# tier (scheduling) decision. We import the enum + classifier here so that
# every ContractionResult carries both axes.
from mechdsl.codegen.family_registry import (  # re-exported for convenience
    FAMILY_EMITTERS_ENABLED,
    Family,
    classify_einsum_string,
)

__all__ = [
    "FAMILY_EMITTERS_ENABLED",
    "MAX_LINES_ABSOLUTE",
    "MAX_LINES_TI_FUNC",
    "MAX_LINES_TI_KERNEL",
    "BudgetExceededError",
    "ContractionResult",
    "Family",
    "Tier",
    "check_absolute_budget",
    "check_kernel_budget",
    "classify_einsum_string",
    "classify_tier",
    "estimate_unrolled_lines",
    "family_emitters_enabled",
    "optimize_all",
    "optimize_contraction",
]

# ---------------------------------------------------------------------------
# Constants — JIT budget limits from 07-CONVENTIONS.md section 9
# ---------------------------------------------------------------------------

MAX_LINES_TI_FUNC = 512
MAX_LINES_TI_KERNEL = 2000
MAX_LINES_ABSOLUTE = 5000

# Tier 1 threshold — simple enough for a library @ti.func
_TIER_1_THRESHOLD = 64


class Tier(IntEnum):
    """Contraction tier classification."""

    TIER_1 = 1  # Library @ti.func (pre-written, trusted)
    TIER_2 = 2  # Generated @ti.func (code-generated, verified)
    TIER_3 = 3  # Fallback (restructured to fit budget)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class BudgetExceededError(Exception):
    """Raised when the absolute contraction budget ceiling is exceeded."""


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ContractionResult:
    """Result of optimizing a single einsum contraction.

    Attributes:
        einsum_string: The einsum subscript notation (e.g. ``"ij,jk->ik"``).
        contraction_path: Pairwise contraction order from *opt_einsum*.
        estimated_flops: Estimated floating-point operations.
        estimated_lines: Estimated number of unrolled source lines.
        tier: Tier classification (1, 2, or 3) — the *scheduling* decision.
        within_budget: Whether this contraction fits within ``@ti.func`` budget.
        budget_detail: Human-readable budget summary.
        family: :class:`Family` classification — the *realisation* decision
            (which per-backend emitter owns this contraction). Orthogonal to
            ``tier``. Added in P9-2. Defaults to :attr:`Family.FALLBACK` so
            hand-built ``ContractionResult`` instances (e.g. in unit tests
            that exercise the budget path) remain valid without having to
            thread a classification through every construction site.
    """

    einsum_string: str
    contraction_path: list[tuple[int, ...]]
    estimated_flops: float
    estimated_lines: int
    tier: Tier
    within_budget: bool
    budget_detail: str = ""
    family: Family = Family.FALLBACK


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_einsum_indices(
    einsum_string: str,
) -> tuple[list[str], str]:
    """Parse einsum string into input subscripts and output subscript.

    Returns:
        (input_subscript_list, output_subscript)
        e.g. ``"ij,jk->ik"`` -> ``(["ij", "jk"], "ik")``
    """
    if "->" not in einsum_string:
        raise ValueError(f"einsum_string must contain '->': got {einsum_string!r}")
    lhs, rhs = einsum_string.split("->", maxsplit=1)
    inputs = lhs.split(",")
    return inputs, rhs


def _build_index_sizes(
    input_subscripts: list[str],
    operand_shapes: list[tuple[int, ...]],
) -> dict[str, int]:
    """Map each index letter to its dimension size."""
    sizes: dict[str, int] = {}
    for subscript, shape in zip(input_subscripts, operand_shapes, strict=True):
        for idx_char, dim in zip(subscript, shape, strict=True):
            if idx_char in sizes:
                if sizes[idx_char] != dim:
                    raise ValueError(
                        f"Inconsistent sizes for index '{idx_char}': {sizes[idx_char]} vs {dim}"
                    )
            else:
                sizes[idx_char] = dim
    return sizes


# ---------------------------------------------------------------------------
# Line estimation
# ---------------------------------------------------------------------------


def estimate_unrolled_lines(
    einsum_string: str,
    operand_shapes: list[tuple[int, ...]],
    contraction_path: list[tuple[int, ...]],
) -> int:
    """Estimate the number of unrolled lines for a contraction.

    For MVP, use a conservative heuristic:

    - Physics indices (range <= 6) are unrolled via ``ti.static`` and
      contribute multiplicatively to the line count.
    - Mesh indices (range > 6) become runtime loops and contribute a
      constant overhead (1 line each for the loop header).

    For each pairwise contraction step in the path we compute::

        step_lines = product(all_physics_dims_involved)

    The total is the sum across all steps, plus a small constant for
    loop headers and assignments.  This deliberately overestimates
    rather than underestimates.
    """
    input_subscripts, output_subscript = _parse_einsum_indices(einsum_string)
    index_sizes = _build_index_sizes(input_subscripts, operand_shapes)

    if not index_sizes:
        return 1  # scalar contraction

    # Collect all unique index characters and their sizes
    all_indices: set[str] = set()
    for sub in input_subscripts:
        all_indices.update(sub)
    all_indices.update(output_subscript)

    # Separate physics (small, unrolled) vs mesh (large, runtime) indices
    physics_indices = {c for c in all_indices if index_sizes.get(c, 1) <= 6}
    mesh_indices = all_indices - physics_indices

    # For each step in the contraction path, estimate unrolled lines.
    # We simulate the contraction by tracking which operands remain.
    current_operands = list(input_subscripts)

    total_lines = 0
    for pair in contraction_path:
        # Indices appearing in the operands being contracted
        involved_indices: set[str] = set()
        for idx in pair:
            if idx < len(current_operands):
                involved_indices.update(current_operands[idx])

        # Physics indices in this step are unrolled
        step_physics = involved_indices & physics_indices
        physics_product = 1
        for c in step_physics:
            physics_product *= index_sizes.get(c, 1)

        # Each unrolled iteration produces ~1 assignment + 1 multiply-add
        # Use factor of 2 for conservatism (assignment line + accumulation)
        step_lines = physics_product * 2

        # Mesh indices add loop headers (1 line each)
        step_mesh = involved_indices & mesh_indices
        step_lines += len(step_mesh)

        total_lines += step_lines

        remaining_indices: set[str] = set()
        for i, op in enumerate(current_operands):
            if i not in pair:
                remaining_indices.update(op)
        # The result of this step has the union of involved indices minus
        # summed-out indices, but for estimation we keep it simple.
        contracted = list(pair)
        contracted.sort(reverse=True)
        new_operands = [op for i, op in enumerate(current_operands) if i not in pair]
        # Result subscript: indices that appear in output or in remaining operands
        result_chars = ""
        for c in involved_indices:
            if c in output_subscript or any(c in op for op in new_operands):
                result_chars += c
        new_operands.append(result_chars)
        current_operands = new_operands

    # If no path steps (e.g. single operand, no contraction), estimate from
    # the output shape alone.
    if total_lines == 0:
        output_physics = {c for c in output_subscript if c in physics_indices}
        product = 1
        for c in output_physics:
            product *= index_sizes.get(c, 1)
        total_lines = max(product, 1)

    return total_lines


# ---------------------------------------------------------------------------
# Tier classification
# ---------------------------------------------------------------------------


def classify_tier(estimated_lines: int) -> Tier:
    """Classify contraction into a tier based on estimated lines.

    - Tier 1: <= 64 lines (simple enough for library ``@ti.func``).
    - Tier 2: <= 512 lines (generated ``@ti.func``, within budget).
    - Tier 3: > 512 lines (needs restructuring or fallback).
    """
    if estimated_lines <= _TIER_1_THRESHOLD:
        return Tier.TIER_1
    if estimated_lines <= MAX_LINES_TI_FUNC:
        return Tier.TIER_2
    return Tier.TIER_3


# ---------------------------------------------------------------------------
# Single contraction optimizer
# ---------------------------------------------------------------------------


def optimize_contraction(
    einsum_string: str,
    operand_shapes: list[tuple[int, ...]],
) -> ContractionResult:
    """Optimize a single einsum contraction.

    1. Use *opt_einsum* to find the optimal contraction path.
    2. Estimate unrolled line count.
    3. Classify tier.
    4. Check per-function budget compliance.

    Args:
        einsum_string: Einsum subscript notation (e.g. ``"ij,jk->ik"``).
        operand_shapes: Shape of each input operand.

    Returns:
        A :class:`ContractionResult` with path, flops, tier, and budget info.
    """
    # Build dummy arrays for opt_einsum (it only needs shapes)
    path_info = opt_einsum.contract_path(
        einsum_string,
        *[_shape_placeholder(s) for s in operand_shapes],
        optimize="optimal",
    )
    path: list[tuple[int, ...]] = path_info[0]
    # opt_einsum path_info[1] is a PathInfo object — extract FLOPS
    path_print = path_info[1]
    estimated_flops = _extract_flops(path_print)

    estimated_lines = estimate_unrolled_lines(einsum_string, operand_shapes, path)
    tier = classify_tier(estimated_lines)
    within_budget = estimated_lines <= MAX_LINES_TI_FUNC

    budget_detail = f"{estimated_lines}/{MAX_LINES_TI_FUNC} lines for @ti.func"
    if not within_budget:
        budget_detail += " [OVER BUDGET — Tier 3 restructuring required]"

    # Attach the realisation-axis classification. Tier and family are
    # orthogonal (scheduling vs realisation); see 09-EINSUM-OPTIMISER.md §9.
    family = classify_einsum_string(einsum_string, operand_shapes)

    return ContractionResult(
        einsum_string=einsum_string,
        contraction_path=list(path),
        estimated_flops=estimated_flops,
        estimated_lines=estimated_lines,
        tier=tier,
        within_budget=within_budget,
        budget_detail=budget_detail,
        family=family,
    )


# ---------------------------------------------------------------------------
# Kernel / absolute budget checks
# ---------------------------------------------------------------------------


def check_kernel_budget(
    contractions: list[ContractionResult],
) -> tuple[bool, str]:
    """Check if a set of contractions fits within ``@ti.kernel`` budget.

    Returns:
        ``(within_budget, detail_message)`` where *within_budget* is ``True``
        when the total estimated lines across all contractions is
        <= :data:`MAX_LINES_TI_KERNEL`.
    """
    total = sum(c.estimated_lines for c in contractions)
    ok = total <= MAX_LINES_TI_KERNEL
    detail = f"{total}/{MAX_LINES_TI_KERNEL} total lines for @ti.kernel"
    if not ok:
        detail += " [OVER BUDGET]"
    return ok, detail


def check_absolute_budget(
    contractions: list[ContractionResult],
) -> tuple[bool, str]:
    """Check absolute ceiling.

    Returns:
        ``(within_budget, detail_message)`` where *within_budget* is ``True``
        when the total is <= :data:`MAX_LINES_ABSOLUTE`.
    """
    total = sum(c.estimated_lines for c in contractions)
    ok = total <= MAX_LINES_ABSOLUTE
    detail = f"{total}/{MAX_LINES_ABSOLUTE} total lines (absolute ceiling)"
    if not ok:
        detail += " [ABSOLUTE CEILING EXCEEDED]"
    return ok, detail


# ---------------------------------------------------------------------------
# Batch optimizer
# ---------------------------------------------------------------------------


def optimize_all(
    einsum_specs: list[tuple[str, list[tuple[int, ...]]]],
) -> list[ContractionResult]:
    """Optimize a batch of einsum contractions and check budgets.

    Args:
        einsum_specs: List of ``(einsum_string, operand_shapes)`` pairs.

    Returns:
        List of :class:`ContractionResult`, one per input spec.

    Raises:
        BudgetExceededError: If the absolute ceiling is exceeded.
    """
    results = [optimize_contraction(es, shapes) for es, shapes in einsum_specs]

    ok, detail = check_absolute_budget(results)
    if not ok:
        total = sum(r.estimated_lines for r in results)
        raise BudgetExceededError(
            f"Absolute ceiling exceeded: {total} lines > {MAX_LINES_ABSOLUTE} limit. {detail}"
        )

    return results


# ---------------------------------------------------------------------------
# Family-emitter feature flag
# ---------------------------------------------------------------------------


_FLAG_OFF_VALUES: frozenset[str] = frozenset({"0", "false", "no", "off"})


def family_emitters_enabled() -> bool:
    """Return ``True`` when backend printers should dispatch via family emitters.

    Resolution order:
    1. Environment variable ``MECHDSL_FAMILY_EMITTERS``. Values in
       ``{"0", "false", "no", "off"}`` (case-insensitive) force the legacy
       tier-only path. Any other non-empty value forces family dispatch.
    2. Module-level :data:`FAMILY_EMITTERS_ENABLED` (default ``True``).

    The env-var override exists so the P9-2 equivalence tests can exercise
    the legacy path in a subprocess without restarting the interpreter.
    """
    env = os.environ.get("MECHDSL_FAMILY_EMITTERS")
    if env is None:
        return FAMILY_EMITTERS_ENABLED
    value = env.strip().lower()
    if not value:
        return FAMILY_EMITTERS_ENABLED
    return value not in _FLAG_OFF_VALUES


# ---------------------------------------------------------------------------
# Internal utilities
# ---------------------------------------------------------------------------


def _shape_placeholder(shape: tuple[int, ...]):
    """Create a tiny object with the given shape for opt_einsum path finding.

    *opt_einsum.contract_path* only inspects ``.shape``, so we use a
    lightweight shim instead of allocating real arrays.
    """

    class _ShapeShim:
        """Minimal object that satisfies opt_einsum's shape inspection."""

        def __init__(self, s: tuple[int, ...]) -> None:
            self.shape = s

        @property
        def dtype(self):
            """Return float64 dtype tag for opt_einsum."""
            return "float64"

    return _ShapeShim(shape)


def _extract_flops(path_print) -> float:
    """Extract FLOPS count from opt_einsum's PathInfo object.

    *opt_einsum* returns a ``PathInfo`` object as the second element of
    ``contract_path``.  We parse the string representation to extract the
    total FLOPS, falling back to 0.0 if parsing fails.
    """
    # opt_einsum.contract_path returns (path, PathInfo)
    # PathInfo has an `opt_cost` attribute in recent versions.
    if hasattr(path_print, "opt_cost"):
        cost = path_print.opt_cost
        if isinstance(cost, (int, float)):
            return float(cost)

    # Fallback: parse the string representation
    info_str = str(path_print)
    # Look for "Optimized FLOP count:" or "FLOP count:" lines
    for line in info_str.splitlines():
        lower = line.lower()
        if "flop" in lower and ":" in lower:
            # Try to extract the numeric part after the last colon
            after_colon = line.rsplit(":", maxsplit=1)[-1].strip()
            try:
                # Handle scientific notation like "1.620e+03"
                return float(after_colon.replace(",", ""))
            except ValueError:
                continue

    # Last resort: estimate from string "Total FLOP count" in naive_cost attr
    if hasattr(path_print, "naive_cost"):
        try:
            return float(path_print.naive_cost)
        except (ValueError, TypeError):
            pass

    warnings.warn(
        "Could not extract FLOPS from opt_einsum PathInfo. Reporting -1.0 as sentinel.",
        RuntimeWarning,
        stacklevel=2,
    )
    return -1.0
