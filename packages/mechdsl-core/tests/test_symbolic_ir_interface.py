"""Boundary tests for the symbolic → Mechanics IR interface.

These tests document which combinations of kinematic formulation, element
type, and material model are accepted or rejected at the ``ProblemIR``
construction boundary, and verify that every rejection message names the
Plan B phase that adds support.

Why this file exists
--------------------
The symbolic layer (``mechdsl.symbolic``) produces ``KinematicsResult`` and
``ConstitutiveModel`` outputs consumed during lowering and codegen.
``ProblemIR`` is the gate that validates the supported subset *before* any
symbolic computation begins.  Without explicit boundary tests it is unclear,
from the test files alone, which combinations are valid inputs to
``ProblemIR`` construction versus which should raise — you have to read the
lowering code to find out.

This file makes the acceptance/rejection surface explicit so that Plan B
additions (new formulations, elements, constitutive models) know exactly
what needs to change in ``ProblemIR.__post_init__``.

Spec refs
---------
- ``dev/design_docs/07-CONVENTIONS.md`` — index convention and Voigt ordering
- ``ir.md`` rule "Supported-subset validation" — every rejection must name
  the Plan B phase that adds support.
"""

from __future__ import annotations

import dataclasses

import pytest

from mechdsl.ir.mechanics_ir import (
    BCType,
    BoundaryCondition,
    BoundaryRegionError,
    ElementType,
    Formulation,
    MaterialSpec,
    ProblemIR,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _one_bc(name: str = "fix", bc_type: BCType = BCType.DIRICHLET) -> tuple[BoundaryCondition, ...]:
    """Minimal single-BC tuple."""
    return (BoundaryCondition(name=name, bc_type=bc_type),)


def _valid_ir(**overrides) -> ProblemIR:
    """Construct the minimal valid MVP ProblemIR, with optional field overrides."""
    defaults: dict = dict(
        dim=3,
        formulation=Formulation.TOTAL_LAGRANGIAN,
        element_type=ElementType.HEX8,
        material=MaterialSpec(model="svk", params={"E": 200e3, "nu": 0.3}),
        boundaries=_one_bc(),
    )
    defaults.update(overrides)
    return ProblemIR(**defaults)


def _plant_field(ir: ProblemIR, name: str, value: object) -> ProblemIR:
    """Return a copy of *ir* with *name* replaced by *value*, bypassing frozen.

    Used to trigger validation guards that require enum-busting without
    having to construct the whole IR from scratch.
    """
    obj = ProblemIR.__new__(ProblemIR)
    for f in dataclasses.fields(ir):
        object.__setattr__(obj, f.name, getattr(ir, f.name))
    object.__setattr__(obj, name, value)
    return obj


# ---------------------------------------------------------------------------
# Valid combinations — must construct without raising
# ---------------------------------------------------------------------------


class TestValidCombinations:
    """All combinations currently in the MVP supported subset."""

    def test_svk_total_lagrangian_hex8(self) -> None:
        ir = _valid_ir()
        assert ir.material.model == "svk"
        assert ir.formulation == Formulation.TOTAL_LAGRANGIAN
        assert ir.element_type == ElementType.HEX8
        assert ir.dim == 3

    def test_j2_power_law_total_lagrangian_hex8(self) -> None:
        ir = _valid_ir(
            material=MaterialSpec(
                model="j2_power_law",
                params={"E": 200e3, "nu": 0.3, "sigma_y0": 250.0, "K_hard": 500.0, "n_hard": 0.5},
            )
        )
        assert ir.material.model == "j2_power_law"

    def test_multiple_boundary_conditions(self) -> None:
        bcs = (
            BoundaryCondition(name="fix", bc_type=BCType.DIRICHLET),
            BoundaryCondition(name="load", bc_type=BCType.NEUMANN, traction="t_bar"),
        )
        ir = _valid_ir(boundaries=bcs)
        assert len(ir.boundaries) == 2

    def test_declared_regions_matching_all_bcs(self) -> None:
        bcs = (
            BoundaryCondition(name="fix", bc_type=BCType.DIRICHLET),
            # Neumann BCs require a traction spec.
            BoundaryCondition(name="load", bc_type=BCType.NEUMANN, traction="t_bar"),
        )
        ir = _valid_ir(boundaries=bcs, declared_regions=frozenset({"fix", "load"}))
        assert ir.declared_regions == frozenset({"fix", "load"})


class TestInvalidDimension:
    """dim != 3 is outside the MVP subset; Plan B phase B2 adds 2-D support."""

    def test_dim_2_raises_with_plan_b2_message(self) -> None:
        with pytest.raises(ValueError, match="Plan B phase B2"):
            _valid_ir(dim=2)

    def test_dim_1_raises_with_plan_b2_message(self) -> None:
        with pytest.raises(ValueError, match="Plan B phase B2"):
            _valid_ir(dim=1)


class TestFormulationGuard:
    """Plan B §B1.3 promoted UPDATED_LAGRANGIAN into the supported subset.

    These tests previously asserted that TOTAL_LAGRANGIAN was the *only* valid
    formulation. After §B1.3, both TL and UL are first-class, and ProblemIR's
    validation moved from a formulation-rejection guard to a
    formulation/configuration consistency guard.
    """

    def test_both_tl_and_ul_are_valid_formulations(self) -> None:
        """Formulation enum exposes exactly {TL, UL}.

        A new member added without updating this test should cause a failure
        here, prompting the implementer to verify the new member is paired
        with the correct Configuration in ProblemIR.__post_init__.
        """
        members = {m for m in Formulation}
        assert members == {
            Formulation.TOTAL_LAGRANGIAN,
            Formulation.UPDATED_LAGRANGIAN,
        }, (
            "A new Formulation enum member was added without updating this test. "
            "Verify the new member is guarded correctly in ProblemIR.__post_init__ "
            "and paired with the correct Configuration enum value."
        )

    def test_formulation_configuration_mismatch_is_rejected(self) -> None:
        """TL paired with CURRENT (or UL paired with REFERENCE) raises ValueError."""
        from mechdsl.ir.mechanics_ir import Configuration

        # TL must be paired with REFERENCE.
        with pytest.raises(ValueError, match="configuration"):
            _valid_ir(configuration=Configuration.CURRENT)
        # UL must be paired with CURRENT.
        with pytest.raises(ValueError, match="configuration"):
            _valid_ir(
                formulation=Formulation.UPDATED_LAGRANGIAN,
                configuration=Configuration.REFERENCE,
            )


class TestElementTypeGuard:
    """Element type guard message references Plan B phase B5."""

    def test_supported_element_types(self) -> None:
        members = {m for m in ElementType}
        assert members == {
            ElementType.HEX8,
            ElementType.TET4,
            ElementType.TET10,
            ElementType.HEX20,
        }, (
            "A new ElementType enum member was added without updating this test. "
            "Verify the new member is guarded correctly in ProblemIR.__post_init__ "
            "(add to the supported-values set or name its Plan B phase in the error)."
        )

    def test_non_hex8_guard_mentions_plan_b5(self) -> None:
        from types import SimpleNamespace

        ir = _valid_ir()
        patched = _plant_field(ir, "element_type", SimpleNamespace(value="hex27"))
        with pytest.raises(ValueError, match="Plan B phase B5"):
            patched.__post_init__()


# ---------------------------------------------------------------------------
# Invalid material models
# ---------------------------------------------------------------------------


class TestInvalidMaterial:
    """Unknown material model names are rejected; message names Plan B phases."""

    @pytest.mark.parametrize(
        "model",
        [
            "lemaitre_damage",
            "",
        ],
    )
    def test_unsupported_material_raises_with_plan_b_reference(self, model: str) -> None:
        with pytest.raises(ValueError, match="Plan B"):
            _valid_ir(material=MaterialSpec(model=model, params={}))


# ---------------------------------------------------------------------------
# Boundary condition validation
# ---------------------------------------------------------------------------


class TestBoundaryConditionValidation:
    """ProblemIR requires at least one BC; region names are checked when
    declared_regions is provided."""

    def test_empty_boundaries_raises(self) -> None:
        with pytest.raises(ValueError, match=r"[Bb]oundary"):
            _valid_ir(boundaries=())

    def test_bc_referencing_undeclared_region_raises_boundary_region_error(self) -> None:
        bcs = (BoundaryCondition(name="phantom_face", bc_type=BCType.DIRICHLET),)
        with pytest.raises(BoundaryRegionError, match="undeclared"):
            _valid_ir(boundaries=bcs, declared_regions=frozenset({"fix", "load"}))

    def test_bc_name_in_declared_regions_does_not_raise(self) -> None:
        bcs = (BoundaryCondition(name="fix", bc_type=BCType.DIRICHLET),)
        ir = _valid_ir(boundaries=bcs, declared_regions=frozenset({"fix"}))
        assert ir.boundaries[0].name == "fix"

    def test_no_declared_regions_skips_name_check(self) -> None:
        # Without declared_regions, any BC name is accepted.
        bcs = (BoundaryCondition(name="arbitrary_name_xyz", bc_type=BCType.DIRICHLET),)
        ir = _valid_ir(boundaries=bcs, declared_regions=None)
        assert ir.declared_regions is None


# ---------------------------------------------------------------------------
# Coordinate metadata consistency
# ---------------------------------------------------------------------------


class TestCoordinateMetadata:
    """Coordinate tuple lengths must match dim=3."""

    def test_too_few_spatial_coords_raises(self) -> None:
        with pytest.raises(ValueError, match="spatial"):
            _valid_ir(coord_spatial=("x", "y"))

    def test_too_many_spatial_coords_raises(self) -> None:
        with pytest.raises(ValueError, match="spatial"):
            _valid_ir(coord_spatial=("x", "y", "z", "w"))

    def test_too_few_material_coords_raises(self) -> None:
        with pytest.raises(ValueError, match="material"):
            _valid_ir(coord_material=("X",))

    def test_correct_coord_lengths_pass(self) -> None:
        ir = _valid_ir(coord_spatial=("x1", "x2", "x3"), coord_material=("X1", "X2", "X3"))
        assert ir.coord_spatial == ("x1", "x2", "x3")
        assert ir.coord_material == ("X1", "X2", "X3")


# ---------------------------------------------------------------------------
# Symbolic kinematics boundary: KinematicsResult from compute()
# ---------------------------------------------------------------------------


class TestSymbolicKinematicsBoundary:
    """Verify the symbolic layer's own input validation before the IR is reached.

    KinematicsResult is produced by mechdsl.symbolic.kinematics.compute().
    It rejects non-3D input directly, so the error surfaces at Layer 2 rather
    than propagating into ProblemIR construction.
    """

    def test_compute_rejects_dim_2_with_plan_b2_message(self) -> None:
        import sympy as sp

        from mechdsl.symbolic.kinematics import compute

        # 2-D displacement gradient symbols: should fail at Layer 2, not Layer 3
        u_syms_2d = [[sp.Integer(0)] * 2 for _ in range(2)]
        X_syms_2d = [sp.Symbol("X"), sp.Symbol("Y")]
        with pytest.raises(ValueError, match="Plan B phase B2"):
            compute(dim=2, u_symbols=u_syms_2d, X_symbols=X_syms_2d)

    def test_compute_accepts_3d_zero_gradient_gives_identity_F(self) -> None:
        import sympy as sp

        from mechdsl.symbolic.kinematics import compute

        # Zero displacement gradient → F = I₃, J = 1
        zero_grad = [[sp.Integer(0)] * 3 for _ in range(3)]
        X_syms = [sp.Symbol("X"), sp.Symbol("Y"), sp.Symbol("Z")]
        result = compute(dim=3, u_symbols=zero_grad, X_symbols=X_syms)
        assert sp.eye(3) == result.F, "F should be identity for zero displacement gradient"
        assert sp.Integer(1) == result.J, "J should be 1 for undeformed configuration"
