"""``mechdsl-lawgen`` command-line entry point.

Part of the MechDSL lawgen pipeline (YAML law spec → restricted SymPy →
Taichi carrier).

This is the *skeleton* CLI: it wires the ``mechdsl-lawgen compile <law.yaml>
--target ticonstit --out <dir>`` surface, parses a law YAML into a
:class:`~mechdsl.lawgen.contracts.PlasticityCarrierSpec`, and — in ``--dry-run``
mode — prints the *emission plan* without writing any files.

There is deliberately **no** lowering / codegen here. Turning the R/H/Q
expressions into Taichi source is Phase 2's job (``taichi_printer`` is not
imported). Likewise there is no ``import ticonstit`` and no NumerixWeave import:
the MechDSL↔NumerixWeave seam is committed artifacts only. The CLI depends only
on :mod:`mechdsl.lawgen`, the standard library, :mod:`yaml`, and :mod:`sympy`.

Law YAML schema
---------------
.. code-block:: yaml

    name: swift_voce                 # str  → carrier identifier
    parameters: [sigma0, Q, b, K, n] # list[str] → material parameters
    variables: [p, edot, T]          # list[str] → free-variable bindings
    expressions:                     # map with the three required roles
      R: "sigma0 + Q*(1 - exp(-b*p)) + K*p**n"
      H: "..."
      Q: "..."

Every parameter and variable becomes a SymPy ``Symbol``; each of ``R``/``H``/``Q``
is parsed against those symbols (with a **non-eval** parser and a restricted
math allow-list — never ``sympify``/``eval`` on untrusted YAML) and handed to
``PlasticityCarrierSpec``.
"""

from __future__ import annotations

import argparse
import keyword
import sys
from pathlib import Path
from tokenize import TokenError

import sympy as sp
import yaml  # type: ignore[import-untyped]  # PyYAML ships no stubs
from sympy.core.function import AppliedUndef
from sympy.parsing.sympy_parser import parse_expr, standard_transformations

from mechdsl.lawgen.carrier_emitter import emit_carrier, snake_case_module_name
from mechdsl.lawgen.contracts import PlasticityCarrierSpec, TiconstitTarget
from mechdsl.lawgen.diagnostics import LawgenError
from mechdsl.lawgen.manifest import (
    GENERATED_BY,
    compute_input_formula_hash,
    emit_manifest,
    write_manifest,
)
from mechdsl.lawgen.test_emitter import emit_tests

# The only ``--target`` value currently accepted. Kept as a module constant so
# the argparse ``choices`` and the error message agree.
_SUPPORTED_TARGETS: tuple[str, ...] = ("ticonstit",)

# Required top-level keys in a law YAML document. ``variables`` and
# ``expressions`` drive the spec's bindings and R/H/Q; ``name``/``parameters``
# name the carrier and its material parameters.
_REQUIRED_KEYS: tuple[str, ...] = ("name", "parameters", "variables", "expressions")

# Exactly the keys a law YAML may carry at the top level. Anything else is a
# typo or an attempt to smuggle unexpected data — rejected.
_ALLOWED_TOP_KEYS: frozenset[str] = frozenset(_REQUIRED_KEYS)

# The math functions an R/H/Q expression may call. A deliberately
# conservative set for the CLI front-end; the printer owns the full Taichi
# allow-list (what it can actually lower).
_ALLOWED_FUNCTIONS: dict[str, object] = {
    "exp": sp.exp,
    "log": sp.log,
    "sqrt": sp.sqrt,
    "sin": sp.sin,
    "cos": sp.cos,
    "tan": sp.tan,
    "sinh": sp.sinh,
    "cosh": sp.cosh,
    "tanh": sp.tanh,
    "Abs": sp.Abs,
    "Max": sp.Max,
    "Min": sp.Min,
    "sign": sp.sign,
}

