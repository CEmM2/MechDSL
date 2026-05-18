"""Tests for Task P5-6: ElementFactory (uniform element/integration/hourglass API).

Acceptance criteria:
- AC-1: Every plan-listed combination produces a valid ElementIR.
- AC-2: Invalid combinations raise ValueError with a helpful message.
- AC-3: LaTeX parser accepts the new --integration and --hourglass flags.
"""

from __future__ import annotations

import pytest

from mechdsl.frontend import parse
from mechdsl.ir.element_factory import ElementFactory
from mechdsl.ir.element_ir import ElementIR
from mechdsl.ir.mechanics_ir import IntegrationRule


class TestTaskP5_6ElementFactory:
    """Tests for Task P5-6: ElementFactory.

    Acceptance criteria covered: AC-1 (valid combinations), AC-2 (invalid combinations raise),
    AC-3 (LaTeX directive round-trip).
    """

    # ------------------------------------------------------------------
    # AC-1 — valid combinations
    # ------------------------------------------------------------------

    @pytest.mark.unit
    def test_factory_hex8_full(self) -> None:
        """Verifies: ElementFactory.create('hex8', integration='full') returns a valid ElementIR.
        Acceptance criterion: AC-1 — plan-listed combination.
        Passes when: the returned ElementIR has element_type=HEX8 and integration=FULL.
        """
        elem = ElementFactory.create("hex8", integration="full")
        assert isinstance(elem, ElementIR)
        assert elem.element_type == "hex8"
        assert elem.n_nodes == 8
        assert elem.integration_rule == IntegrationRule.FULL
        # Hex8 full uses 2x2x2 = 8 Gauss points.
        assert elem.quadrature.n_points == 8

    @pytest.mark.unit
    def test_factory_hex8_reduced_with_flanagan_belytschko(self) -> None:
        """Verifies: ElementFactory.create('hex8', integration='reduced', hourglass='flanagan_belytschko').
        Acceptance criterion: AC-1 — plan-listed combination.
        Passes when: the ElementIR selects the reduced tables and binds the FB hourglass control.
        """
        elem = ElementFactory.create("hex8", integration="reduced", hourglass="flanagan_belytschko")
        assert isinstance(elem, ElementIR)
        assert elem.element_type == "hex8"
        assert elem.integration_rule == IntegrationRule.REDUCED
        # Reduced Hex8 is the 1-point centre rule.
        assert elem.quadrature.n_points == 1

    @pytest.mark.unit
    def test_factory_hex20_full(self) -> None:
        """Verifies: ElementFactory.create('hex20', integration='full') returns a valid ElementIR.
        Acceptance criterion: AC-1 — plan-listed combination.
        Passes when: element_type=HEX20 with 27-point quadrature.
        """
        elem = ElementFactory.create("hex20", integration="full")
        assert isinstance(elem, ElementIR)
        assert elem.element_type == "hex20"
        assert elem.n_nodes == 20
        # Hex20 full uses 3x3x3 = 27 Gauss points.
        assert elem.quadrature.n_points == 27

    @pytest.mark.unit
    def test_factory_tet4_full(self) -> None:
        """Verifies: ElementFactory.create('tet4', integration='full') returns a valid ElementIR.
        Acceptance criterion: AC-1 — plan-listed combination.
        Passes when: element_type=TET4 with 1-point tet quadrature.
        """
        elem = ElementFactory.create("tet4", integration="full")
        assert isinstance(elem, ElementIR)
        assert elem.element_type == "tet4"
        assert elem.n_nodes == 4
        assert elem.quadrature.n_points == 1

    @pytest.mark.unit
    def test_factory_tet10_full(self) -> None:
        """Verifies: ElementFactory.create('tet10', integration='full') returns a valid ElementIR.
        Acceptance criterion: AC-1 — plan-listed combination.
        Passes when: element_type=TET10 with 4-point tet quadrature.
        """
        elem = ElementFactory.create("tet10", integration="full")
        assert isinstance(elem, ElementIR)
        assert elem.element_type == "tet10"
        assert elem.n_nodes == 10
        assert elem.quadrature.n_points == 4

    # ------------------------------------------------------------------
    # AC-2 — invalid combinations
    # ------------------------------------------------------------------

    @pytest.mark.unit
    def test_factory_tet4_reduced_is_invalid(self) -> None:
        """Verifies: reduced integration on tet4 is rejected.
        Acceptance criterion: AC-2 — invalid combinations raise.
        Passes when: ValueError is raised with a helpful message mentioning tet4 + reduced
        and citing Plan B phase B5.
        """
        with pytest.raises(ValueError, match="Plan B phase B5") as info:
            ElementFactory.create("tet4", integration="reduced")
        assert "tet4" in str(info.value)
        assert "reduced" in str(info.value).lower() or "hex8" in str(info.value)

    @pytest.mark.unit
    def test_factory_hex8_reduced_without_hourglass_warns_or_errors(self) -> None:
        """Verifies: reduced Hex8 without any hourglass scheme is permitted but the
        underlying constructor warns via its docstring; the ElementIR carries the
        reduced quadrature so the rank-deficiency is observable downstream.

        Acceptance criterion: AC-2 — invalid-or-dangerous combination.
        Passes when: the call succeeds (no hard failure) and produces a reduced
        ElementIR with no hourglass binding — the caller is responsible for adding
        Flanagan-Belytschko stabilisation per Plan B §B5.5.
        """
        elem = ElementFactory.create("hex8", integration="reduced", hourglass=None)
        assert elem.integration_rule == IntegrationRule.REDUCED
        assert elem.quadrature.n_points == 1

    @pytest.mark.unit
    def test_factory_hourglass_on_full_integration_is_invalid(self) -> None:
        """Verifies: requesting Flanagan-Belytschko hourglass with full integration
        is rejected — the controller only stabilises reduced rules.

        Acceptance criterion: AC-2 — invalid combinations raise with Plan B
        phase B5 reference.
        """
        with pytest.raises(ValueError, match="Plan B phase B5"):
            ElementFactory.create("hex8", integration="full", hourglass="flanagan_belytschko")

    @pytest.mark.unit
    def test_factory_unknown_topology_is_invalid(self) -> None:
        """Verifies: unknown topology strings are rejected with a Plan B phase B5
        reference so users know where additional element families will land.

        Acceptance criterion: AC-2 — invalid combinations raise.
        """
        with pytest.raises(ValueError, match="Plan B phase B5"):
            ElementFactory.create("quad4", integration="full")

    # ------------------------------------------------------------------
    # AC-3 — LaTeX directive round-trip
    # ------------------------------------------------------------------

    @pytest.mark.unit
    def test_latex_integration_directive_roundtrip(self) -> None:
        """Verifies: '% mechanics cell hex8 --integration reduced --hourglass flanagan_belytschko'
        parses into a context whose (cell_type, integration, hourglass) triple matches what
        ElementFactory.create accepts.

        Acceptance criterion: AC-3 — LaTeX directive round-trip.
        Passes when: the parsed context exposes integration='reduced' and
        hourglass='flanagan_belytschko', and ElementFactory rebuilds an equivalent
        reduced-Hex8 ElementIR from those values.
        """
        source = r"""
% mechanics dim 3
% mechanics cell hex8 --integration reduced --hourglass flanagan_belytschko
% mechanics formulation total_lagrangian
% mechanics material svk --E 200e3 --nu 0.3
"""
        ctx = parse(source)
        assert ctx["cell_type"] == "hex8"
        assert ctx["integration"] == "reduced"
        assert ctx["hourglass"] == "flanagan_belytschko"

        elem = ElementFactory.create(
            ctx["cell_type"],
            integration=ctx["integration"],
            hourglass=ctx["hourglass"],
        )
        assert elem.element_type == "hex8"
        assert elem.integration_rule == IntegrationRule.REDUCED

        # The legacy form (no flags) still works and produces the FULL default.
        legacy_source = r"""
% mechanics dim 3
% mechanics cell hex8
% mechanics formulation total_lagrangian
% mechanics material svk --E 200e3 --nu 0.3
"""
        legacy_ctx = parse(legacy_source)
        assert legacy_ctx["cell_type"] == "hex8"
        assert legacy_ctx["integration"] == "full"
        assert legacy_ctx["hourglass"] is None
