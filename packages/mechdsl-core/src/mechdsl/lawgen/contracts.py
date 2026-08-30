"""Lawgen emission contracts — the seam between the CLI and the Phase 2 lowerer.

Part of the MechDSL lawgen pipeline (YAML law spec → restricted SymPy →
Taichi carrier).

This module defines the two frozen dataclasses that every downstream lowerer
task and the end-to-end test consume:

* :class:`TiconstitTarget` — the ``ticonstit`` emission *target profile*: the
  frozen contract id, the generated-code package, the default Taichi scalar
  type, and the six JIT budget knobs. The budget-knob defaults MUST stay in
  lock-step with ``budgets.py`` — which references these fields by name.
* :class:`PlasticityCarrierSpec` — a single plasticity carrier law: its name,
  material parameters, the R/H/Q constitutive expressions, and the free-variable
  bindings (``p``, ``edot``, ``T``).

Per MechDSL IR discipline (``.claude/rules/ir.md``) both dataclasses are
immutable (``frozen=True``) and validate at construction time in
``__post_init__``. There is deliberately **no** NumerixWeave / ``ticonstit``
import here — the MechDSL↔NumerixWeave seam is committed artifacts only
(plan risk R5). SymPy is a first-class mechdsl-core dependency and is the
natural carrier for the R/H/Q expressions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import TYPE_CHECKING

# SymPy is imported at runtime because ``PlasticityCarrierSpec.__post_init__``
# validates value types with ``isinstance(v, sp.Expr)`` / ``isinstance(v,
# sp.Symbol)``. SymPy is a first-class mechdsl-core dependency, so the
# runtime import is cheap and expected.
import sympy as sp

if TYPE_CHECKING:
    from collections.abc import Mapping

# ---------------------------------------------------------------------------
# Frozen contract identity.
#
# The canonical contract id is the *only* accepted value for
# ``TiconstitTarget.contract_id``. It is module-level so downstream code can
# reference the constant instead of hard-coding the string literal.
# ---------------------------------------------------------------------------

TICONSTIT_CONTRACT_ID: str = "ticonstit.plasticity_carrier.v1"
# Canonical, frozen ticonstit emission-contract id.

TICONSTIT_PACKAGE: str = "ticonstit.generated"
# Default Python package for ticonstit-generated code.


# ---------------------------------------------------------------------------
# TiconstitTarget — emission target profile.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TiconstitTarget:
    """The ``ticonstit`` emission target profile.

    Carries the frozen contract identity, the generated-code package, the
    default Taichi scalar type, and the six JIT budget knobs the Phase 2
    lowerer enforces.

    ``ti_type_default`` defaults to ``"ti.f64"``: MechDSL's tension-positive
    conventions (``07-CONVENTIONS.md``) and its verification tolerances
    (displacement diff < 1e-10) require double precision, so f64 is the
    sensible default scalar type for generated carriers.

    The six budget-knob defaults are defined by the MechDSL lawgen target
    contract and are frozen: ``budgets.py`` references these field names, so
    they must not be renamed or have their defaults drift.
    """

    contract_id: str = TICONSTIT_CONTRACT_ID
    package: str = TICONSTIT_PACKAGE
    ti_type_default: str = "ti.f64"

    # --- JIT budget knobs (defaults frozen) ---
    max_expr_ops: int = 400
    max_cse_temps_per_func: int = 96
    max_func_lines: int = 220
    max_total_generated_lines_per_class: int = 900
    max_piecewise_branches: int = 8
    max_pow_with_symbolic_exponent: int = 12

    def __post_init__(self) -> None:
        # The three identity fields must be non-empty *str* — a list or any
        # other truthy non-string is rejected, not silently accepted.
        for str_field in ("contract_id", "package", "ti_type_default"):
            value = getattr(self, str_field)
            if not isinstance(value, str) or not value:
                raise TypeError(
                    f"TiconstitTarget.{str_field} must be a non-empty string, "
                    f"got {type(value).__name__} {value!r}."
                )
        if self.contract_id != TICONSTIT_CONTRACT_ID:
            raise ValueError(
                f"TiconstitTarget.contract_id={self.contract_id!r} is not the "
                f"canonical ticonstit contract id; the only accepted value is "
                f"{TICONSTIT_CONTRACT_ID!r}."
            )
        # Each budget knob must be a genuine positive int. ``type(v) is int``
        # rejects ``bool`` (``type(True) is bool``) and ``float`` (``1.5``) that
        # an ``isinstance`` / ``> 0`` check would silently wave through.
        for knob in (
            "max_expr_ops",
            "max_cse_temps_per_func",
            "max_func_lines",
            "max_total_generated_lines_per_class",
            "max_piecewise_branches",
            "max_pow_with_symbolic_exponent",
        ):
            value = getattr(self, knob)
            if type(value) is not int:
                raise TypeError(
                    f"TiconstitTarget.{knob} must be an int, got {type(value).__name__} {value!r}."
                )
            if value <= 0:
                raise ValueError(f"TiconstitTarget.{knob}={value!r} must be a positive integer.")


# ---------------------------------------------------------------------------
# PlasticityCarrierSpec — one plasticity carrier law.
# ---------------------------------------------------------------------------


def _freeze_mapping(raw: Mapping[str, sp.Expr] | None) -> Mapping[str, sp.Expr]:
    """Wrap ``raw`` as a read-only ``MappingProxyType``.

    Frozen dataclasses block attribute reassignment but not in-place mutation
    of a stored dict. Wrapping the R/H/Q expression map and the variable
    bindings in a ``MappingProxyType`` (cached via ``object.__setattr__`` in
    ``__post_init__``) keeps the spec genuinely immutable, matching the IR
    discipline used across ``mechdsl.ir``.
    """
    return MappingProxyType(dict(raw or {}))


@dataclass(frozen=True)
class PlasticityCarrierSpec:
    """A single plasticity carrier law, ready for Phase 2 lowering.

    Fields
    ------
    name:
        Identifier for the carrier (drives the generated class/function name).
    parameters:
        Material parameter names (e.g. ``("sigma_y0", "K", "n")``), stored as a
        tuple so the ordering is stable for codegen.
    expressions:
        The three constitutive expressions keyed exactly by ``"R"``, ``"H"``,
        and ``"Q"`` as SymPy expressions. Storing them in a map keyed by role
        preserves *which is which* through lowering. All three keys are
        required.
    variable_bindings:
        Free-variable name → SymPy symbol map (accumulated plastic strain ``p``,
        strain rate ``edot``, temperature ``T``). These are the runtime inputs
        the generated carrier is a function of.
    monotone_check:
        When ``True``, the P3-2 test emitter appends a monotonicity assertion to
        the generated test file — checking that the hardening ``R`` is
        non-decreasing in the accumulated plastic strain across the sample
        points. Defaults to ``False`` (no monotonicity block emitted), so every
        existing construction site (the CLI, Phase-1 tests) that omits it keeps
        working unchanged. It is a plain flag, not a SymPy object, so it is
        validated as a genuine ``bool`` in ``__post_init__``.

    The R/H/Q expressions and variable bindings are stored as SymPy objects (not
    strings) because Phase 2 routes them through ``taichi_printer``, which
    consumes SymPy expressions directly.
    """

    #: The three role keys every carrier must provide, in canonical order.
    REQUIRED_EXPRESSIONS: tuple[str, ...] = field(
        default=("R", "H", "Q"), init=False, repr=False, compare=False
    )

    name: str
    parameters: tuple[str, ...]
    expressions: Mapping[str, sp.Expr]
    variable_bindings: Mapping[str, sp.Symbol]
    monotone_check: bool = False

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("PlasticityCarrierSpec.name must be a non-empty string.")
        if isinstance(self.parameters, (str, bytes)):
            # A bare str/bytes is iterable, so tuple() would silently split it
            # into per-character garbage names (e.g. "Kn" -> ('K', 'n')).
            # Reject it up front; parameters must be a sequence of name strings.
            raise ValueError(
                f"PlasticityCarrierSpec(name={self.name!r}) parameters must be a "
                f"sequence of parameter-name strings, not a single "
                f"{type(self.parameters).__name__}; got {self.parameters!r}."
            )
        if not self.parameters:
            raise ValueError(
                f"PlasticityCarrierSpec(name={self.name!r}) requires at least one "
                "material parameter."
            )

        missing = [k for k in self.REQUIRED_EXPRESSIONS if k not in self.expressions]
        if missing:
            raise ValueError(
                f"PlasticityCarrierSpec(name={self.name!r}) is missing required "
                f"expression(s) {missing}; all of {list(self.REQUIRED_EXPRESSIONS)} "
                "must be supplied."
            )
        if not self.variable_bindings:
            raise ValueError(
                f"PlasticityCarrierSpec(name={self.name!r}) requires at least one "
                "variable binding (e.g. p, edot, T)."
            )

        # Normalise parameters to a tuple and freeze the mapping fields so the
        # spec is genuinely immutable (frozen=True alone does not stop mutation
        # of a stored dict).
        object.__setattr__(self, "parameters", tuple(self.parameters))
        object.__setattr__(self, "expressions", _freeze_mapping(self.expressions))
        object.__setattr__(self, "variable_bindings", _freeze_mapping(self.variable_bindings))

        # Validate value types after freezing. Keys must be non-empty
        # strings; every expression value must be an ``sp.Expr`` and every
        # binding an ``sp.Symbol``. Requiring ``sp.Expr`` also closes the
        # alias-mutation hole — a mutable ``list``/``dict`` value is not an
        # ``sp.Expr``, so it can never be stored on the spec.
        for key, expr in self.expressions.items():
            if not isinstance(key, str) or not key:
                raise TypeError(
                    f"PlasticityCarrierSpec(name={self.name!r}) expression keys must be "
                    f"non-empty strings; got {key!r}."
                )
            if not isinstance(expr, sp.Expr):
                raise TypeError(
                    f"PlasticityCarrierSpec(name={self.name!r}) expression {key!r} must be a "
                    f"sympy.Expr, got {type(expr).__name__} {expr!r}."
                )
        for key, sym in self.variable_bindings.items():
            if not isinstance(key, str) or not key:
                raise TypeError(
                    f"PlasticityCarrierSpec(name={self.name!r}) variable-binding keys must be "
                    f"non-empty strings; got {key!r}."
                )
            if not isinstance(sym, sp.Symbol):
                raise TypeError(
                    f"PlasticityCarrierSpec(name={self.name!r}) variable binding {key!r} must be a "
                    f"sympy.Symbol, got {type(sym).__name__} {sym!r}."
                )

        # ``monotone_check`` is an emit-time flag, not a SymPy object; it must
        # be a genuine ``bool``. ``type(v) is bool`` rejects a truthy int/str that
        # an ``isinstance`` check would silently wave through.
        if type(self.monotone_check) is not bool:
            raise TypeError(
                f"PlasticityCarrierSpec(name={self.name!r}) monotone_check must be a bool, got "
                f"{type(self.monotone_check).__name__} {self.monotone_check!r}."
            )

    @property
    def R(self) -> sp.Expr:
        """The isotropic-hardening flow-stress expression ``R``."""
        return self.expressions["R"]

    @property
    def H(self) -> sp.Expr:
        """The hardening-modulus expression ``H``."""
        return self.expressions["H"]

    @property
    def Q(self) -> sp.Expr:
        """The saturation / rate-term expression ``Q``."""
        return self.expressions["Q"]
