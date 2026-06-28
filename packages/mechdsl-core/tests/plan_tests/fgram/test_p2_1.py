"""Tests for fgram P2-1 math-aware compile_latex plumbing."""

from __future__ import annotations

import pytest

import mechdsl.frontend as frontend
from mechdsl import compile_latex
from mechdsl.frontend import FrontendSemanticError, parse, parse_compile_context
from mechdsl.ir.mechanics_ir import ProblemIR

_DIRECTIVES_ONLY = (
    "% mechanics dim 3\n"
    "% mechanics cell hex8\n"
    "% mechanics formulation total_lagrangian\n"
    "% mechanics material svk --E 200e3 --nu 0.3\n"
    "% mechanics boundary fix --type dirichlet --value 0 --components 0 1 2\n"
)

_SUPPORTED_MATH_SOURCE = (
    _DIRECTIVES_ONLY
    + "% declare FUU --dim 3\n"
    + "% declare AUU --dim 3\n"
    + "$A^{i I} = F^{i I}$\n"
)

# ``\sin`` is in math_parser._UNSUPPORTED_FUNCTIONS (full-grammar deferral).
# ``\det`` is NOT used here: Phase 4 (P4-1) promoted it to a supported node,
# so it no longer exercises the frontend rejection path.
_UNSUPPORTED_MATH_SOURCE = _DIRECTIVES_ONLY + "% declare FUU --dim 3\n" + "$T = \\sin{F}$\n"

_PROSE_GOVERNING_EQUATION_SOURCE = (
    _DIRECTIVES_ONLY
    + "The governing equation is "
    + "$\\nabla \\cdot \\boldsymbol{P} + \\boldsymbol{b} = 0$.\n"
)

_WEAK_FORM_ACTIONABLE_MATH_SOURCE = (
    _DIRECTIVES_ONLY
    + "% mechanics weak_form momentum --residual\n"
    + "$\\nabla \\cdot \\boldsymbol{P} + \\boldsymbol{b} = 0$\n"
)

_NOSPACE_WEAK_FORM_ACTIONABLE_MATH_SOURCE = (
    _DIRECTIVES_ONLY
    + "%mechanics weak_form momentum --residual\n"
    + "$\\nabla \\cdot \\boldsymbol{P} + \\boldsymbol{b} = 0$\n"
)

_NOSPACE_CONSTITUTIVE_ACTIONABLE_MATH_SOURCE = (
    _DIRECTIVES_ONLY + "%mechanics constitutive Psi --strain_energy\n" + "$J = \\det{F}$\n"
)


@pytest.mark.unit
def test_parse_compile_context_preserves_directive_only_context_exactly() -> None:
    """Directive-only compile frontend semantics stay byte-for-byte boring."""
    assert parse_compile_context(_DIRECTIVES_ONLY) == parse(_DIRECTIVES_ONLY)


@pytest.mark.unit
def test_parse_compile_context_ignores_prose_math_without_mechanics_math_context() -> None:
    """Narrative equations in directive-only examples must not invoke NRPyLaTeX."""
    assert parse_compile_context(_PROSE_GOVERNING_EQUATION_SOURCE) == parse(
        _PROSE_GOVERNING_EQUATION_SOURCE
    )


@pytest.mark.integration
def test_compile_latex_math_bearing_source_reaches_semantic_bundle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A supported equation must flow through the math-aware frontend path."""
    original = frontend.parse_with_math
    saw_math_bundle: list[bool] = []

    def _spy_parse_with_math(source: str) -> dict:
        context = original(source)
        saw_math_bundle.append("math" in context)
        return context

    monkeypatch.setattr(frontend, "parse_with_math", _spy_parse_with_math)

    bundle = compile_latex(_SUPPORTED_MATH_SOURCE, profile="mvp")

    assert saw_math_bundle == [True]
    assert bundle.problem_ir_dict["material"]["model"] == "svk"
    assert bundle.element_ir_summary["element_type"] == "hex8"


@pytest.mark.parametrize(
    "source",
    [
        _WEAK_FORM_ACTIONABLE_MATH_SOURCE,
        _NOSPACE_WEAK_FORM_ACTIONABLE_MATH_SOURCE,
        _NOSPACE_CONSTITUTIVE_ACTIONABLE_MATH_SOURCE,
    ],
)
@pytest.mark.integration
def test_compile_latex_actionable_mechanics_math_fails_before_problem_ir(
    source: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Metadata-tagged equations are actionable and fail at the frontend boundary."""
    problem_ir_calls: list[dict] = []

    def _sentinel_from_context(ctx: dict) -> ProblemIR:
        problem_ir_calls.append(ctx)
        raise AssertionError("ProblemIR.from_context must not run for unsupported math")

    monkeypatch.setattr(ProblemIR, "from_context", _sentinel_from_context)

    with pytest.raises(FrontendSemanticError, match="before IR construction"):
        compile_latex(source, profile="mvp")

    assert problem_ir_calls == []


@pytest.mark.integration
def test_compile_latex_unsupported_math_fails_before_problem_ir(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unsupported math-bearing input is rejected at the frontend boundary."""
    problem_ir_calls: list[dict] = []

    def _sentinel_from_context(ctx: dict) -> ProblemIR:
        problem_ir_calls.append(ctx)
        raise AssertionError("ProblemIR.from_context must not run for unsupported math")

    monkeypatch.setattr(ProblemIR, "from_context", _sentinel_from_context)

    with pytest.raises(FrontendSemanticError, match="before IR construction"):
        compile_latex(_UNSUPPORTED_MATH_SOURCE, profile="mvp")

    assert problem_ir_calls == []
