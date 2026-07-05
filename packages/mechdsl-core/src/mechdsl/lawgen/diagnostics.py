"""Structured, collect-all diagnostics for the lawgen lowerer (Task P3-1).

MFront-mimic Cycle M0, Phase 3 (``dev/plans/mfront_cycleM0.md`` lines 98-100).

This module is the *reporting* layer that stands beside the Phase-2 gates
(:mod:`mechdsl.lawgen.budgets`, P2-2; :mod:`mechdsl.lawgen.sympy_to_taichi`,
P2-4). Where Phase 2 fails on the **first** problem, P3-1 turns those checks into
**collect-all** ones: every unsupported SymPy node and every budget breach
produces a structured :class:`LawgenDiagnostic`, they are accumulated in a
:class:`DiagnosticCollector`, and the whole batch is raised at once as a single
:class:`LawgenError` so the user sees *every* problem in one run.

Design rules (plan R2, "no silent fallback")
---------------------------------------------
* **Fail loud, but collect first.** Nothing is swallowed: an accumulated
  diagnostic always surfaces via :meth:`DiagnosticCollector.raise_if_any`. The
  only "no-op" path is the genuinely clean one (zero diagnostics).
* **Every diagnostic is complete.** All five fields of :class:`LawgenDiagnostic`
  (``law`` / ``expression`` / ``node`` / ``reason`` / ``fix``) are required,
  non-empty strings, validated at construction. In particular ``fix`` must be an
  actionable hint — a diagnostic with no remedy is a bug, so an empty ``fix``
  raises.
* **The aggregate is discoverable.** :class:`LawgenError` carries the full list
  of diagnostics on ``.diagnostics`` *and* embeds each one in ``.args`` and in
  its message, so a caller (or a test) can read every problem off the exception
  without re-running the compile.

Relationship to the Phase-2 error types
----------------------------------------
:class:`LawgenError` subclasses :class:`NotImplementedError`. Phase 2's
fail-loud raises for unsupported nodes were ``NotImplementedError`` (the
unmapped-function / non-exhaustive-``Piecewise`` path); making the collect-all
aggregate a ``NotImplementedError`` keeps every ``except NotImplementedError`` /
``pytest.raises(NotImplementedError)`` site working while upgrading the payload
from a bare message to a structured, multi-diagnostic report. The per-budget
:class:`~mechdsl.lawgen.budgets.BudgetError` is still used *inside* the budget
checker to format each budget diagnostic's ``reason`` (measured + limit); the
raised *aggregate* is now the richer :class:`LawgenError`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator
    from types import TracebackType

__all__ = [
    "DiagnosticCollector",
    "LawgenDiagnostic",
    "LawgenError",
]


@dataclass(frozen=True)
class LawgenDiagnostic:
    """One structured problem found while lowering a constitutive law.

    Immutable (frozen) so a collected diagnostic cannot be mutated between the
    point it is recorded and the point it is reported. All five fields are
    **required, non-empty strings** — a diagnostic missing any of them is
    rejected at construction (see :meth:`__post_init__`), because a report the
    user cannot act on is worse than no report.

    Attributes
    ----------
    law:
        The law / role the problem belongs to, e.g. the expression role
        ``"R"``/``"H"``/``"Q"`` or a law name. Answers *which law*.
    expression:
        A human-readable rendering of the offending expression (typically
        ``str(expr)``). Answers *where in the law*.
    node:
        The specific offending node or budget knob — the unsupported SymPy
        function name (``"erf"``), or the budget knob (``"max_expr_ops"``).
        Answers *what exactly*.
    reason:
        Why it fails. For a budget breach this MUST contain both the measured
        value and the limit (e.g. ``"measured 4 > limit 2"``) so the user can
        see how far over budget the law is.
    fix:
        An actionable remedy hint — never empty. Tells the user what to change
        (register the function, simplify the law, raise the knob, …).
    """

    law: str
    expression: str
    node: str
    reason: str
    fix: str

    def __post_init__(self) -> None:
        """Reject any empty/blank field — every diagnostic must be complete.

        Each of the five fields must be a non-empty string once stripped of
        surrounding whitespace. ``fix`` is included: an actionable remedy is
        mandatory (a diagnostic with no fix is a silent dead-end, which R2
        forbids).
        """
        for name in ("law", "expression", "node", "reason", "fix"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(
                    f"LawgenDiagnostic.{name} must be a non-empty string, got {value!r}. "
                    "Every diagnostic field (including an actionable 'fix') is required — "
                    "an incomplete diagnostic is a bug (no silent fallback, R2)."
                )

    def render(self) -> str:
        """Render this diagnostic as one multi-field human-readable block.

        Used both in the :class:`LawgenError` message and anywhere a single
        diagnostic needs printing. Every field is labelled so the report reads
        the same whether it is one diagnostic or one of many.
        """
        return (
            f"[{self.law}] {self.node}\n"
            f"    expression: {self.expression}\n"
            f"    reason:     {self.reason}\n"
            f"    fix:        {self.fix}"
        )


class LawgenError(NotImplementedError):
    """Aggregate error carrying *every* diagnostic collected in one lowering run.

    Subclasses :class:`NotImplementedError` so Phase 2's fail-loud contract for
    unsupported nodes (which raised ``NotImplementedError``) is preserved: any
    existing ``except NotImplementedError`` / ``pytest.raises(NotImplementedError)``
    still catches the aggregate, only now the payload is a structured,
    collect-all report instead of a single message.

    The diagnostics are exposed three ways, so a caller never has to re-run the
    compile to learn what went wrong:

    * :attr:`diagnostics` — the tuple of :class:`LawgenDiagnostic` records.
    * ``args`` — the rendered message *plus* each diagnostic, so
      ``LawgenError.args`` contains every problem (the P3-1 acceptance check).
    * ``str(err)`` — a header line naming the count, then every diagnostic's
      :meth:`LawgenDiagnostic.render` block.
    """

    def __init__(self, diagnostics: Iterable[LawgenDiagnostic]) -> None:
        """Build the aggregate from one-or-more collected diagnostics.

        ``diagnostics`` must be non-empty — a ``LawgenError`` with nothing to
        report is meaningless (:meth:`DiagnosticCollector.raise_if_any` only
        constructs one when there is at least one diagnostic). The rendered
        message and the individual diagnostics are both placed in ``args`` so
        every problem is discoverable straight off the exception.
        """
        collected = tuple(diagnostics)
        if not collected:
            raise ValueError(
                "LawgenError requires at least one diagnostic; raise nothing when "
                "the collector is empty (use DiagnosticCollector.raise_if_any)."
            )
        self.diagnostics: tuple[LawgenDiagnostic, ...] = collected
        message = self._format(collected)
        # Put the message AND every diagnostic in ``args`` so a caller reading
        # ``err.args`` sees all problems (P3-1 AC: "both appear in .args").
        super().__init__(message, *collected)

    @staticmethod
    def _format(diagnostics: tuple[LawgenDiagnostic, ...]) -> str:
        """Compose the header + every diagnostic block into one message string."""
        count = len(diagnostics)
        noun = "diagnostic" if count == 1 else "diagnostics"
        header = f"lawgen emission failed with {count} {noun} (no silent fallback — R2):"
        blocks = "\n".join(diag.render() for diag in diagnostics)
        return f"{header}\n{blocks}"


@dataclass
class DiagnosticCollector:
    """Accumulates :class:`LawgenDiagnostic` records, then raises them all at once.

    The collect-all counterpart to Phase 2's fail-first gates: a caller
    :meth:`add`\\ s a diagnostic for *every* problem it finds and calls
    :meth:`raise_if_any` at the end, so a single run reports every problem rather
    than aborting on the first.

    Usage (imperative)::

        collector = DiagnosticCollector()
        for expr in exprs:
            if problem(expr):
                collector.add(LawgenDiagnostic(...))
        collector.raise_if_any()   # raises LawgenError with ALL problems, or no-op

    Usage (context manager)::

        with DiagnosticCollector() as collector:
            collector.add(...)
        # raise_if_any() runs on clean block exit

    The context-manager form calls :meth:`raise_if_any` on a *clean* exit only:
    if the ``with`` body itself raises, that exception propagates untouched (we
    never swallow it to raise a possibly-empty aggregate).
    """

    _diagnostics: list[LawgenDiagnostic] = field(default_factory=list)

    def add(self, diagnostic: LawgenDiagnostic) -> None:
        """Record one diagnostic. Order is preserved (append)."""
        self._diagnostics.append(diagnostic)

    def extend(self, diagnostics: Iterable[LawgenDiagnostic]) -> None:
        """Record several diagnostics in order (convenience over :meth:`add`)."""
        self._diagnostics.extend(diagnostics)

    @property
    def diagnostics(self) -> tuple[LawgenDiagnostic, ...]:
        """The diagnostics collected so far, in insertion order (immutable view)."""
        return tuple(self._diagnostics)

    def __bool__(self) -> bool:
        """True iff at least one diagnostic has been collected."""
        return bool(self._diagnostics)

    def __len__(self) -> int:
        """Number of diagnostics collected so far."""
        return len(self._diagnostics)

    def __iter__(self) -> Iterator[LawgenDiagnostic]:
        """Iterate the collected diagnostics in insertion order."""
        return iter(self._diagnostics)

    def raise_if_any(self) -> None:
        """Raise :class:`LawgenError` with ALL collected diagnostics, or no-op.

        If any diagnostics were collected, raise a single :class:`LawgenError`
        carrying every one of them (so the user sees all problems at once). If
        none were collected, return cleanly — this is the *only* silent path, and
        it is silent precisely because there is nothing to report.
        """
        if self._diagnostics:
            raise LawgenError(self._diagnostics)

    def __enter__(self) -> DiagnosticCollector:
        """Enter the context-manager form; returns ``self`` for ``as`` binding."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> Literal[False]:
        """On a clean block exit, raise any collected diagnostics.

        If the ``with`` body raised (``exc is not None``), that exception
        propagates untouched — we do not swallow a real error to substitute a
        (possibly empty) aggregate. On a clean exit, :meth:`raise_if_any` fires,
        so ``with DiagnosticCollector() as c: ...`` behaves like the imperative
        form. Returns ``False`` so an in-body exception is never suppressed.
        """
        if exc is None:
            self.raise_if_any()
        return False
