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


FLAG_OPTIONS: dict[str, frozenset[str]] = {
    "constitutive": frozenset({"strain_energy", "cauchy", "pk2"}),
    "weak_form": frozenset({"residual"}),
    "verify": frozenset({"patch_test"}),
}
"""Command-scoped flag-only options accepted by the directive splitter."""


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


def _parse_options(options: dict[str, str]) -> dict[str, Any]:
    """Parse all option values through :func:`_parse_scalar`."""
    return {key: _parse_scalar(value) for key, value in options.items()}


def _is_number(token: str) -> bool:
    """Return ``True`` when ``token`` parses as a float."""
    try:
        float(token)
    except ValueError:
        return False
    return True


def _parse_traction(value: str, *, line_no: int) -> list[float] | str:
    """Parse a traction option into a symbolic name or numeric 3-vector."""
    if "," in value:
        # A comma-bearing value is a symbolic traction expression (e.g.
        # "0, -P/A") and passes through unchanged — UNLESS every comma-separated
        # component is numeric, which means the caller meant a numeric vector but
        # used commas instead of spaces.  Reject that explicitly so
        # '--traction "0, 0, -1000"' fails here with an actionable message rather
        # than silently passing through as a bogus symbolic name.
        parts = [p.strip() for p in value.split(",")]
        if all(_is_number(p) for p in parts):
            raise ParseError(
                f"line {line_no}: --traction numeric vectors must be "
                f"space-separated, not comma-separated (e.g. '0 0 -1000'); "
                f"got {value!r}"
            )
        return value

    tokens = value.split()
    if len(tokens) < 2:
        return value

    try:
        traction = [float(tok) for tok in tokens]
    except ValueError as exc:
        raise ParseError(
            f"line {line_no}: --traction must be either a symbol name "
            f"(e.g. 't_bar') or a space-separated numeric 3-vector "
            f"(e.g. '0 0 -1000'); got {value!r}"
        ) from exc
    if len(traction) != 3:
        raise ParseError(
            f"line {line_no}: --traction numeric form requires exactly "
            f"3 components, got {len(traction)} ({value!r})"
        )
    return traction


def _reject_unknown_options(
    options: dict[str, str],
    allowed: set[str],
    *,
    command: str,
    line_no: int,
) -> None:
    """Raise for options outside a directive's documented grammar."""
    unknown = set(options) - allowed
    if unknown:
        raise ParseError(
            f"line {line_no}: '% mechanics {command}' got unknown option(s) "
            f"{sorted(unknown)!r}; supported options are {sorted(allowed)!r}"
        )


def _append_entry(accum: dict[str, Any], key: str, entry: dict[str, Any]) -> None:
    """Append a normalized metadata entry under ``key``."""
    entries: list[dict[str, Any]] = list(accum.get(key, []))
    entries.append(entry)
    accum[key] = entries


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
    bc: dict[str, Any] = {
        "name": positional[0],
        "type": options["type"],
        "source_line": line_no,
    }
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
            bc["traction"] = _parse_traction(raw_value, line_no=line_no)
        elif key == "surface":
            # post_recovery_plan P1-2: --surface tags the mesh sideset the BC
            # acts on; routes through to BoundaryCondition.surface_tag.
            bc["surface_tag"] = raw_value
        else:
            bc[key] = _parse_scalar(raw_value)
    boundaries: list[dict[str, Any]] = list(accum.get("boundaries", []))
    boundaries.append(bc)
    accum["boundaries"] = boundaries


