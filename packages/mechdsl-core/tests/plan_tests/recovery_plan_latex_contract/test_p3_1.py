"""Live audit for recovery-plan P3-1: enrich ProblemIR with semantic fields + serialization.

Asserts that:
1. The four optional enrichment dataclasses exist and round-trip standalone.
2. ProblemIR carries the four new optional fields with safe defaults.
3. ``ProblemIR.to_dict() / from_dict()`` round-trip both legacy
   (no enrichment fields) and enriched dicts.
4. Backward compatibility: every legacy construction site still works
   without source changes, and a legacy dict deserializes to an equivalent
   ProblemIR.
"""

from __future__ import annotations

import pytest

from mechdsl.ir.mechanics_ir import (
    ALLOWED_FIELD_KINDS,
    BCType,
    BoundaryCondition,
    DomainSpec,
    ElementType,
    FieldSpec,
    Formulation,
    MaterialSpec,
    MeshContract,
    ProblemIR,
    ResidualContract,
)


def _make_legacy_problem_ir() -> ProblemIR:
    """A ProblemIR built without any Phase-3 enrichment fields."""
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


def _make_enriched_problem_ir() -> ProblemIR:
    """A ProblemIR built WITH every Phase-3 enrichment field populated."""
    return ProblemIR(
        dim=3,
        formulation=Formulation.TOTAL_LAGRANGIAN,
        element_type=ElementType.HEX8,
        material=MaterialSpec(model="svk", params={"E": 200e3, "nu": 0.3}),
        boundaries=(
            BoundaryCondition(name="fix", bc_type=BCType.DIRICHLET),
            BoundaryCondition(name="load", bc_type=BCType.NEUMANN, traction="t_bar"),
        ),
        fields=(FieldSpec(name="u", kind="vector", components=3),),
        domain=DomainSpec(name="unit_cube", metadata={"bbox": [0, 1, 0, 1, 0, 1]}),
        mesh_contract=MeshContract(region_tags=("fix", "load")),
        residual_contract=ResidualContract(
            terms=("internal_force", "external_force"),
            weak_form_label="static_TL",
        ),
    )


class TestEnrichmentDataclassesExist:
    """The four optional enrichment types must round-trip standalone."""

    @pytest.mark.unit
    def test_field_spec_round_trip(self) -> None:
        f = FieldSpec(name="u", kind="vector", components=3)
        assert FieldSpec.from_dict(f.to_dict()) == f

    @pytest.mark.unit
    def test_domain_spec_round_trip(self) -> None:
        d = DomainSpec(name="unit_cube", metadata={"bbox": [0, 1, 0, 1, 0, 1]})
        assert DomainSpec.from_dict(d.to_dict()) == d

    @pytest.mark.unit
    def test_mesh_contract_round_trip(self) -> None:
        m = MeshContract(region_tags=("fix", "load"), metadata={"min_elements": 8})
        assert MeshContract.from_dict(m.to_dict()) == m

    @pytest.mark.unit
    def test_residual_contract_round_trip(self) -> None:
        r = ResidualContract(
            terms=("internal_force", "external_force"),
            weak_form_label="static_TL",
            metadata={"linearity": "nonlinear"},
        )
        assert ResidualContract.from_dict(r.to_dict()) == r


class TestProblemIREnrichmentFields:
    """ProblemIR must expose the four new enrichment fields with safe defaults."""

    @pytest.mark.integration
    def test_legacy_ir_has_safe_default_enrichment(self) -> None:
        ir = _make_legacy_problem_ir()
        assert ir.fields == ()
        assert ir.domain is None
        assert ir.mesh_contract is None
        assert ir.residual_contract is None

    @pytest.mark.integration
    def test_enriched_ir_carries_populated_fields(self) -> None:
        ir = _make_enriched_problem_ir()
        assert len(ir.fields) == 1
        assert ir.fields[0].name == "u"
        assert ir.domain is not None and ir.domain.name == "unit_cube"
        assert ir.mesh_contract is not None
        assert ir.mesh_contract.region_tags == ("fix", "load")
        assert ir.residual_contract is not None
        assert ir.residual_contract.weak_form_label == "static_TL"


