"""Tests for Layer 1 — Frontend build_context() function (Sprint 2 Phase 2).

Tests for P2-T6 (build_context implementation), P2-T7 (validation), and P2-T8 (parser tests).
Covers 08-VERIFICATION.md parser test IDs P1, P2, P5, P6.
"""

from __future__ import annotations

import pytest

from mechdsl.frontend import build_context
from mechdsl.symbolic.convected import UnsupportedError

_MVP_PARAMS = {"E": 210e9, "nu": 0.3}
_MVP_BOUNDARIES = [{"face": "x0", "type": "dirichlet", "dofs": [0, 1, 2]}]


class TestBuildContextBasics:
    """Tests for P2-T6: build_context() basic functionality.

    Acceptance criteria:
    - Returns dict with all expected keys
    - Valid MVP inputs produce correct dict
    """

    def test_valid_mvp_input_returns_correct_dict(self) -> None:
        """
        Verifies: valid MVP inputs (dim=3, hex8, total_lagrangian, svk) produce correct context dict.

        Acceptance criterion: Valid MVP inputs produce correct dict
        Passes when: returned dict has expected keys and values
        Related to: P2-T6 acceptance criterion 2
        """
        ctx = build_context(
            dim=3,
            cell_type="hex8",
            formulation="total_lagrangian",
            material_type="svk",
            params=_MVP_PARAMS,
            boundaries=_MVP_BOUNDARIES,
        )

        assert ctx["dim"] == 3
        assert ctx["cell_type"] == "hex8"
        assert ctx["formulation"] == "total_lagrangian"
        assert ctx["material_type"] == "svk"
        assert ctx["params"] == _MVP_PARAMS
        assert ctx["boundaries"] == _MVP_BOUNDARIES
        assert ctx["coord_system"] == "cartesian"

    def test_dict_contains_all_required_keys(self) -> None:
        """
        Verifies: returned dict contains all required keys (dim, cell_type, formulation, material_type, params, boundaries, coord_system).

        Acceptance criterion: Dict contains all required keys
        Passes when: returned dict has all 7 expected keys
        Related to: P2-T6 acceptance criterion 1
        """
        ctx = build_context(
            dim=3,
            cell_type="hex8",
            formulation="total_lagrangian",
            material_type="svk",
            params=_MVP_PARAMS,
            boundaries=_MVP_BOUNDARIES,
        )

        required_keys = {
            "dim",
            "cell_type",
            "formulation",
            "material_type",
            "params",
            "boundaries",
            "coord_system",
            "hourglass_coef",
            # Plan B phase B5 (task P5-6) added the integration / hourglass
            # selectors so the LaTeX `% mechanics cell` directive can carry
            # element-discretisation choices end-to-end.
            "integration",
            "hourglass",
        }
        assert required_keys == set(ctx.keys())


class TestBuildContextValidation:
    """Tests for P2-T7: build_context() input validation.

    Acceptance criteria:
    - Each unsupported input raises UnsupportedError
    - Error messages include plan-phase pointers
    - Valid MVP inputs still work
    """

    def test_dim_2_raises_unsupported_error(self) -> None:
        """
        Verifies: dim=2 raises UnsupportedError with plan-phase pointer.

        Acceptance criterion: dim≠3 raises UnsupportedError
        Passes when: UnsupportedError raised, message mentions Plan B phase B2
        Related to: P2-T7 implementation step 1
        """
        with pytest.raises(UnsupportedError, match="Plan B phase B2"):
            build_context(
                dim=2,
                cell_type="hex8",
                formulation="total_lagrangian",
                material_type="svk",
                params=_MVP_PARAMS,
                boundaries=_MVP_BOUNDARIES,
            )

    def test_cell_type_tet4_full_is_accepted(self) -> None:
        """
        Verifies: cell_type='tet4' with default integration='full' is now accepted.

        After Plan B phase B5 task P5-6 the frontend dispatches through
        :class:`mechdsl.ir.element_factory.ElementFactory`, which supports
        all four MVP topologies (hex8, hex20, tet4, tet10) at full
        integration.  This test pins the new behaviour so a regression
        that re-introduces the legacy ``cell_type != "hex8"`` guard is
        caught immediately.
        """
        ctx = build_context(
            dim=3,
            cell_type="tet4",
            formulation="total_lagrangian",
            material_type="svk",
            params=_MVP_PARAMS,
            boundaries=_MVP_BOUNDARIES,
        )
        assert ctx["cell_type"] == "tet4"
        assert ctx["integration"] == "full"
        assert ctx["hourglass"] is None

    def test_cell_type_tet4_reduced_raises_unsupported_error(self) -> None:
        """
        Verifies: cell_type='tet4' with integration='reduced' is rejected.

        Reduced integration is hex8-only (Plan B §B5.4 / P5-4); requesting
        it on tet4 must raise :class:`UnsupportedError` with a Plan B phase
        B5 reference so the user knows where the support gap lives.
        """
        with pytest.raises(UnsupportedError, match="Plan B phase B5"):
            build_context(
                dim=3,
                cell_type="tet4",
                formulation="total_lagrangian",
                material_type="svk",
                params=_MVP_PARAMS,
                boundaries=_MVP_BOUNDARIES,
                integration="reduced",
            )

    def test_formulation_updated_lagrangian_is_accepted(self) -> None:
        """
        Verifies: formulation='updated_lagrangian' is accepted after Plan B §B1.3.

        Acceptance criterion: UL parses into a valid context dict without raising.
        Passes when: build_context returns a dict with formulation='updated_lagrangian'.
        Related to: Plan B P1-1 (ConfigurationIR extension).
        """
        ctx = build_context(
            dim=3,
            cell_type="hex8",
            formulation="updated_lagrangian",
            material_type="svk",
            params=_MVP_PARAMS,
            boundaries=_MVP_BOUNDARIES,
        )
        assert ctx["formulation"] == "updated_lagrangian"
        assert ctx["cell_type"] == "hex8"

    def test_material_lemaitre_damage_raises_unsupported_error(self) -> None:
        """
        Verifies: material_type='lemaitre_damage' raises UnsupportedError.

        Acceptance criterion: material_type not in supported set raises UnsupportedError
        Passes when: UnsupportedError raised, message lists supported models
        Related to: P2-T7 implementation step 4
        """
        with pytest.raises(UnsupportedError, match="lemaitre_damage") as exc_info:
            build_context(
                dim=3,
                cell_type="hex8",
                formulation="total_lagrangian",
                material_type="lemaitre_damage",
                params=_MVP_PARAMS,
                boundaries=_MVP_BOUNDARIES,
            )
        msg = str(exc_info.value)
        assert "j2_power_law" in msg
        assert "svk" in msg

    def test_coord_system_non_cartesian_raises_unsupported_error(self) -> None:
        """
        Verifies: coord_system != 'cartesian' raises UnsupportedError.

        Acceptance criterion: only 'cartesian' accepted for MVP
        Passes when: UnsupportedError raised with the Plan B phase B2 pointer
        """
        with pytest.raises(UnsupportedError, match="Plan B phase B2"):
            build_context(
                dim=3,
                cell_type="hex8",
                formulation="total_lagrangian",
                material_type="svk",
                params=_MVP_PARAMS,
                boundaries=_MVP_BOUNDARIES,
                coord_system="cylindrical",
            )