def _mech_bc(accum: dict[str, Any], args: ParsedArgs, line_no: int) -> None:
    """Handle documented ``% mechanics bc ...`` metadata.

    ``dirichlet`` and ``neumann`` normalize to the same boundary schema as
    legacy ``% mechanics boundary`` directives.  ``body_force`` is not a
    boundary region, so it is stored separately as codegen metadata.
    """
    positional, options = args
    if len(positional) != 1:
        raise ParseError(
            f"line {line_no}: '% mechanics bc' expects exactly one positional "
            f"argument (dirichlet|neumann|body_force), got {positional!r}"
        )
    bc_type = positional[0]
    if bc_type not in {"dirichlet", "neumann", "body_force"}:
        raise ParseError(
            f"line {line_no}: '% mechanics bc' type must be one of "
            f"'dirichlet', 'neumann', 'body_force'; got {bc_type!r}"
        )
    if bc_type == "body_force":
        _reject_unknown_options(
            options,
            {"field", "value"},
            command="bc body_force",
            line_no=line_no,
        )
        if "field" not in options or "value" not in options:
            raise ParseError(
                f"line {line_no}: '% mechanics bc body_force' requires --field and --value"
            )
        _append_entry(
            accum,
            "body_forces",
            {
                "type": "body_force",
                "field_name": options["field"],
                "value": _parse_scalar(options["value"]),
                "source_line": line_no,
            },
        )
        return

    allowed_options = (
        {"field", "boundary", "value", "surface"}
        if bc_type == "dirichlet"
        else {"field", "boundary", "traction", "surface"}
    )
    _reject_unknown_options(
        options,
        allowed_options,
        command=f"bc {bc_type}",
        line_no=line_no,
    )
    required = {"value"} if bc_type == "dirichlet" else {"traction"}
    missing = sorted(required - set(options))
    if missing:
        raise ParseError(
            f"line {line_no}: '% mechanics bc {bc_type}' missing required option(s) {missing!r}"
        )

    boundary_count = len(accum.get("boundaries", []))
    bc: dict[str, Any] = {
        "name": options.get("boundary", f"{bc_type}_{boundary_count}"),
        "type": bc_type,
        "field_name": options.get("field", "u"),
        "source_line": line_no,
    }
    if bc_type == "dirichlet":
        bc["value"] = _parse_scalar(options["value"])
    else:
        bc["traction"] = _parse_traction(options["traction"], line_no=line_no)
    if "surface" in options:
        bc["surface_tag"] = options["surface"]
    boundaries: list[dict[str, Any]] = list(accum.get("boundaries", []))
    boundaries.append(bc)
    accum["boundaries"] = boundaries


def _mech_field(accum: dict[str, Any], args: ParsedArgs, line_no: int) -> None:
    """Handle ``% mechanics field <name> --type ... --space ... --order ...``."""
    positional, options = args
    if len(positional) != 1:
        raise ParseError(
            f"line {line_no}: '% mechanics field' expects exactly one "
            f"positional argument (the field name), got {positional!r}"
        )
    _reject_unknown_options(
        options,
        {"type", "space", "order"},
        command="field",
        line_no=line_no,
    )
    missing = sorted({"type", "space", "order"} - set(options))
    if missing:
        raise ParseError(
            f"line {line_no}: '% mechanics field {positional[0]}' missing "
            f"required option(s) {missing!r}; field metadata feeds later "
            "Plan B SymPDE integration and must be complete when declared"
        )
    field_type = options["type"]
    if field_type not in {"scalar", "vector"}:
        raise ParseError(
            f"line {line_no}: '% mechanics field' --type must be 'scalar' "
            f"or 'vector'; got {field_type!r}"
        )
    try:
        order = int(options["order"])
    except ValueError as exc:
        raise ParseError(
            f"line {line_no}: '% mechanics field' --order must be an integer, "
            f"got {options['order']!r}"
        ) from exc
    if order < 0:
        raise ParseError(
            f"line {line_no}: '% mechanics field' --order must be non-negative, got {order}"
        )
    _append_entry(
        accum,
        "fields",
        {
            "name": positional[0],
            "kind": field_type,
            "space": options["space"],
            "order": order,
            "source_line": line_no,
        },
    )


