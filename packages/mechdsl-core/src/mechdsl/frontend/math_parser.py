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
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterable

import nrpylatex
from sympy import SympifyError

_SPATIAL_INDEX_RE = re.compile(r"^[ijkl]$")
_MATERIAL_INDEX_RE = re.compile(r"^[IJKL]$")
_EQUATION_ENV_RE = re.compile(
    r"\\begin\{equation\*?\}(?P<body>.*?)\\end\{equation\*?\}",
    re.DOTALL,
)
_UNSUPPORTED_FUNCTIONS = {"sin", "cos", "tan", "exp", "sinh", "cosh"}
_SPATIAL_TENSORS = {"sigma", "tau", "b", "e", "L"}
_MATERIAL_TENSORS = {"C", "E", "S"}


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


@dataclass(frozen=True)
class IndexedOccurrence:
    """One indexed symbol occurrence observed in preserved equation source."""

    symbol: str
    indices: tuple[str, ...]
    source: str


@dataclass(frozen=True)
class EquationSemantics:
    """Expression-preserving equation record produced before lowering.

    ``free_indices`` are the free indices of the right-hand side. For a
    well-formed assignment these equal the LHS free indices —
    :func:`_free_and_contracted_indices` raises if any RHS term's free set
    diverges from the LHS, so the two are guaranteed identical by the time
    this record is constructed.
    """

    lhs: str
    rhs: str
    free_indices: tuple[str, ...]
    contracted_indices: tuple[str, ...]
    source_line: int
    source: str
    role: str | None = None
    lhs_occurrences: tuple[IndexedOccurrence, ...] = ()
    rhs_occurrences: tuple[IndexedOccurrence, ...] = ()


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
    equations: tuple[EquationSemantics, ...] = ()


def _wrap_nrpylatex_error(exc: BaseException) -> MathParseError:
    return MathParseError(
        f"nrpylatex {type(exc).__name__}: {exc}. "
        "Unsupported nrpylatex node — see post_recovery_plan Phase 4 "
        "(packages/mechdsl-core/src/mechdsl/frontend/math_parser.py "
        "supported-subset docstring) for the accepted grammar."
    )


def _normalise_symbol(symbol: str) -> str:
    symbol = symbol.strip()
    if symbol.startswith("\\"):
        return symbol[1:]
    return symbol


def _compact_indices(raw: str) -> tuple[str, ...]:
    raw = re.sub(r"\\[{}, ]+", "", raw)
    return tuple(ch for ch in re.sub(r"\s+", "", raw) if ch.isalpha())


def _strip_latex_noise(source: str) -> str:
    source = re.sub(r"\\label\{[^}]+\}", "", source)
    source = source.replace("\\left", "").replace("\\right", "")
    return source.strip().rstrip("\\").strip()


def _extract_indexed_occurrences(expr: str) -> tuple[IndexedOccurrence, ...]:
    # Each subscript/superscript group accepts either a brace-enclosed index
    # list (``\sigma_{iI}``) or a single bare character (``\sigma_i``) — standard
    # LaTeX renders a lone trailing char as the index without braces, so the
    # bare form must not be silently treated as a scalar occurrence.
    pattern = re.compile(
        r"(?P<symbol>\\?[A-Za-z]+)"
        r"(?:\s*(?P<first>[_^])\s*(?:\{(?P<first_indices>[^}]+)\}|(?P<first_bare>[A-Za-z0-9])))"
        r"(?:\s*(?P<second>[_^])\s*(?:\{(?P<second_indices>[^}]+)\}|(?P<second_bare>[A-Za-z0-9])))?"
    )
    out: list[IndexedOccurrence] = []
    for match in pattern.finditer(expr):
        first_raw = match.group("first_indices") or match.group("first_bare")
        indices = list(_compact_indices(first_raw))
        second_raw = match.group("second_indices") or match.group("second_bare")
        if second_raw is not None:
            indices.extend(_compact_indices(second_raw))
        out.append(
            IndexedOccurrence(
                symbol=_normalise_symbol(match.group("symbol")),
                indices=tuple(indices),
                source=match.group(0),
            )
        )
    return tuple(out)


