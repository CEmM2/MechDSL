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
================  ============  =========================================

Anything else raises :class:`BridgeError` with a Phase-4 pointer.

The bridge does **not** mutate or extend any existing symbolic type;
it only constructs new dataclass nodes that downstream code can reason
about.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import nrpylatex

from mechdsl.frontend.math_parser import IndexClassification


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

    raise BridgeError(
        f"convert: rank-{rank} tensor {name!r} not supported. The bridge "
        "currently maps rank-0 (constant or scalar) and rank-2 tensors. "
        "Higher ranks (e.g. rank-4 tangent moduli) are deferred — "
        "post_recovery_plan Phase 4."
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


__all__ = [
    "BridgeError",
    "SymbolicNode",
    "convert",
    "convert_namespace",
]
