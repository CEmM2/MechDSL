"""Tests for Layer 3 — Mechanics IR construction and validation."""

import json

import pytest

from mechdsl.ir.mechanics_ir import (
    BCType,
    BoundaryCondition,
    ElementType,
    Formulation,
    MaterialSpec,
    ProblemIR,
)


def _make_valid_problem(**overrides) -> ProblemIR:
    """Helper to build a valid MVP ProblemIR with optional overrides."""
    defaults = {
        "dim": 3,
        "formulation": Formulation.TOTAL_LAGRANGIAN,
        "element_type": ElementType.HEX8,
        "material": MaterialSpec(model="svk", params={"E": 1000.0, "nu": 0.3}),
        "boundaries": (
            BoundaryCondition(
                name="fix_base",
                bc_type=BCType.DIRICHLET,
                components=(0, 1, 2),
                value=0.0,
            ),
        ),
    }
    defaults.update(overrides)
    return ProblemIR(**defaults)


# ------------------------------------------------------------------
# 1. Valid MVP input constructs ProblemIR
# ------------------------------------------------------------------


class TestProblemIRConstruction:
    def test_valid_svk(self):
        """Valid SVK problem builds without error."""
        p = _make_valid_problem()
        assert p.dim == 3
        assert p.formulation == Formulation.TOTAL_LAGRANGIAN
        assert p.element_type == ElementType.HEX8
        assert p.material.model == "svk"
        assert len(p.boundaries) == 1

    def test_valid_j2(self):
        """Valid J2 problem builds without error."""
        mat = MaterialSpec(
            model="j2_power_law",
            params={"E": 200e3, "nu": 0.3, "sigma_y0": 250.0, "K": 1000.0, "n": 10.0},
        )
        p = _make_valid_problem(material=mat)
        assert p.material.model == "j2_power_law"

    def test_multiple_bcs(self):
        """Multiple boundary conditions accepted."""
        bcs = (
            BoundaryCondition(name="fix_base", bc_type=BCType.DIRICHLET, value=0.0),
            BoundaryCondition(
                name="load_top",
                bc_type=BCType.NEUMANN,
                traction="1e3",
            ),
        )
        p = _make_valid_problem(boundaries=bcs)
        assert len(p.boundaries) == 2

    def test_default_coordinates(self):
        """Default coordinate names are x,y,z and X,Y,Z."""
        p = _make_valid_problem()
        assert p.coord_spatial == ("x", "y", "z")
        assert p.coord_material == ("X", "Y", "Z")


# ------------------------------------------------------------------
# 2. Round-trip: to_dict -> from_dict preserves all fields
# ------------------------------------------------------------------


class TestRoundTrip:
    def test_to_dict_from_dict(self):
        """to_dict -> from_dict produces an equal ProblemIR."""
        original = _make_valid_problem()
        d = original.to_dict()
        restored = ProblemIR.from_dict(d)
        assert restored.dim == original.dim
        assert restored.formulation == original.formulation
        assert restored.element_type == original.element_type
        assert restored.material.model == original.material.model
        assert restored.material.params == original.material.params
        assert len(restored.boundaries) == len(original.boundaries)
        assert restored.boundaries[0].name == original.boundaries[0].name
        assert restored.boundaries[0].bc_type == original.boundaries[0].bc_type
        assert restored.coord_spatial == original.coord_spatial
        assert restored.coord_material == original.coord_material

    def test_round_trip_with_j2_and_neumann(self):
        """Round-trip with J2 material and Neumann BC."""
        mat = MaterialSpec(
            model="j2_power_law",
            params={"E": 200e3, "nu": 0.3, "sigma_y0": 250.0, "K": 1000.0, "n": 10.0},
        )
        bcs = (
            BoundaryCondition(name="fix", bc_type=BCType.DIRICHLET, value=0.0),
            BoundaryCondition(
                name="load",
                bc_type=BCType.NEUMANN,
                components=(2,),
                traction="1e3",
            ),
        )
        original = _make_valid_problem(material=mat, boundaries=bcs)
        restored = ProblemIR.from_dict(original.to_dict())
        assert restored.material.params["sigma_y0"] == 250.0
        assert restored.boundaries[1].traction == "1e3"
        assert restored.boundaries[1].components == (2,)