# The *only* global namespace expressions are parsed against. We do NOT
# use parse_expr's default global_dict (``exec('from sympy import *')``, which
# also injects ``__builtins__`` — and thus ``__import__``). Instead:
#   * ``"__builtins__": {}`` — set explicitly so ``eval_expr`` cannot re-inject
#     the real builtins; this is what makes ``__import__``/``eval``/``open``
#     unreachable, so a hostile expression cannot execute anything.
#   * the SymPy numeric/symbol constructors that ``standard_transformations``
#     emits (``Integer``/``Float``/``Rational``/``Symbol``) — required so plain
#     numeric literals like ``1`` parse.
#   * the math allow-list above.
_PARSE_GLOBALS: dict[str, object] = {
    "__builtins__": {},
    "Integer": sp.Integer,
    "Float": sp.Float,
    "Rational": sp.Rational,
    "Symbol": sp.Symbol,
    **_ALLOWED_FUNCTIONS,
}


class _LawError(Exception):
    """A user-facing, message-only error while loading a law YAML.

    Raised for any malformed input (bad YAML, missing key, bad expression) so
    the CLI can print a concise ``error: ...`` line to stderr and exit non-zero
    instead of leaking a raw traceback.
    """


# ---------------------------------------------------------------------------
# YAML → PlasticityCarrierSpec.
# ---------------------------------------------------------------------------


def load_carrier_spec(law_path: Path) -> PlasticityCarrierSpec:
    """Parse ``law_path`` into a :class:`PlasticityCarrierSpec`.

    Raises :class:`_LawError` (message only, no traceback) for every user-input
    failure route: the file is missing, the YAML is malformed, an unknown or
    missing key is present, ``name``/``parameters``/``variables`` are not valid
    Python identifiers (or collide / duplicate), or an R/H/Q expression fails to
    parse / references an undeclared name or unknown function.
    """
    spec, _raw = load_carrier_source(law_path)
    return spec


