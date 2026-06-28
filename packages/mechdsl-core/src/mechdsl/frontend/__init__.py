"""LaTeX parsing, % mechanics directives, two-point tensor index resolution.

Public entry points (in tier order — see ``README.md`` Support tiers and
``dev/plans/recovery_plan_latex_contract.md`` Phase 2 / R1):

**Canonical (MVP-stable)**

- :func:`mechdsl.compile_latex` — the LaTeX-source-driven façade. Prefer
  this for new code and documentation examples; it is the canonical entry
  point for the recovered contract.

**Secondary (preserved for testing and programmatic construction)**

- :func:`parse` — parse a LaTeX source string containing ``% mechanics``
  directives into a context dict. Used internally by ``compile_latex``;
  exposed for direct use when callers need the intermediate context dict.
- :func:`parse_file` — :func:`parse` for a file path.
- :func:`build_context` — programmatic construction of the same context
  dict ``parse`` returns. Useful for tests and embedding scenarios where
  no LaTeX source is available; not the canonical public-API path.
"""

from __future__ import annotations

import re
from typing import Any

from mechdsl.symbolic.convected import UnsupportedError

__all__ = [
    "FrontendSemanticError",
    "UnsupportedError",
    "build_context",
    "has_math_block",
    "parse",
    "parse_compile_context",
    "parse_file",
    "parse_with_math",
]


# post_recovery_plan Phase 4 (P4-3) — detect ``$...$`` math blocks in
# LaTeX source. The pattern uses non-greedy capture and disallows
# unescaped newlines so commented-out maths or stray dollar signs in
# verbatim blocks do not span lines.
_MATH_BLOCK_RE = re.compile(r"(?<!\\)\$([^$\n]+?)(?<!\\)\$")


def has_math_block(source: str) -> bool:
    """``True`` iff ``source`` contains at least one ``$...$`` math
    block. The math parser is invoked only when this is true
    (parse-when-needed guard, plan §Phase 4 lines 226–227).
    """
    return bool(_MATH_BLOCK_RE.search(source))


def _extract_math_blocks(source: str) -> list[str]:
    """Return every ``$...$`` block in ``source`` that is **not** on a
    ``%``-comment line. Comment lines may legitimately reference math
    syntax in prose (e.g. ``% the $...$ block below``); only inline
    math on non-comment lines is routed through the math parser.
    """
    blocks: list[str] = []
    for line in source.splitlines():
        if line.lstrip().startswith("%"):
            continue
        blocks.extend(_MATH_BLOCK_RE.findall(line))
    return blocks


def has_math_block_in_source(source: str) -> bool:
    """Strict variant of :func:`has_math_block` that ignores
    ``%``-comment lines (used internally by :func:`parse_with_math`)."""
    return bool(_extract_math_blocks(source))


def _has_actionable_math_context(source: str) -> bool:
    """Return true when ``compile_latex`` should interpret math blocks.

    Narrative LaTeX often contains governing-equation prose in ``$...$``.
    Those blocks are documentation unless paired with explicit mechanics
    math intent: NRPyLaTeX ``% declare`` lines or directives that bind
    equations into frontend semantics.
    """
    if not has_math_block_in_source(source):
        return False
    for line in source.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("% declare"):
            return True
        if not stripped.startswith("%"):
            continue
        body = stripped[1:].lstrip()
        if not body.startswith("mechanics"):
            continue
        tail = body[len("mechanics") :]
        if tail and not tail[0].isspace():
            continue
        parts = tail.split()
        if parts and parts[0] in {"constitutive", "weak_form"}:
            return True
    return False


class FrontendSemanticError(RuntimeError):
    """Raised when a math-aware frontend source cannot produce compile
    semantics before IR construction.

    This exception is intentionally frontend-owned so ``compile_latex``
    rejects unsupported math-bearing input before it reaches
    :meth:`ProblemIR.from_context` or backend codegen.
    """


