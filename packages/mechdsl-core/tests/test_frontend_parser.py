"""Tests for the LaTeX ``% mechanics`` directive parser (Plan A §A3).

Covers:

- The MVP example from ``PLAN-A.md §A3.5`` parses end to end.
- Each directive handler's happy path (``dim``, ``cell``, ``coord``,
  ``formulation``, ``material``, ``boundary``, ``index``).
- Syntax-error paths (unknown command, malformed option, missing value,
  unbalanced quotes, trailing comments, wrong positional count).
- Deferred-directive rejection (``field``, ``weak_form``, ``constitutive``,
  ``codegen``, ``verify``) with Plan B pointer.
- Parser → :func:`build_context` round-trip equality.
- Supported-subset rejection propagates with Plan B phase pointers
  (analogues of parser IDs P2 / P5 / P6 from ``08-VERIFICATION.md``).
- :func:`parse_file` reads a file and returns the same dict.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from mechdsl.frontend import build_context, parse, parse_file
from mechdsl.frontend.directives import ParseError
from mechdsl.frontend.parser import scan_directives
from mechdsl.symbolic.convected import UnsupportedError

if TYPE_CHECKING:
    from pathlib import Path

# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------


_MVP_EXAMPLE = r"""
\documentclass{article}
\begin{document}

% mechanics dim 3
% mechanics cell hex8
% mechanics coord spatial x y z
% mechanics coord material X Y Z
% mechanics material svk --E 200e3 --nu 0.3
% mechanics formulation total_lagrangian
% mechanics boundary Gamma_u --type dirichlet --value 0 --components 0 1 2
% mechanics boundary Gamma_t --type neumann --traction "t_bar"

The governing equation is $\nabla \cdot \boldsymbol{P} + \boldsymbol{b} = 0$.

