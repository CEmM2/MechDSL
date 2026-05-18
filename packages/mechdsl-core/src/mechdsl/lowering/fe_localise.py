"""FE localisation pass: ProblemIR -> ElementIR + einsum specifications.

This is Layer 4 of the FEM compiler pipeline. It performs a lossless
transformation from the semantic ProblemIR to the discretisation-level
ElementIR, extracting einsum strings for the key element operations.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from mechdsl.ir.element_ir import (
    ElementIR,
    GeometrySummary,
    LocalForceDescriptor,
    LocalTangentDescriptor,
    MaterialEvalContract,
    create_hex8_element_ir,
)
from mechdsl.ir.mechanics_ir import Configuration, ElementType, Formulation, ProblemIR
from mechdsl.symbolic.convected import UnsupportedError


class LocalisationError(UnsupportedError, ValueError):
    """Raised when ``localise()`` rejects a stable-path combination.

    Recovery-plan P4-4 (R3.4) added this exception to give the lowering
    layer a single, named rejection class with a stable contract: every
    instance carries a clear phase pointer in its message naming the
    Plan-B phase that adds support for the rejected combination.

    Subclasses :class:`UnsupportedError` so callers that catch the
    broader rule-defined "outside supported subset" exception
    (per ``.claude/rules/ir.md``) keep working. Also subclasses
    :class:`ValueError` for back-compat with pre-P4-4 callers that caught
    the bare ``ValueError`` raised by the old in-line rejection paths.
    """


if TYPE_CHECKING:
    from mechdsl.codegen.artifact import ContractionPlan
    from mechdsl.codegen.einsum_optimizer import ContractionResult

_SUPPORTED_MODELS: frozenset[str] = frozenset(
    {
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
)


# Reference-cell volumes (∫_ref 1 dV). Used by `_enrich_element_ir` (P4-3) to
# populate `GeometrySummary.reference_volume`. Hex variants live on the
# canonical [-1,1]^3 reference; the tet variants sit on the unit reference
# tetrahedron (volume 1/6).
_REFERENCE_CELL_VOLUME: dict[str, float] = {
    "hex8": 8.0,
    "hex20": 8.0,
    "tet4": 1.0 / 6.0,
    "tet10": 1.0 / 6.0,
}


# Material models whose algorithmic consistent tangent is symmetric. SVK is
# strictly symmetric (hyperelastic ∂²Ψ/∂E²); the J2 + power-law return map
# is algorithmically symmetric for associative flow with a smooth yield
# surface. Plan B's rate-dependent / non-associative models (perzyna,
# johnson_cook, lemaitre) ship non-symmetric tangents and are flagged here
# accordingly.
_SYMMETRIC_TANGENT_MODELS: frozenset[str] = frozenset({"svk", "j2_power_law"})


def _enrich_element_ir(legacy_ir: ElementIR, problem_ir: ProblemIR) -> ElementIR:
    """Populate the P4-1 execution-contract dataclasses on an ``ElementIR``.

    Recovery-plan P4-3 (R3.3) makes the IR the *primary* output of lowering:
    the enriched ``ElementIR`` is built first and the einsum optimizer view
    is derived from it. Pre-P4-3 ``localise()`` returned a bare ElementIR
    (no contract dataclasses populated); this helper is the centralised
    derivation that ``localise()`` calls before extracting einsum specs.

    The four contract blocks are derived from the ``ProblemIR`` /
    ``ElementIR`` semantics — no Taichi-specific assumptions — so the
    enrichment stays backend-agnostic per the Phase 4 constraint.

    Parameters
    ----------
    legacy_ir
        The bare ``ElementIR`` produced by ``create_*_element_ir(...)``;
        no contract dataclasses populated yet.
    problem_ir
        The originating problem — used to pick the correct stress / strain
        measure pair (PK2 + Green-Lagrange for TL, Cauchy + Almansi for UL)
        and the symmetry flag on the local tangent.
    """
    n_quad = legacy_ir.quadrature.n_points
    reference_volume = _REFERENCE_CELL_VOLUME.get(legacy_ir.element_type, 1.0)
    geometry = GeometrySummary(
        n_quad=n_quad,
        reference_volume=reference_volume,
        natural_coord_dim=legacy_ir.dim,
    )

    if legacy_ir.configuration == "current":  # UL
        material_eval = MaterialEvalContract(
            stress_measure="cauchy",
            strain_measure="almansi",
        )
    else:  # TL (default)
        material_eval = MaterialEvalContract(
            stress_measure="pk2",
            strain_measure="green_lagrange",
        )

    n_dof = legacy_ir.n_nodes * legacy_ir.dim
    local_force = LocalForceDescriptor(
        n_dof=n_dof,
        contraction_sketch="qaI,qIJ->qaJ",  # B^T @ stress over quadrature
    )
    local_tangent = LocalTangentDescriptor(
        n_dof=n_dof,
        is_symmetric=problem_ir.material.model in _SYMMETRIC_TANGENT_MODELS,
        contraction_sketch="qaI,qIJKL,qbK->qaJbL",  # B^T C B
    )

    return replace(
        legacy_ir,
        geometry=geometry,
        material_eval=material_eval,
        local_force=local_force,
        local_tangent=local_tangent,
    )


@dataclass(frozen=True)
class EinsumSpec:
    """**Derived optimizer view** — a single einsum contraction extracted
    from the element formulation.

    .. note::

       Recovery-plan P4-2 (R3.2) demoted ``EinsumSpec`` from a primary
       semantic carrier to a *derived view* over :class:`ElementIR`. The
       canonical semantic source for element-level information is now
       ``ElementIR`` (see :mod:`mechdsl.ir.element_ir`); ``EinsumSpec``
       captures the contraction-shape slice that the einsum optimizer
       needs and is regenerated whenever ``ElementIR`` changes.

       Producers should derive these via
       :func:`mechdsl.lowering.einsum_extract.extract_einsum_specs`
       instead of constructing them independently.

    The einsum_string uses Einstein summation convention with named axes:

        q = quadrature point
        a, b = node indices
        i, j = spatial indices
        I, J, K, L = material indices
    """

    name: str  # e.g. "internal_force", "tangent_matvec"
    einsum_string: str  # e.g. "qaI,qIJ->qaJ"
    operand_shapes: tuple[tuple[int, ...], ...]  # shapes of input operands
    result_shape: tuple[int, ...]
    description: str = ""


@dataclass(frozen=True)
class LocalisationResult:
    """**Derived view** — bundles an :class:`ElementIR` with its derived
    einsum-optimizer specs.

    .. note::

       Recovery-plan P4-2 (R3.2) demoted ``LocalisationResult`` from "the
       primary semantic carrier downstream consumers should read" to a
       derived bundle. The semantic source of truth is the ``element_ir``
       field; ``einsum_specs`` is a derived optimizer view recomputed
       from that ``ElementIR`` (see :meth:`from_element_ir`). Downstream
       consumers that need only the semantic content should reach for the
       :class:`ElementIR` directly; consumers that need the optimizer
       view should use this bundle.

    Producing a ``LocalisationResult`` from an already-built ``ElementIR``
    is a single :meth:`from_element_ir` call — that is the canonical
    "derive optimizer view from primary semantic carrier" path.
    """

    element_ir: ElementIR
    einsum_specs: tuple[EinsumSpec, ...]
    problem_ir: ProblemIR  # back-reference

    @classmethod
    def from_element_ir(
        cls,
        element_ir: ElementIR,
        problem_ir: ProblemIR,
    ) -> LocalisationResult:
        """Derive a :class:`LocalisationResult` from an enriched ``ElementIR``.

        This makes the derived-view relationship explicit: callers build
        (or modify) ``ElementIR`` independently — possibly enriching it
        with the P4-1 contract dataclasses — and then materialize the
        optimizer view on demand. Pre-P4-2, ``localise()`` was the only
        production path; ``from_element_ir`` is the post-P4-2 reverse
        constructor that lets test fixtures and downstream consumers
        derive the view without re-running the full ``ProblemIR ->
        ElementIR`` pass.

        Parameters
        ----------
        element_ir
            The primary semantic carrier produced upstream. Optionally
            carries P4-1 enrichment (geometry, material_eval, force /
            tangent descriptors); this method does not require those
            fields to be populated.
        problem_ir
            Back-reference to the originating problem. Stored verbatim on
            the returned bundle for traceability.

        Returns
        -------
        LocalisationResult
            A new bundle whose ``einsum_specs`` are freshly derived from
            ``element_ir`` via
            :func:`mechdsl.lowering.einsum_extract.extract_einsum_specs`.
        """
        from mechdsl.lowering.einsum_extract import extract_einsum_specs

        return cls(
            element_ir=element_ir,
            einsum_specs=tuple(extract_einsum_specs(element_ir).values()),
            problem_ir=problem_ir,
        )


def _check_stable_path_combo(problem_ir: ProblemIR) -> None:
    """Reject ``ProblemIR`` configurations the lowering pass cannot lower.

    Recovery-plan P4-4 (R3.4) centralises the previously-scattered
    rejection logic into a single guard with a stable contract:

    1. Every rejection raises :class:`LocalisationError` (a subclass of
       :class:`UnsupportedError`).
    2. Every message names the offending construct AND the Plan-B phase
       that adds support for it.
    3. The checks fire deterministically in axis order
       (formulation → element → material) so error messages stay stable
       across runs.
    """
    # Formulation: both TL and UL are valid in the IR after Plan B §B1.3,
    # but anything outside the canonical pair is a hard reject.
    if problem_ir.formulation not in (
        Formulation.TOTAL_LAGRANGIAN,
        Formulation.UPDATED_LAGRANGIAN,
    ):
        raise LocalisationError(
            f"Formulation {problem_ir.formulation.value!r} not supported "
            "for localisation. Only total_lagrangian and updated_lagrangian "
            "are recognised; additional formulations are planned for "
            "Plan B phase B1."
        )
    # Element type: only Hex8 is wired into the lowering pass today;
    # Tet4 / Tet10 / Hex20 are valid in the IR but Plan B §B5 owns their
    # localisation.
    if problem_ir.element_type != ElementType.HEX8:
        raise LocalisationError(
            f"Element type {problem_ir.element_type.value!r} not supported "
            "for localisation. Only hex8 is wired into the lowering pass "
            "today; Tet4 / Tet10 / Hex20 support is planned for Plan B phase B5."
        )
    # Material model: must be on the lowering pass's allowlist.
    if problem_ir.material.model not in _SUPPORTED_MODELS:
        raise LocalisationError(
            f"Material model {problem_ir.material.model!r} not supported "
            "for localisation. "
            f"Supported: {sorted(_SUPPORTED_MODELS)}. "
            "Additional constitutive models are planned across Plan B phases "
            "B4 (hyperelastic) and B6 (damage)."
        )


def localise(problem_ir: ProblemIR) -> LocalisationResult:
    """Map ProblemIR to ElementIR with extracted einsum specifications.

    This is a lossless transformation.  It:
    1. Validates formulation/element compatibility.
    2. Selects element type and creates ElementIR (Hex8 only for MVP).
    3. Extracts einsum strings for key operations:
       - strain_displacement: displacement -> deformation gradient mapping
       - internal_force: B^T @ stress integration
       - tangent_matvec: consistent tangent matrix-vector product

    Raises
    ------
    LocalisationError
        For incompatible IR combinations (unsupported formulation,
        element type, or material model). Subclasses
        :class:`UnsupportedError`, so callers that catch the broader
        rule-defined exception keep working without source changes. See
        :func:`_check_stable_path_combo` for the canonical rejection
        contract: every message names the offending construct AND the
        Plan-B phase that adds support.
    """
    # -- Validate formulation/element compatibility ----------------------
    # Both TL and UL are valid after Plan B §B1.3. The configuration enum on
    # ProblemIR is already guaranteed consistent with the formulation by
    # ProblemIR.__post_init__.
    _check_stable_path_combo(problem_ir)

    # -- Create element IR -----------------------------------------------
    # Thread formulation + configuration through the element IR so downstream
    # emitters (P1-3 residual, P1-4 tangent) can branch on element_ir.configuration
    # rather than sniffing ProblemIR again. See Plan B §B1.3.
    configuration_str = (
        Configuration.CURRENT.value
        if problem_ir.formulation == Formulation.UPDATED_LAGRANGIAN
        else Configuration.REFERENCE.value
    )
    legacy_ir = create_hex8_element_ir(
        formulation=problem_ir.formulation.value,
        configuration=configuration_str,
    )
    # P4-3: lowering emits the enriched ElementIR first, then derives the
    # einsum optimizer view from it. Pre-P4-3, the bare IR was returned and
    # downstream layers re-derived these contract facts inline.
    element_ir = _enrich_element_ir(legacy_ir, problem_ir)

    # -- Derive optimizer view from the enriched IR ----------------------
    return LocalisationResult.from_element_ir(element_ir, problem_ir)


# ---------------------------------------------------------------------------
# Integrated pipeline: localise + optimise
# ---------------------------------------------------------------------------


def _contraction_result_to_plan(result: ContractionResult) -> ContractionPlan:
    """Convert a :class:`ContractionResult` to a :class:`ContractionPlan`.

    P9-2 propagates the template-family classification from the optimiser
    result into the serialisable plan. The family is stored as the enum
    *name* string so the artifact bundle stays JSON-round-trippable without
    a custom enum encoder.
    """
    from mechdsl.codegen.artifact import ContractionPlan as _CP

    return _CP(
        einsum_string=result.einsum_string,
        contraction_path=result.contraction_path,
        estimated_flops=int(result.estimated_flops),
        tier=int(result.tier),
        family=result.family.name,
    )


def localise_and_optimize(
    problem_ir: ProblemIR,
) -> tuple[LocalisationResult, tuple[ContractionPlan, ...]]:
    """Full lowering pipeline: localise + optimise contractions.

    1. Call :func:`localise` to get ElementIR + einsum specs.
    2. Run the einsum optimiser on each spec.
    3. Convert results to :class:`ContractionPlan` objects for the artifact bundle.
    4. Return both the localisation result and the plans.

    Parameters
    ----------
    problem_ir : ProblemIR
        The semantic problem specification.

    Returns
    -------
    tuple[LocalisationResult, tuple[ContractionPlan, ...]]
        The localisation result and one contraction plan per einsum spec,
        in the same order as ``result.einsum_specs``.

    Raises
    ------
    ValueError
        Propagated from :func:`localise` for unsupported configurations.
    BudgetExceededError
        If the absolute budget ceiling is exceeded (propagated from the
        einsum optimiser).
    """
    from mechdsl.codegen.einsum_optimizer import optimize_contraction as _opt

    loc_result = localise(problem_ir)

    plans: list[ContractionPlan] = []
    for spec in loc_result.einsum_specs:
        contraction = _opt(
            spec.einsum_string,
            list(spec.operand_shapes),
        )
        plans.append(_contraction_result_to_plan(contraction))

    return loc_result, tuple(plans)