class TestBuildContextParserTests:
    """Tests for P2-T8: Parser test IDs P1, P2, P5, P6 from 08-VERIFICATION.md.

    Acceptance criteria:
    - All tests pass
    - Covers P1, P2, P5, P6 test IDs from 08-VERIFICATION.md
    """

    def test_P1_valid_mvp_source_correct_dict_structure(self) -> None:
        """
        Parser test ID P1: Valid MVP source → correct dict structure.

        Verifies: valid MVP inputs produce dict with correct keys and types.
        Acceptance criterion: P1 test passes
        Passes when: returned dict has all keys with correct types
        Related to: P2-T8 implementation step 2 and 08-VERIFICATION.md P1
        """
        ctx = build_context(
            dim=3,
            cell_type="hex8",
            formulation="total_lagrangian",
            material_type="svk",
            params=_MVP_PARAMS,
            boundaries=_MVP_BOUNDARIES,
        )

        # Verify all required keys are present
        assert set(ctx.keys()) == {
            "dim",
            "cell_type",
            "formulation",
            "material_type",
            "params",
            "boundaries",
            "coord_system",
            "hourglass_coef",
            # Plan B phase B5 (task P5-6) — see TestBuildContextBasics
            # for the rationale.
            "integration",
            "hourglass",
        }

        # Verify correct types for each key
        assert isinstance(ctx["dim"], int)
        assert isinstance(ctx["cell_type"], str)
        assert isinstance(ctx["formulation"], str)
        assert isinstance(ctx["material_type"], str)
        assert isinstance(ctx["params"], dict)
        assert isinstance(ctx["boundaries"], list)
        assert isinstance(ctx["coord_system"], str)

    def test_P2_unknown_material_error_with_suggestion(self) -> None:
        """
        Parser test ID P2: Unknown material → UnsupportedError with suggestion.

        Verifies: unknown material_type raises UnsupportedError with helpful error message.
        Acceptance criterion: P2 test passes
        Passes when: UnsupportedError raised with suggestion for supported materials
        Related to: P2-T8 implementation step 3 and 08-VERIFICATION.md P2
        """
        with pytest.raises(UnsupportedError) as exc_info:
            build_context(
                dim=3,
                cell_type="hex8",
                formulation="total_lagrangian",
                material_type="unknown_material",
                params=_MVP_PARAMS,
                boundaries=_MVP_BOUNDARIES,
            )

        msg = str(exc_info.value)
        # Error message should name the unsupported material
        assert "unknown_material" in msg
        # Error message should list the supported models as a suggestion
        assert "svk" in msg
        assert "j2_power_law" in msg

    def test_P5_missing_dim_error(self) -> None:
        """
        Parser test ID P5: Missing dim → appropriate error.

        Verifies: missing or invalid dim parameter raises appropriate error.
        Acceptance criterion: P5 test passes
        Passes when: appropriate error raised (TypeError or ValueError)
        Related to: P2-T8 implementation step 4 and 08-VERIFICATION.md P5
        """
        # dim is a required positional argument; omitting it raises TypeError
        with pytest.raises(TypeError):
            build_context(  # type: ignore[call-arg]
                cell_type="hex8",
                formulation="total_lagrangian",
                material_type="svk",
                params=_MVP_PARAMS,
                boundaries=_MVP_BOUNDARIES,
            )

    def test_P6_convected_coords_cartesian_default(self) -> None:
        """
        Parser test ID P6: Convected coordinate handling (Cartesian default).

        Verifies: coord_system defaults to 'cartesian' and is present in returned dict.
        Acceptance criterion: P6 test passes
        Passes when: returned dict has coord_system='cartesian' when not specified
        Related to: P2-T8 implementation step 5 and 08-VERIFICATION.md P6
        """
        # Call without coord_system argument — should default to 'cartesian'
        ctx = build_context(3, "hex8", "total_lagrangian", "svk", {}, [])

        assert "coord_system" in ctx
        assert ctx["coord_system"] == "cartesian"
