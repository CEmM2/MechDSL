"""Per-directive handlers for the ``% mechanics`` LaTeX DSL (normalization layer).

This module is the **normalizer** half of the frontend — see
``packages/mechdsl-core/src/mechdsl/frontend/ARCHITECTURE.md`` for the
parser-of-record vs adapter/normalizer/validator split.

Each handler takes a mutable accumulator dict and a parsed argument tuple
(``positional``, ``options``) and mutates the accumulator in place. Handlers
are responsible for *normalization*: parsing scalar / list / boolean argument
forms into the canonical context-dict schema. Supported-subset validation
(whether the resulting context is acceptable to the MVP path) lives
separately in :func:`mechdsl.frontend.build_context`.

The accumulator is the same dict shape that
:func:`mechdsl.frontend.build_context` accepts, with one extension: the
coordinate families (``coord_spatial``, ``coord_material``,
``coord_convected``) are collected separately and attached to the returned
context so downstream layers can resolve indices.

See ``dev/design_docs/02-LATEX-DSL.md`` for the directive grammar and
``dev/design_docs/PLAN-A.md §A3`` for the MVP subset.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


class ParseError(ValueError):
    """Raised when a ``% mechanics`` directive is syntactically malformed.

    Distinguishes *syntax* errors (bad grammar, unknown command, missing
    value for option) from *supported-subset* errors raised later by
    :func:`mechdsl.frontend.build_context`, which are wrapped in
    :class:`~mechdsl.symbolic.convected.UnsupportedError` and always name
    the Plan B phase that adds support.
    """


# Parsed argument shape: (positional tokens, {option_key: option_value}).
ParsedArgs = tuple[list[str], dict[str, str]]
Handler = Callable[[dict[str, Any], ParsedArgs, int], None]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _require_positional(
    args: ParsedArgs,
    n: int,
    *,
    command: str,
    line_no: int,
    exact: bool = True,
) -> list[str]:
    """Validate positional-argument count for a directive."""
    positional, _ = args
    if exact and len(positional) != n:
        raise ParseError(
            f"line {line_no}: '% mechanics {command}' expects exactly "
            f"{n} positional argument(s), got {len(positional)}: {positional!r}"
        )
    if not exact and len(positional) < n:
        raise ParseError(
            f"line {line_no}: '% mechanics {command}' expects at least "
            f"{n} positional argument(s), got {len(positional)}: {positional!r}"
        )
    return positional


def _parse_scalar(value: str) -> float | int | str:
    """Coerce an option value to int/float if possible, otherwise return str.

    Keeping values as their natural Python type makes the accumulator look
    identical to what a programmatic caller of :func:`build_context` would
    construct, so the round-trip test can use plain equality.
    """
    # Try int first (``--N 3``), then float (``--E 200e3``), then str.
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    return value


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


def _mech_dim(accum: dict[str, Any], args: ParsedArgs, line_no: int) -> None:
    """Handle ``% mechanics dim N``."""
    positional = _require_positional(args, 1, command="dim", line_no=line_no)
    try:
        dim = int(positional[0])
    except ValueError as exc:
        raise ParseError(
            f"line {line_no}: '% mechanics dim' argument must be an integer, got {positional[0]!r}"
        ) from exc
    accum["dim"] = dim


def _mech_cell(accum: dict[str, Any], args: ParsedArgs, line_no: int) -> None:
    """Handle ``% mechanics cell <type> [--integration <rule>] [--hourglass <scheme>]``.

    The ``--integration`` and ``--hourglass`` flags are Plan B phase B5
    additions (task P5-6).  Both flow through to the accumulator under the
    keys ``integration`` and ``hourglass`` respectively, where
    :func:`mechdsl.frontend.build_context` then dispatches them through
    :class:`mechdsl.ir.element_factory.ElementFactory` for combination
    validation.

    Examples
    --------
    ``% mechanics cell hex8``
        Legacy form — defaults to full integration, no hourglass control.
    ``% mechanics cell hex8 --integration reduced --hourglass flanagan_belytschko``
        Reduced Hex8 with Flanagan-Belytschko stabilisation.
    ``% mechanics cell tet4 --integration full``
        Explicit full-integration tet element.
    """
    positional = _require_positional(args, 1, command="cell", line_no=line_no)
    _, options = args
    accum["cell_type"] = positional[0]
    _ALLOWED = {"integration", "hourglass"}
    unknown = set(options) - _ALLOWED
    if unknown:
        raise ParseError(
            f"line {line_no}: '% mechanics cell' got unknown option(s) "
            f"{sorted(unknown)!r}; supported options are {sorted(_ALLOWED)!r}"
        )
    if "integration" in options:
        accum["integration"] = options["integration"]
    if "hourglass" in options:
        accum["hourglass"] = options["hourglass"]


def _mech_coord(accum: dict[str, Any], args: ParsedArgs, line_no: int) -> None:
    """Handle ``% mechanics coord <family> <name> [<name>...]``.

    Family is one of ``spatial``, ``material``, ``convected``.  Names are
    stored as a tuple under ``coord_<family>`` in the accumulator.
    """
    positional = _require_positional(args, 2, command="coord", line_no=line_no, exact=False)
    family = positional[0]
    names = tuple(positional[1:])
    if family not in ("spatial", "material", "convected"):
        raise ParseError(
            f"line {line_no}: '% mechanics coord' family must be one of "
            f"'spatial', 'material', 'convected'; got {family!r}"
        )
    key = f"coord_{family}"
    if key in accum:
        raise ParseError(f"line {line_no}: '% mechanics coord {family}' declared twice")
    accum[key] = names


def _mech_formulation(accum: dict[str, Any], args: ParsedArgs, line_no: int) -> None:
    """Handle ``% mechanics formulation <name>``."""
    positional = _require_positional(args, 1, command="formulation", line_no=line_no)
    accum["formulation"] = positional[0]


def _mech_material(accum: dict[str, Any], args: ParsedArgs, line_no: int) -> None:
    """Handle ``% mechanics material <type> [--key value]...``."""
    positional, options = args
    if len(positional) != 1:
        raise ParseError(
            f"line {line_no}: '% mechanics material' expects exactly one "
            f"positional argument (the material type), got {positional!r}"
        )
    accum["material_type"] = positional[0]
    params: dict[str, Any] = dict(accum.get("params", {}))
    for key, raw_value in options.items():
        params[key] = _parse_scalar(raw_value)
    accum["params"] = params


def _mech_boundary(accum: dict[str, Any], args: ParsedArgs, line_no: int) -> None:
    """Handle ``% mechanics boundary <name> [--key value]...``.

    Appends a BC dict to ``accum['boundaries']``.  Each BC dict has at
    least ``name`` and ``type`` keys; additional option fields flow through
    verbatim so downstream layers can consume them.
    """
    positional, options = args
    if len(positional) != 1:
        raise ParseError(
            f"line {line_no}: '% mechanics boundary' expects exactly one "
            f"positional argument (the boundary name), got {positional!r}"
        )
    if "type" not in options:
        raise ParseError(
            f"line {line_no}: '% mechanics boundary {positional[0]}' is "
            f"missing required option --type (dirichlet|neumann)"
        )
    bc: dict[str, Any] = {"name": positional[0], "type": options["type"]}
    for key, raw_value in options.items():
        if key == "type":
            continue
        if key == "components":
            # Components are a space-separated list of ints, e.g. "0 1 2".
            try:
                bc["components"] = [int(tok) for tok in raw_value.split()]
            except ValueError as exc:
                raise ParseError(
                    f"line {line_no}: --components must be a space-separated "
                    f"list of integers, got {raw_value!r}"
                ) from exc
        elif key == "traction":
            # Traction may be a symbolic name ("t_bar") or a 3-vector of floats
            # written as a quoted whitespace-separated triple ("0 0 -1000").
            # post_recovery_plan P1-2 added the numeric form so directive-driven
            # Neumann BCs can carry an explicit load without a symbol registry.
            tokens = raw_value.split()
            if len(tokens) >= 2:
                try:
                    bc["traction"] = [float(tok) for tok in tokens]
                except ValueError as exc:
                    raise ParseError(
                        f"line {line_no}: --traction must be either a symbol "
                        f"name (e.g. 't_bar') or a space-separated numeric "
                        f"3-vector (e.g. '0 0 -1000'); got {raw_value!r}"
                    ) from exc
                if len(bc["traction"]) != 3:
                    raise ParseError(
                        f"line {line_no}: --traction numeric form requires "
                        f"exactly 3 components, got {len(bc['traction'])} "
                        f"({raw_value!r})"
                    )
            else:
                bc["traction"] = raw_value  # symbolic-name form preserved
        elif key == "surface":
            # post_recovery_plan P1-2: --surface tags the mesh sideset the BC
            # acts on; routes through to BoundaryCondition.surface_tag.
            bc["surface_tag"] = raw_value
        else:
            bc[key] = _parse_scalar(raw_value)
    boundaries: list[dict[str, Any]] = list(accum.get("boundaries", []))
    boundaries.append(bc)
    accum["boundaries"] = boundaries


def _mech_index(accum: dict[str, Any], args: ParsedArgs, line_no: int) -> None:
    """Handle ``% mechanics index <family> <letter> [<letter>...]``.

    Records which Latin index letters belong to which manifold so the
    two-point tensor layer can validate contractions.  MVP does not
    consume these beyond storage; they exist so dual-use LaTeX sources
    can declare them without tripping the unknown-command error.
    """
    positional = _require_positional(args, 2, command="index", line_no=line_no, exact=False)
    family = positional[0]
    letters = tuple(positional[1:])
    if family not in ("spatial", "material"):
        raise ParseError(
            f"line {line_no}: '% mechanics index' family must be 'spatial' "
            f"or 'material'; got {family!r}"
        )
    key = f"indices_{family}"
    existing: tuple[str, ...] = accum.get(key, ())
    accum[key] = existing + letters


def _mech_assign(accum: dict[str, Any], args: ParsedArgs, line_no: int) -> None:
    """Handle ``% mechanics assign <tensor_name> --metric_current <val>`` or
    ``% mechanics assign <tensor_name> --metric_reference <val>``.

    Stashes the metric tensor symbol name in the accumulator so downstream
    layers can map NRPyLaTeX metric symbols to the correct role.  The option
    value is ignored — only the key presence is meaningful.  Use a placeholder
    value such as ``true`` when writing directives::

        % mechanics assign gDD --metric_current true
        % mechanics assign GDD --metric_reference true
    """
    positional, options = args
    if len(positional) != 1:
        raise ParseError(
            f"line {line_no}: '% mechanics assign' expects exactly one "
            f"positional argument (the tensor symbol name), got {positional!r}"
        )
    tensor_name = positional[0]
    has_current = "metric_current" in options
    has_reference = "metric_reference" in options
    if has_current and has_reference:
        raise ParseError(
            f"line {line_no}: '% mechanics assign {tensor_name}' has both "
            f"--metric_current and --metric_reference; specify exactly one"
        )
    if not has_current and not has_reference:
        raise ParseError(
            f"line {line_no}: '% mechanics assign {tensor_name}' requires "
            f"exactly one of --metric_current or --metric_reference"
        )
    if has_current:
        accum["metric_current"] = tensor_name
    else:
        accum["metric_reference"] = tensor_name


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


HANDLERS: dict[str, Handler] = {
    "dim": _mech_dim,
    "cell": _mech_cell,
    "coord": _mech_coord,
    "formulation": _mech_formulation,
    "material": _mech_material,
    "boundary": _mech_boundary,
    "index": _mech_index,
    "assign": _mech_assign,
}
"""Registry of MVP directive handlers.

Directives outside this set (``field``, ``weak_form``, ``constitutive``,
``codegen``, ``verify``) are documented in ``02-LATEX-DSL.md`` but are not
part of the MVP subset — they are rejected with a Plan B pointer by
:func:`mechdsl.frontend.parser.parse`.
"""


# Directives that are documented in 02-LATEX-DSL.md but deferred past MVP.
# Mapping: command -> (plan_phase, rationale).
DEFERRED_DIRECTIVES: dict[str, tuple[str, str]] = {
    "field": ("Plan B", "solution-field metadata is Plan B (SymPDE integration)"),
    "weak_form": ("Plan B", "SymPDE variational-form emission is Plan B"),
    "constitutive": (
        "Plan B",
        "user-defined strain-energy parsing requires the NRPyLaTeX fork",
    ),
    "codegen": (
        "Plan B",
        "multi-target codegen selectors (MFEM/MOOSE) are Plan B; MVP emits Taichi unconditionally",
    ),
    "verify": ("Plan B", "verification-metadata directives are Plan B"),
}