# ------------------------------------------------------------------
# 3. JSON serialization round-trip
# ------------------------------------------------------------------


class TestJSONRoundTrip:
    def test_json_serialization(self):
        """Serialize to JSON string and back."""
        original = _make_valid_problem()
        json_str = json.dumps(original.to_dict(), indent=2)
        d = json.loads(json_str)
        restored = ProblemIR.from_dict(d)
        assert restored.dim == original.dim
        assert restored.formulation == original.formulation
        assert restored.material.model == original.material.model

    def test_json_types_are_primitive(self):
        """to_dict output contains only JSON-primitive types."""
        d = _make_valid_problem().to_dict()
        # Must not raise — all values are JSON-serializable
        json_str = json.dumps(d)
        assert isinstance(json_str, str)
        # Check specific types
        assert isinstance(d["dim"], int)
        assert isinstance(d["formulation"], str)
        assert isinstance(d["boundaries"], list)
        assert isinstance(d["coord_spatial"], list)


# ------------------------------------------------------------------
# 4. Invalid dim (dim=2) raises ValueError
# ------------------------------------------------------------------


class TestInvalidDim:
    def test_dim_2_rejected(self):
        """dim=2 raises ValueError mentioning Plan B."""
        with pytest.raises(ValueError, match="Plan B"):
            ProblemIR(
                dim=2,
                formulation=Formulation.TOTAL_LAGRANGIAN,
                element_type=ElementType.HEX8,
                material=MaterialSpec(model="svk"),
                boundaries=(BoundaryCondition(name="fix", bc_type=BCType.DIRICHLET),),
                coord_spatial=("x", "y"),
                coord_material=("X", "Y"),
            )

    def test_dim_1_rejected(self):
        """dim=1 also rejected."""
        with pytest.raises(ValueError, match="dim=1"):
            ProblemIR(
                dim=1,
                formulation=Formulation.TOTAL_LAGRANGIAN,
                element_type=ElementType.HEX8,
                material=MaterialSpec(model="svk"),
                boundaries=(BoundaryCondition(name="fix", bc_type=BCType.DIRICHLET),),
                coord_spatial=("x",),
                coord_material=("X",),
            )


# ------------------------------------------------------------------
# 5. Invalid formulation raises
# ------------------------------------------------------------------


class TestInvalidFormulation:
    """Plan B §B1.3 added UPDATED_LAGRANGIAN alongside TOTAL_LAGRANGIAN.

    The old enum-hack tests in this class rejected a mock UL member and
    asserted the error message pointed at Plan B phase B1. After Plan B
    §B1.3, UL is a first-class formulation, so those guards no longer
    fire. The tests below now pin the positive acceptance path and the
    new consistency invariant between formulation and configuration.
    """

    def test_updated_lagrangian_is_accepted(self) -> None:
        """UL + CURRENT configuration constructs a valid ProblemIR."""
        from mechdsl.ir.mechanics_ir import Configuration

        ir = ProblemIR(
            dim=3,
            formulation=Formulation.UPDATED_LAGRANGIAN,
            element_type=ElementType.HEX8,
            material=MaterialSpec(model="svk", params={"E": 200e3, "nu": 0.3}),
            boundaries=(BoundaryCondition(name="fix", bc_type=BCType.DIRICHLET),),
            configuration=Configuration.CURRENT,
        )
        assert ir.formulation is Formulation.UPDATED_LAGRANGIAN
        assert ir.configuration is Configuration.CURRENT

    def test_formulation_configuration_consistency_guard(self) -> None:
        """Mismatched formulation/configuration pairs raise ValueError."""
        from mechdsl.ir.mechanics_ir import Configuration

        # TL + CURRENT rejected
        with pytest.raises(ValueError, match="configuration"):
            ProblemIR(
                dim=3,
                formulation=Formulation.TOTAL_LAGRANGIAN,
                element_type=ElementType.HEX8,
                material=MaterialSpec(model="svk", params={"E": 200e3, "nu": 0.3}),
                boundaries=(BoundaryCondition(name="fix", bc_type=BCType.DIRICHLET),),
                configuration=Configuration.CURRENT,
            )
        # UL + REFERENCE rejected
        with pytest.raises(ValueError, match="configuration"):
            ProblemIR(
                dim=3,
                formulation=Formulation.UPDATED_LAGRANGIAN,
                element_type=ElementType.HEX8,
                material=MaterialSpec(model="svk", params={"E": 200e3, "nu": 0.3}),
                boundaries=(BoundaryCondition(name="fix", bc_type=BCType.DIRICHLET),),
                configuration=Configuration.REFERENCE,
            )


