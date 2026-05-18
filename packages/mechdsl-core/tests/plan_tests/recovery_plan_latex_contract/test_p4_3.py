"""Live audit for recovery-plan P4-3: lowering emits richer ElementIR first.

Asserts that:

1. ``localise(problem_ir)`` populates the four P4-1 execution-contract
   dataclasses on the returned ``ElementIR`` (geometry, material_eval,
   local_force, local_tangent).
2. The enrichment is consistent with the originating ``ProblemIR``: TL
   formulations carry PK2 + Green-Lagrange; UL would carry Cauchy +
   Almansi (validated through the public API even though UL lowering is
   gated elsewhere).
3. Symmetric-tangent models (svk, j2_power_law) flip ``local_tangent.
   is_symmetric=True``; non-symmetric models (perzyna, johnson_cook,
   lemaitre) flip it ``False``.
4. The optimizer view (einsum_specs / contraction plans) is derived
   *from* the enriched ``ElementIR`` — same ElementIR ⇒ same plan set.
5. ``ArtifactBundle.from_pipeline`` surfaces the enriched contract
   blocks in ``element_ir_summary`` so golden artifacts capture the
   enrichment.
6. Pre-P4-3 ``localise()`` consumers continue to receive a
   ``LocalisationResult`` with the same surface shape (back-compat).
"""

from __future__ import annotations

import pytest

from mechdsl.codegen.artifact import ArtifactBundle, ContractionPlan
from mechdsl.ir.mechanics_ir import (
    BCType,
    BoundaryCondition,
    ElementType,
    Formulation,
    MaterialSpec,
    ProblemIR,
)
from mechdsl.lowering.fe_localise import LocalisationResult, localise, localise_and_optimize


def _mvp_problem_ir(
    *,
    formulation: Formulation = Formulation.TOTAL_LAGRANGIAN,
    material_model: str = "svk",
) -> ProblemIR:
    params: dict[str, float] = (
        {
            "E": 200e3,
            "nu": 0.3,
            "sigma_y0": 250.0,
            "K": 1000.0,
            "n": 10.0,
        }
        if material_model == "j2_power_law"
        else {"E": 200e3, "nu": 0.3}
    )
    return ProblemIR(
        dim=3,
        formulation=formulation,
        element_type=ElementType.HEX8,
        material=MaterialSpec(model=material_model, params=params),
        boundaries=(
            BoundaryCondition(name="fix", bc_type=BCType.DIRICHLET),
            BoundaryCondition(name="load", bc_type=BCType.NEUMANN, traction="t_bar"),
        ),
    )


# ---------------------------------------------------------------------------
# 1. localise() emits the enriched ElementIR
# ---------------------------------------------------------------------------


class TestLocaliseEmitsEnrichedIR:
    @pytest.mark.regression
    def test_geometry_block_populated(self) -> None:
        result = localise(_mvp_problem_ir())
        geom = result.element_ir.geometry
        assert geom is not None
        assert geom.n_quad == result.element_ir.quadrature.n_points
        assert geom.reference_volume == 8.0  # Hex8 reference volume
        assert geom.natural_coord_dim == 3

    @pytest.mark.regression
    def test_material_eval_block_populated_for_tl(self) -> None:
        result = localise(_mvp_problem_ir(formulation=Formulation.TOTAL_LAGRANGIAN))
        me = result.element_ir.material_eval
        assert me is not None
        assert me.stress_measure == "pk2"
        assert me.strain_measure == "green_lagrange"

    @pytest.mark.regression
    def test_material_eval_block_populated_for_ul(self) -> None:
        result = localise(_mvp_problem_ir(formulation=Formulation.UPDATED_LAGRANGIAN))
        me = result.element_ir.material_eval
        assert me is not None
        assert me.stress_measure == "cauchy"
        assert me.strain_measure == "almansi"

    @pytest.mark.regression
    def test_local_force_block_populated(self) -> None:
        result = localise(_mvp_problem_ir())
        lf = result.element_ir.local_force
        assert lf is not None
        assert lf.n_dof == result.element_ir.n_nodes * result.element_ir.dim
        assert lf.contraction_sketch  # non-empty

    @pytest.mark.regression
    def test_local_tangent_block_populated(self) -> None:
        result = localise(_mvp_problem_ir())
        lt = result.element_ir.local_tangent
        assert lt is not None
        assert lt.n_dof == 24
        assert lt.contraction_sketch  # non-empty