def load_carrier_source(law_path: Path) -> tuple[PlasticityCarrierSpec, dict[str, str]]:
    """Parse ``law_path`` into a spec **and** the verbatim R/H/Q expression strings.

    Same validation and failure routes as :func:`load_carrier_spec` (which is a
    thin wrapper over this), but also returns the *raw* expression strings exactly
    as the YAML spells them (keyed ``"R"``/``"H"``/``"Q"``). The real-emission path
    needs the verbatim ``R`` string to build the canonical ``input_formula`` whose
    SHA-256 is the manifest ``source_hash`` — SymPy re-printing ``spec.R`` would
    change the spacing/ordering and thus the hash, so the raw string is preserved
    here rather than reconstructed from the parsed expression.
    """
    try:
        raw_text = law_path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise _LawError(f"law YAML not found: {law_path}") from exc
    except OSError as exc:  # unreadable file, permission error, …
        raise _LawError(f"could not read law YAML {law_path}: {exc}") from exc

    try:
        doc = yaml.safe_load(raw_text)
    except yaml.YAMLError as exc:
        raise _LawError(f"malformed YAML in {law_path}: {exc}") from exc

    if not isinstance(doc, dict):
        raise _LawError(
            f"law YAML {law_path} must be a mapping with keys "
            f"{list(_REQUIRED_KEYS)}, got {type(doc).__name__}."
        )

    # Reject any unexpected top-level key up front (typos, smuggled data).
    unknown_top = sorted(set(doc) - _ALLOWED_TOP_KEYS)
    if unknown_top:
        raise _LawError(f"law YAML has unknown top-level key(s): {', '.join(unknown_top)}")

    for key in _REQUIRED_KEYS:
        if key not in doc:
            raise _LawError(f"law YAML missing required key {key!r}")

    name = doc["name"]
    if not isinstance(name, str) or not name:
        raise _LawError("law YAML key 'name' must be a non-empty string")
    # name drives generated file/class names, so it must be a plain Python
    # identifier — this rejects path separators/traversal ("../../escape") and
    # reserved words ("class").
    _require_identifier(name, kind="name")

    parameters = _as_str_list(doc["parameters"], key="parameters")
    variables = _as_str_list(doc["variables"], key="variables")

    # Every parameter/variable name must be a valid identifier, with no
    # duplicates within a list and no parameter↔variable collision (a name can
    # only mean one thing in the symbol table).
    for param in parameters:
        _require_identifier(param, kind="parameter")
    for var in variables:
        _require_identifier(var, kind="variable")
    _reject_duplicates(parameters, kind="parameter")
    _reject_duplicates(variables, kind="variable")
    collisions = sorted(set(parameters) & set(variables))
    if collisions:
        raise _LawError(
            f"name(s) declared as both a parameter and a variable: {', '.join(collisions)}"
        )

    expressions_raw = doc["expressions"]
    if not isinstance(expressions_raw, dict):
        raise _LawError("law YAML key 'expressions' must be a mapping of R/H/Q strings")
    # Reject any expressions key outside the required R/H/Q roles.
    unknown_roles = sorted(set(expressions_raw) - set(PlasticityCarrierSpec.REQUIRED_EXPRESSIONS))
    if unknown_roles:
        raise _LawError(
            f"law YAML 'expressions' has unknown role key(s): {', '.join(unknown_roles)}"
        )

    # Build the symbol table every expression is parsed against: one Symbol
    # per material parameter and per free variable. Variable symbols double as
    # the spec's variable_bindings.
    variable_bindings: dict[str, sp.Symbol] = {v: sp.Symbol(v) for v in variables}
    locals_table: dict[str, sp.Symbol] = {p: sp.Symbol(p) for p in parameters}
    locals_table.update(variable_bindings)

    expressions: dict[str, sp.Expr] = {}
    raw_expressions: dict[str, str] = {}
    for role in PlasticityCarrierSpec.REQUIRED_EXPRESSIONS:
        if role not in expressions_raw:
            raise _LawError(f"law YAML 'expressions' missing required role {role!r}")
        raw = expressions_raw[role]
        expressions[role] = _parse_expr(raw, role=role, locals_table=locals_table)
        # Preserve the verbatim source string (``_parse_expr`` has already checked
        # it is a str); the manifest source_hash is the SHA-256 of this exact text.
        raw_expressions[role] = raw

    try:
        spec = PlasticityCarrierSpec(
            name=name,
            parameters=tuple(parameters),
            expressions=expressions,
            variable_bindings=variable_bindings,
        )
    except (ValueError, TypeError) as exc:
        # Surface contract-level validation (empty parameters, etc.) as a clean
        # user error rather than a traceback.
        raise _LawError(str(exc)) from exc
    return spec, raw_expressions


def _as_str_list(value: object, *, key: str) -> list[str]:
    """Coerce a YAML list of names into ``list[str]``, or raise ``_LawError``."""
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise _LawError(f"law YAML key {key!r} must be a list of strings")
    if not value:
        raise _LawError(f"law YAML key {key!r} must be a non-empty list of strings")
    return list(value)


def _require_identifier(candidate: str, *, kind: str) -> None:
    """Reject ``candidate`` unless it is a valid, non-keyword Python identifier (F4).

    Guards against path separators / traversal (``../../escape``) and reserved
    words (``class``) leaking into generated file/class names or the symbol
    table.
    """
    if not candidate.isidentifier() or keyword.iskeyword(candidate):
        raise _LawError(
            f"{kind} {candidate!r} is not a valid Python identifier "
            "(letters, digits, underscores; not starting with a digit; not a reserved word)"
        )


def _reject_duplicates(names: list[str], *, kind: str) -> None:
    """Raise ``_LawError`` if ``names`` contains a repeat (F4)."""
    seen: set[str] = set()
    dupes: list[str] = []
    for name in names:
        if name in seen and name not in dupes:
            dupes.append(name)
        seen.add(name)
    if dupes:
        raise _LawError(f"duplicate {kind} name(s): {', '.join(sorted(dupes))}")