def _mech_fiber(accum: dict[str, Any], args: ParsedArgs, line_no: int) -> None:
    """Handle ``% mechanics fiber --family "x, y, z"``.

    Declares one fiber-direction family as per-element FIELD data (distinct
    from scalar ``% mechanics material`` params). Each directive contributes one
    family; repeat the directive for multi-family anisotropic models (HGO uses
    two). The direction is a numeric 3-vector, comma- or space-separated.
    Accumulates ``{"direction": (x, y, z), "source_line": n}`` entries under
    ``fiber_families``, which the IR maps to a ``FiberFieldSpec`` carried through
    ProblemIR -> Element IR (constitutive_latex P5-1).
    """
    positional, options = args
    if positional:
        raise ParseError(
            f"line {line_no}: '% mechanics fiber' takes no positional argument "
            f'(use --family "x, y, z"), got {positional!r}'
        )
    _reject_unknown_options(options, {"family"}, command="fiber", line_no=line_no)
    if "family" not in options:
        raise ParseError(
            f"line {line_no}: '% mechanics fiber' requires --family with a numeric "
            '3-vector direction (e.g. --family "1, 0, 0"); anisotropic fiber '
            "plumbing is constitutive_latex Phase 5 (P5-1)."
        )
    raw = options["family"]
    tokens = [t for t in raw.replace(",", " ").split() if t]
    try:
        direction = tuple(float(t) for t in tokens)
    except ValueError as exc:
        raise ParseError(
            f"line {line_no}: '% mechanics fiber' --family must be a numeric "
            f"3-vector (e.g. '1, 0, 0'); got {raw!r} (constitutive_latex P5-1)."
        ) from exc
    if len(direction) != 3:
        raise ParseError(
            f"line {line_no}: '% mechanics fiber' --family requires exactly 3 "
            f"components, got {len(direction)} ({raw!r}) (constitutive_latex P5-1)."
        )
    if sum(c * c for c in direction) <= 0.0:
        raise ParseError(
            f"line {line_no}: '% mechanics fiber' --family must be a nonzero "
            f"direction, got {raw!r} (constitutive_latex P5-1)."
        )
    _append_entry(
        accum,
        "fiber_families",
        {"direction": direction, "source_line": line_no},
    )


def _mech_constitutive(accum: dict[str, Any], args: ParsedArgs, line_no: int) -> None:
    """Handle documented constitutive role metadata."""
    positional, options = args
    if len(positional) != 1:
        raise ParseError(
            f"line {line_no}: '% mechanics constitutive' expects exactly one "
            f"positional argument (the assigned symbol), got {positional!r}"
        )
    _reject_unknown_options(
        options,
        {"strain_energy", "cauchy", "pk2"},
        command="constitutive",
        line_no=line_no,
    )
    roles = [role for role in ("strain_energy", "cauchy", "pk2") if role in options]
    if len(roles) != 1:
        raise ParseError(
            f"line {line_no}: '% mechanics constitutive {positional[0]}' "
            "requires exactly one role flag: --strain_energy, --cauchy, or --pk2"
        )
    _append_entry(
        accum,
        "constitutive",
        {"symbol": positional[0], "role": roles[0], "source_line": line_no},
    )


def _mech_weak_form(accum: dict[str, Any], args: ParsedArgs, line_no: int) -> None:
    """Handle documented weak-form metadata."""
    positional, options = args
    if len(positional) != 1:
        raise ParseError(
            f"line {line_no}: '% mechanics weak_form' expects exactly one "
            f"positional argument (the weak-form label), got {positional!r}"
        )
    _reject_unknown_options(
        options,
        {"test", "trial", "domain", "residual"},
        command="weak_form",
        line_no=line_no,
    )
    if "residual" in options:
        unknown_with_residual = sorted({"test", "trial"} & set(options))
        if unknown_with_residual:
            raise ParseError(
                f"line {line_no}: '% mechanics weak_form {positional[0]}' "
                f"--residual cannot be combined with {unknown_with_residual!r}"
            )
        entry = {
            "name": positional[0],
            "kind": "residual",
            "source_line": line_no,
        }
        contract = {
            "terms": [],
            "weak_form_label": positional[0],
            "metadata": {"kind": "residual", "source_line": line_no},
        }
    else:
        missing = sorted({"test", "trial", "domain"} - set(options))
        if missing:
            raise ParseError(
                f"line {line_no}: '% mechanics weak_form {positional[0]}' "
                f"missing required option(s) {missing!r}"
            )
        entry = {
            "name": positional[0],
            "kind": "bilinear",
            "test": options["test"],
            "trial": options["trial"],
            "domain": options["domain"],
            "source_line": line_no,
        }
        contract = {
            "terms": [positional[0]],
            "weak_form_label": positional[0],
            "metadata": {
                "kind": "bilinear",
                "test": options["test"],
                "trial": options["trial"],
                "domain": options["domain"],
                "source_line": line_no,
            },
        }
    if "residual_contract" in accum:
        existing_label = accum["residual_contract"].get("weak_form_label")
        raise ParseError(
            f"line {line_no}: '% mechanics weak_form {positional[0]}' would "
            f"overwrite an existing residual_contract bound to {existing_label!r}; "
            "ProblemIR.residual_contract is singular — declare only one weak_form "
            "per source (multi-form support is planned for Plan B)"
        )
    accum["residual_contract"] = contract
    _append_entry(accum, "weak_forms", entry)


