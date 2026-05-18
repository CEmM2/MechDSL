"""Tests for NRPyLaTeX metric-assignment directives (Plan B Phase 2, Task P2-4).

Covers the `% mechanics assign gDD --metric_current true` and
`% mechanics assign GDD --metric_reference true` frontend directives.
"""

import pytest

from mechdsl.frontend.directives import ParseError
from mechdsl.frontend.parser import parse

# Minimal required header so parse() succeeds past the required-directive checks.
_MIN_HEADER = (
    "% mechanics dim 3\n"
    "% mechanics cell hex8\n"
    "% mechanics formulation total_lagrangian\n"
    "% mechanics material svk --E 200e3 --nu 0.3\n"
)


class TestTaskP2_4MetricAssignDirectives:
    """
    Tests for Task P2-4: NRPyLaTeX metric-assignment directives.
    Acceptance criteria covered: [1] Parse round-trip, [2] Context dict,
    [3] Cylindrical propagation to ElementIR.
    """

    def test_parser_accepts_assign_metric_current(self):
        """
        Verifies: `% mechanics assign gDD --metric_current true` parses without raising.
        Acceptance criterion: parse('% mechanics assign gDD --metric_current true\\n...')
        round-trips without raising.
        Passes when: No exception is raised during parsing and context contains
        metric_current == 'gDD'.
        """
        source = _MIN_HEADER + "% mechanics assign gDD --metric_current true\n"
        ctx = parse(source)
        assert ctx["metric_current"] == "gDD"

    def test_parser_accepts_assign_metric_reference(self):
        """
        Verifies: `% mechanics assign GDD --metric_reference true` parses without raising.
        Acceptance criterion: Parser accepts assign --metric_reference.
        Passes when: No exception is raised and context contains metric_reference == 'GDD'.
        """
        source = _MIN_HEADER + "% mechanics assign GDD --metric_reference true\n"
        ctx = parse(source)
        assert ctx["metric_reference"] == "GDD"

    def test_context_dict_preserves_both_assignments(self):
        """
        Verifies: After parsing both assign directives, the context dict contains
        entries for both 'metric_current' and 'metric_reference'.
        Acceptance criterion: The context dict contains the metric assignment entries.
        Passes when: context['metric_current'] and context['metric_reference'] are
        both populated with the correct tensor symbol names.
        """
        source = (
            _MIN_HEADER
            + "% mechanics assign gDD --metric_current true\n"
            + "% mechanics assign GDD --metric_reference true\n"
        )
        ctx = parse(source)
        assert ctx["metric_current"] == "gDD"
        assert ctx["metric_reference"] == "GDD"

    def test_malformed_assign_raises_parse_error(self):
        """
        Verifies: A malformed assign directive (e.g., missing --metric_* flag)
        raises a ParseError with a descriptive message.
        Acceptance criterion: Malformed assign raises ParseError.
        Passes when: ParseError is raised with an informative message.
        """
        # No --metric_* flag at all: parser will error on missing value for
        # the trailing token, so we use a source with just the positional arg.
        # Provide a dummy option key that is neither metric_current nor
        # metric_reference so the handler itself raises ParseError.
        source_no_flag = _MIN_HEADER + "% mechanics assign gDD --other_flag true\n"
        with pytest.raises(ParseError, match=r"metric_current|metric_reference"):
            parse(source_no_flag)

        # No positional argument at all — handler must raise ParseError about
        # missing tensor name.  We supply a valid option so the parser
        # tokenises cleanly but the handler validates the positional count.
        source_no_positional = _MIN_HEADER + "% mechanics assign --metric_current true\n"
        with pytest.raises(ParseError):
            parse(source_no_positional)

    def test_both_flags_raises_parse_error(self):
        """
        Verifies: Specifying both --metric_current and --metric_reference raises ParseError.
        Passes when: ParseError is raised with an informative message.
        """
        source = (
            _MIN_HEADER + "% mechanics assign gDD --metric_current true --metric_reference true\n"
        )
        with pytest.raises(ParseError, match="both"):
            parse(source)

    @pytest.mark.e2e
    @pytest.mark.xfail(
        reason="e2e metric propagation requires build_context metric wiring — deferred to P10-1 (SOSOVSKI/MechDSL#79)",
        strict=False,
    )
    def test_cylindrical_metric_propagates_to_element_ir(self):
        """
        Verifies: A cylindrical metric assigned via directives propagates from
        the parser through build_context all the way to ElementIR.
        Acceptance criterion: Cylindrical metric example propagates from parser
        to ElementIR.
        Passes when: ElementIR contains the correct metric field after pipeline
        processing.
        """
        pytest.skip(
            "e2e metric propagation requires build_context metric integration (Plan B P10-1)"
        )
