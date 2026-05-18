"""Uniform element-construction API (Plan B §B5.2, task P5-6).

The :class:`ElementFactory` collapses the four element constructors
(:func:`mechdsl.ir.element_ir.create_hex8_element_ir`,
:func:`~mechdsl.ir.element_ir.create_tet4_element_ir`,
:func:`~mechdsl.ir.element_ir.create_tet10_element_ir`,
:func:`~mechdsl.ir.element_ir.create_hex20_element_ir`) behind a single
``create(topology, integration='full', hourglass=None, ...)`` entry point
that downstream phases (residual, tangent, codegen, frontend) call into.

Implementation notes
--------------------
* Pure dispatch table — every supported ``(topology, integration, hourglass)``
  triple maps to one of the existing element-IR constructors.  No mutable
  state is held on the factory itself.
* All rejections raise :class:`ValueError` whose message includes the
  literal substring ``"Plan B phase B5"``; this is enforced by
  ``test_documentation.py``.
* The returned :class:`~mechdsl.ir.element_ir.ElementIR` is the immutable
  dataclass produced by the underlying constructor — no caching, no
  mutation.

See ``dev/design_docs/PLAN-B.md §B5.2`` for the API shape and
``dev/tasks/PLAN-B/json/P5-6.json`` for the supported-triple matrix.
"""

from __future__ import annotations

from typing import Final

from mechdsl.ir.element_ir import (
    ElementIR,
    create_hex8_element_ir,
    create_hex20_element_ir,
    create_tet4_element_ir,
    create_tet10_element_ir,
)
from mechdsl.ir.mechanics_ir import IntegrationRule

_PLAN_REF: Final[str] = "Plan B phase B5"

#: Topologies the factory currently knows about.
_KNOWN_TOPOLOGIES: Final[frozenset[str]] = frozenset({"hex8", "tet4", "tet10", "hex20"})

#: Integration-rule strings the factory currently knows about.
_KNOWN_INTEGRATIONS: Final[frozenset[str]] = frozenset({"full", "reduced"})

#: Hourglass-scheme strings the factory currently knows about.
_KNOWN_HOURGLASS: Final[frozenset[str | None]] = frozenset({None, "flanagan_belytschko"})


class ElementFactory:
    """Single entry point for building :class:`ElementIR` instances.

    The factory implements a closed dispatch table over the
    ``(topology, integration, hourglass)`` triple.  Every triple either
    maps to an existing element-IR constructor or raises
    :class:`ValueError` with a Plan B phase reference.

    Examples
    --------
    >>> elem = ElementFactory.create("hex8")
    >>> elem.element_type
    'hex8'

    >>> elem = ElementFactory.create(
    ...     "hex8", integration="reduced", hourglass="flanagan_belytschko"
    ... )
    >>> elem.integration_rule.value
    'reduced'
    """

    @classmethod
    def create(
        cls,
        topology: str,
        integration: str = "full",
        hourglass: str | None = None,
        formulation: str = "total_lagrangian",
        configuration: str = "reference",
    ) -> ElementIR:
        """Build an :class:`ElementIR` for the requested triple.

        Parameters
        ----------
        topology
            One of ``"hex8"``, ``"hex20"``, ``"tet4"``, ``"tet10"``.
        integration
            ``"full"`` (default) or ``"reduced"``.  Reduced integration is
            currently only supported on Hex8.
        hourglass
            ``None`` (default) or ``"flanagan_belytschko"``.  The
            Flanagan-Belytschko controller is hex8-specific and only
            applies to reduced integration.
        formulation
            ``"total_lagrangian"`` (default) or ``"updated_lagrangian"``;
            forwarded verbatim to the underlying constructor.
        configuration
            ``"reference"`` (default) or ``"current"``; forwarded
            verbatim to the underlying constructor.

        Returns
        -------
        ElementIR
            A freshly constructed, immutable element IR.  Reduced Hex8
            without an explicit hourglass scheme is allowed (the
            underlying ``create_hex8_element_ir`` records the reduced
            quadrature) but is rank-deficient — see Plan B §B5.5.

        Raises
        ------
        ValueError
            For unknown topology / integration / hourglass strings or for
            invalid combinations (``reduced`` on non-hex8,
            ``flanagan_belytschko`` on a non-reduced rule, etc.).  Every
            rejection message contains the literal substring
            ``"Plan B phase B5"``.
        """
        # -- 1. Vocabulary checks ----------------------------------------
        if topology not in _KNOWN_TOPOLOGIES:
            raise ValueError(
                f"Unknown element topology {topology!r}. "
                f"Supported topologies are {sorted(_KNOWN_TOPOLOGIES)}. "
                f"Additional element families are planned for {_PLAN_REF}."
            )
        if integration not in _KNOWN_INTEGRATIONS:
            raise ValueError(
                f"Unknown integration rule {integration!r}. "
                f"Supported integration rules are {sorted(_KNOWN_INTEGRATIONS)}. "
                f"See {_PLAN_REF} (§B5.4) for the integration-rule axis."
            )
        if hourglass not in _KNOWN_HOURGLASS:
            raise ValueError(
                f"Unknown hourglass scheme {hourglass!r}. "
                f"Supported hourglass schemes are "
                f"{sorted(s for s in _KNOWN_HOURGLASS if s is not None)} "
                f"or None. See {_PLAN_REF} (§B5.5)."
            )

        # -- 2. Combination validation -----------------------------------
        # Reduced integration is currently hex8-only (Plan B §B5.4 / P5-4).
        if integration == "reduced" and topology != "hex8":
            raise ValueError(
                f"Reduced integration is only implemented for hex8, got "
                f"topology={topology!r}. Reduced rules for other element "
                f"families are planned for {_PLAN_REF}."
            )
        # Flanagan-Belytschko hourglass control only stabilises reduced rules.
        if hourglass == "flanagan_belytschko" and integration != "reduced":
            raise ValueError(
                f"Hourglass scheme 'flanagan_belytschko' only applies to "
                f"reduced integration; got integration={integration!r}. "
                f"See {_PLAN_REF} (§B5.5)."
            )
        # Flanagan-Belytschko is hex8-specific (Plan B §B5.5 / P5-5).
        if hourglass == "flanagan_belytschko" and topology != "hex8":
            raise ValueError(
                f"Hourglass scheme 'flanagan_belytschko' is hex8-specific, "
                f"got topology={topology!r}. Hourglass control for other "
                f"element families is planned for {_PLAN_REF}."
            )

        # -- 3. Dispatch -------------------------------------------------
        integration_rule = (
            IntegrationRule.REDUCED if integration == "reduced" else IntegrationRule.FULL
        )
        if topology == "hex8":
            return create_hex8_element_ir(
                formulation=formulation,
                configuration=configuration,
                integration_rule=integration_rule,
            )
        if topology == "tet4":
            return create_tet4_element_ir(
                formulation=formulation,
                configuration=configuration,
            )
        if topology == "tet10":
            return create_tet10_element_ir(
                formulation=formulation,
                configuration=configuration,
            )
        if topology == "hex20":
            return create_hex20_element_ir(
                formulation=formulation,
                configuration=configuration,
            )
        # Unreachable: vocabulary check above guarantees one of the four.
        raise ValueError(  # pragma: no cover
            f"Unhandled topology {topology!r} reached dispatch; "
            f"this is an internal bug. See {_PLAN_REF}."
        )
