"""Live audit for recovery-plan P4-2: EinsumSpec / LocalisationResult demoted.

Asserts that:

1. The docstrings on ``EinsumSpec`` and ``LocalisationResult`` mark them
   explicitly as derived views over :class:`ElementIR` (so their role is
   discoverable from ``help()`` and IDE tooltips, not just from the
   recovery plan).
2. ``LocalisationResult.from_element_ir(element_ir, problem_ir)`` exists
   and produces a bundle whose ``einsum_specs`` are freshly derived from
   the provided ``ElementIR`` — making the derived-view relationship
   explicit in code.
3. The enriched ``ElementIR`` survives independently of the optimizer
   view: building an ``ElementIR`` (with the P4-1 enrichment fields
   populated), then deriving a ``LocalisationResult`` from it, leaves
   the original ``ElementIR`` unchanged and equal-to-itself.
4. The pre-P4-2 production path ``localise(problem_ir)`` still produces
   the same shape of result (no regression).
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from mechdsl.ir.element_ir import (
    ElementIR,
    GeometrySummary,
    LocalForceDescriptor,
    LocalTangentDescriptor,
    MaterialEvalContract,
    create_hex8_element_ir,
)
from mechdsl.ir.mechanics_ir import (
    BCType,
    BoundaryCondition,
    ElementType,
    Formulation,
    MaterialSpec,
    ProblemIR,
)
from mechdsl.lowering.fe_localise import EinsumSpec, LocalisationResult, localise


def _mvp_problem_ir() -> ProblemIR:
    return ProblemIR(
        dim=3,
        formulation=Formulation.TOTAL_LAGRANGIAN,
        element_type=ElementType.HEX8,
        material=MaterialSpec(model="svk", params={"E": 200e3, "nu": 0.3}),
        boundaries=(
            BoundaryCondition(name="fix", bc_type=BCType.DIRICHLET),
            BoundaryCondition(name="load", bc_type=BCType.NEUMANN, traction="t_bar"),
        ),
    )


def _enriched_hex8_element_ir() -> ElementIR:
    base = create_hex8_element_ir()
    return replace(
        base,
        geometry=GeometrySummary(n_quad=8, reference_volume=8.0),
        material_eval=MaterialEvalContract(stress_measure="pk2"),
        local_force=LocalForceDescriptor(n_dof=24),
        local_tangent=LocalTangentDescriptor(n_dof=24, is_symmetric=True),
    )


# ---------------------------------------------------------------------------
# 1. Docstrings document the derived-view status
# ---------------------------------------------------------------------------


class TestDerivedViewDocumentation:
    @pytest.mark.unit
    def test_einsum_spec_docstring_marks_as_derived_view(self) -> None:
        # The "derived view" label must be discoverable from `help()` so a
        # consumer who reads the docstring sees the post-P4-2 status.
        assert EinsumSpec.__doc__ is not None
        assert "derived" in EinsumSpec.__doc__.lower()

    @pytest.mark.unit
    def test_localisation_result_docstring_marks_as_derived_view(self) -> None:
        assert LocalisationResult.__doc__ is not None
        assert "derived" in LocalisationResult.__doc__.lower()
        # Also call out the recovery-plan task that introduced the demotion
        # so future readers can find the rationale.
        assert "P4-2" in LocalisationResult.__doc__


# ---------------------------------------------------------------------------
# 2. `from_element_ir` makes the derivation explicit
# ---------------------------------------------------------------------------


class TestFromElementIR:
    @pytest.mark.unit
    def test_classmethod_exists(self) -> None:
        assert hasattr(LocalisationResult, "from_element_ir")
        assert callable(LocalisationResult.from_element_ir)

    @pytest.mark.unit
    def test_from_element_ir_with_legacy_ir_yields_specs(self) -> None:
        problem_ir = _mvp_problem_ir()
        element_ir = create_hex8_element_ir()
        result = LocalisationResult.from_element_ir(element_ir, problem_ir)
        assert result.element_ir is element_ir
        assert result.problem_ir is problem_ir
        # The derivation must materialize at least one optimizer spec; the
        # exact spec set is the einsum_extract test's concern.
        assert len(result.einsum_specs) > 0

    @pytest.mark.unit
    def test_from_element_ir_with_enriched_ir_preserves_enrichment(self) -> None:
        problem_ir = _mvp_problem_ir()
        enriched = _enriched_hex8_element_ir()
        result = LocalisationResult.from_element_ir(enriched, problem_ir)
        # Enrichment fields survive end-to-end through the bundle.
        assert result.element_ir.geometry == enriched.geometry
        assert result.element_ir.material_eval == enriched.material_eval
        assert result.element_ir.local_force == enriched.local_force
        assert result.element_ir.local_tangent == enriched.local_tangent

    @pytest.mark.unit
    def test_from_element_ir_does_not_mutate_input(self) -> None:
        problem_ir = _mvp_problem_ir()
        enriched = _enriched_hex8_element_ir()
        snapshot = enriched.to_dict()
        LocalisationResult.from_element_ir(enriched, problem_ir)
        # Frozen dataclass + careful derivation = no mutation.
        assert enriched.to_dict() == snapshot


# ---------------------------------------------------------------------------
# 3. Enriched ElementIR survives independently of the optimizer view
# ---------------------------------------------------------------------------


class TestEnrichedIRIndependence:
    @pytest.mark.unit
    def test_enriched_ir_can_be_built_without_localisation_result(self) -> None:
        # If P4-2's demotion leaked, building an ElementIR-only path would
        # require also building the optimizer view. It must not.
        ir = _enriched_hex8_element_ir()
        assert ir.element_type == "hex8"
        assert ir.geometry is not None and ir.geometry.n_quad == 8

    @pytest.mark.unit
    def test_localise_still_produces_localisation_result(self) -> None:
        # Pre-P4-2 callers still get the same shape of result back from the
        # production path — no regression in the public API.
        result = localise(_mvp_problem_ir())
        assert isinstance(result, LocalisationResult)
        assert isinstance(result.element_ir, ElementIR)
        assert all(isinstance(s, EinsumSpec) for s in result.einsum_specs)

    @pytest.mark.unit
    def test_two_localise_results_share_einsum_spec_shape(self) -> None:
        # The derivation is deterministic per-ElementIR shape: building the
        # bundle twice from the same inputs produces matching specs.
        problem_ir = _mvp_problem_ir()
        element_ir = create_hex8_element_ir()
        a = LocalisationResult.from_element_ir(element_ir, problem_ir)
        b = LocalisationResult.from_element_ir(element_ir, problem_ir)
        assert tuple(s.einsum_string for s in a.einsum_specs) == tuple(
            s.einsum_string for s in b.einsum_specs
        )
