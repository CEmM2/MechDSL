"""Regression tests for deferred PR-review follow-ups.

Each class pins the behaviour change requested in a ``gemini-code-assist``
review comment that was triaged into a GitHub issue and deferred:

- #272 — bare single-char LaTeX indices (``\\sigma_i``) keep index metadata.
- #273 — comma-separated traction values are rejected, not silently accepted.
- #274 — ``from_latex_semantics`` rejects a non-mapping ``residual_contract``
  and duplicate weak-form declarations (a ``weak_forms`` list with >1 entry).
"""

from __future__ import annotations

import pytest

from mechdsl.frontend.directives import ParseError, _parse_traction
from mechdsl.frontend.math_parser import _extract_indexed_occurrences
from mechdsl.ir.mechanics_ir import ProblemIR, ResidualContract


class TestTractionCommaRejection:
    """Issue #273: comma-separated traction must raise, not pass through as a name."""

    def test_comma_separated_spaced_rejected(self) -> None:
        with pytest.raises(ParseError, match="space-separated"):
            _parse_traction("0, 0, -1000", line_no=7)

    def test_comma_separated_unspaced_rejected(self) -> None:
        with pytest.raises(ParseError, match="space-separated"):
            _parse_traction("0,0,-1000", line_no=7)

    def test_space_separated_numeric_still_parses(self) -> None:
        assert _parse_traction("0 0 -1000", line_no=1) == [0.0, 0.0, -1000.0]

    def test_symbolic_name_still_passes_through(self) -> None:
        assert _parse_traction("t_bar", line_no=1) == "t_bar"

    def test_symbolic_comma_expression_still_passes_through(self) -> None:
        # A comma-bearing expression with a non-numeric component is a symbolic
        # traction (documented contract) and must NOT be rejected.
        assert _parse_traction("0, -P/A", line_no=1) == "0, -P/A"


class TestBareLatexIndices:
    r"""Issue #272: ``\sigma_i`` (no braces) must record its index, not drop it."""

    def test_bare_single_subscript(self) -> None:
        (occ,) = _extract_indexed_occurrences(r"\sigma_i")
        assert occ.indices == ("i",)

    def test_bare_matches_braced_form(self) -> None:
        (bare,) = _extract_indexed_occurrences(r"\sigma_i")
        (braced,) = _extract_indexed_occurrences(r"\sigma_{i}")
        assert bare.indices == braced.indices == ("i",)

    def test_bare_subscript_and_superscript(self) -> None:
        (occ,) = _extract_indexed_occurrences(r"F_i^J")
        assert occ.indices == ("i", "J")

    def test_braced_two_point_still_parses(self) -> None:
        (occ,) = _extract_indexed_occurrences(r"F_{iI}")
        assert occ.indices == ("i", "I")


class TestResidualContractGuard:
    """Issue #274: a non-mapping ``residual_contract`` is rejected explicitly."""

    def test_list_of_contracts_rejected(self) -> None:
        with pytest.raises(ValueError, match="single weak-form contract"):
            ProblemIR._residual_contract_from_context(
                {"residual_contract": [{"weak_form_label": "a"}, {"weak_form_label": "b"}]}
            )

    def test_scalar_residual_contract_rejected(self) -> None:
        with pytest.raises(ValueError, match="single weak-form contract"):
            ProblemIR._residual_contract_from_context({"residual_contract": "galerkin"})

    def test_absent_residual_contract_returns_none(self) -> None:
        assert ProblemIR._residual_contract_from_context({}) is None

    def test_valid_mapping_still_builds_contract(self) -> None:
        contract = ProblemIR._residual_contract_from_context(
            {"residual_contract": {"weak_form_label": "galerkin", "terms": ["internal_force"]}}
        )
        assert isinstance(contract, ResidualContract)
        assert contract.weak_form_label == "galerkin"

    def test_multiple_weak_forms_rejected(self) -> None:
        """A ``weak_forms`` list with >1 entry is a duplicate singular-field decl."""
        with pytest.raises(ValueError, match="2 weak forms"):
            ProblemIR._residual_contract_from_context(
                {
                    "residual_contract": {"weak_form_label": "a"},
                    "weak_forms": [{"weak_form_label": "a"}, {"weak_form_label": "b"}],
                }
            )

    def test_multiple_weak_forms_rejected_without_contract(self) -> None:
        """The duplicate guard fires even if no ``residual_contract`` is present,
        so the duplicate forms are not silently dropped."""
        with pytest.raises(ValueError, match="weak forms"):
            ProblemIR._residual_contract_from_context(
                {"weak_forms": [{"weak_form_label": "a"}, {"weak_form_label": "b"}]}
            )

    def test_single_weak_form_alongside_contract_still_builds(self) -> None:
        """The normal directive-layer output — one ``residual_contract`` next to a
        single-entry ``weak_forms`` list — must NOT be rejected (regression)."""
        contract = ProblemIR._residual_contract_from_context(
            {
                "residual_contract": {"weak_form_label": "galerkin", "terms": ["internal_force"]},
                "weak_forms": [{"weak_form_label": "galerkin"}],
            }
        )
        assert isinstance(contract, ResidualContract)
        assert contract.weak_form_label == "galerkin"
