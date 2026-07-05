"""Spec-driven Taichi carrier-class emitter (Task P4-1).

MFront-mimic Cycle M0, Phase 4 (``dev/plans/mfront_cycleM0.md`` lines 114-116).

This is the *class emitter* the Phase-2 handoff (note 4) deferred to Phase 3/4:
the piece that assembles a complete, self-contained Taichi module — a
``class <Name>`` with its ``@ti.func`` methods — from a
:class:`~mechdsl.lawgen.contracts.PlasticityCarrierSpec`. The Phase-2 lowerer
(:func:`~mechdsl.lawgen.sympy_to_taichi.lower_expression`) turns a scalar
``sympy.Expr`` into Taichi expression *lines* that reference **bare** symbol
names (``sigma0``, ``p``, ``n``); this module is what maps those bare names onto
the class contract — material parameters → ``self.<param>``, free variables →
method arguments — and wraps the lowered lines in the ``get_R`` / ``get_dR`` /
``get_H`` / ``get_dH`` / ``get_Q`` / ``get_dQ`` / ``eval_components`` methods that
mirror Cycle 0's hand-authored ``swift_voce.py``.

Contract emitted (matches Cycle 0 ``ticonstit.generated.plasticity.swift_voce``)
--------------------------------------------------------------------------------
::

    @ti.data_oriented
    class <Name>:
        def __init__(self, params_dict, ti_type=ti.f64): ...   # binds self.<param>
        @ti.func get_R(peeq, yield_scale=1.0)
        @ti.func get_dR(peeq, yield_scale=1.0)
        @ti.func get_H(edot)
        @ti.func get_dH(edot)
        @ti.func get_Q(T)
        @ti.func get_dQ(T)
        @ti.func eval_components(peeq, edot, T, yield_scale=1.0)
            -> (R, rate, thermal, dR, drate, dthermal)

Design rules
------------
* **Per-method lowering** (Phase-2 handoff note 2). Each ``get_*`` method is
  lowered *independently* — the R/dR/H/dH/Q/dQ expressions are never lowered as
  one batch — so no cross-method CSE reorganises one method's structure into
  another's. This keeps each method's shape close to Cycle 0's hand-authored
  method (the P4-2 equivalence gate is *numerical*, rtol=1e-10, so the derivative
  reorganisation batching would introduce is unnecessary and undesirable).
* **Auto-differentiated derivatives.** ``get_dR`` / ``get_dH`` / ``get_dQ`` are
  ``sympy.diff`` of the corresponding factor w.r.t. that factor's *primary*
  variable (R,dR → ``peeq``; H,dH → ``edot``; Q,dQ → ``T``), then lowered with
  the same guards. The generator never hand-writes a derivative — it differentiates
  the authored factor, so a factor and its derivative can never drift.
* **Frozen Phase-2 APIs, reused verbatim.** ``lower_expression(exprs, *,
  guards=True, target=...)``, :class:`~mechdsl.lawgen.sympy_to_taichi.LoweredExpr`,
  and :meth:`~mechdsl.lawgen.budgets.BudgetChecker.check_all` are called by name,
  never re-implemented. The budget gate runs (fail-loud via the P3-1
  :class:`~mechdsl.lawgen.diagnostics.LawgenError`) BEFORE any source is returned.
* **Generated file imports Taichi + stdlib only.** The emitted module never
  imports ``mechdsl``, ``sympy``, ``ticonstit``, or NumerixWeave — it is a pure
  Taichi runtime carrier (INV-DG-1). This module asserts that invariant on its
  own output before returning it.
* **Byte-stable.** Given a fixed ``spec`` (and SymPy/mechdsl version) the emitted
  string is deterministic: the lowerer is deterministic, the parameter order is
  ``spec.parameters`` order, and no timestamps / absolute paths are embedded.

Symbol → binding map
--------------------
The lowered lines carry bare names. :func:`_rebind` rewrites them, using SymPy's
own token boundaries (never a regex over the source string — R4): each material
parameter symbol maps to ``self.<param>`` and each free-variable symbol maps to
the method argument name it is bound to (``p`` → ``peeq``, ``edot`` → ``edot``,
``T`` → ``T``). The rebinding is applied to the SymPy *expression* (via
``expr.subs`` with placeholder symbols) so it is structural, not textual.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sympy as sp

from mechdsl.lawgen.budgets import BudgetChecker
from mechdsl.lawgen.contracts import PlasticityCarrierSpec, TiconstitTarget
from mechdsl.lawgen.sympy_to_taichi import LoweredExpr, lower_expression

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = [
    "METHOD_PRIMARY_VARIABLE",
    "CarrierEmitResult",
    "emit_carrier",
    "snake_case_module_name",
]

# The free-variable name each method differentiates / evaluates against, and the
# Taichi argument name that variable is emitted as. R/dR are functions of the
# accumulated plastic strain (spec variable ``p``, emitted as ``peeq`` to match
# Cycle 0's method signature); H/dH of the plastic strain rate ``edot``; Q/dQ of
# the temperature ``T``. R/H/Q are three INDEPENDENT factors — dR is d(R)/d(peeq),
# NOT H — each auto-differentiated w.r.t. its own primary variable.
METHOD_PRIMARY_VARIABLE: dict[str, str] = {"R": "p", "H": "edot", "Q": "T"}

# The Taichi method-argument name each primary free variable is emitted as. The
# spec binds ``p`` (accumulated plastic strain); Cycle 0's ``get_R``/``get_dR``
# name that argument ``peeq``. ``edot``/``T`` keep their spec names.
_VARIABLE_ARGUMENT_NAME: dict[str, str] = {"p": "peeq", "edot": "edot", "T": "T"}

# Indentation units (4-space, PEP 8). Method bodies live two levels in (class +
# method); ``eval_components`` call lines likewise.
_I1 = "    "
_I2 = "        "

# The ``ti.f64`` yield-scale annotation Cycle 0's get_R/get_dR use on the
# ``yield_scale`` argument.
_YIELD_SCALE_SIG = "yield_scale: ti.f64 = 1.0"


class CarrierEmitResult:
    """The emitted carrier module plus the per-method lowered results.

    ``source`` is the complete, ready-to-write Taichi module string. The
    ``lowered_by_method`` map (role → :class:`LoweredExpr`) is exposed so the
    caller (the CLI) can feed the *same* lowered results into the budget gate and
    reuse the lowered ``R`` for the generated test's JIT smoke kernel — without
    lowering twice.
    """

    __slots__ = ("lowered_by_method", "source")

    def __init__(self, source: str, lowered_by_method: dict[str, LoweredExpr]) -> None:
        self.source = source
        self.lowered_by_method = lowered_by_method


def snake_case_module_name(name: str) -> str:
    """Return the snake_case module filename stem for a carrier class ``name``.

    The generated *class* is ``spec.name`` (e.g. ``"SwiftVoce"``); Cycle 0's
    *module* is snake_case (``swift_voce.py``), decoupled from the class name (the
    manifest ``source`` field records the mapping). This converts a CamelCase /
    mixed identifier to snake_case: ``"SwiftVoce"`` → ``"swift_voce"``,
    ``"J2Plasticity"`` → ``"j2_plasticity"``. An already-snake name is returned
    unchanged (lowercased). ``name`` is a validated Python identifier (the CLI's
    F4 gate), so the result is always a valid module stem.
    """
    chars: list[str] = []
    for index, char in enumerate(name):
        # Insert a separator before an uppercase letter that follows a lowercase
        # letter or a digit (``SwiftVoce`` → ``Swift_Voce``) or before an
        # uppercase letter that starts a new word in an acronym run followed by a
        # lowercase (``HTMLParser`` → ``HTML_Parser``). Underscores already
        # present are preserved (never doubled).
        if char.isupper() and index > 0:
            prev = name[index - 1]
            nxt = name[index + 1] if index + 1 < len(name) else ""
            if prev != "_" and (prev.islower() or prev.isdigit() or (nxt.islower() and nxt != "")):
                chars.append("_")
        chars.append(char.lower())
    return "".join(chars)


def _diff_primary(spec: PlasticityCarrierSpec, role: str) -> sp.Symbol | None:
    """Return the SymPy symbol ``role``'s derivative differentiates w.r.t., or ``None``.

    Resolves ``role``'s conventional primary variable
    (:data:`METHOD_PRIMARY_VARIABLE`) against the spec's ``variable_bindings``.
    Returns the bound symbol when the variable exists, else ``None`` — a factor
    whose conventional primary the spec does not bind has no dependence on it, so
    its derivative is simply the zero expression (differentiating w.r.t. a fresh
    symbol the factor does not contain yields ``0``); the caller then differentiates
    against that binding-or-fallback and lowers the result.
    """
    primary_name = METHOD_PRIMARY_VARIABLE[role]
    return spec.variable_bindings.get(primary_name)


def _rebind_map(spec: PlasticityCarrierSpec) -> dict[sp.Symbol, sp.Symbol]:
    """Map each spec symbol to the placeholder symbol carrying its emitted name.

    Every material parameter ``P`` maps to a fresh symbol named ``self.P`` and
    every free variable ``v`` maps to a fresh symbol named after its method
    argument (``p`` → ``peeq``; ``edot``/``T`` unchanged). Substituting these into
    the SymPy expression *before* lowering makes the rebinding structural (SymPy
    token boundaries, never a regex over the printed source — R4): the lowerer then
    prints ``self.sigma0`` / ``peeq`` directly. A ``self.<param>`` name is not a
    valid Python identifier, but ``sympy.Symbol`` accepts any string as a name and
    the printer emits it verbatim, so ``self.sigma0`` renders exactly.
    """
    mapping: dict[sp.Symbol, sp.Symbol] = {}
    for param in spec.parameters:
        mapping[sp.Symbol(param)] = sp.Symbol(f"self.{param}")
    for var_name, var_symbol in spec.variable_bindings.items():
        emitted = _VARIABLE_ARGUMENT_NAME.get(var_name, var_name)
        if emitted != var_name:
            mapping[var_symbol] = sp.Symbol(emitted)
    return mapping


def _lower_rebound(
    expr: sp.Expr,
    rebind: Mapping[sp.Symbol, sp.Symbol],
    target: TiconstitTarget,
) -> LoweredExpr:
    """Rebind ``expr``'s symbols to their emitted names, then lower it (guarded).

    The substitution is applied to the SymPy expression, so the lowerer sees
    ``self.sigma0`` / ``peeq`` as ordinary symbol names and prints them verbatim.
    Lowering is per-method (a single ``expr``), guards on (the production path the
    P4-2 gate measures), and uses the emission ``target`` so its
    ``max_piecewise_branches`` knob gates any ``Piecewise``.
    """
    rebound = expr.subs(rebind)
    return lower_expression(rebound, guards=True, target=target)


def _render_method(
    name: str,
    signature: str,
    lowered: LoweredExpr,
    *,
    wrap_yield_scale: bool,
) -> str:
    """Render one ``@ti.func`` method from a lowered single-expression result.

    ``signature`` is the full argument list after ``self`` (e.g. ``"peeq,
    yield_scale: ti.f64 = 1.0"``). The lowered CSE temporaries become local
    assignment lines and the single return line becomes the method's ``return``.
    When ``wrap_yield_scale`` is set the return is multiplied by ``yield_scale``
    (Cycle 0's ``get_R``/``get_dR`` scale their whole result by it); otherwise the
    return is emitted as-is (``get_H``/``get_dH``/``get_Q``/``get_dQ`` take no
    yield scale).
    """
    lines = [f"{_I1}@ti.func", f"{_I1}def {name}(self, {signature}):"]
    for temporary in lowered.temporaries:
        lines.append(f"{_I2}{temporary}")
    # A single expression lowers to exactly one return line.
    (ret,) = lowered.returns
    if wrap_yield_scale:
        lines.append(f"{_I2}return yield_scale * ({ret})")
    else:
        lines.append(f"{_I2}return {ret}")
    return "\n".join(lines)


def _render_init(spec: PlasticityCarrierSpec) -> str:
    """Render ``__init__`` binding every material parameter to ``self.<param>``.

    Each parameter is read from ``params_dict`` and stored as ``float`` on the
    instance (matching Cycle 0's ``self.sigma0 = float(params_dict["sigma0"])``
    idiom), in ``spec.parameters`` order so the emission is deterministic. The
    Taichi scalar type is captured as ``self.float_ti`` (Cycle 0's field name) so
    a caller can honour a non-default ``ti_type``.
    """
    lines = [
        f"{_I1}def __init__(self, params_dict, ti_type=ti.f64):",
        f"{_I2}self.float_ti = ti_type",
    ]
    for param in spec.parameters:
        lines.append(f'{_I2}self.{param} = float(params_dict["{param}"])')
    return "\n".join(lines)


def _render_eval_components() -> str:
    """Render ``eval_components`` delegating to the six factor methods.

    Returns the six-tuple ``(R, rate, thermal, dR, drate, dthermal)`` in Cycle 0's
    order by calling ``get_R``/``get_H``/``get_Q`` and their derivatives. This is a
    fixed dispatch method (no lowering), so it is a literal template — the only
    per-law variation is already captured in the six ``get_*`` methods it calls.
    """
    return "\n".join(
        [
            f"{_I1}@ti.func",
            f"{_I1}def eval_components(self, peeq, edot, T, {_YIELD_SCALE_SIG}):",
            f"{_I2}R = self.get_R(peeq, yield_scale)",
            f"{_I2}dR = self.get_dR(peeq, yield_scale)",
            f"{_I2}rate = self.get_H(edot)",
            f"{_I2}drate = self.get_dH(edot)",
            f"{_I2}thermal = self.get_Q(T)",
            f"{_I2}dthermal = self.get_dQ(T)",
            f"{_I2}return R, rate, thermal, dR, drate, dthermal",
        ]
    )


def _render_header(spec: PlasticityCarrierSpec, *, source_hash: str, generated_by: str) -> str:
    """Render the ``# AUTO-GENERATED`` banner + module docstring + ``import taichi``.

    The banner stamps ``generated_by`` and the ``source_hash`` (the input-formula
    hash, supplied by the caller) exactly as Cycle 0's header does, so the emitted
    file records its provenance. The docstring names the source law and its
    contract. Only ``import taichi as ti`` follows — no ``mechdsl`` / ``sympy`` /
    ``ticonstit`` import (INV-DG-1).
    """
    return (
        f"# AUTO-GENERATED by {generated_by}. source_hash: {source_hash}\n"
        f'"""{spec.name} isotropic hardening law (generated plasticity carrier).\n'
        "\n"
        "DO NOT EDIT BY HAND — regenerate via ``mechdsl-lawgen compile`` from the\n"
        "authoritative law YAML. This is a pure Taichi runtime carrier: it imports\n"
        "only Taichi (INV-DG-1) — never SymPy, MechDSL, or ticonstit.\n"
        "\n"
        "Contract (matches the Cycle 0 hand-authored SwiftVoce)::\n"
        "\n"
        "    __init__(params_dict, ti_type=ti.f64)\n"
        "    @ti.func get_R(peeq, yield_scale=1.0)\n"
        "    @ti.func get_dR(peeq, yield_scale=1.0)\n"
        "    @ti.func get_H(edot)\n"
        "    @ti.func get_dH(edot)\n"
        "    @ti.func get_Q(T)\n"
        "    @ti.func get_dQ(T)\n"
        "    @ti.func eval_components(peeq, edot, T, yield_scale=1.0)\n"
        "        -> (R, rate, thermal, dR, drate, dthermal)\n"
        '"""\n'
        "\n"
        "import taichi as ti"
    )


def emit_carrier(
    spec: PlasticityCarrierSpec,
    *,
    source_hash: str,
    generated_by: str,
    target: TiconstitTarget | None = None,
) -> CarrierEmitResult:
    """Emit the complete Taichi carrier module for ``spec``.

    Pipeline
    --------
    1. Build the symbol → emitted-name rebinding (``self.<param>`` / method args).
    2. Per method, differentiate (for dR/dH/dQ) and lower the rebound expression
       **independently** (guards on, per-method — no cross-method CSE).
    3. Run the frozen Phase-2 budget gate over all six lowered methods; a breach
       raises a collect-all :class:`~mechdsl.lawgen.diagnostics.LawgenError`
       BEFORE any source is returned (fail-loud, R2).
    4. Assemble the header, ``__init__``, the six ``get_*`` methods, and
       ``eval_components`` into one module string.
    5. Assert the emitted module imports Taichi only (INV-DG-1) before returning.

    Parameters
    ----------
    spec:
        The carrier law. ``spec.name`` is the emitted class; ``spec.parameters``
        become ``self.<param>``; ``spec.R``/``spec.H``/``spec.Q`` are the three
        factors, each auto-differentiated w.r.t. its own primary variable for the
        ``get_d*`` methods.
    source_hash:
        The input-formula hash to stamp in the banner (from
        :func:`~mechdsl.lawgen.manifest.compute_input_formula_hash`). Recorded
        verbatim — this function does not recompute it.
    generated_by:
        The generator + version string for the banner (e.g.
        :data:`~mechdsl.lawgen.manifest.GENERATED_BY`).
    target:
        Emission target whose budget knobs gate the lowering. Defaults to a plain
        :class:`~mechdsl.lawgen.contracts.TiconstitTarget`.

    Returns
    -------
    CarrierEmitResult
        The module ``source`` and the per-method ``lowered_by_method`` map.

    Raises
    ------
    LawgenError
        If any factor contains an unsupported node or any method exceeds a JIT
        budget knob (collect-all, before any source is produced).
    """
    active_target = target if target is not None else TiconstitTarget()
    rebind = _rebind_map(spec)

    # --- Per-method lowering (independent — no cross-method CSE) --------------
    lowered_by_method: dict[str, LoweredExpr] = {}
    for role in ("R", "H", "Q"):
        factor = spec.expressions[role]
        lowered_by_method[role] = _lower_rebound(factor, rebind, active_target)

        # Derivative w.r.t. this factor's own primary variable. A missing binding
        # yields a zero derivative (fresh symbol not present in the factor).
        primary = _diff_primary(spec, role)
        diff_symbol = primary if primary is not None else sp.Symbol(METHOD_PRIMARY_VARIABLE[role])
        derivative = sp.diff(factor, diff_symbol)
        lowered_by_method[f"d{role}"] = _lower_rebound(derivative, rebind, active_target)

    # --- Frozen Phase-2 budget gate (fail-loud BEFORE emission) --------------
    # Keyed by method name so a breach names the offending function. The
    # expression map drives the per-expression knobs; the lowered map the
    # per-function / whole-class knobs.
    expr_by_method: dict[str, sp.Expr] = {}
    for role in ("R", "H", "Q"):
        rebound_factor = spec.expressions[role].subs(rebind)
        expr_by_method[role] = rebound_factor
        primary = _diff_primary(spec, role)
        diff_symbol = primary if primary is not None else sp.Symbol(METHOD_PRIMARY_VARIABLE[role])
        expr_by_method[f"d{role}"] = sp.diff(spec.expressions[role], diff_symbol).subs(rebind)
    BudgetChecker(active_target).check_all(expr_by_method, lowered_by_method)

    # --- Assemble the module --------------------------------------------------
    header = _render_header(spec, source_hash=source_hash, generated_by=generated_by)
    init = _render_init(spec)
    method_blocks = [
        _render_method(
            "get_R", f"peeq, {_YIELD_SCALE_SIG}", lowered_by_method["R"], wrap_yield_scale=True
        ),
        _render_method(
            "get_dR", f"peeq, {_YIELD_SCALE_SIG}", lowered_by_method["dR"], wrap_yield_scale=True
        ),
        _render_method("get_H", "edot", lowered_by_method["H"], wrap_yield_scale=False),
        _render_method("get_dH", "edot", lowered_by_method["dH"], wrap_yield_scale=False),
        _render_method("get_Q", "T", lowered_by_method["Q"], wrap_yield_scale=False),
        _render_method("get_dQ", "T", lowered_by_method["dQ"], wrap_yield_scale=False),
    ]
    eval_components = _render_eval_components()

    body_blocks = [init, *method_blocks, eval_components]
    class_block = f"@ti.data_oriented\nclass {spec.name}:\n" + "\n\n".join(body_blocks)

    source = f"{header}\n\n\n{class_block}\n"

    _assert_taichi_only(source, spec.name)
    return CarrierEmitResult(source=source, lowered_by_method=lowered_by_method)


# Modules the generated runtime carrier must never import (INV-DG-1 / R3): the
# offline generator (SymPy, MechDSL) and the consumer (ticonstit / NumerixWeave).
_FORBIDDEN_IMPORT_TOKENS: tuple[str, ...] = ("sympy", "mechdsl", "ticonstit", "numerixweave")


def _assert_taichi_only(source: str, name: str) -> None:
    """Fail loud if the emitted module imports anything but Taichi + stdlib.

    Scans every ``import`` / ``from ... import`` line for a forbidden top-level
    module (:data:`_FORBIDDEN_IMPORT_TOKENS`). The generated carrier is a pure
    Taichi runtime artifact (INV-DG-1): a stray ``import sympy`` / ``import
    mechdsl`` would break the MechDSL↔NumerixWeave dependency DAG that P4-3's guard
    enforces. Runs on the emitter's own output as a self-check before the source
    is ever written, so a regression fails here rather than in the cross-repo DAG
    gate.
    """
    for raw_line in source.splitlines():
        line = raw_line.strip()
        if not (line.startswith("import ") or line.startswith("from ")):
            continue
        # The imported top-level module is the token after ``import`` / ``from``.
        module = line.split(None, 2)[1].split(".", 1)[0].lower()
        if module in _FORBIDDEN_IMPORT_TOKENS:
            raise AssertionError(
                f"emitted carrier {name!r} imports forbidden module {module!r} "
                f"(line: {line!r}); a generated ticonstit runtime carrier must import "
                "only Taichi and the Python standard library (INV-DG-1)."
            )