def _split_terms(expr: str) -> tuple[str, ...]:
    terms: list[str] = []
    depth = 0
    start = 0
    for pos, ch in enumerate(expr):
        if ch in "{(":
            depth += 1
        elif ch in "})" and depth > 0:
            depth -= 1
        elif ch in "+-" and depth == 0 and pos > start:
            terms.append(expr[start:pos].strip())
            start = pos + 1
    terms.append(expr[start:].strip())
    return tuple(term for term in terms if term)


def _index_role(index: str) -> str:
    if _SPATIAL_INDEX_RE.match(index):
        return "spatial"
    if _MATERIAL_INDEX_RE.match(index):
        return "material"
    return "other"


def _validate_occurrence_manifold(occurrence: IndexedOccurrence) -> None:
    roles = {_index_role(index) for index in occurrence.indices}
    symbol = occurrence.symbol
    if symbol in _SPATIAL_TENSORS and "material" in roles:
        raise MathParseError(
            f"tensor {occurrence.source!r} mixes a material index into spatial tensor "
            f"{symbol!r}; use a material stress/strain or an explicit two-point tensor. "
            "post_recovery_plan Phase 4."
        )
    if symbol in _MATERIAL_TENSORS and "spatial" in roles:
        raise MathParseError(
            f"tensor {occurrence.source!r} mixes a spatial index into material tensor "
            f"{symbol!r}; use F/P for two-point mappings per 07-CONVENTIONS. "
            "post_recovery_plan Phase 4."
        )


def _validate_supported_equation_source(source: str) -> None:
    commands = set(re.findall(r"\\([A-Za-z]+)", source))
    unsupported = sorted(commands & _UNSUPPORTED_FUNCTIONS)
    if unsupported:
        raise MathParseError(
            f"unsupported LaTeX function(s) {unsupported} in preserved equation "
            f"{source!r}. These are full-grammar phase work; post_recovery_plan Phase 4."
        )