class TestProblemIRRoundTrip:
    """Serialization round-trips must preserve both legacy and enriched forms."""

    @pytest.mark.integration
    def test_legacy_round_trip_equal(self) -> None:
        ir = _make_legacy_problem_ir()
        round_tripped = ProblemIR.from_dict(ir.to_dict())
        assert round_tripped == ir

    @pytest.mark.integration
    def test_enriched_round_trip_equal(self) -> None:
        ir = _make_enriched_problem_ir()
        round_tripped = ProblemIR.from_dict(ir.to_dict())
        assert round_tripped == ir

    @pytest.mark.integration
    def test_to_dict_includes_enrichment_keys(self) -> None:
        ir = _make_legacy_problem_ir()
        d = ir.to_dict()
        for key in ("fields", "domain", "mesh_contract", "residual_contract"):
            assert key in d, f"to_dict() must always emit `{key}` for forward consumers"

    @pytest.mark.integration
    def test_from_dict_accepts_legacy_dict_without_enrichment_keys(self) -> None:
        # Build a dict that deliberately omits the four new keys to mimic
        # a pre-recovery golden file.
        legacy_dict = {
            "dim": 3,
            "formulation": "total_lagrangian",
            "element_type": "hex8",
            "material": {"model": "svk", "params": {"E": 200e3, "nu": 0.3}},
            "boundaries": [
                {"name": "fix", "bc_type": "dirichlet"},
            ],
        }
        ir = ProblemIR.from_dict(legacy_dict)
        # Defaults rebuild correctly.
        assert ir.fields == ()
        assert ir.domain is None
        assert ir.mesh_contract is None
        assert ir.residual_contract is None


class TestEnrichmentInvariants:
    """The frozen-dataclass invariant must extend through metadata bags.

    Bare ``frozen=True`` only blocks attribute reassignment; nested dicts can
    still be mutated. The enrichment dataclasses wrap their metadata in
    ``MappingProxyType`` to close that gap.
    """

    @pytest.mark.unit
    def test_field_spec_rejects_unknown_kind(self) -> None:
        with pytest.raises(ValueError, match=r"kind="):
            FieldSpec(name="u", kind="matrix")

    @pytest.mark.unit
    def test_field_spec_accepts_every_allowlisted_kind(self) -> None:
        for kind in ALLOWED_FIELD_KINDS:
            FieldSpec(name="u", kind=kind)

    @pytest.mark.unit
    def test_allowed_field_kinds_is_frozenset(self) -> None:
        assert isinstance(ALLOWED_FIELD_KINDS, frozenset)
        assert frozenset({"scalar", "vector", "tensor"}) == ALLOWED_FIELD_KINDS

    @pytest.mark.unit
    def test_domain_spec_metadata_is_immutable(self) -> None:
        d = DomainSpec(name="cube", metadata={"bbox": [0, 1]})
        with pytest.raises(TypeError):
            d.metadata["bbox"] = [2, 3]
        # MappingProxyType has no `pop`; the AttributeError is itself the
        # invariant we want — write-style methods are not exposed at all.
        with pytest.raises(AttributeError):
            d.metadata.pop("bbox")

    @pytest.mark.unit
    def test_mesh_contract_metadata_is_immutable(self) -> None:
        m = MeshContract(region_tags=("a",), metadata={"min_elements": 8})
        with pytest.raises(TypeError):
            m.metadata["min_elements"] = 16

    @pytest.mark.unit
    def test_residual_contract_metadata_is_immutable(self) -> None:
        r = ResidualContract(terms=("internal",), metadata={"linearity": "nonlinear"})
        with pytest.raises(TypeError):
            r.metadata["linearity"] = "linear"

    @pytest.mark.unit
    def test_immutable_metadata_still_round_trips(self) -> None:
        d = DomainSpec(name="cube", metadata={"bbox": [0, 1]})
        m = MeshContract(region_tags=("a",), metadata={"min_elements": 8})
        r = ResidualContract(terms=("internal",), metadata={"linearity": "nonlinear"})
        assert DomainSpec.from_dict(d.to_dict()) == d
        assert MeshContract.from_dict(m.to_dict()) == m
        assert ResidualContract.from_dict(r.to_dict()) == r
