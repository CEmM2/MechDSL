"""Tests for Layer 4 — FE localisation pass (ProblemIR -> ElementIR + einsums)."""

from __future__ import annotations

import pytest

from mechdsl.ir.mechanics_ir import (
    BCType,
    BoundaryCondition,
    ElementType,
    Formulation,
    MaterialSpec,
    ProblemIR,
)
from mechdsl.lowering.fe_localise import (
    EinsumSpec,
    LocalisationResult,
    localise,
)

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _make_mvp_problem(**overrides) -> ProblemIR:
    """Build a valid MVP ProblemIR (3D, Hex8, TL, SVK) with optional overrides."""
    defaults: dict = {
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


def _find_spec(result: LocalisationResult, name: str) -> EinsumSpec:
    """Find an EinsumSpec by name, raising if missing."""
    for spec in result.einsum_specs:
        if spec.name == name:
            return spec
    raise AssertionError(f"EinsumSpec '{name}' not found in result")


# ------------------------------------------------------------------
# 1. MVP input produces valid LocalisationResult
# ------------------------------------------------------------------


class TestLocaliseHappy:
    def test_mvp_input_produces_result(self):
        """3D Hex8 TL SVK input yields a LocalisationResult."""
        p = _make_mvp_problem()
        result = localise(p)
        assert isinstance(result, LocalisationResult)

    def test_j2_material_also_localises(self):
        """J2 power-law material also passes localisation."""
        mat = MaterialSpec(
            model="j2_power_law",
            params={"E": 200e3, "nu": 0.3, "sigma_y": 250.0, "n": 10.0},
        )
        result = localise(_make_mvp_problem(material=mat))
        assert isinstance(result, LocalisationResult)


# ------------------------------------------------------------------
# 2. ElementIR in result is correct Hex8 configuration
# ------------------------------------------------------------------


class TestElementIR:
    def test_element_type_hex8(self):
        result = localise(_make_mvp_problem())
        assert result.element_ir.element_type == "hex8"

    def test_n_nodes(self):
        result = localise(_make_mvp_problem())
        assert result.element_ir.n_nodes == 8

    def test_dim(self):
        result = localise(_make_mvp_problem())
        assert result.element_ir.dim == 3

    def test_quadrature_points(self):
        result = localise(_make_mvp_problem())
        assert result.element_ir.quadrature.n_points == 8

    def test_formulation(self):
        result = localise(_make_mvp_problem())
        assert result.element_ir.formulation == "total_lagrangian"


# ------------------------------------------------------------------
# 3. Einsum spec present for internal_force
# ------------------------------------------------------------------


class TestInternalForceEinsum:
    def test_present(self):
        result = localise(_make_mvp_problem())
        spec = _find_spec(result, "internal_force")
        assert spec.name == "internal_force"

    def test_einsum_string_nonempty(self):
        result = localise(_make_mvp_problem())
        spec = _find_spec(result, "internal_force")
        assert len(spec.einsum_string) > 0
        assert "->" in spec.einsum_string

    def test_operand_count(self):
        result = localise(_make_mvp_problem())
        spec = _find_spec(result, "internal_force")
        # internal_force has 2 operands: dN and P
        assert len(spec.operand_shapes) == 2

    def test_result_shape(self):
        result = localise(_make_mvp_problem())
        spec = _find_spec(result, "internal_force")
        # result is (n_qp, n_nodes, dim) = (8, 8, 3)
        assert spec.result_shape == (8, 8, 3)


# ------------------------------------------------------------------
# 4. Einsum spec present for strain_displacement
# ------------------------------------------------------------------


class TestStrainDisplacementEinsum:
    def test_present(self):
        result = localise(_make_mvp_problem())
        spec = _find_spec(result, "strain_displacement")
        assert spec.name == "strain_displacement"

    def test_einsum_string_nonempty(self):
        result = localise(_make_mvp_problem())
        spec = _find_spec(result, "strain_displacement")
        assert len(spec.einsum_string) > 0
        assert "->" in spec.einsum_string

    def test_operand_count(self):
        result = localise(_make_mvp_problem())
        spec = _find_spec(result, "strain_displacement")
        # strain_displacement has 2 operands: dN and u
        assert len(spec.operand_shapes) == 2

    def test_result_shape(self):
        result = localise(_make_mvp_problem())
        spec = _find_spec(result, "strain_displacement")
        # result is (n_qp, dim, dim) = (8, 3, 3)
        assert spec.result_shape == (8, 3, 3)


# ------------------------------------------------------------------
# 5. Einsum spec present for tangent_matvec
# ------------------------------------------------------------------


class TestTangentMatvecEinsum:
    def test_present(self):
        result = localise(_make_mvp_problem())
        spec = _find_spec(result, "tangent_matvec")
        assert spec.name == "tangent_matvec"

    def test_einsum_string_nonempty(self):
        result = localise(_make_mvp_problem())
        spec = _find_spec(result, "tangent_matvec")
        assert len(spec.einsum_string) > 0
        assert "->" in spec.einsum_string

    def test_operand_count(self):
        result = localise(_make_mvp_problem())
        spec = _find_spec(result, "tangent_matvec")
        # tangent_matvec has 3 operands: dN_left, A, dN_right
        assert len(spec.operand_shapes) == 3

    def test_result_shape(self):
        result = localise(_make_mvp_problem())
        spec = _find_spec(result, "tangent_matvec")
        # result is (n_qp, n_nodes, dim, n_nodes, dim) = (8, 8, 3, 8, 3)
        assert spec.result_shape == (8, 8, 3, 8, 3)


# ------------------------------------------------------------------
# 6. Einsum string shapes are consistent
# ------------------------------------------------------------------


class TestEinsumShapeConsistency:
    """Verify that einsum strings, operand shapes, and result shapes agree."""

    @staticmethod
    def _parse_einsum(einsum_str: str) -> tuple[list[str], str]:
        """Parse 'ab,bc->ac' into (['ab', 'bc'], 'ac')."""
        lhs, rhs = einsum_str.split("->")
        operands = lhs.split(",")
        return operands, rhs

    def test_operand_ranks_match_einsum_indices(self):
        """Each operand's rank matches the number of indices in the einsum."""
        result = localise(_make_mvp_problem())
        for spec in result.einsum_specs:
            ops, _rhs = self._parse_einsum(spec.einsum_string)
            assert len(ops) == len(spec.operand_shapes), (
                f"{spec.name}: einsum has {len(ops)} operands "
                f"but operand_shapes has {len(spec.operand_shapes)}"
            )
            for i, (indices, shape) in enumerate(zip(ops, spec.operand_shapes, strict=True)):
                assert len(indices) == len(shape), (
                    f"{spec.name} operand {i}: "
                    f"einsum indices '{indices}' (rank {len(indices)}) "
                    f"vs shape {shape} (rank {len(shape)})"
                )

    def test_result_rank_matches_einsum_output(self):
        """Result rank matches the number of output indices."""
        result = localise(_make_mvp_problem())
        for spec in result.einsum_specs:
            _ops, rhs = self._parse_einsum(spec.einsum_string)
            assert len(rhs) == len(spec.result_shape), (
                f"{spec.name}: einsum output '{rhs}' (rank {len(rhs)}) "
                f"vs result_shape {spec.result_shape} (rank {len(spec.result_shape)})"
            )

    def test_all_three_specs_present(self):
        """Exactly three einsum specs are produced."""
        result = localise(_make_mvp_problem())
        assert len(result.einsum_specs) == 3
        names = {s.name for s in result.einsum_specs}
        assert names == {"strain_displacement", "internal_force", "tangent_matvec"}


# ------------------------------------------------------------------
# 7. Incompatible formulation rejected with error
# ------------------------------------------------------------------


class TestIncompatibleFormulation:
    """Plan B §B1.3 promoted UPDATED_LAGRANGIAN from a rejected construct to a
    supported formulation. The old enum-hack test that asserted a mock UL
    member was rejected by ``localise`` no longer applies. The replacement
    test asserts the positive path: localise now accepts UL and returns an
    ElementIR tagged with the current configuration.
    """

    def test_ul_localises_to_current_configuration_element_ir(self):
        """Localising a UL ProblemIR produces an ElementIR in current config."""
        from mechdsl.ir.mechanics_ir import Configuration

        problem = ProblemIR(
            dim=3,
            formulation=Formulation.UPDATED_LAGRANGIAN,
            element_type=ElementType.HEX8,
            material=MaterialSpec(model="svk", params={"E": 1000.0, "nu": 0.3}),
            boundaries=(BoundaryCondition(name="fix", bc_type=BCType.DIRICHLET, value=0.0),),
            configuration=Configuration.CURRENT,
        )
        result = localise(problem)
        assert result.element_ir.formulation == "updated_lagrangian"
        assert result.element_ir.configuration == "current"


# ------------------------------------------------------------------
# 8. Incompatible element type rejected with error
# ------------------------------------------------------------------


class TestIncompatibleElementType:
    def test_non_hex8_rejected(self):
        """Non-Hex8 element type raises ValueError mentioning Plan B."""
        original_members = dict(ElementType.__members__)
        try:
            test_val = object.__new__(ElementType)
            test_val._value_ = "tet4"
            test_val._name_ = "TET4"
            ElementType._member_map_["TET4"] = test_val
            ElementType._value2member_map_["tet4"] = test_val

            from mechdsl.ir.mechanics_ir import ProblemIR as _PIR

            p = object.__new__(_PIR)
            object.__setattr__(p, "dim", 3)
            object.__setattr__(p, "formulation", Formulation.TOTAL_LAGRANGIAN)
            object.__setattr__(p, "element_type", test_val)
            object.__setattr__(
                p,
                "material",
                MaterialSpec(model="svk", params={"E": 1000.0, "nu": 0.3}),
            )
            object.__setattr__(
                p,
                "boundaries",
                (BoundaryCondition(name="fix", bc_type=BCType.DIRICHLET, value=0.0),),
            )
            object.__setattr__(p, "coord_spatial", ("x", "y", "z"))
            object.__setattr__(p, "coord_material", ("X", "Y", "Z"))

            with pytest.raises(ValueError, match="Plan B"):
                localise(p)
        finally:
            ElementType._member_map_.clear()
            ElementType._member_map_.update(original_members)
            ElementType._value2member_map_.pop("tet4", None)


# ------------------------------------------------------------------
# 9. LocalisationResult is immutable (frozen)
# ------------------------------------------------------------------


class TestImmutability:
    def test_localisation_result_frozen(self):
        """LocalisationResult is a frozen dataclass — cannot mutate."""
        result = localise(_make_mvp_problem())
        with pytest.raises(AttributeError):
            result.element_ir = None  # type: ignore[misc]

    def test_einsum_spec_frozen(self):
        """EinsumSpec is a frozen dataclass — cannot mutate."""
        result = localise(_make_mvp_problem())
        spec = result.einsum_specs[0]
        with pytest.raises(AttributeError):
            spec.name = "hacked"  # type: ignore[misc]


# ------------------------------------------------------------------
# 10. ProblemIR back-reference preserved
# ------------------------------------------------------------------


class TestBackReference:
    def test_problem_ir_preserved(self):
        """LocalisationResult retains the original ProblemIR."""
        p = _make_mvp_problem()
        result = localise(p)
        assert result.problem_ir is p

    def test_problem_ir_fields_accessible(self):
        """Can access ProblemIR fields through the back-reference."""
        p = _make_mvp_problem()
        result = localise(p)
        assert result.problem_ir.dim == 3
        assert result.problem_ir.formulation == Formulation.TOTAL_LAGRANGIAN
        assert result.problem_ir.element_type == ElementType.HEX8
        assert result.problem_ir.material.model == "svk"
