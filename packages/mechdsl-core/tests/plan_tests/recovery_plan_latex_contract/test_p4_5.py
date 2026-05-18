"""Live audit for recovery-plan P4-5: artifact bundling reflects enriched IR.

Asserts that:

1. ``ArtifactBundle.from_pipeline`` populates a new ``element_ir_dict``
   field carrying the canonical ``ElementIR.to_dict()`` output (the P4-1
   contract surface).
2. The bundle's ``to_dict / from_dict`` round-trips ``element_ir_dict``
   through a JSON pass; the round-tripped bundle is equal to the
   original.
3. Legacy bundles without ``element_ir_dict`` deserialise cleanly with
   the new field defaulting to an empty dict — golden files from earlier
   phases continue to round-trip.
4. ``content_hash`` is stable for pre-P4-5 bundles (the legacy
   ``element_ir_summary`` already carries the P4-3 enrichment that the
   hash covers; ``element_ir_dict`` is informational and does not
   participate in the hash).
5. The IR-ownership hierarchy documented in the bundle docstring matches
   the runtime structure: ``element_ir_dict`` carries the four P4-1
   contract blocks; ``contraction_plans`` are present alongside as the
   derived optimizer view.
"""

from __future__ import annotations

import pytest

from mechdsl.codegen.artifact import ArtifactBundle
from mechdsl.ir.mechanics_ir import (
    BCType,
    BoundaryCondition,
    ElementType,
    Formulation,
    MaterialSpec,
    ProblemIR,
)
from mechdsl.lowering.fe_localise import localise_and_optimize


def _bundle() -> ArtifactBundle:
    problem_ir = ProblemIR(
        dim=3,
        formulation=Formulation.TOTAL_LAGRANGIAN,
        element_type=ElementType.HEX8,
        material=MaterialSpec(model="svk", params={"E": 200e3, "nu": 0.3}),
        boundaries=(
            BoundaryCondition(name="fix", bc_type=BCType.DIRICHLET),
            BoundaryCondition(name="load", bc_type=BCType.NEUMANN, traction="t_bar"),
        ),
    )
    loc, plans = localise_and_optimize(problem_ir)
    return ArtifactBundle.from_pipeline(loc.problem_ir, loc, plans)


# ---------------------------------------------------------------------------
# 1. element_ir_dict carries the canonical contract surface
# ---------------------------------------------------------------------------


class TestElementIRDictPopulated:
    @pytest.mark.unit
    def test_field_exists_on_bundle(self) -> None:
        bundle = _bundle()
        assert hasattr(bundle, "element_ir_dict")
        assert isinstance(bundle.element_ir_dict, dict)

    @pytest.mark.unit
    def test_field_carries_canonical_contract_surface(self) -> None:
        bundle = _bundle()
        d = bundle.element_ir_dict
        # Every key documented on ElementIR.to_dict() must be present.
        for key in (
            "element_type",
            "n_nodes",
            "dim",
            "formulation",
            "configuration",
            "integration_rule",
            "geometry",
            "material_eval",
            "local_force",
            "local_tangent",
        ):
            assert key in d, f"element_ir_dict missing key {key!r}"

    @pytest.mark.unit
    def test_field_carries_p4_1_enrichment(self) -> None:
        bundle = _bundle()
        d = bundle.element_ir_dict
        # The four P4-1 contract blocks come back fully populated because
        # localise() (post-P4-3) enriches the IR. Each must serialize as a
        # dict, not None.
        assert isinstance(d["geometry"], dict)
        assert isinstance(d["material_eval"], dict)
        assert isinstance(d["local_force"], dict)
        assert isinstance(d["local_tangent"], dict)
        # Spot-check one nested value end-to-end.
        assert d["geometry"]["n_quad"] == 8
        assert d["material_eval"]["stress_measure"] == "pk2"
        assert d["local_force"]["n_dof"] == 24
        assert d["local_tangent"]["is_symmetric"] is True


