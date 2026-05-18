"""LaTeX-math frontend wrapping the ``nrpylatex`` parser.

post_recovery_plan Phase 4 (P4-1) wires ``nrpylatex`` (already declared in
pyproject.toml) into the frontend layer so ``$...$`` math blocks in
LaTeX source can flow into the symbolic stage.

Supported subset (nrpylatex 1.4.0)
----------------------------------
This module intentionally exposes the **import-chain plumbing** for a
constrained subset of LaTeX-math; broader coverage is gated by the
underlying ``nrpylatex`` grammar. Concretely, ``parse_math`` accepts
inputs that ``nrpylatex.parse_latex`` accepts, which today means:

- Declarations use ``% declare`` comments at the top of the input.
  **Tensor rank is encoded via a U/D suffix in the symbol name itself**
  (``FUU`` declares a rank-2 tensor accessible in math via ``F^{ij}``;
  ``hDD`` declares ``h_{ij}``)::

      % declare FUU --dim 3            # rank-2, both indices upper
      % declare AUU --dim 3            # rank-2, both indices upper
      % declare \\mu \\lambda --const   # rank-0 constants
      A^{i j} = F^{i j}                # supported: balanced free indices

- Indexed expressions must obey strict Einstein summation: every free
  index appearing on the LHS must appear (with the same
  upper / lower placement) on the RHS, and every contracted index must
  appear exactly twice. ``nrpylatex`` raises ``GeneratorError`` on
  imbalanced expressions; ``parse_math`` re-raises as
  :class:`MathParseError` with a Phase-4 pointer.

- Bound (contracted) indices must connect tensors of complementary
  position (one upper, one lower). Forms such as ``F^{kk}`` (two upper
  indices on a non-symmetric tensor) raise ``GeneratorError`` — declare
  the corresponding ``FDD`` partner and use ``F^{ij} F_{ij}`` instead.

- Implicit multiplication only — explicit ``*`` is rejected by the
  scanner. Use ``\\mu F^{ij}`` instead of ``\\mu * F^{ij}``.

- Functions must use brace-grouped arguments::

      \\log{x}     # accepted
      \\log(x)     # rejected by scanner

- Functions ``\\det``, ``\\sin``, etc. that require sympy intrinsics not
  registered with nrpylatex 1.4.0's parser raise ``SympifyError``;
  these are caught and re-raised as :class:`MathParseError` Phase-4 to
  signal the deferred extension surface.

Index convention enforcement (07-CONVENTIONS)
---------------------------------------------
``nrpylatex`` does not distinguish *spatial* from *material* index
roles — both ``i`` and ``I`` are treated as literal symbol characters.
mechdsl's convention (lowercase ``i,j,k,l`` = spatial; uppercase
``I,J,K,L`` = material; mixed ``F_{iI}`` = two-point) is enforced
**post-parse** by :func:`enforce_index_convention`, which tags each
``IndexedSymbol``'s indices by case and raises if a tensor mixes
spatial and material indices on the same axis.

Errors
------
Every failure path in this module raises :class:`MathParseError` with
a message that includes the literal phrase
``"post_recovery_plan Phase 4"`` so the bridge surface is
traceable from the failure mode alone.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import nrpylatex
from sympy import SympifyError

_SPATIAL_INDEX_RE = re.compile(r"^[ijkl]$")
_MATERIAL_INDEX_RE = re.compile(r"^[IJKL]$")


class MathParseError(RuntimeError):
    """Raised when nrpylatex cannot parse a math block, when the
    declared subset is exceeded, or when the post-parse index
    convention check fails. Always carries the phrase
    ``post_recovery_plan Phase 4`` so the failure surface is
    traceable.
    """


@dataclass(frozen=True)
class IndexClassification:
    """Per-tensor classification of indices into spatial / material /
    other (digits, repeats, contracted dummies). Built by
    :func:`enforce_index_convention` from the symbol's U/D suffix and
    the literal index letters used in the source LaTeX.
    """

    name: str
    suffix: str  # e.g. "UU", "UD" — from nrpylatex IndexedSymbol
    spatial_axes: tuple[int, ...] = ()
    material_axes: tuple[int, ...] = ()
    other_axes: tuple[int, ...] = ()


@dataclass
class MathParseResult:
    """Output of :func:`parse_math`. ``tensors`` maps the declared
    symbol names to ``nrpylatex.IndexedSymbol`` instances. ``returned``
    is the value ``parse_latex`` returned (typically a tuple of names).
    ``classifications`` is the per-tensor index classification produced
    by :func:`enforce_index_convention`.
    """

    tensors: dict[str, Any]
    returned: Any
    classifications: dict[str, IndexClassification] = field(default_factory=dict)


def _wrap_nrpylatex_error(exc: BaseException) -> MathParseError:
    return MathParseError(
        f"nrpylatex {type(exc).__name__}: {exc}. "
        "Unsupported nrpylatex node — see post_recovery_plan Phase 4 "
        "(packages/mechdsl-core/src/mechdsl/frontend/math_parser.py "
        "supported-subset docstring) for the accepted grammar."
    )


def parse_math(latex_block: str) -> MathParseResult:
    """Parse ``latex_block`` via ``nrpylatex.parse_latex`` and return a
    :class:`MathParseResult`. The nrpylatex global parser namespace is
    reset before each call to keep parses hermetic.

    Raises
    ------
    MathParseError
        For any nrpylatex parser/scanner/generator error, with the
        Phase-4 pointer in the message.
    """
    if not isinstance(latex_block, str):
        raise MathParseError("parse_math requires a str — post_recovery_plan Phase 4.")

    try:
        returned = nrpylatex.parse_latex(latex_block, reset=True)
    except SympifyError as exc:
        raise _wrap_nrpylatex_error(exc) from exc
    except (
        nrpylatex.ParserError,
        nrpylatex.ScannerError,
        nrpylatex.GeneratorError,
        nrpylatex.NamespaceError,
        nrpylatex.IndexedSymbolError,
        nrpylatex.NRPyLaTeXError,
    ) as exc:
        raise _wrap_nrpylatex_error(exc) from exc
    except Exception as exc:
        raise _wrap_nrpylatex_error(exc) from exc

    tensors = dict(nrpylatex.Parser._namespace)
    classifications = enforce_index_convention(latex_block, tensors)

    return MathParseResult(tensors=tensors, returned=returned, classifications=classifications)


def enforce_index_convention(
    latex_block: str, tensors: dict[str, Any]
) -> dict[str, IndexClassification]:
    """Inspect each declared tensor's appearance in ``latex_block`` and
    classify its index letters into spatial / material / other per
    07-CONVENTIONS.md.

    The check runs **after** parsing, so it cannot reject a tensor at
    parse time — instead it raises :class:`MathParseError` if a single
    tensor is observed with both spatial and material letters on the
    same axis (e.g. ``F^{ij}`` and ``F^{iI}`` in the same block, with
    ``F`` declared once at rank 2). In practice this catches accidental
    mixing of the two regimes.

    Returns a per-symbol :class:`IndexClassification`.
    """

    out: dict[str, IndexClassification] = {}
    for name, sym in tensors.items():
        rank = getattr(sym, "rank", 0) or 0
        if rank == 0:
            out[name] = IndexClassification(name=name, suffix="")
            continue

        # Collect every (axis, letter) pair observed in the source for
        # this symbol, e.g. F^{iI} → [(0, 'i'), (1, 'I')]. nrpylatex's
        # namespace key encodes rank as a trailing U/D suffix (FUU,
        # ADD, gUD), but the literal LaTeX source uses the bare name
        # ("F", "A", "g") — strip the suffix for the source lookup.
        source_name = re.sub(r"[UD]+$", "", name) or name
        per_axis: list[set[str]] = [set() for _ in range(rank)]
        for match in re.finditer(rf"{re.escape(source_name)}[_^]?\{{([^}}]+)\}}", latex_block):
            indices = match.group(1).strip()
            indices = re.sub(r"\s+", "", indices)
            if len(indices) != rank:
                continue
            for axis, ch in enumerate(indices):
                per_axis[axis].add(ch)

        spatial_axes: list[int] = []
        material_axes: list[int] = []
        other_axes: list[int] = []
        for axis, letters in enumerate(per_axis):
            kinds = {
                "spatial"
                if _SPATIAL_INDEX_RE.match(c)
                else "material"
                if _MATERIAL_INDEX_RE.match(c)
                else "other"
                for c in letters
            }
            if "spatial" in kinds and "material" in kinds:
                raise MathParseError(
                    f"tensor {name!r} appears with both spatial and material "
                    f"indices on axis {axis} — mechdsl 07-CONVENTIONS forbids "
                    "this. post_recovery_plan Phase 4."
                )
            if "spatial" in kinds:
                spatial_axes.append(axis)
            elif "material" in kinds:
                material_axes.append(axis)
            else:
                other_axes.append(axis)

        # Suffix from nrpylatex IndexedSymbol if it exposes one.
        symbol_str = getattr(sym, "symbol", name)
        suffix_match = re.search(r"[UD]+$", str(symbol_str))
        suffix = suffix_match.group(0) if suffix_match else ""

        out[name] = IndexClassification(
            name=name,
            suffix=suffix,
            spatial_axes=tuple(spatial_axes),
            material_axes=tuple(material_axes),
            other_axes=tuple(other_axes),
        )
    return out


__all__ = [
    "IndexClassification",
    "MathParseError",
    "MathParseResult",
    "enforce_index_convention",
    "parse_math",
]