class TestSymmetricTangentFlag:
    @pytest.mark.regression
    @pytest.mark.parametrize("model", ["svk", "j2_power_law"])
    def test_symmetric_models_flag_symmetric(self, model: str) -> None:
        result = localise(_mvp_problem_ir(material_model=model))
        assert result.element_ir.local_tangent is not None
        assert result.element_ir.local_tangent.is_symmetric is True

    @pytest.mark.regression
    @pytest.mark.parametrize("model", ["perzyna", "johnson_cook", "lemaitre"])
    def test_non_symmetric_models_flag_non_symmetric(self, model: str) -> None:
        # These models have non-MVP param requirements but the lowering
        # path doesn't enforce P3-5f's required-params at construction —
        # the test exercises the symmetric-flag wiring only.
        result = localise(_mvp_problem_ir(material_model=model))
        assert result.element_ir.local_tangent is not None
        assert result.element_ir.local_tangent.is_symmetric is False


# ---------------------------------------------------------------------------
# 2. Optimizer view is derived from the enriched ElementIR
# ---------------------------------------------------------------------------


class TestOptimizerViewDerivedFromEnrichedIR:
    @pytest.mark.regression
    def test_einsum_specs_match_from_element_ir(self) -> None:
        problem_ir = _mvp_problem_ir()
        result = localise(problem_ir)
        # Re-derive directly from the same enriched ElementIR via the
        # `from_element_ir` classmethod — identical specs are expected.
        rederived = LocalisationResult.from_element_ir(result.element_ir, problem_ir)
        assert tuple(s.einsum_string for s in rederived.einsum_specs) == tuple(
            s.einsum_string for s in result.einsum_specs
        )

    @pytest.mark.regression
    def test_localise_and_optimize_returns_plans(self) -> None:
        loc, plans = localise_and_optimize(_mvp_problem_ir())
        assert isinstance(loc, LocalisationResult)
        assert all(isinstance(p, ContractionPlan) for p in plans)
        # One plan per einsum spec, in the same order.
        assert len(plans) == len(loc.einsum_specs)


# ---------------------------------------------------------------------------
# 3. ArtifactBundle.from_pipeline surfaces the enrichment
# ---------------------------------------------------------------------------


class TestArtifactBundleSurfaceEnrichment:
    @pytest.mark.regression
    def test_element_ir_summary_carries_enrichment_keys(self) -> None:
        loc, plans = localise_and_optimize(_mvp_problem_ir())
        bundle = ArtifactBundle.from_pipeline(
            problem_ir=loc.problem_ir,
            localisation=loc,
            contraction_plans=plans,
        )
        summary = bundle.element_ir_summary
        for key in ("geometry", "material_eval", "local_force", "local_tangent"):
            assert key in summary, f"element_ir_summary must carry {key!r}"
            assert summary[key] is not None  # populated since localise() enriches

        # Spot-check one block end-to-end through the bundle.
        assert summary["geometry"]["n_quad"] == 8
        assert summary["material_eval"]["stress_measure"] == "pk2"
        assert summary["local_force"]["n_dof"] == 24
        assert summary["local_tangent"]["is_symmetric"] is True

    @pytest.mark.regression
    def test_bundle_round_trips_with_enrichment(self) -> None:
        loc, plans = localise_and_optimize(_mvp_problem_ir())
        bundle = ArtifactBundle.from_pipeline(loc.problem_ir, loc, plans)
        rebuilt = ArtifactBundle.from_dict(bundle.to_dict())
        assert rebuilt.element_ir_summary["geometry"] == bundle.element_ir_summary["geometry"]
        assert (
            rebuilt.element_ir_summary["material_eval"]
            == bundle.element_ir_summary["material_eval"]
        )


# ---------------------------------------------------------------------------
# 4. Back-compat: localise() still produces the LocalisationResult shape
# ---------------------------------------------------------------------------


class TestLocaliseBackCompat:
    @pytest.mark.regression
    def test_localise_returns_localisation_result(self) -> None:
        result = localise(_mvp_problem_ir())
        assert isinstance(result, LocalisationResult)
        # The pre-P4-3 fields all still exist with the same names.
        assert result.element_ir is not None
        assert result.einsum_specs
        assert result.problem_ir is not None