# ---------------------------------------------------------------------------
# 2. JSON round-trip preserves element_ir_dict + plans
# ---------------------------------------------------------------------------


class TestRoundTrip:
    @pytest.mark.unit
    def test_to_dict_includes_element_ir_dict(self) -> None:
        bundle = _bundle()
        d = bundle.to_dict()
        assert "element_ir_dict" in d
        assert d["element_ir_dict"] == bundle.element_ir_dict

    @pytest.mark.unit
    def test_round_trip_preserves_enrichment(self) -> None:
        bundle = _bundle()
        rebuilt = ArtifactBundle.from_dict(bundle.to_dict())
        assert rebuilt.element_ir_dict == bundle.element_ir_dict
        assert rebuilt.contraction_plans == bundle.contraction_plans

    @pytest.mark.unit
    def test_round_trip_through_json_string(self) -> None:
        bundle = _bundle()
        json_text = bundle.to_json()
        rebuilt = ArtifactBundle.from_json(json_str=json_text)
        assert rebuilt.element_ir_dict == bundle.element_ir_dict
        assert tuple(p.to_dict() for p in rebuilt.contraction_plans) == tuple(
            p.to_dict() for p in bundle.contraction_plans
        )


# ---------------------------------------------------------------------------
# 3. Legacy bundles round-trip without element_ir_dict
# ---------------------------------------------------------------------------


class TestLegacyBundleCompat:
    @pytest.mark.unit
    def test_legacy_dict_without_element_ir_dict_deserialises(self) -> None:
        # Hand-build a pre-P4-5 dict with the only-required keys.
        legacy_dict = {
            "problem_ir_dict": {"dim": 3, "formulation": "total_lagrangian"},
            "element_ir_summary": {"element_type": "hex8", "n_nodes": 8},
        }
        bundle = ArtifactBundle.from_dict(legacy_dict)
        assert bundle.element_ir_dict == {}

    @pytest.mark.unit
    def test_legacy_bundle_round_trips_without_loss(self) -> None:
        legacy_dict = {
            "problem_ir_dict": {"dim": 3, "formulation": "total_lagrangian"},
            "element_ir_summary": {"element_type": "hex8", "n_nodes": 8},
        }
        rebuilt = ArtifactBundle.from_dict(legacy_dict).to_dict()
        # New key emitted but empty — does not change the legacy semantic
        # content. Pre-P4-5 consumers ignore the unfamiliar key.
        assert rebuilt["element_ir_dict"] == {}
        assert rebuilt["problem_ir_dict"] == legacy_dict["problem_ir_dict"]
        assert rebuilt["element_ir_summary"] == legacy_dict["element_ir_summary"]


# ---------------------------------------------------------------------------
# 4. content_hash unchanged for pre-P4-5 inputs
# ---------------------------------------------------------------------------


class TestContentHashStability:
    @pytest.mark.unit
    def test_hash_does_not_depend_on_element_ir_dict_value(self) -> None:
        bundle = _bundle()
        baseline_hash = bundle.content_hash()
        # Mutate `element_ir_dict` (via dataclasses.replace) and confirm
        # the hash is unchanged — content_hash deliberately covers the
        # legacy summary + plans only, so the new field stays
        # informational and pre-P4-5 golden hashes survive.
        from dataclasses import replace as _replace

        mutated = _replace(bundle, element_ir_dict={"injected": "value"})
        assert mutated.content_hash() == baseline_hash


# ---------------------------------------------------------------------------
# 5. Ownership hierarchy is reflected in the bundle docstring
# ---------------------------------------------------------------------------


class TestOwnershipDocumented:
    @pytest.mark.unit
    def test_docstring_describes_post_p4_5_hierarchy(self) -> None:
        assert ArtifactBundle.__doc__ is not None
        doc = ArtifactBundle.__doc__
        assert "element_ir_dict" in doc
        assert "P4-5" in doc
        # The "primary semantic carrier" / "derived optimizer view" framing
        # makes the ownership question concrete in the docstring.
        assert "primary" in doc.lower()
        assert "derived" in doc.lower()
