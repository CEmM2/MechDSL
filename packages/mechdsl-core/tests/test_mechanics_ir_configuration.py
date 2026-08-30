"""Tests for Task P1-1: ConfigurationIR extension (reference/current tagging).

These tests cover the acceptance criteria for the reference/current
configuration tagging added to Mechanics IR / Element IR.

Plan: dev/design_docs/PLAN-B.md lines 48-55 (B1.3 Configuration-aware IR refactor)
"""

from __future__ import annotations

import pytest

from mechdsl.frontend import UnsupportedError, build_context, parse
from mechdsl.ir.mechanics_ir import (
    BCType,
    BoundaryCondition,
    Configuration,
    ElementType,
    Formulation,
    MaterialSpec,
    ProblemIR,
)
from mechdsl.lowering.fe_localise import localise


def _valid_bc() -> tuple[BoundaryCondition, ...]:
    return (BoundaryCondition(name="fix", bc_type=BCType.DIRICHLET),)


def _svk_material() -> MaterialSpec:
    return MaterialSpec(model="svk", params={"E": 200e3, "nu": 0.3})


def _plan_a_tl_ir() -> ProblemIR:
    """Plan A baseline: TL + SVK + Hex8 + default (REFERENCE) configuration."""
    return ProblemIR(
        dim=3,
        formulation=Formulation.TOTAL_LAGRANGIAN,
        element_type=ElementType.HEX8,
        material=_svk_material(),
        boundaries=_valid_bc(),
    )


def _plan_b_ul_ir() -> ProblemIR:
    """Plan B UL path: UL + SVK + Hex8 + explicit CURRENT configuration."""
    return ProblemIR(
        dim=3,
        formulation=Formulation.UPDATED_LAGRANGIAN,
        element_type=ElementType.HEX8,
        material=_svk_material(),
        boundaries=_valid_bc(),
        configuration=Configuration.CURRENT,
    )


