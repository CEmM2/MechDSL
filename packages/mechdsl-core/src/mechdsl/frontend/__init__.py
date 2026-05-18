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
    "UnsupportedError",
    "build_context",
    "has_math_block",
    "parse",
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
        }
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
    for block in blocks:
        nrpy_input = (declarations + "\n" + block).strip() if declarations else block
        res = parse_math(nrpy_input)
        all_tensors.update(res.tensors)
        all_classifications.update(res.classifications)

    context["math"] = {
        "blocks": blocks,
        "tensors": convert_namespace(all_tensors, all_classifications),
        "namespace": all_tensors,
        "classifications": all_classifications,
    }
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
        Optional per-element fiber orientation data (required only for
        anisotropic models such as HGO).
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
    if material_type == "hgo" and fiber_data is None:
        raise UnsupportedError(
            "material_type='hgo' requires the fiber_data kwarg "
            "(per-element (a1, a2) unit-vector pair, shape (n_elem, 2, 3))."
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
    return ctx


# Import after ``build_context`` is defined so ``parser.parse`` can resolve
# it via ``from mechdsl.frontend import build_context`` without a circular
# import at module-load time.
from mechdsl.frontend.parser import parse, parse_file  # noqa: E402