def _parse_expr(raw: object, *, role: str, locals_table: dict[str, sp.Symbol]) -> sp.Expr:
    """Parse one R/H/Q expression string safely against ``locals_table``.

    Security (F1): parsing goes through :func:`sympy.parsing.sympy_parser.parse_expr`
    with a *restricted* namespace — the declared symbols as ``local_dict`` and
    :data:`_PARSE_GLOBALS` (``__builtins__`` blanked + SymPy constructors +
    math allow-list) as ``global_dict``. ``__import__``, ``eval``, ``open`` etc.
    are simply not names in scope, so a hostile expression like
    ``__import__('os').system(...)`` cannot execute anything (contrast
    ``sympify``, which evals against full builtins). ``transformations`` is the
    plain ``standard_transformations`` — no implicit-call magic.

    Validation:

    * F2 — reject any undefined applied function (e.g. a typo ``expp(-b*p)``);
    * free-symbol subset — reject any free symbol not in the declared set
      (parameters ∪ variables), so a typo'd name (``signa0`` for ``sigma0``)
      fails loudly instead of becoming a stray symbol.
    """
    if not isinstance(raw, str):
        raise _LawError(f"law YAML expression {role!r} must be a string, got {type(raw).__name__}")
    try:
        expr = parse_expr(
            raw,
            local_dict=dict(locals_table),
            global_dict=dict(_PARSE_GLOBALS),
            transformations=standard_transformations,
            evaluate=True,
        )
    # parse_expr internally ``eval``s transformed code against the restricted
    # namespace; a hostile/garbage input (e.g. ``__import__('os').system(...)``)
    # can surface as SyntaxError/TokenError/NameError/AttributeError/TypeError/
    # ValueError. None of those *execute* anything — os/__import__/eval are not
    # in scope — but we catch broadly so no such failure ever leaks as a raw
    # traceback to the user.
    except (SyntaxError, TokenError) as exc:
        raise _LawError(f"could not parse expression {role!r} ({raw!r}): {exc}") from exc
    except Exception as exc:
        raise _LawError(f"could not parse expression {role!r} ({raw!r}): {exc}") from exc

    if not isinstance(expr, sp.Expr):
        raise _LawError(f"expression {role!r} ({raw!r}) did not parse to a scalar expression")

    # Any AppliedUndef is a call to a function that is not in the allow-list
    # (a typo like ``expp`` or an intentionally-unknown call).
    unknown_funcs = sorted({type(f).__name__ for f in expr.atoms(AppliedUndef)})
    if unknown_funcs:
        raise _LawError(
            f"expression {role!r} calls unknown function(s): {', '.join(unknown_funcs)}"
        )

    declared = set(locals_table)
    undeclared = sorted(sym.name for sym in expr.free_symbols if sym.name not in declared)
    if undeclared:
        raise _LawError(
            f"expression {role!r} references undeclared name(s): {', '.join(undeclared)}"
        )
    return expr


# ---------------------------------------------------------------------------
# Emission plan (dry-run).
# ---------------------------------------------------------------------------


def _planned_paths(out_dir: Path, spec: PlasticityCarrierSpec) -> dict[str, Path]:
    """The output paths a *real* compile writes, keyed by role.

    The generated *class* is ``spec.name`` (CamelCase, e.g. ``SwiftVoce``) but the
    *module* filename is snake_case (``swift_voce.py``), matching Cycle 0's
    file↔class decoupling — the manifest ``source`` field records the mapping. The
    dry-run plan and the real emission share this one function, so they never
    disagree about where a file lands.
    """
    module = snake_case_module_name(spec.name)
    carrier = out_dir / "plasticity" / f"{module}.py"
    return {
        "carrier": carrier,
        "manifest": out_dir / "_manifest.json",
        "test": out_dir / "tests" / f"test_{module}.py",
    }