def parse_with_math(source: str) -> dict[str, Any]:
    """Parse ``source`` through the directive parser and, when
    ``$...$`` math blocks are present, route them through
    :func:`mechdsl.frontend.math_parser.parse_math` and convert the
    nrpylatex namespace via
    :func:`mechdsl.symbolic.bridge.convert_namespace`.

    Directive-only inputs return exactly :func:`parse`'s output (no
    ``math`` key in the returned dict — math parser is not invoked).
    Math-bearing inputs return :func:`parse`'s output augmented with a
    ``math`` block::

        context["math"] = {
            "blocks": [<raw block text>, ...],
            "tensors": {<name>: SymbolicNode, ...},
            "namespace": {<name>: nrpylatex IndexedSymbol|Constant, ...},
            "classifications": {<name>: IndexClassification, ...},
            "equations": [
                {"lhs", "rhs", "role", "free_indices",
                 "contracted_indices", "source_line"},
                ...
            ],
        }

    The ``equations`` entry carries the per-equation semantics that
    :func:`mechdsl.frontend.math_parser.parse_math` extracts from each
    ``$...$`` block (fgram Phase 4 ``EquationSemantics``). Entries are
    JSON-primitive dicts so the bundle round-trips through
    :meth:`mechdsl.ir.mechanics_ir.ProblemIR.from_latex_semantics` into the
    serialized IR's ``latex_semantics`` record without re-parsing the source.
    """
    context = parse(source)
    if not has_math_block_in_source(source):
        return context

    # Lazy local imports — keeps the directive-only path off the math
    # parser dependency chain.
    from mechdsl.frontend.math_parser import parse_math
    from mechdsl.symbolic.bridge import convert_namespace

    blocks = _extract_math_blocks(source)
    # nrpylatex needs ``% declare`` directives in the same input as the
    # tensor expression they introduce. Pull every ``% declare`` line
    # out of the source (mechdsl's directive parser uses ``% mechanics``
    # — no namespace clash) and prepend them to each ``$...$`` block.
    declare_lines = [
        line.rstrip() for line in source.splitlines() if line.lstrip().startswith("% declare")
    ]
    declarations = "\n".join(declare_lines)

    all_tensors = {}
    all_classifications = {}
    all_equations: list[dict[str, Any]] = []
    for block in blocks:
        nrpy_input = (declarations + "\n" + block).strip() if declarations else block
        res = parse_math(nrpy_input)
        all_tensors.update(res.tensors)
        all_classifications.update(res.classifications)
        all_equations.extend(_equation_to_dict(eq) for eq in res.equations)

    context["math"] = {
        "blocks": blocks,
        "tensors": convert_namespace(all_tensors, all_classifications),
        "namespace": all_tensors,
        "classifications": all_classifications,
        # Per-equation semantics from the math parser (fgram P5-1). JSON-
        # primitive dicts so downstream IR construction reads real pipeline
        # output rather than a hand-built shape.
        "equations": all_equations,
    }
    return context


def _equation_to_dict(eq: Any) -> dict[str, Any]:
    """Serialize an ``EquationSemantics`` to a JSON-primitive dict.

    Only the fields :meth:`ProblemIR.from_latex_semantics` consumes (or that
    aid review/golden-diffing) are emitted. Kept local to the frontend so the
    math-parser dataclass stays an implementation detail of the math layer.
    """
    return {
        "lhs": eq.lhs,
        "rhs": eq.rhs,
        "role": eq.role,
        "free_indices": list(eq.free_indices),
        "contracted_indices": list(eq.contracted_indices),
        "source_line": eq.source_line,
    }


def parse_compile_context(source: str) -> dict[str, Any]:
    """Return the canonical frontend context for ``compile_latex``.

    Directive-only sources preserve :func:`parse`'s exact behaviour.
    Narrative math blocks in directive-only examples are treated as prose.
    Actionable math-bearing sources (``% declare`` or mechanics metadata
    that binds equations) must successfully produce the semantic
    ``context["math"]`` bundle here; unsupported actionable math is wrapped
    as a frontend-level failure so it cannot leak into IR construction or
    code generation.
    """
    math_bearing = _has_actionable_math_context(source)
    if not math_bearing:
        return parse(source)

    try:
        context = parse_with_math(source)
    except Exception as exc:
        from mechdsl.frontend.math_parser import MathParseError
        from mechdsl.symbolic.bridge import BridgeError

        if math_bearing and isinstance(exc, (MathParseError, BridgeError)):
            raise FrontendSemanticError(
                f"Unsupported math-bearing LaTeX source rejected before IR construction: {exc}"
            ) from exc
        raise

    if math_bearing and "math" not in context:
        raise FrontendSemanticError(
            "Math-bearing LaTeX source did not produce frontend math semantics "
            "before IR construction."
        )
    return context