\end{document}
"""


_J2_EXAMPLE = r"""
% mechanics dim 3
% mechanics cell hex8
% mechanics formulation total_lagrangian
% mechanics material j2_power_law --E 200e3 --nu 0.3 --sigma_y0 250 --K 500 --n 0.5
% mechanics boundary Gamma_u --type dirichlet --value 0
"""


# ---------------------------------------------------------------------------
# Scanner behaviour
# ---------------------------------------------------------------------------


class TestScanDirectives:
    """``scan_directives`` should find only whole-line ``% mechanics`` comments."""

    def test_empty_source_returns_empty_list(self) -> None:
        assert scan_directives("") == []

    def test_content_lines_are_ignored(self) -> None:
        source = "some text\nmore text\n$x = y$\n"
        assert scan_directives(source) == []

    def test_regular_latex_comments_are_ignored(self) -> None:
        source = "% this is a normal comment\n% another one\n"
        assert scan_directives(source) == []

    def test_line_numbers_are_one_indexed(self) -> None:
        source = "\n\n% mechanics dim 3\n"
        assert scan_directives(source) == [(3, "dim 3")]

    def test_leading_whitespace_is_allowed(self) -> None:
        source = "    % mechanics dim 3\n"
        assert scan_directives(source) == [(1, "dim 3")]

    def test_no_whitespace_before_prefix_is_allowed(self) -> None:
        source = "%mechanics dim 3\n"
        assert scan_directives(source) == [(1, "dim 3")]

    def test_prefix_must_be_a_whole_word(self) -> None:
        # '% mechanicsfoo' is a plain LaTeX comment, NOT a malformed directive.
        source = "% mechanicsfoo dim 3\n"
        assert scan_directives(source) == []


# ---------------------------------------------------------------------------
# Happy-path end-to-end
# ---------------------------------------------------------------------------


class TestMVPExampleEndToEnd:
    """The PLAN-A §A3.5 MVP example parses into the expected context dict."""

    def test_mvp_example_parses_without_error(self) -> None:
        ctx = parse(_MVP_EXAMPLE)
        assert ctx is not None

    def test_mvp_example_has_build_context_keys(self) -> None:
        ctx = parse(_MVP_EXAMPLE)
        required = {
            "dim",
            "cell_type",
            "formulation",
            "material_type",
            "params",
            "boundaries",
            "coord_system",
        }
        assert required <= set(ctx.keys())

    def test_mvp_example_scalar_fields(self) -> None:
        ctx = parse(_MVP_EXAMPLE)
        assert ctx["dim"] == 3
        assert ctx["cell_type"] == "hex8"
        assert ctx["formulation"] == "total_lagrangian"
        assert ctx["material_type"] == "svk"
        assert ctx["coord_system"] == "cartesian"

    def test_mvp_example_material_params_are_numeric(self) -> None:
        ctx = parse(_MVP_EXAMPLE)
        assert ctx["params"] == {"E": 200e3, "nu": 0.3}
        assert isinstance(ctx["params"]["E"], float)
        assert isinstance(ctx["params"]["nu"], float)

    def test_mvp_example_coord_families_preserved(self) -> None:
        ctx = parse(_MVP_EXAMPLE)
        assert ctx["coord_spatial"] == ("x", "y", "z")
        assert ctx["coord_material"] == ("X", "Y", "Z")

    def test_mvp_example_boundaries_in_source_order(self) -> None:
        ctx = parse(_MVP_EXAMPLE)
        bcs = ctx["boundaries"]
        assert len(bcs) == 2
        assert bcs[0]["name"] == "Gamma_u"
        assert bcs[0]["type"] == "dirichlet"
        assert bcs[0]["value"] == 0
        assert bcs[0]["components"] == [0, 1, 2]
        assert bcs[1]["name"] == "Gamma_t"
        assert bcs[1]["type"] == "neumann"
        assert bcs[1]["traction"] == "t_bar"


class TestJ2Example:
    """J2 power-law hardening example parses with the five required params."""

    def test_j2_material_params(self) -> None:
        ctx = parse(_J2_EXAMPLE)
        assert ctx["material_type"] == "j2_power_law"
        assert ctx["params"] == {
            "E": 200e3,
            "nu": 0.3,
            "sigma_y0": 250,
            "K": 500,
            "n": 0.5,
        }


# ---------------------------------------------------------------------------
# Build-context round-trip
# ---------------------------------------------------------------------------


class TestBuildContextRoundTrip:
    """Parser output must match ``build_context(...)`` with equivalent args."""

    def test_parser_matches_build_context_core_keys(self) -> None:
        parsed = parse(_MVP_EXAMPLE)
        programmatic = build_context(
            dim=3,
            cell_type="hex8",
            formulation="total_lagrangian",
            material_type="svk",
            params={"E": 200e3, "nu": 0.3},
            boundaries=[
                {
                    "name": "Gamma_u",
                    "type": "dirichlet",
                    "value": 0,
                    "components": [0, 1, 2],
                },
                {"name": "Gamma_t", "type": "neumann", "traction": "t_bar"},
            ],
        )
        # The seven build_context keys must match exactly.
        for key in (
            "dim",
            "cell_type",
            "formulation",
            "material_type",
            "params",
            "boundaries",
            "coord_system",
        ):
            assert parsed[key] == programmatic[key], f"mismatch on key={key!r}"


# ---------------------------------------------------------------------------
# Per-handler sanity
# ---------------------------------------------------------------------------


_MIN_HEADER = (
    "% mechanics dim 3\n"
    "% mechanics cell hex8\n"
    "% mechanics formulation total_lagrangian\n"
    "% mechanics material svk --E 1 --nu 0.3\n"
)


class TestIndexDirective:
    """``% mechanics index`` is stored but not consumed by build_context."""

    def test_index_spatial_and_material_accumulate(self) -> None:
        source = (
            _MIN_HEADER + "% mechanics index spatial i j k\n" + "% mechanics index material I J K\n"
        )
        ctx = parse(source)
        assert ctx["indices_spatial"] == ("i", "j", "k")
        assert ctx["indices_material"] == ("I", "J", "K")

    def test_index_multiple_spatial_lines_concatenate(self) -> None:
        source = _MIN_HEADER + "% mechanics index spatial i j\n" + "% mechanics index spatial k l\n"
        ctx = parse(source)
        assert ctx["indices_spatial"] == ("i", "j", "k", "l")

    def test_index_unknown_family_raises(self) -> None:
        source = _MIN_HEADER + "% mechanics index foo i\n"
        with pytest.raises(ParseError, match="family must be"):
            parse(source)


class TestCoordDirective:
    """coord family must be spatial/material/convected and non-duplicated."""

    def test_duplicate_coord_family_raises(self) -> None:
        source = (
            _MIN_HEADER + "% mechanics coord spatial x y z\n" + "% mechanics coord spatial a b c\n"
        )
        with pytest.raises(ParseError, match="declared twice"):
            parse(source)

    def test_convected_family_stored_but_subset_rejects_later(self) -> None:
        # The coord handler accepts 'convected', but downstream any
        # non-Cartesian use would be rejected.  Here we only test that
        # storing it does not itself crash.
        source = _MIN_HEADER + "% mechanics coord convected theta1 theta2 theta3\n"
        ctx = parse(source)
        assert ctx["coord_convected"] == ("theta1", "theta2", "theta3")


# ---------------------------------------------------------------------------
# Syntax error paths
# ---------------------------------------------------------------------------


class TestSyntaxErrors:
    """Malformed directives raise ParseError with a line number."""

    def test_unknown_command_raises(self) -> None:
        with pytest.raises(ParseError, match="unknown directive"):
            parse("% mechanics wobble 3\n")

    def test_option_without_value_raises(self) -> None:
        source = _MIN_HEADER + "% mechanics boundary fix --type\n"
        with pytest.raises(ParseError, match="missing a value"):
            parse(source)

    def test_option_followed_by_another_option_raises(self) -> None:
        source = _MIN_HEADER + "% mechanics boundary fix --type --value 0\n"
        with pytest.raises(ParseError, match="missing a value"):
            parse(source)

    def test_empty_option_name_raises(self) -> None:
        source = _MIN_HEADER + "% mechanics dim -- 3\n"
        with pytest.raises(ParseError, match="empty option name"):
            parse(source)

    def test_unbalanced_quote_raises(self) -> None:
        source = _MIN_HEADER + '% mechanics boundary fix --type "dirichlet\n'
        with pytest.raises(ParseError, match="unbalanced quoting"):
            parse(source)

    def test_dim_non_integer_raises(self) -> None:
        source = "% mechanics dim three\n"
        with pytest.raises(ParseError, match="must be an integer"):
            parse(source)

    def test_wrong_positional_count_for_dim(self) -> None:
        source = "% mechanics dim 3 also\n"
        with pytest.raises(ParseError, match="exactly 1 positional"):
            parse(source)

    def test_boundary_missing_name(self) -> None:
        source = _MIN_HEADER + "% mechanics boundary --type dirichlet\n"
        with pytest.raises(ParseError, match="exactly one"):
            parse(source)

    def test_boundary_missing_type_option(self) -> None:
        source = _MIN_HEADER + "% mechanics boundary fix\n"
        with pytest.raises(ParseError, match="missing required option --type"):
            parse(source)

    def test_boundary_components_non_integer_raises(self) -> None:
        source = _MIN_HEADER + "% mechanics boundary fix --type dirichlet --components 0 x 2\n"
        with pytest.raises(ParseError, match="list of integers"):
            parse(source)


class TestMissingRequiredDirectives:
    """``parse`` enforces that the four required directives are present."""

    def test_missing_dim_raises(self) -> None:
        source = (
            "% mechanics cell hex8\n"
            "% mechanics formulation total_lagrangian\n"
            "% mechanics material svk --E 1 --nu 0.3\n"
        )
        with pytest.raises(ParseError, match=r"missing required.*dim"):
            parse(source)

    def test_missing_cell_raises(self) -> None:
        source = (
            "% mechanics dim 3\n"
            "% mechanics formulation total_lagrangian\n"
            "% mechanics material svk --E 1 --nu 0.3\n"
        )
        with pytest.raises(ParseError, match=r"missing required.*cell"):
            parse(source)

    def test_missing_formulation_raises(self) -> None:
        source = (
            "% mechanics dim 3\n% mechanics cell hex8\n% mechanics material svk --E 1 --nu 0.3\n"
        )
        with pytest.raises(ParseError, match=r"missing required.*formulation"):
            parse(source)

    def test_missing_material_raises(self) -> None:
        source = (
            "% mechanics dim 3\n% mechanics cell hex8\n% mechanics formulation total_lagrangian\n"
        )
        with pytest.raises(ParseError, match=r"missing required.*material"):
            parse(source)


# ---------------------------------------------------------------------------
# Deferred directives
# ---------------------------------------------------------------------------


class TestDeferredDirectives:
    """Non-MVP directives from 02-LATEX-DSL.md raise with a Plan B pointer."""

    @pytest.mark.parametrize(
        "body",
        [
            "field u --type vector --space V --order 1",
            "weak_form momentum --test v --trial u",
            "constitutive Psi --strain_energy",
            "codegen --target taichi --output out.py",
            "verify --benchmark cantilever",
        ],
    )
    def test_deferred_directive_rejected(self, body: str) -> None:
        source = _MIN_HEADER + f"% mechanics {body}\n"
        with pytest.raises(ParseError, match="Plan B"):
            parse(source)

    def test_assign_is_not_deferred(self) -> None:
        """``assign`` must be in HANDLERS (not DEFERRED_DIRECTIVES) after P2-4."""
        from mechdsl.frontend.directives import DEFERRED_DIRECTIVES, HANDLERS

        assert "assign" in HANDLERS, "'assign' must be registered in HANDLERS after Task P2-4"
        assert "assign" not in DEFERRED_DIRECTIVES, "'assign' must NOT be in DEFERRED_DIRECTIVES"


# ---------------------------------------------------------------------------
# Supported-subset rejection (P2 / P5 / P6 analogues)
# ---------------------------------------------------------------------------


class TestSupportedSubsetRejection:
    """Semantic rejections bubble up as UnsupportedError with Plan B pointers."""

    def test_dim_2_rejected_with_plan_b2(self) -> None:
        source = (
            "% mechanics dim 2\n"
            "% mechanics cell hex8\n"
            "% mechanics formulation total_lagrangian\n"
            "% mechanics material svk --E 1 --nu 0.3\n"
        )
        with pytest.raises(UnsupportedError, match="Plan B phase B2"):
            parse(source)

    def test_updated_lagrangian_is_accepted_after_plan_b_b1(self) -> None:
        """Plan B §B1.3 promoted UL from rejected to supported. The directive
        now parses into a valid context dict."""
        source = (
            "% mechanics dim 3\n"
            "% mechanics cell hex8\n"
            "% mechanics formulation updated_lagrangian\n"
            "% mechanics material svk --E 1 --nu 0.3\n"
        )
        ctx = parse(source)
        assert ctx["formulation"] == "updated_lagrangian"

    def test_tet4_reduced_rejected_with_plan_b5(self) -> None:
        """tet4 with default full integration is now accepted (P5-6); the
        Plan B §B5 rejection path is preserved by exercising a still-invalid
        combination — reduced integration on tet4."""
        source = (
            "% mechanics dim 3\n"
            "% mechanics cell tet4 --integration reduced\n"
            "% mechanics formulation total_lagrangian\n"
            "% mechanics material svk --E 1 --nu 0.3\n"
        )
        with pytest.raises(UnsupportedError, match="Plan B phase B5"):
            parse(source)

    def test_unknown_material_lists_supported_models(self) -> None:
        source = (
            "% mechanics dim 3\n"
            "% mechanics cell hex8\n"
            "% mechanics formulation total_lagrangian\n"
            "% mechanics material lemaitre_damage --D0 0.1\n"
        )
        with pytest.raises(UnsupportedError) as excinfo:
            parse(source)
        msg = str(excinfo.value)
        assert "lemaitre_damage" in msg
        assert "svk" in msg
        assert "j2_power_law" in msg


# ---------------------------------------------------------------------------
# parse_file
# ---------------------------------------------------------------------------


class TestParseFile:
    """``parse_file`` reads a file and returns the same dict as ``parse``."""

    def test_parse_file_matches_parse(self, tmp_path: Path) -> None:
        source_path = tmp_path / "mvp.tex"
        source_path.write_text(_MVP_EXAMPLE, encoding="utf-8")
        from_file = parse_file(source_path)
        from_string = parse(_MVP_EXAMPLE)
        assert from_file == from_string

    def test_parse_file_accepts_str_path(self, tmp_path: Path) -> None:
        source_path = tmp_path / "mvp.tex"
        source_path.write_text(_MVP_EXAMPLE, encoding="utf-8")
        ctx = parse_file(str(source_path))
        assert ctx["dim"] == 3
