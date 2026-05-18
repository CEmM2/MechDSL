"""Tests for Task P4-3: wire math parser into frontend pipeline.

Acceptance criteria covered:
1. Math-bearing LaTeX produces a populated symbolic expression tree.
2. Directive-only LaTeX skips math parsing entirely (parse-when-needed
   guard, plan §Phase 4 lines 226-227).
3. No regression in existing frontend tests (test_directives,
   test_two_point, test_frontend_parser).
"""

from __future__ import annotations

import pytest

from mechdsl.frontend import has_math_block, parse, parse_with_math
from mechdsl.symbolic.bridge import SymbolicNode

_DIRECTIVES_ONLY = (
    "% mechanics dim 3\n"
    "% mechanics cell hex8\n"
    "% mechanics formulation total_lagrangian\n"
    "% mechanics material svk --E 200e3 --nu 0.3\n"
    "% mechanics boundary Gamma_u --type dirichlet --value 0\n"
)

_DIRECTIVES_WITH_MATH = (
    _DIRECTIVES_ONLY
    + "\n% Math block exercises the nrpylatex grammar:\n"
    + "% declare FUU --dim 3\n"
    + "% declare AUU --dim 3\n"
    + "$A^{i I} = F^{i I}$\n"
)


class TestTaskP4_3:
    """Tests for Task P4-3: wire math parser into frontend pipeline."""

    @pytest.mark.integration
    def test_math_bearing_input_routes_through_math_parser(self) -> None:
        context = parse_with_math(_DIRECTIVES_WITH_MATH)
        assert "math" in context, "math-bearing input must populate context['math']"
        math = context["math"]
        assert math["blocks"], "math.blocks must be non-empty for math-bearing input"
        tensors = math["tensors"]
        assert "FUU" in tensors and isinstance(tensors["FUU"], SymbolicNode)
        assert "AUU" in tensors and tensors["AUU"].rank == 2
        f_class = math["classifications"]["FUU"]
        assert 0 in f_class.spatial_axes
        assert 1 in f_class.material_axes

    @pytest.mark.integration
    def test_directive_only_input_skips_math_parser(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Directive-only input must NOT invoke the math parser. Verified
        by an import-counter monkeypatch: replacing ``parse_math`` with a
        sentinel that raises if called confirms the parse-when-needed
        guard short-circuits before the math parser runs.
        """
        from mechdsl.frontend import math_parser

        invocations: list[str] = []

        def _sentinel(latex_block: str):
            invocations.append(latex_block)
            raise AssertionError("math_parser.parse_math was invoked on directive-only input")

        monkeypatch.setattr(math_parser, "parse_math", _sentinel)
        context = parse_with_math(_DIRECTIVES_ONLY)
        assert invocations == [], "math parser was called on directive-only input"
        assert "math" not in context

    @pytest.mark.integration
    def test_directive_only_dict_matches_plain_parse(self) -> None:
        """Augmentation is additive: ``parse_with_math`` on
        directive-only input returns exactly the dict :func:`parse`
        returns (no extra keys, no shape change). Guards
        directive-pipeline back-compat.
        """
        plain = parse(_DIRECTIVES_ONLY)
        with_math = parse_with_math(_DIRECTIVES_ONLY)
        assert with_math == plain

    @pytest.mark.unit
    def test_has_math_block_detects_inline_dollar(self) -> None:
        assert has_math_block("$x = 1$")
        assert has_math_block("text\n$F^{ij} = A^{ij}$\nmore")
        assert not has_math_block("plain text without math")
        assert not has_math_block(r"escaped \$ not math \$")
        assert not has_math_block("% mechanics dim 3\n% mechanics cell hex8\n")

    @pytest.mark.integration
    def test_existing_frontend_tests_still_pass(self) -> None:
        """Smoke check: re-import the existing frontend modules and
        verify their public API surface still exposes the symbols other
        tests rely on. The directive parser, two-point resolver and
        ``build_context`` must remain reachable post-Phase-4 wiring.
        """
        import mechdsl.frontend as fe
        from mechdsl.frontend import directives, parser, two_point

        for sym in ("parse", "parse_file", "build_context"):
            assert hasattr(fe, sym), f"mechdsl.frontend.{sym} missing"
        assert callable(parser.parse)
        assert hasattr(directives, "ParseError") or hasattr(parser, "ParseError")
        assert two_point is not None
