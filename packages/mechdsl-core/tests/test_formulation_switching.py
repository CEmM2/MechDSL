"""Tests for Task P1-6: formulation switching (directive + codegen dispatch).

Plan: dev/design_docs/PLAN-B.md lines 66-70 (B1.5 Formulation switching).

Verifies that a single LaTeX source (or programmatic ``build_context`` call)
emits either a TL or UL generated solver file by flipping one directive.
The ConfigurationIR auto-inference (P1-6) makes this seamless: callers need
only set ``formulation='updated_lagrangian'`` and ProblemIR.__post_init__
infers ``configuration=CURRENT`` automatically.

Also verifies that non-UL supported-subset rejections are unchanged.
"""

from __future__ import annotations

import ast
from typing import Any

import pytest

from mechdsl.codegen.artifact import ArtifactBundle
from mechdsl.codegen.taichi_printer import emit
from mechdsl.frontend import build_context, parse
from mechdsl.ir.mechanics_ir import Configuration, ProblemIR
from mechdsl.lowering.fe_localise import localise_and_optimize
from mechdsl.symbolic.convected import UnsupportedError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_UL_LATEX_SOURCE = r"""
% mechanics dim 3
% mechanics cell hex8
% mechanics formulation updated_lagrangian
% mechanics material svk --E 200e3 --nu 0.3
% mechanics boundary fix --type dirichlet --value 0 --components 0 1 2
% mechanics boundary load --type neumann --traction "t_bar"
"""

_TL_LATEX_SOURCE = r"""
% mechanics dim 3
% mechanics cell hex8
% mechanics formulation total_lagrangian
% mechanics material svk --E 200e3 --nu 0.3
% mechanics boundary fix --type dirichlet --value 0 --components 0 1 2
% mechanics boundary load --type neumann --traction "t_bar"
"""

_MVP_PARAMS: dict[str, float] = {"E": 200e3, "nu": 0.3}
_MVP_BOUNDARIES: list[dict[str, Any]] = [
    {"name": "fix", "type": "dirichlet", "value": 0, "components": [0, 1, 2]},
    {"name": "load", "type": "neumann", "traction": "t_bar"},
]


def _compile_from_context(ctx: dict[str, Any]) -> str:
    """End-to-end compile: frontend context dict → emitted Python source."""
    problem_ir = ProblemIR.from_context(ctx)
    loc_result, plans = localise_and_optimize(problem_ir)
    bundle = ArtifactBundle.from_pipeline(problem_ir, loc_result, plans)
    return emit(bundle)


class TestTaskP1_6FormulationSwitching:
    """
    Tests for Task P1-6: Formulation switching (directive + codegen dispatch)

    Acceptance criteria covered:
      1. UL directive parses without raising (existing test inverted — see above)
      2. UL emits different source than TL on the same inputs (new stub below)
      3. Existing non-UL rejection tests still pass (existing coverage)
    """

    @pytest.mark.integration
    def test_ul_directive_parses_without_raising(self) -> None:
        """
        Verifies: parsing a LaTeX source with `% mechanics formulation
        updated_lagrangian` returns a valid context dict, and the full
        compile pipeline produces syntactically valid Python.

        Acceptance criterion: "parse('% mechanics formulation updated_lagrangian...')
        returns a valid context dict (no UnsupportedError)."
        """
        ctx = parse(_UL_LATEX_SOURCE)
        assert ctx["formulation"] == "updated_lagrangian"

        # The context dict compiles end-to-end to valid Python.
        source = _compile_from_context(ctx)
        ast.parse(source)

    @pytest.mark.integration
    def test_ul_emits_different_source_than_tl_on_same_inputs(self) -> None:
        """
        Verifies: compiling the same SVK + Hex8 problem under TL and UL yields
        syntactically distinct generated Python source bodies (both parseable).

        Acceptance criterion: "The generator emits distinct source bodies for
        TL and UL on the same problem (both syntactically valid Python)."
        """
        ul_ctx = parse(_UL_LATEX_SOURCE)
        tl_ctx = parse(_TL_LATEX_SOURCE)

        ul_source = _compile_from_context(ul_ctx)
        tl_source = _compile_from_context(tl_ctx)

        # Both must be syntactically valid Python.
        ast.parse(ul_source)
        ast.parse(tl_source)

        # They must differ (UL uses Cauchy/dNdx/detj; TL uses PK1/dNdX/detJ0).
        assert ul_source != tl_source, "UL and TL should emit different source for the same problem"

        # Smoke check: UL source contains UL-specific markers.
        assert "sigma" in ul_source
        assert "dNdx" in ul_source
        assert "detj" in ul_source

    @pytest.mark.integration
    def test_tl_rejection_behaviour_unchanged_for_other_non_mvp_values(self) -> None:
        """
        Verifies: the supported-subset rejection still fires for other non-MVP
        values (tet4, dim=2, lemaitre_damage) — only the UL rejection was lifted.

        Acceptance criterion: "The frontend-subset-rejection test suite still
        passes for dim/cell/material rejections."
        """
        # dim=2 still rejected
        with pytest.raises(UnsupportedError, match="Plan B phase B2"):
            build_context(
                dim=2,
                cell_type="hex8",
                formulation="total_lagrangian",
                material_type="svk",
                params=_MVP_PARAMS,
                boundaries=_MVP_BOUNDARIES,
            )

        # tet4 + reduced integration is still rejected; tet4 + full is accepted
        # (ElementFactory wiring).
        with pytest.raises(UnsupportedError, match="Plan B"):
            build_context(
                dim=3,
                cell_type="tet4",
                formulation="total_lagrangian",
                material_type="svk",
                params=_MVP_PARAMS,
                boundaries=_MVP_BOUNDARIES,
                integration="reduced",
            )

        # lemaitre_damage (damage models) still rejected
        with pytest.raises(UnsupportedError, match="lemaitre_damage"):
            build_context(
                dim=3,
                cell_type="hex8",
                formulation="total_lagrangian",
                material_type="lemaitre_damage",
                params=_MVP_PARAMS,
                boundaries=_MVP_BOUNDARIES,
            )

    @pytest.mark.integration
    def test_programmatic_build_context_ul_compiles_end_to_end(self) -> None:
        """Programmatic build_context with UL compiles without explicit
        configuration — ProblemIR auto-infers Configuration.CURRENT from
        formulation='updated_lagrangian' (Plan B §B1.5)."""
        ctx = build_context(
            dim=3,
            cell_type="hex8",
            formulation="updated_lagrangian",
            material_type="svk",
            params=_MVP_PARAMS,
            boundaries=_MVP_BOUNDARIES,
        )
        source = _compile_from_context(ctx)
        ast.parse(source)

        # Verify the ProblemIR auto-inferred CURRENT configuration.
        problem_ir = ProblemIR.from_context(ctx)
        assert problem_ir.configuration is Configuration.CURRENT
