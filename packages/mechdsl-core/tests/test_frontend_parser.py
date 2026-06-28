"""Tests for the LaTeX ``% mechanics`` directive parser (Plan A §A3).

Covers:

- The MVP example from ``PLAN-A.md §A3.5`` parses end to end.
- Each directive handler's happy path (``dim``, ``cell``, ``coord``,
  ``formulation``, ``material``, ``boundary``, ``index``).
- Syntax-error paths (unknown command, malformed option, missing value,
  unbalanced quotes, trailing comments, wrong positional count).
- Documented directive normalization (``bc``, ``field``, ``weak_form``,
  ``constitutive``, ``codegen``, ``verify``), including MVP-stable
  rejection for unsupported codegen / verification modes.
- Parser → :func:`build_context` round-trip equality.
- Supported-subset rejection propagates with Plan B phase pointers
  (analogues of parser IDs P2 / P5 / P6 from ``08-VERIFICATION.md``).
- :func:`parse_file` reads a file and returns the same dict.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from mechdsl import compile_latex
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

    def test_trailing_latex_comment_is_stripped(self) -> None:
        source = "% mechanics weak_form momentum --residual  % nonlinear residual form\n"
        assert scan_directives(source) == [(1, "weak_form momentum --residual")]

    def test_percent_inside_quoted_value_is_preserved(self) -> None:
        source = '% mechanics material svk --label "100% load case"  % trailing comment\n'
        assert scan_directives(source) == [(1, 'material svk --label "100% load case"')]

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
        assert bcs[0]["source_line"] == 11
        assert bcs[1]["name"] == "Gamma_t"
        assert bcs[1]["type"] == "neumann"
        assert bcs[1]["traction"] == "t_bar"
        assert bcs[1]["source_line"] == 12


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
                    "source_line": 11,
                },
                {"name": "Gamma_t", "type": "neumann", "traction": "t_bar", "source_line": 12},
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
# Documented directive normalization
# ---------------------------------------------------------------------------


class TestDocumentedDirectiveNormalization:
    """Documented P3 directive shapes normalize into explicit metadata."""

    def test_bc_alias_accepts_documented_dirichlet_and_neumann_shapes(self) -> None:
        source = (
            _MIN_HEADER
            + "% mechanics field u --type vector --space V --order 1\n"
            + "% mechanics bc dirichlet --field u --boundary left --value 0\n"
            + '% mechanics bc neumann --field u --boundary right --traction "0, -P/A"\n'
        )
        ctx = parse(source)

        assert ctx["boundaries"] == [
            {
                "name": "left",
                "type": "dirichlet",
                "field_name": "u",
                "source_line": 6,
                "value": 0,
            },
            {
                "name": "right",
                "type": "neumann",
                "field_name": "u",
                "source_line": 7,
                "traction": "0, -P/A",
            },
        ]

    def test_bc_alias_dirichlet_rejects_traction_payload(self) -> None:
        source = _MIN_HEADER + '% mechanics bc dirichlet --value 0 --traction "0 0 -1"\n'

        with pytest.raises(ParseError, match=r"bc dirichlet.*unknown option.*traction"):
            parse(source)

    def test_bc_alias_neumann_rejects_value_payload(self) -> None:
        source = _MIN_HEADER + '% mechanics bc neumann --traction "0 0 -1" --value 0\n'

        with pytest.raises(ParseError, match=r"bc neumann.*unknown option.*value"):
            parse(source)

    def test_bc_alias_numeric_neumann_reuses_legacy_traction_normalization(self) -> None:
        source = _MIN_HEADER + '% mechanics bc neumann --traction "0 0 -1000"\n'
        ctx = parse(source)

        assert ctx["boundaries"] == [
            {
                "name": "neumann_0",
                "type": "neumann",
                "field_name": "u",
                "source_line": 5,
                "traction": [0.0, 0.0, -1000.0],
            }
        ]

    def test_bc_alias_numeric_neumann_drives_f_ext_kernel(self) -> None:
        source = _MIN_HEADER + '% mechanics bc neumann --traction "0 0 -1000" --surface z1\n'
        bundle = compile_latex(source, profile="mvp")

        assert bundle.f_ext_kernel is not None
        assert "init_f_ext_from_neumann_neumann_0" in bundle.f_ext_kernel
        assert "Surface tag: 'z1'" in bundle.f_ext_kernel
        assert "-1000" in bundle.f_ext_kernel

    def test_bc_body_force_is_metadata_not_boundary_region(self) -> None:
        source = (
            _MIN_HEADER
            + "% mechanics field u --type vector --space V --order 1\n"
            + '% mechanics bc body_force --field u --value "0, -rho*g"\n'
        )
        ctx = parse(source)

        assert ctx["boundaries"] == []
        assert ctx["body_forces"] == [
            {
                "type": "body_force",
                "field_name": "u",
                "value": "0, -rho*g",
                "source_line": 6,
            }
        ]

    def test_legacy_boundary_syntax_remains_valid(self) -> None:
        source = _MIN_HEADER + "% mechanics boundary fix --type dirichlet --value 0\n"
        ctx = parse(source)
        assert ctx["boundaries"] == [
            {"name": "fix", "type": "dirichlet", "source_line": 5, "value": 0}
        ]

    def test_legacy_and_bc_boundaries_preserve_source_lines(self) -> None:
        source = (
            "\n"
            + _MIN_HEADER
            + "% mechanics boundary fix --type dirichlet --value 0\n"
            + '% mechanics bc neumann --field u --boundary load --traction "0 0 -1000"\n'
        )
        ctx = parse(source)

        assert ctx["boundaries"][0]["source_line"] == 6
        assert ctx["boundaries"][1]["source_line"] == 7

    def test_field_directives_preserve_field_metadata_and_source_line(self) -> None:
        source = (
            "\n"
            + _MIN_HEADER
            + "% mechanics field u --type vector --space V --order 1\n"
            + "% mechanics field p --type scalar --space Q --order 0\n"
        )
        ctx = parse(source)

        assert ctx["fields"] == [
            {
                "name": "u",
                "kind": "vector",
                "space": "V",
                "order": 1,
                "source_line": 6,
            },
            {
                "name": "p",
                "kind": "scalar",
                "space": "Q",
                "order": 0,
                "source_line": 7,
            },
        ]
        assert ctx["directive_locations"]["field"] == [6, 7]

    def test_field_negative_order_raises_line_specific_parse_error(self) -> None:
        source = _MIN_HEADER + "% mechanics field u --type vector --space V --order -1\n"
        with pytest.raises(ParseError, match=r"line 5:.*--order.*non-negative"):
            parse(source)

    @pytest.mark.parametrize(
        ("body", "role"),
        [
            ("constitutive Psi --strain_energy", "strain_energy"),
            ("constitutive sigma --cauchy", "cauchy"),
            ("constitutive S --pk2", "pk2"),
        ],
    )
    def test_constitutive_directives_normalize_roles(self, body: str, role: str) -> None:
        ctx = parse(_MIN_HEADER + f"% mechanics {body}\n")
        assert ctx["constitutive"] == [{"symbol": body.split()[1], "role": role, "source_line": 5}]

    def test_weak_form_linear_shape_normalizes_variational_metadata(self) -> None:
        source = _MIN_HEADER + "% mechanics weak_form momentum --test v --trial u --domain Omega\n"
        ctx = parse(source)

        assert ctx["weak_forms"] == [
            {
                "name": "momentum",
                "kind": "bilinear",
                "test": "v",
                "trial": "u",
                "domain": "Omega",
                "source_line": 5,
            }
        ]
        assert ctx["residual_contract"]["weak_form_label"] == "momentum"
        assert ctx["residual_contract"]["metadata"]["kind"] == "bilinear"

    def test_weak_form_residual_shape_normalizes_residual_metadata(self) -> None:
        ctx = parse(_MIN_HEADER + "% mechanics weak_form momentum --residual\n")

        assert ctx["weak_forms"] == [{"name": "momentum", "kind": "residual", "source_line": 5}]
        assert ctx["residual_contract"] == {
            "terms": [],
            "weak_form_label": "momentum",
            "metadata": {"kind": "residual", "source_line": 5},
        }

    def test_weak_form_residual_accepts_trailing_latex_comment(self) -> None:
        ctx = parse(_MIN_HEADER + "% mechanics weak_form momentum --residual  % nonlinear\n")

        assert ctx["weak_forms"] == [{"name": "momentum", "kind": "residual", "source_line": 5}]

    def test_duplicate_weak_form_rejects_with_existing_label(self) -> None:
        source = (
            _MIN_HEADER
            + "% mechanics weak_form momentum --test v --trial u --domain Omega\n"
            + "% mechanics weak_form energy --residual\n"
        )
        with pytest.raises(
            ParseError, match=r"line 6:.*overwrite an existing residual_contract.*'momentum'"
        ):
            parse(source)

    def test_codegen_taichi_shape_normalizes_metadata(self) -> None:
        ctx = parse(_MIN_HEADER + "% mechanics codegen --target taichi --output cantilever.py\n")

        assert ctx["codegen"] == {
            "target": "taichi",
            "output": "cantilever.py",
            "source_line": 5,
        }

    @pytest.mark.parametrize("target", ["mfem", "moose"])
    def test_codegen_non_taichi_targets_reject_cleanly(self, target: str) -> None:
        source = _MIN_HEADER + f"% mechanics codegen --target {target} --output out.txt\n"
        with pytest.raises(ParseError, match=f"line 5:.*target {target!r}.*MVP-stable"):
            parse(source)

    def test_compile_latex_rejects_non_taichi_codegen_on_mvp_path(self) -> None:
        source = (
            _MIN_HEADER
            + "% mechanics boundary fix --type dirichlet --value 0\n"
            + "% mechanics codegen --target mfem --output cantilever_mfem.cpp\n"
        )
        with pytest.raises(ParseError, match=r"target 'mfem'.*MVP-stable"):
            compile_latex(source, profile="mvp")

    def test_verify_benchmark_shape_normalizes_metadata(self) -> None:
        source = "% mechanics dim 3\n% mechanics cell hex8\n% mechanics formulation total_lagrangian\n% mechanics material svk --E 200e9 --nu 0.3\n% mechanics verify --benchmark cantilever_beam --E 200e9 --nu 0.3 --P 1e6\n"
        ctx = parse(source)

        assert ctx["verify"] == [
            {
                "kind": "benchmark",
                "source_line": 5,
                "benchmark": "cantilever_beam",
                "params": {"E": 200e9, "nu": 0.3, "P": 1e6},
            }
        ]

    def test_verify_patch_test_shape_normalizes_metadata(self) -> None:
        ctx = parse(_MIN_HEADER + "% mechanics verify --patch_test\n")
        assert ctx["verify"] == [{"kind": "patch_test", "source_line": 5}]

    def test_verify_patch_test_rejects_extra_options(self) -> None:
        source = _MIN_HEADER + "% mechanics verify --patch_test --E 200e9\n"
        with pytest.raises(ParseError, match=r"line 5:.*verify.*unknown option\(s\)"):
            parse(source)

    def test_verify_mms_method_rejects_cleanly(self) -> None:
        source = _MIN_HEADER + "% mechanics verify --method mms --order 2\n"
        with pytest.raises(ParseError, match=r"line 5:.*method mms.*not supported"):
            parse(source)

    def test_assign_is_not_deferred(self) -> None:
        """``assign`` must be in HANDLERS (not DEFERRED_DIRECTIVES) after P2-4."""
        from mechdsl.frontend.directives import DEFERRED_DIRECTIVES, HANDLERS

        assert "assign" in HANDLERS, "'assign' must be registered in HANDLERS after Task P2-4"
        assert "assign" not in DEFERRED_DIRECTIVES, "'assign' must NOT be in DEFERRED_DIRECTIVES"

    @pytest.mark.parametrize(
        "command",
        ["field", "weak_form", "constitutive", "codegen", "verify", "bc"],
    )
    def test_documented_p3_commands_are_handlers_not_deferred(self, command: str) -> None:
        from mechdsl.frontend.directives import DEFERRED_DIRECTIVES, HANDLERS

        assert command in HANDLERS
        assert command not in DEFERRED_DIRECTIVES


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