def format_emission_plan(
    spec: PlasticityCarrierSpec, target: TiconstitTarget, out_dir: Path
) -> str:
    """Render the human-readable emission plan for ``--dry-run``.

    The exact line prefixes below are a stable contract: Phase 4's end-to-end
    test asserts against them. Keep them in sync if you change the format.
    """
    paths = _planned_paths(out_dir, spec)
    lines = [
        "mechdsl-lawgen: emission plan (dry-run, no files written)",
        f"  carrier:      {spec.name}",
        "  target:       ticonstit",
        f"  contract_id:  {target.contract_id}",
        f"  package:      {target.package}",
        f"  parameters:   {', '.join(spec.parameters)}",
        f"  variables:    {', '.join(spec.variable_bindings)}",
        "  planned output paths:",
        f"    carrier:    {paths['carrier']}",
        f"    manifest:   {paths['manifest']}",
        f"    test:       {paths['test']}",
        "  expressions to lower:",
    ]
    for role in PlasticityCarrierSpec.REQUIRED_EXPRESSIONS:
        lines.append(f"    {role}: {spec.expressions[role]}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Argument parsing + command dispatch.
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Construct the ``mechdsl-lawgen`` argument parser."""
    parser = argparse.ArgumentParser(
        prog="mechdsl-lawgen",
        description="Emit constitutive-law carriers for the ticonstit target.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    compile_parser = subparsers.add_parser(
        "compile",
        help="Compile a law YAML into a ticonstit carrier.",
        description=(
            "Parse <law.yaml> into a plasticity carrier spec and emit it for the "
            "given target. Use --dry-run to print the emission plan without "
            "writing any files."
        ),
    )
    compile_parser.add_argument("law", type=Path, help="Path to the law YAML file.")
    compile_parser.add_argument(
        "--target",
        choices=_SUPPORTED_TARGETS,
        default="ticonstit",
        help="Emission target (only 'ticonstit' is supported).",
    )
    compile_parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output directory for generated code (required unless --dry-run).",
    )
    compile_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the emission plan and write no files.",
    )
    compile_parser.set_defaults(func=_cmd_compile)
    return parser


def _cmd_compile(args: argparse.Namespace) -> int:
    """Handle ``mechdsl-lawgen compile ...``. Returns the process exit code.

    ``--target`` is validated at parse time via argparse ``choices`` (an unknown
    target already exited with a usage error), so it needs no re-check here.
    """
    # --out is part of the planned paths even in dry-run (nothing is written);
    # a real compile requires it.
    out_dir = args.out if args.out is not None else Path("<out>")
    if not args.dry_run and args.out is None:
        print(
            "error: --out <dir> is required for a real compile "
            "(or pass --dry-run to preview the emission plan).",
            file=sys.stderr,
        )
        return 2

    try:
        spec, raw_expressions = load_carrier_source(args.law)
    except _LawError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    target = TiconstitTarget()

    if args.dry_run:
        print(format_emission_plan(spec, target, out_dir))
        return 0

    return _emit(spec, raw_expressions, target, out_dir)


def _emit(
    spec: PlasticityCarrierSpec,
    raw_expressions: dict[str, str],
    target: TiconstitTarget,
    out_dir: Path,
) -> int:
    """Run the real emission pipeline: lower + guard + budget → carrier + manifest + test.

    Writes three artifacts under ``out_dir`` (mirroring Cycle 0's
    ``ticonstit.generated`` layout): the Taichi carrier module
    (``plasticity/<module>.py``), the ``_manifest.json``, and the self-contained
    generated pytest file (``tests/test_<module>.py``). Every step reuses a frozen
    Phase-1-3 API — :func:`~mechdsl.lawgen.carrier_emitter.emit_carrier` (which runs
    the budget gate), :func:`~mechdsl.lawgen.manifest.emit_manifest` /
    :func:`~mechdsl.lawgen.manifest.write_manifest`, and
    :func:`~mechdsl.lawgen.test_emitter.emit_tests`. A
    :class:`~mechdsl.lawgen.diagnostics.LawgenError` (unsupported node / over-budget)
    is reported to stderr and turned into a non-zero exit — no partial files are
    written, because emission is fail-loud before any write.

    Byte-stability: the emitted carrier, manifest, and test are deterministic for a
    fixed spec (no timestamps / absolute paths embedded), so two runs produce
    byte-identical output — the P4-1 determinism acceptance criterion.
    """
    paths = _planned_paths(out_dir, spec)
    module = snake_case_module_name(spec.name)

    # The canonical generator-input formula whose verbatim SHA-256 is the manifest
    # source_hash. Built from the raw YAML ``R`` string with the ``"R = "`` prefix.
    input_formula = f"R = {raw_expressions['R']}"
    source_hash = compute_input_formula_hash(input_formula)

    # The manifest ``tests`` field records where the generated test lives in the
    # ticonstit tree (a stable repo-relative path, not the scratch --out abspath),
    # so the manifest stays byte-stable regardless of where the compile emits.
    test_manifest_path = f"libs/ticonstit/tests/generated/test_{module}.py"

    try:
        # emit_carrier runs the frozen budget gate (fail-loud) before returning.
        carrier = emit_carrier(
            spec, source_hash=source_hash, generated_by=GENERATED_BY, target=target
        )
        entry = emit_manifest(
            spec,
            input_formula=input_formula,
            target_contract=_TICONSTIT_RUNTIME_CONTRACT,
            exports=spec.name,
            source=f"{module}.py",
            tests=[test_manifest_path],
            required=_required_parameters(spec),
            optional=_optional_parameters(spec),
            # Fail loud if the hashed input formula is not symbolically spec.R — a
            # stale/mistyped formula would otherwise fingerprint the wrong law. Safe
            # to enable here because the emitted law is internally consistent (the
            # YAML spells the saturation param `Q` in both the formula and the
            # parameter list). A `Q` (formula) vs `Q_inf` (material card) divergence
            # is a separate, manifest-parameter-name matter that this
            # formula<->spec check does not touch.
            check_matches_spec=True,
        )
    except LawgenError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except (ValueError, TypeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    # Write the three artifacts. Parent dirs are created by each writer.
    carrier_path = paths["carrier"]
    carrier_path.parent.mkdir(parents=True, exist_ok=True)
    carrier_path.write_text(carrier.source, encoding="utf-8")

    write_manifest([entry], paths["manifest"])

    # The generated test lowers R itself (lowered_r=None): its smoke kernel takes
    # peeq as an argument and pins every *bare* material-parameter name to a local
    # placeholder (``p0 = 1.0``, ``n = 1.0``, …), so it needs the BARE-symbol lowered
    # R, NOT the carrier's rebound ``self.<param>`` form. Feeding the rebound R here
    # would emit ``self.p0`` into the kernel with no ``self`` in scope
    # (TaichiNameError). The rebound form is for the carrier class only.
    emit_tests(spec, lowered_r=None, target_test_path=paths["test"])

    print(
        f"mechdsl-lawgen: emitted {spec.name} carrier\n"
        f"  carrier:  {carrier_path}\n"
        f"  manifest: {paths['manifest']}\n"
        f"  test:     {paths['test']}\n"
        f"  source_hash: {source_hash}"
    )
    return 0


# The runtime contract the SwiftVoce carrier implements (the ``target_contract``
# recorded in the manifest). This is the *runtime* contract name, deliberately distinct
# from ``TiconstitTarget.contract_id`` (the emission-contract id).
_TICONSTIT_RUNTIME_CONTRACT: str = "VoceHardeningModel"

#: The Voce base parameters that are always required. Any remaining spec parameter
#: is optional (the Swift power-law term / rate / thermal extras).
_REQUIRED_PARAMETER_NAMES: frozenset[str] = frozenset({"sigma0", "Q", "Q_inf", "b"})


def _required_parameters(spec: PlasticityCarrierSpec) -> list[str]:
    """The spec parameters that are Voce-base required, in spec order."""
    return [p for p in spec.parameters if p in _REQUIRED_PARAMETER_NAMES]


def _optional_parameters(spec: PlasticityCarrierSpec) -> list[str]:
    """The spec parameters that are optional (Swift/rate/thermal), in spec order."""
    return [p for p in spec.parameters if p not in _REQUIRED_PARAMETER_NAMES]


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns a process exit code (0 = success)."""
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = args.func
    result: int = handler(args)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