# ------------------------------------------------------------------
# 6. Invalid element type raises
# ------------------------------------------------------------------


class TestInvalidElementType:
    def test_element_type_guard_message(self):
        """Unsupported element type (Hex27) raises ValueError mentioning Plan B."""
        original_members = dict(ElementType.__members__)
        try:
            test_val = object.__new__(ElementType)
            test_val._value_ = "hex27"
            test_val._name_ = "HEX27"
            ElementType._member_map_["HEX27"] = test_val
            ElementType._value2member_map_["hex27"] = test_val

            with pytest.raises(ValueError, match="Plan B"):
                ProblemIR(
                    dim=3,
                    formulation=Formulation.TOTAL_LAGRANGIAN,
                    element_type=test_val,
                    material=MaterialSpec(model="svk"),
                    boundaries=(BoundaryCondition(name="fix", bc_type=BCType.DIRICHLET),),
                )
        finally:
            ElementType._member_map_.clear()
            ElementType._member_map_.update(original_members)
            ElementType._value2member_map_.pop("hex27", None)


# ------------------------------------------------------------------
# 7. Unknown material model raises
# ------------------------------------------------------------------


class TestInvalidMaterial:
    def test_unknown_model_rejected(self):
        """Unknown material model raises ValueError."""
        with pytest.raises(ValueError, match="Unknown material model"):
            _make_valid_problem(material=MaterialSpec(model="lemaitre_damage"))

    def test_empty_model_rejected(self):
        """Empty material model string raises."""
        with pytest.raises(ValueError, match="Unknown material model"):
            _make_valid_problem(material=MaterialSpec(model=""))


# ------------------------------------------------------------------
# 8. Missing boundaries raises
# ------------------------------------------------------------------


class TestMissingBoundaries:
    def test_empty_boundaries_rejected(self):
        """Empty boundary tuple raises ValueError."""
        with pytest.raises(ValueError, match="At least one boundary condition"):
            _make_valid_problem(boundaries=())


# ------------------------------------------------------------------
# 9. Mismatched coordinate dimensions raise
# ------------------------------------------------------------------


class TestCoordinateMismatch:
    def test_spatial_coord_mismatch(self):
        """Spatial coordinate count != dim raises ValueError."""
        with pytest.raises(ValueError, match="spatial coordinates"):
            _make_valid_problem(coord_spatial=("x", "y"))

    def test_material_coord_mismatch(self):
        """Material coordinate count != dim raises ValueError."""
        with pytest.raises(ValueError, match="material coordinates"):
            _make_valid_problem(coord_material=("X", "Y"))

    def test_extra_spatial_coords(self):
        """Too many spatial coordinates also rejected."""
        with pytest.raises(ValueError, match="spatial coordinates"):
            _make_valid_problem(coord_spatial=("x", "y", "z", "w"))