def build_context(
    dim: int,
    cell_type: str,
    formulation: str,
    material_type: str,
    params: dict,
    boundaries: list,
    coord_system: str = "cartesian",
    fiber_data=None,
    fiber_families=None,
    hourglass_coef: float = 0.05,
    integration: str = "full",
    hourglass: str | None = None,
) -> dict:
    """Build and return a context dict representing a mechanics problem.

    This is the **secondary** programmatic entry point for Layer 1 (Frontend).
    The canonical public API is :func:`mechdsl.compile_latex`, which accepts
    a LaTeX source string and forwards through this function's machinery
    after parsing. ``build_context`` remains supported for tests and embedding
    scenarios that have no LaTeX source available — see ``README.md``
    Support tiers and ``dev/plans/recovery_plan_latex_contract.md`` Phase 2 (R1).

    It returns the same context dict that the LaTeX parser would produce.
    Validates that inputs fall within the MVP-supported subset.  ProblemIR
    construction is Layer 3's responsibility and must NOT happen here.

    Parameters
    ----------
    dim:
        Spatial dimension (3 for all MVP problems).
    cell_type:
        Element type string.  After Plan B phase B5 (task P5-6) this
        accepts ``"hex8"``, ``"hex20"``, ``"tet4"``, and ``"tet10"`` —
        the full ElementFactory topology vocabulary.  Unknown topologies
        and invalid ``(cell_type, integration, hourglass)`` triples raise
        :class:`UnsupportedError` with a Plan B phase pointer.
    formulation:
        Kinematic formulation, e.g. ``"total_lagrangian"``.
    material_type:
        Material model identifier, e.g. ``"svk"`` or ``"j2_power_law"``.
    params:
        Material / solver parameter dict (passed through as-is).
    boundaries:
        List of boundary condition dicts (passed through as-is).
    coord_system:
        Coordinate system; defaults to ``"cartesian"``.
    fiber_data:
        Optional per-element fiber orientation data as a numeric array
        (``(n_elem, 2, 3)`` unit-vector pairs) — the programmatic / mesh-binding
        entry. Required (along with or instead of ``fiber_families``) for
        anisotropic models such as HGO.
    fiber_families:
        Optional fiber-direction families declared via the
        ``% mechanics fiber`` directive (constitutive_latex P5-1) — a list of
        ``{"direction": (x, y, z), ...}`` entries. Satisfies the
        anisotropic-requires-fiber requirement when ``fiber_data`` is absent.
    hourglass_coef:
        Dimensionless Flanagan-Belytschko hourglass control coefficient
        used by reduced-integration elements (Plan B phase B5, task P5-5).
        Defaults to ``0.05``; typical range is ``0.01 - 0.10``.
    integration:
        Integration rule selector, ``"full"`` (default) or ``"reduced"``.
        Plan B phase B5 task P5-6 added the option; routed through
        :class:`mechdsl.ir.element_factory.ElementFactory` for combination
        validation.
    hourglass:
        Hourglass-control scheme, ``None`` (default) or
        ``"flanagan_belytschko"``.  Only meaningful for reduced Hex8.

    Returns
    -------
    dict
        Context dict with keys: ``dim``, ``cell_type``, ``formulation``,
        ``material_type``, ``params``, ``boundaries``, ``coord_system``,
        ``hourglass_coef``, ``integration``, ``hourglass``.

    Raises
    ------
    UnsupportedError
        When any input falls outside the MVP-supported subset.
    """
    if dim != 3:
        raise UnsupportedError(
            f"dim={dim} is not supported; 2D support is planned for Plan B phase B2."
        )
    # Topology + integration + hourglass validation is delegated to
    # ElementFactory.create so the frontend, parser, and lowering layers all
    # agree on the supported triples (Plan B phase B5, task P5-6). Any
    # ValueError from the factory is rewrapped as UnsupportedError so the
    # frontend's public-API contract (UnsupportedError + Plan B pointer)
    # is preserved.
    from mechdsl.ir.element_factory import ElementFactory

    try:
        ElementFactory.create(
            topology=cell_type,
            integration=integration,
            hourglass=hourglass,
            formulation=formulation
            if formulation in {"total_lagrangian", "updated_lagrangian"}
            else "total_lagrangian",
        )
    except ValueError as exc:
        raise UnsupportedError(
            f"cell_type={cell_type!r} integration={integration!r} "
            f"hourglass={hourglass!r} is not supported: {exc}"
        ) from exc
    _SUPPORTED_FORMULATIONS = {"total_lagrangian", "updated_lagrangian"}
    if formulation not in _SUPPORTED_FORMULATIONS:
        raise UnsupportedError(
            f"formulation={formulation!r} is not supported; "
            f"supported formulations are: {sorted(_SUPPORTED_FORMULATIONS)}."
        )
    _SUPPORTED_MATERIALS = {
        "svk",
        "j2_power_law",
        "perzyna",
        "johnson_cook",
        "neo_hookean",
        "mooney_rivlin",
        "ogden",
        "hgo",
        "lemaitre",
    }
    if material_type not in _SUPPORTED_MATERIALS:
        raise UnsupportedError(
            f"material_type={material_type!r} is not supported; "
            f"supported models are: {sorted(_SUPPORTED_MATERIALS)}. "
            "Additional constitutive models are planned across Plan B phases "
            "B3 (viscoplasticity), B4 (advanced hyperelasticity), and B6 (damage)."
        )
    if coord_system != "cartesian":
        raise UnsupportedError(
            f"coord_system={coord_system!r} is not supported; "
            "curvilinear reference coordinates are planned for Plan B phase B2."
        )
    if material_type == "hgo" and fiber_data is None and not fiber_families:
        raise UnsupportedError(
            "material_type='hgo' requires fiber direction(s): either the "
            "fiber_data kwarg (per-element (a1, a2) unit-vector pairs, shape "
            "(n_elem, 2, 3)) or the '% mechanics fiber --family' directive "
            "(constitutive_latex P5-1)."
        )

    ctx: dict = {
        "dim": dim,
        "cell_type": cell_type,
        "formulation": formulation,
        "material_type": material_type,
        "params": params,
        "boundaries": boundaries,
        "coord_system": coord_system,
        "hourglass_coef": float(hourglass_coef),
        "integration": integration,
        "hourglass": hourglass,
    }
    if fiber_data is not None:
        ctx["fiber_data"] = fiber_data
    if fiber_families:
        ctx["fiber_families"] = fiber_families
    return ctx


# Import after ``build_context`` is defined so ``parser.parse`` can resolve
# it via ``from mechdsl.frontend import build_context`` without a circular
# import at module-load time.
from mechdsl.frontend.parser import parse, parse_file  # noqa: E402
