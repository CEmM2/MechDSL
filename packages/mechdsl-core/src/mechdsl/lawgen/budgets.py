"""Pre-emission JIT budget gate for the lawgen lowerer (Task P2-2).

Part of the MechDSL lawgen pipeline (YAML law spec → restricted SymPy →
Taichi carrier).

This module is the *gate* that stands between the deterministic lowerer
(:mod:`mechdsl.lawgen.sympy_to_taichi`, P2-1) and any Taichi emission
(Phase 3/4). It counts six quantities over a law's SymPy expressions and its
lowered source lines, and **fails loud** (R2) the moment any of them exceeds the
matching :class:`~mechdsl.lawgen.contracts.TiconstitTarget` budget knob. No
Taichi source is produced here — this is purely a pre-emission check, so an
over-budget law never reaches the printer.

The six budgets (defaults from ``TiconstitTarget``; the target's knobs override)
-------------------------------------------------------------------------------
============================================  ================================
Budget knob (``TiconstitTarget`` field)       What it counts
============================================  ================================
``max_expr_ops``                              ``sp.count_ops`` of each law
                                              expression (checked per
                                              expression — the *worst* wins).
``max_cse_temps_per_func``                    ``len(lowered.temporaries)`` for
                                              each emitted function.
``max_func_lines``                            ``len(temporaries) + len(returns)``
                                              — the emitted line count of one
                                              function.
``max_total_generated_lines_per_class``       the sum of ``max_func_lines`` over
                                              every emitted function of the law.
``max_piecewise_branches``                    branch count of the largest
                                              ``sp.Piecewise`` in each
                                              expression.
``max_pow_with_symbolic_exponent``            number of ``sp.Pow`` nodes with a
                                              non-integer exponent, across each
                                              expression.
============================================  ================================

Error contract (P3-1 — collect-all)
-----------------------------------
:meth:`BudgetChecker.check_all` runs **all six** budget checks over **all**
expressions/functions and accumulates *every* violation into a
:class:`~mechdsl.lawgen.diagnostics.DiagnosticCollector`, then raises a single
:class:`~mechdsl.lawgen.diagnostics.LawgenError` carrying the whole batch (P3-1
collect-all: the user sees every over-budget knob in one run, not just the first).
Each budget violation still carries the structured
``"<knob> budget exceeded: <measured> > <limit>"`` text — built by
:meth:`BudgetError.for_budget` — as the diagnostic's ``reason`` (so the measured
value AND the limit are always present), while :class:`BudgetError` itself, which
*is-a* :class:`~mechdsl.codegen.einsum_optimizer.BudgetExceededError`, remains the
per-violation formatter and the public budget-error type. This mirrors how
:class:`mechdsl.lowering.fe_localise.LocalisationError` subclasses the broader
``UnsupportedError``.

Reusability for downstream phases (P2-3 / P2-4 / P3)
----------------------------------------------------
The three counters are module-level pure functions
(:func:`count_expr_ops`, :func:`count_piecewise_branches`,
:func:`count_pow_symbolic_exponent`) so they are independently testable and can
be reused outside :class:`BudgetChecker`. :class:`BudgetChecker` binds one
:class:`TiconstitTarget` and exposes :meth:`BudgetChecker.check_all`, which
Phase 3/4 call *before* emission.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

import sympy as sp

# Extend the repo's single message-only budget error rather than inventing a
# parallel hierarchy. ``BudgetError`` IS-A ``BudgetExceededError`` so callers
# that already catch the shared budget error keep working, while lawgen code
# can catch the narrower lawgen-specific type.
from mechdsl.codegen.einsum_optimizer import BudgetExceededError
from mechdsl.lawgen.contracts import TiconstitTarget
from mechdsl.lawgen.diagnostics import DiagnosticCollector, LawgenDiagnostic

if TYPE_CHECKING:
    from collections.abc import Iterable

    from mechdsl.lawgen.sympy_to_taichi import LoweredExpr

__all__ = [
    "BudgetChecker",
    "BudgetError",
    "count_expr_ops",
    "count_piecewise_branches",
    "count_pow_symbolic_exponent",
]


class BudgetError(BudgetExceededError):
    """Raised when a lawgen expression/emission exceeds a JIT budget knob.

    A lawgen-specific budget error that *is-a*
    :class:`~mechdsl.codegen.einsum_optimizer.BudgetExceededError` (the shared,
    message-only budget error). Subclassing — rather than raising the base type
    directly — lets lawgen callers catch precisely the pre-emission budget
    failures while callers that already handle the broader
    ``BudgetExceededError`` keep working. This mirrors
    :class:`mechdsl.lowering.fe_localise.LocalisationError`, which subclasses the
    broader ``UnsupportedError``.

    The message names the violated budget, the measured value, and the limit
    (see :meth:`BudgetError.for_budget`).
    """

    @classmethod
    def for_budget(
        cls,
        knob: str,
        measured: int,
        limit: int,
        *,
        where: str | None = None,
    ) -> BudgetError:
        """Build a :class:`BudgetError` with a structured message.

        The message is ``"<knob> budget exceeded: <measured> > <limit>"`` with
        an optional ``" (<where>)"`` suffix locating the offending function.
        Callers (and tests) can read the knob name, the measured value, and the
        limit straight from the text.
        """
        message = f"{knob} budget exceeded: {measured} > {limit}"
        if where is not None:
            message += f" ({where})"
        return cls(message)


# ---------------------------------------------------------------------------
# Module-level pure counters (independently testable).
# ---------------------------------------------------------------------------


def count_expr_ops(expr: sp.Expr) -> int:
    """Return ``sympy.count_ops(expr)`` as a plain ``int``.

    ``sp.count_ops`` is the canonical operation-count metric SymPy exposes; it
    counts arithmetic operators and function applications in the expression
    tree. ``visual=False`` returns an integer (the default), which we coerce to
    a Python ``int`` so the value is JSON/log friendly and version-stable.

    Risk note (P2-2): ``count_ops`` semantics can vary slightly across SymPy
    versions, so budget fixtures should use a low overridden limit on a fixed
    small expression rather than pinning an exact absolute count.
    """
    return int(sp.count_ops(expr, visual=False))


def count_piecewise_branches(expr: sp.Expr) -> int:
    """Return the largest branch count of any ``Piecewise`` in ``expr``.

    A ``sympy.Piecewise`` stores one ``(value, condition)`` pair per branch in
    its ``.args``, so ``len(piece.args)`` is the branch count. When several
    ``Piecewise`` nodes are nested/added, the maximum branch count is what the
    ``max_piecewise_branches`` budget guards (the deepest single switch). Returns
    ``0`` when the expression contains no ``Piecewise``.
    """
    pieces = expr.atoms(sp.Piecewise)
    if not pieces:
        return 0
    return max(len(piece.args) for piece in pieces)


def count_pow_symbolic_exponent(expr: sp.Expr) -> int:
    """Count ``Pow`` nodes in ``expr`` that lower to a runtime ``ti.pow``.

    Rule (precise): a ``sympy.Pow`` node counts iff its exponent is **not** a
    ``sympy.Integer`` **and** is not an exact half-power ``±sympy.S.Half``.
    That is:

    * Integer-literal exponents (``x**2``, ``x**-3``) are exempt — they lower to
      plain repeated multiplication and cost the JIT nothing extra.
    * Exact ``±1/2`` exponents (``sqrt(x)`` = ``Pow(x, S.Half)`` and
      ``1/sqrt(x)`` = ``Pow(x, -S.Half)``) are exempt too. P2-1's printer
      (:meth:`mechdsl.lawgen.sympy_to_taichi.TaichiExprPrinter._print_Pow`)
      special-cases these to ``ti.sqrt`` / ``1/ti.sqrt`` — **not** ``ti.pow`` —
      so they do not incur the runtime-``ti.pow`` cost this budget guards.
      The ``±S.Half`` detection mirrors that printer's idiom
      (``expr.exp is sp.S.Half`` / ``-expr.exp is sp.S.Half``).
    * Every other non-integer exponent counts: a symbolic exponent (``x**n``
      with ``n`` a ``Symbol``), a non-half rational (``x**(3/2)``), and a float
      (``x**2.0``) all force a runtime ``ti.pow`` / guarded-``ti.select``
      emission.
    """
    return sum(
        1
        for node in expr.atoms(sp.Pow)
        if not isinstance(node.exp, sp.Integer) and node.exp != sp.S.Half and -node.exp != sp.S.Half
    )


# ---------------------------------------------------------------------------
# BudgetChecker — the pre-emission gate.
# ---------------------------------------------------------------------------


def _func_line_count(lowered: LoweredExpr) -> int:
    """Emitted line count of one lowered function: temporaries + returns.

    Each CSE temporary is one assignment line and each return expression is one
    line, so the emitted line count of a single ``@ti.func`` is the sum of the
    two tuple lengths. This is the unit both ``max_func_lines`` (per function)
    and ``max_total_generated_lines_per_class`` (summed) are measured in.
    """
    return len(lowered.temporaries) + len(lowered.returns)


def _budget_diagnostic(
    knob: str,
    measured: int,
    limit: int,
    *,
    law: str,
) -> LawgenDiagnostic:
    """Build the structured :class:`~mechdsl.lawgen.diagnostics.LawgenDiagnostic` for one budget breach.

    The ``reason`` reuses :meth:`BudgetError.for_budget`'s exact message text
    (``"<knob> budget exceeded: <measured> > <limit>"``), so it always contains
    **both the measured value and the limit** (P3-1 AC3). ``node`` is the budget
    knob name; ``fix`` is an actionable hint pointing at the two ways to clear a
    budget breach — simplify the law or raise the knob on the
    :class:`~mechdsl.lawgen.contracts.TiconstitTarget`.
    """
    return LawgenDiagnostic(
        law=law,
        expression=law,
        node=knob,
        reason=str(BudgetError.for_budget(knob, measured, limit)),
        fix=(
            f"reduce the law so its {knob} measure ({measured}) is at most {limit}, "
            f"or raise the {knob} knob on the TiconstitTarget if the emission budget allows it."
        ),
    )


class BudgetChecker:
    """Pre-emission JIT-budget gate bound to a :class:`TiconstitTarget`.

    The bound target supplies the six budget knobs, so a caller that constructs
    a :class:`TiconstitTarget` with a lowered/raised knob transparently overrides
    the module defaults (the defaults *are* the ``TiconstitTarget`` defaults —
    there is a single source of truth, P1-1).

    Usage (Phase 3/4)
    -----------------
    Construct with the emission target, then call :meth:`check_all` with the
    law's SymPy expressions and their lowered results *before* handing anything
    to the printer::

        checker = BudgetChecker(target)
        checker.check_all(spec.expressions, lowered_by_role)

    :meth:`check_all` accumulates **every** budget violation (across all six
    knobs and all expressions/functions) and raises a single
    :class:`~mechdsl.lawgen.diagnostics.LawgenError` carrying them all (P3-1
    collect-all); if nothing is over budget it returns ``None`` and emission may
    proceed.
    """

    def __init__(self, target: TiconstitTarget | None = None) -> None:
        """Bind the checker to a :class:`TiconstitTarget` (knobs = its fields).

        ``target=None`` uses a default :class:`TiconstitTarget`, i.e. the six
        plan-frozen defaults; pass a customised target to override any knob.
        """
        self.target: TiconstitTarget = target if target is not None else TiconstitTarget()

    def check_all(
        self,
        expressions: Mapping[str, sp.Expr] | Iterable[sp.Expr],
        lowered: Mapping[str, LoweredExpr] | Iterable[LoweredExpr],
    ) -> None:
        """Run all six budget checks; collect **all** violations, then raise once.

        Collect-all (P3-1): every over-budget knob — across every expression and
        every function — is recorded as a
        :class:`~mechdsl.lawgen.diagnostics.LawgenDiagnostic`, and the whole batch
        is raised at the end as one
        :class:`~mechdsl.lawgen.diagnostics.LawgenError`. A law that trips three
        budgets reports all three, not just the first. If nothing is over budget,
        :meth:`raise_if_any` is a no-op and this returns ``None``.

        Parameters
        ----------
        expressions:
            The law's SymPy expressions — either a role→expr mapping (e.g.
            ``spec.expressions`` keyed ``"R"``/``"H"``/``"Q"``) or a bare
            iterable of expressions. The keys locate the offending expression in
            each diagnostic (``law``); the *values* drive the per-expression
            checks (``max_expr_ops``, ``max_piecewise_branches``,
            ``max_pow_with_symbolic_exponent``).
        lowered:
            The corresponding lowered results — one :class:`LoweredExpr` per
            emitted function, as a mapping (same keys as ``expressions``) or a
            bare iterable. Drive the emission-shape checks
            (``max_cse_temps_per_func``, ``max_func_lines``,
            ``max_total_generated_lines_per_class``).

        Returns
        -------
        None
            When every budget is satisfied. (Fail-loud only — R2: an over-budget
            input never returns cleanly; it raises with every violation.)

        Raises
        ------
        LawgenError
            Carrying one :class:`~mechdsl.lawgen.diagnostics.LawgenDiagnostic`
            per violated budget. Each diagnostic's ``reason`` names the knob, the
            measured value, and the limit; its ``fix`` is an actionable hint.
        """
        expr_items = _as_named_items(expressions)
        lowered_items = _as_named_items(lowered)
        collector = DiagnosticCollector()

        # --- Per-expression checks (SymPy side) --------------------------------
        for name, expr in expr_items:
            law = f"expression {name!r}" if name is not None else "<expression>"

            ops = count_expr_ops(expr)
            if ops > self.target.max_expr_ops:
                collector.add(
                    _budget_diagnostic("max_expr_ops", ops, self.target.max_expr_ops, law=law)
                )

            branches = count_piecewise_branches(expr)
            if branches > self.target.max_piecewise_branches:
                collector.add(
                    _budget_diagnostic(
                        "max_piecewise_branches",
                        branches,
                        self.target.max_piecewise_branches,
                        law=law,
                    )
                )

            sym_pows = count_pow_symbolic_exponent(expr)
            if sym_pows > self.target.max_pow_with_symbolic_exponent:
                collector.add(
                    _budget_diagnostic(
                        "max_pow_with_symbolic_exponent",
                        sym_pows,
                        self.target.max_pow_with_symbolic_exponent,
                        law=law,
                    )
                )

        # --- Per-function + whole-class checks (emission side) -----------------
        total_lines = 0
        for name, low in lowered_items:
            law = f"function {name!r}" if name is not None else "<function>"

            temps = len(low.temporaries)
            if temps > self.target.max_cse_temps_per_func:
                collector.add(
                    _budget_diagnostic(
                        "max_cse_temps_per_func", temps, self.target.max_cse_temps_per_func, law=law
                    )
                )

            func_lines = _func_line_count(low)
            if func_lines > self.target.max_func_lines:
                collector.add(
                    _budget_diagnostic(
                        "max_func_lines", func_lines, self.target.max_func_lines, law=law
                    )
                )

            total_lines += func_lines

        if total_lines > self.target.max_total_generated_lines_per_class:
            collector.add(
                _budget_diagnostic(
                    "max_total_generated_lines_per_class",
                    total_lines,
                    self.target.max_total_generated_lines_per_class,
                    law="<class>",
                )
            )

        # Collect-all, fail-loud: one LawgenError with every violation, or no-op.
        collector.raise_if_any()


def _as_named_items[T](
    items: Mapping[str, T] | Iterable[T],
) -> list[tuple[str | None, T]]:
    """Normalise a mapping-or-iterable into ``(name, value)`` pairs.

    Generic in the value type ``_T`` so the checker's per-expression / per-
    function loops keep their precise element type (``sp.Expr`` / ``LoweredExpr``)
    instead of collapsing to ``object``.

    A ``Mapping`` yields ``(key, value)`` pairs so the error message can name
    the offending role (``"R"``/``"H"``/``"Q"``). A bare iterable yields
    ``(None, value)`` pairs — the checks still run, only the locating suffix is
    omitted. A single ``sp.Expr``/``LoweredExpr`` is *not* iterated element-wise
    (a bare ``Expr`` is technically iterable via ``.args``); callers pass a
    mapping or an explicit sequence.
    """
    if isinstance(items, Mapping):
        return [(str(key), value) for key, value in items.items()]
    return [(None, value) for value in items]