def _free_and_contracted_indices(
    lhs_occurrences: Iterable[IndexedOccurrence],
    rhs_occurrences: Iterable[IndexedOccurrence],
    source: str,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    lhs_counts: dict[str, int] = {}
    for occurrence in lhs_occurrences:
        _validate_occurrence_manifold(occurrence)
        for index in occurrence.indices:
            lhs_counts[index] = lhs_counts.get(index, 0) + 1

    lhs_free = tuple(sorted(index for index, count in lhs_counts.items() if count == 1))
    contracted: set[str] = set()
    rhs_free_union: set[str] = set()
    expected_free = set(lhs_free)

    for term in _split_terms(source):
        term_occurrences = _extract_indexed_occurrences(term)
        term_counts: dict[str, int] = {}
        for occurrence in term_occurrences:
            _validate_occurrence_manifold(occurrence)
            for index in occurrence.indices:
                term_counts[index] = term_counts.get(index, 0) + 1

        for index, count in term_counts.items():
            if count == 1:
                rhs_free_union.add(index)
            elif count == 2:
                contracted.add(index)
            else:
                raise MathParseError(
                    f"index {index!r} appears {count} times in term {term!r}; "
                    "Einstein contractions must be pairwise before symbolic lowering. "
                    "post_recovery_plan Phase 4."
                )

        term_free = {index for index, count in term_counts.items() if count == 1}
        if term_occurrences and term_free != expected_free:
            raise MathParseError(
                f"free-index mismatch in equation {source!r}: LHS has "
                f"{sorted(expected_free)}, RHS term {term!r} has {sorted(term_free)}. "
                "post_recovery_plan Phase 4."
            )

    return tuple(sorted(rhs_free_union)), tuple(sorted(contracted))


def _classify_role(lhs: str, rhs: str, latex_block: str) -> str:
    # Directive keywords in the surrounding block are authoritative.
    lowered = latex_block.lower()
    matched: list[str] = []
    if "strain_energy" in lowered or "strain energy" in lowered:
        matched.append("strain_energy")
    if "yield" in lowered:
        matched.append("yield_function")
    if "weak_form" in lowered or "weak residual" in lowered:
        matched.append("weak_residual")
    if "stress" in lowered:
        matched.append("stress_measure")
    if len(matched) > 1:
        raise ValueError(
            f"Multiple conflicting mechanics directives in the same LaTeX block: "
            f"{', '.join(matched)}. Declare each role in a separate block."
        )
    if matched:
        return matched[0]

    # Fallback only when no directive is present: LHS-symbol heuristics.
    # Advisory — a downstream consumer that has directive context should
    # prefer it over a role inferred here from a user-chosen symbol name.
    match = re.match(r"\s*(\\?[A-Za-z]+)", lhs)
    lhs_symbol = _normalise_symbol(match.group(1)) if match else ""
    if lhs_symbol in {"Psi", "psi"}:
        return "strain_energy"
    if lhs_symbol in {"f", "Phi", "phi"}:
        return "yield_function"
    if lhs_symbol in {"R", "r"}:
        return "weak_residual"
    if lhs_symbol in {"S", "P", "sigma", "tau"}:
        return "stress_measure"
    if rhs:
        return "auxiliary_definition"
    return "unknown"


def extract_equations(latex_block: str) -> tuple[EquationSemantics, ...]:
    """Preserve assignment equations from source before nrpylatex lowering."""

    equations: list[EquationSemantics] = []
    consumed_spans: list[tuple[int, int]] = []
    for match in _EQUATION_ENV_RE.finditer(latex_block):
        consumed_spans.append(match.span())
        env_line = latex_block.count("\n", 0, match.start()) + 1
        body = _strip_latex_noise(match.group("body"))
        if "=" in body:
            equations.append(_build_equation(body, env_line, latex_block))

    for line_number, line in enumerate(latex_block.splitlines(), start=1):
        offset = sum(len(part) + 1 for part in latex_block.splitlines()[: line_number - 1])
        if any(start <= offset < end for start, end in consumed_spans):
            continue
        stripped = _strip_latex_noise(line)
        if not stripped or stripped.startswith("%") or "=" not in stripped:
            continue
        equations.append(_build_equation(stripped, line_number, latex_block))

    return tuple(equations)


def _build_equation(source: str, source_line: int, latex_block: str) -> EquationSemantics:
    _validate_supported_equation_source(source)
    lhs, rhs = (_strip_latex_noise(part) for part in source.split("=", 1))
    lhs_occurrences = _extract_indexed_occurrences(lhs)
    rhs_occurrences = _extract_indexed_occurrences(rhs)
    free_indices, contracted_indices = _free_and_contracted_indices(
        lhs_occurrences, rhs_occurrences, rhs
    )
    return EquationSemantics(
        lhs=lhs,
        rhs=rhs,
        free_indices=free_indices,
        contracted_indices=contracted_indices,
        source_line=source_line,
        source=source,
        role=_classify_role(lhs, rhs, latex_block),
        lhs_occurrences=lhs_occurrences,
        rhs_occurrences=rhs_occurrences,
    )


def _declaration_only_input(latex_block: str) -> str:
    return "\n".join(
        line.rstrip() for line in latex_block.splitlines() if line.lstrip().startswith("% declare")
    )


def _parse_with_nrpylatex(latex_block: str) -> Any:
    try:
        return nrpylatex.parse_latex(latex_block, reset=True)
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

    equations = extract_equations(latex_block)
    try:
        returned = _parse_with_nrpylatex(latex_block)
    except MathParseError:
        declarations = _declaration_only_input(latex_block)
        if not declarations or not equations:
            raise
        returned = _parse_with_nrpylatex(declarations)

    tensors = dict(nrpylatex.Parser._namespace)
    classifications = enforce_index_convention(latex_block, tensors)

    return MathParseResult(
        tensors=tensors,
        returned=returned,
        classifications=classifications,
        equations=equations,
    )


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
    "EquationSemantics",
    "IndexClassification",
    "IndexedOccurrence",
    "MathParseError",
    "MathParseResult",
    "enforce_index_convention",
    "extract_equations",
    "parse_math",
]