class TestTaskP1_1:
    """
    Tests for Task P1-1: ConfigurationIR extension (reference/current tagging)

    Acceptance criteria:
      1. ConfigurationIR enum exists and round-trips through construction.
      2. Constructing ProblemIR with formulation='updated_lagrangian' does NOT raise.
      3. All existing fast tests still pass (regression guard, exercised by full suite).
      4. parse('% mechanics formulation updated_lagrangian ...') returns a dict with formulation='updated_lagrangian'.
      5. The Plan A rejection tests are updated (TestFormulationGuard) or kept as regression
         guards pinning REFERENCE configuration behaviour.
    """

    @pytest.mark.unit
    def test_configuration_enum_members(self) -> None:
        """Configuration enum exposes exactly REFERENCE and CURRENT.

        Acceptance criterion: "ConfigurationIR exists, is frozen, round-trips through
        dataclass construction."
        """
        members = {m.name for m in Configuration}
        assert members == {"REFERENCE", "CURRENT"}
        assert Configuration.REFERENCE.value == "reference"
        assert Configuration.CURRENT.value == "current"

    @pytest.mark.unit
    def test_problem_ir_reference_configuration_matches_plan_a_baseline(self) -> None:
        """ProblemIR defaults to REFERENCE so Plan A construction is unchanged.

        Acceptance criterion: "All 998 fast tests still pass, untouched."
        A Plan A ProblemIR built WITHOUT the new argument must receive
        Configuration.REFERENCE by default, and round-trip cleanly through to_dict.
        """
        ir = _plan_a_tl_ir()
        assert ir.configuration is Configuration.REFERENCE

        d = ir.to_dict()
        # Older tests may not know about this key, but it MUST round-trip.
        assert d["configuration"] == "reference"

        ir_round = ProblemIR.from_dict(d)
        assert ir_round.configuration is Configuration.REFERENCE
        assert ir_round.formulation is Formulation.TOTAL_LAGRANGIAN

    @pytest.mark.unit
    def test_problem_ir_current_configuration_constructs_without_raising(self) -> None:
        """UL + CURRENT constructs without hitting the Plan A 'Plan B phase B1' rejection.

        Acceptance criterion: "Constructing ProblemIR with formulation='updated_lagrangian'
        does NOT raise."
        """
        ir = _plan_b_ul_ir()
        assert ir.formulation is Formulation.UPDATED_LAGRANGIAN
        assert ir.configuration is Configuration.CURRENT
        assert ir.material.model == "svk"

    @pytest.mark.unit
    def test_problem_ir_configuration_consistency_with_formulation(self) -> None:
        """UL formulation requires CURRENT configuration; TL requires REFERENCE.

        Acceptance criterion (derived from plan B1.3 "stress measures tagged with
        configuration" + scope rule "gate the UL path behind the new enum"): the two
        sentinels must stay consistent so downstream emitters never see a half-set IR.
        """
        # TL with CURRENT is invalid.
        with pytest.raises(ValueError, match="configuration"):
            ProblemIR(
                dim=3,
                formulation=Formulation.TOTAL_LAGRANGIAN,
                element_type=ElementType.HEX8,
                material=_svk_material(),
                boundaries=_valid_bc(),
                configuration=Configuration.CURRENT,
            )
        # UL with REFERENCE is invalid.
        with pytest.raises(ValueError, match="configuration"):
            ProblemIR(
                dim=3,
                formulation=Formulation.UPDATED_LAGRANGIAN,
                element_type=ElementType.HEX8,
                material=_svk_material(),
                boundaries=_valid_bc(),
                configuration=Configuration.REFERENCE,
            )

    @pytest.mark.unit
    def test_fe_localise_selects_reference_for_tl_and_current_for_ul(self) -> None:
        """fe_localise must tag the emitted ElementIR with the correct configuration.

        Acceptance criterion: "ElementIR geometry mapping switches between reference (TL)
        and current (UL) Jacobians." For P1-1 the switch is carried by a string field on
        ElementIR; P1-2 will fill in the actual j-Jacobian slots.
        """
        tl_loc = localise(_plan_a_tl_ir())
        assert tl_loc.element_ir.configuration == "reference"

        ul_loc = localise(_plan_b_ul_ir())
        assert ul_loc.element_ir.configuration == "current"

    @pytest.mark.unit
    def test_frontend_parse_accepts_updated_lagrangian_directive(self) -> None:
        """parse() returns a valid context dict for the UL directive — no UnsupportedError.

        Acceptance criterion: "parse('% mechanics formulation updated_lagrangian...') returns
        a dict with formulation='updated_lagrangian'."
        """
        source = (
            "% mechanics dim 3\n"
            "% mechanics cell hex8\n"
            "% mechanics formulation updated_lagrangian\n"
            "% mechanics material svk --E 1 --nu 0.3\n"
            "% mechanics boundary fix --type dirichlet\n"
        )
        ctx = parse(source)
        assert ctx["formulation"] == "updated_lagrangian"
        assert ctx["cell_type"] == "hex8"
        assert ctx["dim"] == 3

        # build_context must also accept UL directly.
        ctx2 = build_context(
            dim=3,
            cell_type="hex8",
            formulation="updated_lagrangian",
            material_type="svk",
            params={"E": 1.0, "nu": 0.3},
            boundaries=[],
        )
        assert ctx2["formulation"] == "updated_lagrangian"

    @pytest.mark.unit
    def test_supported_subset_rejection_still_fires_for_unrelated_guards(self) -> None:
        """Removing the UL rejection must NOT remove the other subset guards.

        Acceptance criterion: "Plan A rejection tests kept as a regression guard pinning
        reference configuration behaviour" — the other rejection surfaces remain in effect.
        """
        with pytest.raises(UnsupportedError, match="Plan B phase B2"):
            build_context(
                dim=2,
                cell_type="hex8",
                formulation="total_lagrangian",
                material_type="svk",
                params={"E": 1.0, "nu": 0.3},
                boundaries=[],
            )
        # tet4 + reduced integration is rejected.
        # tet4 with the default full integration is supported.
        with pytest.raises(UnsupportedError, match="Plan B phase B5"):
            build_context(
                dim=3,
                cell_type="tet4",
                formulation="total_lagrangian",
                material_type="svk",
                params={"E": 1.0, "nu": 0.3},
                boundaries=[],
                integration="reduced",
            )
        # Unknown material still rejected.
        with pytest.raises(UnsupportedError, match="lemaitre_damage"):
            build_context(
                dim=3,
                cell_type="hex8",
                formulation="total_lagrangian",
                material_type="lemaitre_damage",
                params={},
                boundaries=[],
            )