def _mech_codegen(accum: dict[str, Any], args: ParsedArgs, line_no: int) -> None:
    """Handle codegen metadata while rejecting non-Taichi stable targets."""
    positional, options = args
    if positional:
        raise ParseError(
            f"line {line_no}: '% mechanics codegen' expects no positional "
            f"arguments, got {positional!r}"
        )
    _reject_unknown_options(
        options,
        {"target", "output"},
        command="codegen",
        line_no=line_no,
    )
    missing = sorted({"target", "output"} - set(options))
    if missing:
        raise ParseError(
            f"line {line_no}: '% mechanics codegen' missing required option(s) {missing!r}"
        )
    target = options["target"]
    if target != "taichi":
        raise ParseError(
            f"line {line_no}: '% mechanics codegen' target {target!r} is "
            "outside the MVP-stable compile_latex path; only 'taichi' is "
            "accepted here. Use experimental backend printers directly."
        )
    accum["codegen"] = {
        "target": target,
        "output": options["output"],
        "source_line": line_no,
    }


def _mech_verify(accum: dict[str, Any], args: ParsedArgs, line_no: int) -> None:
    """Handle verification metadata and reject unsupported modes cleanly."""
    positional, options = args
    if positional:
        raise ParseError(
            f"line {line_no}: '% mechanics verify' expects no positional "
            f"arguments, got {positional!r}"
        )
    if "method" in options:
        raise ParseError(
            f"line {line_no}: '% mechanics verify --method {options['method']}' "
            "is not supported on the MVP-stable path; supported verification "
            "metadata forms are --benchmark ... and --patch_test"
        )
    if "patch_test" in options:
        _reject_unknown_options(options, {"patch_test"}, command="verify", line_no=line_no)
        kind = "patch_test"
        metadata: dict[str, Any] = {}
    elif "benchmark" in options:
        # Benchmark params are forwarded as the `params` dict; the set of valid
        # keys depends on the benchmark (e.g. cantilever_beam takes E, nu, P,
        # plasticity benchmarks add sigma_y, etc.), so callers can pass any
        # scalar `--key value` pair beyond `--benchmark`. No unknown-option
        # rejection is performed here on purpose.
        kind = "benchmark"
        metadata = _parse_options({k: v for k, v in options.items() if k != "benchmark"})
    else:
        raise ParseError(
            f"line {line_no}: '% mechanics verify' requires --benchmark or --patch_test"
        )
    entry = {
        "kind": kind,
        "source_line": line_no,
    }
    if kind == "benchmark":
        entry["benchmark"] = options["benchmark"]
        entry["params"] = metadata
    _append_entry(accum, "verify", entry)


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
    "bc": _mech_bc,
    "field": _mech_field,
    "fiber": _mech_fiber,
    "constitutive": _mech_constitutive,
    "weak_form": _mech_weak_form,
    "codegen": _mech_codegen,
    "verify": _mech_verify,
    "index": _mech_index,
    "assign": _mech_assign,
}
"""Registry of documented ``% mechanics`` directive handlers."""


# Compatibility hook for older tests/importers. P3-1 promotes all documented
# directive shapes into HANDLERS, so no command is currently deferred here.
DEFERRED_DIRECTIVES: dict[str, tuple[str, str]] = {}
