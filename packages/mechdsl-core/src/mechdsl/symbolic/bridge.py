"""Adapter from ``nrpylatex`` AST output to mechdsl symbolic types.

post_recovery_plan Phase 4 (P4-2). The bridge sits between the
:mod:`mechdsl.frontend.math_parser` output and the existing symbolic
machinery in :mod:`mechdsl.symbolic`. It is the **only** module that
imports ``nrpylatex`` types beyond the parser wrapper.

Supported subset
----------------
``convert`` accepts the per-symbol entries produced by
``parse_math``. For each ``nrpylatex.IndexedSymbol`` it emits a
:class:`SymbolicNode` describing what the symbolic layer should treat
the entry as:

================  ============  =========================================
nrpylatex shape   ``kind``      Notes
================  ============  =========================================
rank-0 + Function('Constant')  ``constant``  Material parameters (μ, λ).
rank-0 (Symbol)   ``scalar``    Free scalars (e.g. J, trace contractions).
rank-2 (UU/DD)    ``tensor2``   Carries axis classification produced by
                                :func:`mechdsl.frontend.math_parser.enforce_index_convention`.
rank-4 (UUUU/…)  ``tensor4``   Tangent moduli C_IJKL. Accepted by the
                                bridge; emission is gated by the JIT
                                budget counter in
                                :mod:`mechdsl.codegen.einsum_optimizer`
                                (≤ 512 unrolled lines per ``@ti.func``).
                                Full Taichi emission is wired in P3-3.
================  ============  =========================================

Rank-1, rank-3, and rank > 4 raise :class:`BridgeError` with a
phase-pointer message.

The bridge does **not** mutate or extend any existing symbolic type;
it only constructs new dataclass nodes that downstream code can reason
about.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import nrpylatex

from mechdsl.frontend.math_parser import EquationSemantics, IndexClassification


class BridgeError(RuntimeError):
    """Raised when an nrpylatex namespace entry cannot be mapped onto
    a supported mechdsl symbolic node. Always carries the phrase
    ``post_recovery_plan Phase 4`` so the bridge surface is traceable.
    """


@dataclass(frozen=True)
class SymbolicNode:
    """Lightweight descriptor of a converted symbol.

    The bridge is intentionally read-only against
    :mod:`mechdsl.symbolic`: it carries the data downstream code needs
    without touching the existing ``kinematics``/``constitutive``/
    ``convected`` modules.
    """

    name: str
    kind: str
    rank: int
    suffix: str
    classification: IndexClassification | None
    raw: Any  # the underlying nrpylatex.IndexedSymbol (or sympy Constant Function)


@dataclass(frozen=True)
class SymbolicEquation:
    """Expression-preserving equation descriptor for downstream IR phases."""

    lhs: str
    rhs: str
    free_indices: tuple[str, ...]
    contracted_indices: tuple[str, ...]
    source_line: int
    role: str | None
    raw: EquationSemantics


def _is_constant(symbol: Any) -> bool:
    """Identify nrpylatex namespace entries that represent material
    constants. Two storage shapes appear in nrpylatex 1.4.0:

    1. A raw ``Function('Constant')(Symbol(name))`` instance (stored
       directly under the namespace key when ``--const`` is declared).
    2. An ``IndexedSymbol`` whose ``structure`` is the constant
       function call.
    """
    if hasattr(symbol, "func") and getattr(symbol.func, "__name__", "") == "Constant":
        return True
    structure = getattr(symbol, "structure", None)
    if structure is not None and hasattr(structure, "func"):
        return getattr(structure.func, "__name__", "") == "Constant"
    return False


def convert(
    name: str,
    indexed_symbol: Any,
    classification: IndexClassification | None = None,
) -> SymbolicNode:
    """Convert one nrpylatex namespace entry into a
    :class:`SymbolicNode`. ``classification`` should come from
    :func:`mechdsl.frontend.math_parser.enforce_index_convention`.

    Raises
    ------
    BridgeError
        For any nrpylatex node shape outside the supported subset.
    """
    # Constants may arrive as raw Function('Constant')(...) (rank-0,
    # not an IndexedSymbol). Handle them up front.
    if _is_constant(indexed_symbol):
        return SymbolicNode(
            name=name,
            kind="constant",
            rank=0,
            suffix=(classification.suffix if classification is not None else "") or "",
            classification=classification,
            raw=indexed_symbol,
        )

    if not isinstance(indexed_symbol, nrpylatex.IndexedSymbol):
        raise BridgeError(
            f"convert expected nrpylatex.IndexedSymbol or Constant for {name!r}, got "
            f"{type(indexed_symbol).__name__} — post_recovery_plan Phase 4."
        )

    rank = int(getattr(indexed_symbol, "rank", 0) or 0)
    suffix = (classification.suffix if classification is not None else "") or ""

    if rank == 0:
        return SymbolicNode(
            name=name,
            kind="scalar",
            rank=0,
            suffix=suffix,
            classification=classification,
            raw=indexed_symbol,
        )

    if rank == 2:
        return SymbolicNode(
            name=name,
            kind="tensor2",
            rank=2,
            suffix=suffix,
            classification=classification,
            raw=indexed_symbol,
        )

    if rank == 4:
        # Rank-4 tangent moduli C_IJKL are accepted by the bridge (P3-2).
        # JIT budget enforcement (≤ 512 unrolled lines per @ti.func) must be
        # applied before any unrolled Taichi emission — use
        # mechdsl.codegen.einsum_optimizer.optimize_contraction to gate emission.
        # Full Taichi emission for rank-4 nodes is wired in P3-3.
        return SymbolicNode(
            name=name,
            kind="tensor4",
            rank=4,
            suffix=suffix,
            classification=classification,
            raw=indexed_symbol,
        )

    raise BridgeError(
        f"convert: rank-{rank} tensor {name!r} is not supported. The bridge "
        "maps rank-0 (constant or scalar), rank-2 tensors, and rank-4 tangent "
        "moduli. Ranks 1, 3, and > 4 are not part of the mechdsl supported "
        "subset — post_recovery_plan Phase 4."
    )


def convert_namespace(
    tensors: dict[str, Any],
    classifications: dict[str, IndexClassification] | None = None,
) -> dict[str, SymbolicNode]:
    """Bulk variant of :func:`convert` over an entire ``parse_math``
    namespace.

    Returns a name → :class:`SymbolicNode` map; raises on first
    unsupported entry.
    """
    classifications = classifications or {}
    out: dict[str, SymbolicNode] = {}
    for name, sym in tensors.items():
        out[name] = convert(name, sym, classifications.get(name))
    return out


def convert_equation(equation: EquationSemantics) -> SymbolicEquation:
    """Convert one preserved parser equation into bridge-owned semantics."""
    if not isinstance(equation, EquationSemantics):
        raise BridgeError(
            f"convert_equation expected EquationSemantics, got "
            f"{type(equation).__name__}. Unsupported bridge node; "
            "full grammar lowering is deferred to post_recovery_plan Phase 4."
        )
    if not equation.lhs or not equation.rhs:
        raise BridgeError(
            "convert_equation requires assignment equations with both LHS and RHS. "
            "Full grammar relation nodes are deferred to post_recovery_plan Phase 4."
        )
    return SymbolicEquation(
        lhs=equation.lhs,
        rhs=equation.rhs,
        free_indices=equation.free_indices,
        contracted_indices=equation.contracted_indices,
        source_line=equation.source_line,
        role=equation.role,
        raw=equation,
    )


def convert_equations(equations: tuple[EquationSemantics, ...]) -> tuple[SymbolicEquation, ...]:
    """Bulk variant of :func:`convert_equation` for parser results."""
    return tuple(convert_equation(equation) for equation in equations)


__all__ = [
    "BridgeError",
    "SymbolicEquation",
    "SymbolicNode",
    "convert",
    "convert_equation",
    "convert_equations",
    "convert_namespace",
]
